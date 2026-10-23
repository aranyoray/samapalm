# SamaPalmRecorder

One button, one minute: a locked 1080p30 palm clip and a simultaneous KardiaMobile 6L/Card ECG,
captured by one phone and written straight into the CONTRACTS section 3.5 / 3.6 layout.

Supersedes route (b) in `../README.md` (`PalmRecorder.kt`, source-only, never compiled). This one
builds, and it also carries the ECG, which `PalmRecorder.kt` did not.

## Why one device matters

The pilot's hard sync problem is that the Pi, the phone and the Kardia tablet are three devices with
three crystals, which is why the protocol spends an LED block and a buzzer on cross-device
alignment. Here the camera and the ECG are captured by the *same* phone, so both land on one clock
(`CLOCK_BOOTTIME`, via `SystemClock.elapsedRealtimeNanos`) and aligning them is subtraction, not a
fit. That removes the phone-to-ECG leg of the sync problem entirely. It does **not** remove the
phone-to-Pi leg: the audio track and the LED block are still how this clip registers against
`pi/clip1_pts.csv`, so keep recording audio and keep the LED in frame.

Two residual error terms are measured rather than assumed, and both land in `sync.json`:

| term | what it is | where it comes from |
|---|---|---|
| camera clock base | `SENSOR_TIMESTAMP` is `CLOCK_BOOTTIME` only when the sensor reports `TIMESTAMP_SOURCE_REALTIME`; otherwise it is `CLOCK_MONOTONIC` | `ClockBridge` reads the source, measures `boottime - monotonic` with a best-of-64 bracketed read, and converts every frame. Mixing the two silently is an hours-wide error on a phone that has slept. |
| ECG transport delay | a BLE packet arrives later than the heartbeat it contains, by a variable amount | `BleKardia.finalise` fits the *lower envelope* of packet arrivals: the least-delayed packets of the first and last quarter define a line that recovers both the time origin and the device's real sample rate. What is left is the link's minimum delay — constant within a session, so it biases absolute PAT but not beat-to-beat timing. Reported as `arrival_delay_median_ns` / `_p95_ns`. |

Neither has been checked against an external reference. The bench acceptance in
`../../README.md` still applies before any pilot use.

## Build

Needs JDK 17 and an Android SDK with platform 36. No Android Studio required.

```
export JAVA_HOME=$(/usr/libexec/java_home -v 17 2>/dev/null || echo /opt/homebrew/opt/openjdk@17)
echo "sdk.dir=$HOME/Library/Android/sdk" > local.properties
./gradlew assembleDebug
```

APK lands at `app/build/outputs/apk/debug/app-debug.apk` (about 14 MB).

Gradle is pinned to 8.13 by the wrapper: AGP 8.13 uses a Gradle API removed in 9.6, so a system
Gradle 9.x cannot build this. Always invoke `./gradlew`, never `gradle`.

Install:

```
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

## Checks

```
./gradlew testDebugUnitTest          # PalmControls (focus, exposure cap, sRGB curve, pre-flight) + a real ATC
python3 tools/check_atc_roundtrip.py # parses the ATC with palmppg/ecg/atc.py
tools/dry_run.sh [seconds]           # on the attached, unlocked phone: REC, record, STOP, pull, print what the HAL did
```

`dry_run.sh` is the check that matters for the camera: it prints, from the clip's own control log, whether
AF/AE/AWB were OFF on every frame, whether the lens sat still on its plane, whether the tone curve, shading
and zoom requests were honoured, and the mean ROI luma — "accepted" request keys on a vendor HAL are not
"honoured" ones, and nothing but the read-back settles it.

The round-trip check is the one that matters: it proves the app's `AtcWriter` output is readable by
the pipeline's own parser (CRC over `id + payload`, 264 B info block, `<BHHBH` fmt), rather than by
a reimplementation of it.

## Operating a clip

1. Launch. The Kardia pairs on its own — accept the system pairing dialog once per device. Wait for
   `BLE: streaming` and a plausible HR before recording.
2. Set `study_id` in the field. It auto-increments after each clip.
3. Torch toggle per the rig: on when the box light alone is not enough. Set it **before** pressing
   REC — it changes the scene, and the exposure settle has to happen after it.
4. Pick the lens-to-palm distance in the spinner (default 17 cm; 13/15/17/20/25). This sets the fixed
   focus plane for the whole session — there is no autofocus at any point, so set it to where the
   palm actually is. The main lens cannot focus closer than 13 cm; closer than that is blur the lens
   cannot remove, and 17-20 cm gives both more depth of field and a palm that fills the ROI.
5. Position the palm over the yellow ROI box. The status line shows `ROI Y` — it must read between
   40 and 215; `DARK` means the palm is not over the box (every clip before this build was recorded
   that way and said nothing). The lower trace is the live ROI mean; a pulse there means the geometry
   is right. The upper trace is lead I.
6. Press REC. Two seconds of settle with AE metered on the ROI, then the pre-flight (dark/hot ROI,
   shutter over 12 ms, slow frames, lens off its plane, unlit torch, no pulse) is shown and logged,
   exposure goes manual (shutter capped at 12 ms, light moved into ISO, one proportional ROI
   correction) and the settled colour gains are re-sent as manual white balance. Then 60 s of
   recording with a countdown. During the clip the view on screen is the analysis stream, not the
   camera preview (the label says so), and the ROI readout keeps running. STOP early keeps the clip.
6. Files are copied to `Download/SamaPalm/<study_id>_<stamp>/` and the private copy is deleted only
   if every file transferred.

Do not touch the preview, the torch or the phone during the clip.

## What a session contains

```
<study_id>_<stamp>/
  phone/clip1.mp4                  H.264 1080p30, AAC mono — audio carries the rig buzzer markers
  phone/clip1_frames.csv           CONTRACTS 3.5 exactly: frame_idx,sensor_ts_ns,wall_ns,iso,exposure_ns
  phone/clip1_controls.csv         per recorded frame: iso, exposure, focus, lens_state, zoom, colour gains, AF/AE/AWB/tonemap/shading modes, flash
  phone/clip1_roi.csv              per analysis frame, pre-encoder: Y/U/V and R/G/B means over the centred ROI, clip fraction, 3x3 Y grid
  phone/clip1_meta.json            CONTRACTS 3.5 keys, plus `controls` (requested vs reported) and the pre-flight verdict
  ecg/kardia_0001.atc              CONTRACTS 3.6 ATC v1, written from the live BLE stream
  ecg/kardia_meta.json             CONTRACTS 3.6 keys
  ecg/kardia_0001_samples.csv      t_ref_ns,sample_idx,lead1_raw,lead2_raw,lead1_mv,lead2_mv
  ecg/kardia_0001_packets.csv      raw BLE arrivals and payloads — the irreplaceable record
  sync.json                        clock sources, applied offsets, ECG timeline fit, residual bias
```

`sensor_ts_ns` in `clip1_frames.csv` is already converted to the reference clock, as CONTRACTS 3.2
requires; the offset applied is in `clip1_meta.json` (`boottime_minus_monotonic_ns`) so the raw
sensor value is recoverable. Aligning ECG to video is then
`frames.sensor_ts_ns` against `samples.t_ref_ns`, directly.

`clip1_roi.csv` is the measurement's sensor-side record: the same ROI the clip shows, read from the
camera's YUV stream before the encoder, so there is a series with no H.264 quantisation to compare the
decoded means against. It is 8-bit sRGB code values as the camera delivered them; the ingest does not
linearise or flat-field it (`palmppg.ingest.phone_tap`), and writes it as `mean_intensity_tap.parquet`
*beside* the decoded means, never instead of them. Every row carries the video frames' own
`SENSOR_TIMESTAMP`, so it joins to `clip1_frames.csv` exactly, dropped frames included.

**Streams on the OnePlus 12.** Measured on 18 Oct: Preview + VideoCapture + ImageAnalysis together make
CameraX negotiate the encoder to 720p; it is a stream-count limit. The first build kept the preview and
dropped the ROI tap for the clip — and lost the readout at the one moment it mattered. This build drops
the *preview* instead: VideoCapture + ImageAnalysis, with the 640x360 analysis frames painted to the
screen in its place (16:9, so the ROI box is the same patch of palm as in the clip). If even two
streams negotiate below 1080p the rig rebinds Preview + VideoCapture, `roi_file` is null and
`roi_trace` in the metadata says why.

## Known limitations

- `resolution`, `bitrate_mbps` and frame count in `clip1_meta.json` are read back from the written
  file, not from the requested quality, so they are what the encoder actually produced.
- The ATC stores device counts 1:1 at an integer 153 nV/LSB; the exact provisional scale is
  152.587890625 nV/count, so mV read back through the parser are 0.27 % high. Both numbers are in
  `kardia_meta.json`. The underlying 10 mV/65536 scale is itself uncalibrated — see `BleKardia`.
- Dropped BLE notifications are detected as arrival-time gaps and zero-filled so sample index stays
  proportional to time; the count is in `sync.json` as `missing_samples_zero_filled`. A clip with a
  non-zero count has flat segments in the ECG by construction.
- The ROI tap is dropped only if two streams negotiate below 1080p; `roi_file` is then null and the
  clip keeps the camera preview. The pre-flight then reports "framing unchecked".
- Exposure lock falls back from manual sensor control to `CONTROL_AE_LOCK` on devices without the
  `MANUAL_SENSOR` capability, and white balance from manual gains to `CONTROL_AWB_LOCK` without
  `MANUAL_POST_PROCESSING`. `lock_applied` / `awb_applied` in `clip1_meta.json` say which was used.
- If the torch goes out when exposure goes manual (a vendor HAL may tie the LED to AE), the rig
  reverts to `AE_LOCK` so the torch stays lit; `lock_applied` reads `ae_lock(torch_fallback)`.
- Focus is a fixed plane, not a sharp image: at f/1.6 and 17 cm the depth of field is about a
  centimetre, so parts of the palm will be soft. That is intended — a soft palm that never
  refocuses is a usable clip; a sharp one that refocuses halfway is not.
- No participant data has been captured with this app. Nothing here is validated against a
  reference clock or a reference ECG.

## Measured on a OnePlus 12 (CPH2583, OxygenOS 15.0.0.503), 2026-10-18

A 60 s dry run with no ECG connected, scene dark, recording to the app's own export path:

| check | result |
|---|---|
| camera hardware level | `LEVEL_3`, `MANUAL_SENSOR` supported |
| control lock achieved | `manual_sensor+af_off` — true manual exposure, not the AE-lock fallback |
| `SENSOR_INFO_TIMESTAMP_SOURCE` | `REALTIME`, so frames are natively on CLOCK_BOOTTIME and no offset is applied |
| boottime/monotonic bracket | 182 ns uncertainty, −52 ns drift across the clip (no suspend) |
| frames logged | 1795 over 59.789 s = 30.0056 fps, 0 capture failures |
| frame interval stability | median 33.3271 ms, SD 0.0001 ms, no interval above 1.5x median |
| ROI rows vs frame rows | 1795 vs 1795, timestamps bit-identical, so the two logs join exactly |
| negotiated resolution | 720p with ImageAnalysis bound; **1080p after the rebind** |

The ECG columns of this table are still empty: the KardiaMobile only advertises while its
electrodes are held, so the BLE path has not been exercised end to end on hardware.

## Build of 2026-10-23: what the ten clips so far showed, and what is verified

Decoded ROI of every exported clip (18 and 22-23 Oct): mean Y 2-11 of 255. The 23 Oct clip is black at
2 s and 15 s and a soft-focus hand enters at 28 s. The lock itself held — one ISO and one exposure
across all 1071 frames at 30.01 fps — but AE metered the whole frame, AF was continuous until the lock,
and the readout was unbound during the clip, so nothing said the palm was not there. This build fixes
the focus plane, meters the ROI, keeps the readout live and reads every control back. Verified so far:

| check | result |
|---|---|
| unit tests | 16 pass (`PalmControls` against the OnePlus 12 main sensor's limits, `AtcWriter`) |
| camera selection | `bound MONITOR via direct:2 (id 2)` — the main sensor by id, not logical camera 0 |
| focus | `5.882353D (17.0 cm, clamped=false)` in the first request, no AF |
| analysis stream | 640x360 (16:9), bound alongside the 1600x1200 preview in MONITOR |
| **RECORD binding at 1080p with two streams** | **not yet run on hardware** |
| **torch under `AE_MODE_OFF`, tonemap curve, shading off, `AWB_MODE_OFF` honoured** | **not yet read back** |

The last two rows are what `tools/dry_run.sh` prints. It needs the phone unlocked: on the lockscreen
Android backgrounds the app and closes the camera, which is where the 23 Oct verification stopped.

