#!/usr/bin/env bash
# offload.sh: copy the study tree to the USB SSD or laptop with a SHA-256 manifest and a completeness check.
# Protocol section 4.6: "rsync to the USB SSD or laptop with SHA-256 manifest and a dry-run check that every
# participant folder has pi, phone, ecg and crf parts before it is marked complete."
#
# Usage
#   offload.sh --check <study_root>          dry run: one line per participant with the four parts; writes
#                                            COMPLETE.flag into a participant folder only when pi, phone, ecg
#                                            and crf are all present; removes a stale flag otherwise
#   offload.sh <study_root> <dest_dir>       runs the check, then rsync -a --partial --info=progress2
#                                            (cp -a with a warning when rsync is missing) to <dest_dir>/<name>,
#                                            builds MANIFEST.sha256 from the SOURCE tree (sha256sum over every
#                                            file), writes it into the copy and verifies the copy against it
#   offload.sh --verify <copy_dir>           re-verifies a copy against its MANIFEST.sha256
#   offload.sh --strict ...                  with either form: exit 4 when any participant is incomplete
#
# Parts (CONTRACTS section 3): pi = pi/clip1.raw + clip1_pts.csv + clip1_meta.json; phone = phone/clip1.mp4 +
# clip1_meta.json; ecg = ecg/kardia_meta.json + (kardia_*.atc or kardia_*.pdf); crf = crf.json.
# Exit codes: 0 ok; 1 usage or tooling error; 3 manifest verification failed; 4 incomplete participant (--strict).
set -euo pipefail

MANIFEST_NAME="MANIFEST.sha256"
STRICT=0

usage() {
  sed -n '2,19p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  exit 1
}

die() { echo "offload.sh: $*" >&2; exit 1; }

part_pi()    { [[ -f "$1/pi/clip1.raw" && -f "$1/pi/clip1_pts.csv" && -f "$1/pi/clip1_meta.json" ]]; }
part_phone() { [[ -f "$1/phone/clip1.mp4" && -f "$1/phone/clip1_meta.json" ]]; }
part_crf()   { [[ -f "$1/crf.json" ]]; }
part_ecg() {
  [[ -f "$1/ecg/kardia_meta.json" ]] || return 1
  if compgen -G "$1/ecg/kardia_*.atc" >/dev/null 2>&1; then return 0; fi
  if compgen -G "$1/ecg/kardia_*.pdf" >/dev/null 2>&1; then return 0; fi
  return 1
}

mark() { if "$1" "$2"; then echo "yes"; else echo "no"; fi; }

# Prints the table, writes/removes COMPLETE.flag, returns the number of incomplete participants in $INCOMPLETE.
check_tree() {
  local root="$1" pdir n_total=0 n_complete=0
  INCOMPLETE=0
  [[ -d "$root/participants" ]] || die "$root has no participants/ directory"
  printf '%-22s %-5s %-5s %-5s %-5s %s\n' "participant" "pi" "phone" "ecg" "crf" "status"
  for pdir in "$root"/participants/*/; do
    [[ -d "$pdir" ]] || continue
    pdir="${pdir%/}"
    local name pi phone ecg crf status
    name="$(basename "$pdir")"
    pi="$(mark part_pi "$pdir")"; phone="$(mark part_phone "$pdir")"
    ecg="$(mark part_ecg "$pdir")"; crf="$(mark part_crf "$pdir")"
    n_total=$((n_total + 1))
    if [[ "$pi" == yes && "$phone" == yes && "$ecg" == yes && "$crf" == yes ]]; then
      status="COMPLETE"
      n_complete=$((n_complete + 1))
      if [[ ! -f "$pdir/COMPLETE.flag" ]]; then
        printf 'complete_utc=%s\nparts=pi,phone,ecg,crf\nmarked_by=offload.sh\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$pdir/COMPLETE.flag"
      fi
    else
      status="INCOMPLETE (not marked)"
      INCOMPLETE=$((INCOMPLETE + 1))
      if [[ -f "$pdir/COMPLETE.flag" ]]; then
        rm -f "$pdir/COMPLETE.flag"
        status="INCOMPLETE (stale COMPLETE.flag removed)"
      fi
    fi
    printf '%-22s %-5s %-5s %-5s %-5s %s\n' "$name" "$pi" "$phone" "$ecg" "$crf" "$status"
  done
  echo "participants: $n_total, complete: $n_complete, incomplete: $INCOMPLETE"
}

build_manifest() {  # $1 source root, $2 manifest output path (absolute)
  local src="$1" out="$2"
  ( cd "$src" && find . -type f ! -name "$MANIFEST_NAME" -print0 | LC_ALL=C sort -z | xargs -0 -r sha256sum ) > "$out"
  echo "manifest: $(wc -l < "$out") files -> $out"
}

verify_copy() {  # $1 copy root (holds MANIFEST.sha256)
  local copy="$1"
  [[ -f "$copy/$MANIFEST_NAME" ]] || die "no $MANIFEST_NAME in $copy"
  if ( cd "$copy" && sha256sum -c --quiet "$MANIFEST_NAME" ); then
    echo "verify: all $(wc -l < "$copy/$MANIFEST_NAME") files match $MANIFEST_NAME in $copy"
    return 0
  fi
  echo "verify: FAILED in $copy (see lines above)" >&2
  return 3
}

copy_tree() {  # $1 source root, $2 copy root
  local src="$1" copy="$2"
  mkdir -p "$copy"
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --partial --info=progress2 "$src/" "$copy/"
  else
    echo "WARNING: rsync not found; falling back to 'cp -a' (no resume, no progress display)" >&2
    cp -a "$src/." "$copy/"
  fi
}

main() {
  [[ $# -ge 1 ]] || usage
  if [[ "$1" == "--strict" ]]; then STRICT=1; shift; fi
  [[ $# -ge 1 ]] || usage
  case "$1" in
    -h|--help) usage ;;
    --check)
      [[ $# -eq 2 ]] || usage
      check_tree "$2"
      [[ "$STRICT" == 1 && "$INCOMPLETE" -gt 0 ]] && exit 4
      exit 0 ;;
    --verify)
      [[ $# -eq 2 ]] || usage
      verify_copy "$2"; exit $? ;;
  esac
  [[ $# -eq 2 ]] || usage
  local src dest name copy
  src="$(cd "$1" && pwd)"; dest="$2"; name="$(basename "$src")"
  mkdir -p "$dest"; dest="$(cd "$dest" && pwd)"; copy="$dest/$name"
  [[ "$copy" != "$src" ]] || die "destination equals the source"
  echo "== completeness check =="
  check_tree "$src"
  if [[ "$STRICT" == 1 && "$INCOMPLETE" -gt 0 ]]; then die "$INCOMPLETE incomplete participant(s); --strict refuses to offload"; fi
  echo "== copy $src -> $copy =="
  copy_tree "$src" "$copy"
  echo "== manifest (computed on the source) =="
  build_manifest "$src" "$copy/$MANIFEST_NAME"
  echo "== verify copy against the source manifest =="
  verify_copy "$copy"
}

main "$@"
