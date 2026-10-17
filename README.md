# palmppg: SWHT-PP-003 camera palm photoplethysmography pilot

Single-site pilot (Medical College and Hospital, Kolkata; n = 500 nested in a planned 8,000) of calibration-free
resting blood pressure and rhythm estimation from a 60 s video of the left palm. Two cameras record the same palm:
a Raspberry Pi Camera Module 3 Wide (raw Bayer, the lab reference) and a OnePlus 12 (compressed consumer video, the
product proxy). A single-lead AliveCor KardiaMobile Card ECG runs during the clip; three cuff readings bracket it.

This repository holds the capture toolkit, the ingest and synchronisation layer, the analysis pipeline, the synthetic
augmentation study, the evaluation and audit code, and the report generators. It reports what was measured.

## Two tracks, enforced in code

| track | may use | may be called |
|---|---|---|
| `product_candidate` | phone-camera features, or Pi features restricted to an 8-bit sRGB compressed proxy; no ECG | a product result |
| `science` | Pi raw Bayer features, ECG-aligned features, pulse arrival time | a science result, reported separately |

`palmppg.core.tracks.REGISTRY` tags every feature column with `requires_ecg` and `requires_raw`;
`palmppg.models.track.TrackGuard` refuses to fit a `product_candidate` model on a forbidden column.

## Run order (documented, in this order; see DECISIONS.md and PREREGISTRATION.md)

1. Synthetic data and positive control: `palmppg synth cohort --n 3` then `palmppg synth positive-control`.
2. Bench sync acceptance: `palmppg bench report <trials_dir>` (20 hardware trials; the synthetic self-test is labelled as such).
3. First 10 participants end to end with the manual review notebook: `palmppg pipeline run --study-root ... --limit 10`.
4. First 100: QC, sync grades, augmentation study, interim go/no-go dashboard with no thresholds changed:
   `palmppg augment study --n 100`, `palmppg gonogo --interim`.
5. Pilot 500 with the frozen config: `palmppg experiments run-all`, `palmppg reports build`.

Every figure and table regenerates from `palmppg reports build`. Experiments are tracked in MLflow (`./mlruns`).

## Environment

```
uv venv .venv && uv pip install --python .venv/bin/python -r environment.lock && uv pip install --python .venv/bin/python -e .
.venv/bin/python -m pytest tests -q          # must be green on synthetic data before any real data is touched
docker build -t palmppg . && docker run --rm palmppg --help
```

CPU-only by default. Deep models train on one GPU when present (`--device cuda`); the pilot scale runs on CPU too.
Pi-only packages (`picamera2`, `gpiozero`) and MediaPipe are optional extras; every module imports without them.

## Layout

```
palmppg/
  core/      config, reference-clock timeline, CRF derivations, track registry, study layout, vocabulary lint
  capture/   capture_pi.py, sync_marker.py, clock_sync.sh, offload.sh, phone_settings.md, android/
  ingest/    Bayer unpack, unit calibration, timestamps, phone decode, Pi proxy chain, QC, LED/audio/ECG sync, bench
  ecg/       ATC parser, PDF digitiser, cleaning, R-peaks, rhythm features, artefact onset
  spatial/   hand landmarks, palm ROIs, patch grid and STMaps, static colour
  pulse/     preprocessing, classical rPPG methods, SQI, fusion, learned and self-supervised models, denoising
  beats/     beat segmentation, morphology, APG, HRV, perfusion, respiratory proxy, PAT (requires ECG)
  features/  feature store, participant-level splits, manifests, stream isolation, data dictionary
  synth/     synthetic participants with a known pulse, augmentation library, positive control
  models/    tabular, temporal, CNN, transformer, graph, adversarial, foundation-model interfaces, fusion, uncertainty
  eval/      metrics, participant bootstrap, non-inferiority, calibration, strata engine, go/no-go, plots
  audits/    shortcut, equity, leakage, partition balance, Pi-versus-phone
  experiments/  E0 to E17 runners
  reports/   STARD flow, TRIPOD+AI checklist, strata tables, model cards, data dictionary, bench report
  pipeline/  per-participant runner
configs/     pipeline.yaml, unit_config.yaml, frozen_config.yaml (signed), experiments/
data/        manifests, splits, hashes (the study data itself is mounted, never committed)
tests/       unit and pipeline tests on synthetic data
```

## Data layout expected on the study mount

See CONTRACTS.md section 3 (it mirrors protocol section 3). The locked prospective test stream lives on a separate
mount (`paths.test_root`) behind `TestStreamGuard`: one read, logged.

## What this repository never claims

Single site, one visit per person, cuff reference that brackets rather than accompanies the clip. Results are
reported overall and per stratum with participant-level bootstrap intervals, always next to a predict-the-mean and a
demographics-only baseline, with negative results in the same table format as positive ones.
