# OnePlus 12 recording routes (protocol section 5, section 4.6 optional stretch)

Three ways to obtain the phone clip. Route (a) needs no code and is the pilot default; route (b) is a
source-only sketch that was never compiled; route (c) is a built app that supersedes (b) and also captures the
ECG on the same clock.

## (c) `SamaPalmRecorder/` — built app, phone clip **and** ECG (preferred over (b))

A full Gradle project (`SamaPalmRecorder/`, builds to a 14 MB APK) that records the locked 60 s clip *and* the
KardiaMobile 6L/Card ECG over BLE, both stamped on `CLOCK_BOOTTIME`. Because one device captures both, the
phone-to-ECG alignment is subtraction rather than a marker fit; the phone-to-Pi leg still needs the LED block
and the buzzer on the audio track, exactly as in route (a). It writes the CONTRACTS 3.5 phone files, a
CONTRACTS 3.6 ATC produced from the live stream, and a `sync.json` reporting the camera clock source, the
applied `boottime - monotonic` offset and the recovered ECG timeline. See `SamaPalmRecorder/README.md`.

Unlike (b) it is built and its ATC output is checked against `palmppg/ecg/atc.py`
(`tools/check_atc_roundtrip.py`). Like (b) it has **not** been through the bench acceptance and has captured no
participant data.

From 2026-10-23 (D-033) both (b) and (c) fix focus at the rig distance instead of locking an autofocus result, open the
main sensor by id, meter exposure on the ROI, send an explicit sRGB tone curve with lens shading off, and freeze white
balance as logged gains; (c) also writes `clip1_controls.csv` and the pre-encoder `clip1_roi.csv` during the clip
(CONTRACTS 3.5). Verify a build with `SamaPalmRecorder/tools/dry_run.sh` before any pilot use.

Route (b) is now also built into the onboarding app as
`android/app/src/main/java/org/samahealth/onboarding/recorder/PalmRecorderActivity.kt`, launched from each clip
screen of the survey and compiled by Gradle in GitHub Actions (see `android/README.md`). `PalmRecorder.kt` in this
folder is the original standalone version, kept for reference; the frame-log format below applies to both.

## (a) Open Camera route (default)

Open Camera with the Camera2 API, configured as in `../phone_settings.md` (1920x1080 at 30 fps, H.264 at the
highest bitrate, constant frame rate if offered, ISO/shutter locked after a 2 s auto settle, WB locked, focus
locked, stabilisation OFF, HDR/night/AI/beauty OFF, audio ON, torch per `capture_mode`, never the stock app).

Output: `phone/clip1.mp4` (H.264 video, AAC audio) and a hand-filled `phone/clip1_meta.json`.

**Limitation.** A consumer recording app only writes container timestamps: the per-frame PTS that ffprobe
extracts from the MP4 (`pts_time`). There is no per-frame `SENSOR_TIMESTAMP`, so

- the ingest treats the file as variable frame rate and resamples by PTS, never by frame index (section 5);
- the PTS clock is the phone's own media clock, with an unknown offset and a small drift against the Pi's
  `CLOCK_BOOTTIME`; the phone clock map therefore comes from **detecting the LED pattern in the phone video
  and the buzzer beeps on the audio track** (section 4.2) and fitting one offset plus drift to the Pi log,
  with the residual reported per edge;
- the uncertainty of each phone frame time is the fit residual (expected below one frame period when the six
  edges are matched) plus the camera's exposure-to-PTS latency, which is constant within a clip and is
  absorbed in the offset term;
- `sequential` mode (no shared LED view) gets a coarse timeline only: file wall clock plus the start beep.

Nothing in this route makes the phone clip beat-aligned by itself; the hardware marker does.

## (b) Custom Camera2 recorder `PalmRecorder.kt` (optional)

`PalmRecorder.kt` is a single-activity Kotlin recorder (about 200 lines) that

- opens the back camera through `CameraDevice`, configures a `MediaRecorder` surface at 1920x1080, 30 fps,
  H.264, 100 Mbit/s, with AAC audio at 48 kHz mono;
- after a 2 s auto settle, locks AE (`CONTROL_AE_LOCK`), AWB (`CONTROL_AWB_LOCK`) and AF (`CONTROL_AF_TRIGGER`
  then `CONTROL_AF_MODE_OFF` at the measured `LENS_FOCUS_DISTANCE`), turns OIS and EIS off
  (`LENS_OPTICAL_STABILIZATION_MODE_OFF`, `CONTROL_VIDEO_STABILIZATION_MODE_OFF`), disables scene modes, noise
  reduction, edge enhancement and tone-map tweaks (`CONTROL_SCENE_MODE_DISABLED`, `NOISE_REDUCTION_MODE_OFF`,
  `EDGE_MODE_OFF`), and sets the torch per `capture_mode`;
- in `CameraCaptureSession.CaptureCallback.onCaptureCompleted` logs, for every frame,
  `frame_idx` (frame counter), `sensor_ts_ns` (`CaptureResult.SENSOR_TIMESTAMP`, the phone's
  `CLOCK_BOOTTIME` in ns), `wall_ns` (`System.currentTimeMillis() * 1e6`), `iso` (`SENSOR_SENSITIVITY`) and
  `exposure_ns` (`SENSOR_EXPOSURE_TIME`) to `clip1_frames.csv` (CONTRACTS section 3.5);
- writes `clip1_meta.json` with the locked values, device model, OS build, torch state and capture mode.

What it gives over route (a): `sensor_ts_ns` per frame on the phone's monotonic clock, which removes the
container-PTS ambiguity (frame drops become timestamp gaps rather than guesses) and lets the LED/beep fit map
the phone *sensor* clock to the Pi clock with one offset and one drift term. It does not remove the need for
the hardware marker: the phone clock and the Pi clock are still different clocks.

**Status: the file has not been compiled in this environment.** It needs an Android Studio / Gradle project
(minSdk 29, targetSdk 34, Kotlin 1.9, `CAMERA`, `RECORD_AUDIO` and storage permissions in the manifest, a
`SurfaceView` in the activity layout). The header comment in the file states this. Before any pilot use it must
be built, installed on the OnePlus 12, and run through the bench acceptance in `../README.md` like any other
recorder; the ingest reads its `clip1_frames.csv` only when the file is present and well formed.

Build sketch:

```
app/src/main/java/org/swht/palm/PalmRecorder.kt   <- this file
app/src/main/AndroidManifest.xml                   <- permissions CAMERA, RECORD_AUDIO; activity PalmRecorder
app/src/main/res/layout/activity_recorder.xml      <- SurfaceView id preview, Button id record
app/build.gradle                                   <- compileSdk 34, minSdk 29, kotlin-android plugin
```

Outputs land in the app's external files directory as `<study_id>/<clip_id>.mp4`, `<clip_id>_frames.csv`
and `<clip_id>_meta.json`; copy them into `participants/<study_id>/phone/` with the names of CONTRACTS 3.5.
