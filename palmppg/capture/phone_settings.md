# OnePlus 12 recording checklist (protocol section 5)

Operator checklist for the product-proxy clip. The phone is a consumer camera and the clip must be an honest
consumer clip: no scene processing, no pixel warping, settings locked and logged. Work through the numbered
steps in order before every participant; steps 1 to 4 are a one-time setup you re-check daily.

Capture app: **Open Camera** (F-Droid or Play Store build, Camera2 API enabled). **Never the stock OnePlus
camera app** (Hasselblad colour processing, scene detection and multi-frame denoise alter the pulse).
Alternative: the custom recorder in `android/` (logs per-frame `SENSOR_TIMESTAMP`; see `android/README.md`).

## A. One-time app setup (re-check at shift start)

1. Install Open Camera; open it; Settings (gear) -> *Camera API* -> **Camera2 API**: ON. Restart the app.
   `[screenshot placeholder: Settings > Camera API with Camera2 API selected]`
2. Settings -> *Video settings* -> *Video resolution*: **1920x1080**; *Video frame rate*: **30 fps**.
   `[screenshot placeholder: Video resolution list with 1920x1080 highlighted, frame rate 30]`
3. Settings -> *Video settings* -> *Video format*: **MPEG-4 / H.264** (not HEVC, not 10-bit); *Video bitrate*:
   **the highest value offered**; *Constant frame rate* (if the build offers it): **ON**.
   `[screenshot placeholder: Video format H.264, bitrate = maximum, constant frame rate ON]`
4. Settings -> *Video settings* -> *Video stabilization*: **OFF**. Settings -> *Photo/Video* -> *Auto-level*: OFF.
   EIS warps pixels frame to frame and destroys the pulse signal; the ingest flags residual warps.
   `[screenshot placeholder: Video stabilization toggle OFF]`
5. Settings -> *Camera preview / processing*: **HDR OFF, Night mode OFF, AI / scene mode OFF, Beauty OFF**,
   *Noise reduction mode*: **OFF** (or *fast* if OFF is not offered), *Edge mode*: OFF.
   `[screenshot placeholder: HDR, night, scene, beauty and noise reduction all OFF]`
6. Settings -> *Video settings* -> *Record audio*: **ON**, source: *camcorder/mic*, no noise suppression.
   The buzzer beep on the audio track is a sync marker (section 4.2); without audio the phone clip can only be
   aligned by the LED block.
   `[screenshot placeholder: Record audio ON]`
7. Settings -> *More camera controls*: enable **ISO/exposure sliders**, **manual white balance**, **manual focus**
   and the lock icons on the preview. Enable *Show ISO / exposure on screen* so the locked values can be read.
   `[screenshot placeholder: on-screen ISO/exposure readout and lock icons visible]`
8. Settings -> *On-screen GUI*: enable the *video timer*; disable *shutter sound*; disable *auto-rotate*.
   `[screenshot placeholder: GUI options]`

## B. Daily, at shift start and shift end (section 4.1)

9. Turn on the phone hotspot for 60 s, join the Pi, run `palmppg/capture/clock_sync.sh <operator>` on the Pi
   (it runs `chronyc makestep` and appends the Pi row to `clock_sync_log.csv`). Read the Kardia tablet's network
   time offset from its network-time app and add it with `clock_sync.sh --kardia <offset_ms> <operator>`.
   Repeat both at shift end. The Pi refuses to record until the step row is dated today.
   `[screenshot placeholder: phone hotspot ON; tablet network-time app showing the offset]`
10. Check the phone's free storage (>= 20 GB), battery (>= 50 %) and that it is in the mount with the lens
    clean. Mounting per `capture_mode` (configs/pipeline.yaml `study.capture_mode`):
    `simultaneous`: beside the Pi camera under the aperture, LED visible in a frame corner, torch **OFF**;
    `sequential`: on the desk stand for a separate palm-over-camera scan after the box clip, torch **ON**.
    `[screenshot placeholder: phone in the mount, LED visible at the aperture rim]`

    **No phone torch is ever an illuminant.** If the box reads under `illumination.lux_nominal`, raise
    `camera.exposure_us` or move the box LEDs closer; never add a second handset's flash to make up the
    shortfall. A phone torch dims as it heats (the 60 s clip would breach `qc.lighting_drift_pct_max`
    of 2 %), it is PWM-dimmed at an undocumented rate against a ~1 % pulsatile signal, and its phosphor
    differs from the box LEDs, which reweights the Bayer channels and confounds the MST/ITA melanin
    stratification behind H2. Lux is a stratum and an E2 covariate, never a pass/fail gate, so a reading
    under target degrades nothing on its own (D-035).

## C. Weekly, per unit (section 5, phone flat field)

11. Record one 10 s clip of the white card under the box light with the same locked settings as a participant
    clip, torch per `capture_mode`, and save it as `units/<unit_id>/phone_flatfield.mp4`. Record the colour
    checker as `units/<unit_id>/colorchecker.jpg`. The ingest uses these to correct vignetting on the phone path.
    `[screenshot placeholder: white card filling the frame under the box light]`

## D. Per participant (every clip)

12. Open Open Camera in **video** mode; confirm the on-screen readout shows 1920x1080, 30 fps, and the audio
    icon is not crossed out. Confirm the torch state matches `capture_mode` (step 10) and do not change it.
    `[screenshot placeholder: video mode preview with resolution, fps and audio icon]`
13. Palm in place, Pi operator ready. Let auto exposure settle for **2 s** with the palm in view, then tap the
    **exposure lock** (AE lock) so **ISO and shutter are locked**. Read both values off the screen.
    `[screenshot placeholder: AE lock icon engaged, ISO and shutter values readable]`
14. Tap the **white balance lock** (or set manual WB to the box light's preset and leave it): **WB locked**.
    `[screenshot placeholder: WB lock engaged]`
15. Tap to focus on the palm centre, then tap the **focus lock** (AF lock): **focus locked**. Do not touch the
    preview again.
    `[screenshot placeholder: AF lock engaged]`
16. Start the phone recording **before** the Pi operator starts `capture_pi.py`, so the phone sees P1 at 2 s.
    Do not move the phone during the clip; the buzzer P1 (three short beeps) and P2 (two long beeps) are the
    markers; at P2 the operator says "lift right thumb, put it back" (section 4.3).
17. Stop the phone recording after the Pi reports the clip end (about 60 s, config `video_seconds`). Only one
    re-shoot is allowed (clip id `clip1b`) and only on a quality failure.
18. Copy the file to `participants/<study_id>/phone/clip1.mp4` and fill `phone/clip1_meta.json` (section E).
    If the custom recorder was used, also copy `clip1_frames.csv`.

## E. What to record in `phone/clip1_meta.json` (CONTRACTS section 3.5)

```json
{
  "app": "OpenCamera 1.5x (Camera2 API)",
  "device_model": "OnePlus 12 (CPH2583)",
  "os_build": "OxygenOS 14.x build string from Settings > About",
  "resolution": [1920, 1080],
  "fps_nominal": 30,
  "bitrate_mbps": 100,
  "iso": 400,
  "exposure_ns": 8333333,
  "wb_locked": true,
  "focus_locked": true,
  "stabilisation": false,
  "hdr": false,
  "torch": "off",
  "capture_mode": "simultaneous",
  "start_wall_ns": 1760000000000000000,
  "led_block": {"x": 8, "y": 8, "w": 48, "h": 48},
  "study_id": "SWHT-PP-003-0001",
  "clip_id": "clip1"
}
```

`iso` and `exposure_ns` are the locked values read off the screen in step 13 (exposure 1/120 s = 8333333 ns).
`start_wall_ns` is the phone wall clock at the start of recording (from the file's creation time; audit only,
the phone clock map comes from the LED block and the beep, never from this value). `led_block` is where the
LED lands in the phone frame (null if the phone cannot see it, sequential mode). `torch` is "on" or "off".

## F. Never

- the stock camera app, any scene / portrait / AI / HDR / night / beauty mode, or video stabilisation;
- changing ISO, shutter, white balance, focus, zoom or torch during the clip;
- muting the microphone;
- cropping, trimming, re-encoding or "enhancing" the file before it is copied.
