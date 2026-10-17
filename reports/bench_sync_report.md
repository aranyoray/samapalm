# Sync bench self-test (SWHT-PP-003, protocol section 4.5)

Generated 2026-10-17. Trials: 20. Source: **SYNTHETIC SELF-TEST: generated LED traces, audio and artefact pairs with known offsets, drift and jitter; no camera, buzzer or GPIO was involved. This exercises the detectors and fits only.**

## Acceptance criteria (from configs/pipeline.yaml)

- LED onsets: Pi video and phone video edges within 1.0 frame period(s) of the Pi log after one offset (+ drift when >= 4 edges), at least 6 edges matched (D-003).
- Audio: beep edges within 20 ms of the Pi log after one offset.
- Artefact: card-tap pair (video event vs ECG artefact) within 0.033 s (one frame).

## Summary

| criterion | pass | checkable | trials |
|---|---|---|---|
| pi_video | 20 | 20 | 20 |
| phone_video | 20 | 20 | 20 |
| audio | 20 | 20 | 20 |
| artefact | 20 | 20 | 20 |
| **all four** | **20** | 20 | 20 |

Overall: 20/20 trials pass every criterion: **ACCEPTED** (synthetic self-test; hardware acceptance still outstanding)

## Per-trial results

| trial | Pi video max resid (frames) | phone video max resid (frames) | phone offset err (frames) | phone drift | audio max resid (ms) | audio offset err (ms) | artefact err (frames) | pass |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.02 | 0.02 | 0.06 | -0.000580 | 0.20 | 0.02 | 0.28 | pass |
| 2 | 0.03 | 0.02 | 0.16 | 0.001120 | 0.23 | 0.04 | 0.43 | pass |
| 3 | 0.06 | 0.04 | 0.20 | 0.001318 | 0.20 | 0.00 | 0.28 | pass |
| 4 | 0.03 | 0.03 | 0.12 | -0.000327 | 0.17 | 0.06 | 0.15 | pass |
| 5 | 0.03 | 0.03 | 0.05 | 0.000328 | 0.25 | 0.07 | 0.39 | pass |
| 6 | 0.05 | 0.03 | 0.13 | 0.001213 | 0.25 | 0.02 | 0.31 | pass |
| 7 | 0.02 | 0.03 | 0.09 | -0.000028 | 0.24 | 0.03 | 0.23 | pass |
| 8 | 0.02 | 0.05 | 0.11 | -0.000006 | 0.23 | 0.07 | 0.17 | pass |
| 9 | 0.03 | 0.04 | 0.11 | -0.000543 | 0.35 | 0.03 | 0.41 | pass |
| 10 | 0.06 | 0.04 | 0.12 | 0.000834 | 0.23 | 0.09 | 0.54 | pass |
| 11 | 0.08 | 0.04 | 0.07 | 0.000171 | 0.31 | 0.01 | 0.19 | pass |
| 12 | 0.02 | 0.03 | 0.10 | -0.000004 | 0.26 | 0.03 | 0.24 | pass |
| 13 | 0.02 | 0.02 | 0.06 | -0.000300 | 0.14 | 0.02 | 0.47 | pass |
| 14 | 0.05 | 0.03 | 0.13 | -0.000904 | 0.28 | 0.09 | 0.34 | pass |
| 15 | 0.01 | 0.03 | 0.06 | -0.000116 | 0.25 | 0.05 | 0.40 | pass |
| 16 | 0.02 | 0.03 | 0.12 | 0.000067 | 0.31 | 0.01 | 0.24 | pass |
| 17 | 0.01 | 0.02 | 0.14 | 0.000319 | 0.21 | 0.01 | 0.05 | pass |
| 18 | 0.05 | 0.03 | 0.19 | 0.001451 | 0.29 | 0.05 | 0.45 | pass |
| 19 | 0.02 | 0.05 | 0.12 | 0.000552 | 0.18 | 0.01 | 0.15 | pass |
| 20 | 0.03 | 0.05 | 0.19 | -0.001348 | 0.24 | 0.05 | 0.33 | pass |

## What this report shows

Recovery of known offsets by the detector and fitting code on generated signals. It is a software self-test and is labelled as such; it does not stand in for the hardware bench acceptance, which must be run on the rig and reported with `hardware=True`.
