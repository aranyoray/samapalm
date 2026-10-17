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
