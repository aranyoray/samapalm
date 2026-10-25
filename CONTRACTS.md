# Interface contracts (read before writing any module)

This file is the single source of truth for how modules talk to each other. The protocol prompt
(section numbers below refer to it) defines *what*; this file defines *shapes*. If a shape here is
wrong for your module, change it here first and note it in DECISIONS.md.

## 0. Ground rules that every module obeys

1. Times in analysis code are **float seconds on the reference clock** (Pi CLOCK_BOOTTIME), relative to
   `Timeline.t0_ref_ns` (first Pi frame). Column name: `t_ref_s`. Never align anything on wall clock or on
   frame index. Wall clock (`wall_ns`) is carried for audit only.
2. Every threshold, band, window length and pattern comes from `Config` (`configs/pipeline.yaml`), accessed
   as `cfg.get("qc.drop_pct_max")`. No magic numbers for protocol quantities.
3. Pi path works on **Bayer planes** (R, G1, G2, B as separate uint16 arrays, half resolution each). Never
   demosaic before pulse extraction. A demosaiced 8-bit preview exists only for hand landmarks and for the
   128x72 proxy video.
4. Phone path works on 8-bit sRGB decoded frames, inverted to "linear-ish" RGB for colour features; the
   output is labelled `linearised_from_srgb = True` and the limitation is stated in the docstring.
5. Optional heavy dependencies (`torch`, `mediapipe`, `picamera2`, `gpiozero`) are imported lazily inside
   functions; the module imports cleanly without them and tests `pytest.importorskip` them.
6. Never hold a full clip in RAM. Readers yield frames or chunks of frames; caches go to zarr/parquet under
   `work/<study_id>/<clip_id>/<camera>/`.
7. Banned vocabulary (enforced by `tests/test_core_lint.py` across the whole repo, docstrings included):
   see `palmppg/core/lint.py`. Describe results as "measured", "agreed within", "not distinguishable".
8. Everything derived from ECG timing is registered `requires_ecg=True`; Bayer-plane/raw-only features are
   `requires_raw=True`. `palmppg.core.tracks.REGISTRY` is the only registry.
9. Seeds: use `palmppg.core.config.rng(seed, salt)`; never bare `np.random`.
10. Tests: `tests/test_<module>_<topic>.py`, each file < 60 s on 4 CPUs, self-contained fixtures. Mark long
    ones `@pytest.mark.slow`.
11. Output tables are parquet (pyarrow); small per-clip summaries are JSON. Booleans are real booleans, missing
    values are `None`/NaN, never sentinel strings.

## 1. Ownership map

| Directory | Owner work package | Contents |
|---|---|---|
| `palmppg/core` | done (do not edit without a DECISIONS note) | config, timeline, crf, tracks, paths, hashing, lint |
| `palmppg/ingest` | WP1 (bayer, calibration, timestamps, phone decode, qc) and WP2 (sync, bench) | see §3, §4 |
| `palmppg/ecg` | WP3 | atc, pdf digitiser, clean, rpeaks, features, artefact onset |
| `palmppg/spatial` | WP4 | landmarks, rois, patches/stmaps, static colour |
| `palmppg/pulse` | WP5 | preprocessing, classical, sqi, fusion, learned, self-supervised, denoising |
| `palmppg/beats` | WP6 | segmentation, morphology, apg, hrv, perfusion, resp, quality, pat |
| `palmppg/features` | WP7 | feature store builders, registry population, stream isolation |
| `palmppg/synth` | WP8 | synthetic participant generator, augmentation library, positive control |
| `palmppg/models` | WP9 | tabular, temporal, cnn, transformer, graph, fm, fusion, uncertainty, track guard |
| `palmppg/eval`, `palmppg/audits` | WP10 | metrics, bootstrap, non-inferiority, calibration, strata engine, go/no-go, audits |
| `palmppg/capture` | WP12 | capture_pi.py, sync_marker.py, offload.sh, phone_settings.md, android/ |
| `palmppg/pipeline`, `palmppg/experiments`, `palmppg/reports`, `palmppg/cli.py` | phase 2 (integration) | per-participant runner, E0-E17, reports, CLI |

## 2. Core API cheat sheet

```python
from palmppg.core.config import load_pipeline_config, load_frozen_config, verify_frozen, rng, seed_everything
cfg = load_pipeline_config()                 # Config; cfg.get("sync.p1.pulses") -> 3; cfg.section("qc") -> dict
from palmppg.core.timeline import Timeline, ClockMap, Window, Event, detect_drops, resample_to_grid, uniform_grid
tl = Timeline(study_id, clip_id, t0_ref_ns)  # t0 = first Pi frame sensor_ts_ns
tl.set_map(ClockMap.identity("pi_frames"))
tl.set_map(ClockMap.fit(native_s, ref_s, "phone_video", method="led_pattern"))
tl.add_event("p1_onset", t_ref_s, uncertainty_s, source="pi_video")
tl.derive_analysis_window(cfg.get("window.static_colour_s"), cfg.get("window.tail_exclusion_s"), clip_end_s=...)
tl.grade(fine_anchor_found, p1_found, p2_found, xcorr_agree, coarse_anchor_found, ecg_map_method)
tl.valid_mask(t_ref_s); tl.save(path); Timeline.load(path)
from palmppg.core.crf import derive, derive_file, covariate_columns
from palmppg.core.tracks import REGISTRY, FeatureMeta, filter_frame, assert_product_candidate_clean, TrackViolation
REGISTRY.add("pulse__pi__thenar__POS__hr_bpm", group="pulse", camera="pi", requires_raw=True)
from palmppg.core.paths import StudyLayout, ParticipantPaths, WorkLayout, TestStreamGuard
```

## 3. On-disk raw formats (section 3 of the protocol)

### 3.1 Pi raw: `pi/clip1.raw`
* Concatenated frames, no header. Each frame is `stride_bytes * height` bytes.
* 10-bit packed CSI-2 (`SRGGB10_CSI2P`): every 4 pixels occupy 5 bytes. Bytes 0..3 hold the high 8 bits of
  pixels 0..3; byte 4 holds the low 2 bits: bits 0-1 -> px0, 2-3 -> px1, 4-5 -> px2, 6-7 -> px3.
* `stride_bytes` = `meta["stride_bytes"]` if present else `ceil(width * 10 / 8)` rounded up to a multiple of 32.
  For 1536 wide, stride is 1920.
* Bayer order from `meta["bayer_pattern"]` (default `RGGB`): R at (even row, even col), G1 at (even, odd),
  G2 at (odd, even), B at (odd, odd). Plane arrays are `(height/2, width/2)` uint16, values 0..1023.
* Black level `pi.black_level` (64) is subtracted after dark-frame subtraction only if no dark frame exists.
* Unit calibration: `units/unit_##/darkframe.raw` (one packed frame, same geometry), `flatfield.raw` (one packed
  frame of the white card), `luxmap.json` (`{"lux_grid": [[...]], "rows": r, "cols": c}` optional).
* Calibrated plane = `(plane - dark) / max(flat_norm, eps)` where `flat_norm` = `(flat - dark)` divided by its
  central-region mean, computed per Bayer plane.

### 3.2 `pi/clip1_pts.csv`
Columns, in order: `frame_idx, sensor_ts_ns, wall_ns, exposure_us, analogue_gain, digital_gain, lux`.
`sensor_ts_ns` is CLOCK_BOOTTIME ns (= reference clock). Rows may be missing when frames were dropped.

### 3.3 `pi/clip1_meta.json`
Keys: `unit_id, operator, dept, stream, app_ver, study_id, clip_id, width, height, stride_bytes, bayer_pattern,
bit_depth, fps_nominal, crop_rect {x,y,w,h} | null, exposure_us, analogue_gain, digital_gain, awb_gains [r,b],
lens_position, led_current_ma, lux, sensor_temp_c, start_wall_ns, stop_wall_ns, start_mono_ns, stop_mono_ns,
live_sqi, motion_flag, recovery_gate, video_seconds, capture_mode, n_frames_written, led_block {x,y,w,h},
thumb_block {x,y,w,h}`.
`led_block`/`thumb_block` are in full-resolution Bayer coordinates of the written frame (after crop).

### 3.4 `pi/sync_events.csv`
Columns: `event_id, kind, pattern, mono_ns, wall_ns, gpio_ok`. `kind` in {`start`,`end`} = LED rising/falling edge.
`pattern` in {`P1`,`P2`}. One row per edge: P1 contributes 3 start + 3 end rows, P2 2 + 2.

### 3.5 Phone
* `phone/clip1.mp4`: H.264, 1080p30 nominal, audio AAC mono 48 kHz with the buzzer tone. Treat as VFR.
* `phone/clip1_meta.json`: `app, device_model, os_build, resolution [w,h], fps_nominal, bitrate_mbps, iso,
  exposure_ns, wb_locked, focus_locked, stabilisation, hdr, torch, capture_mode, start_wall_ns, led_block {x,y,w,h} | null,
  study_id, clip_id`.
* `phone/clip1_frames.csv` (optional, custom recorder only): `frame_idx, sensor_ts_ns, wall_ns, iso, exposure_ns`.
* `phone/clip1_controls.csv` (optional, onboarding app recorder): `frame_idx, sensor_ts_ns, iso, exposure_ns, focus_diopters,
  lens_state, zoom_ratio, gain_r, gain_g_even, gain_g_odd, gain_b, awb_mode, ae_mode, af_mode, tonemap_mode, shading_mode,
  flash_state` — what the camera reported on every recorded frame, same `frame_idx`/`sensor_ts_ns` as `clip1_frames.csv`;
  Camera2 enum values as integers (AF/AE/AWB `0` = OFF, lens_state `0` = STATIONARY, tonemap `0` = CONTRAST_CURVE,
  shading `0` = OFF, flash_state `3` = FIRED). A pinned clip has one ISO, one exposure, one focus value and no MOVING frames.
* `phone/clip1_roi.csv` (optional, onboarding app recorder): `roi_idx, sensor_ts_ns_raw, t_ref_ns, n_px, y_mean, u_mean, v_mean,
  r_mean, g_mean, b_mean, clip_frac, g00 .. g22` — mean colour of the centred 40 % ROI taken from the camera's YUV stream
  *before* H.264, one row per analysis frame, plus a 3x3 grid of Y means. `sensor_ts_ns_raw` is bit-identical to the video
  frames' `SENSOR_TIMESTAMP`, so it joins to `clip1_frames.csv`. 8-bit sRGB code values (BT.601 full-range YUV -> RGB on the
  means); not linearised, not flat-fielded. Read with `palmppg.ingest.phone_tap`; `ingest_phone` writes it alongside the
  decoded means as `mean_intensity_tap.parquet` and never in their place.
* `clip1_meta.json` additional keys (onboarding app recorder, D-033): `lock_applied, awb_applied, distance_cm,
  controls_file, roi_file, roi_rows, controls {camera_id, preferred_physical_id, focus {distance_cm, requested_diopters,
  applied_diopters, clamped_to_lens, lens_minimum_focus_distance_diopters, calibration, reported_diopters,
  af_mode_reported, lens_state_reported}, exposure {settled_ns, settled_iso, requested_ns, requested_iso, capped_to_ns,
  was_capped, iso_saturated, reported_ns, reported_iso, ae_mode_reported, metered_on_roi}, white_balance {applied,
  awb_mode_reported, gains_rggb, transform_row_major}, tonemap_mode_requested, tonemap_mode_reported,
  shading_mode_reported, aberration_mode_reported, zoom_ratio_reported, flash_state_reported, result_fps,
  analysis_resolution, preflight {ok, warnings, exposure_correction_factor}}`.
* `clip1_meta.json` `controls.exposure` additional keys (onboarding app recorder, D-044): `mains_hz,
  mains_half_cycle_ns, flicker_free, flicker_free_requested`. `flicker_free` is read off the shutter the
  camera reported, not the one requested, so it says whether the clip actually is flicker-free.
* `clip1_meta.json` additional keys (onboarding app recorder, D-040): `requested_ecg_lead_in_s,
  requested_ecg_lead_out_s` — the ECG runs before and after the clip, so the clip is a window inside a longer
  ECG record. The lead-out is `0.0` when the clip was interrupted.
* `clip1_sync.json` additional key (onboarding app recorder, D-040): `clip_window {clip_start_ref_ns,
  clip_stop_ref_ns, requested_lead_in_s, requested_lead_out_s, interrupted, measured_lead_in_s,
  measured_lead_out_s, clip_start_sample_idx, clip_stop_sample_idx, note}` — where the clip sits inside the ECG
  record, on the reference clock and as sample indices into `clip1_ecg_samples.csv`. The measured lead is what
  was captured, which is shorter than requested when the stream started late or stalled; the sample indices can
  fall outside the record for the same reason and must be clamped by the reader.
* `clip1_ecg_meta.json` additional keys (onboarding app recorder, D-040): `lead_in_s, lead_out_s, window_note`.

### 3.6 ECG
* `ecg/kardia_####.atc`: AliveCor ATC v1 chunk file. Header: `b"ALIVE"` + 3 version bytes (8 bytes). Then
  blocks: `u32 length` (LE), `4-byte id`, `data[length]`, `u32 crc32`. Blocks: `info` (date 32 B ASCII ISO8601,
  uuid 40 B, phone udid 44 B, phone model 32 B, recorder sw 32 B, recorder hw 32 B, location 52 B), `fmt ` (u8 format,
  u16 frequency Hz, u16 resolution in nV/LSB (500), u8 flags, u16 reserved), `ecg ` (int16 LE samples lead I),
  optional `ann ` annotations. Unknown blocks are skipped. The parser is tolerant: a bad CRC is logged, not fatal.
  This layout must be re-checked on the first real file (DECISIONS D-007).
* `ecg/kardia_meta.json`: `start_wall_ts` (ISO8601 on the Kardia device clock), `duration_s, fs, app_rhythm_label,
  device_id, export_format` ("atc" | "pdf").
* `ecg/kardia_####.pdf`: Kardia strip; digitiser assumes 25 mm/s, 10 mm/mV, red/pink grid, dark trace.
* `clinician.json`: `rhythm` in cfg `ecg.rhythm_classes`, `ecg_hr` (bpm), `lead12_obtained` (bool),
  `adverse_event` (str|null), `reader_id, read_date`.

### 3.7 `crf.json`
One file per participant, `participants/<PID>/crf.json`. v2 (schema `2026-10-24.1`, `docs/onboarding_v2_design.md`
section 7): `palmppg crf pull` merges the enrol and scan parts of a PID; the questions of both parts sit at top level
(ids are unique across parts) and `parts: {enrol: {...}, scan: {...}}` holds each part's context (`part`, `operator`,
`unit_id`, `app_ver`, `device_code`, `capture_mode`, `schema_version`, `status`, `submitted_at`; scan also
`clip_plan`). bp1/bp2/bp3 are objects `{sbp, dbp, hr, wall_ts}`; `conditions`, `acute_30m`, `strata`, `scan_strata`
are lists; clips are the records of design section 2.4. No name, phone or hospital number ever appears.
v1 files (schema `2026-10-20.1`, section 3.1 names, `flags`, `hba1c`, boolean `pregnant`) are still read:
`palmppg.core.crf.derive` maps v1 flags onto conditions and fills the same covariates for both.

### 3.8 `clock_sync_log.csv`
`date, time_utc, device, offset_ms_vs_phone, method, operator`. `device` in {`pi_unit_01`, `kardia_tablet`, ...}.

## 4. Derived artefacts under `work/<study_id>/<clip_id>/`

| Path | Producer | Shape |
|---|---|---|
| `timeline.json` | ingest.sync | `Timeline.to_dict()` |
| `pi/qc.json`, `phone/qc.json` | ingest.qc | flat dict of flags + numbers (see §4.1) |
| `pi/frame_times.parquet` | ingest.timestamps | `frame_idx, t_ref_s, wall_ns, exposure_us, analogue_gain, digital_gain, lux, dropped_before (int)` |
| `phone/frame_times.parquet` | ingest.phone | `frame_idx, pts_s, t_ref_s, dropped_before` |
| `<camera>/landmarks.parquet` | spatial.landmarks | `frame_idx, t_ref_s, source, confidence, is_left, palmar, lm00_x..lm20_z` (normalised image coords, z relative) |
| `<camera>/rois.json` | spatial.rois | `{roi_name: {"polygon": [[x,y],...], "frame_idx": i, "n_pixels": n}}` in full-res image coords; `thumb` present for exclusion |
| `<camera>/traces.parquet` | spatial.traces | uniform grid: `t_ref_s, frame_idx` + `<roi>__<ch>__mean`, `<roi>__<ch>__median`, `<roi>__npix`, `<roi>__sat_frac`; channels `R,G1,G2,B` (pi) or `R,G,B` (phone, pi_proxy); NaN in dropped frames |
| `<camera>/patches.zarr` | spatial.stmaps | array `(n_frames, rows, cols, n_ch)` float32 means on the grid; attrs: channels, t_ref_s |
| `<camera>/proxy_128x72.zarr` | ingest | `(n_frames, 72, 128, 3)` uint8 demosaiced sRGB preview, attrs t_ref_s |
| `<camera>/static_colour.json` | spatial.static_colour | §6.2 features, first 2 s only, plus `colour_space` ("linear_raw" or "inverted_srgb") |
| `<camera>/pulse.parquet` | pulse | `t_ref_s` + `<method>__<roi>` columns (band 0.5-4 Hz, z-scored) |
| `<camera>/pulse_morph.parquet` | pulse | same columns, band 0.4-8 Hz |
| `<camera>/pulse_sqi.json` | pulse | `{"<method>__<roi>": {"sqi": .., "snr_db": .., "hr_bpm": ..}, "best": "<method>__<roi>", "fused": {...}}` |
| `<camera>/beats.parquet` | beats | one row per beat: `foot_t, peak_t, notch_t, ibi_s, quality, <morphology columns>` |
| `<camera>/beat_features.json` | beats | clip-level aggregates: hrv, morphology ensemble, apg, perfusion, resp |
| `ecg/ecg_clean.parquet` | ecg | `t_ecg_s` (native), `t_ref_s` (NaN until mapped), `mv` |
| `ecg/rpeaks.parquet` | ecg | `idx, t_ecg_s, t_ref_s, detector_agree` |
| `ecg/ecg_features.json` | ecg | hr, ibi stats, rhythm features, `clinician_rhythm`, `app_rhythm_label`, `ecg_digitised` |
| `ecg/artefact.json` | ecg | `{"onset_t_ecg_s": .., "score": .., "found": bool}` |
| `<camera>/pat.json` | beats.pat | `requires_ecg: true`, pairing rate, PAT mean/SD, ectopic capture fraction (grade fine only) |
| `features_<camera>.parquet` | features | one row per clip per camera |

### 4.1 `qc.json` keys (both cameras; NaN/None when not applicable)
`camera, study_id, clip_id, n_frames, duration_s, fs_median, drop_pct, drop_flag, saturation_frac, saturation_flag,
flicker_peaks_hz (list), flicker_flag, lighting_drift_pct, lighting_drift_flag, vignetting_residual_pct,
vignetting_flag, hand_detected, hand_is_left, hand_palmar, landmark_source, landmark_jitter_px, motion_flag,
eis_warp_px, eis_flag, sync_grade, sqi_best, sqi_flag, valid_clip, reasons (list of failing flag names)`.
`valid_clip` = hand_detected and not drop_flag and not saturation_flag and not flicker_flag and sqi_best >= threshold.

## 5. Feature naming and registry

Column = `group__camera__roi__method__name`, parts omitted when not applicable
(`palmppg.core.tracks.feature_prefix`). `camera` in {pi, phone, pi_proxy}. Every column written to a feature
table is registered first (`REGISTRY.add(...)`). ECG-derived and PAT: `requires_ecg=True`. Bayer-plane,
10-bit or uncompressed-only features: `requires_raw=True`. Phone and pi_proxy features: `requires_raw=False`.

## 6. Signal conventions

* Pulse signal polarity: positive deflection = increase in blood volume (i.e. the *negated* green intensity).
  All classical methods return the signal in this polarity.
* Pre-processing (`palmppg.pulse.preprocess`): `detrend_smoothness_prior(x, lam)`, `bandpass(x, fs, lo, hi,
  order=4, zero_phase=True)`, `zscore(x)`; NaN gaps are linearly bridged for filtering and restored to NaN after.
* SQI in [0, 1]: `snr_band` = clipped, scaled SNR in dB of the dominant peak in 0.5-4 Hz (power in +/-0.1 Hz
  around the peak and its first harmonic versus the rest of the band), per 10 s window, median over windows.
* Instantaneous rate series for sync cross-correlation: from beat intervals, interpolated to `sync.xcorr.rate_fs`.

## 7. Model tracks

`palmppg.models.track.TrackGuard(track)` wraps every estimator: on `fit(X)` it calls
`REGISTRY.check_columns(X.columns, track)` and raises `TrackViolation` for forbidden columns. Experiment
configs declare `track:`; results tables carry a `track` column. Only `product_candidate` results may be
described as product results in reports.

## 8. Artefacts added during integration (2026-10-18)

| Path | Producer | Shape |
|---|---|---|
| `sync.json` | ingest.sync `write_sync_json` | full sync report: `grade`, `grade_detail`, `offsets.<stream>.{offset_s, drift, uncertainty_s, method}`, `pi_video`, `phone`, `ecg.{thumb_contact, wall_clock, anchor_comparison, thumb_lift, fine, map, xcorr}`, `residuals`, `flags` |
| `pipeline.json`, `pipeline_rerun.json` | pipeline.run_participant | per-stage status, seconds, error and traceback; `ok`; per-camera QC summary |
| `landmarks_provider.json` | pipeline.run_participant | ground-truth landmarks adapted to the SyntheticLandmarkProvider layout |
| `ecg/rate_series.parquet` | ecg.run | `t_ecg_s, bpm` at `sync.xcorr.rate_fs` |
| `<camera>/mean_intensity.parquet`, `mean_intensity_grid.parquet` | ingest.run | per-frame and grid mean intensities per plane/channel |
| `<camera>/ingest.json` | ingest.run | calibration, drops, flicker detail, EIS detail, proxy info |
| `<camera>/spatial_summary.json`, `traces_meta.json` | spatial.run | landmark summary for QC; trace channel metadata |
| `<camera>/pulse_rate.parquet`, `pulse_run.json` | pulse.run | instantaneous rate of the best signal; fusion weights and run detail |
| `pulse_sqi.json` `selection` | pulse.run `select_best` | `{mode, n_candidates, agreement, score, consensus_hr_bpm, raw_sqi}` (D-023) |
| `<camera>/pat_pairs.parquet` | beats.run | R-peak to foot pairs (grade fine only, requires_ecg) |
| `features_<camera>.parquet` | pipeline.run_participant via features.store | one row per clip per camera |
| `work/tables/pipeline_runs.parquet` | pipeline.run_cohort | one row per clip: ok, sync grade, failed stages, valid flags |
| `work/experiments/<E>/results.{json,md}`, `preds_*.parquet` | experiments.runner | per-experiment results; out-of-fold predictions with both baselines |
| `work/augmentation/*` | experiments.augmentation_study | degradation, curves, ranking, benign check, ablation, transform logs |
| `work/reports/*` | reports.build | every report page; regenerated by `palmppg reports build` |

`qc.json` gained `qc_series_source` (`whole_palm_trace` or `whole_frame`, D-019).

## 9. Onboarding app and backend (2026-10-20; v2 2026-10-24)

* `configs/crf_schema.json` (schema_version `2026-10-24.1`) is the CRF definition shared by the Android app and the
  pipeline. `settings.part` (enrol | scan) and `settings.clip_plan` (1x60 | 2x30) pick the flow: `flows[part]` when it
  exists, else `flows[part_clipplan]` (flows `enrol`, `scan_1x60`, `scan_2x30`; the `pid` screen is shared). Engines:
  `palmppg/core/crf_schema.py` and `org.samahealth.crf.CrfEngine`, identical on `configs/crf_fixtures/golden.json`.
* Export of one part (`CrfEngine.export` returns the CRF only; Kotlin `Exported(crf)`): answered visible questions
  (consent is not exported; `irregular_pulse` as a boolean), the exported derivations (`bmi`, `trimester`,
  `mentzer`, `hplc_reflex`, `anaemia_grade`, `haem_cell`, `dm_label`, `strata` for enrol; `recovery`,
  `bracket_flag`, `scan_strata` for scan), the context keys (`operator`, `unit_id`, `app_ver`, `device_code`,
  `capture_mode`, `screen_log`), `part`, `schema_version` and, for the scan part only, `clip_plan`. Names stay on the
  paper consent form: there is no identity record and no `initials`. Clip records are objects
  `{started_at, ended_at, quality, kardia_on, beep_heard, notes, phone_file?, ..., kardia_determination?}` (design 2.4).
* Strata keys (`sex:F`, `mst:7`, `mstgrp:dark`, `cond:htn`, `haem:ida`, `dm:no_known`, `preg:yes`, `sex_mst:F:7`,
  `cond_mstgrp:htn:dark`, `haem_mstgrp:ida:dark`, `rhythm:af`, `scan:done`) are the cell keys of
  `configs/recruitment_targets.json`; priority and cell fill: `palmppg/core/strata.py` and `org.samahealth.crf.Strata`,
  identical on `configs/crf_fixtures/strata_golden.json` (design section 3).
* Supabase: `public.visits` (one row per PID and part: visit_uuid, pid, part, status draft|submitted|screen_fail|void,
  crf jsonb, ...), `public.visit_audit`, `public.devices`, `public.operators`, `public.recruitment_targets`, view
  `public.participant_export` (one row per PID, both parts) and legacy `public.crf_export`. `public.identity` is kept
  for legacy rows only. Schema: `supabase/migrations/0001_init.sql`, `0002_two_parts.sql`.
* `palmppg crf pull --study-root <dir>` writes the merged `participants/<PID>/crf.json` (section 3.7) for submitted
  parts and `onboarding/{screen_failures.csv, crf_export_<UTC>.csv, pull_log.jsonl}`.
* Quality grades (design section 4): `palmppg/quality/onsite.py` and the Kotlin module `android/quality-core`
  (`org.samahealth.quality`) implement the same rules and are pinned by `configs/quality_fixtures/*.json`, which
  `tools/make_quality_fixtures.py` writes. `Grade(level, reasons, metrics)` with level `good | borderline | retake`.
  Readers: `RoiCsv` and `FramesCsv` over the recorder's `<clip>_roi.csv` and `<clip>_frames.csv`, `EcgCsv` over
  `<clip>_ecg_samples.csv`, `AtcReader` over ATC, and `KardiaPdf`, which reads the vector trace out of a Kardia PDF
  export (300 Hz, calibration pulse for the mV scale, strips ordered top to bottom) rather than rasterising it.
  Before scoring, the ECG goes through a 50 Hz mains notch (RBJ, Q 30) and then the 0.5-40 Hz band-pass
  (D-043); `mains_hz`/`mains_q` in the config turn it off or move it to a 60 Hz site. `EcgSummary.summarise`
  gives the participant-facing wording and never names a rhythm. The BLE ECG is graded
  over the clip window from `clip1_sync.json`, not over the whole record (D-040): the lead is kept in the file
  for analysis but is not part of the clip, and the participant's fingers may not be on the electrodes during
  it. An imported Kardia file has no window and is graded whole, as before. The app writes the grades
  into the clip record as `video_grade`/`video_reasons`/`video_metrics` and `ecg_grade`/`ecg_reasons`/`ecg_metrics`,
  with `ecg_file` and `ecg_source` (`ble | kardia_pdf | kardia_atc`). A Kardia export also carries the
  device's own printed reading, which is kept as `ecg_device_determination`, `ecg_device_hr`,
  `ecg_device_mains_hz` and `ecg_device_enhanced_filter` (D-045). These are the device's word, shown as such;
  they never fill in the operator's own `kardia_determination` and `kardia_hr` answers.
* ECGFounder preprocessing (design section 9): `palmppg/ecg/founder_prep.py` is the chain (resample to 500 Hz,
  polarity check, 10 s windows, 50 Hz notch and Butterworth 0.67-40 Hz forward and backward, minus a 0.4 s running
  median, z-score) and is importable without torch; `palmppg/ecg/founder.py` re-exports it and adds the vendored
  network. `android/ecg-model` (`org.samahealth.ecgmodel.FounderPrep`) is the Kotlin port, pinned by
  `configs/founder_fixtures/preprocess.json` from `tools/make_founder_fixtures.py`. The exported graph takes
  `ecg` float32 `[batch, 1, 5000]` and returns `logits` and `probs` `[batch, 150]`; window probabilities combine as
  max for the ectopy and pause labels and mean for the rest. Model output is a research pre-read for the study
  clinician only, never a participant result.
