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
./gradlew testDebugUnitTest          # writes a real ATC with the production writer
python3 tools/check_atc_roundtrip.py # parses it with palmppg/ecg/atc.py
```

The round-trip check is the one that matters: it proves the app's `AtcWriter` output is readable by
the pipeline's own parser (CRC over `id + payload`, 264 B info block, `<BHHBH` fmt), rather than by
a reimplementation of it.

## Operating a clip

1. Launch. The Kardia pairs on its own — accept the system pairing dialog once per device. Wait for
   `BLE: streaming` and a plausible HR before recording.
2. Set `study_id` in the field. It auto-increments after each clip.
3. Torch toggle per the rig: on when the box light alone is not enough. Set it **before** pressing
   REC — it changes the scene, and the exposure settle has to happen after it.
4. Position the palm about 15 cm above the aperture, inside the yellow ROI box. The lower trace is
   the live ROI mean; a visible pulse there means the geometry is right. The upper trace is lead I.
5. Press REC. Two seconds of settle, then exposure / white balance / focus lock, then exactly 60 s
   of recording with a countdown. It stops itself. Pressing STOP early keeps the short clip.
6. Files are copied to `Download/SamaPalm/<study_id>_<stamp>/` and the private copy is deleted only
   if every file transferred.

Do not touch the preview, the torch or the phone during the clip.

## What a session contains

```
<study_id>_<stamp>/
  phone/clip1.mp4                  H.264 1080p30, AAC mono — audio carries the rig buzzer markers
  phone/clip1_frames.csv           CONTRACTS 3.5 exactly: frame_idx,sensor_ts_ns,wall_ns,iso,exposure_ns
  phone/clip1_meta.json            CONTRACTS 3.5 keys, plus what the ingest cannot infer
  phone/clip1_ppg_roi.csv          t_ref_ns,y_mean,u_mean,v_mean over the centred ROI
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

`clip1_ppg_roi.csv` is a coarse on-device convenience trace from the `ImageAnalysis` stream
(subsampled, frames dropped under load — every row is timestamped, so gaps are explicit). It is for
operator feedback and sync checking. The mp4 is the measurement.

**On the OnePlus 12 this file is not produced.** Measured: binding Preview + VideoCapture +
ImageAnalysis together makes CameraX negotiate the encoder down to 720p, even though the camera is
LEVEL_3 and 1080p is available with two streams. Constraining the preview stream to 720p does not
recover it, so it is a stream-count limit rather than a resolution budget. Since protocol section 5
requires 1080p and the ROI trace is only an aid, the app checks the negotiated resolution after
binding and rebinds without `ImageAnalysis` if the clip would be short of
`MIN_VIDEO_SHORT_SIDE`. When that happens the status line and `clip1_meta.json`
(`roi_dropped_reason`) both say so, and `roi_trace_file` is null. Devices that can carry all three
streams at 1080p keep the trace.

## Known limitations

- `resolution`, `bitrate_mbps` and frame count in `clip1_meta.json` are read back from the written
  file, not from the requested quality, so they are what the encoder actually produced.
- The ATC stores device counts 1:1 at an integer 153 nV/LSB; the exact provisional scale is
  152.587890625 nV/count, so mV read back through the parser are 0.27 % high. Both numbers are in
  `kardia_meta.json`. The underlying 10 mV/65536 scale is itself uncalibrated — see `BleKardia`.
- Dropped BLE notifications are detected as arrival-time gaps and zero-filled so sample index stays
  proportional to time; the count is in `sync.json` as `missing_samples_zero_filled`. A clip with a
  non-zero count has flat segments in the ECG by construction.
- The ROI trace is dropped whenever keeping it would cost video resolution (see above) or the
  three-stream bind fails outright; the clip still records and `roi_trace_file` is then null. On the
  OnePlus 12 this is the normal path, so plan to position the palm from the preview image rather
  than from a live pulse trace.
- Exposure lock falls back from true manual sensor control to `CONTROL_AE_LOCK` on devices without
  the `MANUAL_SENSOR` capability. `lock_applied` in `clip1_meta.json` says which was used.
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

