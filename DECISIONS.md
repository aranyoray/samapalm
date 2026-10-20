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
