#!/usr/bin/env bash
# Scripted dry run of SamaPalmRecorder on the attached phone: install, launch, REC, record, STOP, pull,
# then print what the camera actually did. The point is the read-back: "accepted" request keys on a
# vendor HAL are not "honoured" ones, and the only proof is the per-frame control log the clip wrote.
#
#   tools/dry_run.sh [seconds=9] [apk=app/build/outputs/apk/debug/app-debug.apk]
#
# Needs: adb on PATH, the phone unlocked (a lockscreen backgrounds the app and closes the camera; the
# script detects this and stops), python3 for the UI dump parse. Point the lens at a palm if you want
# the pre-flight to pass; pointed at a desk it will warn "ROI dark", which is itself a useful check.
set -euo pipefail
SECS="${1:-9}"
APK="${2:-$(dirname "$0")/../app/build/outputs/apk/debug/app-debug.apk}"
PKG=org.swht.palm
OUT="$(mktemp -d /tmp/samapalm-dryrun-XXXX)"

adb shell input keyevent KEYCODE_WAKEUP >/dev/null
if adb shell dumpsys window 2>/dev/null | grep -q 'mDreamingLockscreen=true'; then
  echo "phone is on the lockscreen: unlock it and run again (the app is backgrounded there and the camera closes)" >&2
  exit 2
fi

[ -f "$APK" ] && adb install -r "$APK" | tail -1
adb logcat -c
adb shell am force-stop "$PKG"
adb shell am start -W -n "$PKG/.MainActivity" | grep -E 'Status|TotalTime'
adb shell sleep 5

adb shell uiautomator dump /sdcard/ui.xml >/dev/null 2>&1
adb shell cat /sdcard/ui.xml > "$OUT/ui.xml"
REC=$(python3 - "$OUT/ui.xml" <<'PY'
import re, sys
x = open(sys.argv[1], encoding="utf-8", errors="replace").read()
m = re.search(r'resource-id="org.swht.palm:id/btnRecord"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', x)
print(f"{(int(m[1])+int(m[3]))//2} {(int(m[2])+int(m[4]))//2}" if m else "NOTFOUND")
PY
)
if [ "$REC" = "NOTFOUND" ]; then echo "REC button not on screen (permissions dialog? camera failed?)" >&2; adb logcat -d -s CameraRig:V SamaPalm:V | tail -20; exit 3; fi

echo "REC at $REC — settle 2.4 s, then ${SECS} s of clip"
adb shell input tap $REC
adb shell sleep $((SECS + 3))
adb shell input tap $REC
adb shell sleep 7

echo; echo "== rig log =="
adb logcat -d -s CameraRig:V SamaPalm:V | sed 's/^[0-9-]* [0-9:.]* *[0-9]* *[0-9]* //' | grep -E 'bound|lock|torch|negotiated|rebind' | tail -12

SESS=$(adb shell 'ls -t /sdcard/Download/SamaPalm | head -1' | tr -d '\r')
echo; echo "== session $SESS =="
adb pull "/sdcard/Download/SamaPalm/$SESS" "$OUT/session" >/dev/null
ls -la "$OUT/session/phone"

python3 - "$OUT/session/phone" <<'PY'
import csv, json, sys, collections, pathlib
d = pathlib.Path(sys.argv[1])
meta = json.load(open(d / "clip1_meta.json"))
c = meta.get("controls") or {}
print("\n== clip1_meta.json ==")
for k in ("negotiated_resolution", "bitrate_mbps", "lock_applied", "awb_applied", "distance_cm", "n_frames_logged", "roi_rows", "roi_file"):
    print(f"  {k:<24} {meta.get(k)}")
print("  camera                  ", c.get("camera_id"), "via", c.get("camera_selection"))
f = c.get("focus", {}); e = c.get("exposure", {}); w = c.get("white_balance", {})
print(f"  focus                    requested {f.get('applied_diopters')} D  reported {f.get('reported_diopters')} D  af_mode {f.get('af_mode_reported')} (0=OFF)  lens_state {f.get('lens_state_reported')} (0=STATIONARY)")
print(f"  exposure                 settled {e.get('settled_ns')} ns@{e.get('settled_iso')} -> requested {e.get('requested_ns')} ns@{e.get('requested_iso')} -> reported {e.get('reported_ns')} ns@{e.get('reported_iso')}  ae_mode {e.get('ae_mode_reported')} (0=OFF)  capped {e.get('was_capped')}")
print(f"  white balance            {w.get('applied')}  awb_mode {w.get('awb_mode_reported')} (0=OFF)  gains {w.get('gains_rggb')}")
print(f"  tonemap/shading/aberr    {c.get('tonemap_mode_reported')} (0=CURVE) / {c.get('shading_mode_reported')} (0=OFF) / {c.get('aberration_mode_reported')} (0=OFF)   zoom {c.get('zoom_ratio_reported')}   flash_state {c.get('flash_state_reported')} (3=FIRED)")
print(f"  pre-flight               {c.get('preflight')}")
for name in ("clip1_frames.csv", "clip1_controls.csv", "clip1_roi.csv"):
    p = d / name
    if not p.exists(): print(f"\n== {name}: absent =="); continue
    rows = list(csv.DictReader(open(p)))
    print(f"\n== {name}: {len(rows)} rows ==")
    if name == "clip1_controls.csv" and rows:
        for col in ("iso", "exposure_ns", "focus_diopters", "lens_state", "zoom_ratio", "awb_mode", "ae_mode", "af_mode", "tonemap_mode", "shading_mode", "flash_state"):
            vals = collections.Counter(r[col] for r in rows)
            print(f"  {col:<16} distinct {len(vals):>2}  {dict(vals.most_common(3))}")
    if name == "clip1_roi.csv" and rows:
        ys = [float(r["y_mean"]) for r in rows]
        print(f"  ROI Y mean {sum(ys)/len(ys):.1f}  min {min(ys):.1f}  max {max(ys):.1f}   (<40 = dark, palm not over the box)")
PY
echo; echo "pulled to $OUT/session"
