> Synthetic cohort: these pages measure the pipeline on generated data and are not study results.

# E0 baselines

## SBP

| track | camera | model | n attempted | n covered | coverage % | bias | error SD | MAE | LoA low | LoA high |
|---|---|---|---|---|---|---|---|---|---|---|
| product_candidate | phone | predict_mean | 30 | 30 | 100.0 | -0.00 | 16.37 | 12.87 | -32.08 | 32.08 |
| product_candidate | phone | demographics_only | 30 | 30 | 100.0 | -0.12 | 13.40 | 10.46 | -26.37 | 26.13 |
| product_candidate | pi_proxy | predict_mean | 30 | 30 | 100.0 | -0.00 | 16.37 | 12.87 | -32.08 | 32.08 |
| product_candidate | pi_proxy | demographics_only | 30 | 30 | 100.0 | -0.12 | 13.40 | 10.46 | -26.37 | 26.13 |
| science | pi | predict_mean | 30 | 30 | 100.0 | -0.00 | 16.37 | 12.87 | -32.08 | 32.08 |
| science | pi | demographics_only | 30 | 30 | 100.0 | -0.12 | 13.40 | 10.46 | -26.37 | 26.13 |

## DBP

| track | camera | model | n attempted | n covered | coverage % | bias | error SD | MAE | LoA low | LoA high |
|---|---|---|---|---|---|---|---|---|---|---|
| product_candidate | phone | predict_mean | 30 | 30 | 100.0 | -0.00 | 9.58 | 7.88 | -18.77 | 18.77 |
| product_candidate | phone | demographics_only | 30 | 30 | 100.0 | 0.43 | 7.71 | 5.84 | -14.68 | 15.54 |
| product_candidate | pi_proxy | predict_mean | 30 | 30 | 100.0 | -0.00 | 9.58 | 7.88 | -18.77 | 18.77 |
| product_candidate | pi_proxy | demographics_only | 30 | 30 | 100.0 | 0.43 | 7.71 | 5.84 | -14.68 | 15.54 |
| science | pi | predict_mean | 30 | 30 | 100.0 | -0.00 | 9.58 | 7.88 | -18.77 | 18.77 |
| science | pi | demographics_only | 30 | 30 | 100.0 | 0.43 | 7.71 | 5.84 | -14.68 | 15.54 |


---

# E1 pulse rate versus ECG HR

Tolerance 3.0 bpm (frozen). Pulse rate = 60 / median beat interval over the analysis window, against the ECG median-interval HR (D-024).

| camera | subset | n | MAE (bpm) | bias (bpm) | within tolerance % |
|---|---|---|---|---|---|
| pi | valid clips | 17 | 2.76 | 1.91 | 82.4 |
| pi | all attempted (failures count) | 17 | 2.76 | 1.91 | 46.7 |
| pi | all attempted, ignoring QC | 30 | 5.88 | 4.63 | 70.0 |
| phone | valid clips | 14 | 49.92 | -46.58 | 0.0 |
| phone | all attempted (failures count) | 14 | 49.92 | -46.58 | 0.0 |
| phone | all attempted, ignoring QC | 14 | 49.92 | -46.58 | 0.0 |
| pi_proxy | valid clips | 13 | 18.78 | -14.37 | 30.8 |
| pi_proxy | all attempted (failures count) | 13 | 18.78 | -14.37 | 13.3 |
| pi_proxy | all attempted, ignoring QC | 29 | 17.41 | -6.55 | 30.0 |

## By MST band (all attempted, failures count; every cell here is under 20 at pilot-test scale and is shown unpooled with its n)

| camera | MST band | n attempted | within tolerance % |
|---|---|---|---|
| pi | 2.0 | 1 | 0.0 |
| pi | 3.0 | 1 | 0.0 |
| pi | 4.0 | 1 | 100.0 |
| pi | 5.0 | 2 | 50.0 |
| pi | 6.0 | 6 | 50.0 |
| pi | 7.0 | 8 | 50.0 |
| pi | 8.0 | 5 | 40.0 |
| pi | 9.0 | 6 | 50.0 |
| phone | 2.0 | 1 | 0.0 |
| phone | 3.0 | 1 | 0.0 |
| phone | 4.0 | 1 | 0.0 |
| phone | 5.0 | 2 | 0.0 |
| phone | 6.0 | 6 | 0.0 |
| phone | 7.0 | 8 | 0.0 |
| phone | 8.0 | 5 | 0.0 |
| phone | 9.0 | 6 | 0.0 |
| pi_proxy | 2.0 | 1 | 0.0 |
| pi_proxy | 3.0 | 1 | 0.0 |
| pi_proxy | 4.0 | 1 | 0.0 |
| pi_proxy | 5.0 | 2 | 0.0 |
| pi_proxy | 6.0 | 6 | 33.3 |
| pi_proxy | 7.0 | 8 | 12.5 |
| pi_proxy | 8.0 | 5 | 0.0 |
| pi_proxy | 9.0 | 6 | 16.7 |


---

# E2 SQI and coverage

Failed and abstained clips count as failures (protocol 11.3).

| camera | attempted | valid | coverage % | median best SQI | failure reasons |
|---|---|---|---|---|---|
| pi | 30 | 17 | 56.7 | 0.66 | flicker_flag 10, sqi_flag 5 |
| phone | 30 | 29 | 96.7 | 0.43 | sqi_flag 1 |
| pi_proxy | 30 | 13 | 43.3 | 0.38 | sqi_flag 10, flicker_flag 9, saturation_flag 5 |

Logistic failure model coefficients (log-odds per SD; exploratory, n tests = number of coefficients):

- pi: mst_band -0.04, flag_hypertension -0.44, flag_diabetes +0.72, flag_chronic_kidney_disease -0.34, flag_arrhythmia -0.45, flag_anaemia_thalassaemia +0.28
- phone: mst_band -0.12, flag_hypertension +0.42, flag_diabetes +0.69, flag_chronic_kidney_disease -0.08, flag_arrhythmia +0.52, flag_anaemia_thalassaemia -0.07, qc__phone__landmark_jitter_px -0.03
- pi_proxy: mst_band +0.33, flag_hypertension -0.07, flag_diabetes -0.02, flag_chronic_kidney_disease -0.55, flag_arrhythmia -0.26, flag_anaemia_thalassaemia +0.01


---

# E3 BP from features

## bp_target_sbp

| track | camera | model | n attempted | n covered | coverage % | bias | error SD | MAE | LoA low | LoA high |
|---|---|---|---|---|---|---|---|---|---|---|
| product_candidate | phone | predict_mean | 30 | 30 | 100.0 | -0.00 | 16.37 | 12.87 | -32.08 | 32.08 |
| product_candidate | phone | demographics_only | 30 | 30 | 100.0 | -0.12 | 13.40 | 10.46 | -26.37 | 26.13 |
| product_candidate | phone | static_plus_temporal | 30 | 29 | 96.7 | -0.07 | 16.38 | 12.64 | -32.17 | 32.03 |
| product_candidate | phone | static_plus_temporal (lightgbm) | 30 | 29 | 96.7 | -1.29 | 14.38 | 10.77 | -29.46 | 26.89 |
| product_candidate | pi_proxy | predict_mean | 30 | 30 | 100.0 | -0.00 | 16.37 | 12.87 | -32.08 | 32.08 |
| product_candidate | pi_proxy | demographics_only | 30 | 30 | 100.0 | -0.12 | 13.40 | 10.46 | -26.37 | 26.13 |
| product_candidate | pi_proxy | static_plus_temporal | 30 | 13 | 43.3 | 0.00 | 18.77 | 15.14 | -36.79 | 36.80 |
| product_candidate | pi_proxy | static_plus_temporal (lightgbm) | 30 | 13 | 43.3 | 1.30 | 19.14 | 15.21 | -36.21 | 38.82 |
| science | pi | predict_mean | 30 | 30 | 100.0 | -0.00 | 16.37 | 12.87 | -32.08 | 32.08 |
| science | pi | demographics_only | 30 | 30 | 100.0 | -0.12 | 13.40 | 10.46 | -26.37 | 26.13 |
| science | pi | static_plus_temporal | 30 | 17 | 56.7 | -1.53 | 17.50 | 13.85 | -35.83 | 32.77 |
| science | pi | static_plus_temporal (lightgbm) | 30 | 17 | 56.7 | 0.25 | 19.09 | 14.33 | -37.16 | 37.66 |

## bp_target_dbp

| track | camera | model | n attempted | n covered | coverage % | bias | error SD | MAE | LoA low | LoA high |
|---|---|---|---|---|---|---|---|---|---|---|
| product_candidate | phone | predict_mean | 30 | 30 | 100.0 | -0.00 | 9.58 | 7.88 | -18.77 | 18.77 |
| product_candidate | phone | demographics_only | 30 | 30 | 100.0 | 0.43 | 7.71 | 5.84 | -14.68 | 15.54 |
| product_candidate | phone | static_plus_temporal | 30 | 29 | 96.7 | 0.08 | 9.33 | 7.57 | -18.20 | 18.37 |
| product_candidate | phone | static_plus_temporal (lightgbm) | 30 | 29 | 96.7 | 1.13 | 10.65 | 8.70 | -19.73 | 22.00 |
| product_candidate | pi_proxy | predict_mean | 30 | 30 | 100.0 | -0.00 | 9.58 | 7.88 | -18.77 | 18.77 |
| product_candidate | pi_proxy | demographics_only | 30 | 30 | 100.0 | 0.43 | 7.71 | 5.84 | -14.68 | 15.54 |
| product_candidate | pi_proxy | static_plus_temporal | 30 | 13 | 43.3 | -0.07 | 10.92 | 8.72 | -21.48 | 21.33 |
| product_candidate | pi_proxy | static_plus_temporal (lightgbm) | 30 | 13 | 43.3 | -0.15 | 14.27 | 10.56 | -28.12 | 27.81 |
| science | pi | predict_mean | 30 | 30 | 100.0 | -0.00 | 9.58 | 7.88 | -18.77 | 18.77 |
| science | pi | demographics_only | 30 | 30 | 100.0 | 0.43 | 7.71 | 5.84 | -14.68 | 15.54 |
| science | pi | static_plus_temporal | 30 | 17 | 56.7 | -0.91 | 10.20 | 8.21 | -20.90 | 19.08 |
| science | pi | static_plus_temporal (lightgbm) | 30 | 17 | 56.7 | 2.03 | 10.06 | 8.91 | -17.69 | 21.75 |

## bp_target_23_sbp

| track | camera | model | n attempted | n covered | coverage % | bias | error SD | MAE | LoA low | LoA high |
|---|---|---|---|---|---|---|---|---|---|---|
| product_candidate | phone | predict_mean | 30 | 30 | 100.0 | -0.00 | 16.96 | 13.46 | -33.24 | 33.24 |
| product_candidate | phone | demographics_only | 30 | 30 | 100.0 | -0.10 | 14.74 | 11.47 | -29.00 | 28.80 |
| product_candidate | phone | static_plus_temporal | 30 | 29 | 96.7 | -0.06 | 16.77 | 13.04 | -32.93 | 32.80 |
| product_candidate | pi_proxy | predict_mean | 30 | 30 | 100.0 | -0.00 | 16.96 | 13.46 | -33.24 | 33.24 |
| product_candidate | pi_proxy | demographics_only | 30 | 30 | 100.0 | -0.10 | 14.74 | 11.47 | -29.00 | 28.80 |
| product_candidate | pi_proxy | static_plus_temporal | 30 | 13 | 43.3 | 0.16 | 18.95 | 15.39 | -36.98 | 37.30 |
| science | pi | predict_mean | 30 | 30 | 100.0 | -0.00 | 16.96 | 13.46 | -33.24 | 33.24 |
| science | pi | demographics_only | 30 | 30 | 100.0 | -0.10 | 14.74 | 11.47 | -29.00 | 28.80 |
| science | pi | static_plus_temporal | 30 | 17 | 56.7 | -1.53 | 18.37 | 14.86 | -37.54 | 34.48 |


---

# E4 BP deep (1D CNN on beat sequences)

## SBP

| track | camera | model | n attempted | n covered | coverage % | bias | error SD | MAE | LoA low | LoA high |
|---|---|---|---|---|---|---|---|---|---|---|
| product_candidate | phone | predict_mean | 30 | 30 | 100.0 | -0.00 | 16.37 | 12.87 | -32.08 | 32.08 |
| product_candidate | phone | demographics_only | 30 | 30 | 100.0 | -0.12 | 13.40 | 10.46 | -26.37 | 26.13 |
| product_candidate | phone | conv1d_beats | 30 | 0 | 0.0 | NA | NA | NA | NA | NA |
| product_candidate | pi_proxy | predict_mean | 30 | 30 | 100.0 | -0.00 | 16.37 | 12.87 | -32.08 | 32.08 |
| product_candidate | pi_proxy | demographics_only | 30 | 30 | 100.0 | -0.12 | 13.40 | 10.46 | -26.37 | 26.13 |
| product_candidate | pi_proxy | conv1d_beats | 30 | 12 | 40.0 | 2.40 | 20.24 | 15.36 | -37.27 | 42.07 |
| science | pi | predict_mean | 30 | 30 | 100.0 | -0.00 | 16.37 | 12.87 | -32.08 | 32.08 |
| science | pi | demographics_only | 30 | 30 | 100.0 | -0.12 | 13.40 | 10.46 | -26.37 | 26.13 |
| science | pi | conv1d_beats | 30 | 17 | 56.7 | 5.19 | 20.65 | 15.24 | -35.28 | 45.67 |


---

# E5 static versus temporal

Pilot margin: temporal features reduce SBP error SD by at least 2.0 mmHg over demographics only (frozen).

| track | camera | SBP SD demographics | SBP SD temporal | reduction | meets margin | SBP SD pulse-shuffled |
|---|---|---|---|---|---|---|
| product_candidate | phone | 13.40 | 16.17 | -2.77 | False | 14.66 |
| product_candidate | pi_proxy | 13.40 | 19.03 | -5.64 | False | 19.38 |
| science | pi | 13.40 | 17.52 | -4.12 | False | 17.61 |

## SBP, all arms

| track | camera | model | n attempted | n covered | coverage % | bias | error SD | MAE | LoA low | LoA high |
|---|---|---|---|---|---|---|---|---|---|---|
| product_candidate | phone | predict_mean | 30 | 30 | 100.0 | -0.00 | 16.37 | 12.87 | -32.08 | 32.08 |
| product_candidate | phone | demographics_only | 30 | 30 | 100.0 | -0.12 | 13.40 | 10.46 | -26.37 | 26.13 |
| product_candidate | phone | static_only | 30 | 29 | 96.7 | -2.32 | 15.27 | 11.99 | -32.25 | 27.62 |
| product_candidate | phone | temporal_only | 30 | 29 | 96.7 | -0.07 | 16.17 | 12.43 | -31.76 | 31.62 |
| product_candidate | phone | static_plus_temporal | 30 | 29 | 96.7 | -0.07 | 16.38 | 12.64 | -32.17 | 32.03 |
| product_candidate | phone | pulse_shuffled_control | 30 | 29 | 96.7 | -0.93 | 14.66 | 10.89 | -29.67 | 27.80 |
| product_candidate | pi_proxy | predict_mean | 30 | 30 | 100.0 | -0.00 | 16.37 | 12.87 | -32.08 | 32.08 |
| product_candidate | pi_proxy | demographics_only | 30 | 30 | 100.0 | -0.12 | 13.40 | 10.46 | -26.37 | 26.13 |
| product_candidate | pi_proxy | static_only | 30 | 13 | 43.3 | 3.46 | 22.71 | 19.51 | -41.05 | 47.98 |
| product_candidate | pi_proxy | temporal_only | 30 | 13 | 43.3 | 1.11 | 19.03 | 14.56 | -36.20 | 38.41 |
| product_candidate | pi_proxy | static_plus_temporal | 30 | 13 | 43.3 | 0.00 | 18.77 | 15.14 | -36.79 | 36.80 |
| product_candidate | pi_proxy | pulse_shuffled_control | 30 | 13 | 43.3 | 0.16 | 19.38 | 15.99 | -37.83 | 38.14 |
| science | pi | predict_mean | 30 | 30 | 100.0 | -0.00 | 16.37 | 12.87 | -32.08 | 32.08 |
| science | pi | demographics_only | 30 | 30 | 100.0 | -0.12 | 13.40 | 10.46 | -26.37 | 26.13 |
| science | pi | static_only | 30 | 17 | 56.7 | 3.97 | 19.68 | 15.96 | -34.61 | 42.55 |
| science | pi | temporal_only | 30 | 17 | 56.7 | -1.58 | 17.52 | 13.86 | -35.92 | 32.75 |
| science | pi | static_plus_temporal | 30 | 17 | 56.7 | -1.53 | 17.50 | 13.85 | -35.83 | 32.77 |
| science | pi | pulse_shuffled_control | 30 | 17 | 56.7 | 0.08 | 17.61 | 13.83 | -34.44 | 34.59 |

## DBP, all arms

| track | camera | model | n attempted | n covered | coverage % | bias | error SD | MAE | LoA low | LoA high |
|---|---|---|---|---|---|---|---|---|---|---|
| product_candidate | phone | predict_mean | 30 | 30 | 100.0 | -0.00 | 9.58 | 7.88 | -18.77 | 18.77 |
| product_candidate | phone | demographics_only | 30 | 30 | 100.0 | 0.43 | 7.71 | 5.84 | -14.68 | 15.54 |
| product_candidate | phone | static_only | 30 | 29 | 96.7 | 0.02 | 9.77 | 8.07 | -19.13 | 19.18 |
| product_candidate | phone | temporal_only | 30 | 29 | 96.7 | 0.07 | 9.38 | 7.62 | -18.32 | 18.47 |
| product_candidate | phone | static_plus_temporal | 30 | 29 | 96.7 | 0.08 | 9.33 | 7.57 | -18.20 | 18.37 |
| product_candidate | phone | pulse_shuffled_control | 30 | 29 | 96.7 | 0.47 | 9.36 | 7.70 | -17.88 | 18.82 |
| product_candidate | pi_proxy | predict_mean | 30 | 30 | 100.0 | -0.00 | 9.58 | 7.88 | -18.77 | 18.77 |
| product_candidate | pi_proxy | demographics_only | 30 | 30 | 100.0 | 0.43 | 7.71 | 5.84 | -14.68 | 15.54 |
| product_candidate | pi_proxy | static_only | 30 | 13 | 43.3 | -0.48 | 12.51 | 10.37 | -25.00 | 24.04 |
| product_candidate | pi_proxy | temporal_only | 30 | 13 | 43.3 | 0.49 | 11.37 | 9.15 | -21.80 | 22.78 |
| product_candidate | pi_proxy | static_plus_temporal | 30 | 13 | 43.3 | -0.07 | 10.92 | 8.72 | -21.48 | 21.33 |
| product_candidate | pi_proxy | pulse_shuffled_control | 30 | 13 | 43.3 | -0.13 | 10.83 | 8.25 | -21.36 | 21.11 |
| science | pi | predict_mean | 30 | 30 | 100.0 | -0.00 | 9.58 | 7.88 | -18.77 | 18.77 |
| science | pi | demographics_only | 30 | 30 | 100.0 | 0.43 | 7.71 | 5.84 | -14.68 | 15.54 |
| science | pi | static_only | 30 | 17 | 56.7 | 1.77 | 9.18 | 7.71 | -16.22 | 19.77 |
| science | pi | temporal_only | 30 | 17 | 56.7 | -12.43 | 43.82 | 19.18 | -98.31 | 73.46 |
| science | pi | static_plus_temporal | 30 | 17 | 56.7 | -0.91 | 10.20 | 8.21 | -20.90 | 19.08 |
| science | pi | pulse_shuffled_control | 30 | 17 | 56.7 | 0.41 | 11.39 | 9.38 | -21.91 | 22.73 |


---

# E6 equity

## product_candidate / phone

## Equity audit (E6): MST 7-10 versus 4-6, one-sided alpha 0.05

| arm | role | n attempted | n covered | coverage % | error SD | n participants |
|---|---|---|---|---|---|---|
| 4-6 | reference | 9 | 8 | 88.9 | 14.07 | 8 |
| 7-10 | comparison | 19 | 19 | 100.0 | 17.80 | 19 |

| test | estimate | one-sided bound | margin | non-inferior | p |
|---|---|---|---|---|---|
| coverage difference, points (Farrington-Manning) | 11.111 | -2.301 | 10 | yes | 0.0157 |
| coverage difference, points (Wald, continuity corrected) | 11.111 | -14.307 | 10 | no | 0.1087 |
| error SD ratio (F-test) | 1.266 | 2.032 | 1.15 | no | 0.5792 |
| error SD ratio (participant bootstrap) | 1.266 | 2.125 | 1.15 | no | 0.6940 |

Regression `error ~ mst_band + age + sex_f + bmi + bp_target` (cluster-robust by participant, n=29, clusters=29)

| term | coef | se | 95% CI | p |
|---|---|---|---|---|
| Intercept | 111.058 | 2.299 | 106.552 .. 115.564 | 0.0000 |
| mst_band | 0.055 | 0.238 | -0.412 .. 0.521 | 0.8180 |
| age | -0.006 | 0.042 | -0.089 .. 0.076 | 0.8795 |
| sex_f | 0.610 | 0.884 | -1.122 .. 2.342 | 0.4902 |
| bmi | -0.122 | 0.113 | -0.343 .. 0.100 | 0.2813 |
| bp_target | -1.061 | 0.025 | -1.110 .. -1.012 | 0.0000 |


MST leakage probe (product_candidate/phone): {}

## product_candidate / pi_proxy

## Equity audit (E6): MST 7-10 versus 4-6, one-sided alpha 0.05

| arm | role | n attempted | n covered | coverage % | error SD | n participants |
|---|---|---|---|---|---|---|
| 4-6 | reference | 9 | 5 | 55.6 | 16.99 | 5 |
| 7-10 | comparison | 19 | 7 | 36.8 | 20.43 | 7 |

| test | estimate | one-sided bound | margin | non-inferior | p |
|---|---|---|---|---|---|
| coverage difference, points (Farrington-Manning) | -18.713 | -47.799 | 10 | no | 0.6678 |
| coverage difference, points (Wald, continuity corrected) | -18.713 | -59.666 | 10 | no | 0.8019 |
| error SD ratio (F-test) | 1.203 | 2.560 | 1.15 | no | 0.5122 |
| error SD ratio (participant bootstrap) | 1.203 | 2.593 | 1.15 | no | 0.6016 |

Regression `error ~ mst_band + age + sex_f + bmi + bp_target` (cluster-robust by participant, n=13, clusters=13)

| term | coef | se | 95% CI | p |
|---|---|---|---|---|
| Intercept | 106.847 | 4.259 | 98.499 .. 115.195 | 0.0000 |
| mst_band | 1.663 | 0.410 | 0.859 .. 2.467 | 0.0001 |
| age | -0.047 | 0.098 | -0.239 .. 0.145 | 0.6329 |
| sex_f | 0.445 | 1.514 | -2.522 .. 3.413 | 0.7686 |
| bmi | 0.287 | 0.405 | -0.506 .. 1.080 | 0.4786 |
| bp_target | -1.141 | 0.130 | -1.396 .. -0.886 | 0.0000 |


MST leakage probe (product_candidate/pi_proxy): {}

## science / pi

## Equity audit (E6): MST 7-10 versus 4-6, one-sided alpha 0.05

| arm | role | n attempted | n covered | coverage % | error SD | n participants |
|---|---|---|---|---|---|---|
| 4-6 | reference | 9 | 7 | 77.8 | 17.26 | 7 |
| 7-10 | comparison | 19 | 10 | 52.6 | 18.36 | 10 |

| test | estimate | one-sided bound | margin | non-inferior | p |
|---|---|---|---|---|---|
| coverage difference, points (Farrington-Manning) | -25.146 | -50.184 | 10 | no | 0.7843 |
| coverage difference, points (Wald, continuity corrected) | -25.146 | -62.907 | 10 | no | 0.9028 |
| error SD ratio (F-test) | 1.064 | 1.954 | 1.15 | no | 0.3999 |
| error SD ratio (participant bootstrap) | 1.064 | 1.971 | 1.15 | no | 0.4315 |

Regression `error ~ mst_band + age + sex_f + bmi + bp_target` (cluster-robust by participant, n=17, clusters=17)

| term | coef | se | 95% CI | p |
|---|---|---|---|---|
| Intercept | 88.218 | 17.846 | 53.242 .. 123.195 | 0.0000 |
| mst_band | 1.037 | 1.013 | -0.947 .. 3.022 | 0.3057 |
| age | -0.182 | 0.132 | -0.441 .. 0.077 | 0.1680 |
| sex_f | -6.037 | 6.023 | -17.842 .. 5.768 | 0.3162 |
| bmi | 0.802 | 0.669 | -0.510 .. 2.114 | 0.2308 |
| bp_target | -0.998 | 0.103 | -1.200 .. -0.797 | 0.0000 |


MST leakage probe (science/pi): {}

Synthetic tone shifts in generated data support no equity claim.


---

# E7 rhythm: AF versus sinus

Operating point 0.5 (pre-specified). Exact binomial intervals. Failed clips count as negative predictions.

| track | camera | model | n | positives | AUROC | sensitivity | specificity |
|---|---|---|---|---|---|---|---|
| product_candidate | phone | predict_prevalence | 28 | 3 | 0.50 | 0.00 | 1.00 | 
| product_candidate | phone | demographics_only | 28 | 3 | 0.47 | 0.33 | 0.80 | 
| product_candidate | phone | irregularity_only | 28 | 3 | 0.33 | 0.00 | 0.76 | 
| product_candidate | phone | morphology | 28 | 3 | 0.32 | 0.00 | 0.84 | 
| product_candidate | pi_proxy | predict_prevalence | 28 | 3 | 0.50 | 0.00 | 1.00 | 
| product_candidate | pi_proxy | demographics_only | 28 | 3 | 0.47 | 0.33 | 0.80 | 
| product_candidate | pi_proxy | irregularity_only | 28 | 3 | NA | 0.00 | 1.00 | 
| product_candidate | pi_proxy | morphology | 28 | 3 | NA | 0.00 | 0.96 | 
| science | pi | predict_prevalence | 28 | 3 | 0.50 | 0.00 | 1.00 | 
| science | pi | demographics_only | 28 | 3 | 0.47 | 0.33 | 0.80 | 
| science | pi | irregularity_only | 28 | 3 | NA | 0.00 | 1.00 | 
| science | pi | morphology | 28 | 3 | NA | 0.00 | 1.00 | 

# E7 rhythm: AF versus hard non-AF

Operating point 0.5 (pre-specified). Exact binomial intervals. Failed clips count as negative predictions.

| track | camera | model | n | positives | AUROC | sensitivity | specificity |
|---|---|---|---|---|---|---|---|
| product_candidate | phone | all |  |  | NA | NA | NA | not estimable: 4 labelled, 3 positive
| product_candidate | pi_proxy | all |  |  | NA | NA | NA | not estimable: 4 labelled, 3 positive
| science | pi | all |  |  | NA | NA | NA | not estimable: 4 labelled, 3 positive


---

# E8 haemoglobin (where Hb exists)

## hb_gdl

| track | camera | model | n attempted | n covered | coverage % | bias | error SD | MAE | LoA low | LoA high |
|---|---|---|---|---|---|---|---|---|---|---|
| product_candidate | phone | predict_mean | 30 | 14 | 46.7 | 0.03 | 1.62 | 1.20 | -3.15 | 3.21 |
| product_candidate | phone | demographics_only | 30 | 14 | 46.7 | 0.19 | 1.77 | 1.38 | -3.27 | 3.65 |
| product_candidate | phone | features | 30 | 14 | 46.7 | -0.01 | 1.98 | 1.65 | -3.89 | 3.86 |
| product_candidate | pi_proxy | predict_mean | 30 | 14 | 46.7 | 0.03 | 1.62 | 1.20 | -3.15 | 3.21 |
| product_candidate | pi_proxy | demographics_only | 30 | 14 | 46.7 | 0.19 | 1.77 | 1.38 | -3.27 | 3.65 |
| product_candidate | pi_proxy | features | 30 | 2 | 6.7 | -0.54 | 0.24 | 0.54 | -1.01 | -0.06 |
| science | pi | predict_mean | 30 | 14 | 46.7 | 0.03 | 1.62 | 1.20 | -3.15 | 3.21 |
| science | pi | demographics_only | 30 | 14 | 46.7 | 0.19 | 1.77 | 1.38 | -3.27 | 3.65 |
| science | pi | features | 30 | 7 | 23.3 | -0.10 | 0.70 | 0.57 | -1.47 | 1.28 |


---

# E9 vascular age (age from morphology and APG)

## age

| track | camera | model | n attempted | n covered | coverage % | bias | error SD | MAE | LoA low | LoA high |
|---|---|---|---|---|---|---|---|---|---|---|
| product_candidate | phone | predict_mean | 30 | 30 | 100.0 | 0.00 | 15.64 | 12.16 | -30.64 | 30.64 |
| product_candidate | phone | demographics_only | 30 | 30 | 100.0 | -0.01 | 15.64 | 12.16 | -30.66 | 30.65 |
| product_candidate | phone | features | 30 | 29 | 96.7 | 0.83 | 19.14 | 13.79 | -36.68 | 38.33 |
| product_candidate | pi_proxy | predict_mean | 30 | 30 | 100.0 | 0.00 | 15.64 | 12.16 | -30.64 | 30.64 |
| product_candidate | pi_proxy | demographics_only | 30 | 30 | 100.0 | -0.01 | 15.64 | 12.16 | -30.66 | 30.65 |
| product_candidate | pi_proxy | features | 30 | 13 | 43.3 | -4.04 | 27.67 | 18.46 | -58.27 | 50.19 |
| science | pi | predict_mean | 30 | 30 | 100.0 | 0.00 | 15.64 | 12.16 | -30.64 | 30.64 |
| science | pi | demographics_only | 30 | 30 | 100.0 | -0.01 | 15.64 | 12.16 | -30.66 | 30.65 |
| science | pi | features | 30 | 17 | 56.7 | -313.81 | 1298.18 | 326.62 | -2858.20 | 2230.58 |


---

# E10 foundation-model transfer

Not run: PaPaGei and SiamQuality weights are not in this environment. No random-init stand-in is reported as a result.


---

# E11 shortcut audit

## product_candidate / phone

## Shortcut audit (E11): nuisance predictability from features, participant-grouped CV

| nuisance | n | n_levels | balanced_accuracy | chance | excess | macro_f1 | chance_macro_f1 | residual_anova_p | residual_kruskal_p | residual_eta_sq | note |
|---|---|---|---|---|---|---|---|---|---|---|---|
| operator | 30 | 3 | 0.300 | 0.333 | -0.033 | 0.284 | 0.333 | 0.748 | 0.684 | 0.022 |  |
| dept | 23 | 4 | 0.263 | 0.250 | 0.013 | 0.219 | 0.242 | 0.957 | 0.950 | 0.065 | levels left out (n<3): Endo OPD (n=2), ANC (OBG) (n=2), Other (n=2), Thal Day Care (n=1) |
| time_of_day | 30 | 2 | 0.500 | 0.500 | 0.000 | 0.400 | 0.486 | 0.772 | 0.370 | 0.003 |  |
| antihtn_today | 28 | 2 | 0.474 | 0.500 | -0.026 | 0.391 | 0.484 | 0.214 | 0.107 | 0.112 | levels left out (n<3): yes <=2 h (n=2) |

`chance` is 1/k for balanced accuracy; `excess` = balanced accuracy - chance (measured, no threshold applied).
Residual columns: one-way ANOVA and Kruskal-Wallis of model residuals across nuisance levels.


## product_candidate / pi_proxy

## Shortcut audit (E11): nuisance predictability from features, participant-grouped CV

| nuisance | n | n_levels | balanced_accuracy | chance | excess | macro_f1 | chance_macro_f1 | residual_anova_p | residual_kruskal_p | residual_eta_sq | note |
|---|---|---|---|---|---|---|---|---|---|---|---|
| operator | 30 | 3 | 0.267 | 0.333 | -0.067 | 0.267 | 0.333 | 0.201 | 0.286 | 0.275 |  |
| dept | 23 | 4 | 0.205 | 0.250 | -0.045 | 0.170 | 0.242 | 0.558 | 0.405 | 0.242 | levels left out (n<3): Endo OPD (n=2), ANC (OBG) (n=2), Other (n=2), Thal Day Care (n=1) |
| time_of_day | 30 | 2 | 0.500 | 0.500 | 0.000 | 0.489 | 0.486 | 0.422 | 0.324 | 0.059 |  |
| antihtn_today | 28 | 2 | 0.500 | 0.500 | 0.000 | 0.404 | 0.484 | 0.036 | 0.042 | 0.371 | levels left out (n<3): yes <=2 h (n=2) |

`chance` is 1/k for balanced accuracy; `excess` = balanced accuracy - chance (measured, no threshold applied).
Residual columns: one-way ANOVA and Kruskal-Wallis of model residuals across nuisance levels.


## science / pi

## Shortcut audit (E11): nuisance predictability from features, participant-grouped CV

| nuisance | n | n_levels | balanced_accuracy | chance | excess | macro_f1 | chance_macro_f1 | residual_anova_p | residual_kruskal_p | residual_eta_sq | note |
|---|---|---|---|---|---|---|---|---|---|---|---|
| operator | 30 | 3 | 0.300 | 0.333 | -0.033 | 0.299 | 0.333 | 0.583 | 0.677 | 0.074 |  |
| dept | 23 | 4 | 0.263 | 0.250 | 0.013 | 0.232 | 0.242 | 0.721 | 0.826 | 0.110 | levels left out (n<3): Endo OPD (n=2), ANC (OBG) (n=2), Other (n=2), Thal Day Care (n=1) |
| time_of_day | 30 | 2 | 0.525 | 0.500 | 0.025 | 0.511 | 0.486 | 0.670 | 0.598 | 0.012 |  |
| antihtn_today | 28 | 2 | 0.500 | 0.500 | 0.000 | 0.404 | 0.484 | 0.632 | 0.732 | 0.063 | levels left out (n<3): yes <=2 h (n=2) |

`chance` is 1/k for balanced accuracy; `excess` = balanced accuracy - chance (measured, no threshold applied).
Residual columns: one-way ANOVA and Kruskal-Wallis of model residuals across nuisance levels.


Nuisance variables with a single level in this data (not auditable): unit_id, stream, camera.


---

# E12 current elevated BP (stage 1 or above on the cuff mean)

Operating point 0.5 (pre-specified). Exact binomial intervals. Failed clips count as negative predictions.

| track | camera | model | n | positives | AUROC | sensitivity | specificity |
|---|---|---|---|---|---|---|---|
| product_candidate | phone | predict_prevalence | 30 | 5 | 0.50 | 0.00 | 1.00 | 
| product_candidate | phone | demographics_only | 30 | 5 | 0.53 | 0.40 | 0.60 | 
| product_candidate | phone | static_plus_temporal | 30 | 5 | 0.79 | 0.00 | 0.92 | 
| product_candidate | pi_proxy | predict_prevalence | 30 | 5 | 0.50 | 0.00 | 1.00 | 
| product_candidate | pi_proxy | demographics_only | 30 | 5 | 0.53 | 0.40 | 0.60 | 
| product_candidate | pi_proxy | static_plus_temporal | 30 | 5 | NA | 0.00 | 1.00 | 
| science | pi | predict_prevalence | 30 | 5 | 0.50 | 0.00 | 1.00 | 
| science | pi | demographics_only | 30 | 5 | 0.53 | 0.40 | 0.60 | 
| science | pi | static_plus_temporal | 30 | 5 | 0.76 | 0.00 | 1.00 | 


---

# E13 glucose boundary: capillary glucose

## glucose_mgdl

| track | camera | model | n attempted | n covered | coverage % | bias | error SD | MAE | LoA low | LoA high |
|---|---|---|---|---|---|---|---|---|---|---|
| product_candidate | phone | predict_mean | 30 | 9 | 30.0 | 2.04 | 72.74 | 59.37 | -140.53 | 144.61 |
| product_candidate | phone | demographics_only | 30 | 9 | 30.0 | -11.34 | 94.37 | 74.09 | -196.30 | 173.63 |
| product_candidate | phone | features | 30 | 9 | 30.0 | 5.08 | 75.52 | 63.23 | -142.93 | 153.09 |
| product_candidate | pi_proxy | predict_mean | 30 | 9 | 30.0 | 2.04 | 72.74 | 59.37 | -140.53 | 144.61 |
| product_candidate | pi_proxy | demographics_only | 30 | 9 | 30.0 | -11.34 | 94.37 | 74.09 | -196.30 | 173.63 |
| product_candidate | pi_proxy | features | 30 | 0 | 0.0 | NA | NA | NA | NA | NA |
| science | pi | predict_mean | 30 | 9 | 30.0 | 2.04 | 72.74 | 59.37 | -140.53 | 144.61 |
| science | pi | demographics_only | 30 | 9 | 30.0 | -11.34 | 94.37 | 74.09 | -196.30 | 173.63 |
| science | pi | features | 30 | 0 | 0.0 | NA | NA | NA | NA | NA |

# E13 glucose boundary: HbA1c

## hba1c

| track | camera | model | n attempted | n covered | coverage % | bias | error SD | MAE | LoA low | LoA high |
|---|---|---|---|---|---|---|---|---|---|---|
| product_candidate | phone | predict_mean | 30 | 16 | 53.3 | 0.06 | 1.76 | 1.42 | -3.39 | 3.51 |
| product_candidate | phone | demographics_only | 30 | 16 | 53.3 | 0.34 | 2.32 | 1.80 | -4.21 | 4.89 |
| product_candidate | phone | features | 30 | 16 | 53.3 | 0.00 | 1.87 | 1.51 | -3.66 | 3.67 |
| product_candidate | pi_proxy | predict_mean | 30 | 16 | 53.3 | 0.06 | 1.76 | 1.42 | -3.39 | 3.51 |
| product_candidate | pi_proxy | demographics_only | 30 | 16 | 53.3 | 0.34 | 2.32 | 1.80 | -4.21 | 4.89 |
| product_candidate | pi_proxy | features | 30 | 4 | 13.3 | -1.45 | 1.60 | 1.45 | -4.58 | 1.68 |
| science | pi | predict_mean | 30 | 16 | 53.3 | 0.06 | 1.76 | 1.42 | -3.39 | 3.51 |
| science | pi | demographics_only | 30 | 16 | 53.3 | 0.34 | 2.32 | 1.80 | -4.21 | 4.89 |
| science | pi | features | 30 | 3 | 10.0 | -0.78 | 0.60 | 0.78 | -1.96 | 0.40 |

Reported in full whatever the direction; no diabetes claim is made from any number here.


---

# E14 repeatability

No re-shot clips in this data; nothing to report.


---

# E15 extras (descriptive only; no reference exists for these)

| feature | n | median |
|---|---|---|
| resp__pi__resp_rate_bpm | 0 | NA |


---

# E16 Pi-versus-phone transfer (product_candidate)

930 camera-neutral features; 30 participants with both cameras.

| arm | n covered | coverage % | bias | error SD | MAE |
|---|---|---|---|---|---|
| pi_proxy_to_phone | 29 | 96.7 | 4.89 | 15.26 | 13.19 |
| phone_to_phone | 29 | 96.7 | -0.08 | 16.37 | 12.62 |
| pi_proxy_to_pi_proxy | 13 | 43.3 | 0.01 | 18.77 | 15.15 |
| pi_proxy_aug_to_phone |  | NA | NA | NA | NA |


---

# E17 beat-level ECG-to-pulse (science track, sync grade fine only, requires_ecg)

Clips graded fine: 14; with PAT: 14; median pairing rate 0.94; median ectopic capture fraction 0.00.

PAT versus SBP across participants: r = 0.02 (p = 0.959, n = 14); exploratory.
Nothing in this experiment may enter a product_candidate model.
