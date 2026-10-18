# Sync bench self-test (SWHT-PP-003, protocol section 4.5)

Generated 2026-10-18. Trials: 20. Source: **SYNTHETIC SELF-TEST: generated LED traces, audio and artefact pairs with known offsets, drift and jitter; no camera, buzzer or GPIO was involved. This exercises the detectors and fits only.**

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
| 1 | 0.05 | 0.03 | 0.12 | 0.000669 | 0.19 | 0.00 | 0.43 | pass |
| 2 | 0.03 | 0.04 | 0.08 | 0.000114 | 0.26 | 0.08 | 0.46 | pass |
| 3 | 0.04 | 0.03 | 0.10 | 0.000932 | 0.25 | 0.03 | 0.33 | pass |
| 4 | 0.06 | 0.05 | 0.13 | -0.000996 | 0.23 | 0.03 | 0.33 | pass |
| 5 | 0.02 | 0.02 | 0.07 | 0.000100 | 0.22 | 0.08 | 0.34 | pass |
| 6 | 0.02 | 0.02 | 0.11 | -0.000130 | 0.31 | 0.02 | 0.27 | pass |
| 7 | 0.03 | 0.03 | 0.11 | -0.000030 | 0.34 | 0.03 | 0.30 | pass |
| 8 | 0.04 | 0.03 | 0.19 | -0.001333 | 0.25 | 0.02 | 0.37 | pass |
| 9 | 0.02 | 0.02 | 0.06 | 0.000098 | 0.28 | 0.00 | 0.29 | pass |
| 10 | 0.03 | 0.06 | 0.07 | -0.000787 | 0.27 | 0.06 | 0.44 | pass |
| 11 | 0.03 | 0.06 | 0.06 | -0.000203 | 0.21 | 0.11 | 0.43 | pass |
| 12 | 0.02 | 0.04 | 0.08 | 0.001059 | 0.20 | 0.00 | 0.30 | pass |
| 13 | 0.03 | 0.03 | 0.13 | 0.000346 | 0.22 | 0.06 | 0.48 | pass |
| 14 | 0.03 | 0.01 | 0.09 | 0.000126 | 0.29 | 0.05 | 0.07 | pass |
| 15 | 0.04 | 0.03 | 0.14 | -0.001360 | 0.23 | 0.11 | 0.49 | pass |
| 16 | 0.02 | 0.03 | 0.10 | -0.000006 | 0.25 | 0.01 | 0.32 | pass |
| 17 | 0.04 | 0.06 | 0.08 | 0.000020 | 0.26 | 0.10 | 0.36 | pass |
| 18 | 0.02 | 0.04 | 0.11 | 0.000175 | 0.27 | 0.06 | 0.12 | pass |
| 19 | 0.03 | 0.06 | 0.13 | 0.000550 | 0.19 | 0.10 | 0.41 | pass |
| 20 | 0.04 | 0.04 | 0.10 | 0.000113 | 0.31 | 0.10 | 0.49 | pass |

## What this report shows

Recovery of known offsets by the detector and fitting code on generated signals. It is a software self-test and is labelled as such; it does not stand in for the hardware bench acceptance, which must be run on the rig and reported with `hardware=True`.
