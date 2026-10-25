# DECISIONS.md

Running log of every decision made without an explicit instruction. Each entry: id, date, decision,
rationale, and what would change it. Provisional entries are the ones waiting on the section 14 questions.

## Provisional (awaiting answers to section 14)

| id | question | assumption coded | where to change |
|---|---|---|---|
| Q14.1 | capture_mode | `simultaneous`; phone mounted beside the Pi under the aperture, LED visible to the phone | `configs/pipeline.yaml: study.capture_mode`, `phone.led_block` in phone meta |
| Q14.2 | clip length | 60 s | `study.video_seconds`, `unit_config.yaml: capture.video_seconds` |
| Q14.3 | Kardia export | ATC preferred, PDF digitiser fallback shipped; Kardia set to 60 s | `study.kardia_duration_s`; `sync.p2.mode: after_start` for 30 s apps |
| Q14.4 | Pi ROI crop | off for the pilot (full 1536x864 frames, about 3 GB per clip) | `pi.roi_crop`, `unit_config.yaml: camera.roi_crop` |
| Q14.5 | phone torch | off in simultaneous mode (box light only); on in sequential mode | `phone.torch` |
| Q14.6 | SpO2 | collected, nullable | CRF `spo2` |
| Q14.7 | GPU / data location | no GPU assumed (CPU paths everywhere; deep models train on CPU at pilot scale or on one GPU when present); data on a USB SSD mounted at `data/study`, test stream on a separate mount `data/test_stream` | `paths.*` |

## Decisions

- **D-001 (2026-10-17) Reference clock.** Pi `CLOCK_BOOTTIME` ns (what picamera2 reports as `SensorTimestamp`) is
  the reference. All analysis times are float seconds relative to the first Pi frame of the clip. Wall clock is
  carried for audit only. Rationale: section 4; the Pi is the only device with a hardware marker it also logs.
- **D-002 (2026-10-17) Analysis window end = P2 onset.** The protocol excludes the last 5 s because of the
  fine-anchor lift at P2, and says windows adapt from `sync_events.csv`. So the window is
  `[clip_start + 2 s, P2_onset]`, which equals `[2 s, 55 s]` for a 60 s clip with P2 at `t_end - 5 s`, and
  `[2 s, 28 s]` when the Kardia app only allows 30 s. Fallback when P2 is not detected: `t_end - 5 s`.
- **D-003 (2026-10-17) LED edge acceptance.** "Six edges agree within one frame period" is read as: all
  detected rising and falling edges of P1 and P2 (up to 10) are fitted with one offset and one drift term; accept
  when at least `sync.min_edges` (6) edges were matched and the maximum residual is below one frame period.
- **D-004 (2026-10-17) Sync grade logic** lives in `Timeline.grade()` so every caller uses the same rule;
  a wall-clock or file-time map can never produce `fine`.
- **D-005 (2026-10-17) CRF derived fields.** `bp_target` = mean of three readings, BP1 dropped when it deviates
  more than 15 mmHg (config) from the BP2/BP3 mean, applied to SBP and DBP separately (the rule can fire for one
  and not the other; both rules are recorded). `bracket_flag` fires when the SBP or the DBP spread across the
  readings exceeds 10 mmHg. `bp_category` uses ACC/AHA 2017 bands on the cuff mean as a stratification format,
  not a clinical statement. `age_band` <40 / 40-59 / 60+. `bmi_class` uses WHO Asia-Pacific cut-offs (18.5, 23,
  25) because that is the convention in Indian cohorts; configurable. `dm_label`: `known_dm` (flag),
  `hba1c_above_threshold_no_flag` (HbA1c >= 6.5 without the flag), `hba1c_below_threshold`, `no_flag_no_hba1c`.
  `equity_scope` = in for MST 4..10, out otherwise. Equity arms: 4-6 versus 7-10 (protocol section 7).
- **D-006 (2026-10-17) Three camera labels.** `pi` (raw Bayer), `phone`, and `pi_proxy` (Pi frames demosaiced,
  sRGB 8-bit, H.264 CRF 23 encoded and decoded, then run through the phone pipeline). `pi_proxy` is how Pi
  data can feed `product_candidate` models ("Pi features restricted to what a phone can produce").
- **D-007 (2026-10-17) ATC parser.** Implemented against the published ATC v1 chunk layout (CONTRACTS §3.6) with
  tolerant chunk walking and a writer used for synthetic data. The first real Kardia export must be opened with
  `palmppg.ecg.atc.describe()` and the layout confirmed before any ECG result is trusted; the PDF digitiser is
  the fallback either way.
- **D-008 (2026-10-17) SQI threshold is provisional** (0.35 on the 0..1 `snr_band` scale from synthetic and
  bench data) and is frozen at run-order step 3 (first 10 participants). It is recorded in `frozen_config.yaml`
  with `status: provisional`; the go/no-go thresholds in the same file are frozen now and signed.
- **D-009 (2026-10-17) Environment.** Python 3.13 in a uv venv; CPU-only torch from PyPI (the PyTorch CPU index
  is unreachable from the build container). picamera2 and gpiozero are Pi-only and imported lazily; capture
  scripts have a `--simulate` mode that exercises every code path without hardware.
- **D-010 (2026-10-17) Banned vocabulary is enforced by a test** over the whole repository and every generated
  report (`palmppg/core/lint.py`), not by convention.
- **D-011 (2026-10-17) Test stream guard.** `TestStreamGuard` refuses a second read of the test mount and logs
  every attempt with the frozen-config hash. Development and test rows never share a parquet file.
- **D-012 (2026-10-17) Synthetic frame geometry.** Synthetic Pi clips default to 384x216 (same aspect, 1/4
  scale, identical packing and Bayer order) so the positive control runs in minutes on 4 CPUs; the unpacker is
  tested at full 1536x864 geometry on a few frames.
- **D-013 (2026-10-17) Registry merge rule.** `FeatureRegistry.register` compares only the track-relevant fields
  (group, camera, requires_ecg, requires_raw) and merges units/description/tags, keeping the richer text. The producer
  of a column owns its track flags; a consumer (the feature store) may register the same name with minimal metadata in
  either order. `sync__grade` is a stratum, not a model input; WP2 registers it `requires_ecg=True` because a `fine`
  grade needs the ECG artefact anchor, and that value stands.
- **D-014 (2026-10-17) qc_table.parquet ownership.** `palmppg.ingest.run.append_qc_table` owns `work/tables/qc_table.parquet`
  (upsert keyed by study_id, clip_id, camera). The feature store reads it and writes its own per-stream aggregate; it
  never overwrites it. Clips that were attempted but never produced a `qc.json` get a row with `valid_clip = False`
  and reason `not_processed`, so they count as failures in coverage (protocol 11.3).
- **D-015 (2026-10-17) bp_tertile cut points** come from the training participants of each outer fold on the pilot
  (there is no development stream yet) and from the development stream once it exists (`features.tertile_fit_stream`);
  the cut points are written next to every table that uses them. Labelling rows with cut points fitted on the same
  rows is refused by the function.
- **D-016 (2026-10-17) Config additions after round 1:** `clock.kardia_tz_offset_h`, `sync.artefact.margin`,
  `qc.landmark_jitter_px_max`, `qc.hand_detect_min_frac`, `qc.hand_mirror`, `qc.hand_palmar_convention`,
  `qc.hand_model_path`, `qc.skin_min_area_frac`, `qc.saturation_level_frac`, `rois.band_width_ratio`,
  `features.{tz, time_of_day_cut_hour, lux_band_edges, tertile_labels}`. Values are the ones the builders used as
  defaults; none is a performance threshold.
- **D-017 (2026-10-17) Pi proxy CRF = 18.** The OnePlus 12 records at its highest bitrate (about 50 Mbit/s at
  1080p30), which is closer to libx264 CRF 18 than to CRF 23. CRF 23, 28 and 35 remain augmentation severities
  (section 8). Measured on the small synthetic geometry (192x108, 20 s, 0.32 percent AC/DC): the proxy keeps the pulse
  at CRF 6 (AC 0.091 percent, spectral peak 96.7 bpm, SQI 0.63 against 0.101 percent / 96.7 bpm / 0.66 on the Pi
  planes) and loses it at CRF 23 (peak 55 bpm), because x264 skips near-static macroblocks when a frame is only a
  few macroblocks wide. The positive control therefore runs the proxy at the default geometry (384x216, 60 s) and
  at the real 1536x864 frames, at CRF 18 and CRF 28, and reports what it measures.
- **D-018 (2026-10-17) Positive-control HR comparison** is made over the analysis window on both sides: the truth
  HR is the mean of the generator's instantaneous rate series inside the window, and the recovered HR comes from the
  beat intervals (beats stage) or the dense-DFT spectral peak of the whole-palm trace, never from the 10 s SQI window
  peak (resolution 6 bpm).
- **D-019 (2026-10-17) QC series source.** `finalise_qc` measures saturation and flicker on the whole-palm ROI trace
  inside the analysis window (protocol 6.1 says "in the skin mask"); the whole-frame series from ingest includes the
  LED block, whose P1 pattern (100 ms on / 200 ms off) has a 10 Hz harmonic that would read as mains flicker.
  `qc.json` records `qc_series_source`.
- **D-020 (2026-10-18) PAT definition and its measured bias.** PAT is R-peak to the intersecting-tangent foot of the
  palm pulse (cfg `beats.foot_method`). On the default-geometry positive control (injected PAT 235 ms to the
  generator's onset foot) the pipeline measured 282 ms on the Pi path. The difference decomposes exactly: the mapped
  R-peaks sit 18 ms early (fine-anchor error, below one 33 ms frame) and the tangent foot sits 28 ms after the onset
  foot by construction (detected feet agree with the generator's tangent foot within 3 ms). PAT is therefore reported
  as a cross-sectional association only (exploratory, `requires_ecg`), with the foot definition named, and absolute
  values are not compared across foot definitions or across sync methods.
- **D-021 (2026-10-18) Proxy at CRF 28.** On the default-geometry positive control the Pi->H.264 proxy recovered the
  pulse at CRF 18 (HR error 0.14 bpm, 61 of 63 feet) and lost it at CRF 28 (30.9 bpm against 70.6 bpm). This is a
  measured property of the synthetic scene (AC/DC 0.5 percent on a static, low-texture palm), reported as a negative
  result; it feeds the phone-app design (highest bitrate, no re-encoding) and the section 8 compression curves.
- **D-022 (2026-10-18) Which camera answers which criterion.** The pilot go/no-go criteria are evaluated on the Pi
  (lab reference): coverage and the MST coverage drop on the Pi, pulse rate on the Pi (as the protocol states), and
  the SBP error-SD reduction on the science track (Pi). Phone and pi_proxy figures are printed alongside in the same
  dashboard and are never used to rescue a failed criterion.
- **D-023 (2026-10-18) Beat signal selection.** The protocol's "best-SQI signal" is chosen among pre-specified
  large-area candidates (whole-palm and the SNR-weighted multi-ROI fusion, per method; cfg `pulse.best_candidates`),
  with each candidate's SQI weighted by cross-method agreement on the rate (`pulse.best_selection: consensus_sqi`,
  tolerance 5 bpm). Taking the maximum SQI over all method x ROI pairs (about 130 candidates) selected noise: on one
  synthetic participant the selected signal sat at 68 bpm while five whole-palm methods agreed on 93 bpm (truth
  92.6 bpm). On the 30-participant synthetic cohort the change raised Pi pulse-rate agreement within 3 bpm on valid
  clips from 40 percent (first 10 participants) to 82 percent (all 30). Per-ROI signals are still written.
- **D-024 (2026-10-18) Pulse rate for E1** = 60 / median beat interval over the analysis window, compared with the
  ECG median-interval rate. One missed beat doubles one interval and drags a mean-interval rate; the median is used
  on both sides so the comparison is like for like.
- **D-025 (2026-10-18) SQI threshold calibration against null clips.** On synthetic null clips (AC/DC = 0, small
  geometry) the best-SQI met the provisional threshold 0.35 on 3 of 8 Pi clips, 8 of 8 phone clips and 4 of 8 proxy
  clips, so the SQI criterion alone would have passed them. The Pi separates (null 95th percentile 0.38; 80 percent of pulse clips above it); the phone and proxy at
  320x180 and 192x108 with H.264 do not (signal and null distributions overlap). The study threshold stays
  provisional in the signed frozen config; at run-order step 3 it is set to the 95th percentile of best-SQI on bench
  null recordings (static white card in the box, recorded on both cameras), a procedure that uses no outcome.
  `palmppg.experiments.sqi_calibration` implements it.
- **D-026 (2026-10-18) Bootstrap resamples in the synthetic report build.** The synthetic-run strata tables used 500
  participant-bootstrap resamples to fit the build in about ten minutes on 4 CPUs; `palmppg reports build` uses cfg
  `bootstrap.n_resamples` (2000) by default, which is what every pilot table uses.
- **D-027 (2026-10-18) Learned-model training re-initialises weights from the seed.** `train_model` resets every
  module's parameters from `TrainConfig.seed` before training, so two runs with the same seed and data are identical
  whatever happened to the global random state before the model was built.
- **D-028 (2026-10-20) Onboarding app and backend.** The CRF is captured by an Android app driven by one shared
  schema (`configs/crf_schema.json`) that the Kotlin engine (`android/crf-core`) and the Python engine
  (`palmppg/core/crf_schema.py`) both interpret; 16 golden fixtures pin identical behaviour in both languages.
  Backend: one free Supabase project (auth, REST and row-level security in one service; about 20 MB of the 500 MB
  free database for 2,000 participants). Neon was not chosen because it would need a separate auth and API layer for a
  mobile client. Google Sheets and CSV export run from Apps Script with a read-only exporter account; the pipeline
  pulls with `palmppg crf pull`.
- **D-029 (2026-10-20) Identity separation.** Name, hospital registration number and phone are stored in their own
  table locally and on the server; the CRF table rejects rows carrying them; operators can write but never read
  identity; the tablet removes names after upload by default; the visit is uploaded before its identity so a PID clash
  cannot attach a name to another person's record. Initials remain in the CRF as protocol section 3.1 lists them.
- **D-030 (2026-10-20) Rest gate and clip plans.** BP1 is taken on seating and the history is taken during the rest
  (protocol section 1); `recovery` = "pass" when the first clip starts at least `rest_seconds` (300) after BP1, else
  "short_rest". The clip plan is a tablet setting: `1x60` (protocol) or `2x30` (two bracketed clips, per the
  hypotheses brief); each is a fixed screen flow in the schema.
- **D-031 (2026-10-20) Add-on CRF fields** for the hypotheses brief (cohort tags, arrhythmia subtype and status,
  haemoglobinopathy type and transfusion, diabetes type and insulin, dialysis and eGFR, ITA, the antenatal block). They
  are carried into the feature store as covariates (`palmppg.core.crf.covariate_columns`); none is a model target and
  none changes a frozen threshold. `docs/hypotheses_crf_map.md` maps each hypothesis to its fields.
- **D-032 (2026-10-20) Android build verification.** This container cannot reach Google's Maven host, so the Android
  module is compiled by GitHub Actions (`.github/workflows/onboarding.yml`), which also publishes the debug APK. The
  JVM module with all survey logic and the Supabase client is compiled and tested locally (Gradle, Maven Central).
- **D-033 (2026-10-23) Phone capture controls are fixed and read back, not locked and assumed.** Every clip recorded
  with the standalone SamaPalmRecorder up to this date (ten sessions, OnePlus 12) had a near-black ROI for most or all
  of its length (decoded ROI mean Y 2-11 of 255; frames at 2 s and 15 s of the 23 Oct clip are fully black, a
  soft-focus hand enters at 28 s), and the app could not say so because the live ROI readout was unbound the moment REC
  was pressed. Continuous AF ran until the lock and pinned wherever the lens was at t = 2 s; `cameraIdList.first { BACK }`
  was logical camera 0 (main + ultrawide) which may hand off sensors at palm distance; white balance was `AWB_LOCK`ed
  without recording what it locked to; the vendor `FAST` tone curve was inherited although the ingest inverts sRGB. The
  standalone recorder was folded into the onboarding app the same day (8fb88ec), so the fix lands in
  `android/.../recorder/PalmRecorderActivity.kt` (the CameraX version of the same fix is kept on branch
  `wip/samapalm-recorder-controls` for reference). From this date the recorder: opens the main sensor by id (`"2"`) with
  zoom pinned at 1.0; sets `CONTROL_AF_MODE_OFF` + `LENS_FOCUS_DISTANCE` for the rig distance (intent extra
  `distance_cm`, default 17 cm = 5.88 D, clamped to the lens's 13 cm closest focus and flagged) in the *first* request;
  sends a 64-point sRGB `TONEMAP_CURVE`, `SHADING_MODE_OFF`, aberration OFF; meters AE on the ROI during the settle; goes
  manual with the shutter capped at 12 ms (light moved into ISO) after one proportional ROI-luma correction; re-sends the
  settled colour gains and transform as manual white balance; reverts to AE lock if the torch goes out under manual
  exposure; and logs every control per frame (`<clip>_controls.csv`) and the pre-encoder ROI colour (`<clip>_roi.csv`,
  16:9 analysis stream at 640x360 so the ROI is the same patch as in the clip). A pre-flight (`PalmControls.preflight`)
  names a dark/hot ROI, an over-cap shutter, slow frames, a lens that did not reach its plane, an unlit torch and a
  pulse-free trace; it warns and logs, it never refuses the operator. The phone is the secondary track (D-022) and no
  participant data exists, so no frozen threshold changes; `frozen_config.yaml` is untouched. Verified on 23 Oct: 15
  `PalmControls` unit tests against the main sensor's real limits, 6 ingest tests, and — on the CameraX build — the
  MONITOR binding on physical camera 2 at 5.88 D with the 640x360 tap. **Not yet verified on hardware** for the
  onboarding recorder: the three-surface session at 1080p, the torch staying lit under `AE_MODE_OFF`, and the HAL
  honouring tonemap/shading/`AWB_MODE_OFF` — the phone was on its lockscreen, which backgrounds the app and closes the
  camera. `palmppg/capture/android/dry_run.sh` performs and prints exactly that read-back.
- **D-034 (2026-10-24) Pi exposure 8000 -> 10000 us: one 50 Hz half-cycle.** `unit_01` benches at 350 lux with
  the OnePlus 12 mount and two box LEDs at 20 mA, against `illumination.lux_nominal: 400`. Lux is not a gate
  anywhere in the pipeline: it is a stratum (`features.lux_band_edges: [200, 400]`) and an E2 covariate, so 350
  fails nothing. It does cost signal, and the previous 8 ms exposure was also 0.8 of a 50 Hz mains half-cycle, so
  any room light leaking past the aperture aliased instead of integrating out (`qc.flicker_hz` already watches
  50/100/10 Hz at `flicker_snr_db_min: 6.0`). Moving to 10 ms fixes both: it is exactly one half-cycle, and the
  25 % more light covers the 350 -> 400 shortfall (350 x 1.25 = 437 lux-equivalent) without touching the optics.
  `frame_duration_us` is 33333, so 10 ms fits with wide margin, and the extra 2 ms of blur is immaterial for a
  resting palm under `landmark_jitter_px_max: 3.0`. `exposure_us` is not in `frozen_config.yaml`, which is
  untouched. The measured value is recorded as `illumination.lux_measured` beside the design target rather than
  overwriting it. `palmppg/synth/bayer_video.py` deliberately keeps `exposure_us: 8000` as its default so the
  committed synthetic run and its reports stay reproducible; the rig and the simulator are separate operating
  points. **Not yet verified on hardware:** the positive control and the D-025 SQI null calibration must be re-run
  at the new operating point before the bench acceptance in run-order step 2, and `lux_measured` re-read at 10 ms.
- **D-035 (2026-10-24) A phone torch is never a supplementary illuminant.** Raised when the 350 lux reading
  prompted adding the hotspot handset's flash to the box. Rejected on three grounds, any one of which is
  disqualifying. (1) Thermal rolloff: phone torches dim measurably as they heat, and `qc.lighting_drift_pct_max`
  is 2 % over a 60 s clip, so this trades a soft lux shortfall that gates nothing for a hard QC failure on every
  clip. (2) PWM: phone torches are PWM-dimmed below full output and can ripple at full, injecting an undocumented
  periodic component into the illuminant while the target signal is a ~1 % pulsatile modulation. (3) Spectrum: the
  torch phosphor and CCT differ from the box LEDs, and with `awb_gains` fixed at [1.6, 1.4] on raw Bayer that
  reweights the channels, which confounds exactly the MST-band and ITA stratification H2 and H2b rest on.
  Secondary: `box_led_current_ma: 20` is a reproducible documented quantity whereas torch output varies with iOS
  version, battery level and thermal state across 500 participants, and the hotspot handset is already carrying
  AP and cellular load that compounds (1). Q14.5 (torch off, box light only, simultaneous mode) stands unchanged.
  The remedy is D-034, then moving the LEDs closer (inverse-square: 400/350 needs distance x 0.935, e.g. 20 cm ->
  18.7 cm), which requires re-shooting the white-card `luxmap.json` against `vignetting_residual_pct_max: 3.0`.
  Recorded in `palmppg/capture/phone_settings.md` so it reaches the operator, not just the log.
- **D-036 (2026-10-24) The hotspot is the route to the NTP pool, not a time source; provisioning is scripted.**
  `clock_sync.sh` documented "the OnePlus 12 hotspot up and the Pi joined to it; chronyd uses it as NTP source"
  and names its column `offset_ms_vs_phone`. No phone runs an NTP server, so the reference has always been the
  internet NTP pool reached *through* the hotspot; the phone's own clock was never involved. This was harmless
  while the hotspot and the study camera were one handset, but the site now shares from a separate iPhone, and
  the old wording reads as though the time reference moved with it. It did not. The documentation is corrected and
  the column name kept so existing `clock_sync_log.csv` files stay readable. Two consequences are now scripted in
  `palmppg/capture/pi_provision.sh`: the subnet is platform-dependent (iOS Personal Hotspot is 172.20.10.0/28,
  gateway .1, clients .2-.14 and so 14 maximum; Android is 192.168.43.0/24), and the Pi has no RTC, so a weak
  signal at shift start blocks capture outright because `capture_pi.py` exits 2 without a makestep row dated
  today. The script writes NetworkManager profiles with `autoconnect-priority` and a checked static address per
  SSID, and installs `palmppg-clock-step.service`, a oneshot after `network-online.target` that runs
  `clock_sync.sh` at boot so the row exists before the first participant. iOS Personal Hotspot also switches
  itself off with no client attached, so a device must hold it up while the Pi first boots; this is in the
  capture README. `--dry-run` prints every nmcli call and the unit file, so the script is exercisable off the Pi
  per the repo rule that every capture script runs without hardware. **Not yet verified on hardware:** no Pi has
  been reachable this session, so the nmcli profiles and the systemd unit are tested only through `--dry-run`.

- **D-037 (2026-10-24) The quality grades are rule-based with published thresholds, and PROVISIONAL.** The
  Quality tab, and the pass/fail the clip widget pre-fills, come from signal-quality rules, not a trained model:
  POS pulse and the de Haan and Jeanne (2013) SNR for the video, and a Pan-Tompkins style detector with the
  Orphanidou (2015) template correlation, Clifford (2012) kSQI and the Dash (2009) irregularity triple for the
  ECG. The thresholds in `VideoQualityConfig` and `EcgQualityConfig` are first guesses: they have been exercised
  on synthetic signals with a known heart rate and beat count, never on a pilot clip, and D-008 requires them to
  be calibrated once clips exist. The operator always decides; a grade only pre-selects. The irregularity flag
  never lowers a grade and never names a rhythm: it is a reason for a clinician to look, which is why the
  participant summary says "the time between beats varied" and nothing more.

- **D-038 (2026-10-24) Names leave the app entirely; the PID on the paper form is the only link.** v1 kept names
  in a separate table that could be purged after upload. v2 has no identity screen, no identity table and no
  upload of one: the Room 1 -> 2 migration drops the table and the names in it. A phone that still holds
  un-uploaded v1 visits keeps them as the legacy part "full": they can still be uploaded but not re-opened,
  because the v2 schema has no flow for them, and showing a half-migrated survey would risk the operator
  "correcting" a record into a shape neither schema describes. This is what makes the app's backup rules able to
  exclude everything: there is nothing on the phone that identifies a person without the paper form.

- **D-039 (2026-10-24) The research model is a pre-read for the study clinician, and is never bundled by
  default.** ECGFounder runs on the phone through ONNX Runtime when the exported graph is present, and its
  output appears only in the Quality tab behind a line saying what it is. It is not on the participant summary,
  which carries the Kardia device's own result instead, because no Indian or South Asian evaluation of this
  model exists and returning its output to a participant needs ethics approval and a clinician over-read
  (design section 9). The 123 MB graph is not in the ordinary APK: a manual CI job builds an APK with it, and a
  phone can also be handed the file directly. The export is checked against torch on the real weights, not just
  random ones (max |delta p| 2.1e-6), because the pad-fusion bug it works around only shows up with trained
  weights.

- **D-040 (2026-10-25) The phone ECG is longer than the clip, and the clip is graded over its own window.**
  The recorder used to open the Kardia capture and the encoder together and close them together, so every beat
  at either boundary was truncated and the first PAT of a clip was computed off half a complex. The ECG now
  opens 10 s before the encoder and closes 10 s after it. The lead-in is spent inside the AE settle rather than
  after the lock, so the extra seconds improve the exposure decision instead of leaving a locked camera and a
  lit torch pointed at a palm. The clip's bounds are written to `<clip>_sync.json` as `clip_window`, on the
  reference clock and as sample indices, so nothing downstream re-derives them from the constant. The quality
  grade is taken over that window: the participant's fingers may not be on the electrodes during the lead, and
  grading the whole record would have counted the lead as flat line and marked good clips borderline at the
  0.1 `borderlineFlatFrac` threshold. An interrupted clip gets no lead-out, because the activity is on its way
  out and an ECG tail nobody waits for is worth less than closing the files cleanly.
  **Not yet verified on hardware:** no phone or Kardia has been available this session; the change compiles and
  the window arithmetic is unit-tested, but the lead has not been seen on a real recording.

- **D-041 (2026-10-25) Kardia recovery is a ladder the operator can also pull, and there is no wake-up opcode.**
  A stalled stream used to get one re-sent unlock at 3 s and a full tear-down at 8 s. It is now one rung per 3 s
  of silence, reset by the next packet: re-send the mode in use, try the other mode, rebuild the GATT
  subscription and re-ask for the fast connection interval, then disconnect and rescan. Only the first two are
  things the device is known to listen to; the published protocol (D-007, kardia-rs interop notes) has no "wake
  up" command and none is invented here, so the later rungs act on our own side of the link. A `Nudge Kardia`
  button on the recorder fires the next rung immediately rather than waiting out the silence, and with no usable
  link it restarts the scan; it is the same code path as the watchdog so the two cannot drift apart. The rung
  taken is shown on the recorder's status line and logged.

- **D-042 (2026-10-25) The recorder sounds the clip, outside the clip's own audio.** A single beep before the
  encoder opens and a double beep after it closes, so an operator holding the rig knows where the clip is
  without watching the screen; an interrupted clip gets the three-tone nack instead. Both tones fall outside the
  recorded audio on purpose: the clip's AAC track exists to carry the rig buzzer as the sync marker, and a
  phone-generated tone inside it could be read as the buzzer. They go to `STREAM_MUSIC`, not the notification
  stream, because ringer-silent mutes notifications and the whole point is to be heard. A device that will not
  give us a tone generator is logged and ignored: it must never fail a clip.

- **D-043 (2026-10-25) The ECG is notched at 50 Hz before it is graded, not only before the model.** The
  grader ran a 0.5-40 Hz band-pass and nothing else, which leaves mains pickup only about 11 dB down: roll-off,
  not rejection. In a room lit by tubes that was enough to cost the beat detector, and the loss showed up as a
  low template match rather than as the mains artefact it was. A 50 Hz RBJ notch at Q 30 now runs ahead of the
  band-pass in both `palmppg/quality/onsite.py` and the Kotlin port, in the same order, so the two still agree
  to 1e-9 on every fixture. On the synthetic cases the clean strip barely moves (template match 0.9972 to
  0.9973) and the noisy one improves (0.386 to 0.395, and three mains-driven false beats disappear). The
  frequency is config, not a constant, because a 60 Hz site needs the other value; the existing 50 Hz notch in
  `FounderPrep` is inherited verbatim from upstream ECGFounder and is left alone. Raw files stay unfiltered:
  filtering before writing would be unrecoverable.

- **D-044 (2026-10-25) The shutter is a whole number of mains half-cycles, when the gain can pay for it.**
  Under manual exposure Camera2's antibanding control does nothing, and nothing else in the recorder addressed
  mains flicker: the shutter was whatever the AE settled on, capped at 12 ms. At 30 fps a 50 Hz room beats at
  about 10 Hz, above the 0.7-4 Hz pulse band, so the palm trace was probably never corrupted - but that is
  arithmetic luck, not design, and it would walk into the band if the frame rate ever moved toward 33 fps. The
  exposure now snaps to a multiple of 10 ms. It snaps only when the sensitivity left can absorb the change:
  forcing 10 ms on a scene that wants 2 ms is five times the light, and at the ISO 100 floor that is a blown
  ROI, which is worse than flicker. `clip_meta.json` records whether the shutter the camera actually reported
  came out flicker-free, so the answer is in the data rather than inferred from the constant.
  **Not yet verified on hardware:** the arithmetic is unit-tested, but no clip has been shot under tubes.

- **D-045 (2026-10-25) The ECG readout shows the numbers and says how far to trust them.** The app showed a
  grade word and nothing else: no rate, no beat count, and - worse - `KardiaPdf` was already reading the
  device's own determination, heart rate, mains frequency and filter setting off the strip and `QualityRunner`
  was dropping all four. The regulated device's own label was being parsed and discarded. It is now carried
  through and shown as the device's word, kept apart from the operator's `kardia_determination` answer so it
  cannot quietly fill in a CRF question. Beside it the app shows what it measured itself and a confidence,
  which is the signal-quality grade restated: it is confidence in the number, never in a diagnosis, and a test
  asserts the readout never emits a rhythm name of its own (D-037 keeps that for the clinician).
