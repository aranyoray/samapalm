#!/usr/bin/env bash
# pi_provision.sh: make the recording Pi find its network and step its clock without an operator (section 4.1).
#
# Why this exists. The Pi has no RTC, so after a cold boot its clock is whatever fake-hwclock restored, and
# capture_pi.py exits 2 unless clock_sync_log.csv has a chronyd_makestep row for this unit dated today. The
# site has no Wi-Fi, so the only route to the NTP pool is a phone hotspot. Without provisioning, a weak
# signal at shift start blocks capture entirely and the operator has to hunt for the Pi's address by hand.
# This script pins both ends: the Pi auto-joins known hotspots at a known address, and steps the clock at
# boot so the preflight row already exists before anyone touches it.
#
# The hotspot is the ROUTE to the internet NTP pool, never itself a time source (D-036): no phone runs an
# NTP server, so which handset shares the connection does not change the reference. The subnet does differ:
#
#   kind      subnet             gateway        usable for clients   default static
#   ios       172.20.10.0/28     172.20.10.1    .2 - .14  (14 max)   172.20.10.12
#   android   192.168.43.0/24    192.168.43.1   .2 - .254            192.168.43.37
#   dhcp      whatever is served (no static address written)
#
# iOS caveat: Personal Hotspot switches itself off when no client is attached, so a Pi that is slow to boot
# can come up to no network. Keep the hotspot settings screen open, or keep a second device attached, until
# the Pi has joined once. After that the saved profile reconnects on its own.
#
# Usage
#   pi_provision.sh --hotspot <ssid> [--psk <pass>] [--kind ios|android|dhcp] [--addr <ip>] [--priority <n>]
#       Add or update a NetworkManager profile for that hotspot: autoconnect on, the given priority (higher
#       wins), and a static address so the address never moves. Re-running with the same SSID updates in place.
#   pi_provision.sh --clock-unit [--unit <id>] [--operator <op>]
#       Install and enable palmppg-clock-step.service: after network-online, run clock_sync.sh so the
#       makestep row for today exists before the first participant.
#   pi_provision.sh --status      show interfaces, saved profiles with priorities, and the unit's last run
#   pi_provision.sh --dry-run ... print every command instead of running it (works with any form; runs anywhere)
#
# Exit codes: 0 ok; 1 usage or tooling error; 2 not root for an action that needs it.
set -euo pipefail

DRY_RUN=0
SERVICE_NAME="palmppg-clock-step.service"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() { sed -n '2,38p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 1; }
die() { echo "pi_provision.sh: $*" >&2; exit 1; }

# Print the command when --dry-run, otherwise run it.
run() {
  if [[ "$DRY_RUN" == 1 ]]; then printf '  '; printf '%q ' "$@"; printf '\n'; else "$@"; fi
}

need_root() {
  [[ "$DRY_RUN" == 1 ]] && return 0
  [[ "$(id -u)" == 0 ]] || { echo "pi_provision.sh: needs root (re-run with sudo)" >&2; exit 2; }
}

# --dry-run must work off the Pi (repo rule: every script runs without hardware), so tools are not required there.
need_cmd() {
  [[ "$DRY_RUN" == 1 ]] && return 0
  command -v "$1" >/dev/null 2>&1 || die "$1 not found${2:+ ($2)}"
}

# $1 kind -> "cidr gateway default_addr"; dhcp yields an empty line.
kind_params() {
  case "$1" in
    ios)     echo "28 172.20.10.1 172.20.10.12" ;;
    android) echo "24 192.168.43.1 192.168.43.37" ;;
    dhcp)    echo "" ;;
    *)       die "unknown --kind '$1' (use ios, android or dhcp)" ;;
  esac
}

# Refuse an address outside the hotspot's usable client range, which would silently never connect.
check_addr() {  # $1 kind, $2 addr
  local kind="$1" addr="$2" last
  [[ "$addr" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] || die "--addr '$addr' is not an IPv4 address"
  last="${addr##*.}"
  case "$kind" in
    ios)
      [[ "$addr" == 172.20.10.* ]] || die "--addr must be in 172.20.10.0/28 for an iOS hotspot, got $addr"
      (( last >= 2 && last <= 14 )) || die "iOS hotspot is a /28: the client range is 172.20.10.2 to .14, got $addr" ;;
    android)
      [[ "$addr" == 192.168.43.* ]] || die "--addr must be in 192.168.43.0/24 for an Android hotspot, got $addr"
      (( last >= 2 && last <= 254 )) || die "client range is 192.168.43.2 to .254, got $addr" ;;
  esac
}

provision_hotspot() {  # $1 ssid, $2 psk, $3 kind, $4 addr, $5 priority
  local ssid="$1" psk="$2" kind="$3" addr="$4" prio="$5" params cidr gw default_addr
  [[ -n "$ssid" ]] || die "--hotspot needs an SSID"
  need_cmd nmcli "NetworkManager; Raspberry Pi OS Bookworm and later ship it"
  need_root

  params="$(kind_params "$kind")"
  if [[ -n "$params" ]]; then
    read -r cidr gw default_addr <<<"$params"
    addr="${addr:-$default_addr}"
    check_addr "$kind" "$addr"
  fi

  echo "== hotspot profile '$ssid' (kind=$kind, priority=$prio) =="
  if [[ "$DRY_RUN" == 0 ]] && nmcli -t -f NAME connection show 2>/dev/null | grep -Fxq "$ssid"; then
    echo "profile exists; updating in place"
  else
    run nmcli connection add type wifi con-name "$ssid" ifname wlan0 ssid "$ssid"
  fi

  run nmcli connection modify "$ssid" \
      connection.autoconnect yes \
      connection.autoconnect-priority "$prio" \
      connection.autoconnect-retries 0 \
      802-11-wireless.hidden no \
      ipv6.method ignore

  if [[ -n "$psk" ]]; then
    run nmcli connection modify "$ssid" \
        wifi-sec.key-mgmt wpa-psk \
        wifi-sec.psk "$psk"
  else
    echo "no --psk given: leaving the existing secret in place (set it later with"
    printf '  nmcli connection modify %q wifi-sec.key-mgmt wpa-psk wifi-sec.psk <pass>\n' "$ssid"
  fi

  if [[ -n "$params" ]]; then
    run nmcli connection modify "$ssid" \
        ipv4.method manual \
        ipv4.addresses "$addr/$cidr" \
        ipv4.gateway "$gw" \
        ipv4.dns "$gw" \
        ipv4.may-fail no
    echo "static address: $addr/$cidr via $gw"
  else
    run nmcli connection modify "$ssid" ipv4.method auto
    echo "address: DHCP"
  fi
  echo "done. The Pi will join '$ssid' whenever it is in range."
}

install_clock_unit() {  # $1 unit id, $2 operator
  local unit="$1" operator="$2" target="/etc/systemd/system/$SERVICE_NAME" tmp
  need_cmd systemctl
  need_root
  echo "== $SERVICE_NAME (unit_id=$unit, operator=$operator) =="
  tmp="$(mktemp)"
  cat > "$tmp" <<UNIT_EOF
[Unit]
Description=palmppg shift-start clock step (chronyd makestep + clock_sync_log.csv row)
Documentation=file://$SCRIPT_DIR/clock_sync.sh
Wants=network-online.target chronyd.service
After=network-online.target chronyd.service

[Service]
Type=oneshot
RemainAfterExit=yes
# Give the hotspot time to appear and chronyd time to find a source before stepping.
ExecStartPre=/bin/sleep 20
ExecStart=$SCRIPT_DIR/clock_sync.sh $operator $unit
# A missing hotspot must not wedge the boot: capture_pi.py still refuses on its own preflight.
SuccessExitStatus=0 1

[Install]
WantedBy=multi-user.target
UNIT_EOF

  if [[ "$DRY_RUN" == 1 ]]; then
    echo "--- would write $target ---"; sed 's/^/  /' "$tmp"; rm -f "$tmp"
  else
    install -m 0644 "$tmp" "$target"; rm -f "$tmp"
    systemctl daemon-reload
    systemctl enable "$SERVICE_NAME"
    echo "installed and enabled $target"
    echo "run it now with: systemctl start $SERVICE_NAME && systemctl status $SERVICE_NAME"
  fi
}

show_status() {
  echo "== interfaces =="; command -v nmcli >/dev/null 2>&1 && nmcli device status || echo "nmcli not present"
  echo
  echo "== saved profiles by autoconnect priority =="
  if command -v nmcli >/dev/null 2>&1; then
    nmcli -t -f NAME,TYPE connection show | awk -F: '$2 ~ /wireless/ {print $1}' | while read -r n; do
      printf '%-28s prio=%-4s addr=%s\n' "$n" \
        "$(nmcli -g connection.autoconnect-priority connection show "$n" 2>/dev/null)" \
        "$(nmcli -g ipv4.addresses connection show "$n" 2>/dev/null | head -1)"
    done
  fi
  echo
  echo "== $SERVICE_NAME =="
  if command -v systemctl >/dev/null 2>&1; then
    systemctl is-enabled "$SERVICE_NAME" 2>/dev/null || echo "not installed"
    systemctl status "$SERVICE_NAME" --no-pager -n 5 2>/dev/null || true
  else
    echo "systemctl not present"
  fi
}

main() {
  [[ $# -ge 1 ]] || usage
  local mode="" ssid="" psk="" kind="ios" addr="" prio="100" unit="" operator="auto"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -h|--help)    usage ;;
      --dry-run)    DRY_RUN=1; shift ;;
      --hotspot)    mode="hotspot"; ssid="${2:-}"; shift 2 ;;
      --psk)        psk="${2:-}"; shift 2 ;;
      --kind)       kind="${2:-}"; shift 2 ;;
      --addr)       addr="${2:-}"; shift 2 ;;
      --priority)   prio="${2:-}"; shift 2 ;;
      --clock-unit) mode="clock"; shift ;;
      --unit)       unit="${2:-}"; shift 2 ;;
      --operator)   operator="${2:-}"; shift 2 ;;
      --status)     mode="status"; shift ;;
      *)            die "unknown argument '$1'" ;;
    esac
  done

  case "$mode" in
    hotspot) provision_hotspot "$ssid" "$psk" "$kind" "$addr" "$prio" ;;
    clock)
      if [[ -z "$unit" ]]; then
        unit="$(awk -F': *' '/^unit_id:/ {gsub(/["'"'"' ]/, "", $2); print $2; exit}' \
                 "$SCRIPT_DIR/../../configs/unit_config.yaml" 2>/dev/null || true)"
        unit="${unit:-$(hostname)}"
      fi
      install_clock_unit "$unit" "$operator" ;;
    status)  show_status ;;
    *)       usage ;;
  esac
}

main "$@"
