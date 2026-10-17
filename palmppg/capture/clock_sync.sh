#!/usr/bin/env bash
# clock_sync.sh: clock discipline on the recording Pi at shift start and shift end (protocol section 4.1).
#
# Usage
#   clock_sync.sh <operator> [unit_id] [log_path]            step the Pi clock with chrony and log the offset
#   clock_sync.sh --kardia <offset_ms> <operator> [log_path] append the manual row for the Kardia tablet
#   clock_sync.sh --simulate <operator> [unit_id] [log_path] same as the first form without chronyc (bench/test)
#
# What the first form does, in order:
#   1. The operator has the OnePlus 12 hotspot up (60 s) and the Pi joined to it; chronyd uses it as NTP source.
#   2. `chronyc makestep`      forces the step instead of slewing (sub-second corrections take minutes otherwise).
#   3. `chronyc tracking`      reports the residual: "System time : 0.000123456 seconds fast of NTP time".
#   4. One row is appended to clock_sync_log.csv (CONTRACTS section 3.8):
#        date,time_utc,device,offset_ms_vs_phone,method,operator
#        2026-10-17,03:31:12,pi_unit_01,0.123,chronyd_makestep,RB
#      date/time are UTC; device is pi_<unit_id>; method is chronyd_makestep. capture_pi.py refuses to
#      start unless the last makestep row for this unit is dated today.
#   5. If the log already has a row for this device today, the drift since that row is printed, scaled to
#      8 hours, and flagged when it exceeds clock.drift_flag_s_per_8h from configs/pipeline.yaml.
#
# Sign convention: offset_ms_vs_phone = device clock minus phone (NTP) time, in milliseconds.
#   "fast of NTP time" -> positive; "slow of NTP time" -> negative.
#
# Manual Kardia tablet row (the tablet runs no chrony). Open a network-time app on the tablet (one that
# shows "device clock offset" against NTP), read the offset in milliseconds with the same sign convention
# (tablet ahead of network time -> positive) and run
#     clock_sync.sh --kardia -340 RB
# which appends
#     2026-10-17,03:32:40,kardia_tablet,-340,manual_ntp_app,RB
# Do this at shift start and shift end as well, so the tablet's drift is measured like the Pi's.
#
# Environment overrides: CLOCK_SYNC_LOG (log path), CLOCK_SYNC_UNIT (unit id), CLOCK_SYNC_SIMULATE=1,
# CLOCK_SYNC_FAKE_TRACKING (text used in place of `chronyc tracking` output when simulating),
# CLOCK_SYNC_NOW_UTC ("YYYY-MM-DD HH:MM:SS" used in place of the current UTC time when simulating).
set -euo pipefail

HEADER="date,time_utc,device,offset_ms_vs_phone,method,operator"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_DEFAULT="${CLOCK_SYNC_LOG:-/data/study/clock_sync_log.csv}"

usage() {
  sed -n '2,37p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  exit 1
}

die() { echo "clock_sync.sh: $*" >&2; exit 1; }

now_utc() {
  if [[ -n "${CLOCK_SYNC_NOW_UTC:-}" ]]; then echo "$CLOCK_SYNC_NOW_UTC"; else date -u '+%Y-%m-%d %H:%M:%S'; fi
}

unit_from_config() {
  local f="$REPO_ROOT/configs/unit_config.yaml"
  if [[ -n "${CLOCK_SYNC_UNIT:-}" ]]; then echo "$CLOCK_SYNC_UNIT"; return; fi
  if [[ -f "$f" ]]; then
    awk -F': *' '/^unit_id:/ {gsub(/["'"'"' ]/, "", $2); print $2; exit}' "$f"
  else
    hostname
  fi
}

drift_threshold_s() {
  local f="$REPO_ROOT/configs/pipeline.yaml"
  if [[ -f "$f" ]]; then
    awk '/^clock:/ {inblk=1; next} inblk && /^[^ ]/ {inblk=0} inblk && /drift_flag_s_per_8h:/ {print $2; exit}' "$f"
  fi
}

# stdin: `chronyc tracking` text -> signed offset in milliseconds (3 decimals) from the "System time" line.
parse_offset_ms() {
  awk -F':' '
    /^System time/ {
      n = split($2, a, " ")
      v = a[1] + 0.0
      if (n >= 3 && a[3] == "slow") v = -v
      printf "%.3f", v * 1000.0
      found = 1
    }
    END { if (!found) exit 1 }'
}

check_operator() {
  [[ -n "$1" ]] || die "operator initials are required (first argument)"
  [[ "$1" != *,* ]] || die "operator must not contain a comma"
}

append_row() {  # $1 log path, $2 device, $3 offset_ms, $4 method, $5 operator
  local log="$1" device="$2" offset="$3" method="$4" operator="$5"
  local stamp d t
  stamp="$(now_utc)"; d="${stamp%% *}"; t="${stamp##* }"
  mkdir -p "$(dirname "$log")"
  if [[ ! -s "$log" ]]; then echo "$HEADER" > "$log"; fi
  printf '%s,%s,%s,%s,%s,%s\n' "$d" "$t" "$device" "$offset" "$method" "$operator" >> "$log"
  echo "appended to $log: $d,$t,$device,$offset,$method,$operator"
}

# Drift since the first row of this device today, scaled to 8 h, flagged against the config threshold.
report_drift() {  # $1 log, $2 device, $3 offset_ms now
  local log="$1" device="$2" offset="$3" today thr
  today="$(now_utc)"; today="${today%% *}"
  thr="$(drift_threshold_s || true)"; thr="${thr:-1.0}"
  awk -F',' -v dev="$device" -v today="$today" -v off="$offset" -v now="$(now_utc)" -v thr="$thr" '
    NR > 1 && $1 == today && $3 == dev && !seen { first_t = $2; first_off = $4 + 0.0; seen = 1 }
    END {
      if (!seen) { print "first row for " dev " today; drift measured at shift end"; exit 0 }
      split(first_t, a, ":"); split(now, b, " "); split(b[2], c, ":")
      hours = ((c[1]*3600 + c[2]*60 + c[3]) - (a[1]*3600 + a[2]*60 + a[3])) / 3600.0
      if (hours <= 0.01) { print "shift-start row already present today; no drift interval yet"; exit 0 }
      drift = (off - first_off) / hours * 8.0
      flag = (drift < 0 ? -drift : drift) > thr * 1000.0 ? "FLAG: exceeds " thr " s per 8 h" : "within " thr " s per 8 h"
      printf "drift since %s today: %.1f ms over %.2f h = %.1f ms per 8 h (%s)\n", first_t, off - first_off, hours, drift, flag
    }' "$log"
}

main() {
  [[ $# -ge 1 ]] || usage
  local mode="step" simulate="${CLOCK_SYNC_SIMULATE:-0}"
  case "$1" in
    -h|--help) usage ;;
    --kardia) mode="kardia"; shift ;;
    --simulate) simulate=1; shift ;;
  esac

  if [[ "$mode" == "kardia" ]]; then
    [[ $# -ge 2 ]] || usage
    local offset="$1" operator="$2" log="${3:-$LOG_DEFAULT}"
    [[ "$offset" =~ ^-?[0-9]+(\.[0-9]+)?$ ]] || die "Kardia offset must be a number in milliseconds, got '$offset'"
    check_operator "$operator"
    append_row "$log" "kardia_tablet" "$offset" "manual_ntp_app" "$operator"
    report_drift "$log" "kardia_tablet" "$offset"
    return 0
  fi

  [[ $# -ge 1 ]] || usage
  local operator="$1" unit="${2:-$(unit_from_config)}" log="${3:-$LOG_DEFAULT}" tracking offset_ms
  check_operator "$operator"
  [[ -n "$unit" ]] || die "unit id unknown: pass it as the second argument or set CLOCK_SYNC_UNIT"
  local device="pi_${unit#pi_}"

  if [[ "$simulate" == "1" ]]; then
    echo "simulate: skipping chronyc makestep"
    tracking="${CLOCK_SYNC_FAKE_TRACKING:-System time     : 0.000512345 seconds slow of NTP time}"
  else
    command -v chronyc >/dev/null 2>&1 || die "chronyc not found: install chrony (apt install chrony) and join the phone hotspot"
    echo "chronyc makestep:"; chronyc makestep
    tracking="$(chronyc tracking)"
  fi
  echo "$tracking"
  offset_ms="$(printf '%s\n' "$tracking" | parse_offset_ms)" || die "no 'System time' line in chronyc tracking output"
  append_row "$log" "$device" "$offset_ms" "chronyd_makestep" "$operator"
  report_drift "$log" "$device" "$offset_ms"
}

main "$@"
