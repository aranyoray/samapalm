# Augmentation study: corruptions ranked by the pulse-rate error they cause

12 clips, 23 transforms, methods GREEN, CHROM, POS, PBV. Error = |rate - reference| in bpm, worst severity, median over clips and methods. Reference = generator truth on synthetic clips, ECG median HR otherwise.

| rank | transform | worst median error (bpm) |
|---|---|---|
| 1 | H264Compress | 62.68 |
| 2 | H265Compress | 47.90 |
| 3 | MicroJitter | 33.42 |
| 4 | ExposureShift | 21.18 |
| 5 | MovingShadow | 10.35 |
| 6 | ShotNoise | 1.96 |
| 7 | Defocus | 1.82 |
| 8 | VFRResample | 1.51 |
| 9 | Downscale | 1.49 |
| 10 | TimestampJitter | 1.41 |
| 11 | FlickerModulation | 1.41 |
| 12 | ChromaSubsample | 1.40 |
| 13 | Perspective | 1.40 |
| 14 | FrameDrops | 1.39 |
| 15 | Quantise8bit | 1.39 |
| 16 | ReadNoise | 1.39 |
| 17 | SyntheticToneShift | 1.39 |
| 18 | IlluminantShift | 1.38 |
| 19 | VignettingGain | 1.37 |
| 20 | MotionBlur | 1.24 |
| 21 | Rotate | 0.95 |
| 22 | Scale | 0.92 |
| 23 | Translate | 0.92 |

Untransformed clips: median error 0.82 bpm.

Synthetic tone shift rows are labelled `SyntheticToneShift` and support no equity claim.
