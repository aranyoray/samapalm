# OnePlus 12 recording routes (protocol section 5, section 4.6 optional stretch)

Two ways to obtain the phone clip. Route (a) needs no code and is the fallback; route (b) is the recorder built
into the onboarding app and is what the pilot uses, because it also captures the ECG.

## (a) Open Camera route (fallback)

Open Camera with the Camera2 API, configured as in `../phone_settings.md` (1920x1080 at 30 fps, H.264 at the
highest bitrate, constant frame rate if offered, ISO/shutter locked after a 2 s auto settle, WB locked, focus
locked, stabilization OFF, HDR/night/AI/beauty OFF, audio ON, torch per `capture_mode`, never the stock app).

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

Nothing in this route makes the phone clip beat-aligned by itself; the hardware marker does. This route also
captures no ECG, so the clip screen's Kardia question stays a self-report.

## (b) The onboarding app recorder (what the pilot uses)

`PalmRecorderActivity` in `../../../android/` (package `org.samahealth.onboarding.recorder`), launched from the
clip screen of the survey with the PID, clip id and `capture_mode`, returning the mp4 path and the ECG sample
count. It is compiled by Gradle in GitHub Actions on every push (`.github/workflows/onboarding.yml`).

It records a 60 s clip and the KardiaMobile 6L/Card ECG **at the same time, on the same device**, which is why
it exists: both streams are stamped with `SystemClock.elapsedRealtimeNanos` (CLOCK_BOOTTIME), so aligning the
ECG to the video is subtraction rather than a marker fit. The phone-to-Pi leg is unchanged and still needs the
LED block and the beep on the audio track, exactly as in route (a).

What it does per clip:

- Camera2 session over the preview surface, a `MediaRecorder` surface at 1920x1080 / 30 fps / H.264 with AAC
  audio (`setVideoSize(1920, 1080)`, `setVideoFrameRate(30)`, `VideoEncoder.H264`, `AudioSource.MIC`), and a
  640x480 `ImageReader` for the live palm readout. If the device will not configure all three, the readout is
  dropped and the clip is kept — the clip is the measurement.
- 2 s auto settle with the torch already in its final state, then exposure, white balance and focus are pinned.
  Where the camera offers `MANUAL_SENSOR` it sets `CONTROL_AE_MODE_OFF` with explicit `SENSOR_SENSITIVITY`,
  `SENSOR_EXPOSURE_TIME` and `SENSOR_FRAME_DURATION`; otherwise it falls back to `CONTROL_AE_LOCK`. Either way
  `CONTROL_AWB_LOCK` is set and `CONTROL_AF_MODE_OFF` holds the measured `LENS_FOCUS_DISTANCE`. OIS and EIS off
  (`LENS_OPTICAL_STABILIZATION_MODE_OFF`, `CONTROL_VIDEO_STABILIZATION_MODE_OFF`), scene modes, noise reduction
  and edge enhancement off, `FLASH_MODE_TORCH` per `capture_mode`. `lock_applied` in the clip metadata records
  which path was taken.
- A `CaptureCallback.onCaptureCompleted` writes one row per frame to `<clip>_frames.csv`:
  `frame_idx,sensor_ts_ns,wall_ns,iso,exposure_ns` (CONTRACTS 3.5, same columns as `clip1_frames.csv` in route
  (a) when that route is given a custom recorder). `sensor_ts_ns` is already on the reference clock — see below.
- Stops itself at 60 s.
- Reads the written file back with `MediaMetadataRetriever` so `resolution`, `bitrate_mbps` and the container
  frame count in `<clip>_meta.json` are what the encoder produced, not what was requested.

The preview is held at the sensor's aspect ratio rather than stretched to the screen, so the on-screen ROI box
marks the pixels that are actually averaged.

### The clock note

`SENSOR_TIMESTAMP` is on CLOCK_BOOTTIME only when the camera reports
`SENSOR_INFO_TIMESTAMP_SOURCE_REALTIME`. Otherwise it is CLOCK_MONOTONIC, and the two differ by however long
the phone has been suspended since boot — hours, on a phone that slept overnight. `ClockBridge` reads the
source, measures the `boottime - monotonic` offset with a best-of-64 bracketed read when a conversion is
needed, and every frame timestamp is routed through it before being written. `<clip>_sync.json` records the
source, the offset applied, its uncertainty and any drift across the clip.

### The ECG

`BleKardia` drives the KardiaMobile 6L/Card over BLE (service `ac060001-328c-a28f-9846-5a8aa212661b`, unlock
`M2 <token>`, 300 Hz interleaved int16 lead I/II). Packets are stamped on arrival, but arrival is later than
the heartbeat by a variable transport delay, so a per-packet stamp would inherit that jitter. The sample
timeline is instead recovered at stop from the **lower envelope** of arrival times: a line through the
least-delayed packet of the first quarter and that of the last quarter gives both the time origin and the
device's real sample rate. What remains is the link's minimum delay, constant within a session, which biases
absolute pulse arrival time but not beat-to-beat variation; it is reported in `<clip>_sync.json`, not hidden.

**Channel layout is decided from the samples, not assumed.** A KardiaMobile Card sends ten single-lead values
per 20-byte packet; a 6L interleaves lead I and lead II. Reading a Card as interleaved pairs yields half the
rate, a 2:1 decimated lead I, and a second "lead" that is really the discarded samples — which is what the
first real recording did, writing 150 Hz instead of 300 Hz. `finalise` therefore compares how much the signal
moves between neighbouring values against how much it moves between values two apart: below 0.9 it is one
waveform. On the recording that exposed this the ratio was 0.58; a synthetic two-lead stream whose leads
correlate at 0.987 scores 2.44. The ratio and the decision are both written to `<clip>_sync.json`, so a wrong
call is visible rather than silent.

Per clip, when a Kardia was streaming: `<clip>_ecg.atc` (AliveCor ATC v1, read by `palmppg/ecg/atc.py`),
`<clip>_ecg_samples.csv` (`t_ref_ns, sample_idx, lead1_raw, lead2_raw, lead1_mv, lead2_mv`),
`<clip>_ecg_packets.csv` (raw arrivals, the irreplaceable record) and `<clip>_ecg_meta.json` (CONTRACTS 3.6).

The ATC stores device counts 1:1 at an integer 153 nV/LSB; the exact provisional scale is 152.587890625
nV/count, so millivolts read back through the parser are 0.27 percent high. Both numbers are in
`<clip>_ecg_meta.json`. The underlying 10 mV/65536 scale is itself not electrically calibrated.

Dropped BLE notifications are detected as arrival-time gaps and zero-filled so that sample index stays
proportional to time; the count is in `<clip>_sync.json` as `missing_samples_zero_filled`. A clip with a
non-zero count has flat segments in the ECG by construction.

### The live palm readout

`PulseMeter` tracks the DC of the ROI mean with a slow exponential average and subtracts it, because the pulse
is well under one percent of the signal and the raw mean plots as a flat drifting line. It picks peaks off the
remainder with a 300 ms refractory period and reports a rate and a perfusion index. Watch the perfusion number:
near zero means no pulse is reaching the camera and the clip will be worthless however long it runs. This is a
positioning aid computed from a subsampled preview-resolution stream, never the measurement, and it is not
written to disk.

### Status

Built, installed and exercised on a OnePlus 12 for the Camera2 path. **The BLE ECG path has not been run
against a Kardia on hardware**: the 6L/Card only advertises while its electrodes are held. Peak detection
thresholds are reasoned, not tuned on real recordings. Like any other recorder it must pass the bench
acceptance in `../README.md` before it is used for study clips.
