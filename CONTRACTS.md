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
* Per-frame PTS from ffprobe (`-show_frames -select_streams v:0` -> `pts_time`, `pkt_pts_time` fallback).

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
Section 3.1 field names verbatim; bp1/bp2/bp3 are objects `{sbp, dbp, hr, wall_ts}`; `flags`, `acute_30m` are lists.

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

## 9. Onboarding app and backend (2026-10-20)

* `configs/crf_schema.json` is the CRF definition shared by the Android app and the pipeline; the export of a submitted
  visit is the `crf.json` of CONTRACTS section 3.7 plus the add-on keys listed in `docs/hypotheses_crf_map.md`,
  `screen_log`, `schema_version`, `clip_plan`, `device_code` and `capture_mode`. Clip records are objects
  `{started_at, ended_at, quality, kardia_on, beep_heard, notes, phone_file?}`.
* Supabase: `public.visits` (one row per participant: visit_uuid, pid, status draft|submitted|screen_fail|void, crf
  jsonb, ...), `public.identity` (pid, name, hospital_reg_no, phone), `public.visit_audit`, `public.devices`,
  `public.operators`, view `public.crf_export` (flat, no identity). Schema: `supabase/migrations/0001_init.sql`.
* `palmppg crf pull --study-root <dir>` writes `participants/<PID>/crf.json` for submitted visits and
  `onboarding/{screen_failures.csv, crf_export_<UTC>.csv, pull_log.jsonl}`.
