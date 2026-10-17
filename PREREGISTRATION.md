# Pre-registered analysis plan: SWHT-PP-003-2026 pilot

Frozen on 2026-10-17 before any participant data is processed. Thresholds below are also in
`configs/frozen_config.yaml`, whose sha256 signature is checked by every experiment runner; editing the file after
signing halts the pipeline until a dated DECISIONS.md entry explains the re-signing.

## Design

Single site (Medical College and Hospital, Kolkata), adults, one visit each. Visit: BP1 on seating; history and CRF
during a 5-minute seated rest; BP2; one palm clip of `video_seconds` (60 s) with the KardiaMobile Card held between
both thumbs; BP3. One re-shoot only when quality fails. Pilot n = 500 nested in a planned 8,000 split into streams:
pilot 500, development 4,500, model selection 1,000, locked prospective test 2,000 (separate mount, read once, logged).

Reference BP = mean of BP1, BP2, BP3; BP1 is dropped when it deviates more than 15 mmHg from the BP2/BP3 mean.
Sensitivity analysis: mean of BP2 and BP3. Cuff readings bracket the clip; they are not simultaneous with it.
Rhythm reference = clinician read of the single-lead ECG. The Kardia app label is a covariate only.

## Endpoints

* Primary: calibration-free resting SBP and DBP in unseen people (participant-level grouped cross-validation).
* Key secondary: AF versus sinus, and AF versus hard non-AF rhythms (flutter, SVT, frequent ectopy, paced).
* Secondary: coverage; pulse rate versus ECG HR; repeatability on re-shot clips; accuracy across MST bands and disease
  groups.
* Exploratory: glucose boundary (a negative result is expected and will be reported in full), anaemia and thalassaemia
  effects, vascular age, and pulse arrival time against ECG where the sync grade is `fine`.

## Pilot go/no-go (frozen; evaluated once, not tuned)

| criterion | threshold |
|---|---|
| coverage overall | at least 90 percent of attempted clips produce a non-abstained reading |
| coverage equity | drop for MST 7-10 versus 4-6 no larger than 10 points |
| pulse rate versus ECG (Pi) | within 3 bpm in at least 95 percent of valid clips; phone figure reported alongside |
| temporal palm features | reduce SBP error SD by at least 2 mmHg over demographics-only in grouped CV |

If any criterion fails the pilot stops and the failure is reported with the same table quality as a success.

## Analysis plan

* Splits by participant only; nested 5-fold grouped CV on the pilot. Augmented copies never sit in a validation fold
  of their source clip. Failed and abstained readings count as failures in coverage.
* Every metric table carries two baselines (predict-the-mean, demographics-only) and a static-versus-temporal
  ablation with a pulse-shuffled leakage control.
* Every metric is reported overall and per stratum (protocol section 7) with n per cell and participant-level
  bootstrap 95 percent intervals (2,000 resamples); cells under 20 are pooled and labelled.
* BP: bias, error SD, MAE, 95 percent limits of agreement, error by reference tertile and by `bracket_flag`,
  coverage; AAMI-style and IEEE 1708-style tables are formats, not compliance statements.
* Rhythm: pre-specified operating points (sensitivity and specificity targets 0.90 for AF versus sinus), exact
  binomial intervals, calibration, decision curves.
* Equity: one-sided non-inferiority of coverage (margin 10 points) and of SBP error SD (ratio margin 1.15) for
  MST 7-10 versus 4-6; regression of error on MST band with covariates; "predict MST band from pulse features"
  leakage probe.
* Multiplicity: fixed sequence SBP error-SD reduction, DBP error-SD reduction, AF-versus-sinus AUC, AF-versus-hard-
  non-AF AUC; every other test is labelled with the number of tests run.
* Tracks: `product_candidate` (phone, or Pi through the 8-bit sRGB compressed proxy; no ECG) is the only track that may
  be described as a product result. `science` (Pi raw, ECG-aligned, PAT) is reported separately.
* Synthetic augmentation study on the first 100 development clips only; synthetic tone shifts support no equity
  claim; GAN or diffusion augmentation never appears in a headline result.

## What will not be claimed

No within-person calibration, no continuous BP, no diabetes claim, no performance statement beyond the single site
and the one-visit design, and no claim beyond what the measured tables show.

## Run order

1. Synthetic data and positive control pass. 2. Bench sync acceptance (20 trials). 3. First 10 participants end to end
with manual review. 4. First 100: QC, sync grades, augmentation study, interim go/no-go dashboard (thresholds
untouched). 5. Pilot 500 with the frozen config.
