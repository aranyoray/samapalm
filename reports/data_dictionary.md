# Data dictionary

Column naming follows `group__camera__roi__method__name` (CONTRACTS section 5). Columns with `requires_ecg` or `requires_raw` are science-track only and never enter a product_candidate model (protocol sections 6.6, 9, 11.5).

3775 columns in 15 groups: apg (30), beats (113), clinician (4), covariate (51), ecg (46), hrv (45), id (5), morphology (90), pat (45), perfusion (140), pulse (2814), qc (87), resp (12), static_colour (267), sync (26).
107 require ECG; 1223 require raw Bayer.

| name | group | camera | requires_ecg | requires_raw | units | description |
|---|---|---|---|---|---|---|
| apg__phone__a | apg | phone | no | no |  | acceleration plethysmogram wave feature (protocol 6.5) [a] |
| apg__phone__ageing_index | apg | phone | no | no | ratio | acceleration plethysmogram wave feature (protocol 6.5) [ageing_index]: dimensionless ratio or index |
| apg__phone__b | apg | phone | no | no |  | acceleration plethysmogram wave feature (protocol 6.5) [b] |
| apg__phone__b_a | apg | phone | no | no |  | acceleration plethysmogram wave feature (protocol 6.5) [b_a] |
| apg__phone__c | apg | phone | no | no |  | acceleration plethysmogram wave feature (protocol 6.5) [c] |
| apg__phone__c_a | apg | phone | no | no |  | acceleration plethysmogram wave feature (protocol 6.5) [c_a] |
| apg__phone__d | apg | phone | no | no |  | acceleration plethysmogram wave feature (protocol 6.5) [d] |
| apg__phone__d_a | apg | phone | no | no |  | acceleration plethysmogram wave feature (protocol 6.5) [d_a] |
| apg__phone__e | apg | phone | no | no |  | acceleration plethysmogram wave feature (protocol 6.5) [e] |
| apg__phone__e_a | apg | phone | no | no |  | acceleration plethysmogram wave feature (protocol 6.5) [e_a] |
| apg__pi__a | apg | pi | no | yes |  | acceleration plethysmogram wave feature (protocol 6.5) [a] |
| apg__pi__ageing_index | apg | pi | no | yes | ratio | acceleration plethysmogram wave feature (protocol 6.5) [ageing_index]: dimensionless ratio or index |
| apg__pi__b | apg | pi | no | yes |  | acceleration plethysmogram wave feature (protocol 6.5) [b] |
| apg__pi__b_a | apg | pi | no | yes |  | acceleration plethysmogram wave feature (protocol 6.5) [b_a] |
| apg__pi__c | apg | pi | no | yes |  | acceleration plethysmogram wave feature (protocol 6.5) [c] |
| apg__pi__c_a | apg | pi | no | yes |  | acceleration plethysmogram wave feature (protocol 6.5) [c_a] |
| apg__pi__d | apg | pi | no | yes |  | acceleration plethysmogram wave feature (protocol 6.5) [d] |
| apg__pi__d_a | apg | pi | no | yes |  | acceleration plethysmogram wave feature (protocol 6.5) [d_a] |
| apg__pi__e | apg | pi | no | yes |  | acceleration plethysmogram wave feature (protocol 6.5) [e] |
| apg__pi__e_a | apg | pi | no | yes |  | acceleration plethysmogram wave feature (protocol 6.5) [e_a] |
| apg__pi_proxy__a | apg | pi_proxy | no | no |  | acceleration plethysmogram wave feature (protocol 6.5) [a] |
| apg__pi_proxy__ageing_index | apg | pi_proxy | no | no | ratio | acceleration plethysmogram wave feature (protocol 6.5) [ageing_index]: dimensionless ratio or index |
| apg__pi_proxy__b | apg | pi_proxy | no | no |  | acceleration plethysmogram wave feature (protocol 6.5) [b] |
| apg__pi_proxy__b_a | apg | pi_proxy | no | no |  | acceleration plethysmogram wave feature (protocol 6.5) [b_a] |
| apg__pi_proxy__c | apg | pi_proxy | no | no |  | acceleration plethysmogram wave feature (protocol 6.5) [c] |
| apg__pi_proxy__c_a | apg | pi_proxy | no | no |  | acceleration plethysmogram wave feature (protocol 6.5) [c_a] |
| apg__pi_proxy__d | apg | pi_proxy | no | no |  | acceleration plethysmogram wave feature (protocol 6.5) [d] |
| apg__pi_proxy__d_a | apg | pi_proxy | no | no |  | acceleration plethysmogram wave feature (protocol 6.5) [d_a] |
| apg__pi_proxy__e | apg | pi_proxy | no | no |  | acceleration plethysmogram wave feature (protocol 6.5) [e] |
| apg__pi_proxy__e_a | apg | pi_proxy | no | no |  | acceleration plethysmogram wave feature (protocol 6.5) [e_a] |
| beats__phone__apg_detail__n_beats | beats | phone | no | no | count | beat-level clip aggregate (protocol 6.5) [apg_detail__n_beats]: count |
| beats__phone__apg_detail__n_waves | beats | phone | no | no | count | beat-level clip aggregate (protocol 6.5) [apg_detail__n_waves]: count |
| beats__phone__apg_detail__t_a_s | beats | phone | no | no | s | beat-level clip aggregate (protocol 6.5) [apg_detail__t_a_s]: duration in seconds |
| beats__phone__apg_detail__t_b_s | beats | phone | no | no | s | beat-level clip aggregate (protocol 6.5) [apg_detail__t_b_s]: duration in seconds |
| beats__phone__apg_detail__t_c_s | beats | phone | no | no | s | beat-level clip aggregate (protocol 6.5) [apg_detail__t_c_s]: duration in seconds |
| beats__phone__apg_detail__t_d_s | beats | phone | no | no | s | beat-level clip aggregate (protocol 6.5) [apg_detail__t_d_s]: duration in seconds |
| beats__phone__apg_detail__t_e_s | beats | phone | no | no | s | beat-level clip aggregate (protocol 6.5) [apg_detail__t_e_s]: duration in seconds |
| beats__phone__fs | beats | phone | no | no |  | beat-level clip aggregate (protocol 6.5) [fs] |
| beats__phone__quality__good_fraction | beats | phone | no | no | ratio | beat-level clip aggregate (protocol 6.5) [quality__good_fraction]: dimensionless ratio or index |
| beats__phone__quality__n_beats | beats | phone | no | no | count | beat-level clip aggregate (protocol 6.5) [quality__n_beats]: count |
| beats__phone__quality__n_good | beats | phone | no | no | count | beat-level clip aggregate (protocol 6.5) [quality__n_good]: count |
| beats__phone__quality__quality_mean | beats | phone | no | no |  | beat-level clip aggregate (protocol 6.5) [quality__quality_mean] |
| beats__phone__quality__quality_median | beats | phone | no | no |  | beat-level clip aggregate (protocol 6.5) [quality__quality_median] |
| beats__phone__quality__quality_min_cfg | beats | phone | no | no |  | beat-level clip aggregate (protocol 6.5) [quality__quality_min_cfg] |
| beats__phone__resp_detail__resp_n_am | beats | phone | no | no |  | beat-level clip aggregate (protocol 6.5) [resp_detail__resp_n_am] |
| beats__phone__resp_detail__resp_n_ibi | beats | phone | no | no |  | beat-level clip aggregate (protocol 6.5) [resp_detail__resp_n_ibi] |
| beats__phone__resp_detail__resp_power_ratio_am | beats | phone | no | no |  | beat-level clip aggregate (protocol 6.5) [resp_detail__resp_power_ratio_am] |
| beats__phone__resp_detail__resp_power_ratio_ibi | beats | phone | no | no |  | beat-level clip aggregate (protocol 6.5) [resp_detail__resp_power_ratio_ibi] |
| beats__phone__resp_detail__resp_rate_agreement_bpm | beats | phone | no | no | bpm | beat-level clip aggregate (protocol 6.5) [resp_detail__resp_rate_agreement_bpm]: rate in beats per minute |
| beats__phone__resp_detail__resp_source | beats | phone | no | no |  | beat-level clip aggregate (protocol 6.5) [resp_detail__resp_source] |
| beats__phone__segmentation__changes | beats | phone | no | no |  | beat-level clip aggregate (protocol 6.5) [segmentation__changes] |
| beats__phone__segmentation__changes__n_added | beats | phone | no | no | count | beat-level clip aggregate (protocol 6.5) [segmentation__changes__n_added]: count |
| beats__phone__segmentation__changes__n_changed | beats | phone | no | no | count | beat-level clip aggregate (protocol 6.5) [segmentation__changes__n_changed]: count |
| beats__phone__segmentation__changes__n_first | beats | phone | no | no | count | beat-level clip aggregate (protocol 6.5) [segmentation__changes__n_first]: count |
| beats__phone__segmentation__changes__n_moved | beats | phone | no | no | count | beat-level clip aggregate (protocol 6.5) [segmentation__changes__n_moved]: count |
| beats__phone__segmentation__changes__n_removed | beats | phone | no | no | count | beat-level clip aggregate (protocol 6.5) [segmentation__changes__n_removed]: count |
| beats__phone__segmentation__changes__n_second | beats | phone | no | no | count | beat-level clip aggregate (protocol 6.5) [segmentation__changes__n_second]: count |
| beats__phone__segmentation__foot_method | beats | phone | no | no |  | beat-level clip aggregate (protocol 6.5) [segmentation__foot_method] |
| beats__phone__segmentation__fs | beats | phone | no | no |  | beat-level clip aggregate (protocol 6.5) [segmentation__fs] |
| beats__phone__segmentation__ibi_bounds_s | beats | phone | no | no | s | beat-level clip aggregate (protocol 6.5) [segmentation__ibi_bounds_s]: duration in seconds |
| beats__phone__segmentation__ibi_bounds_s__n | beats | phone | no | no |  | beat-level clip aggregate (protocol 6.5) [segmentation__ibi_bounds_s__n] |
| beats__phone__segmentation__matched_filter | beats | phone | no | no |  | beat-level clip aggregate (protocol 6.5) [segmentation__matched_filter] |
| beats__phone__segmentation__n_peaks | beats | phone | no | no | count | beat-level clip aggregate (protocol 6.5) [segmentation__n_peaks]: count |
| beats__phone__segmentation__pre | beats | phone | no | no |  | beat-level clip aggregate (protocol 6.5) [segmentation__pre] |
| beats__phone__segmentation__t0 | beats | phone | no | no |  | beat-level clip aggregate (protocol 6.5) [segmentation__t0] |
| beats__phone__signal | beats | phone | no | no |  | beat-level clip aggregate (protocol 6.5) [signal] |
| beats__phone__window | beats | phone | no | no |  | beat-level clip aggregate (protocol 6.5) [window] |
| beats__phone__window__n | beats | phone | no | no |  | beat-level clip aggregate (protocol 6.5) [window__n] |
| beats__pi__apg_detail__n_beats | beats | pi | no | yes | count | beat-level clip aggregate (protocol 6.5) [apg_detail__n_beats]: count |
| beats__pi__apg_detail__n_waves | beats | pi | no | yes | count | beat-level clip aggregate (protocol 6.5) [apg_detail__n_waves]: count |
| beats__pi__apg_detail__t_a_s | beats | pi | no | yes | s | beat-level clip aggregate (protocol 6.5) [apg_detail__t_a_s]: duration in seconds |
| beats__pi__apg_detail__t_b_s | beats | pi | no | yes | s | beat-level clip aggregate (protocol 6.5) [apg_detail__t_b_s]: duration in seconds |
| beats__pi__apg_detail__t_c_s | beats | pi | no | yes | s | beat-level clip aggregate (protocol 6.5) [apg_detail__t_c_s]: duration in seconds |
| beats__pi__apg_detail__t_d_s | beats | pi | no | yes | s | beat-level clip aggregate (protocol 6.5) [apg_detail__t_d_s]: duration in seconds |
| beats__pi__apg_detail__t_e_s | beats | pi | no | yes | s | beat-level clip aggregate (protocol 6.5) [apg_detail__t_e_s]: duration in seconds |
| beats__pi__fs | beats | pi | no | yes |  | beat-level clip aggregate (protocol 6.5) [fs] |
| beats__pi__quality__good_fraction | beats | pi | no | yes | ratio | beat-level clip aggregate (protocol 6.5) [quality__good_fraction]: dimensionless ratio or index |
| beats__pi__quality__n_beats | beats | pi | no | yes | count | beat-level clip aggregate (protocol 6.5) [quality__n_beats]: count |
| beats__pi__quality__n_good | beats | pi | no | yes | count | beat-level clip aggregate (protocol 6.5) [quality__n_good]: count |
| beats__pi__quality__quality_mean | beats | pi | no | yes |  | beat-level clip aggregate (protocol 6.5) [quality__quality_mean] |
| beats__pi__quality__quality_median | beats | pi | no | yes |  | beat-level clip aggregate (protocol 6.5) [quality__quality_median] |
| beats__pi__quality__quality_min_cfg | beats | pi | no | yes |  | beat-level clip aggregate (protocol 6.5) [quality__quality_min_cfg] |
| beats__pi__resp_detail__resp_n_am | beats | pi | no | yes |  | beat-level clip aggregate (protocol 6.5) [resp_detail__resp_n_am] |
| beats__pi__resp_detail__resp_n_ibi | beats | pi | no | yes |  | beat-level clip aggregate (protocol 6.5) [resp_detail__resp_n_ibi] |
| beats__pi__resp_detail__resp_power_ratio_am | beats | pi | no | yes |  | beat-level clip aggregate (protocol 6.5) [resp_detail__resp_power_ratio_am] |
| beats__pi__resp_detail__resp_power_ratio_ibi | beats | pi | no | yes |  | beat-level clip aggregate (protocol 6.5) [resp_detail__resp_power_ratio_ibi] |
| beats__pi__resp_detail__resp_rate_agreement_bpm | beats | pi | no | yes | bpm | beat-level clip aggregate (protocol 6.5) [resp_detail__resp_rate_agreement_bpm]: rate in beats per minute |
| beats__pi__resp_detail__resp_source | beats | pi | no | yes |  | beat-level clip aggregate (protocol 6.5) [resp_detail__resp_source] |
| beats__pi__segmentation__changes__n_added | beats | pi | no | yes | count | beat-level clip aggregate (protocol 6.5) [segmentation__changes__n_added]: count |
| beats__pi__segmentation__changes__n_changed | beats | pi | no | yes | count | beat-level clip aggregate (protocol 6.5) [segmentation__changes__n_changed]: count |
| beats__pi__segmentation__changes__n_first | beats | pi | no | yes | count | beat-level clip aggregate (protocol 6.5) [segmentation__changes__n_first]: count |
| beats__pi__segmentation__changes__n_moved | beats | pi | no | yes | count | beat-level clip aggregate (protocol 6.5) [segmentation__changes__n_moved]: count |
| beats__pi__segmentation__changes__n_removed | beats | pi | no | yes | count | beat-level clip aggregate (protocol 6.5) [segmentation__changes__n_removed]: count |
| beats__pi__segmentation__changes__n_second | beats | pi | no | yes | count | beat-level clip aggregate (protocol 6.5) [segmentation__changes__n_second]: count |
| beats__pi__segmentation__foot_method | beats | pi | no | yes |  | beat-level clip aggregate (protocol 6.5) [segmentation__foot_method] |
| beats__pi__segmentation__fs | beats | pi | no | yes |  | beat-level clip aggregate (protocol 6.5) [segmentation__fs] |
| beats__pi__segmentation__ibi_bounds_s | beats | pi | no | yes | s | beat-level clip aggregate (protocol 6.5) [segmentation__ibi_bounds_s]: duration in seconds |
| beats__pi__segmentation__ibi_bounds_s__n | beats | pi | no | yes |  | beat-level clip aggregate (protocol 6.5) [segmentation__ibi_bounds_s__n] |
| beats__pi__segmentation__matched_filter | beats | pi | no | yes |  | beat-level clip aggregate (protocol 6.5) [segmentation__matched_filter] |
| beats__pi__segmentation__n_peaks | beats | pi | no | yes | count | beat-level clip aggregate (protocol 6.5) [segmentation__n_peaks]: count |
| beats__pi__segmentation__pre | beats | pi | no | yes |  | beat-level clip aggregate (protocol 6.5) [segmentation__pre] |
| beats__pi__segmentation__t0 | beats | pi | no | yes |  | beat-level clip aggregate (protocol 6.5) [segmentation__t0] |
| beats__pi__signal | beats | pi | no | yes |  | beat-level clip aggregate (protocol 6.5) [signal] |
| beats__pi__window | beats | pi | no | yes |  | beat-level clip aggregate (protocol 6.5) [window] |
| beats__pi__window__n | beats | pi | no | yes |  | beat-level clip aggregate (protocol 6.5) [window__n] |
| beats__pi_proxy__apg_detail__n_beats | beats | pi_proxy | no | no | count | beat-level clip aggregate (protocol 6.5) [apg_detail__n_beats]: count |
| beats__pi_proxy__apg_detail__n_waves | beats | pi_proxy | no | no | count | beat-level clip aggregate (protocol 6.5) [apg_detail__n_waves]: count |
| beats__pi_proxy__apg_detail__t_a_s | beats | pi_proxy | no | no | s | beat-level clip aggregate (protocol 6.5) [apg_detail__t_a_s]: duration in seconds |
| beats__pi_proxy__apg_detail__t_b_s | beats | pi_proxy | no | no | s | beat-level clip aggregate (protocol 6.5) [apg_detail__t_b_s]: duration in seconds |
| beats__pi_proxy__apg_detail__t_c_s | beats | pi_proxy | no | no | s | beat-level clip aggregate (protocol 6.5) [apg_detail__t_c_s]: duration in seconds |
| beats__pi_proxy__apg_detail__t_d_s | beats | pi_proxy | no | no | s | beat-level clip aggregate (protocol 6.5) [apg_detail__t_d_s]: duration in seconds |
| beats__pi_proxy__apg_detail__t_e_s | beats | pi_proxy | no | no | s | beat-level clip aggregate (protocol 6.5) [apg_detail__t_e_s]: duration in seconds |
| beats__pi_proxy__fs | beats | pi_proxy | no | no |  | beat-level clip aggregate (protocol 6.5) [fs] |
| beats__pi_proxy__quality__good_fraction | beats | pi_proxy | no | no | ratio | beat-level clip aggregate (protocol 6.5) [quality__good_fraction]: dimensionless ratio or index |
| beats__pi_proxy__quality__n_beats | beats | pi_proxy | no | no | count | beat-level clip aggregate (protocol 6.5) [quality__n_beats]: count |
| beats__pi_proxy__quality__n_good | beats | pi_proxy | no | no | count | beat-level clip aggregate (protocol 6.5) [quality__n_good]: count |
| beats__pi_proxy__quality__quality_mean | beats | pi_proxy | no | no |  | beat-level clip aggregate (protocol 6.5) [quality__quality_mean] |
| beats__pi_proxy__quality__quality_median | beats | pi_proxy | no | no |  | beat-level clip aggregate (protocol 6.5) [quality__quality_median] |
| beats__pi_proxy__quality__quality_min_cfg | beats | pi_proxy | no | no |  | beat-level clip aggregate (protocol 6.5) [quality__quality_min_cfg] |
| beats__pi_proxy__resp_detail__resp_n_am | beats | pi_proxy | no | no |  | beat-level clip aggregate (protocol 6.5) [resp_detail__resp_n_am] |
| beats__pi_proxy__resp_detail__resp_n_ibi | beats | pi_proxy | no | no |  | beat-level clip aggregate (protocol 6.5) [resp_detail__resp_n_ibi] |
| beats__pi_proxy__resp_detail__resp_power_ratio_am | beats | pi_proxy | no | no |  | beat-level clip aggregate (protocol 6.5) [resp_detail__resp_power_ratio_am] |
| beats__pi_proxy__resp_detail__resp_power_ratio_ibi | beats | pi_proxy | no | no |  | beat-level clip aggregate (protocol 6.5) [resp_detail__resp_power_ratio_ibi] |
| beats__pi_proxy__resp_detail__resp_rate_agreement_bpm | beats | pi_proxy | no | no | bpm | beat-level clip aggregate (protocol 6.5) [resp_detail__resp_rate_agreement_bpm]: rate in beats per minute |
| beats__pi_proxy__resp_detail__resp_source | beats | pi_proxy | no | no |  | beat-level clip aggregate (protocol 6.5) [resp_detail__resp_source] |
| beats__pi_proxy__segmentation__changes | beats | pi_proxy | no | no |  | beat-level clip aggregate (protocol 6.5) [segmentation__changes] |
| beats__pi_proxy__segmentation__changes__n_added | beats | pi_proxy | no | no | count | beat-level clip aggregate (protocol 6.5) [segmentation__changes__n_added]: count |
| beats__pi_proxy__segmentation__changes__n_changed | beats | pi_proxy | no | no | count | beat-level clip aggregate (protocol 6.5) [segmentation__changes__n_changed]: count |
| beats__pi_proxy__segmentation__changes__n_first | beats | pi_proxy | no | no | count | beat-level clip aggregate (protocol 6.5) [segmentation__changes__n_first]: count |
| beats__pi_proxy__segmentation__changes__n_moved | beats | pi_proxy | no | no | count | beat-level clip aggregate (protocol 6.5) [segmentation__changes__n_moved]: count |
| beats__pi_proxy__segmentation__changes__n_removed | beats | pi_proxy | no | no | count | beat-level clip aggregate (protocol 6.5) [segmentation__changes__n_removed]: count |
| beats__pi_proxy__segmentation__changes__n_second | beats | pi_proxy | no | no | count | beat-level clip aggregate (protocol 6.5) [segmentation__changes__n_second]: count |
| beats__pi_proxy__segmentation__foot_method | beats | pi_proxy | no | no |  | beat-level clip aggregate (protocol 6.5) [segmentation__foot_method] |
| beats__pi_proxy__segmentation__fs | beats | pi_proxy | no | no |  | beat-level clip aggregate (protocol 6.5) [segmentation__fs] |
| beats__pi_proxy__segmentation__ibi_bounds_s | beats | pi_proxy | no | no | s | beat-level clip aggregate (protocol 6.5) [segmentation__ibi_bounds_s]: duration in seconds |
| beats__pi_proxy__segmentation__ibi_bounds_s__n | beats | pi_proxy | no | no |  | beat-level clip aggregate (protocol 6.5) [segmentation__ibi_bounds_s__n] |
| beats__pi_proxy__segmentation__matched_filter | beats | pi_proxy | no | no |  | beat-level clip aggregate (protocol 6.5) [segmentation__matched_filter] |
| beats__pi_proxy__segmentation__n_peaks | beats | pi_proxy | no | no | count | beat-level clip aggregate (protocol 6.5) [segmentation__n_peaks]: count |
| beats__pi_proxy__segmentation__pre | beats | pi_proxy | no | no |  | beat-level clip aggregate (protocol 6.5) [segmentation__pre] |
| beats__pi_proxy__segmentation__t0 | beats | pi_proxy | no | no |  | beat-level clip aggregate (protocol 6.5) [segmentation__t0] |
| beats__pi_proxy__signal | beats | pi_proxy | no | no |  | beat-level clip aggregate (protocol 6.5) [signal] |
| beats__pi_proxy__window | beats | pi_proxy | no | no |  | beat-level clip aggregate (protocol 6.5) [window] |
| beats__pi_proxy__window__n | beats | pi_proxy | no | no |  | beat-level clip aggregate (protocol 6.5) [window__n] |
| clinician__adverse_event | clinician | any | yes | no |  | clinician ECG read, requires_ecg (protocol 3) [adverse_event] |
| clinician__ecg_hr | clinician | any | yes | no |  | clinician ECG read, requires_ecg (protocol 3) [ecg_hr] |
| clinician__lead12_obtained | clinician | any | yes | no |  | clinician ECG read, requires_ecg (protocol 3) [lead12_obtained] |
| clinician__rhythm | clinician | any | yes | no |  | clinician ECG read, requires_ecg (protocol 3) [rhythm] |
| acute_30m | covariate | any | no | no | list | acute exposures in the last 30 min, ';'-joined |
| age | covariate | any | no | no | years | age at visit |
| age_band | covariate | any | no | no | label | <40 \| 40-59 \| 60+ |
| antihtn_today | covariate | any | no | no | label | antihypertensive taken today: yes <=2 h \| yes >2 h \| no |
| app_ver | covariate | any | no | no | label | onboarding app version, kept verbatim |
| arr_type | covariate | any | no | no | label | arrhythmia type when flagged |
| bmi | covariate | any | no | no | kg/m^2 | body-mass index from height and weight |
| bmi_class | covariate | any | no | no | label | WHO Asia-Pacific BMI class |
| bp_category | covariate | any | no | no | label | ACC/AHA 2017 band on the cuff mean (stratification format) |
| bp_target_23_dbp | covariate | any | no | no | mmHg | mean of BP2 and BP3 DBP (sensitivity target) |
| bp_target_23_sbp | covariate | any | no | no | mmHg | mean of BP2 and BP3 SBP (sensitivity target) |
| bp_target_dbp | covariate | any | no | no | mmHg | cuff DBP reference (target) |
| bp_target_rule | covariate | any | no | no | label | which averaging rule produced the SBP target |
| bp_target_sbp | covariate | any | no | no | mmHg | cuff SBP reference: mean of three readings, BP1 dropped when outlying (target) |
| bp_tertile | covariate | any | no | no | label | reference SBP tertile with cut points from the development set or the training fold (D-015) |
| bracket_flag | covariate | any | no | no | bool | cuff readings spread above the bracket threshold |
| capture_mode | covariate | any | no | no | label | simultaneous \| sequential (protocol 2) |
| cuff_size | covariate | any | no | no | label | cuff size used, kept verbatim |
| dept | covariate | any | no | no | label | department tag |
| dm_label | covariate | any | no | no | label | diabetes label derived from flag and HbA1c (DECISIONS D-005) |
| ecg_digitised | covariate | any | yes | no | bool | ECG came from the PDF digitiser rather than an ATC file |
| equity_scope | covariate | any | no | no | label | in when MST band is within the equity range |
| flag_anaemia_thalassaemia | covariate | any | no | no | bool | anaemia or thalassaemia flag |
| flag_arrhythmia | covariate | any | no | no | bool | arrhythmia flag |
| flag_chronic_kidney_disease | covariate | any | no | no | bool | chronic kidney disease flag |
| flag_diabetes | covariate | any | no | no | bool | diabetes flag |
| flag_hypertension | covariate | any | no | no | bool | hypertension flag |
| flags | covariate | any | no | no | list | disease flags, ';'-joined |
| glucose_mgdl | covariate | any | no | no | mg/dL | point-of-care glucose, nullable |
| haem_type | covariate | any | no | no | label | haematological type when flagged |
| handedness | covariate | any | no | no | label | handedness |
| hb_gdl | covariate | any | no | no | g/dL | chart haemoglobin |
| hba1c | covariate | any | no | no | % | chart HbA1c |
| hr_cuff_mean | covariate | any | no | no | bpm | mean cuff heart rate across readings |
| imaged_hand | covariate | any | no | no | label | hand imaged |
| irregular_pulse | covariate | any | no | no | bool | operator noted an irregular pulse |
| last_meal_h | covariate | any | no | no | h | hours since the last meal |
| lux_band | covariate | any | no | no | label | ambient lux band <200 \| 200-400 \| >400 (protocol 7) |
| mst_band | covariate | any | no | no | band | Monk Skin Tone band, self-selected 1..10 |
| mst_equity_arm | covariate | any | no | no | label | equity arm 4-6 versus 7-10 (protocol 7) |
| mst_group | covariate | any | no | no | label | MST grouping 4-5 \| 6-7 \| 8-10 (1-3 out of scope) |
| operator | covariate | any | no | no | label | operator id, kept verbatim |
| pregnant | covariate | any | no | no | bool | pregnant at visit |
| recovery | covariate | any | no | no | label | recovery gate result |
| rhythm_class | covariate | any | yes | no | label | clinician rhythm class from clinician.json (protocol 6.4) |
| sex | covariate | any | no | no | label | sex as recorded on the CRF |
| sex_f | covariate | any | no | no |  | 1 when sex is F, else 0 (numeric encoding of the CRF sex field) |
| spo2 | covariate | any | no | no | % | spot SpO2, nullable |
| sync_grade | covariate | any | no | no | label | sync grade: fine \| coarse \| none (protocol 4.4) |
| time_of_day | covariate | any | no | no | label | morning \| afternoon on the local clock (protocol 7) |
| unit_id | covariate | any | no | no | label | capture unit id, kept verbatim |
| ecg__app_rhythm_label | ecg | any | yes | no | label | Kardia app rhythm label (covariate only, never the label) |
| ecg__artefact_found | ecg | any | yes | no | bool | fine-anchor artefact onset found |
| ecg__artefact_onset_t_ecg_s | ecg | any | yes | no | s | artefact onset in ECG native seconds |
| ecg__artefact_score | ecg | any | yes | no | ratio | feature value over threshold at the onset |
| ecg__clinician_ecg_hr | ecg | any | yes | no | bpm | clinician-read heart rate (reference quantity) |
| ecg__clinician_rhythm | ecg | any | yes | no | label | clinician-read rhythm class (the label; from clinician.json) |
| ecg__clinician_rhythm_unmapped | ecg | any | yes | no | bool | clinician text was not one of ecg.rhythm_classes (mapped to other) |
| ecg__clipped_frac | ecg | any | yes | no | fraction | ATC samples at the int16 rails |
| ecg__crc_ok_all | ecg | any | yes | no | bool | every ATC block passed its CRC |
| ecg__detector_agree_frac | ecg | any | yes | no | fraction | primary R-peaks matched by the second detector |
| ecg__detectors | ecg | any | yes | no | label | detectors run, ';'-joined, primary first |
| ecg__digitiser_px_per_mm | ecg | any | yes | no | px/mm | PDF digitiser: grid pitch measured on the page |
| ecg__digitiser_rows_found | ecg | any | yes | no | count | PDF digitiser: strip rows found |
| ecg__digitiser_skew_deg | ecg | any | yes | no | deg | PDF digitiser: deskew angle applied |
| ecg__digitiser_trace_coverage | ecg | any | yes | no | fraction | PDF digitiser: columns with a trace |
| ecg__ecg_digitised | ecg | any | yes | no | bool | ECG came from the PDF digitiser rather than an ATC file |
| ecg__ecg_duration_s | ecg | any | yes | no | s | ECG recording length |
| ecg__export_format | ecg | any | yes | no | label | atc \| pdf |
| ecg__feature_window_end_s | ecg | any | yes | no | s | R-peaks after this ECG time are excluded (artefact onset or tail exclusion) |
| ecg__fs | ecg | any | yes | no | Hz | ECG sampling rate |
| ecg__hard_non_af | ecg | any | yes | no | bool | clinician rhythm is in ecg.hard_non_af |
| ecg__hr_mean_bpm | ecg | any | yes | no | bpm | 60 / mean valid IBI over the feature window |
| ecg__hr_median_bpm | ecg | any | yes | no | bpm | median instantaneous heart rate (60 / IBI) |
| ecg__ibi_cv | ecg | any | yes | no | ratio | IBI irregularity: coefficient of variation (SD / mean) |
| ecg__ibi_mean_ms | ecg | any | yes | no | ms | mean valid IBI |
| ecg__ibi_median_ms | ecg | any | yes | no | ms | median valid IBI |
| ecg__ibi_succ_diff_gt50_frac | ecg | any | yes | no | fraction | IBI irregularity: fraction of successive differences above 50 ms |
| ecg__n_beats | ecg | any | yes | no | count | R-peaks inside the feature window |
| ecg__n_ibi | ecg | any | yes | no | count | IBIs inside the window (adjacent peaks) |
| ecg__n_ibi_rejected | ecg | any | yes | no | count | IBIs outside beats.ibi_bounds_s |
| ecg__n_peaks_primary | ecg | any | yes | no | count | R-peaks found by the primary detector over the whole recording |
| ecg__n_samples | ecg | any | yes | no | count | ECG samples |
| ecg__pnn50 | ecg | any | yes | no | % | percentage of successive IBI differences above 50 ms |
| ecg__poincare_ratio | ecg | any | yes | no | ratio | SD1 / SD2 |
| ecg__poincare_sd1_ms | ecg | any | yes | no | ms | Poincare short-axis SD |
| ecg__poincare_sd2_ms | ecg | any | yes | no | ms | Poincare long-axis SD |
| ecg__r_amp_cv | ecg | any | yes | no | ratio | coefficient of variation of the R-peak amplitudes |
| ecg__r_amp_median_mv | ecg | any | yes | no | mV | median cleaned-ECG amplitude at the R-peaks |
| ecg__rmssd_ms | ecg | any | yes | no | ms | root mean square of successive IBI differences |
| ecg__sampen | ecg | any | yes | no | nats | sample entropy of the IBI series (m=2, r=0.2 SD) |
| ecg__sdnn_ms | ecg | any | yes | no | ms | SD of valid IBIs (ddof=1) |
| ecg__secondary_matched_frac | ecg | any | yes | no | fraction | second-detector peaks matched to a primary peak |
| ecg__source_file | ecg | any | yes | no | label | ECG file used |
| ecg__start_time | ecg | any | yes | no | label | ISO8601 start time from the ATC header (audit only; never used to align) |
| ecg__turning_point_ratio | ecg | any | yes | no | ratio | turning points / (n - 2) of the IBI sequence (2/3 for a random sequence) |
| ecg__window_span_s | ecg | any | yes | no | s | first to last R-peak used |
| hrv__phone__hr_cv | hrv | phone | no | no |  | heart-rate variability from palm beats (protocol 6.5) [hr_cv] |
| hrv__phone__ibi_hist_entropy | hrv | phone | no | no | nats | heart-rate variability from palm beats (protocol 6.5) [ibi_hist_entropy]: entropy |
| hrv__phone__mean_hr_bpm | hrv | phone | no | no | bpm | heart-rate variability from palm beats (protocol 6.5) [mean_hr_bpm]: rate in beats per minute |
| hrv__phone__mean_ibi_ms | hrv | phone | no | no | ms | heart-rate variability from palm beats (protocol 6.5) [mean_ibi_ms]: duration in milliseconds |
| hrv__phone__median_ibi_ms | hrv | phone | no | no | ms | heart-rate variability from palm beats (protocol 6.5) [median_ibi_ms]: duration in milliseconds |
| hrv__phone__n_beats | hrv | phone | no | no | count | heart-rate variability from palm beats (protocol 6.5) [n_beats]: count |
| hrv__phone__n_ibi | hrv | phone | no | no | count | heart-rate variability from palm beats (protocol 6.5) [n_ibi]: count |
| hrv__phone__pnn50 | hrv | phone | no | no |  | heart-rate variability from palm beats (protocol 6.5) [pnn50] |
| hrv__phone__rmssd_ms | hrv | phone | no | no | ms | heart-rate variability from palm beats (protocol 6.5) [rmssd_ms]: duration in milliseconds |
| hrv__phone__sampen | hrv | phone | no | no |  | heart-rate variability from palm beats (protocol 6.5) [sampen] |
| hrv__phone__sd1_ms | hrv | phone | no | no | ms | heart-rate variability from palm beats (protocol 6.5) [sd1_ms]: duration in milliseconds |
| hrv__phone__sd1_sd2_ratio | hrv | phone | no | no | ratio | heart-rate variability from palm beats (protocol 6.5) [sd1_sd2_ratio]: dimensionless ratio or index |
| hrv__phone__sd2_ms | hrv | phone | no | no | ms | heart-rate variability from palm beats (protocol 6.5) [sd2_ms]: duration in milliseconds |
| hrv__phone__sdnn_ms | hrv | phone | no | no | ms | heart-rate variability from palm beats (protocol 6.5) [sdnn_ms]: duration in milliseconds |
| hrv__phone__tpr | hrv | phone | no | no |  | heart-rate variability from palm beats (protocol 6.5) [tpr] |
| hrv__pi__hr_cv | hrv | pi | no | yes |  | heart-rate variability from palm beats (protocol 6.5) [hr_cv] |
| hrv__pi__ibi_hist_entropy | hrv | pi | no | yes | nats | heart-rate variability from palm beats (protocol 6.5) [ibi_hist_entropy]: entropy |
| hrv__pi__mean_hr_bpm | hrv | pi | no | yes | bpm | heart-rate variability from palm beats (protocol 6.5) [mean_hr_bpm]: rate in beats per minute |
| hrv__pi__mean_ibi_ms | hrv | pi | no | yes | ms | heart-rate variability from palm beats (protocol 6.5) [mean_ibi_ms]: duration in milliseconds |
| hrv__pi__median_ibi_ms | hrv | pi | no | yes | ms | heart-rate variability from palm beats (protocol 6.5) [median_ibi_ms]: duration in milliseconds |
| hrv__pi__n_beats | hrv | pi | no | yes | count | heart-rate variability from palm beats (protocol 6.5) [n_beats]: count |
| hrv__pi__n_ibi | hrv | pi | no | yes | count | heart-rate variability from palm beats (protocol 6.5) [n_ibi]: count |
| hrv__pi__pnn50 | hrv | pi | no | yes |  | heart-rate variability from palm beats (protocol 6.5) [pnn50] |
| hrv__pi__rmssd_ms | hrv | pi | no | yes | ms | heart-rate variability from palm beats (protocol 6.5) [rmssd_ms]: duration in milliseconds |
| hrv__pi__sampen | hrv | pi | no | yes |  | heart-rate variability from palm beats (protocol 6.5) [sampen] |
| hrv__pi__sd1_ms | hrv | pi | no | yes | ms | heart-rate variability from palm beats (protocol 6.5) [sd1_ms]: duration in milliseconds |
| hrv__pi__sd1_sd2_ratio | hrv | pi | no | yes | ratio | heart-rate variability from palm beats (protocol 6.5) [sd1_sd2_ratio]: dimensionless ratio or index |
| hrv__pi__sd2_ms | hrv | pi | no | yes | ms | heart-rate variability from palm beats (protocol 6.5) [sd2_ms]: duration in milliseconds |
| hrv__pi__sdnn_ms | hrv | pi | no | yes | ms | heart-rate variability from palm beats (protocol 6.5) [sdnn_ms]: duration in milliseconds |
| hrv__pi__tpr | hrv | pi | no | yes |  | heart-rate variability from palm beats (protocol 6.5) [tpr] |
| hrv__pi_proxy__hr_cv | hrv | pi_proxy | no | no |  | heart-rate variability from palm beats (protocol 6.5) [hr_cv] |
| hrv__pi_proxy__ibi_hist_entropy | hrv | pi_proxy | no | no | nats | heart-rate variability from palm beats (protocol 6.5) [ibi_hist_entropy]: entropy |
| hrv__pi_proxy__mean_hr_bpm | hrv | pi_proxy | no | no | bpm | heart-rate variability from palm beats (protocol 6.5) [mean_hr_bpm]: rate in beats per minute |
| hrv__pi_proxy__mean_ibi_ms | hrv | pi_proxy | no | no | ms | heart-rate variability from palm beats (protocol 6.5) [mean_ibi_ms]: duration in milliseconds |
| hrv__pi_proxy__median_ibi_ms | hrv | pi_proxy | no | no | ms | heart-rate variability from palm beats (protocol 6.5) [median_ibi_ms]: duration in milliseconds |
| hrv__pi_proxy__n_beats | hrv | pi_proxy | no | no | count | heart-rate variability from palm beats (protocol 6.5) [n_beats]: count |
| hrv__pi_proxy__n_ibi | hrv | pi_proxy | no | no | count | heart-rate variability from palm beats (protocol 6.5) [n_ibi]: count |
| hrv__pi_proxy__pnn50 | hrv | pi_proxy | no | no |  | heart-rate variability from palm beats (protocol 6.5) [pnn50] |
| hrv__pi_proxy__rmssd_ms | hrv | pi_proxy | no | no | ms | heart-rate variability from palm beats (protocol 6.5) [rmssd_ms]: duration in milliseconds |
| hrv__pi_proxy__sampen | hrv | pi_proxy | no | no |  | heart-rate variability from palm beats (protocol 6.5) [sampen] |
| hrv__pi_proxy__sd1_ms | hrv | pi_proxy | no | no | ms | heart-rate variability from palm beats (protocol 6.5) [sd1_ms]: duration in milliseconds |
| hrv__pi_proxy__sd1_sd2_ratio | hrv | pi_proxy | no | no | ratio | heart-rate variability from palm beats (protocol 6.5) [sd1_sd2_ratio]: dimensionless ratio or index |
| hrv__pi_proxy__sd2_ms | hrv | pi_proxy | no | no | ms | heart-rate variability from palm beats (protocol 6.5) [sd2_ms]: duration in milliseconds |
| hrv__pi_proxy__sdnn_ms | hrv | pi_proxy | no | no | ms | heart-rate variability from palm beats (protocol 6.5) [sdnn_ms]: duration in milliseconds |
| hrv__pi_proxy__tpr | hrv | pi_proxy | no | no |  | heart-rate variability from palm beats (protocol 6.5) [tpr] |
| camera | id | any | no | no | id | pi \| phone \| pi_proxy |
| clip_id | id | any | no | no | id | clip id; clip1b marks the single permitted re-shoot |
| source_study_id | id | any | no | no | id | source participant of an augmented copy (protocol 8); null for originals |
| stream | id | any | no | no | label | data stream: pilot \| development \| model_selection \| test |
| study_id | id | any | no | no | id | participant id (join key) |
| morphology__phone__amplitude | morphology | phone | no | no |  | beat morphology, per-beat ensemble (protocol 6.5) [amplitude] |
| morphology__phone__amplitude_sd | morphology | phone | no | no |  | beat morphology, per-beat ensemble (protocol 6.5) [amplitude_sd] |
| morphology__phone__area_ratio | morphology | phone | no | no | ratio | beat morphology, per-beat ensemble (protocol 6.5) [area_ratio]: dimensionless ratio or index |
| morphology__phone__area_ratio_sd | morphology | phone | no | no |  | beat morphology, per-beat ensemble (protocol 6.5) [area_ratio_sd] |
| morphology__phone__augmentation_index_proxy | morphology | phone | no | no |  | beat morphology, per-beat ensemble (protocol 6.5) [augmentation_index_proxy] |
| morphology__phone__augmentation_index_proxy_sd | morphology | phone | no | no |  | beat morphology, per-beat ensemble (protocol 6.5) [augmentation_index_proxy_sd] |
| morphology__phone__decay_tau_s | morphology | phone | no | no | s | beat morphology, per-beat ensemble (protocol 6.5) [decay_tau_s]: duration in seconds |
| morphology__phone__decay_tau_s_sd | morphology | phone | no | no |  | beat morphology, per-beat ensemble (protocol 6.5) [decay_tau_s_sd] |
| morphology__phone__diastolic_area | morphology | phone | no | no |  | beat morphology, per-beat ensemble (protocol 6.5) [diastolic_area] |
| morphology__phone__diastolic_area_sd | morphology | phone | no | no |  | beat morphology, per-beat ensemble (protocol 6.5) [diastolic_area_sd] |
| morphology__phone__diastolic_time_s | morphology | phone | no | no | s | beat morphology, per-beat ensemble (protocol 6.5) [diastolic_time_s]: duration in seconds |
| morphology__phone__diastolic_time_s_sd | morphology | phone | no | no |  | beat morphology, per-beat ensemble (protocol 6.5) [diastolic_time_s_sd] |
| morphology__phone__dicrotic_notch_present | morphology | phone | no | no | bool | beat morphology, per-beat ensemble (protocol 6.5) [dicrotic_notch_present]: boolean flag |
| morphology__phone__n_beats_total | morphology | phone | no | no | count | beat morphology, per-beat ensemble (protocol 6.5) [n_beats_total]: count |
| morphology__phone__n_beats_used | morphology | phone | no | no | bool | beat morphology, per-beat ensemble (protocol 6.5) [n_beats_used]: boolean flag |
| morphology__phone__notch_fraction | morphology | phone | no | no | ratio | beat morphology, per-beat ensemble (protocol 6.5) [notch_fraction]: dimensionless ratio or index |
| morphology__phone__notch_time_s | morphology | phone | no | no | s | beat morphology, per-beat ensemble (protocol 6.5) [notch_time_s]: duration in seconds |
| morphology__phone__notch_time_s_sd | morphology | phone | no | no |  | beat morphology, per-beat ensemble (protocol 6.5) [notch_time_s_sd] |
| morphology__phone__pulse_width_s | morphology | phone | no | no | s | beat morphology, per-beat ensemble (protocol 6.5) [pulse_width_s]: duration in seconds |
| morphology__phone__pulse_width_s_sd | morphology | phone | no | no |  | beat morphology, per-beat ensemble (protocol 6.5) [pulse_width_s_sd] |
| morphology__phone__reflection_index | morphology | phone | no | no | ratio | beat morphology, per-beat ensemble (protocol 6.5) [reflection_index]: dimensionless ratio or index |
| morphology__phone__reflection_index_sd | morphology | phone | no | no |  | beat morphology, per-beat ensemble (protocol 6.5) [reflection_index_sd] |
| morphology__phone__rise_slope | morphology | phone | no | no |  | beat morphology, per-beat ensemble (protocol 6.5) [rise_slope] |
| morphology__phone__rise_slope_sd | morphology | phone | no | no |  | beat morphology, per-beat ensemble (protocol 6.5) [rise_slope_sd] |
| morphology__phone__systolic_area | morphology | phone | no | no |  | beat morphology, per-beat ensemble (protocol 6.5) [systolic_area] |
| morphology__phone__systolic_area_sd | morphology | phone | no | no |  | beat morphology, per-beat ensemble (protocol 6.5) [systolic_area_sd] |
| morphology__phone__systolic_width_50_s | morphology | phone | no | no | s | beat morphology, per-beat ensemble (protocol 6.5) [systolic_width_50_s]: duration in seconds |
| morphology__phone__systolic_width_50_s_sd | morphology | phone | no | no |  | beat morphology, per-beat ensemble (protocol 6.5) [systolic_width_50_s_sd] |
| morphology__phone__upstroke_time_s | morphology | phone | no | no | s | beat morphology, per-beat ensemble (protocol 6.5) [upstroke_time_s]: duration in seconds |
| morphology__phone__upstroke_time_s_sd | morphology | phone | no | no |  | beat morphology, per-beat ensemble (protocol 6.5) [upstroke_time_s_sd] |
| morphology__pi__amplitude | morphology | pi | no | yes |  | beat morphology, per-beat ensemble (protocol 6.5) [amplitude] |
| morphology__pi__amplitude_sd | morphology | pi | no | yes |  | beat morphology, per-beat ensemble (protocol 6.5) [amplitude_sd] |
| morphology__pi__area_ratio | morphology | pi | no | yes | ratio | beat morphology, per-beat ensemble (protocol 6.5) [area_ratio]: dimensionless ratio or index |
| morphology__pi__area_ratio_sd | morphology | pi | no | yes |  | beat morphology, per-beat ensemble (protocol 6.5) [area_ratio_sd] |
| morphology__pi__augmentation_index_proxy | morphology | pi | no | yes |  | beat morphology, per-beat ensemble (protocol 6.5) [augmentation_index_proxy] |
| morphology__pi__augmentation_index_proxy_sd | morphology | pi | no | yes |  | beat morphology, per-beat ensemble (protocol 6.5) [augmentation_index_proxy_sd] |
| morphology__pi__decay_tau_s | morphology | pi | no | yes | s | beat morphology, per-beat ensemble (protocol 6.5) [decay_tau_s]: duration in seconds |
| morphology__pi__decay_tau_s_sd | morphology | pi | no | yes |  | beat morphology, per-beat ensemble (protocol 6.5) [decay_tau_s_sd] |
| morphology__pi__diastolic_area | morphology | pi | no | yes |  | beat morphology, per-beat ensemble (protocol 6.5) [diastolic_area] |
| morphology__pi__diastolic_area_sd | morphology | pi | no | yes |  | beat morphology, per-beat ensemble (protocol 6.5) [diastolic_area_sd] |
| morphology__pi__diastolic_time_s | morphology | pi | no | yes | s | beat morphology, per-beat ensemble (protocol 6.5) [diastolic_time_s]: duration in seconds |
| morphology__pi__diastolic_time_s_sd | morphology | pi | no | yes |  | beat morphology, per-beat ensemble (protocol 6.5) [diastolic_time_s_sd] |
| morphology__pi__dicrotic_notch_present | morphology | pi | no | yes | bool | beat morphology, per-beat ensemble (protocol 6.5) [dicrotic_notch_present]: boolean flag |
| morphology__pi__n_beats_total | morphology | pi | no | yes | count | beat morphology, per-beat ensemble (protocol 6.5) [n_beats_total]: count |
| morphology__pi__n_beats_used | morphology | pi | no | yes | bool | beat morphology, per-beat ensemble (protocol 6.5) [n_beats_used]: boolean flag |
| morphology__pi__notch_fraction | morphology | pi | no | yes | ratio | beat morphology, per-beat ensemble (protocol 6.5) [notch_fraction]: dimensionless ratio or index |
| morphology__pi__notch_time_s | morphology | pi | no | yes | s | beat morphology, per-beat ensemble (protocol 6.5) [notch_time_s]: duration in seconds |
| morphology__pi__notch_time_s_sd | morphology | pi | no | yes |  | beat morphology, per-beat ensemble (protocol 6.5) [notch_time_s_sd] |
| morphology__pi__pulse_width_s | morphology | pi | no | yes | s | beat morphology, per-beat ensemble (protocol 6.5) [pulse_width_s]: duration in seconds |
| morphology__pi__pulse_width_s_sd | morphology | pi | no | yes |  | beat morphology, per-beat ensemble (protocol 6.5) [pulse_width_s_sd] |
| morphology__pi__reflection_index | morphology | pi | no | yes | ratio | beat morphology, per-beat ensemble (protocol 6.5) [reflection_index]: dimensionless ratio or index |
| morphology__pi__reflection_index_sd | morphology | pi | no | yes |  | beat morphology, per-beat ensemble (protocol 6.5) [reflection_index_sd] |
| morphology__pi__rise_slope | morphology | pi | no | yes |  | beat morphology, per-beat ensemble (protocol 6.5) [rise_slope] |
| morphology__pi__rise_slope_sd | morphology | pi | no | yes |  | beat morphology, per-beat ensemble (protocol 6.5) [rise_slope_sd] |
| morphology__pi__systolic_area | morphology | pi | no | yes |  | beat morphology, per-beat ensemble (protocol 6.5) [systolic_area] |
| morphology__pi__systolic_area_sd | morphology | pi | no | yes |  | beat morphology, per-beat ensemble (protocol 6.5) [systolic_area_sd] |
| morphology__pi__systolic_width_50_s | morphology | pi | no | yes | s | beat morphology, per-beat ensemble (protocol 6.5) [systolic_width_50_s]: duration in seconds |
| morphology__pi__systolic_width_50_s_sd | morphology | pi | no | yes |  | beat morphology, per-beat ensemble (protocol 6.5) [systolic_width_50_s_sd] |
| morphology__pi__upstroke_time_s | morphology | pi | no | yes | s | beat morphology, per-beat ensemble (protocol 6.5) [upstroke_time_s]: duration in seconds |
| morphology__pi__upstroke_time_s_sd | morphology | pi | no | yes |  | beat morphology, per-beat ensemble (protocol 6.5) [upstroke_time_s_sd] |
| morphology__pi_proxy__amplitude | morphology | pi_proxy | no | no |  | beat morphology, per-beat ensemble (protocol 6.5) [amplitude] |
| morphology__pi_proxy__amplitude_sd | morphology | pi_proxy | no | no |  | beat morphology, per-beat ensemble (protocol 6.5) [amplitude_sd] |
| morphology__pi_proxy__area_ratio | morphology | pi_proxy | no | no | ratio | beat morphology, per-beat ensemble (protocol 6.5) [area_ratio]: dimensionless ratio or index |
| morphology__pi_proxy__area_ratio_sd | morphology | pi_proxy | no | no |  | beat morphology, per-beat ensemble (protocol 6.5) [area_ratio_sd] |
| morphology__pi_proxy__augmentation_index_proxy | morphology | pi_proxy | no | no |  | beat morphology, per-beat ensemble (protocol 6.5) [augmentation_index_proxy] |
| morphology__pi_proxy__augmentation_index_proxy_sd | morphology | pi_proxy | no | no |  | beat morphology, per-beat ensemble (protocol 6.5) [augmentation_index_proxy_sd] |
| morphology__pi_proxy__decay_tau_s | morphology | pi_proxy | no | no | s | beat morphology, per-beat ensemble (protocol 6.5) [decay_tau_s]: duration in seconds |
| morphology__pi_proxy__decay_tau_s_sd | morphology | pi_proxy | no | no |  | beat morphology, per-beat ensemble (protocol 6.5) [decay_tau_s_sd] |
| morphology__pi_proxy__diastolic_area | morphology | pi_proxy | no | no |  | beat morphology, per-beat ensemble (protocol 6.5) [diastolic_area] |
| morphology__pi_proxy__diastolic_area_sd | morphology | pi_proxy | no | no |  | beat morphology, per-beat ensemble (protocol 6.5) [diastolic_area_sd] |
| morphology__pi_proxy__diastolic_time_s | morphology | pi_proxy | no | no | s | beat morphology, per-beat ensemble (protocol 6.5) [diastolic_time_s]: duration in seconds |
| morphology__pi_proxy__diastolic_time_s_sd | morphology | pi_proxy | no | no |  | beat morphology, per-beat ensemble (protocol 6.5) [diastolic_time_s_sd] |
| morphology__pi_proxy__dicrotic_notch_present | morphology | pi_proxy | no | no | bool | beat morphology, per-beat ensemble (protocol 6.5) [dicrotic_notch_present]: boolean flag |
| morphology__pi_proxy__n_beats_total | morphology | pi_proxy | no | no | count | beat morphology, per-beat ensemble (protocol 6.5) [n_beats_total]: count |
| morphology__pi_proxy__n_beats_used | morphology | pi_proxy | no | no | bool | beat morphology, per-beat ensemble (protocol 6.5) [n_beats_used]: boolean flag |
| morphology__pi_proxy__notch_fraction | morphology | pi_proxy | no | no | ratio | beat morphology, per-beat ensemble (protocol 6.5) [notch_fraction]: dimensionless ratio or index |
| morphology__pi_proxy__notch_time_s | morphology | pi_proxy | no | no | s | beat morphology, per-beat ensemble (protocol 6.5) [notch_time_s]: duration in seconds |
| morphology__pi_proxy__notch_time_s_sd | morphology | pi_proxy | no | no |  | beat morphology, per-beat ensemble (protocol 6.5) [notch_time_s_sd] |
| morphology__pi_proxy__pulse_width_s | morphology | pi_proxy | no | no | s | beat morphology, per-beat ensemble (protocol 6.5) [pulse_width_s]: duration in seconds |
| morphology__pi_proxy__pulse_width_s_sd | morphology | pi_proxy | no | no |  | beat morphology, per-beat ensemble (protocol 6.5) [pulse_width_s_sd] |
| morphology__pi_proxy__reflection_index | morphology | pi_proxy | no | no | ratio | beat morphology, per-beat ensemble (protocol 6.5) [reflection_index]: dimensionless ratio or index |
| morphology__pi_proxy__reflection_index_sd | morphology | pi_proxy | no | no |  | beat morphology, per-beat ensemble (protocol 6.5) [reflection_index_sd] |
| morphology__pi_proxy__rise_slope | morphology | pi_proxy | no | no |  | beat morphology, per-beat ensemble (protocol 6.5) [rise_slope] |
| morphology__pi_proxy__rise_slope_sd | morphology | pi_proxy | no | no |  | beat morphology, per-beat ensemble (protocol 6.5) [rise_slope_sd] |
| morphology__pi_proxy__systolic_area | morphology | pi_proxy | no | no |  | beat morphology, per-beat ensemble (protocol 6.5) [systolic_area] |
| morphology__pi_proxy__systolic_area_sd | morphology | pi_proxy | no | no |  | beat morphology, per-beat ensemble (protocol 6.5) [systolic_area_sd] |
| morphology__pi_proxy__systolic_width_50_s | morphology | pi_proxy | no | no | s | beat morphology, per-beat ensemble (protocol 6.5) [systolic_width_50_s]: duration in seconds |
| morphology__pi_proxy__systolic_width_50_s_sd | morphology | pi_proxy | no | no |  | beat morphology, per-beat ensemble (protocol 6.5) [systolic_width_50_s_sd] |
| morphology__pi_proxy__upstroke_time_s | morphology | pi_proxy | no | no | s | beat morphology, per-beat ensemble (protocol 6.5) [upstroke_time_s]: duration in seconds |
| morphology__pi_proxy__upstroke_time_s_sd | morphology | pi_proxy | no | no |  | beat morphology, per-beat ensemble (protocol 6.5) [upstroke_time_s_sd] |
| pat__phone__ectopic_capture_fraction | pat | phone | yes | no | ratio | pulse arrival time versus ECG, requires_ecg (protocol 6.6) [ectopic_capture_fraction]: dimensionless ratio or index |
| pat__phone__ibi_corr | pat | phone | yes | no |  | pulse arrival time versus ECG, requires_ecg (protocol 6.6) [ibi_corr] |
| pat__phone__ibi_diff_mad_ms | pat | phone | yes | no | ms | pulse arrival time versus ECG, requires_ecg (protocol 6.6) [ibi_diff_mad_ms]: duration in milliseconds |
| pat__phone__ibi_diff_mean_ms | pat | phone | yes | no | ms | pulse arrival time versus ECG, requires_ecg (protocol 6.6) [ibi_diff_mean_ms]: duration in milliseconds |
| pat__phone__ibi_diff_sd_ms | pat | phone | yes | no | ms | pulse arrival time versus ECG, requires_ecg (protocol 6.6) [ibi_diff_sd_ms]: duration in milliseconds |
| pat__phone__n_compared | pat | phone | yes | no | count | pulse arrival time versus ECG, requires_ecg (protocol 6.6) [n_compared]: count |
| pat__phone__n_ectopic_captured | pat | phone | yes | no | count | pulse arrival time versus ECG, requires_ecg (protocol 6.6) [n_ectopic_captured]: count |
| pat__phone__n_ectopic_ecg | pat | phone | yes | no | count | pulse arrival time versus ECG, requires_ecg (protocol 6.6) [n_ectopic_ecg]: count |
| pat__phone__n_pairs | pat | phone | yes | no | count | pulse arrival time versus ECG, requires_ecg (protocol 6.6) [n_pairs]: count |
| pat__phone__n_rpeaks | pat | phone | yes | no | count | pulse arrival time versus ECG, requires_ecg (protocol 6.6) [n_rpeaks]: count |
| pat__phone__pairing_rate | pat | phone | yes | no |  | pulse arrival time versus ECG, requires_ecg (protocol 6.6) [pairing_rate] |
| pat__phone__pat_mean_ms | pat | phone | yes | no | ms | pulse arrival time versus ECG, requires_ecg (protocol 6.6) [pat_mean_ms]: duration in milliseconds |
| pat__phone__pat_median_ms | pat | phone | yes | no | ms | pulse arrival time versus ECG, requires_ecg (protocol 6.6) [pat_median_ms]: duration in milliseconds |
| pat__phone__pat_sd_ms | pat | phone | yes | no | ms | pulse arrival time versus ECG, requires_ecg (protocol 6.6) [pat_sd_ms]: duration in milliseconds |
| pat__phone__sync_grade | pat | phone | yes | no |  | pulse arrival time versus ECG, requires_ecg (protocol 6.6) [sync_grade] |
| pat__pi__ectopic_capture_fraction | pat | pi | yes | yes | ratio | pulse arrival time versus ECG, requires_ecg (protocol 6.6) [ectopic_capture_fraction]: dimensionless ratio or index |
| pat__pi__ibi_corr | pat | pi | yes | yes |  | pulse arrival time versus ECG, requires_ecg (protocol 6.6) [ibi_corr] |
| pat__pi__ibi_diff_mad_ms | pat | pi | yes | yes | ms | pulse arrival time versus ECG, requires_ecg (protocol 6.6) [ibi_diff_mad_ms]: duration in milliseconds |
| pat__pi__ibi_diff_mean_ms | pat | pi | yes | yes | ms | pulse arrival time versus ECG, requires_ecg (protocol 6.6) [ibi_diff_mean_ms]: duration in milliseconds |
| pat__pi__ibi_diff_sd_ms | pat | pi | yes | yes | ms | pulse arrival time versus ECG, requires_ecg (protocol 6.6) [ibi_diff_sd_ms]: duration in milliseconds |
| pat__pi__n_compared | pat | pi | yes | yes | count | pulse arrival time versus ECG, requires_ecg (protocol 6.6) [n_compared]: count |
| pat__pi__n_ectopic_captured | pat | pi | yes | yes | count | pulse arrival time versus ECG, requires_ecg (protocol 6.6) [n_ectopic_captured]: count |
| pat__pi__n_ectopic_ecg | pat | pi | yes | yes | count | pulse arrival time versus ECG, requires_ecg (protocol 6.6) [n_ectopic_ecg]: count |
| pat__pi__n_pairs | pat | pi | yes | yes | count | pulse arrival time versus ECG, requires_ecg (protocol 6.6) [n_pairs]: count |
| pat__pi__n_rpeaks | pat | pi | yes | yes | count | pulse arrival time versus ECG, requires_ecg (protocol 6.6) [n_rpeaks]: count |
| pat__pi__pairing_rate | pat | pi | yes | yes |  | pulse arrival time versus ECG, requires_ecg (protocol 6.6) [pairing_rate] |
| pat__pi__pat_mean_ms | pat | pi | yes | yes | ms | pulse arrival time versus ECG, requires_ecg (protocol 6.6) [pat_mean_ms]: duration in milliseconds |
| pat__pi__pat_median_ms | pat | pi | yes | yes | ms | pulse arrival time versus ECG, requires_ecg (protocol 6.6) [pat_median_ms]: duration in milliseconds |
| pat__pi__pat_sd_ms | pat | pi | yes | yes | ms | pulse arrival time versus ECG, requires_ecg (protocol 6.6) [pat_sd_ms]: duration in milliseconds |
| pat__pi__sync_grade | pat | pi | yes | yes |  | pulse arrival time versus ECG, requires_ecg (protocol 6.6) [sync_grade] |
| pat__pi_proxy__ectopic_capture_fraction | pat | pi_proxy | yes | no | ratio | pulse arrival time versus ECG, requires_ecg (protocol 6.6) [ectopic_capture_fraction]: dimensionless ratio or index |
| pat__pi_proxy__ibi_corr | pat | pi_proxy | yes | no |  | pulse arrival time versus ECG, requires_ecg (protocol 6.6) [ibi_corr] |
| pat__pi_proxy__ibi_diff_mad_ms | pat | pi_proxy | yes | no | ms | pulse arrival time versus ECG, requires_ecg (protocol 6.6) [ibi_diff_mad_ms]: duration in milliseconds |
| pat__pi_proxy__ibi_diff_mean_ms | pat | pi_proxy | yes | no | ms | pulse arrival time versus ECG, requires_ecg (protocol 6.6) [ibi_diff_mean_ms]: duration in milliseconds |
| pat__pi_proxy__ibi_diff_sd_ms | pat | pi_proxy | yes | no | ms | pulse arrival time versus ECG, requires_ecg (protocol 6.6) [ibi_diff_sd_ms]: duration in milliseconds |
| pat__pi_proxy__n_compared | pat | pi_proxy | yes | no | count | pulse arrival time versus ECG, requires_ecg (protocol 6.6) [n_compared]: count |
| pat__pi_proxy__n_ectopic_captured | pat | pi_proxy | yes | no | count | pulse arrival time versus ECG, requires_ecg (protocol 6.6) [n_ectopic_captured]: count |
| pat__pi_proxy__n_ectopic_ecg | pat | pi_proxy | yes | no | count | pulse arrival time versus ECG, requires_ecg (protocol 6.6) [n_ectopic_ecg]: count |
| pat__pi_proxy__n_pairs | pat | pi_proxy | yes | no | count | pulse arrival time versus ECG, requires_ecg (protocol 6.6) [n_pairs]: count |
| pat__pi_proxy__n_rpeaks | pat | pi_proxy | yes | no | count | pulse arrival time versus ECG, requires_ecg (protocol 6.6) [n_rpeaks]: count |
| pat__pi_proxy__pairing_rate | pat | pi_proxy | yes | no |  | pulse arrival time versus ECG, requires_ecg (protocol 6.6) [pairing_rate] |
| pat__pi_proxy__pat_mean_ms | pat | pi_proxy | yes | no | ms | pulse arrival time versus ECG, requires_ecg (protocol 6.6) [pat_mean_ms]: duration in milliseconds |
| pat__pi_proxy__pat_median_ms | pat | pi_proxy | yes | no | ms | pulse arrival time versus ECG, requires_ecg (protocol 6.6) [pat_median_ms]: duration in milliseconds |
| pat__pi_proxy__pat_sd_ms | pat | pi_proxy | yes | no | ms | pulse arrival time versus ECG, requires_ecg (protocol 6.6) [pat_sd_ms]: duration in milliseconds |
| pat__pi_proxy__sync_grade | pat | pi_proxy | yes | no |  | pulse arrival time versus ECG, requires_ecg (protocol 6.6) [sync_grade] |
| perfusion__phone__central_palm__B | perfusion | phone | no | no |  | perfusion index per ROI and channel (protocol 6.5) [central_palm__B] |
| perfusion__phone__central_palm__G | perfusion | phone | no | no |  | perfusion index per ROI and channel (protocol 6.5) [central_palm__G] |
| perfusion__phone__central_palm__R | perfusion | phone | no | no |  | perfusion index per ROI and channel (protocol 6.5) [central_palm__R] |
| perfusion__phone__hypothenar__B | perfusion | phone | no | no |  | perfusion index per ROI and channel (protocol 6.5) [hypothenar__B] |
| perfusion__phone__hypothenar__G | perfusion | phone | no | no |  | perfusion index per ROI and channel (protocol 6.5) [hypothenar__G] |
| perfusion__phone__hypothenar__R | perfusion | phone | no | no |  | perfusion index per ROI and channel (protocol 6.5) [hypothenar__R] |
| perfusion__phone__mid_phalanges__B | perfusion | phone | no | no |  | perfusion index per ROI and channel (protocol 6.5) [mid_phalanges__B] |
| perfusion__phone__mid_phalanges__G | perfusion | phone | no | no |  | perfusion index per ROI and channel (protocol 6.5) [mid_phalanges__G] |
| perfusion__phone__mid_phalanges__R | perfusion | phone | no | no |  | perfusion index per ROI and channel (protocol 6.5) [mid_phalanges__R] |
| perfusion__phone__pad_index__B | perfusion | phone | no | no |  | perfusion index per ROI and channel (protocol 6.5) [pad_index__B] |
| perfusion__phone__pad_index__G | perfusion | phone | no | no |  | perfusion index per ROI and channel (protocol 6.5) [pad_index__G] |
| perfusion__phone__pad_index__R | perfusion | phone | no | no |  | perfusion index per ROI and channel (protocol 6.5) [pad_index__R] |
| perfusion__phone__pad_little__B | perfusion | phone | no | no |  | perfusion index per ROI and channel (protocol 6.5) [pad_little__B] |
| perfusion__phone__pad_little__G | perfusion | phone | no | no |  | perfusion index per ROI and channel (protocol 6.5) [pad_little__G] |
| perfusion__phone__pad_little__R | perfusion | phone | no | no |  | perfusion index per ROI and channel (protocol 6.5) [pad_little__R] |
| perfusion__phone__pad_middle__B | perfusion | phone | no | no |  | perfusion index per ROI and channel (protocol 6.5) [pad_middle__B] |
| perfusion__phone__pad_middle__G | perfusion | phone | no | no |  | perfusion index per ROI and channel (protocol 6.5) [pad_middle__G] |
| perfusion__phone__pad_middle__R | perfusion | phone | no | no |  | perfusion index per ROI and channel (protocol 6.5) [pad_middle__R] |
| perfusion__phone__pad_ring__B | perfusion | phone | no | no |  | perfusion index per ROI and channel (protocol 6.5) [pad_ring__B] |
| perfusion__phone__pad_ring__G | perfusion | phone | no | no |  | perfusion index per ROI and channel (protocol 6.5) [pad_ring__G] |
| perfusion__phone__pad_ring__R | perfusion | phone | no | no |  | perfusion index per ROI and channel (protocol 6.5) [pad_ring__R] |
| perfusion__phone__prox_index__B | perfusion | phone | no | no |  | perfusion index per ROI and channel (protocol 6.5) [prox_index__B] |
| perfusion__phone__prox_index__G | perfusion | phone | no | no |  | perfusion index per ROI and channel (protocol 6.5) [prox_index__G] |
| perfusion__phone__prox_index__R | perfusion | phone | no | no |  | perfusion index per ROI and channel (protocol 6.5) [prox_index__R] |
| perfusion__phone__prox_little__B | perfusion | phone | no | no |  | perfusion index per ROI and channel (protocol 6.5) [prox_little__B] |
| perfusion__phone__prox_little__G | perfusion | phone | no | no |  | perfusion index per ROI and channel (protocol 6.5) [prox_little__G] |
| perfusion__phone__prox_little__R | perfusion | phone | no | no |  | perfusion index per ROI and channel (protocol 6.5) [prox_little__R] |
| perfusion__phone__prox_middle__B | perfusion | phone | no | no |  | perfusion index per ROI and channel (protocol 6.5) [prox_middle__B] |
| perfusion__phone__prox_middle__G | perfusion | phone | no | no |  | perfusion index per ROI and channel (protocol 6.5) [prox_middle__G] |
| perfusion__phone__prox_middle__R | perfusion | phone | no | no |  | perfusion index per ROI and channel (protocol 6.5) [prox_middle__R] |
| perfusion__phone__prox_ring__B | perfusion | phone | no | no |  | perfusion index per ROI and channel (protocol 6.5) [prox_ring__B] |
| perfusion__phone__prox_ring__G | perfusion | phone | no | no |  | perfusion index per ROI and channel (protocol 6.5) [prox_ring__G] |
| perfusion__phone__prox_ring__R | perfusion | phone | no | no |  | perfusion index per ROI and channel (protocol 6.5) [prox_ring__R] |
| perfusion__phone__thenar__B | perfusion | phone | no | no |  | perfusion index per ROI and channel (protocol 6.5) [thenar__B] |
| perfusion__phone__thenar__G | perfusion | phone | no | no |  | perfusion index per ROI and channel (protocol 6.5) [thenar__G] |
| perfusion__phone__thenar__R | perfusion | phone | no | no |  | perfusion index per ROI and channel (protocol 6.5) [thenar__R] |
| perfusion__phone__volar_wrist__B | perfusion | phone | no | no |  | perfusion index per ROI and channel (protocol 6.5) [volar_wrist__B] |
| perfusion__phone__volar_wrist__G | perfusion | phone | no | no |  | perfusion index per ROI and channel (protocol 6.5) [volar_wrist__G] |
| perfusion__phone__volar_wrist__R | perfusion | phone | no | no |  | perfusion index per ROI and channel (protocol 6.5) [volar_wrist__R] |
| perfusion__phone__whole_palm__B | perfusion | phone | no | no |  | perfusion index per ROI and channel (protocol 6.5) [whole_palm__B] |
| perfusion__phone__whole_palm__G | perfusion | phone | no | no |  | perfusion index per ROI and channel (protocol 6.5) [whole_palm__G] |
| perfusion__phone__whole_palm__R | perfusion | phone | no | no |  | perfusion index per ROI and channel (protocol 6.5) [whole_palm__R] |
| perfusion__pi__central_palm__B | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [central_palm__B] |
| perfusion__pi__central_palm__G1 | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [central_palm__G1] |
| perfusion__pi__central_palm__G2 | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [central_palm__G2] |
| perfusion__pi__central_palm__R | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [central_palm__R] |
| perfusion__pi__hypothenar__B | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [hypothenar__B] |
| perfusion__pi__hypothenar__G1 | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [hypothenar__G1] |
| perfusion__pi__hypothenar__G2 | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [hypothenar__G2] |
| perfusion__pi__hypothenar__R | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [hypothenar__R] |
| perfusion__pi__mid_phalanges__B | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [mid_phalanges__B] |
| perfusion__pi__mid_phalanges__G1 | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [mid_phalanges__G1] |
| perfusion__pi__mid_phalanges__G2 | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [mid_phalanges__G2] |
| perfusion__pi__mid_phalanges__R | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [mid_phalanges__R] |
| perfusion__pi__pad_index__B | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [pad_index__B] |
| perfusion__pi__pad_index__G1 | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [pad_index__G1] |
| perfusion__pi__pad_index__G2 | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [pad_index__G2] |
| perfusion__pi__pad_index__R | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [pad_index__R] |
| perfusion__pi__pad_little__B | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [pad_little__B] |
| perfusion__pi__pad_little__G1 | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [pad_little__G1] |
| perfusion__pi__pad_little__G2 | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [pad_little__G2] |
| perfusion__pi__pad_little__R | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [pad_little__R] |
| perfusion__pi__pad_middle__B | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [pad_middle__B] |
| perfusion__pi__pad_middle__G1 | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [pad_middle__G1] |
| perfusion__pi__pad_middle__G2 | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [pad_middle__G2] |
| perfusion__pi__pad_middle__R | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [pad_middle__R] |
| perfusion__pi__pad_ring__B | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [pad_ring__B] |
| perfusion__pi__pad_ring__G1 | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [pad_ring__G1] |
| perfusion__pi__pad_ring__G2 | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [pad_ring__G2] |
| perfusion__pi__pad_ring__R | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [pad_ring__R] |
| perfusion__pi__prox_index__B | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [prox_index__B] |
| perfusion__pi__prox_index__G1 | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [prox_index__G1] |
| perfusion__pi__prox_index__G2 | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [prox_index__G2] |
| perfusion__pi__prox_index__R | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [prox_index__R] |
| perfusion__pi__prox_little__B | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [prox_little__B] |
| perfusion__pi__prox_little__G1 | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [prox_little__G1] |
| perfusion__pi__prox_little__G2 | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [prox_little__G2] |
| perfusion__pi__prox_little__R | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [prox_little__R] |
| perfusion__pi__prox_middle__B | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [prox_middle__B] |
| perfusion__pi__prox_middle__G1 | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [prox_middle__G1] |
| perfusion__pi__prox_middle__G2 | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [prox_middle__G2] |
| perfusion__pi__prox_middle__R | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [prox_middle__R] |
| perfusion__pi__prox_ring__B | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [prox_ring__B] |
| perfusion__pi__prox_ring__G1 | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [prox_ring__G1] |
| perfusion__pi__prox_ring__G2 | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [prox_ring__G2] |
| perfusion__pi__prox_ring__R | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [prox_ring__R] |
| perfusion__pi__thenar__B | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [thenar__B] |
| perfusion__pi__thenar__G1 | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [thenar__G1] |
| perfusion__pi__thenar__G2 | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [thenar__G2] |
| perfusion__pi__thenar__R | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [thenar__R] |
| perfusion__pi__volar_wrist__B | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [volar_wrist__B] |
| perfusion__pi__volar_wrist__G1 | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [volar_wrist__G1] |
| perfusion__pi__volar_wrist__G2 | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [volar_wrist__G2] |
| perfusion__pi__volar_wrist__R | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [volar_wrist__R] |
| perfusion__pi__whole_palm__B | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [whole_palm__B] |
| perfusion__pi__whole_palm__G1 | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [whole_palm__G1] |
| perfusion__pi__whole_palm__G2 | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [whole_palm__G2] |
| perfusion__pi__whole_palm__R | perfusion | pi | no | yes |  | perfusion index per ROI and channel (protocol 6.5) [whole_palm__R] |
| perfusion__pi_proxy__central_palm__B | perfusion | pi_proxy | no | no |  | perfusion index per ROI and channel (protocol 6.5) [central_palm__B] |
| perfusion__pi_proxy__central_palm__G | perfusion | pi_proxy | no | no |  | perfusion index per ROI and channel (protocol 6.5) [central_palm__G] |
| perfusion__pi_proxy__central_palm__R | perfusion | pi_proxy | no | no |  | perfusion index per ROI and channel (protocol 6.5) [central_palm__R] |
| perfusion__pi_proxy__hypothenar__B | perfusion | pi_proxy | no | no |  | perfusion index per ROI and channel (protocol 6.5) [hypothenar__B] |
| perfusion__pi_proxy__hypothenar__G | perfusion | pi_proxy | no | no |  | perfusion index per ROI and channel (protocol 6.5) [hypothenar__G] |
| perfusion__pi_proxy__hypothenar__R | perfusion | pi_proxy | no | no |  | perfusion index per ROI and channel (protocol 6.5) [hypothenar__R] |
| perfusion__pi_proxy__mid_phalanges__B | perfusion | pi_proxy | no | no |  | perfusion index per ROI and channel (protocol 6.5) [mid_phalanges__B] |
| perfusion__pi_proxy__mid_phalanges__G | perfusion | pi_proxy | no | no |  | perfusion index per ROI and channel (protocol 6.5) [mid_phalanges__G] |
| perfusion__pi_proxy__mid_phalanges__R | perfusion | pi_proxy | no | no |  | perfusion index per ROI and channel (protocol 6.5) [mid_phalanges__R] |
| perfusion__pi_proxy__pad_index__B | perfusion | pi_proxy | no | no |  | perfusion index per ROI and channel (protocol 6.5) [pad_index__B] |
| perfusion__pi_proxy__pad_index__G | perfusion | pi_proxy | no | no |  | perfusion index per ROI and channel (protocol 6.5) [pad_index__G] |
| perfusion__pi_proxy__pad_index__R | perfusion | pi_proxy | no | no |  | perfusion index per ROI and channel (protocol 6.5) [pad_index__R] |
| perfusion__pi_proxy__pad_little__B | perfusion | pi_proxy | no | no |  | perfusion index per ROI and channel (protocol 6.5) [pad_little__B] |
| perfusion__pi_proxy__pad_little__G | perfusion | pi_proxy | no | no |  | perfusion index per ROI and channel (protocol 6.5) [pad_little__G] |
| perfusion__pi_proxy__pad_little__R | perfusion | pi_proxy | no | no |  | perfusion index per ROI and channel (protocol 6.5) [pad_little__R] |
| perfusion__pi_proxy__pad_middle__B | perfusion | pi_proxy | no | no |  | perfusion index per ROI and channel (protocol 6.5) [pad_middle__B] |
| perfusion__pi_proxy__pad_middle__G | perfusion | pi_proxy | no | no |  | perfusion index per ROI and channel (protocol 6.5) [pad_middle__G] |
| perfusion__pi_proxy__pad_middle__R | perfusion | pi_proxy | no | no |  | perfusion index per ROI and channel (protocol 6.5) [pad_middle__R] |
| perfusion__pi_proxy__pad_ring__B | perfusion | pi_proxy | no | no |  | perfusion index per ROI and channel (protocol 6.5) [pad_ring__B] |
| perfusion__pi_proxy__pad_ring__G | perfusion | pi_proxy | no | no |  | perfusion index per ROI and channel (protocol 6.5) [pad_ring__G] |
| perfusion__pi_proxy__pad_ring__R | perfusion | pi_proxy | no | no |  | perfusion index per ROI and channel (protocol 6.5) [pad_ring__R] |
| perfusion__pi_proxy__prox_index__B | perfusion | pi_proxy | no | no |  | perfusion index per ROI and channel (protocol 6.5) [prox_index__B] |
| perfusion__pi_proxy__prox_index__G | perfusion | pi_proxy | no | no |  | perfusion index per ROI and channel (protocol 6.5) [prox_index__G] |
| perfusion__pi_proxy__prox_index__R | perfusion | pi_proxy | no | no |  | perfusion index per ROI and channel (protocol 6.5) [prox_index__R] |
| perfusion__pi_proxy__prox_little__B | perfusion | pi_proxy | no | no |  | perfusion index per ROI and channel (protocol 6.5) [prox_little__B] |
| perfusion__pi_proxy__prox_little__G | perfusion | pi_proxy | no | no |  | perfusion index per ROI and channel (protocol 6.5) [prox_little__G] |
| perfusion__pi_proxy__prox_little__R | perfusion | pi_proxy | no | no |  | perfusion index per ROI and channel (protocol 6.5) [prox_little__R] |
| perfusion__pi_proxy__prox_middle__B | perfusion | pi_proxy | no | no |  | perfusion index per ROI and channel (protocol 6.5) [prox_middle__B] |
| perfusion__pi_proxy__prox_middle__G | perfusion | pi_proxy | no | no |  | perfusion index per ROI and channel (protocol 6.5) [prox_middle__G] |
| perfusion__pi_proxy__prox_middle__R | perfusion | pi_proxy | no | no |  | perfusion index per ROI and channel (protocol 6.5) [prox_middle__R] |
| perfusion__pi_proxy__prox_ring__B | perfusion | pi_proxy | no | no |  | perfusion index per ROI and channel (protocol 6.5) [prox_ring__B] |
| perfusion__pi_proxy__prox_ring__G | perfusion | pi_proxy | no | no |  | perfusion index per ROI and channel (protocol 6.5) [prox_ring__G] |
| perfusion__pi_proxy__prox_ring__R | perfusion | pi_proxy | no | no |  | perfusion index per ROI and channel (protocol 6.5) [prox_ring__R] |
| perfusion__pi_proxy__thenar__B | perfusion | pi_proxy | no | no |  | perfusion index per ROI and channel (protocol 6.5) [thenar__B] |
| perfusion__pi_proxy__thenar__G | perfusion | pi_proxy | no | no |  | perfusion index per ROI and channel (protocol 6.5) [thenar__G] |
| perfusion__pi_proxy__thenar__R | perfusion | pi_proxy | no | no |  | perfusion index per ROI and channel (protocol 6.5) [thenar__R] |
| perfusion__pi_proxy__volar_wrist__B | perfusion | pi_proxy | no | no |  | perfusion index per ROI and channel (protocol 6.5) [volar_wrist__B] |
| perfusion__pi_proxy__volar_wrist__G | perfusion | pi_proxy | no | no |  | perfusion index per ROI and channel (protocol 6.5) [volar_wrist__G] |
| perfusion__pi_proxy__volar_wrist__R | perfusion | pi_proxy | no | no |  | perfusion index per ROI and channel (protocol 6.5) [volar_wrist__R] |
| perfusion__pi_proxy__whole_palm__B | perfusion | pi_proxy | no | no |  | perfusion index per ROI and channel (protocol 6.5) [whole_palm__B] |
| perfusion__pi_proxy__whole_palm__G | perfusion | pi_proxy | no | no |  | perfusion index per ROI and channel (protocol 6.5) [whole_palm__G] |
| perfusion__pi_proxy__whole_palm__R | perfusion | pi_proxy | no | no |  | perfusion index per ROI and channel (protocol 6.5) [whole_palm__R] |
| pulse__phone__best | pulse | phone | no | no | label | best method__roi by SQI |
| pulse__phone__best__hr_bpm | pulse | phone | no | no | bpm | pulse extraction summary per method and ROI (protocol 6.3) [best__hr_bpm]: pulse rate of the dominant spectral peak |
| pulse__phone__best__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [best__kurtosis] |
| pulse__phone__best__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [best__n_windows]: count |
| pulse__phone__best__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [best__skewness] |
| pulse__phone__best__snr_db | pulse | phone | no | no | dB | pulse extraction summary per method and ROI (protocol 6.3) [best__snr_db]: SNR of the dominant band peak versus the rest of the band |
| pulse__phone__best__sqi | pulse | phone | no | no | 0..1 | pulse extraction summary per method and ROI (protocol 6.3) [best__sqi]: signal quality index (snr_band, CONTRACTS section 6) |
| pulse__phone__best__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [best__template_corr] |
| pulse__phone__central_palm__2SR__hr_bpm | pulse | phone | no | no | bpm | 2SR on central_palm: hr_bpm (section 6.3) |
| pulse__phone__central_palm__2SR__snr_db | pulse | phone | no | no | dB | 2SR on central_palm: snr_db (section 6.3) |
| pulse__phone__central_palm__2SR__sqi | pulse | phone | no | no | 0..1 | 2SR on central_palm: sqi (section 6.3) |
| pulse__phone__central_palm__CHROM__hr_bpm | pulse | phone | no | no | bpm | CHROM on central_palm: hr_bpm (section 6.3) |
| pulse__phone__central_palm__CHROM__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__CHROM__kurtosis] |
| pulse__phone__central_palm__CHROM__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__CHROM__n_windows]: count |
| pulse__phone__central_palm__CHROM__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__CHROM__skewness] |
| pulse__phone__central_palm__CHROM__snr_db | pulse | phone | no | no | dB | CHROM on central_palm: snr_db (section 6.3) |
| pulse__phone__central_palm__CHROM__sqi | pulse | phone | no | no | 0..1 | CHROM on central_palm: sqi (section 6.3) |
| pulse__phone__central_palm__CHROM__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__CHROM__template_corr] |
| pulse__phone__central_palm__GREEN__hr_bpm | pulse | phone | no | no | bpm | GREEN on central_palm: hr_bpm (section 6.3) |
| pulse__phone__central_palm__GREEN__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__GREEN__kurtosis] |
| pulse__phone__central_palm__GREEN__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__GREEN__n_windows]: count |
| pulse__phone__central_palm__GREEN__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__GREEN__skewness] |
| pulse__phone__central_palm__GREEN__snr_db | pulse | phone | no | no | dB | GREEN on central_palm: snr_db (section 6.3) |
| pulse__phone__central_palm__GREEN__sqi | pulse | phone | no | no | 0..1 | GREEN on central_palm: sqi (section 6.3) |
| pulse__phone__central_palm__GREEN__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__GREEN__template_corr] |
| pulse__phone__central_palm__ICA__hr_bpm | pulse | phone | no | no | bpm | ICA on central_palm: hr_bpm (section 6.3) |
| pulse__phone__central_palm__ICA__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__ICA__kurtosis] |
| pulse__phone__central_palm__ICA__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__ICA__n_windows]: count |
| pulse__phone__central_palm__ICA__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__ICA__skewness] |
| pulse__phone__central_palm__ICA__snr_db | pulse | phone | no | no | dB | ICA on central_palm: snr_db (section 6.3) |
| pulse__phone__central_palm__ICA__sqi | pulse | phone | no | no | 0..1 | ICA on central_palm: sqi (section 6.3) |
| pulse__phone__central_palm__ICA__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__ICA__template_corr] |
| pulse__phone__central_palm__LGI__hr_bpm | pulse | phone | no | no | bpm | LGI on central_palm: hr_bpm (section 6.3) |
| pulse__phone__central_palm__LGI__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__LGI__kurtosis] |
| pulse__phone__central_palm__LGI__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__LGI__n_windows]: count |
| pulse__phone__central_palm__LGI__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__LGI__skewness] |
| pulse__phone__central_palm__LGI__snr_db | pulse | phone | no | no | dB | LGI on central_palm: snr_db (section 6.3) |
| pulse__phone__central_palm__LGI__sqi | pulse | phone | no | no | 0..1 | LGI on central_palm: sqi (section 6.3) |
| pulse__phone__central_palm__LGI__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__LGI__template_corr] |
| pulse__phone__central_palm__OMIT__hr_bpm | pulse | phone | no | no | bpm | OMIT on central_palm: hr_bpm (section 6.3) |
| pulse__phone__central_palm__OMIT__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__OMIT__kurtosis] |
| pulse__phone__central_palm__OMIT__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__OMIT__n_windows]: count |
| pulse__phone__central_palm__OMIT__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__OMIT__skewness] |
| pulse__phone__central_palm__OMIT__snr_db | pulse | phone | no | no | dB | OMIT on central_palm: snr_db (section 6.3) |
| pulse__phone__central_palm__OMIT__sqi | pulse | phone | no | no | 0..1 | OMIT on central_palm: sqi (section 6.3) |
| pulse__phone__central_palm__OMIT__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__OMIT__template_corr] |
| pulse__phone__central_palm__PBV__hr_bpm | pulse | phone | no | no | bpm | PBV on central_palm: hr_bpm (section 6.3) |
| pulse__phone__central_palm__PBV__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__PBV__kurtosis] |
| pulse__phone__central_palm__PBV__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__PBV__n_windows]: count |
| pulse__phone__central_palm__PBV__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__PBV__skewness] |
| pulse__phone__central_palm__PBV__snr_db | pulse | phone | no | no | dB | PBV on central_palm: snr_db (section 6.3) |
| pulse__phone__central_palm__PBV__sqi | pulse | phone | no | no | 0..1 | PBV on central_palm: sqi (section 6.3) |
| pulse__phone__central_palm__PBV__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__PBV__template_corr] |
| pulse__phone__central_palm__PCA__hr_bpm | pulse | phone | no | no | bpm | PCA on central_palm: hr_bpm (section 6.3) |
| pulse__phone__central_palm__PCA__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__PCA__kurtosis] |
| pulse__phone__central_palm__PCA__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__PCA__n_windows]: count |
| pulse__phone__central_palm__PCA__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__PCA__skewness] |
| pulse__phone__central_palm__PCA__snr_db | pulse | phone | no | no | dB | PCA on central_palm: snr_db (section 6.3) |
| pulse__phone__central_palm__PCA__sqi | pulse | phone | no | no | 0..1 | PCA on central_palm: sqi (section 6.3) |
| pulse__phone__central_palm__PCA__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__PCA__template_corr] |
| pulse__phone__central_palm__POS__hr_bpm | pulse | phone | no | no | bpm | POS on central_palm: hr_bpm (section 6.3) |
| pulse__phone__central_palm__POS__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__POS__kurtosis] |
| pulse__phone__central_palm__POS__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__POS__n_windows]: count |
| pulse__phone__central_palm__POS__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__POS__skewness] |
| pulse__phone__central_palm__POS__snr_db | pulse | phone | no | no | dB | POS on central_palm: snr_db (section 6.3) |
| pulse__phone__central_palm__POS__sqi | pulse | phone | no | no | 0..1 | POS on central_palm: sqi (section 6.3) |
| pulse__phone__central_palm__POS__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__POS__template_corr] |
| pulse__phone__fused__2SR__hr_bpm | pulse | phone | no | no | bpm | 2SR on fused: hr_bpm (section 6.3) |
| pulse__phone__fused__2SR__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__2SR__kurtosis] |
| pulse__phone__fused__2SR__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [fused__2SR__n_windows]: count |
| pulse__phone__fused__2SR__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__2SR__skewness] |
| pulse__phone__fused__2SR__snr_db | pulse | phone | no | no | dB | 2SR on fused: snr_db (section 6.3) |
| pulse__phone__fused__2SR__sqi | pulse | phone | no | no | 0..1 | 2SR on fused: sqi (section 6.3) |
| pulse__phone__fused__2SR__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__2SR__template_corr] |
| pulse__phone__fused__CHROM__hr_bpm | pulse | phone | no | no | bpm | CHROM on fused: hr_bpm (section 6.3) |
| pulse__phone__fused__CHROM__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__CHROM__kurtosis] |
| pulse__phone__fused__CHROM__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [fused__CHROM__n_windows]: count |
| pulse__phone__fused__CHROM__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__CHROM__skewness] |
| pulse__phone__fused__CHROM__snr_db | pulse | phone | no | no | dB | CHROM on fused: snr_db (section 6.3) |
| pulse__phone__fused__CHROM__sqi | pulse | phone | no | no | 0..1 | CHROM on fused: sqi (section 6.3) |
| pulse__phone__fused__CHROM__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__CHROM__template_corr] |
| pulse__phone__fused__GREEN__hr_bpm | pulse | phone | no | no | bpm | GREEN on fused: hr_bpm (section 6.3) |
| pulse__phone__fused__GREEN__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__GREEN__kurtosis] |
| pulse__phone__fused__GREEN__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [fused__GREEN__n_windows]: count |
| pulse__phone__fused__GREEN__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__GREEN__skewness] |
| pulse__phone__fused__GREEN__snr_db | pulse | phone | no | no | dB | GREEN on fused: snr_db (section 6.3) |
| pulse__phone__fused__GREEN__sqi | pulse | phone | no | no | 0..1 | GREEN on fused: sqi (section 6.3) |
| pulse__phone__fused__GREEN__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__GREEN__template_corr] |
| pulse__phone__fused__ICA__hr_bpm | pulse | phone | no | no | bpm | ICA on fused: hr_bpm (section 6.3) |
| pulse__phone__fused__ICA__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__ICA__kurtosis] |
| pulse__phone__fused__ICA__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [fused__ICA__n_windows]: count |
| pulse__phone__fused__ICA__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__ICA__skewness] |
| pulse__phone__fused__ICA__snr_db | pulse | phone | no | no | dB | ICA on fused: snr_db (section 6.3) |
| pulse__phone__fused__ICA__sqi | pulse | phone | no | no | 0..1 | ICA on fused: sqi (section 6.3) |
| pulse__phone__fused__ICA__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__ICA__template_corr] |
| pulse__phone__fused__LGI__hr_bpm | pulse | phone | no | no | bpm | LGI on fused: hr_bpm (section 6.3) |
| pulse__phone__fused__LGI__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__LGI__kurtosis] |
| pulse__phone__fused__LGI__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [fused__LGI__n_windows]: count |
| pulse__phone__fused__LGI__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__LGI__skewness] |
| pulse__phone__fused__LGI__snr_db | pulse | phone | no | no | dB | LGI on fused: snr_db (section 6.3) |
| pulse__phone__fused__LGI__sqi | pulse | phone | no | no | 0..1 | LGI on fused: sqi (section 6.3) |
| pulse__phone__fused__LGI__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__LGI__template_corr] |
| pulse__phone__fused__OMIT__hr_bpm | pulse | phone | no | no | bpm | OMIT on fused: hr_bpm (section 6.3) |
| pulse__phone__fused__OMIT__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__OMIT__kurtosis] |
| pulse__phone__fused__OMIT__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [fused__OMIT__n_windows]: count |
| pulse__phone__fused__OMIT__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__OMIT__skewness] |
| pulse__phone__fused__OMIT__snr_db | pulse | phone | no | no | dB | OMIT on fused: snr_db (section 6.3) |
| pulse__phone__fused__OMIT__sqi | pulse | phone | no | no | 0..1 | OMIT on fused: sqi (section 6.3) |
| pulse__phone__fused__OMIT__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__OMIT__template_corr] |
| pulse__phone__fused__PBV__hr_bpm | pulse | phone | no | no | bpm | PBV on fused: hr_bpm (section 6.3) |
| pulse__phone__fused__PBV__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__PBV__kurtosis] |
| pulse__phone__fused__PBV__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [fused__PBV__n_windows]: count |
| pulse__phone__fused__PBV__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__PBV__skewness] |
| pulse__phone__fused__PBV__snr_db | pulse | phone | no | no | dB | PBV on fused: snr_db (section 6.3) |
| pulse__phone__fused__PBV__sqi | pulse | phone | no | no | 0..1 | PBV on fused: sqi (section 6.3) |
| pulse__phone__fused__PBV__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__PBV__template_corr] |
| pulse__phone__fused__PCA__hr_bpm | pulse | phone | no | no | bpm | PCA on fused: hr_bpm (section 6.3) |
| pulse__phone__fused__PCA__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__PCA__kurtosis] |
| pulse__phone__fused__PCA__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [fused__PCA__n_windows]: count |
| pulse__phone__fused__PCA__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__PCA__skewness] |
| pulse__phone__fused__PCA__snr_db | pulse | phone | no | no | dB | PCA on fused: snr_db (section 6.3) |
| pulse__phone__fused__PCA__sqi | pulse | phone | no | no | 0..1 | PCA on fused: sqi (section 6.3) |
| pulse__phone__fused__PCA__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__PCA__template_corr] |
| pulse__phone__fused__POS__hr_bpm | pulse | phone | no | no | bpm | POS on fused: hr_bpm (section 6.3) |
| pulse__phone__fused__POS__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__POS__kurtosis] |
| pulse__phone__fused__POS__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [fused__POS__n_windows]: count |
| pulse__phone__fused__POS__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__POS__skewness] |
| pulse__phone__fused__POS__snr_db | pulse | phone | no | no | dB | POS on fused: snr_db (section 6.3) |
| pulse__phone__fused__POS__sqi | pulse | phone | no | no | 0..1 | POS on fused: sqi (section 6.3) |
| pulse__phone__fused__POS__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__POS__template_corr] |
| pulse__phone__fused__hr_bpm | pulse | phone | no | no | bpm | pulse extraction summary per method and ROI (protocol 6.3) [fused__hr_bpm]: pulse rate of the dominant spectral peak |
| pulse__phone__fused__method | pulse | phone | no | no | label | pulse extraction summary per method and ROI (protocol 6.3) [fused__method]: method name |
| pulse__phone__fused__snr_db | pulse | phone | no | no | dB | pulse extraction summary per method and ROI (protocol 6.3) [fused__snr_db]: SNR of the dominant band peak versus the rest of the band |
| pulse__phone__fused__sqi | pulse | phone | no | no | 0..1 | pulse extraction summary per method and ROI (protocol 6.3) [fused__sqi]: signal quality index (snr_band, CONTRACTS section 6) |
| pulse__phone__hypothenar__2SR__hr_bpm | pulse | phone | no | no | bpm | 2SR on hypothenar: hr_bpm (section 6.3) |
| pulse__phone__hypothenar__2SR__snr_db | pulse | phone | no | no | dB | 2SR on hypothenar: snr_db (section 6.3) |
| pulse__phone__hypothenar__2SR__sqi | pulse | phone | no | no | 0..1 | 2SR on hypothenar: sqi (section 6.3) |
| pulse__phone__hypothenar__CHROM__hr_bpm | pulse | phone | no | no | bpm | CHROM on hypothenar: hr_bpm (section 6.3) |
| pulse__phone__hypothenar__CHROM__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__CHROM__kurtosis] |
| pulse__phone__hypothenar__CHROM__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__CHROM__n_windows]: count |
| pulse__phone__hypothenar__CHROM__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__CHROM__skewness] |
| pulse__phone__hypothenar__CHROM__snr_db | pulse | phone | no | no | dB | CHROM on hypothenar: snr_db (section 6.3) |
| pulse__phone__hypothenar__CHROM__sqi | pulse | phone | no | no | 0..1 | CHROM on hypothenar: sqi (section 6.3) |
| pulse__phone__hypothenar__CHROM__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__CHROM__template_corr] |
| pulse__phone__hypothenar__GREEN__hr_bpm | pulse | phone | no | no | bpm | GREEN on hypothenar: hr_bpm (section 6.3) |
| pulse__phone__hypothenar__GREEN__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__GREEN__kurtosis] |
| pulse__phone__hypothenar__GREEN__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__GREEN__n_windows]: count |
| pulse__phone__hypothenar__GREEN__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__GREEN__skewness] |
| pulse__phone__hypothenar__GREEN__snr_db | pulse | phone | no | no | dB | GREEN on hypothenar: snr_db (section 6.3) |
| pulse__phone__hypothenar__GREEN__sqi | pulse | phone | no | no | 0..1 | GREEN on hypothenar: sqi (section 6.3) |
| pulse__phone__hypothenar__GREEN__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__GREEN__template_corr] |
| pulse__phone__hypothenar__ICA__hr_bpm | pulse | phone | no | no | bpm | ICA on hypothenar: hr_bpm (section 6.3) |
| pulse__phone__hypothenar__ICA__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__ICA__kurtosis] |
| pulse__phone__hypothenar__ICA__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__ICA__n_windows]: count |
| pulse__phone__hypothenar__ICA__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__ICA__skewness] |
| pulse__phone__hypothenar__ICA__snr_db | pulse | phone | no | no | dB | ICA on hypothenar: snr_db (section 6.3) |
| pulse__phone__hypothenar__ICA__sqi | pulse | phone | no | no | 0..1 | ICA on hypothenar: sqi (section 6.3) |
| pulse__phone__hypothenar__ICA__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__ICA__template_corr] |
| pulse__phone__hypothenar__LGI__hr_bpm | pulse | phone | no | no | bpm | LGI on hypothenar: hr_bpm (section 6.3) |
| pulse__phone__hypothenar__LGI__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__LGI__kurtosis] |
| pulse__phone__hypothenar__LGI__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__LGI__n_windows]: count |
| pulse__phone__hypothenar__LGI__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__LGI__skewness] |
| pulse__phone__hypothenar__LGI__snr_db | pulse | phone | no | no | dB | LGI on hypothenar: snr_db (section 6.3) |
| pulse__phone__hypothenar__LGI__sqi | pulse | phone | no | no | 0..1 | LGI on hypothenar: sqi (section 6.3) |
| pulse__phone__hypothenar__LGI__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__LGI__template_corr] |
| pulse__phone__hypothenar__OMIT__hr_bpm | pulse | phone | no | no | bpm | OMIT on hypothenar: hr_bpm (section 6.3) |
| pulse__phone__hypothenar__OMIT__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__OMIT__kurtosis] |
| pulse__phone__hypothenar__OMIT__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__OMIT__n_windows]: count |
| pulse__phone__hypothenar__OMIT__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__OMIT__skewness] |
| pulse__phone__hypothenar__OMIT__snr_db | pulse | phone | no | no | dB | OMIT on hypothenar: snr_db (section 6.3) |
| pulse__phone__hypothenar__OMIT__sqi | pulse | phone | no | no | 0..1 | OMIT on hypothenar: sqi (section 6.3) |
| pulse__phone__hypothenar__OMIT__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__OMIT__template_corr] |
| pulse__phone__hypothenar__PBV__hr_bpm | pulse | phone | no | no | bpm | PBV on hypothenar: hr_bpm (section 6.3) |
| pulse__phone__hypothenar__PBV__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__PBV__kurtosis] |
| pulse__phone__hypothenar__PBV__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__PBV__n_windows]: count |
| pulse__phone__hypothenar__PBV__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__PBV__skewness] |
| pulse__phone__hypothenar__PBV__snr_db | pulse | phone | no | no | dB | PBV on hypothenar: snr_db (section 6.3) |
| pulse__phone__hypothenar__PBV__sqi | pulse | phone | no | no | 0..1 | PBV on hypothenar: sqi (section 6.3) |
| pulse__phone__hypothenar__PBV__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__PBV__template_corr] |
| pulse__phone__hypothenar__PCA__hr_bpm | pulse | phone | no | no | bpm | PCA on hypothenar: hr_bpm (section 6.3) |
| pulse__phone__hypothenar__PCA__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__PCA__kurtosis] |
| pulse__phone__hypothenar__PCA__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__PCA__n_windows]: count |
| pulse__phone__hypothenar__PCA__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__PCA__skewness] |
| pulse__phone__hypothenar__PCA__snr_db | pulse | phone | no | no | dB | PCA on hypothenar: snr_db (section 6.3) |
| pulse__phone__hypothenar__PCA__sqi | pulse | phone | no | no | 0..1 | PCA on hypothenar: sqi (section 6.3) |
| pulse__phone__hypothenar__PCA__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__PCA__template_corr] |
| pulse__phone__hypothenar__POS__hr_bpm | pulse | phone | no | no | bpm | POS on hypothenar: hr_bpm (section 6.3) |
| pulse__phone__hypothenar__POS__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__POS__kurtosis] |
| pulse__phone__hypothenar__POS__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__POS__n_windows]: count |
| pulse__phone__hypothenar__POS__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__POS__skewness] |
| pulse__phone__hypothenar__POS__snr_db | pulse | phone | no | no | dB | POS on hypothenar: snr_db (section 6.3) |
| pulse__phone__hypothenar__POS__sqi | pulse | phone | no | no | 0..1 | POS on hypothenar: sqi (section 6.3) |
| pulse__phone__hypothenar__POS__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__POS__template_corr] |
| pulse__phone__mid_phalanges__2SR__hr_bpm | pulse | phone | no | no | bpm | 2SR on mid_phalanges: hr_bpm (section 6.3) |
| pulse__phone__mid_phalanges__2SR__snr_db | pulse | phone | no | no | dB | 2SR on mid_phalanges: snr_db (section 6.3) |
| pulse__phone__mid_phalanges__2SR__sqi | pulse | phone | no | no | 0..1 | 2SR on mid_phalanges: sqi (section 6.3) |
| pulse__phone__mid_phalanges__CHROM__hr_bpm | pulse | phone | no | no | bpm | CHROM on mid_phalanges: hr_bpm (section 6.3) |
| pulse__phone__mid_phalanges__CHROM__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__CHROM__kurtosis] |
| pulse__phone__mid_phalanges__CHROM__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__CHROM__n_windows]: count |
| pulse__phone__mid_phalanges__CHROM__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__CHROM__skewness] |
| pulse__phone__mid_phalanges__CHROM__snr_db | pulse | phone | no | no | dB | CHROM on mid_phalanges: snr_db (section 6.3) |
| pulse__phone__mid_phalanges__CHROM__sqi | pulse | phone | no | no | 0..1 | CHROM on mid_phalanges: sqi (section 6.3) |
| pulse__phone__mid_phalanges__CHROM__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__CHROM__template_corr] |
| pulse__phone__mid_phalanges__GREEN__hr_bpm | pulse | phone | no | no | bpm | GREEN on mid_phalanges: hr_bpm (section 6.3) |
| pulse__phone__mid_phalanges__GREEN__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__GREEN__kurtosis] |
| pulse__phone__mid_phalanges__GREEN__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__GREEN__n_windows]: count |
| pulse__phone__mid_phalanges__GREEN__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__GREEN__skewness] |
| pulse__phone__mid_phalanges__GREEN__snr_db | pulse | phone | no | no | dB | GREEN on mid_phalanges: snr_db (section 6.3) |
| pulse__phone__mid_phalanges__GREEN__sqi | pulse | phone | no | no | 0..1 | GREEN on mid_phalanges: sqi (section 6.3) |
| pulse__phone__mid_phalanges__GREEN__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__GREEN__template_corr] |
| pulse__phone__mid_phalanges__ICA__hr_bpm | pulse | phone | no | no | bpm | ICA on mid_phalanges: hr_bpm (section 6.3) |
| pulse__phone__mid_phalanges__ICA__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__ICA__kurtosis] |
| pulse__phone__mid_phalanges__ICA__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__ICA__n_windows]: count |
| pulse__phone__mid_phalanges__ICA__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__ICA__skewness] |
| pulse__phone__mid_phalanges__ICA__snr_db | pulse | phone | no | no | dB | ICA on mid_phalanges: snr_db (section 6.3) |
| pulse__phone__mid_phalanges__ICA__sqi | pulse | phone | no | no | 0..1 | ICA on mid_phalanges: sqi (section 6.3) |
| pulse__phone__mid_phalanges__ICA__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__ICA__template_corr] |
| pulse__phone__mid_phalanges__LGI__hr_bpm | pulse | phone | no | no | bpm | LGI on mid_phalanges: hr_bpm (section 6.3) |
| pulse__phone__mid_phalanges__LGI__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__LGI__kurtosis] |
| pulse__phone__mid_phalanges__LGI__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__LGI__n_windows]: count |
| pulse__phone__mid_phalanges__LGI__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__LGI__skewness] |
| pulse__phone__mid_phalanges__LGI__snr_db | pulse | phone | no | no | dB | LGI on mid_phalanges: snr_db (section 6.3) |
| pulse__phone__mid_phalanges__LGI__sqi | pulse | phone | no | no | 0..1 | LGI on mid_phalanges: sqi (section 6.3) |
| pulse__phone__mid_phalanges__LGI__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__LGI__template_corr] |
| pulse__phone__mid_phalanges__OMIT__hr_bpm | pulse | phone | no | no | bpm | OMIT on mid_phalanges: hr_bpm (section 6.3) |
| pulse__phone__mid_phalanges__OMIT__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__OMIT__kurtosis] |
| pulse__phone__mid_phalanges__OMIT__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__OMIT__n_windows]: count |
| pulse__phone__mid_phalanges__OMIT__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__OMIT__skewness] |
| pulse__phone__mid_phalanges__OMIT__snr_db | pulse | phone | no | no | dB | OMIT on mid_phalanges: snr_db (section 6.3) |
| pulse__phone__mid_phalanges__OMIT__sqi | pulse | phone | no | no | 0..1 | OMIT on mid_phalanges: sqi (section 6.3) |
| pulse__phone__mid_phalanges__OMIT__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__OMIT__template_corr] |
| pulse__phone__mid_phalanges__PBV__hr_bpm | pulse | phone | no | no | bpm | PBV on mid_phalanges: hr_bpm (section 6.3) |
| pulse__phone__mid_phalanges__PBV__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__PBV__kurtosis] |
| pulse__phone__mid_phalanges__PBV__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__PBV__n_windows]: count |
| pulse__phone__mid_phalanges__PBV__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__PBV__skewness] |
| pulse__phone__mid_phalanges__PBV__snr_db | pulse | phone | no | no | dB | PBV on mid_phalanges: snr_db (section 6.3) |
| pulse__phone__mid_phalanges__PBV__sqi | pulse | phone | no | no | 0..1 | PBV on mid_phalanges: sqi (section 6.3) |
| pulse__phone__mid_phalanges__PBV__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__PBV__template_corr] |
| pulse__phone__mid_phalanges__PCA__hr_bpm | pulse | phone | no | no | bpm | PCA on mid_phalanges: hr_bpm (section 6.3) |
| pulse__phone__mid_phalanges__PCA__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__PCA__kurtosis] |
| pulse__phone__mid_phalanges__PCA__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__PCA__n_windows]: count |
| pulse__phone__mid_phalanges__PCA__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__PCA__skewness] |
| pulse__phone__mid_phalanges__PCA__snr_db | pulse | phone | no | no | dB | PCA on mid_phalanges: snr_db (section 6.3) |
| pulse__phone__mid_phalanges__PCA__sqi | pulse | phone | no | no | 0..1 | PCA on mid_phalanges: sqi (section 6.3) |
| pulse__phone__mid_phalanges__PCA__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__PCA__template_corr] |
| pulse__phone__mid_phalanges__POS__hr_bpm | pulse | phone | no | no | bpm | POS on mid_phalanges: hr_bpm (section 6.3) |
| pulse__phone__mid_phalanges__POS__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__POS__kurtosis] |
| pulse__phone__mid_phalanges__POS__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__POS__n_windows]: count |
| pulse__phone__mid_phalanges__POS__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__POS__skewness] |
| pulse__phone__mid_phalanges__POS__snr_db | pulse | phone | no | no | dB | POS on mid_phalanges: snr_db (section 6.3) |
| pulse__phone__mid_phalanges__POS__sqi | pulse | phone | no | no | 0..1 | POS on mid_phalanges: sqi (section 6.3) |
| pulse__phone__mid_phalanges__POS__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__POS__template_corr] |
| pulse__phone__pad_index__2SR__hr_bpm | pulse | phone | no | no | bpm | 2SR on pad_index: hr_bpm (section 6.3) |
| pulse__phone__pad_index__2SR__snr_db | pulse | phone | no | no | dB | 2SR on pad_index: snr_db (section 6.3) |
| pulse__phone__pad_index__2SR__sqi | pulse | phone | no | no | 0..1 | 2SR on pad_index: sqi (section 6.3) |
| pulse__phone__pad_index__CHROM__hr_bpm | pulse | phone | no | no | bpm | CHROM on pad_index: hr_bpm (section 6.3) |
| pulse__phone__pad_index__CHROM__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__CHROM__kurtosis] |
| pulse__phone__pad_index__CHROM__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__CHROM__n_windows]: count |
| pulse__phone__pad_index__CHROM__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__CHROM__skewness] |
| pulse__phone__pad_index__CHROM__snr_db | pulse | phone | no | no | dB | CHROM on pad_index: snr_db (section 6.3) |
| pulse__phone__pad_index__CHROM__sqi | pulse | phone | no | no | 0..1 | CHROM on pad_index: sqi (section 6.3) |
| pulse__phone__pad_index__CHROM__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__CHROM__template_corr] |
| pulse__phone__pad_index__GREEN__hr_bpm | pulse | phone | no | no | bpm | GREEN on pad_index: hr_bpm (section 6.3) |
| pulse__phone__pad_index__GREEN__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__GREEN__kurtosis] |
| pulse__phone__pad_index__GREEN__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__GREEN__n_windows]: count |
| pulse__phone__pad_index__GREEN__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__GREEN__skewness] |
| pulse__phone__pad_index__GREEN__snr_db | pulse | phone | no | no | dB | GREEN on pad_index: snr_db (section 6.3) |
| pulse__phone__pad_index__GREEN__sqi | pulse | phone | no | no | 0..1 | GREEN on pad_index: sqi (section 6.3) |
| pulse__phone__pad_index__GREEN__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__GREEN__template_corr] |
| pulse__phone__pad_index__ICA__hr_bpm | pulse | phone | no | no | bpm | ICA on pad_index: hr_bpm (section 6.3) |
| pulse__phone__pad_index__ICA__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__ICA__kurtosis] |
| pulse__phone__pad_index__ICA__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__ICA__n_windows]: count |
| pulse__phone__pad_index__ICA__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__ICA__skewness] |
| pulse__phone__pad_index__ICA__snr_db | pulse | phone | no | no | dB | ICA on pad_index: snr_db (section 6.3) |
| pulse__phone__pad_index__ICA__sqi | pulse | phone | no | no | 0..1 | ICA on pad_index: sqi (section 6.3) |
| pulse__phone__pad_index__ICA__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__ICA__template_corr] |
| pulse__phone__pad_index__LGI__hr_bpm | pulse | phone | no | no | bpm | LGI on pad_index: hr_bpm (section 6.3) |
| pulse__phone__pad_index__LGI__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__LGI__kurtosis] |
| pulse__phone__pad_index__LGI__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__LGI__n_windows]: count |
| pulse__phone__pad_index__LGI__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__LGI__skewness] |
| pulse__phone__pad_index__LGI__snr_db | pulse | phone | no | no | dB | LGI on pad_index: snr_db (section 6.3) |
| pulse__phone__pad_index__LGI__sqi | pulse | phone | no | no | 0..1 | LGI on pad_index: sqi (section 6.3) |
| pulse__phone__pad_index__LGI__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__LGI__template_corr] |
| pulse__phone__pad_index__OMIT__hr_bpm | pulse | phone | no | no | bpm | OMIT on pad_index: hr_bpm (section 6.3) |
| pulse__phone__pad_index__OMIT__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__OMIT__kurtosis] |
| pulse__phone__pad_index__OMIT__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__OMIT__n_windows]: count |
| pulse__phone__pad_index__OMIT__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__OMIT__skewness] |
| pulse__phone__pad_index__OMIT__snr_db | pulse | phone | no | no | dB | OMIT on pad_index: snr_db (section 6.3) |
| pulse__phone__pad_index__OMIT__sqi | pulse | phone | no | no | 0..1 | OMIT on pad_index: sqi (section 6.3) |
| pulse__phone__pad_index__OMIT__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__OMIT__template_corr] |
| pulse__phone__pad_index__PBV__hr_bpm | pulse | phone | no | no | bpm | PBV on pad_index: hr_bpm (section 6.3) |
| pulse__phone__pad_index__PBV__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__PBV__kurtosis] |
| pulse__phone__pad_index__PBV__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__PBV__n_windows]: count |
| pulse__phone__pad_index__PBV__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__PBV__skewness] |
| pulse__phone__pad_index__PBV__snr_db | pulse | phone | no | no | dB | PBV on pad_index: snr_db (section 6.3) |
| pulse__phone__pad_index__PBV__sqi | pulse | phone | no | no | 0..1 | PBV on pad_index: sqi (section 6.3) |
| pulse__phone__pad_index__PBV__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__PBV__template_corr] |
| pulse__phone__pad_index__PCA__hr_bpm | pulse | phone | no | no | bpm | PCA on pad_index: hr_bpm (section 6.3) |
| pulse__phone__pad_index__PCA__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__PCA__kurtosis] |
| pulse__phone__pad_index__PCA__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__PCA__n_windows]: count |
| pulse__phone__pad_index__PCA__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__PCA__skewness] |
| pulse__phone__pad_index__PCA__snr_db | pulse | phone | no | no | dB | PCA on pad_index: snr_db (section 6.3) |
| pulse__phone__pad_index__PCA__sqi | pulse | phone | no | no | 0..1 | PCA on pad_index: sqi (section 6.3) |
| pulse__phone__pad_index__PCA__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__PCA__template_corr] |
| pulse__phone__pad_index__POS__hr_bpm | pulse | phone | no | no | bpm | POS on pad_index: hr_bpm (section 6.3) |
| pulse__phone__pad_index__POS__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__POS__kurtosis] |
| pulse__phone__pad_index__POS__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__POS__n_windows]: count |
| pulse__phone__pad_index__POS__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__POS__skewness] |
| pulse__phone__pad_index__POS__snr_db | pulse | phone | no | no | dB | POS on pad_index: snr_db (section 6.3) |
| pulse__phone__pad_index__POS__sqi | pulse | phone | no | no | 0..1 | POS on pad_index: sqi (section 6.3) |
| pulse__phone__pad_index__POS__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__POS__template_corr] |
| pulse__phone__pad_little__2SR__hr_bpm | pulse | phone | no | no | bpm | 2SR on pad_little: hr_bpm (section 6.3) |
| pulse__phone__pad_little__2SR__snr_db | pulse | phone | no | no | dB | 2SR on pad_little: snr_db (section 6.3) |
| pulse__phone__pad_little__2SR__sqi | pulse | phone | no | no | 0..1 | 2SR on pad_little: sqi (section 6.3) |
| pulse__phone__pad_little__CHROM__hr_bpm | pulse | phone | no | no | bpm | CHROM on pad_little: hr_bpm (section 6.3) |
| pulse__phone__pad_little__CHROM__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__CHROM__kurtosis] |
| pulse__phone__pad_little__CHROM__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__CHROM__n_windows]: count |
| pulse__phone__pad_little__CHROM__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__CHROM__skewness] |
| pulse__phone__pad_little__CHROM__snr_db | pulse | phone | no | no | dB | CHROM on pad_little: snr_db (section 6.3) |
| pulse__phone__pad_little__CHROM__sqi | pulse | phone | no | no | 0..1 | CHROM on pad_little: sqi (section 6.3) |
| pulse__phone__pad_little__CHROM__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__CHROM__template_corr] |
| pulse__phone__pad_little__GREEN__hr_bpm | pulse | phone | no | no | bpm | GREEN on pad_little: hr_bpm (section 6.3) |
| pulse__phone__pad_little__GREEN__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__GREEN__kurtosis] |
| pulse__phone__pad_little__GREEN__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__GREEN__n_windows]: count |
| pulse__phone__pad_little__GREEN__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__GREEN__skewness] |
| pulse__phone__pad_little__GREEN__snr_db | pulse | phone | no | no | dB | GREEN on pad_little: snr_db (section 6.3) |
| pulse__phone__pad_little__GREEN__sqi | pulse | phone | no | no | 0..1 | GREEN on pad_little: sqi (section 6.3) |
| pulse__phone__pad_little__GREEN__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__GREEN__template_corr] |
| pulse__phone__pad_little__ICA__hr_bpm | pulse | phone | no | no | bpm | ICA on pad_little: hr_bpm (section 6.3) |
| pulse__phone__pad_little__ICA__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__ICA__kurtosis] |
| pulse__phone__pad_little__ICA__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__ICA__n_windows]: count |
| pulse__phone__pad_little__ICA__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__ICA__skewness] |
| pulse__phone__pad_little__ICA__snr_db | pulse | phone | no | no | dB | ICA on pad_little: snr_db (section 6.3) |
| pulse__phone__pad_little__ICA__sqi | pulse | phone | no | no | 0..1 | ICA on pad_little: sqi (section 6.3) |
| pulse__phone__pad_little__ICA__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__ICA__template_corr] |
| pulse__phone__pad_little__LGI__hr_bpm | pulse | phone | no | no | bpm | LGI on pad_little: hr_bpm (section 6.3) |
| pulse__phone__pad_little__LGI__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__LGI__kurtosis] |
| pulse__phone__pad_little__LGI__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__LGI__n_windows]: count |
| pulse__phone__pad_little__LGI__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__LGI__skewness] |
| pulse__phone__pad_little__LGI__snr_db | pulse | phone | no | no | dB | LGI on pad_little: snr_db (section 6.3) |
| pulse__phone__pad_little__LGI__sqi | pulse | phone | no | no | 0..1 | LGI on pad_little: sqi (section 6.3) |
| pulse__phone__pad_little__LGI__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__LGI__template_corr] |
| pulse__phone__pad_little__OMIT__hr_bpm | pulse | phone | no | no | bpm | OMIT on pad_little: hr_bpm (section 6.3) |
| pulse__phone__pad_little__OMIT__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__OMIT__kurtosis] |
| pulse__phone__pad_little__OMIT__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__OMIT__n_windows]: count |
| pulse__phone__pad_little__OMIT__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__OMIT__skewness] |
| pulse__phone__pad_little__OMIT__snr_db | pulse | phone | no | no | dB | OMIT on pad_little: snr_db (section 6.3) |
| pulse__phone__pad_little__OMIT__sqi | pulse | phone | no | no | 0..1 | OMIT on pad_little: sqi (section 6.3) |
| pulse__phone__pad_little__OMIT__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__OMIT__template_corr] |
| pulse__phone__pad_little__PBV__hr_bpm | pulse | phone | no | no | bpm | PBV on pad_little: hr_bpm (section 6.3) |
| pulse__phone__pad_little__PBV__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__PBV__kurtosis] |
| pulse__phone__pad_little__PBV__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__PBV__n_windows]: count |
| pulse__phone__pad_little__PBV__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__PBV__skewness] |
| pulse__phone__pad_little__PBV__snr_db | pulse | phone | no | no | dB | PBV on pad_little: snr_db (section 6.3) |
| pulse__phone__pad_little__PBV__sqi | pulse | phone | no | no | 0..1 | PBV on pad_little: sqi (section 6.3) |
| pulse__phone__pad_little__PBV__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__PBV__template_corr] |
| pulse__phone__pad_little__PCA__hr_bpm | pulse | phone | no | no | bpm | PCA on pad_little: hr_bpm (section 6.3) |
| pulse__phone__pad_little__PCA__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__PCA__kurtosis] |
| pulse__phone__pad_little__PCA__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__PCA__n_windows]: count |
| pulse__phone__pad_little__PCA__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__PCA__skewness] |
| pulse__phone__pad_little__PCA__snr_db | pulse | phone | no | no | dB | PCA on pad_little: snr_db (section 6.3) |
| pulse__phone__pad_little__PCA__sqi | pulse | phone | no | no | 0..1 | PCA on pad_little: sqi (section 6.3) |
| pulse__phone__pad_little__PCA__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__PCA__template_corr] |
| pulse__phone__pad_little__POS__hr_bpm | pulse | phone | no | no | bpm | POS on pad_little: hr_bpm (section 6.3) |
| pulse__phone__pad_little__POS__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__POS__kurtosis] |
| pulse__phone__pad_little__POS__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__POS__n_windows]: count |
| pulse__phone__pad_little__POS__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__POS__skewness] |
| pulse__phone__pad_little__POS__snr_db | pulse | phone | no | no | dB | POS on pad_little: snr_db (section 6.3) |
| pulse__phone__pad_little__POS__sqi | pulse | phone | no | no | 0..1 | POS on pad_little: sqi (section 6.3) |
| pulse__phone__pad_little__POS__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__POS__template_corr] |
| pulse__phone__pad_middle__2SR__hr_bpm | pulse | phone | no | no | bpm | 2SR on pad_middle: hr_bpm (section 6.3) |
| pulse__phone__pad_middle__2SR__snr_db | pulse | phone | no | no | dB | 2SR on pad_middle: snr_db (section 6.3) |
| pulse__phone__pad_middle__2SR__sqi | pulse | phone | no | no | 0..1 | 2SR on pad_middle: sqi (section 6.3) |
| pulse__phone__pad_middle__CHROM__hr_bpm | pulse | phone | no | no | bpm | CHROM on pad_middle: hr_bpm (section 6.3) |
| pulse__phone__pad_middle__CHROM__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__CHROM__kurtosis] |
| pulse__phone__pad_middle__CHROM__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__CHROM__n_windows]: count |
| pulse__phone__pad_middle__CHROM__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__CHROM__skewness] |
| pulse__phone__pad_middle__CHROM__snr_db | pulse | phone | no | no | dB | CHROM on pad_middle: snr_db (section 6.3) |
| pulse__phone__pad_middle__CHROM__sqi | pulse | phone | no | no | 0..1 | CHROM on pad_middle: sqi (section 6.3) |
| pulse__phone__pad_middle__CHROM__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__CHROM__template_corr] |
| pulse__phone__pad_middle__GREEN__hr_bpm | pulse | phone | no | no | bpm | GREEN on pad_middle: hr_bpm (section 6.3) |
| pulse__phone__pad_middle__GREEN__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__GREEN__kurtosis] |
| pulse__phone__pad_middle__GREEN__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__GREEN__n_windows]: count |
| pulse__phone__pad_middle__GREEN__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__GREEN__skewness] |
| pulse__phone__pad_middle__GREEN__snr_db | pulse | phone | no | no | dB | GREEN on pad_middle: snr_db (section 6.3) |
| pulse__phone__pad_middle__GREEN__sqi | pulse | phone | no | no | 0..1 | GREEN on pad_middle: sqi (section 6.3) |
| pulse__phone__pad_middle__GREEN__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__GREEN__template_corr] |
| pulse__phone__pad_middle__ICA__hr_bpm | pulse | phone | no | no | bpm | ICA on pad_middle: hr_bpm (section 6.3) |
| pulse__phone__pad_middle__ICA__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__ICA__kurtosis] |
| pulse__phone__pad_middle__ICA__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__ICA__n_windows]: count |
| pulse__phone__pad_middle__ICA__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__ICA__skewness] |
| pulse__phone__pad_middle__ICA__snr_db | pulse | phone | no | no | dB | ICA on pad_middle: snr_db (section 6.3) |
| pulse__phone__pad_middle__ICA__sqi | pulse | phone | no | no | 0..1 | ICA on pad_middle: sqi (section 6.3) |
| pulse__phone__pad_middle__ICA__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__ICA__template_corr] |
| pulse__phone__pad_middle__LGI__hr_bpm | pulse | phone | no | no | bpm | LGI on pad_middle: hr_bpm (section 6.3) |
| pulse__phone__pad_middle__LGI__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__LGI__kurtosis] |
| pulse__phone__pad_middle__LGI__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__LGI__n_windows]: count |
| pulse__phone__pad_middle__LGI__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__LGI__skewness] |
| pulse__phone__pad_middle__LGI__snr_db | pulse | phone | no | no | dB | LGI on pad_middle: snr_db (section 6.3) |
| pulse__phone__pad_middle__LGI__sqi | pulse | phone | no | no | 0..1 | LGI on pad_middle: sqi (section 6.3) |
| pulse__phone__pad_middle__LGI__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__LGI__template_corr] |
| pulse__phone__pad_middle__OMIT__hr_bpm | pulse | phone | no | no | bpm | OMIT on pad_middle: hr_bpm (section 6.3) |
| pulse__phone__pad_middle__OMIT__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__OMIT__kurtosis] |
| pulse__phone__pad_middle__OMIT__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__OMIT__n_windows]: count |
| pulse__phone__pad_middle__OMIT__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__OMIT__skewness] |
| pulse__phone__pad_middle__OMIT__snr_db | pulse | phone | no | no | dB | OMIT on pad_middle: snr_db (section 6.3) |
| pulse__phone__pad_middle__OMIT__sqi | pulse | phone | no | no | 0..1 | OMIT on pad_middle: sqi (section 6.3) |
| pulse__phone__pad_middle__OMIT__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__OMIT__template_corr] |
| pulse__phone__pad_middle__PBV__hr_bpm | pulse | phone | no | no | bpm | PBV on pad_middle: hr_bpm (section 6.3) |
| pulse__phone__pad_middle__PBV__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__PBV__kurtosis] |
| pulse__phone__pad_middle__PBV__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__PBV__n_windows]: count |
| pulse__phone__pad_middle__PBV__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__PBV__skewness] |
| pulse__phone__pad_middle__PBV__snr_db | pulse | phone | no | no | dB | PBV on pad_middle: snr_db (section 6.3) |
| pulse__phone__pad_middle__PBV__sqi | pulse | phone | no | no | 0..1 | PBV on pad_middle: sqi (section 6.3) |
| pulse__phone__pad_middle__PBV__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__PBV__template_corr] |
| pulse__phone__pad_middle__PCA__hr_bpm | pulse | phone | no | no | bpm | PCA on pad_middle: hr_bpm (section 6.3) |
| pulse__phone__pad_middle__PCA__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__PCA__kurtosis] |
| pulse__phone__pad_middle__PCA__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__PCA__n_windows]: count |
| pulse__phone__pad_middle__PCA__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__PCA__skewness] |
| pulse__phone__pad_middle__PCA__snr_db | pulse | phone | no | no | dB | PCA on pad_middle: snr_db (section 6.3) |
| pulse__phone__pad_middle__PCA__sqi | pulse | phone | no | no | 0..1 | PCA on pad_middle: sqi (section 6.3) |
| pulse__phone__pad_middle__PCA__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__PCA__template_corr] |
| pulse__phone__pad_middle__POS__hr_bpm | pulse | phone | no | no | bpm | POS on pad_middle: hr_bpm (section 6.3) |
| pulse__phone__pad_middle__POS__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__POS__kurtosis] |
| pulse__phone__pad_middle__POS__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__POS__n_windows]: count |
| pulse__phone__pad_middle__POS__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__POS__skewness] |
| pulse__phone__pad_middle__POS__snr_db | pulse | phone | no | no | dB | POS on pad_middle: snr_db (section 6.3) |
| pulse__phone__pad_middle__POS__sqi | pulse | phone | no | no | 0..1 | POS on pad_middle: sqi (section 6.3) |
| pulse__phone__pad_middle__POS__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__POS__template_corr] |
| pulse__phone__pad_ring__2SR__hr_bpm | pulse | phone | no | no | bpm | 2SR on pad_ring: hr_bpm (section 6.3) |
| pulse__phone__pad_ring__2SR__snr_db | pulse | phone | no | no | dB | 2SR on pad_ring: snr_db (section 6.3) |
| pulse__phone__pad_ring__2SR__sqi | pulse | phone | no | no | 0..1 | 2SR on pad_ring: sqi (section 6.3) |
| pulse__phone__pad_ring__CHROM__hr_bpm | pulse | phone | no | no | bpm | CHROM on pad_ring: hr_bpm (section 6.3) |
| pulse__phone__pad_ring__CHROM__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__CHROM__kurtosis] |
| pulse__phone__pad_ring__CHROM__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__CHROM__n_windows]: count |
| pulse__phone__pad_ring__CHROM__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__CHROM__skewness] |
| pulse__phone__pad_ring__CHROM__snr_db | pulse | phone | no | no | dB | CHROM on pad_ring: snr_db (section 6.3) |
| pulse__phone__pad_ring__CHROM__sqi | pulse | phone | no | no | 0..1 | CHROM on pad_ring: sqi (section 6.3) |
| pulse__phone__pad_ring__CHROM__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__CHROM__template_corr] |
| pulse__phone__pad_ring__GREEN__hr_bpm | pulse | phone | no | no | bpm | GREEN on pad_ring: hr_bpm (section 6.3) |
| pulse__phone__pad_ring__GREEN__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__GREEN__kurtosis] |
| pulse__phone__pad_ring__GREEN__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__GREEN__n_windows]: count |
| pulse__phone__pad_ring__GREEN__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__GREEN__skewness] |
| pulse__phone__pad_ring__GREEN__snr_db | pulse | phone | no | no | dB | GREEN on pad_ring: snr_db (section 6.3) |
| pulse__phone__pad_ring__GREEN__sqi | pulse | phone | no | no | 0..1 | GREEN on pad_ring: sqi (section 6.3) |
| pulse__phone__pad_ring__GREEN__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__GREEN__template_corr] |
| pulse__phone__pad_ring__ICA__hr_bpm | pulse | phone | no | no | bpm | ICA on pad_ring: hr_bpm (section 6.3) |
| pulse__phone__pad_ring__ICA__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__ICA__kurtosis] |
| pulse__phone__pad_ring__ICA__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__ICA__n_windows]: count |
| pulse__phone__pad_ring__ICA__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__ICA__skewness] |
| pulse__phone__pad_ring__ICA__snr_db | pulse | phone | no | no | dB | ICA on pad_ring: snr_db (section 6.3) |
| pulse__phone__pad_ring__ICA__sqi | pulse | phone | no | no | 0..1 | ICA on pad_ring: sqi (section 6.3) |
| pulse__phone__pad_ring__ICA__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__ICA__template_corr] |
| pulse__phone__pad_ring__LGI__hr_bpm | pulse | phone | no | no | bpm | LGI on pad_ring: hr_bpm (section 6.3) |
| pulse__phone__pad_ring__LGI__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__LGI__kurtosis] |
| pulse__phone__pad_ring__LGI__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__LGI__n_windows]: count |
| pulse__phone__pad_ring__LGI__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__LGI__skewness] |
| pulse__phone__pad_ring__LGI__snr_db | pulse | phone | no | no | dB | LGI on pad_ring: snr_db (section 6.3) |
| pulse__phone__pad_ring__LGI__sqi | pulse | phone | no | no | 0..1 | LGI on pad_ring: sqi (section 6.3) |
| pulse__phone__pad_ring__LGI__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__LGI__template_corr] |
| pulse__phone__pad_ring__OMIT__hr_bpm | pulse | phone | no | no | bpm | OMIT on pad_ring: hr_bpm (section 6.3) |
| pulse__phone__pad_ring__OMIT__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__OMIT__kurtosis] |
| pulse__phone__pad_ring__OMIT__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__OMIT__n_windows]: count |
| pulse__phone__pad_ring__OMIT__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__OMIT__skewness] |
| pulse__phone__pad_ring__OMIT__snr_db | pulse | phone | no | no | dB | OMIT on pad_ring: snr_db (section 6.3) |
| pulse__phone__pad_ring__OMIT__sqi | pulse | phone | no | no | 0..1 | OMIT on pad_ring: sqi (section 6.3) |
| pulse__phone__pad_ring__OMIT__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__OMIT__template_corr] |
| pulse__phone__pad_ring__PBV__hr_bpm | pulse | phone | no | no | bpm | PBV on pad_ring: hr_bpm (section 6.3) |
| pulse__phone__pad_ring__PBV__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__PBV__kurtosis] |
| pulse__phone__pad_ring__PBV__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__PBV__n_windows]: count |
| pulse__phone__pad_ring__PBV__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__PBV__skewness] |
| pulse__phone__pad_ring__PBV__snr_db | pulse | phone | no | no | dB | PBV on pad_ring: snr_db (section 6.3) |
| pulse__phone__pad_ring__PBV__sqi | pulse | phone | no | no | 0..1 | PBV on pad_ring: sqi (section 6.3) |
| pulse__phone__pad_ring__PBV__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__PBV__template_corr] |
| pulse__phone__pad_ring__PCA__hr_bpm | pulse | phone | no | no | bpm | PCA on pad_ring: hr_bpm (section 6.3) |
| pulse__phone__pad_ring__PCA__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__PCA__kurtosis] |
| pulse__phone__pad_ring__PCA__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__PCA__n_windows]: count |
| pulse__phone__pad_ring__PCA__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__PCA__skewness] |
| pulse__phone__pad_ring__PCA__snr_db | pulse | phone | no | no | dB | PCA on pad_ring: snr_db (section 6.3) |
| pulse__phone__pad_ring__PCA__sqi | pulse | phone | no | no | 0..1 | PCA on pad_ring: sqi (section 6.3) |
| pulse__phone__pad_ring__PCA__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__PCA__template_corr] |
| pulse__phone__pad_ring__POS__hr_bpm | pulse | phone | no | no | bpm | POS on pad_ring: hr_bpm (section 6.3) |
| pulse__phone__pad_ring__POS__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__POS__kurtosis] |
| pulse__phone__pad_ring__POS__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__POS__n_windows]: count |
| pulse__phone__pad_ring__POS__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__POS__skewness] |
| pulse__phone__pad_ring__POS__snr_db | pulse | phone | no | no | dB | POS on pad_ring: snr_db (section 6.3) |
| pulse__phone__pad_ring__POS__sqi | pulse | phone | no | no | 0..1 | POS on pad_ring: sqi (section 6.3) |
| pulse__phone__pad_ring__POS__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__POS__template_corr] |
| pulse__phone__prox_index__2SR__hr_bpm | pulse | phone | no | no | bpm | 2SR on prox_index: hr_bpm (section 6.3) |
| pulse__phone__prox_index__2SR__snr_db | pulse | phone | no | no | dB | 2SR on prox_index: snr_db (section 6.3) |
| pulse__phone__prox_index__2SR__sqi | pulse | phone | no | no | 0..1 | 2SR on prox_index: sqi (section 6.3) |
| pulse__phone__prox_index__CHROM__hr_bpm | pulse | phone | no | no | bpm | CHROM on prox_index: hr_bpm (section 6.3) |
| pulse__phone__prox_index__CHROM__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__CHROM__kurtosis] |
| pulse__phone__prox_index__CHROM__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__CHROM__n_windows]: count |
| pulse__phone__prox_index__CHROM__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__CHROM__skewness] |
| pulse__phone__prox_index__CHROM__snr_db | pulse | phone | no | no | dB | CHROM on prox_index: snr_db (section 6.3) |
| pulse__phone__prox_index__CHROM__sqi | pulse | phone | no | no | 0..1 | CHROM on prox_index: sqi (section 6.3) |
| pulse__phone__prox_index__CHROM__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__CHROM__template_corr] |
| pulse__phone__prox_index__GREEN__hr_bpm | pulse | phone | no | no | bpm | GREEN on prox_index: hr_bpm (section 6.3) |
| pulse__phone__prox_index__GREEN__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__GREEN__kurtosis] |
| pulse__phone__prox_index__GREEN__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__GREEN__n_windows]: count |
| pulse__phone__prox_index__GREEN__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__GREEN__skewness] |
| pulse__phone__prox_index__GREEN__snr_db | pulse | phone | no | no | dB | GREEN on prox_index: snr_db (section 6.3) |
| pulse__phone__prox_index__GREEN__sqi | pulse | phone | no | no | 0..1 | GREEN on prox_index: sqi (section 6.3) |
| pulse__phone__prox_index__GREEN__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__GREEN__template_corr] |
| pulse__phone__prox_index__ICA__hr_bpm | pulse | phone | no | no | bpm | ICA on prox_index: hr_bpm (section 6.3) |
| pulse__phone__prox_index__ICA__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__ICA__kurtosis] |
| pulse__phone__prox_index__ICA__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__ICA__n_windows]: count |
| pulse__phone__prox_index__ICA__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__ICA__skewness] |
| pulse__phone__prox_index__ICA__snr_db | pulse | phone | no | no | dB | ICA on prox_index: snr_db (section 6.3) |
| pulse__phone__prox_index__ICA__sqi | pulse | phone | no | no | 0..1 | ICA on prox_index: sqi (section 6.3) |
| pulse__phone__prox_index__ICA__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__ICA__template_corr] |
| pulse__phone__prox_index__LGI__hr_bpm | pulse | phone | no | no | bpm | LGI on prox_index: hr_bpm (section 6.3) |
| pulse__phone__prox_index__LGI__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__LGI__kurtosis] |
| pulse__phone__prox_index__LGI__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__LGI__n_windows]: count |
| pulse__phone__prox_index__LGI__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__LGI__skewness] |
| pulse__phone__prox_index__LGI__snr_db | pulse | phone | no | no | dB | LGI on prox_index: snr_db (section 6.3) |
| pulse__phone__prox_index__LGI__sqi | pulse | phone | no | no | 0..1 | LGI on prox_index: sqi (section 6.3) |
| pulse__phone__prox_index__LGI__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__LGI__template_corr] |
| pulse__phone__prox_index__OMIT__hr_bpm | pulse | phone | no | no | bpm | OMIT on prox_index: hr_bpm (section 6.3) |
| pulse__phone__prox_index__OMIT__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__OMIT__kurtosis] |
| pulse__phone__prox_index__OMIT__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__OMIT__n_windows]: count |
| pulse__phone__prox_index__OMIT__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__OMIT__skewness] |
| pulse__phone__prox_index__OMIT__snr_db | pulse | phone | no | no | dB | OMIT on prox_index: snr_db (section 6.3) |
| pulse__phone__prox_index__OMIT__sqi | pulse | phone | no | no | 0..1 | OMIT on prox_index: sqi (section 6.3) |
| pulse__phone__prox_index__OMIT__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__OMIT__template_corr] |
| pulse__phone__prox_index__PBV__hr_bpm | pulse | phone | no | no | bpm | PBV on prox_index: hr_bpm (section 6.3) |
| pulse__phone__prox_index__PBV__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__PBV__kurtosis] |
| pulse__phone__prox_index__PBV__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__PBV__n_windows]: count |
| pulse__phone__prox_index__PBV__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__PBV__skewness] |
| pulse__phone__prox_index__PBV__snr_db | pulse | phone | no | no | dB | PBV on prox_index: snr_db (section 6.3) |
| pulse__phone__prox_index__PBV__sqi | pulse | phone | no | no | 0..1 | PBV on prox_index: sqi (section 6.3) |
| pulse__phone__prox_index__PBV__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__PBV__template_corr] |
| pulse__phone__prox_index__PCA__hr_bpm | pulse | phone | no | no | bpm | PCA on prox_index: hr_bpm (section 6.3) |
| pulse__phone__prox_index__PCA__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__PCA__kurtosis] |
| pulse__phone__prox_index__PCA__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__PCA__n_windows]: count |
| pulse__phone__prox_index__PCA__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__PCA__skewness] |
| pulse__phone__prox_index__PCA__snr_db | pulse | phone | no | no | dB | PCA on prox_index: snr_db (section 6.3) |
| pulse__phone__prox_index__PCA__sqi | pulse | phone | no | no | 0..1 | PCA on prox_index: sqi (section 6.3) |
| pulse__phone__prox_index__PCA__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__PCA__template_corr] |
| pulse__phone__prox_index__POS__hr_bpm | pulse | phone | no | no | bpm | POS on prox_index: hr_bpm (section 6.3) |
| pulse__phone__prox_index__POS__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__POS__kurtosis] |
| pulse__phone__prox_index__POS__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__POS__n_windows]: count |
| pulse__phone__prox_index__POS__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__POS__skewness] |
| pulse__phone__prox_index__POS__snr_db | pulse | phone | no | no | dB | POS on prox_index: snr_db (section 6.3) |
| pulse__phone__prox_index__POS__sqi | pulse | phone | no | no | 0..1 | POS on prox_index: sqi (section 6.3) |
| pulse__phone__prox_index__POS__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__POS__template_corr] |
| pulse__phone__prox_little__2SR__hr_bpm | pulse | phone | no | no | bpm | 2SR on prox_little: hr_bpm (section 6.3) |
| pulse__phone__prox_little__2SR__snr_db | pulse | phone | no | no | dB | 2SR on prox_little: snr_db (section 6.3) |
| pulse__phone__prox_little__2SR__sqi | pulse | phone | no | no | 0..1 | 2SR on prox_little: sqi (section 6.3) |
| pulse__phone__prox_little__CHROM__hr_bpm | pulse | phone | no | no | bpm | CHROM on prox_little: hr_bpm (section 6.3) |
| pulse__phone__prox_little__CHROM__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__CHROM__kurtosis] |
| pulse__phone__prox_little__CHROM__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__CHROM__n_windows]: count |
| pulse__phone__prox_little__CHROM__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__CHROM__skewness] |
| pulse__phone__prox_little__CHROM__snr_db | pulse | phone | no | no | dB | CHROM on prox_little: snr_db (section 6.3) |
| pulse__phone__prox_little__CHROM__sqi | pulse | phone | no | no | 0..1 | CHROM on prox_little: sqi (section 6.3) |
| pulse__phone__prox_little__CHROM__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__CHROM__template_corr] |
| pulse__phone__prox_little__GREEN__hr_bpm | pulse | phone | no | no | bpm | GREEN on prox_little: hr_bpm (section 6.3) |
| pulse__phone__prox_little__GREEN__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__GREEN__kurtosis] |
| pulse__phone__prox_little__GREEN__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__GREEN__n_windows]: count |
| pulse__phone__prox_little__GREEN__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__GREEN__skewness] |
| pulse__phone__prox_little__GREEN__snr_db | pulse | phone | no | no | dB | GREEN on prox_little: snr_db (section 6.3) |
| pulse__phone__prox_little__GREEN__sqi | pulse | phone | no | no | 0..1 | GREEN on prox_little: sqi (section 6.3) |
| pulse__phone__prox_little__GREEN__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__GREEN__template_corr] |
| pulse__phone__prox_little__ICA__hr_bpm | pulse | phone | no | no | bpm | ICA on prox_little: hr_bpm (section 6.3) |
| pulse__phone__prox_little__ICA__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__ICA__kurtosis] |
| pulse__phone__prox_little__ICA__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__ICA__n_windows]: count |
| pulse__phone__prox_little__ICA__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__ICA__skewness] |
| pulse__phone__prox_little__ICA__snr_db | pulse | phone | no | no | dB | ICA on prox_little: snr_db (section 6.3) |
| pulse__phone__prox_little__ICA__sqi | pulse | phone | no | no | 0..1 | ICA on prox_little: sqi (section 6.3) |
| pulse__phone__prox_little__ICA__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__ICA__template_corr] |
| pulse__phone__prox_little__LGI__hr_bpm | pulse | phone | no | no | bpm | LGI on prox_little: hr_bpm (section 6.3) |
| pulse__phone__prox_little__LGI__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__LGI__kurtosis] |
| pulse__phone__prox_little__LGI__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__LGI__n_windows]: count |
| pulse__phone__prox_little__LGI__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__LGI__skewness] |
| pulse__phone__prox_little__LGI__snr_db | pulse | phone | no | no | dB | LGI on prox_little: snr_db (section 6.3) |
| pulse__phone__prox_little__LGI__sqi | pulse | phone | no | no | 0..1 | LGI on prox_little: sqi (section 6.3) |
| pulse__phone__prox_little__LGI__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__LGI__template_corr] |
| pulse__phone__prox_little__OMIT__hr_bpm | pulse | phone | no | no | bpm | OMIT on prox_little: hr_bpm (section 6.3) |
| pulse__phone__prox_little__OMIT__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__OMIT__kurtosis] |
| pulse__phone__prox_little__OMIT__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__OMIT__n_windows]: count |
| pulse__phone__prox_little__OMIT__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__OMIT__skewness] |
| pulse__phone__prox_little__OMIT__snr_db | pulse | phone | no | no | dB | OMIT on prox_little: snr_db (section 6.3) |
| pulse__phone__prox_little__OMIT__sqi | pulse | phone | no | no | 0..1 | OMIT on prox_little: sqi (section 6.3) |
| pulse__phone__prox_little__OMIT__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__OMIT__template_corr] |
| pulse__phone__prox_little__PBV__hr_bpm | pulse | phone | no | no | bpm | PBV on prox_little: hr_bpm (section 6.3) |
| pulse__phone__prox_little__PBV__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__PBV__kurtosis] |
| pulse__phone__prox_little__PBV__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__PBV__n_windows]: count |
| pulse__phone__prox_little__PBV__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__PBV__skewness] |
| pulse__phone__prox_little__PBV__snr_db | pulse | phone | no | no | dB | PBV on prox_little: snr_db (section 6.3) |
| pulse__phone__prox_little__PBV__sqi | pulse | phone | no | no | 0..1 | PBV on prox_little: sqi (section 6.3) |
| pulse__phone__prox_little__PBV__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__PBV__template_corr] |
| pulse__phone__prox_little__PCA__hr_bpm | pulse | phone | no | no | bpm | PCA on prox_little: hr_bpm (section 6.3) |
| pulse__phone__prox_little__PCA__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__PCA__kurtosis] |
| pulse__phone__prox_little__PCA__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__PCA__n_windows]: count |
| pulse__phone__prox_little__PCA__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__PCA__skewness] |
| pulse__phone__prox_little__PCA__snr_db | pulse | phone | no | no | dB | PCA on prox_little: snr_db (section 6.3) |
| pulse__phone__prox_little__PCA__sqi | pulse | phone | no | no | 0..1 | PCA on prox_little: sqi (section 6.3) |
| pulse__phone__prox_little__PCA__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__PCA__template_corr] |
| pulse__phone__prox_little__POS__hr_bpm | pulse | phone | no | no | bpm | POS on prox_little: hr_bpm (section 6.3) |
| pulse__phone__prox_little__POS__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__POS__kurtosis] |
| pulse__phone__prox_little__POS__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__POS__n_windows]: count |
| pulse__phone__prox_little__POS__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__POS__skewness] |
| pulse__phone__prox_little__POS__snr_db | pulse | phone | no | no | dB | POS on prox_little: snr_db (section 6.3) |
| pulse__phone__prox_little__POS__sqi | pulse | phone | no | no | 0..1 | POS on prox_little: sqi (section 6.3) |
| pulse__phone__prox_little__POS__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__POS__template_corr] |
| pulse__phone__prox_middle__2SR__hr_bpm | pulse | phone | no | no | bpm | 2SR on prox_middle: hr_bpm (section 6.3) |
| pulse__phone__prox_middle__2SR__snr_db | pulse | phone | no | no | dB | 2SR on prox_middle: snr_db (section 6.3) |
| pulse__phone__prox_middle__2SR__sqi | pulse | phone | no | no | 0..1 | 2SR on prox_middle: sqi (section 6.3) |
| pulse__phone__prox_middle__CHROM__hr_bpm | pulse | phone | no | no | bpm | CHROM on prox_middle: hr_bpm (section 6.3) |
| pulse__phone__prox_middle__CHROM__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__CHROM__kurtosis] |
| pulse__phone__prox_middle__CHROM__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__CHROM__n_windows]: count |
| pulse__phone__prox_middle__CHROM__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__CHROM__skewness] |
| pulse__phone__prox_middle__CHROM__snr_db | pulse | phone | no | no | dB | CHROM on prox_middle: snr_db (section 6.3) |
| pulse__phone__prox_middle__CHROM__sqi | pulse | phone | no | no | 0..1 | CHROM on prox_middle: sqi (section 6.3) |
| pulse__phone__prox_middle__CHROM__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__CHROM__template_corr] |
| pulse__phone__prox_middle__GREEN__hr_bpm | pulse | phone | no | no | bpm | GREEN on prox_middle: hr_bpm (section 6.3) |
| pulse__phone__prox_middle__GREEN__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__GREEN__kurtosis] |
| pulse__phone__prox_middle__GREEN__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__GREEN__n_windows]: count |
| pulse__phone__prox_middle__GREEN__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__GREEN__skewness] |
| pulse__phone__prox_middle__GREEN__snr_db | pulse | phone | no | no | dB | GREEN on prox_middle: snr_db (section 6.3) |
| pulse__phone__prox_middle__GREEN__sqi | pulse | phone | no | no | 0..1 | GREEN on prox_middle: sqi (section 6.3) |
| pulse__phone__prox_middle__GREEN__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__GREEN__template_corr] |
| pulse__phone__prox_middle__ICA__hr_bpm | pulse | phone | no | no | bpm | ICA on prox_middle: hr_bpm (section 6.3) |
| pulse__phone__prox_middle__ICA__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__ICA__kurtosis] |
| pulse__phone__prox_middle__ICA__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__ICA__n_windows]: count |
| pulse__phone__prox_middle__ICA__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__ICA__skewness] |
| pulse__phone__prox_middle__ICA__snr_db | pulse | phone | no | no | dB | ICA on prox_middle: snr_db (section 6.3) |
| pulse__phone__prox_middle__ICA__sqi | pulse | phone | no | no | 0..1 | ICA on prox_middle: sqi (section 6.3) |
| pulse__phone__prox_middle__ICA__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__ICA__template_corr] |
| pulse__phone__prox_middle__LGI__hr_bpm | pulse | phone | no | no | bpm | LGI on prox_middle: hr_bpm (section 6.3) |
| pulse__phone__prox_middle__LGI__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__LGI__kurtosis] |
| pulse__phone__prox_middle__LGI__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__LGI__n_windows]: count |
| pulse__phone__prox_middle__LGI__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__LGI__skewness] |
| pulse__phone__prox_middle__LGI__snr_db | pulse | phone | no | no | dB | LGI on prox_middle: snr_db (section 6.3) |
| pulse__phone__prox_middle__LGI__sqi | pulse | phone | no | no | 0..1 | LGI on prox_middle: sqi (section 6.3) |
| pulse__phone__prox_middle__LGI__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__LGI__template_corr] |
| pulse__phone__prox_middle__OMIT__hr_bpm | pulse | phone | no | no | bpm | OMIT on prox_middle: hr_bpm (section 6.3) |
| pulse__phone__prox_middle__OMIT__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__OMIT__kurtosis] |
| pulse__phone__prox_middle__OMIT__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__OMIT__n_windows]: count |
| pulse__phone__prox_middle__OMIT__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__OMIT__skewness] |
| pulse__phone__prox_middle__OMIT__snr_db | pulse | phone | no | no | dB | OMIT on prox_middle: snr_db (section 6.3) |
| pulse__phone__prox_middle__OMIT__sqi | pulse | phone | no | no | 0..1 | OMIT on prox_middle: sqi (section 6.3) |
| pulse__phone__prox_middle__OMIT__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__OMIT__template_corr] |
| pulse__phone__prox_middle__PBV__hr_bpm | pulse | phone | no | no | bpm | PBV on prox_middle: hr_bpm (section 6.3) |
| pulse__phone__prox_middle__PBV__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__PBV__kurtosis] |
| pulse__phone__prox_middle__PBV__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__PBV__n_windows]: count |
| pulse__phone__prox_middle__PBV__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__PBV__skewness] |
| pulse__phone__prox_middle__PBV__snr_db | pulse | phone | no | no | dB | PBV on prox_middle: snr_db (section 6.3) |
| pulse__phone__prox_middle__PBV__sqi | pulse | phone | no | no | 0..1 | PBV on prox_middle: sqi (section 6.3) |
| pulse__phone__prox_middle__PBV__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__PBV__template_corr] |
| pulse__phone__prox_middle__PCA__hr_bpm | pulse | phone | no | no | bpm | PCA on prox_middle: hr_bpm (section 6.3) |
| pulse__phone__prox_middle__PCA__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__PCA__kurtosis] |
| pulse__phone__prox_middle__PCA__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__PCA__n_windows]: count |
| pulse__phone__prox_middle__PCA__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__PCA__skewness] |
| pulse__phone__prox_middle__PCA__snr_db | pulse | phone | no | no | dB | PCA on prox_middle: snr_db (section 6.3) |
| pulse__phone__prox_middle__PCA__sqi | pulse | phone | no | no | 0..1 | PCA on prox_middle: sqi (section 6.3) |
| pulse__phone__prox_middle__PCA__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__PCA__template_corr] |
| pulse__phone__prox_middle__POS__hr_bpm | pulse | phone | no | no | bpm | POS on prox_middle: hr_bpm (section 6.3) |
| pulse__phone__prox_middle__POS__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__POS__kurtosis] |
| pulse__phone__prox_middle__POS__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__POS__n_windows]: count |
| pulse__phone__prox_middle__POS__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__POS__skewness] |
| pulse__phone__prox_middle__POS__snr_db | pulse | phone | no | no | dB | POS on prox_middle: snr_db (section 6.3) |
| pulse__phone__prox_middle__POS__sqi | pulse | phone | no | no | 0..1 | POS on prox_middle: sqi (section 6.3) |
| pulse__phone__prox_middle__POS__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__POS__template_corr] |
| pulse__phone__prox_ring__2SR__hr_bpm | pulse | phone | no | no | bpm | 2SR on prox_ring: hr_bpm (section 6.3) |
| pulse__phone__prox_ring__2SR__snr_db | pulse | phone | no | no | dB | 2SR on prox_ring: snr_db (section 6.3) |
| pulse__phone__prox_ring__2SR__sqi | pulse | phone | no | no | 0..1 | 2SR on prox_ring: sqi (section 6.3) |
| pulse__phone__prox_ring__CHROM__hr_bpm | pulse | phone | no | no | bpm | CHROM on prox_ring: hr_bpm (section 6.3) |
| pulse__phone__prox_ring__CHROM__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__CHROM__kurtosis] |
| pulse__phone__prox_ring__CHROM__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__CHROM__n_windows]: count |
| pulse__phone__prox_ring__CHROM__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__CHROM__skewness] |
| pulse__phone__prox_ring__CHROM__snr_db | pulse | phone | no | no | dB | CHROM on prox_ring: snr_db (section 6.3) |
| pulse__phone__prox_ring__CHROM__sqi | pulse | phone | no | no | 0..1 | CHROM on prox_ring: sqi (section 6.3) |
| pulse__phone__prox_ring__CHROM__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__CHROM__template_corr] |
| pulse__phone__prox_ring__GREEN__hr_bpm | pulse | phone | no | no | bpm | GREEN on prox_ring: hr_bpm (section 6.3) |
| pulse__phone__prox_ring__GREEN__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__GREEN__kurtosis] |
| pulse__phone__prox_ring__GREEN__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__GREEN__n_windows]: count |
| pulse__phone__prox_ring__GREEN__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__GREEN__skewness] |
| pulse__phone__prox_ring__GREEN__snr_db | pulse | phone | no | no | dB | GREEN on prox_ring: snr_db (section 6.3) |
| pulse__phone__prox_ring__GREEN__sqi | pulse | phone | no | no | 0..1 | GREEN on prox_ring: sqi (section 6.3) |
| pulse__phone__prox_ring__GREEN__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__GREEN__template_corr] |
| pulse__phone__prox_ring__ICA__hr_bpm | pulse | phone | no | no | bpm | ICA on prox_ring: hr_bpm (section 6.3) |
| pulse__phone__prox_ring__ICA__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__ICA__kurtosis] |
| pulse__phone__prox_ring__ICA__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__ICA__n_windows]: count |
| pulse__phone__prox_ring__ICA__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__ICA__skewness] |
| pulse__phone__prox_ring__ICA__snr_db | pulse | phone | no | no | dB | ICA on prox_ring: snr_db (section 6.3) |
| pulse__phone__prox_ring__ICA__sqi | pulse | phone | no | no | 0..1 | ICA on prox_ring: sqi (section 6.3) |
| pulse__phone__prox_ring__ICA__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__ICA__template_corr] |
| pulse__phone__prox_ring__LGI__hr_bpm | pulse | phone | no | no | bpm | LGI on prox_ring: hr_bpm (section 6.3) |
| pulse__phone__prox_ring__LGI__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__LGI__kurtosis] |
| pulse__phone__prox_ring__LGI__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__LGI__n_windows]: count |
| pulse__phone__prox_ring__LGI__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__LGI__skewness] |
| pulse__phone__prox_ring__LGI__snr_db | pulse | phone | no | no | dB | LGI on prox_ring: snr_db (section 6.3) |
| pulse__phone__prox_ring__LGI__sqi | pulse | phone | no | no | 0..1 | LGI on prox_ring: sqi (section 6.3) |
| pulse__phone__prox_ring__LGI__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__LGI__template_corr] |
| pulse__phone__prox_ring__OMIT__hr_bpm | pulse | phone | no | no | bpm | OMIT on prox_ring: hr_bpm (section 6.3) |
| pulse__phone__prox_ring__OMIT__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__OMIT__kurtosis] |
| pulse__phone__prox_ring__OMIT__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__OMIT__n_windows]: count |
| pulse__phone__prox_ring__OMIT__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__OMIT__skewness] |
| pulse__phone__prox_ring__OMIT__snr_db | pulse | phone | no | no | dB | OMIT on prox_ring: snr_db (section 6.3) |
| pulse__phone__prox_ring__OMIT__sqi | pulse | phone | no | no | 0..1 | OMIT on prox_ring: sqi (section 6.3) |
| pulse__phone__prox_ring__OMIT__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__OMIT__template_corr] |
| pulse__phone__prox_ring__PBV__hr_bpm | pulse | phone | no | no | bpm | PBV on prox_ring: hr_bpm (section 6.3) |
| pulse__phone__prox_ring__PBV__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__PBV__kurtosis] |
| pulse__phone__prox_ring__PBV__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__PBV__n_windows]: count |
| pulse__phone__prox_ring__PBV__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__PBV__skewness] |
| pulse__phone__prox_ring__PBV__snr_db | pulse | phone | no | no | dB | PBV on prox_ring: snr_db (section 6.3) |
| pulse__phone__prox_ring__PBV__sqi | pulse | phone | no | no | 0..1 | PBV on prox_ring: sqi (section 6.3) |
| pulse__phone__prox_ring__PBV__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__PBV__template_corr] |
| pulse__phone__prox_ring__PCA__hr_bpm | pulse | phone | no | no | bpm | PCA on prox_ring: hr_bpm (section 6.3) |
| pulse__phone__prox_ring__PCA__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__PCA__kurtosis] |
| pulse__phone__prox_ring__PCA__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__PCA__n_windows]: count |
| pulse__phone__prox_ring__PCA__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__PCA__skewness] |
| pulse__phone__prox_ring__PCA__snr_db | pulse | phone | no | no | dB | PCA on prox_ring: snr_db (section 6.3) |
| pulse__phone__prox_ring__PCA__sqi | pulse | phone | no | no | 0..1 | PCA on prox_ring: sqi (section 6.3) |
| pulse__phone__prox_ring__PCA__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__PCA__template_corr] |
| pulse__phone__prox_ring__POS__hr_bpm | pulse | phone | no | no | bpm | POS on prox_ring: hr_bpm (section 6.3) |
| pulse__phone__prox_ring__POS__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__POS__kurtosis] |
| pulse__phone__prox_ring__POS__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__POS__n_windows]: count |
| pulse__phone__prox_ring__POS__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__POS__skewness] |
| pulse__phone__prox_ring__POS__snr_db | pulse | phone | no | no | dB | POS on prox_ring: snr_db (section 6.3) |
| pulse__phone__prox_ring__POS__sqi | pulse | phone | no | no | 0..1 | POS on prox_ring: sqi (section 6.3) |
| pulse__phone__prox_ring__POS__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__POS__template_corr] |
| pulse__phone__roi_set__2SR__hr_bpm | pulse | phone | no | no | bpm | 2SR on roi_set: hr_bpm (section 6.3) |
| pulse__phone__roi_set__2SR__snr_db | pulse | phone | no | no | dB | 2SR on roi_set: snr_db (section 6.3) |
| pulse__phone__roi_set__2SR__sqi | pulse | phone | no | no | 0..1 | 2SR on roi_set: sqi (section 6.3) |
| pulse__phone__roi_set__CHROM__hr_bpm | pulse | phone | no | no | bpm | CHROM on roi_set: hr_bpm (section 6.3) |
| pulse__phone__roi_set__CHROM__snr_db | pulse | phone | no | no | dB | CHROM on roi_set: snr_db (section 6.3) |
| pulse__phone__roi_set__CHROM__sqi | pulse | phone | no | no | 0..1 | CHROM on roi_set: sqi (section 6.3) |
| pulse__phone__roi_set__GREEN__hr_bpm | pulse | phone | no | no | bpm | GREEN on roi_set: hr_bpm (section 6.3) |
| pulse__phone__roi_set__GREEN__snr_db | pulse | phone | no | no | dB | GREEN on roi_set: snr_db (section 6.3) |
| pulse__phone__roi_set__GREEN__sqi | pulse | phone | no | no | 0..1 | GREEN on roi_set: sqi (section 6.3) |
| pulse__phone__roi_set__ICA__hr_bpm | pulse | phone | no | no | bpm | ICA on roi_set: hr_bpm (section 6.3) |
| pulse__phone__roi_set__ICA__snr_db | pulse | phone | no | no | dB | ICA on roi_set: snr_db (section 6.3) |
| pulse__phone__roi_set__ICA__sqi | pulse | phone | no | no | 0..1 | ICA on roi_set: sqi (section 6.3) |
| pulse__phone__roi_set__LGI__hr_bpm | pulse | phone | no | no | bpm | LGI on roi_set: hr_bpm (section 6.3) |
| pulse__phone__roi_set__LGI__snr_db | pulse | phone | no | no | dB | LGI on roi_set: snr_db (section 6.3) |
| pulse__phone__roi_set__LGI__sqi | pulse | phone | no | no | 0..1 | LGI on roi_set: sqi (section 6.3) |
| pulse__phone__roi_set__OMIT__hr_bpm | pulse | phone | no | no | bpm | OMIT on roi_set: hr_bpm (section 6.3) |
| pulse__phone__roi_set__OMIT__snr_db | pulse | phone | no | no | dB | OMIT on roi_set: snr_db (section 6.3) |
| pulse__phone__roi_set__OMIT__sqi | pulse | phone | no | no | 0..1 | OMIT on roi_set: sqi (section 6.3) |
| pulse__phone__roi_set__PBV__hr_bpm | pulse | phone | no | no | bpm | PBV on roi_set: hr_bpm (section 6.3) |
| pulse__phone__roi_set__PBV__snr_db | pulse | phone | no | no | dB | PBV on roi_set: snr_db (section 6.3) |
| pulse__phone__roi_set__PBV__sqi | pulse | phone | no | no | 0..1 | PBV on roi_set: sqi (section 6.3) |
| pulse__phone__roi_set__PCA__hr_bpm | pulse | phone | no | no | bpm | PCA on roi_set: hr_bpm (section 6.3) |
| pulse__phone__roi_set__PCA__snr_db | pulse | phone | no | no | dB | PCA on roi_set: snr_db (section 6.3) |
| pulse__phone__roi_set__PCA__sqi | pulse | phone | no | no | 0..1 | PCA on roi_set: sqi (section 6.3) |
| pulse__phone__roi_set__POS__hr_bpm | pulse | phone | no | no | bpm | POS on roi_set: hr_bpm (section 6.3) |
| pulse__phone__roi_set__POS__snr_db | pulse | phone | no | no | dB | POS on roi_set: snr_db (section 6.3) |
| pulse__phone__roi_set__POS__sqi | pulse | phone | no | no | 0..1 | POS on roi_set: sqi (section 6.3) |
| pulse__phone__selection__agreement | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [selection__agreement] |
| pulse__phone__selection__consensus_hr_bpm | pulse | phone | no | no | bpm | pulse extraction summary per method and ROI (protocol 6.3) [selection__consensus_hr_bpm]: rate in beats per minute |
| pulse__phone__selection__mode | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [selection__mode] |
| pulse__phone__selection__n_candidates | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [selection__n_candidates]: count |
| pulse__phone__selection__raw_sqi | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [selection__raw_sqi] |
| pulse__phone__selection__score | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [selection__score] |
| pulse__phone__thenar__2SR__hr_bpm | pulse | phone | no | no | bpm | 2SR on thenar: hr_bpm (section 6.3) |
| pulse__phone__thenar__2SR__snr_db | pulse | phone | no | no | dB | 2SR on thenar: snr_db (section 6.3) |
| pulse__phone__thenar__2SR__sqi | pulse | phone | no | no | 0..1 | 2SR on thenar: sqi (section 6.3) |
| pulse__phone__thenar__CHROM__hr_bpm | pulse | phone | no | no | bpm | CHROM on thenar: hr_bpm (section 6.3) |
| pulse__phone__thenar__CHROM__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__CHROM__kurtosis] |
| pulse__phone__thenar__CHROM__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [thenar__CHROM__n_windows]: count |
| pulse__phone__thenar__CHROM__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__CHROM__skewness] |
| pulse__phone__thenar__CHROM__snr_db | pulse | phone | no | no | dB | CHROM on thenar: snr_db (section 6.3) |
| pulse__phone__thenar__CHROM__sqi | pulse | phone | no | no | 0..1 | CHROM on thenar: sqi (section 6.3) |
| pulse__phone__thenar__CHROM__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__CHROM__template_corr] |
| pulse__phone__thenar__GREEN__hr_bpm | pulse | phone | no | no | bpm | GREEN on thenar: hr_bpm (section 6.3) |
| pulse__phone__thenar__GREEN__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__GREEN__kurtosis] |
| pulse__phone__thenar__GREEN__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [thenar__GREEN__n_windows]: count |
| pulse__phone__thenar__GREEN__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__GREEN__skewness] |
| pulse__phone__thenar__GREEN__snr_db | pulse | phone | no | no | dB | GREEN on thenar: snr_db (section 6.3) |
| pulse__phone__thenar__GREEN__sqi | pulse | phone | no | no | 0..1 | GREEN on thenar: sqi (section 6.3) |
| pulse__phone__thenar__GREEN__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__GREEN__template_corr] |
| pulse__phone__thenar__ICA__hr_bpm | pulse | phone | no | no | bpm | ICA on thenar: hr_bpm (section 6.3) |
| pulse__phone__thenar__ICA__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__ICA__kurtosis] |
| pulse__phone__thenar__ICA__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [thenar__ICA__n_windows]: count |
| pulse__phone__thenar__ICA__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__ICA__skewness] |
| pulse__phone__thenar__ICA__snr_db | pulse | phone | no | no | dB | ICA on thenar: snr_db (section 6.3) |
| pulse__phone__thenar__ICA__sqi | pulse | phone | no | no | 0..1 | ICA on thenar: sqi (section 6.3) |
| pulse__phone__thenar__ICA__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__ICA__template_corr] |
| pulse__phone__thenar__LGI__hr_bpm | pulse | phone | no | no | bpm | LGI on thenar: hr_bpm (section 6.3) |
| pulse__phone__thenar__LGI__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__LGI__kurtosis] |
| pulse__phone__thenar__LGI__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [thenar__LGI__n_windows]: count |
| pulse__phone__thenar__LGI__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__LGI__skewness] |
| pulse__phone__thenar__LGI__snr_db | pulse | phone | no | no | dB | LGI on thenar: snr_db (section 6.3) |
| pulse__phone__thenar__LGI__sqi | pulse | phone | no | no | 0..1 | LGI on thenar: sqi (section 6.3) |
| pulse__phone__thenar__LGI__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__LGI__template_corr] |
| pulse__phone__thenar__OMIT__hr_bpm | pulse | phone | no | no | bpm | OMIT on thenar: hr_bpm (section 6.3) |
| pulse__phone__thenar__OMIT__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__OMIT__kurtosis] |
| pulse__phone__thenar__OMIT__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [thenar__OMIT__n_windows]: count |
| pulse__phone__thenar__OMIT__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__OMIT__skewness] |
| pulse__phone__thenar__OMIT__snr_db | pulse | phone | no | no | dB | OMIT on thenar: snr_db (section 6.3) |
| pulse__phone__thenar__OMIT__sqi | pulse | phone | no | no | 0..1 | OMIT on thenar: sqi (section 6.3) |
| pulse__phone__thenar__OMIT__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__OMIT__template_corr] |
| pulse__phone__thenar__PBV__hr_bpm | pulse | phone | no | no | bpm | PBV on thenar: hr_bpm (section 6.3) |
| pulse__phone__thenar__PBV__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__PBV__kurtosis] |
| pulse__phone__thenar__PBV__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [thenar__PBV__n_windows]: count |
| pulse__phone__thenar__PBV__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__PBV__skewness] |
| pulse__phone__thenar__PBV__snr_db | pulse | phone | no | no | dB | PBV on thenar: snr_db (section 6.3) |
| pulse__phone__thenar__PBV__sqi | pulse | phone | no | no | 0..1 | PBV on thenar: sqi (section 6.3) |
| pulse__phone__thenar__PBV__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__PBV__template_corr] |
| pulse__phone__thenar__PCA__hr_bpm | pulse | phone | no | no | bpm | PCA on thenar: hr_bpm (section 6.3) |
| pulse__phone__thenar__PCA__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__PCA__kurtosis] |
| pulse__phone__thenar__PCA__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [thenar__PCA__n_windows]: count |
| pulse__phone__thenar__PCA__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__PCA__skewness] |
| pulse__phone__thenar__PCA__snr_db | pulse | phone | no | no | dB | PCA on thenar: snr_db (section 6.3) |
| pulse__phone__thenar__PCA__sqi | pulse | phone | no | no | 0..1 | PCA on thenar: sqi (section 6.3) |
| pulse__phone__thenar__PCA__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__PCA__template_corr] |
| pulse__phone__thenar__POS__hr_bpm | pulse | phone | no | no | bpm | POS on thenar: hr_bpm (section 6.3) |
| pulse__phone__thenar__POS__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__POS__kurtosis] |
| pulse__phone__thenar__POS__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [thenar__POS__n_windows]: count |
| pulse__phone__thenar__POS__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__POS__skewness] |
| pulse__phone__thenar__POS__snr_db | pulse | phone | no | no | dB | POS on thenar: snr_db (section 6.3) |
| pulse__phone__thenar__POS__sqi | pulse | phone | no | no | 0..1 | POS on thenar: sqi (section 6.3) |
| pulse__phone__thenar__POS__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__POS__template_corr] |
| pulse__phone__volar_wrist__2SR__hr_bpm | pulse | phone | no | no | bpm | 2SR on volar_wrist: hr_bpm (section 6.3) |
| pulse__phone__volar_wrist__2SR__snr_db | pulse | phone | no | no | dB | 2SR on volar_wrist: snr_db (section 6.3) |
| pulse__phone__volar_wrist__2SR__sqi | pulse | phone | no | no | 0..1 | 2SR on volar_wrist: sqi (section 6.3) |
| pulse__phone__volar_wrist__CHROM__hr_bpm | pulse | phone | no | no | bpm | CHROM on volar_wrist: hr_bpm (section 6.3) |
| pulse__phone__volar_wrist__CHROM__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__CHROM__kurtosis] |
| pulse__phone__volar_wrist__CHROM__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__CHROM__n_windows]: count |
| pulse__phone__volar_wrist__CHROM__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__CHROM__skewness] |
| pulse__phone__volar_wrist__CHROM__snr_db | pulse | phone | no | no | dB | CHROM on volar_wrist: snr_db (section 6.3) |
| pulse__phone__volar_wrist__CHROM__sqi | pulse | phone | no | no | 0..1 | CHROM on volar_wrist: sqi (section 6.3) |
| pulse__phone__volar_wrist__CHROM__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__CHROM__template_corr] |
| pulse__phone__volar_wrist__GREEN__hr_bpm | pulse | phone | no | no | bpm | GREEN on volar_wrist: hr_bpm (section 6.3) |
| pulse__phone__volar_wrist__GREEN__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__GREEN__kurtosis] |
| pulse__phone__volar_wrist__GREEN__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__GREEN__n_windows]: count |
| pulse__phone__volar_wrist__GREEN__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__GREEN__skewness] |
| pulse__phone__volar_wrist__GREEN__snr_db | pulse | phone | no | no | dB | GREEN on volar_wrist: snr_db (section 6.3) |
| pulse__phone__volar_wrist__GREEN__sqi | pulse | phone | no | no | 0..1 | GREEN on volar_wrist: sqi (section 6.3) |
| pulse__phone__volar_wrist__GREEN__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__GREEN__template_corr] |
| pulse__phone__volar_wrist__ICA__hr_bpm | pulse | phone | no | no | bpm | ICA on volar_wrist: hr_bpm (section 6.3) |
| pulse__phone__volar_wrist__ICA__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__ICA__kurtosis] |
| pulse__phone__volar_wrist__ICA__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__ICA__n_windows]: count |
| pulse__phone__volar_wrist__ICA__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__ICA__skewness] |
| pulse__phone__volar_wrist__ICA__snr_db | pulse | phone | no | no | dB | ICA on volar_wrist: snr_db (section 6.3) |
| pulse__phone__volar_wrist__ICA__sqi | pulse | phone | no | no | 0..1 | ICA on volar_wrist: sqi (section 6.3) |
| pulse__phone__volar_wrist__ICA__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__ICA__template_corr] |
| pulse__phone__volar_wrist__LGI__hr_bpm | pulse | phone | no | no | bpm | LGI on volar_wrist: hr_bpm (section 6.3) |
| pulse__phone__volar_wrist__LGI__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__LGI__kurtosis] |
| pulse__phone__volar_wrist__LGI__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__LGI__n_windows]: count |
| pulse__phone__volar_wrist__LGI__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__LGI__skewness] |
| pulse__phone__volar_wrist__LGI__snr_db | pulse | phone | no | no | dB | LGI on volar_wrist: snr_db (section 6.3) |
| pulse__phone__volar_wrist__LGI__sqi | pulse | phone | no | no | 0..1 | LGI on volar_wrist: sqi (section 6.3) |
| pulse__phone__volar_wrist__LGI__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__LGI__template_corr] |
| pulse__phone__volar_wrist__OMIT__hr_bpm | pulse | phone | no | no | bpm | OMIT on volar_wrist: hr_bpm (section 6.3) |
| pulse__phone__volar_wrist__OMIT__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__OMIT__kurtosis] |
| pulse__phone__volar_wrist__OMIT__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__OMIT__n_windows]: count |
| pulse__phone__volar_wrist__OMIT__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__OMIT__skewness] |
| pulse__phone__volar_wrist__OMIT__snr_db | pulse | phone | no | no | dB | OMIT on volar_wrist: snr_db (section 6.3) |
| pulse__phone__volar_wrist__OMIT__sqi | pulse | phone | no | no | 0..1 | OMIT on volar_wrist: sqi (section 6.3) |
| pulse__phone__volar_wrist__OMIT__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__OMIT__template_corr] |
| pulse__phone__volar_wrist__PBV__hr_bpm | pulse | phone | no | no | bpm | PBV on volar_wrist: hr_bpm (section 6.3) |
| pulse__phone__volar_wrist__PBV__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__PBV__kurtosis] |
| pulse__phone__volar_wrist__PBV__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__PBV__n_windows]: count |
| pulse__phone__volar_wrist__PBV__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__PBV__skewness] |
| pulse__phone__volar_wrist__PBV__snr_db | pulse | phone | no | no | dB | PBV on volar_wrist: snr_db (section 6.3) |
| pulse__phone__volar_wrist__PBV__sqi | pulse | phone | no | no | 0..1 | PBV on volar_wrist: sqi (section 6.3) |
| pulse__phone__volar_wrist__PBV__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__PBV__template_corr] |
| pulse__phone__volar_wrist__PCA__hr_bpm | pulse | phone | no | no | bpm | PCA on volar_wrist: hr_bpm (section 6.3) |
| pulse__phone__volar_wrist__PCA__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__PCA__kurtosis] |
| pulse__phone__volar_wrist__PCA__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__PCA__n_windows]: count |
| pulse__phone__volar_wrist__PCA__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__PCA__skewness] |
| pulse__phone__volar_wrist__PCA__snr_db | pulse | phone | no | no | dB | PCA on volar_wrist: snr_db (section 6.3) |
| pulse__phone__volar_wrist__PCA__sqi | pulse | phone | no | no | 0..1 | PCA on volar_wrist: sqi (section 6.3) |
| pulse__phone__volar_wrist__PCA__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__PCA__template_corr] |
| pulse__phone__volar_wrist__POS__hr_bpm | pulse | phone | no | no | bpm | POS on volar_wrist: hr_bpm (section 6.3) |
| pulse__phone__volar_wrist__POS__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__POS__kurtosis] |
| pulse__phone__volar_wrist__POS__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__POS__n_windows]: count |
| pulse__phone__volar_wrist__POS__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__POS__skewness] |
| pulse__phone__volar_wrist__POS__snr_db | pulse | phone | no | no | dB | POS on volar_wrist: snr_db (section 6.3) |
| pulse__phone__volar_wrist__POS__sqi | pulse | phone | no | no | 0..1 | POS on volar_wrist: sqi (section 6.3) |
| pulse__phone__volar_wrist__POS__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__POS__template_corr] |
| pulse__phone__whole_palm__2SR__hr_bpm | pulse | phone | no | no | bpm | 2SR on whole_palm: hr_bpm (section 6.3) |
| pulse__phone__whole_palm__2SR__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__2SR__kurtosis] |
| pulse__phone__whole_palm__2SR__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__2SR__n_windows]: count |
| pulse__phone__whole_palm__2SR__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__2SR__skewness] |
| pulse__phone__whole_palm__2SR__snr_db | pulse | phone | no | no | dB | 2SR on whole_palm: snr_db (section 6.3) |
| pulse__phone__whole_palm__2SR__sqi | pulse | phone | no | no | 0..1 | 2SR on whole_palm: sqi (section 6.3) |
| pulse__phone__whole_palm__2SR__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__2SR__template_corr] |
| pulse__phone__whole_palm__CHROM__hr_bpm | pulse | phone | no | no | bpm | CHROM on whole_palm: hr_bpm (section 6.3) |
| pulse__phone__whole_palm__CHROM__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__CHROM__kurtosis] |
| pulse__phone__whole_palm__CHROM__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__CHROM__n_windows]: count |
| pulse__phone__whole_palm__CHROM__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__CHROM__skewness] |
| pulse__phone__whole_palm__CHROM__snr_db | pulse | phone | no | no | dB | CHROM on whole_palm: snr_db (section 6.3) |
| pulse__phone__whole_palm__CHROM__sqi | pulse | phone | no | no | 0..1 | CHROM on whole_palm: sqi (section 6.3) |
| pulse__phone__whole_palm__CHROM__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__CHROM__template_corr] |
| pulse__phone__whole_palm__GREEN__hr_bpm | pulse | phone | no | no | bpm | GREEN on whole_palm: hr_bpm (section 6.3) |
| pulse__phone__whole_palm__GREEN__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__GREEN__kurtosis] |
| pulse__phone__whole_palm__GREEN__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__GREEN__n_windows]: count |
| pulse__phone__whole_palm__GREEN__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__GREEN__skewness] |
| pulse__phone__whole_palm__GREEN__snr_db | pulse | phone | no | no | dB | GREEN on whole_palm: snr_db (section 6.3) |
| pulse__phone__whole_palm__GREEN__sqi | pulse | phone | no | no | 0..1 | GREEN on whole_palm: sqi (section 6.3) |
| pulse__phone__whole_palm__GREEN__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__GREEN__template_corr] |
| pulse__phone__whole_palm__ICA__hr_bpm | pulse | phone | no | no | bpm | ICA on whole_palm: hr_bpm (section 6.3) |
| pulse__phone__whole_palm__ICA__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__ICA__kurtosis] |
| pulse__phone__whole_palm__ICA__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__ICA__n_windows]: count |
| pulse__phone__whole_palm__ICA__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__ICA__skewness] |
| pulse__phone__whole_palm__ICA__snr_db | pulse | phone | no | no | dB | ICA on whole_palm: snr_db (section 6.3) |
| pulse__phone__whole_palm__ICA__sqi | pulse | phone | no | no | 0..1 | ICA on whole_palm: sqi (section 6.3) |
| pulse__phone__whole_palm__ICA__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__ICA__template_corr] |
| pulse__phone__whole_palm__LGI__hr_bpm | pulse | phone | no | no | bpm | LGI on whole_palm: hr_bpm (section 6.3) |
| pulse__phone__whole_palm__LGI__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__LGI__kurtosis] |
| pulse__phone__whole_palm__LGI__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__LGI__n_windows]: count |
| pulse__phone__whole_palm__LGI__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__LGI__skewness] |
| pulse__phone__whole_palm__LGI__snr_db | pulse | phone | no | no | dB | LGI on whole_palm: snr_db (section 6.3) |
| pulse__phone__whole_palm__LGI__sqi | pulse | phone | no | no | 0..1 | LGI on whole_palm: sqi (section 6.3) |
| pulse__phone__whole_palm__LGI__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__LGI__template_corr] |
| pulse__phone__whole_palm__OMIT__hr_bpm | pulse | phone | no | no | bpm | OMIT on whole_palm: hr_bpm (section 6.3) |
| pulse__phone__whole_palm__OMIT__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__OMIT__kurtosis] |
| pulse__phone__whole_palm__OMIT__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__OMIT__n_windows]: count |
| pulse__phone__whole_palm__OMIT__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__OMIT__skewness] |
| pulse__phone__whole_palm__OMIT__snr_db | pulse | phone | no | no | dB | OMIT on whole_palm: snr_db (section 6.3) |
| pulse__phone__whole_palm__OMIT__sqi | pulse | phone | no | no | 0..1 | OMIT on whole_palm: sqi (section 6.3) |
| pulse__phone__whole_palm__OMIT__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__OMIT__template_corr] |
| pulse__phone__whole_palm__PBV__hr_bpm | pulse | phone | no | no | bpm | PBV on whole_palm: hr_bpm (section 6.3) |
| pulse__phone__whole_palm__PBV__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__PBV__kurtosis] |
| pulse__phone__whole_palm__PBV__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__PBV__n_windows]: count |
| pulse__phone__whole_palm__PBV__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__PBV__skewness] |
| pulse__phone__whole_palm__PBV__snr_db | pulse | phone | no | no | dB | PBV on whole_palm: snr_db (section 6.3) |
| pulse__phone__whole_palm__PBV__sqi | pulse | phone | no | no | 0..1 | PBV on whole_palm: sqi (section 6.3) |
| pulse__phone__whole_palm__PBV__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__PBV__template_corr] |
| pulse__phone__whole_palm__PCA__hr_bpm | pulse | phone | no | no | bpm | PCA on whole_palm: hr_bpm (section 6.3) |
| pulse__phone__whole_palm__PCA__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__PCA__kurtosis] |
| pulse__phone__whole_palm__PCA__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__PCA__n_windows]: count |
| pulse__phone__whole_palm__PCA__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__PCA__skewness] |
| pulse__phone__whole_palm__PCA__snr_db | pulse | phone | no | no | dB | PCA on whole_palm: snr_db (section 6.3) |
| pulse__phone__whole_palm__PCA__sqi | pulse | phone | no | no | 0..1 | PCA on whole_palm: sqi (section 6.3) |
| pulse__phone__whole_palm__PCA__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__PCA__template_corr] |
| pulse__phone__whole_palm__POS__hr_bpm | pulse | phone | no | no | bpm | POS on whole_palm: hr_bpm (section 6.3) |
| pulse__phone__whole_palm__POS__kurtosis | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__POS__kurtosis] |
| pulse__phone__whole_palm__POS__n_windows | pulse | phone | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__POS__n_windows]: count |
| pulse__phone__whole_palm__POS__skewness | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__POS__skewness] |
| pulse__phone__whole_palm__POS__snr_db | pulse | phone | no | no | dB | POS on whole_palm: snr_db (section 6.3) |
| pulse__phone__whole_palm__POS__sqi | pulse | phone | no | no | 0..1 | POS on whole_palm: sqi (section 6.3) |
| pulse__phone__whole_palm__POS__template_corr | pulse | phone | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__POS__template_corr] |
| pulse__pi__best | pulse | pi | no | yes | label | best method__roi by SQI |
| pulse__pi__best__hr_bpm | pulse | pi | no | yes | bpm | pulse extraction summary per method and ROI (protocol 6.3) [best__hr_bpm]: pulse rate of the dominant spectral peak |
| pulse__pi__best__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [best__kurtosis] |
| pulse__pi__best__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [best__n_windows]: count |
| pulse__pi__best__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [best__skewness] |
| pulse__pi__best__snr_db | pulse | pi | no | yes | dB | pulse extraction summary per method and ROI (protocol 6.3) [best__snr_db]: SNR of the dominant band peak versus the rest of the band |
| pulse__pi__best__sqi | pulse | pi | no | yes | 0..1 | pulse extraction summary per method and ROI (protocol 6.3) [best__sqi]: signal quality index (snr_band, CONTRACTS section 6) |
| pulse__pi__best__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [best__template_corr] |
| pulse__pi__central_palm__2SR__hr_bpm | pulse | pi | no | yes | bpm | 2SR on central_palm: hr_bpm (section 6.3) |
| pulse__pi__central_palm__2SR__snr_db | pulse | pi | no | yes | dB | 2SR on central_palm: snr_db (section 6.3) |
| pulse__pi__central_palm__2SR__sqi | pulse | pi | no | yes | 0..1 | 2SR on central_palm: sqi (section 6.3) |
| pulse__pi__central_palm__CHROM__hr_bpm | pulse | pi | no | yes | bpm | CHROM on central_palm: hr_bpm (section 6.3) |
| pulse__pi__central_palm__CHROM__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__CHROM__kurtosis] |
| pulse__pi__central_palm__CHROM__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__CHROM__n_windows]: count |
| pulse__pi__central_palm__CHROM__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__CHROM__skewness] |
| pulse__pi__central_palm__CHROM__snr_db | pulse | pi | no | yes | dB | CHROM on central_palm: snr_db (section 6.3) |
| pulse__pi__central_palm__CHROM__sqi | pulse | pi | no | yes | 0..1 | CHROM on central_palm: sqi (section 6.3) |
| pulse__pi__central_palm__CHROM__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__CHROM__template_corr] |
| pulse__pi__central_palm__GREEN__hr_bpm | pulse | pi | no | yes | bpm | GREEN on central_palm: hr_bpm (section 6.3) |
| pulse__pi__central_palm__GREEN__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__GREEN__kurtosis] |
| pulse__pi__central_palm__GREEN__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__GREEN__n_windows]: count |
| pulse__pi__central_palm__GREEN__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__GREEN__skewness] |
| pulse__pi__central_palm__GREEN__snr_db | pulse | pi | no | yes | dB | GREEN on central_palm: snr_db (section 6.3) |
| pulse__pi__central_palm__GREEN__sqi | pulse | pi | no | yes | 0..1 | GREEN on central_palm: sqi (section 6.3) |
| pulse__pi__central_palm__GREEN__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__GREEN__template_corr] |
| pulse__pi__central_palm__ICA__hr_bpm | pulse | pi | no | yes | bpm | ICA on central_palm: hr_bpm (section 6.3) |
| pulse__pi__central_palm__ICA__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__ICA__kurtosis] |
| pulse__pi__central_palm__ICA__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__ICA__n_windows]: count |
| pulse__pi__central_palm__ICA__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__ICA__skewness] |
| pulse__pi__central_palm__ICA__snr_db | pulse | pi | no | yes | dB | ICA on central_palm: snr_db (section 6.3) |
| pulse__pi__central_palm__ICA__sqi | pulse | pi | no | yes | 0..1 | ICA on central_palm: sqi (section 6.3) |
| pulse__pi__central_palm__ICA__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__ICA__template_corr] |
| pulse__pi__central_palm__LGI__hr_bpm | pulse | pi | no | yes | bpm | LGI on central_palm: hr_bpm (section 6.3) |
| pulse__pi__central_palm__LGI__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__LGI__kurtosis] |
| pulse__pi__central_palm__LGI__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__LGI__n_windows]: count |
| pulse__pi__central_palm__LGI__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__LGI__skewness] |
| pulse__pi__central_palm__LGI__snr_db | pulse | pi | no | yes | dB | LGI on central_palm: snr_db (section 6.3) |
| pulse__pi__central_palm__LGI__sqi | pulse | pi | no | yes | 0..1 | LGI on central_palm: sqi (section 6.3) |
| pulse__pi__central_palm__LGI__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__LGI__template_corr] |
| pulse__pi__central_palm__OMIT__hr_bpm | pulse | pi | no | yes | bpm | OMIT on central_palm: hr_bpm (section 6.3) |
| pulse__pi__central_palm__OMIT__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__OMIT__kurtosis] |
| pulse__pi__central_palm__OMIT__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__OMIT__n_windows]: count |
| pulse__pi__central_palm__OMIT__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__OMIT__skewness] |
| pulse__pi__central_palm__OMIT__snr_db | pulse | pi | no | yes | dB | OMIT on central_palm: snr_db (section 6.3) |
| pulse__pi__central_palm__OMIT__sqi | pulse | pi | no | yes | 0..1 | OMIT on central_palm: sqi (section 6.3) |
| pulse__pi__central_palm__OMIT__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__OMIT__template_corr] |
| pulse__pi__central_palm__PBV__hr_bpm | pulse | pi | no | yes | bpm | PBV on central_palm: hr_bpm (section 6.3) |
| pulse__pi__central_palm__PBV__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__PBV__kurtosis] |
| pulse__pi__central_palm__PBV__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__PBV__n_windows]: count |
| pulse__pi__central_palm__PBV__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__PBV__skewness] |
| pulse__pi__central_palm__PBV__snr_db | pulse | pi | no | yes | dB | PBV on central_palm: snr_db (section 6.3) |
| pulse__pi__central_palm__PBV__sqi | pulse | pi | no | yes | 0..1 | PBV on central_palm: sqi (section 6.3) |
| pulse__pi__central_palm__PBV__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__PBV__template_corr] |
| pulse__pi__central_palm__PCA__hr_bpm | pulse | pi | no | yes | bpm | PCA on central_palm: hr_bpm (section 6.3) |
| pulse__pi__central_palm__PCA__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__PCA__kurtosis] |
| pulse__pi__central_palm__PCA__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__PCA__n_windows]: count |
| pulse__pi__central_palm__PCA__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__PCA__skewness] |
| pulse__pi__central_palm__PCA__snr_db | pulse | pi | no | yes | dB | PCA on central_palm: snr_db (section 6.3) |
| pulse__pi__central_palm__PCA__sqi | pulse | pi | no | yes | 0..1 | PCA on central_palm: sqi (section 6.3) |
| pulse__pi__central_palm__PCA__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__PCA__template_corr] |
| pulse__pi__central_palm__POS__hr_bpm | pulse | pi | no | yes | bpm | POS on central_palm: hr_bpm (section 6.3) |
| pulse__pi__central_palm__POS__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__POS__kurtosis] |
| pulse__pi__central_palm__POS__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__POS__n_windows]: count |
| pulse__pi__central_palm__POS__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__POS__skewness] |
| pulse__pi__central_palm__POS__snr_db | pulse | pi | no | yes | dB | POS on central_palm: snr_db (section 6.3) |
| pulse__pi__central_palm__POS__sqi | pulse | pi | no | yes | 0..1 | POS on central_palm: sqi (section 6.3) |
| pulse__pi__central_palm__POS__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__POS__template_corr] |
| pulse__pi__fused__2SR__hr_bpm | pulse | pi | no | yes | bpm | 2SR on fused: hr_bpm (section 6.3) |
| pulse__pi__fused__2SR__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__2SR__kurtosis] |
| pulse__pi__fused__2SR__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [fused__2SR__n_windows]: count |
| pulse__pi__fused__2SR__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__2SR__skewness] |
| pulse__pi__fused__2SR__snr_db | pulse | pi | no | yes | dB | 2SR on fused: snr_db (section 6.3) |
| pulse__pi__fused__2SR__sqi | pulse | pi | no | yes | 0..1 | 2SR on fused: sqi (section 6.3) |
| pulse__pi__fused__2SR__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__2SR__template_corr] |
| pulse__pi__fused__CHROM__hr_bpm | pulse | pi | no | yes | bpm | CHROM on fused: hr_bpm (section 6.3) |
| pulse__pi__fused__CHROM__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__CHROM__kurtosis] |
| pulse__pi__fused__CHROM__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [fused__CHROM__n_windows]: count |
| pulse__pi__fused__CHROM__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__CHROM__skewness] |
| pulse__pi__fused__CHROM__snr_db | pulse | pi | no | yes | dB | CHROM on fused: snr_db (section 6.3) |
| pulse__pi__fused__CHROM__sqi | pulse | pi | no | yes | 0..1 | CHROM on fused: sqi (section 6.3) |
| pulse__pi__fused__CHROM__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__CHROM__template_corr] |
| pulse__pi__fused__GREEN__hr_bpm | pulse | pi | no | yes | bpm | GREEN on fused: hr_bpm (section 6.3) |
| pulse__pi__fused__GREEN__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__GREEN__kurtosis] |
| pulse__pi__fused__GREEN__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [fused__GREEN__n_windows]: count |
| pulse__pi__fused__GREEN__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__GREEN__skewness] |
| pulse__pi__fused__GREEN__snr_db | pulse | pi | no | yes | dB | GREEN on fused: snr_db (section 6.3) |
| pulse__pi__fused__GREEN__sqi | pulse | pi | no | yes | 0..1 | GREEN on fused: sqi (section 6.3) |
| pulse__pi__fused__GREEN__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__GREEN__template_corr] |
| pulse__pi__fused__ICA__hr_bpm | pulse | pi | no | yes | bpm | ICA on fused: hr_bpm (section 6.3) |
| pulse__pi__fused__ICA__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__ICA__kurtosis] |
| pulse__pi__fused__ICA__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [fused__ICA__n_windows]: count |
| pulse__pi__fused__ICA__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__ICA__skewness] |
| pulse__pi__fused__ICA__snr_db | pulse | pi | no | yes | dB | ICA on fused: snr_db (section 6.3) |
| pulse__pi__fused__ICA__sqi | pulse | pi | no | yes | 0..1 | ICA on fused: sqi (section 6.3) |
| pulse__pi__fused__ICA__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__ICA__template_corr] |
| pulse__pi__fused__LGI__hr_bpm | pulse | pi | no | yes | bpm | LGI on fused: hr_bpm (section 6.3) |
| pulse__pi__fused__LGI__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__LGI__kurtosis] |
| pulse__pi__fused__LGI__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [fused__LGI__n_windows]: count |
| pulse__pi__fused__LGI__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__LGI__skewness] |
| pulse__pi__fused__LGI__snr_db | pulse | pi | no | yes | dB | LGI on fused: snr_db (section 6.3) |
| pulse__pi__fused__LGI__sqi | pulse | pi | no | yes | 0..1 | LGI on fused: sqi (section 6.3) |
| pulse__pi__fused__LGI__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__LGI__template_corr] |
| pulse__pi__fused__OMIT__hr_bpm | pulse | pi | no | yes | bpm | OMIT on fused: hr_bpm (section 6.3) |
| pulse__pi__fused__OMIT__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__OMIT__kurtosis] |
| pulse__pi__fused__OMIT__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [fused__OMIT__n_windows]: count |
| pulse__pi__fused__OMIT__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__OMIT__skewness] |
| pulse__pi__fused__OMIT__snr_db | pulse | pi | no | yes | dB | OMIT on fused: snr_db (section 6.3) |
| pulse__pi__fused__OMIT__sqi | pulse | pi | no | yes | 0..1 | OMIT on fused: sqi (section 6.3) |
| pulse__pi__fused__OMIT__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__OMIT__template_corr] |
| pulse__pi__fused__PBV__hr_bpm | pulse | pi | no | yes | bpm | PBV on fused: hr_bpm (section 6.3) |
| pulse__pi__fused__PBV__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__PBV__kurtosis] |
| pulse__pi__fused__PBV__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [fused__PBV__n_windows]: count |
| pulse__pi__fused__PBV__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__PBV__skewness] |
| pulse__pi__fused__PBV__snr_db | pulse | pi | no | yes | dB | PBV on fused: snr_db (section 6.3) |
| pulse__pi__fused__PBV__sqi | pulse | pi | no | yes | 0..1 | PBV on fused: sqi (section 6.3) |
| pulse__pi__fused__PBV__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__PBV__template_corr] |
| pulse__pi__fused__PCA__hr_bpm | pulse | pi | no | yes | bpm | PCA on fused: hr_bpm (section 6.3) |
| pulse__pi__fused__PCA__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__PCA__kurtosis] |
| pulse__pi__fused__PCA__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [fused__PCA__n_windows]: count |
| pulse__pi__fused__PCA__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__PCA__skewness] |
| pulse__pi__fused__PCA__snr_db | pulse | pi | no | yes | dB | PCA on fused: snr_db (section 6.3) |
| pulse__pi__fused__PCA__sqi | pulse | pi | no | yes | 0..1 | PCA on fused: sqi (section 6.3) |
| pulse__pi__fused__PCA__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__PCA__template_corr] |
| pulse__pi__fused__POS__hr_bpm | pulse | pi | no | yes | bpm | POS on fused: hr_bpm (section 6.3) |
| pulse__pi__fused__POS__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__POS__kurtosis] |
| pulse__pi__fused__POS__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [fused__POS__n_windows]: count |
| pulse__pi__fused__POS__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__POS__skewness] |
| pulse__pi__fused__POS__snr_db | pulse | pi | no | yes | dB | POS on fused: snr_db (section 6.3) |
| pulse__pi__fused__POS__sqi | pulse | pi | no | yes | 0..1 | POS on fused: sqi (section 6.3) |
| pulse__pi__fused__POS__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__POS__template_corr] |
| pulse__pi__fused__hr_bpm | pulse | pi | no | yes | bpm | pulse extraction summary per method and ROI (protocol 6.3) [fused__hr_bpm]: pulse rate of the dominant spectral peak |
| pulse__pi__fused__method | pulse | pi | no | yes | label | pulse extraction summary per method and ROI (protocol 6.3) [fused__method]: method name |
| pulse__pi__fused__snr_db | pulse | pi | no | yes | dB | pulse extraction summary per method and ROI (protocol 6.3) [fused__snr_db]: SNR of the dominant band peak versus the rest of the band |
| pulse__pi__fused__sqi | pulse | pi | no | yes | 0..1 | pulse extraction summary per method and ROI (protocol 6.3) [fused__sqi]: signal quality index (snr_band, CONTRACTS section 6) |
| pulse__pi__hypothenar__2SR__hr_bpm | pulse | pi | no | yes | bpm | 2SR on hypothenar: hr_bpm (section 6.3) |
| pulse__pi__hypothenar__2SR__snr_db | pulse | pi | no | yes | dB | 2SR on hypothenar: snr_db (section 6.3) |
| pulse__pi__hypothenar__2SR__sqi | pulse | pi | no | yes | 0..1 | 2SR on hypothenar: sqi (section 6.3) |
| pulse__pi__hypothenar__CHROM__hr_bpm | pulse | pi | no | yes | bpm | CHROM on hypothenar: hr_bpm (section 6.3) |
| pulse__pi__hypothenar__CHROM__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__CHROM__kurtosis] |
| pulse__pi__hypothenar__CHROM__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__CHROM__n_windows]: count |
| pulse__pi__hypothenar__CHROM__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__CHROM__skewness] |
| pulse__pi__hypothenar__CHROM__snr_db | pulse | pi | no | yes | dB | CHROM on hypothenar: snr_db (section 6.3) |
| pulse__pi__hypothenar__CHROM__sqi | pulse | pi | no | yes | 0..1 | CHROM on hypothenar: sqi (section 6.3) |
| pulse__pi__hypothenar__CHROM__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__CHROM__template_corr] |
| pulse__pi__hypothenar__GREEN__hr_bpm | pulse | pi | no | yes | bpm | GREEN on hypothenar: hr_bpm (section 6.3) |
| pulse__pi__hypothenar__GREEN__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__GREEN__kurtosis] |
| pulse__pi__hypothenar__GREEN__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__GREEN__n_windows]: count |
| pulse__pi__hypothenar__GREEN__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__GREEN__skewness] |
| pulse__pi__hypothenar__GREEN__snr_db | pulse | pi | no | yes | dB | GREEN on hypothenar: snr_db (section 6.3) |
| pulse__pi__hypothenar__GREEN__sqi | pulse | pi | no | yes | 0..1 | GREEN on hypothenar: sqi (section 6.3) |
| pulse__pi__hypothenar__GREEN__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__GREEN__template_corr] |
| pulse__pi__hypothenar__ICA__hr_bpm | pulse | pi | no | yes | bpm | ICA on hypothenar: hr_bpm (section 6.3) |
| pulse__pi__hypothenar__ICA__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__ICA__kurtosis] |
| pulse__pi__hypothenar__ICA__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__ICA__n_windows]: count |
| pulse__pi__hypothenar__ICA__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__ICA__skewness] |
| pulse__pi__hypothenar__ICA__snr_db | pulse | pi | no | yes | dB | ICA on hypothenar: snr_db (section 6.3) |
| pulse__pi__hypothenar__ICA__sqi | pulse | pi | no | yes | 0..1 | ICA on hypothenar: sqi (section 6.3) |
| pulse__pi__hypothenar__ICA__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__ICA__template_corr] |
| pulse__pi__hypothenar__LGI__hr_bpm | pulse | pi | no | yes | bpm | LGI on hypothenar: hr_bpm (section 6.3) |
| pulse__pi__hypothenar__LGI__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__LGI__kurtosis] |
| pulse__pi__hypothenar__LGI__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__LGI__n_windows]: count |
| pulse__pi__hypothenar__LGI__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__LGI__skewness] |
| pulse__pi__hypothenar__LGI__snr_db | pulse | pi | no | yes | dB | LGI on hypothenar: snr_db (section 6.3) |
| pulse__pi__hypothenar__LGI__sqi | pulse | pi | no | yes | 0..1 | LGI on hypothenar: sqi (section 6.3) |
| pulse__pi__hypothenar__LGI__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__LGI__template_corr] |
| pulse__pi__hypothenar__OMIT__hr_bpm | pulse | pi | no | yes | bpm | OMIT on hypothenar: hr_bpm (section 6.3) |
| pulse__pi__hypothenar__OMIT__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__OMIT__kurtosis] |
| pulse__pi__hypothenar__OMIT__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__OMIT__n_windows]: count |
| pulse__pi__hypothenar__OMIT__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__OMIT__skewness] |
| pulse__pi__hypothenar__OMIT__snr_db | pulse | pi | no | yes | dB | OMIT on hypothenar: snr_db (section 6.3) |
| pulse__pi__hypothenar__OMIT__sqi | pulse | pi | no | yes | 0..1 | OMIT on hypothenar: sqi (section 6.3) |
| pulse__pi__hypothenar__OMIT__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__OMIT__template_corr] |
| pulse__pi__hypothenar__PBV__hr_bpm | pulse | pi | no | yes | bpm | PBV on hypothenar: hr_bpm (section 6.3) |
| pulse__pi__hypothenar__PBV__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__PBV__kurtosis] |
| pulse__pi__hypothenar__PBV__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__PBV__n_windows]: count |
| pulse__pi__hypothenar__PBV__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__PBV__skewness] |
| pulse__pi__hypothenar__PBV__snr_db | pulse | pi | no | yes | dB | PBV on hypothenar: snr_db (section 6.3) |
| pulse__pi__hypothenar__PBV__sqi | pulse | pi | no | yes | 0..1 | PBV on hypothenar: sqi (section 6.3) |
| pulse__pi__hypothenar__PBV__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__PBV__template_corr] |
| pulse__pi__hypothenar__PCA__hr_bpm | pulse | pi | no | yes | bpm | PCA on hypothenar: hr_bpm (section 6.3) |
| pulse__pi__hypothenar__PCA__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__PCA__kurtosis] |
| pulse__pi__hypothenar__PCA__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__PCA__n_windows]: count |
| pulse__pi__hypothenar__PCA__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__PCA__skewness] |
| pulse__pi__hypothenar__PCA__snr_db | pulse | pi | no | yes | dB | PCA on hypothenar: snr_db (section 6.3) |
| pulse__pi__hypothenar__PCA__sqi | pulse | pi | no | yes | 0..1 | PCA on hypothenar: sqi (section 6.3) |
| pulse__pi__hypothenar__PCA__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__PCA__template_corr] |
| pulse__pi__hypothenar__POS__hr_bpm | pulse | pi | no | yes | bpm | POS on hypothenar: hr_bpm (section 6.3) |
| pulse__pi__hypothenar__POS__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__POS__kurtosis] |
| pulse__pi__hypothenar__POS__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__POS__n_windows]: count |
| pulse__pi__hypothenar__POS__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__POS__skewness] |
| pulse__pi__hypothenar__POS__snr_db | pulse | pi | no | yes | dB | POS on hypothenar: snr_db (section 6.3) |
| pulse__pi__hypothenar__POS__sqi | pulse | pi | no | yes | 0..1 | POS on hypothenar: sqi (section 6.3) |
| pulse__pi__hypothenar__POS__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__POS__template_corr] |
| pulse__pi__mid_phalanges__2SR__hr_bpm | pulse | pi | no | yes | bpm | 2SR on mid_phalanges: hr_bpm (section 6.3) |
| pulse__pi__mid_phalanges__2SR__snr_db | pulse | pi | no | yes | dB | 2SR on mid_phalanges: snr_db (section 6.3) |
| pulse__pi__mid_phalanges__2SR__sqi | pulse | pi | no | yes | 0..1 | 2SR on mid_phalanges: sqi (section 6.3) |
| pulse__pi__mid_phalanges__CHROM__hr_bpm | pulse | pi | no | yes | bpm | CHROM on mid_phalanges: hr_bpm (section 6.3) |
| pulse__pi__mid_phalanges__CHROM__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__CHROM__kurtosis] |
| pulse__pi__mid_phalanges__CHROM__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__CHROM__n_windows]: count |
| pulse__pi__mid_phalanges__CHROM__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__CHROM__skewness] |
| pulse__pi__mid_phalanges__CHROM__snr_db | pulse | pi | no | yes | dB | CHROM on mid_phalanges: snr_db (section 6.3) |
| pulse__pi__mid_phalanges__CHROM__sqi | pulse | pi | no | yes | 0..1 | CHROM on mid_phalanges: sqi (section 6.3) |
| pulse__pi__mid_phalanges__CHROM__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__CHROM__template_corr] |
| pulse__pi__mid_phalanges__GREEN__hr_bpm | pulse | pi | no | yes | bpm | GREEN on mid_phalanges: hr_bpm (section 6.3) |
| pulse__pi__mid_phalanges__GREEN__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__GREEN__kurtosis] |
| pulse__pi__mid_phalanges__GREEN__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__GREEN__n_windows]: count |
| pulse__pi__mid_phalanges__GREEN__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__GREEN__skewness] |
| pulse__pi__mid_phalanges__GREEN__snr_db | pulse | pi | no | yes | dB | GREEN on mid_phalanges: snr_db (section 6.3) |
| pulse__pi__mid_phalanges__GREEN__sqi | pulse | pi | no | yes | 0..1 | GREEN on mid_phalanges: sqi (section 6.3) |
| pulse__pi__mid_phalanges__GREEN__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__GREEN__template_corr] |
| pulse__pi__mid_phalanges__ICA__hr_bpm | pulse | pi | no | yes | bpm | ICA on mid_phalanges: hr_bpm (section 6.3) |
| pulse__pi__mid_phalanges__ICA__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__ICA__kurtosis] |
| pulse__pi__mid_phalanges__ICA__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__ICA__n_windows]: count |
| pulse__pi__mid_phalanges__ICA__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__ICA__skewness] |
| pulse__pi__mid_phalanges__ICA__snr_db | pulse | pi | no | yes | dB | ICA on mid_phalanges: snr_db (section 6.3) |
| pulse__pi__mid_phalanges__ICA__sqi | pulse | pi | no | yes | 0..1 | ICA on mid_phalanges: sqi (section 6.3) |
| pulse__pi__mid_phalanges__ICA__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__ICA__template_corr] |
| pulse__pi__mid_phalanges__LGI__hr_bpm | pulse | pi | no | yes | bpm | LGI on mid_phalanges: hr_bpm (section 6.3) |
| pulse__pi__mid_phalanges__LGI__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__LGI__kurtosis] |
| pulse__pi__mid_phalanges__LGI__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__LGI__n_windows]: count |
| pulse__pi__mid_phalanges__LGI__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__LGI__skewness] |
| pulse__pi__mid_phalanges__LGI__snr_db | pulse | pi | no | yes | dB | LGI on mid_phalanges: snr_db (section 6.3) |
| pulse__pi__mid_phalanges__LGI__sqi | pulse | pi | no | yes | 0..1 | LGI on mid_phalanges: sqi (section 6.3) |
| pulse__pi__mid_phalanges__LGI__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__LGI__template_corr] |
| pulse__pi__mid_phalanges__OMIT__hr_bpm | pulse | pi | no | yes | bpm | OMIT on mid_phalanges: hr_bpm (section 6.3) |
| pulse__pi__mid_phalanges__OMIT__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__OMIT__kurtosis] |
| pulse__pi__mid_phalanges__OMIT__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__OMIT__n_windows]: count |
| pulse__pi__mid_phalanges__OMIT__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__OMIT__skewness] |
| pulse__pi__mid_phalanges__OMIT__snr_db | pulse | pi | no | yes | dB | OMIT on mid_phalanges: snr_db (section 6.3) |
| pulse__pi__mid_phalanges__OMIT__sqi | pulse | pi | no | yes | 0..1 | OMIT on mid_phalanges: sqi (section 6.3) |
| pulse__pi__mid_phalanges__OMIT__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__OMIT__template_corr] |
| pulse__pi__mid_phalanges__PBV__hr_bpm | pulse | pi | no | yes | bpm | PBV on mid_phalanges: hr_bpm (section 6.3) |
| pulse__pi__mid_phalanges__PBV__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__PBV__kurtosis] |
| pulse__pi__mid_phalanges__PBV__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__PBV__n_windows]: count |
| pulse__pi__mid_phalanges__PBV__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__PBV__skewness] |
| pulse__pi__mid_phalanges__PBV__snr_db | pulse | pi | no | yes | dB | PBV on mid_phalanges: snr_db (section 6.3) |
| pulse__pi__mid_phalanges__PBV__sqi | pulse | pi | no | yes | 0..1 | PBV on mid_phalanges: sqi (section 6.3) |
| pulse__pi__mid_phalanges__PBV__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__PBV__template_corr] |
| pulse__pi__mid_phalanges__PCA__hr_bpm | pulse | pi | no | yes | bpm | PCA on mid_phalanges: hr_bpm (section 6.3) |
| pulse__pi__mid_phalanges__PCA__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__PCA__kurtosis] |
| pulse__pi__mid_phalanges__PCA__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__PCA__n_windows]: count |
| pulse__pi__mid_phalanges__PCA__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__PCA__skewness] |
| pulse__pi__mid_phalanges__PCA__snr_db | pulse | pi | no | yes | dB | PCA on mid_phalanges: snr_db (section 6.3) |
| pulse__pi__mid_phalanges__PCA__sqi | pulse | pi | no | yes | 0..1 | PCA on mid_phalanges: sqi (section 6.3) |
| pulse__pi__mid_phalanges__PCA__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__PCA__template_corr] |
| pulse__pi__mid_phalanges__POS__hr_bpm | pulse | pi | no | yes | bpm | POS on mid_phalanges: hr_bpm (section 6.3) |
| pulse__pi__mid_phalanges__POS__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__POS__kurtosis] |
| pulse__pi__mid_phalanges__POS__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__POS__n_windows]: count |
| pulse__pi__mid_phalanges__POS__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__POS__skewness] |
| pulse__pi__mid_phalanges__POS__snr_db | pulse | pi | no | yes | dB | POS on mid_phalanges: snr_db (section 6.3) |
| pulse__pi__mid_phalanges__POS__sqi | pulse | pi | no | yes | 0..1 | POS on mid_phalanges: sqi (section 6.3) |
| pulse__pi__mid_phalanges__POS__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__POS__template_corr] |
| pulse__pi__pad_index__2SR__hr_bpm | pulse | pi | no | yes | bpm | 2SR on pad_index: hr_bpm (section 6.3) |
| pulse__pi__pad_index__2SR__snr_db | pulse | pi | no | yes | dB | 2SR on pad_index: snr_db (section 6.3) |
| pulse__pi__pad_index__2SR__sqi | pulse | pi | no | yes | 0..1 | 2SR on pad_index: sqi (section 6.3) |
| pulse__pi__pad_index__CHROM__hr_bpm | pulse | pi | no | yes | bpm | CHROM on pad_index: hr_bpm (section 6.3) |
| pulse__pi__pad_index__CHROM__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__CHROM__kurtosis] |
| pulse__pi__pad_index__CHROM__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__CHROM__n_windows]: count |
| pulse__pi__pad_index__CHROM__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__CHROM__skewness] |
| pulse__pi__pad_index__CHROM__snr_db | pulse | pi | no | yes | dB | CHROM on pad_index: snr_db (section 6.3) |
| pulse__pi__pad_index__CHROM__sqi | pulse | pi | no | yes | 0..1 | CHROM on pad_index: sqi (section 6.3) |
| pulse__pi__pad_index__CHROM__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__CHROM__template_corr] |
| pulse__pi__pad_index__GREEN__hr_bpm | pulse | pi | no | yes | bpm | GREEN on pad_index: hr_bpm (section 6.3) |
| pulse__pi__pad_index__GREEN__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__GREEN__kurtosis] |
| pulse__pi__pad_index__GREEN__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__GREEN__n_windows]: count |
| pulse__pi__pad_index__GREEN__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__GREEN__skewness] |
| pulse__pi__pad_index__GREEN__snr_db | pulse | pi | no | yes | dB | GREEN on pad_index: snr_db (section 6.3) |
| pulse__pi__pad_index__GREEN__sqi | pulse | pi | no | yes | 0..1 | GREEN on pad_index: sqi (section 6.3) |
| pulse__pi__pad_index__GREEN__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__GREEN__template_corr] |
| pulse__pi__pad_index__ICA__hr_bpm | pulse | pi | no | yes | bpm | ICA on pad_index: hr_bpm (section 6.3) |
| pulse__pi__pad_index__ICA__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__ICA__kurtosis] |
| pulse__pi__pad_index__ICA__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__ICA__n_windows]: count |
| pulse__pi__pad_index__ICA__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__ICA__skewness] |
| pulse__pi__pad_index__ICA__snr_db | pulse | pi | no | yes | dB | ICA on pad_index: snr_db (section 6.3) |
| pulse__pi__pad_index__ICA__sqi | pulse | pi | no | yes | 0..1 | ICA on pad_index: sqi (section 6.3) |
| pulse__pi__pad_index__ICA__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__ICA__template_corr] |
| pulse__pi__pad_index__LGI__hr_bpm | pulse | pi | no | yes | bpm | LGI on pad_index: hr_bpm (section 6.3) |
| pulse__pi__pad_index__LGI__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__LGI__kurtosis] |
| pulse__pi__pad_index__LGI__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__LGI__n_windows]: count |
| pulse__pi__pad_index__LGI__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__LGI__skewness] |
| pulse__pi__pad_index__LGI__snr_db | pulse | pi | no | yes | dB | LGI on pad_index: snr_db (section 6.3) |
| pulse__pi__pad_index__LGI__sqi | pulse | pi | no | yes | 0..1 | LGI on pad_index: sqi (section 6.3) |
| pulse__pi__pad_index__LGI__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__LGI__template_corr] |
| pulse__pi__pad_index__OMIT__hr_bpm | pulse | pi | no | yes | bpm | OMIT on pad_index: hr_bpm (section 6.3) |
| pulse__pi__pad_index__OMIT__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__OMIT__kurtosis] |
| pulse__pi__pad_index__OMIT__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__OMIT__n_windows]: count |
| pulse__pi__pad_index__OMIT__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__OMIT__skewness] |
| pulse__pi__pad_index__OMIT__snr_db | pulse | pi | no | yes | dB | OMIT on pad_index: snr_db (section 6.3) |
| pulse__pi__pad_index__OMIT__sqi | pulse | pi | no | yes | 0..1 | OMIT on pad_index: sqi (section 6.3) |
| pulse__pi__pad_index__OMIT__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__OMIT__template_corr] |
| pulse__pi__pad_index__PBV__hr_bpm | pulse | pi | no | yes | bpm | PBV on pad_index: hr_bpm (section 6.3) |
| pulse__pi__pad_index__PBV__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__PBV__kurtosis] |
| pulse__pi__pad_index__PBV__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__PBV__n_windows]: count |
| pulse__pi__pad_index__PBV__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__PBV__skewness] |
| pulse__pi__pad_index__PBV__snr_db | pulse | pi | no | yes | dB | PBV on pad_index: snr_db (section 6.3) |
| pulse__pi__pad_index__PBV__sqi | pulse | pi | no | yes | 0..1 | PBV on pad_index: sqi (section 6.3) |
| pulse__pi__pad_index__PBV__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__PBV__template_corr] |
| pulse__pi__pad_index__PCA__hr_bpm | pulse | pi | no | yes | bpm | PCA on pad_index: hr_bpm (section 6.3) |
| pulse__pi__pad_index__PCA__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__PCA__kurtosis] |
| pulse__pi__pad_index__PCA__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__PCA__n_windows]: count |
| pulse__pi__pad_index__PCA__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__PCA__skewness] |
| pulse__pi__pad_index__PCA__snr_db | pulse | pi | no | yes | dB | PCA on pad_index: snr_db (section 6.3) |
| pulse__pi__pad_index__PCA__sqi | pulse | pi | no | yes | 0..1 | PCA on pad_index: sqi (section 6.3) |
| pulse__pi__pad_index__PCA__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__PCA__template_corr] |
| pulse__pi__pad_index__POS__hr_bpm | pulse | pi | no | yes | bpm | POS on pad_index: hr_bpm (section 6.3) |
| pulse__pi__pad_index__POS__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__POS__kurtosis] |
| pulse__pi__pad_index__POS__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__POS__n_windows]: count |
| pulse__pi__pad_index__POS__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__POS__skewness] |
| pulse__pi__pad_index__POS__snr_db | pulse | pi | no | yes | dB | POS on pad_index: snr_db (section 6.3) |
| pulse__pi__pad_index__POS__sqi | pulse | pi | no | yes | 0..1 | POS on pad_index: sqi (section 6.3) |
| pulse__pi__pad_index__POS__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__POS__template_corr] |
| pulse__pi__pad_little__2SR__hr_bpm | pulse | pi | no | yes | bpm | 2SR on pad_little: hr_bpm (section 6.3) |
| pulse__pi__pad_little__2SR__snr_db | pulse | pi | no | yes | dB | 2SR on pad_little: snr_db (section 6.3) |
| pulse__pi__pad_little__2SR__sqi | pulse | pi | no | yes | 0..1 | 2SR on pad_little: sqi (section 6.3) |
| pulse__pi__pad_little__CHROM__hr_bpm | pulse | pi | no | yes | bpm | CHROM on pad_little: hr_bpm (section 6.3) |
| pulse__pi__pad_little__CHROM__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__CHROM__kurtosis] |
| pulse__pi__pad_little__CHROM__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__CHROM__n_windows]: count |
| pulse__pi__pad_little__CHROM__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__CHROM__skewness] |
| pulse__pi__pad_little__CHROM__snr_db | pulse | pi | no | yes | dB | CHROM on pad_little: snr_db (section 6.3) |
| pulse__pi__pad_little__CHROM__sqi | pulse | pi | no | yes | 0..1 | CHROM on pad_little: sqi (section 6.3) |
| pulse__pi__pad_little__CHROM__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__CHROM__template_corr] |
| pulse__pi__pad_little__GREEN__hr_bpm | pulse | pi | no | yes | bpm | GREEN on pad_little: hr_bpm (section 6.3) |
| pulse__pi__pad_little__GREEN__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__GREEN__kurtosis] |
| pulse__pi__pad_little__GREEN__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__GREEN__n_windows]: count |
| pulse__pi__pad_little__GREEN__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__GREEN__skewness] |
| pulse__pi__pad_little__GREEN__snr_db | pulse | pi | no | yes | dB | GREEN on pad_little: snr_db (section 6.3) |
| pulse__pi__pad_little__GREEN__sqi | pulse | pi | no | yes | 0..1 | GREEN on pad_little: sqi (section 6.3) |
| pulse__pi__pad_little__GREEN__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__GREEN__template_corr] |
| pulse__pi__pad_little__ICA__hr_bpm | pulse | pi | no | yes | bpm | ICA on pad_little: hr_bpm (section 6.3) |
| pulse__pi__pad_little__ICA__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__ICA__kurtosis] |
| pulse__pi__pad_little__ICA__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__ICA__n_windows]: count |
| pulse__pi__pad_little__ICA__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__ICA__skewness] |
| pulse__pi__pad_little__ICA__snr_db | pulse | pi | no | yes | dB | ICA on pad_little: snr_db (section 6.3) |
| pulse__pi__pad_little__ICA__sqi | pulse | pi | no | yes | 0..1 | ICA on pad_little: sqi (section 6.3) |
| pulse__pi__pad_little__ICA__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__ICA__template_corr] |
| pulse__pi__pad_little__LGI__hr_bpm | pulse | pi | no | yes | bpm | LGI on pad_little: hr_bpm (section 6.3) |
| pulse__pi__pad_little__LGI__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__LGI__kurtosis] |
| pulse__pi__pad_little__LGI__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__LGI__n_windows]: count |
| pulse__pi__pad_little__LGI__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__LGI__skewness] |
| pulse__pi__pad_little__LGI__snr_db | pulse | pi | no | yes | dB | LGI on pad_little: snr_db (section 6.3) |
| pulse__pi__pad_little__LGI__sqi | pulse | pi | no | yes | 0..1 | LGI on pad_little: sqi (section 6.3) |
| pulse__pi__pad_little__LGI__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__LGI__template_corr] |
| pulse__pi__pad_little__OMIT__hr_bpm | pulse | pi | no | yes | bpm | OMIT on pad_little: hr_bpm (section 6.3) |
| pulse__pi__pad_little__OMIT__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__OMIT__kurtosis] |
| pulse__pi__pad_little__OMIT__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__OMIT__n_windows]: count |
| pulse__pi__pad_little__OMIT__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__OMIT__skewness] |
| pulse__pi__pad_little__OMIT__snr_db | pulse | pi | no | yes | dB | OMIT on pad_little: snr_db (section 6.3) |
| pulse__pi__pad_little__OMIT__sqi | pulse | pi | no | yes | 0..1 | OMIT on pad_little: sqi (section 6.3) |
| pulse__pi__pad_little__OMIT__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__OMIT__template_corr] |
| pulse__pi__pad_little__PBV__hr_bpm | pulse | pi | no | yes | bpm | PBV on pad_little: hr_bpm (section 6.3) |
| pulse__pi__pad_little__PBV__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__PBV__kurtosis] |
| pulse__pi__pad_little__PBV__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__PBV__n_windows]: count |
| pulse__pi__pad_little__PBV__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__PBV__skewness] |
| pulse__pi__pad_little__PBV__snr_db | pulse | pi | no | yes | dB | PBV on pad_little: snr_db (section 6.3) |
| pulse__pi__pad_little__PBV__sqi | pulse | pi | no | yes | 0..1 | PBV on pad_little: sqi (section 6.3) |
| pulse__pi__pad_little__PBV__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__PBV__template_corr] |
| pulse__pi__pad_little__PCA__hr_bpm | pulse | pi | no | yes | bpm | PCA on pad_little: hr_bpm (section 6.3) |
| pulse__pi__pad_little__PCA__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__PCA__kurtosis] |
| pulse__pi__pad_little__PCA__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__PCA__n_windows]: count |
| pulse__pi__pad_little__PCA__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__PCA__skewness] |
| pulse__pi__pad_little__PCA__snr_db | pulse | pi | no | yes | dB | PCA on pad_little: snr_db (section 6.3) |
| pulse__pi__pad_little__PCA__sqi | pulse | pi | no | yes | 0..1 | PCA on pad_little: sqi (section 6.3) |
| pulse__pi__pad_little__PCA__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__PCA__template_corr] |
| pulse__pi__pad_little__POS__hr_bpm | pulse | pi | no | yes | bpm | POS on pad_little: hr_bpm (section 6.3) |
| pulse__pi__pad_little__POS__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__POS__kurtosis] |
| pulse__pi__pad_little__POS__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__POS__n_windows]: count |
| pulse__pi__pad_little__POS__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__POS__skewness] |
| pulse__pi__pad_little__POS__snr_db | pulse | pi | no | yes | dB | POS on pad_little: snr_db (section 6.3) |
| pulse__pi__pad_little__POS__sqi | pulse | pi | no | yes | 0..1 | POS on pad_little: sqi (section 6.3) |
| pulse__pi__pad_little__POS__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__POS__template_corr] |
| pulse__pi__pad_middle__2SR__hr_bpm | pulse | pi | no | yes | bpm | 2SR on pad_middle: hr_bpm (section 6.3) |
| pulse__pi__pad_middle__2SR__snr_db | pulse | pi | no | yes | dB | 2SR on pad_middle: snr_db (section 6.3) |
| pulse__pi__pad_middle__2SR__sqi | pulse | pi | no | yes | 0..1 | 2SR on pad_middle: sqi (section 6.3) |
| pulse__pi__pad_middle__CHROM__hr_bpm | pulse | pi | no | yes | bpm | CHROM on pad_middle: hr_bpm (section 6.3) |
| pulse__pi__pad_middle__CHROM__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__CHROM__kurtosis] |
| pulse__pi__pad_middle__CHROM__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__CHROM__n_windows]: count |
| pulse__pi__pad_middle__CHROM__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__CHROM__skewness] |
| pulse__pi__pad_middle__CHROM__snr_db | pulse | pi | no | yes | dB | CHROM on pad_middle: snr_db (section 6.3) |
| pulse__pi__pad_middle__CHROM__sqi | pulse | pi | no | yes | 0..1 | CHROM on pad_middle: sqi (section 6.3) |
| pulse__pi__pad_middle__CHROM__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__CHROM__template_corr] |
| pulse__pi__pad_middle__GREEN__hr_bpm | pulse | pi | no | yes | bpm | GREEN on pad_middle: hr_bpm (section 6.3) |
| pulse__pi__pad_middle__GREEN__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__GREEN__kurtosis] |
| pulse__pi__pad_middle__GREEN__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__GREEN__n_windows]: count |
| pulse__pi__pad_middle__GREEN__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__GREEN__skewness] |
| pulse__pi__pad_middle__GREEN__snr_db | pulse | pi | no | yes | dB | GREEN on pad_middle: snr_db (section 6.3) |
| pulse__pi__pad_middle__GREEN__sqi | pulse | pi | no | yes | 0..1 | GREEN on pad_middle: sqi (section 6.3) |
| pulse__pi__pad_middle__GREEN__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__GREEN__template_corr] |
| pulse__pi__pad_middle__ICA__hr_bpm | pulse | pi | no | yes | bpm | ICA on pad_middle: hr_bpm (section 6.3) |
| pulse__pi__pad_middle__ICA__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__ICA__kurtosis] |
| pulse__pi__pad_middle__ICA__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__ICA__n_windows]: count |
| pulse__pi__pad_middle__ICA__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__ICA__skewness] |
| pulse__pi__pad_middle__ICA__snr_db | pulse | pi | no | yes | dB | ICA on pad_middle: snr_db (section 6.3) |
| pulse__pi__pad_middle__ICA__sqi | pulse | pi | no | yes | 0..1 | ICA on pad_middle: sqi (section 6.3) |
| pulse__pi__pad_middle__ICA__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__ICA__template_corr] |
| pulse__pi__pad_middle__LGI__hr_bpm | pulse | pi | no | yes | bpm | LGI on pad_middle: hr_bpm (section 6.3) |
| pulse__pi__pad_middle__LGI__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__LGI__kurtosis] |
| pulse__pi__pad_middle__LGI__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__LGI__n_windows]: count |
| pulse__pi__pad_middle__LGI__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__LGI__skewness] |
| pulse__pi__pad_middle__LGI__snr_db | pulse | pi | no | yes | dB | LGI on pad_middle: snr_db (section 6.3) |
| pulse__pi__pad_middle__LGI__sqi | pulse | pi | no | yes | 0..1 | LGI on pad_middle: sqi (section 6.3) |
| pulse__pi__pad_middle__LGI__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__LGI__template_corr] |
| pulse__pi__pad_middle__OMIT__hr_bpm | pulse | pi | no | yes | bpm | OMIT on pad_middle: hr_bpm (section 6.3) |
| pulse__pi__pad_middle__OMIT__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__OMIT__kurtosis] |
| pulse__pi__pad_middle__OMIT__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__OMIT__n_windows]: count |
| pulse__pi__pad_middle__OMIT__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__OMIT__skewness] |
| pulse__pi__pad_middle__OMIT__snr_db | pulse | pi | no | yes | dB | OMIT on pad_middle: snr_db (section 6.3) |
| pulse__pi__pad_middle__OMIT__sqi | pulse | pi | no | yes | 0..1 | OMIT on pad_middle: sqi (section 6.3) |
| pulse__pi__pad_middle__OMIT__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__OMIT__template_corr] |
| pulse__pi__pad_middle__PBV__hr_bpm | pulse | pi | no | yes | bpm | PBV on pad_middle: hr_bpm (section 6.3) |
| pulse__pi__pad_middle__PBV__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__PBV__kurtosis] |
| pulse__pi__pad_middle__PBV__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__PBV__n_windows]: count |
| pulse__pi__pad_middle__PBV__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__PBV__skewness] |
| pulse__pi__pad_middle__PBV__snr_db | pulse | pi | no | yes | dB | PBV on pad_middle: snr_db (section 6.3) |
| pulse__pi__pad_middle__PBV__sqi | pulse | pi | no | yes | 0..1 | PBV on pad_middle: sqi (section 6.3) |
| pulse__pi__pad_middle__PBV__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__PBV__template_corr] |
| pulse__pi__pad_middle__PCA__hr_bpm | pulse | pi | no | yes | bpm | PCA on pad_middle: hr_bpm (section 6.3) |
| pulse__pi__pad_middle__PCA__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__PCA__kurtosis] |
| pulse__pi__pad_middle__PCA__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__PCA__n_windows]: count |
| pulse__pi__pad_middle__PCA__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__PCA__skewness] |
| pulse__pi__pad_middle__PCA__snr_db | pulse | pi | no | yes | dB | PCA on pad_middle: snr_db (section 6.3) |
| pulse__pi__pad_middle__PCA__sqi | pulse | pi | no | yes | 0..1 | PCA on pad_middle: sqi (section 6.3) |
| pulse__pi__pad_middle__PCA__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__PCA__template_corr] |
| pulse__pi__pad_middle__POS__hr_bpm | pulse | pi | no | yes | bpm | POS on pad_middle: hr_bpm (section 6.3) |
| pulse__pi__pad_middle__POS__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__POS__kurtosis] |
| pulse__pi__pad_middle__POS__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__POS__n_windows]: count |
| pulse__pi__pad_middle__POS__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__POS__skewness] |
| pulse__pi__pad_middle__POS__snr_db | pulse | pi | no | yes | dB | POS on pad_middle: snr_db (section 6.3) |
| pulse__pi__pad_middle__POS__sqi | pulse | pi | no | yes | 0..1 | POS on pad_middle: sqi (section 6.3) |
| pulse__pi__pad_middle__POS__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__POS__template_corr] |
| pulse__pi__pad_ring__2SR__hr_bpm | pulse | pi | no | yes | bpm | 2SR on pad_ring: hr_bpm (section 6.3) |
| pulse__pi__pad_ring__2SR__snr_db | pulse | pi | no | yes | dB | 2SR on pad_ring: snr_db (section 6.3) |
| pulse__pi__pad_ring__2SR__sqi | pulse | pi | no | yes | 0..1 | 2SR on pad_ring: sqi (section 6.3) |
| pulse__pi__pad_ring__CHROM__hr_bpm | pulse | pi | no | yes | bpm | CHROM on pad_ring: hr_bpm (section 6.3) |
| pulse__pi__pad_ring__CHROM__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__CHROM__kurtosis] |
| pulse__pi__pad_ring__CHROM__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__CHROM__n_windows]: count |
| pulse__pi__pad_ring__CHROM__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__CHROM__skewness] |
| pulse__pi__pad_ring__CHROM__snr_db | pulse | pi | no | yes | dB | CHROM on pad_ring: snr_db (section 6.3) |
| pulse__pi__pad_ring__CHROM__sqi | pulse | pi | no | yes | 0..1 | CHROM on pad_ring: sqi (section 6.3) |
| pulse__pi__pad_ring__CHROM__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__CHROM__template_corr] |
| pulse__pi__pad_ring__GREEN__hr_bpm | pulse | pi | no | yes | bpm | GREEN on pad_ring: hr_bpm (section 6.3) |
| pulse__pi__pad_ring__GREEN__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__GREEN__kurtosis] |
| pulse__pi__pad_ring__GREEN__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__GREEN__n_windows]: count |
| pulse__pi__pad_ring__GREEN__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__GREEN__skewness] |
| pulse__pi__pad_ring__GREEN__snr_db | pulse | pi | no | yes | dB | GREEN on pad_ring: snr_db (section 6.3) |
| pulse__pi__pad_ring__GREEN__sqi | pulse | pi | no | yes | 0..1 | GREEN on pad_ring: sqi (section 6.3) |
| pulse__pi__pad_ring__GREEN__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__GREEN__template_corr] |
| pulse__pi__pad_ring__ICA__hr_bpm | pulse | pi | no | yes | bpm | ICA on pad_ring: hr_bpm (section 6.3) |
| pulse__pi__pad_ring__ICA__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__ICA__kurtosis] |
| pulse__pi__pad_ring__ICA__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__ICA__n_windows]: count |
| pulse__pi__pad_ring__ICA__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__ICA__skewness] |
| pulse__pi__pad_ring__ICA__snr_db | pulse | pi | no | yes | dB | ICA on pad_ring: snr_db (section 6.3) |
| pulse__pi__pad_ring__ICA__sqi | pulse | pi | no | yes | 0..1 | ICA on pad_ring: sqi (section 6.3) |
| pulse__pi__pad_ring__ICA__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__ICA__template_corr] |
| pulse__pi__pad_ring__LGI__hr_bpm | pulse | pi | no | yes | bpm | LGI on pad_ring: hr_bpm (section 6.3) |
| pulse__pi__pad_ring__LGI__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__LGI__kurtosis] |
| pulse__pi__pad_ring__LGI__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__LGI__n_windows]: count |
| pulse__pi__pad_ring__LGI__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__LGI__skewness] |
| pulse__pi__pad_ring__LGI__snr_db | pulse | pi | no | yes | dB | LGI on pad_ring: snr_db (section 6.3) |
| pulse__pi__pad_ring__LGI__sqi | pulse | pi | no | yes | 0..1 | LGI on pad_ring: sqi (section 6.3) |
| pulse__pi__pad_ring__LGI__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__LGI__template_corr] |
| pulse__pi__pad_ring__OMIT__hr_bpm | pulse | pi | no | yes | bpm | OMIT on pad_ring: hr_bpm (section 6.3) |
| pulse__pi__pad_ring__OMIT__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__OMIT__kurtosis] |
| pulse__pi__pad_ring__OMIT__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__OMIT__n_windows]: count |
| pulse__pi__pad_ring__OMIT__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__OMIT__skewness] |
| pulse__pi__pad_ring__OMIT__snr_db | pulse | pi | no | yes | dB | OMIT on pad_ring: snr_db (section 6.3) |
| pulse__pi__pad_ring__OMIT__sqi | pulse | pi | no | yes | 0..1 | OMIT on pad_ring: sqi (section 6.3) |
| pulse__pi__pad_ring__OMIT__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__OMIT__template_corr] |
| pulse__pi__pad_ring__PBV__hr_bpm | pulse | pi | no | yes | bpm | PBV on pad_ring: hr_bpm (section 6.3) |
| pulse__pi__pad_ring__PBV__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__PBV__kurtosis] |
| pulse__pi__pad_ring__PBV__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__PBV__n_windows]: count |
| pulse__pi__pad_ring__PBV__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__PBV__skewness] |
| pulse__pi__pad_ring__PBV__snr_db | pulse | pi | no | yes | dB | PBV on pad_ring: snr_db (section 6.3) |
| pulse__pi__pad_ring__PBV__sqi | pulse | pi | no | yes | 0..1 | PBV on pad_ring: sqi (section 6.3) |
| pulse__pi__pad_ring__PBV__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__PBV__template_corr] |
| pulse__pi__pad_ring__PCA__hr_bpm | pulse | pi | no | yes | bpm | PCA on pad_ring: hr_bpm (section 6.3) |
| pulse__pi__pad_ring__PCA__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__PCA__kurtosis] |
| pulse__pi__pad_ring__PCA__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__PCA__n_windows]: count |
| pulse__pi__pad_ring__PCA__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__PCA__skewness] |
| pulse__pi__pad_ring__PCA__snr_db | pulse | pi | no | yes | dB | PCA on pad_ring: snr_db (section 6.3) |
| pulse__pi__pad_ring__PCA__sqi | pulse | pi | no | yes | 0..1 | PCA on pad_ring: sqi (section 6.3) |
| pulse__pi__pad_ring__PCA__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__PCA__template_corr] |
| pulse__pi__pad_ring__POS__hr_bpm | pulse | pi | no | yes | bpm | POS on pad_ring: hr_bpm (section 6.3) |
| pulse__pi__pad_ring__POS__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__POS__kurtosis] |
| pulse__pi__pad_ring__POS__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__POS__n_windows]: count |
| pulse__pi__pad_ring__POS__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__POS__skewness] |
| pulse__pi__pad_ring__POS__snr_db | pulse | pi | no | yes | dB | POS on pad_ring: snr_db (section 6.3) |
| pulse__pi__pad_ring__POS__sqi | pulse | pi | no | yes | 0..1 | POS on pad_ring: sqi (section 6.3) |
| pulse__pi__pad_ring__POS__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__POS__template_corr] |
| pulse__pi__prox_index__2SR__hr_bpm | pulse | pi | no | yes | bpm | 2SR on prox_index: hr_bpm (section 6.3) |
| pulse__pi__prox_index__2SR__snr_db | pulse | pi | no | yes | dB | 2SR on prox_index: snr_db (section 6.3) |
| pulse__pi__prox_index__2SR__sqi | pulse | pi | no | yes | 0..1 | 2SR on prox_index: sqi (section 6.3) |
| pulse__pi__prox_index__CHROM__hr_bpm | pulse | pi | no | yes | bpm | CHROM on prox_index: hr_bpm (section 6.3) |
| pulse__pi__prox_index__CHROM__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__CHROM__kurtosis] |
| pulse__pi__prox_index__CHROM__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__CHROM__n_windows]: count |
| pulse__pi__prox_index__CHROM__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__CHROM__skewness] |
| pulse__pi__prox_index__CHROM__snr_db | pulse | pi | no | yes | dB | CHROM on prox_index: snr_db (section 6.3) |
| pulse__pi__prox_index__CHROM__sqi | pulse | pi | no | yes | 0..1 | CHROM on prox_index: sqi (section 6.3) |
| pulse__pi__prox_index__CHROM__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__CHROM__template_corr] |
| pulse__pi__prox_index__GREEN__hr_bpm | pulse | pi | no | yes | bpm | GREEN on prox_index: hr_bpm (section 6.3) |
| pulse__pi__prox_index__GREEN__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__GREEN__kurtosis] |
| pulse__pi__prox_index__GREEN__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__GREEN__n_windows]: count |
| pulse__pi__prox_index__GREEN__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__GREEN__skewness] |
| pulse__pi__prox_index__GREEN__snr_db | pulse | pi | no | yes | dB | GREEN on prox_index: snr_db (section 6.3) |
| pulse__pi__prox_index__GREEN__sqi | pulse | pi | no | yes | 0..1 | GREEN on prox_index: sqi (section 6.3) |
| pulse__pi__prox_index__GREEN__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__GREEN__template_corr] |
| pulse__pi__prox_index__ICA__hr_bpm | pulse | pi | no | yes | bpm | ICA on prox_index: hr_bpm (section 6.3) |
| pulse__pi__prox_index__ICA__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__ICA__kurtosis] |
| pulse__pi__prox_index__ICA__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__ICA__n_windows]: count |
| pulse__pi__prox_index__ICA__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__ICA__skewness] |
| pulse__pi__prox_index__ICA__snr_db | pulse | pi | no | yes | dB | ICA on prox_index: snr_db (section 6.3) |
| pulse__pi__prox_index__ICA__sqi | pulse | pi | no | yes | 0..1 | ICA on prox_index: sqi (section 6.3) |
| pulse__pi__prox_index__ICA__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__ICA__template_corr] |
| pulse__pi__prox_index__LGI__hr_bpm | pulse | pi | no | yes | bpm | LGI on prox_index: hr_bpm (section 6.3) |
| pulse__pi__prox_index__LGI__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__LGI__kurtosis] |
| pulse__pi__prox_index__LGI__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__LGI__n_windows]: count |
| pulse__pi__prox_index__LGI__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__LGI__skewness] |
| pulse__pi__prox_index__LGI__snr_db | pulse | pi | no | yes | dB | LGI on prox_index: snr_db (section 6.3) |
| pulse__pi__prox_index__LGI__sqi | pulse | pi | no | yes | 0..1 | LGI on prox_index: sqi (section 6.3) |
| pulse__pi__prox_index__LGI__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__LGI__template_corr] |
| pulse__pi__prox_index__OMIT__hr_bpm | pulse | pi | no | yes | bpm | OMIT on prox_index: hr_bpm (section 6.3) |
| pulse__pi__prox_index__OMIT__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__OMIT__kurtosis] |
| pulse__pi__prox_index__OMIT__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__OMIT__n_windows]: count |
| pulse__pi__prox_index__OMIT__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__OMIT__skewness] |
| pulse__pi__prox_index__OMIT__snr_db | pulse | pi | no | yes | dB | OMIT on prox_index: snr_db (section 6.3) |
| pulse__pi__prox_index__OMIT__sqi | pulse | pi | no | yes | 0..1 | OMIT on prox_index: sqi (section 6.3) |
| pulse__pi__prox_index__OMIT__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__OMIT__template_corr] |
| pulse__pi__prox_index__PBV__hr_bpm | pulse | pi | no | yes | bpm | PBV on prox_index: hr_bpm (section 6.3) |
| pulse__pi__prox_index__PBV__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__PBV__kurtosis] |
| pulse__pi__prox_index__PBV__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__PBV__n_windows]: count |
| pulse__pi__prox_index__PBV__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__PBV__skewness] |
| pulse__pi__prox_index__PBV__snr_db | pulse | pi | no | yes | dB | PBV on prox_index: snr_db (section 6.3) |
| pulse__pi__prox_index__PBV__sqi | pulse | pi | no | yes | 0..1 | PBV on prox_index: sqi (section 6.3) |
| pulse__pi__prox_index__PBV__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__PBV__template_corr] |
| pulse__pi__prox_index__PCA__hr_bpm | pulse | pi | no | yes | bpm | PCA on prox_index: hr_bpm (section 6.3) |
| pulse__pi__prox_index__PCA__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__PCA__kurtosis] |
| pulse__pi__prox_index__PCA__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__PCA__n_windows]: count |
| pulse__pi__prox_index__PCA__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__PCA__skewness] |
| pulse__pi__prox_index__PCA__snr_db | pulse | pi | no | yes | dB | PCA on prox_index: snr_db (section 6.3) |
| pulse__pi__prox_index__PCA__sqi | pulse | pi | no | yes | 0..1 | PCA on prox_index: sqi (section 6.3) |
| pulse__pi__prox_index__PCA__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__PCA__template_corr] |
| pulse__pi__prox_index__POS__hr_bpm | pulse | pi | no | yes | bpm | POS on prox_index: hr_bpm (section 6.3) |
| pulse__pi__prox_index__POS__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__POS__kurtosis] |
| pulse__pi__prox_index__POS__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__POS__n_windows]: count |
| pulse__pi__prox_index__POS__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__POS__skewness] |
| pulse__pi__prox_index__POS__snr_db | pulse | pi | no | yes | dB | POS on prox_index: snr_db (section 6.3) |
| pulse__pi__prox_index__POS__sqi | pulse | pi | no | yes | 0..1 | POS on prox_index: sqi (section 6.3) |
| pulse__pi__prox_index__POS__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__POS__template_corr] |
| pulse__pi__prox_little__2SR__hr_bpm | pulse | pi | no | yes | bpm | 2SR on prox_little: hr_bpm (section 6.3) |
| pulse__pi__prox_little__2SR__snr_db | pulse | pi | no | yes | dB | 2SR on prox_little: snr_db (section 6.3) |
| pulse__pi__prox_little__2SR__sqi | pulse | pi | no | yes | 0..1 | 2SR on prox_little: sqi (section 6.3) |
| pulse__pi__prox_little__CHROM__hr_bpm | pulse | pi | no | yes | bpm | CHROM on prox_little: hr_bpm (section 6.3) |
| pulse__pi__prox_little__CHROM__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__CHROM__kurtosis] |
| pulse__pi__prox_little__CHROM__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__CHROM__n_windows]: count |
| pulse__pi__prox_little__CHROM__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__CHROM__skewness] |
| pulse__pi__prox_little__CHROM__snr_db | pulse | pi | no | yes | dB | CHROM on prox_little: snr_db (section 6.3) |
| pulse__pi__prox_little__CHROM__sqi | pulse | pi | no | yes | 0..1 | CHROM on prox_little: sqi (section 6.3) |
| pulse__pi__prox_little__CHROM__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__CHROM__template_corr] |
| pulse__pi__prox_little__GREEN__hr_bpm | pulse | pi | no | yes | bpm | GREEN on prox_little: hr_bpm (section 6.3) |
| pulse__pi__prox_little__GREEN__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__GREEN__kurtosis] |
| pulse__pi__prox_little__GREEN__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__GREEN__n_windows]: count |
| pulse__pi__prox_little__GREEN__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__GREEN__skewness] |
| pulse__pi__prox_little__GREEN__snr_db | pulse | pi | no | yes | dB | GREEN on prox_little: snr_db (section 6.3) |
| pulse__pi__prox_little__GREEN__sqi | pulse | pi | no | yes | 0..1 | GREEN on prox_little: sqi (section 6.3) |
| pulse__pi__prox_little__GREEN__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__GREEN__template_corr] |
| pulse__pi__prox_little__ICA__hr_bpm | pulse | pi | no | yes | bpm | ICA on prox_little: hr_bpm (section 6.3) |
| pulse__pi__prox_little__ICA__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__ICA__kurtosis] |
| pulse__pi__prox_little__ICA__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__ICA__n_windows]: count |
| pulse__pi__prox_little__ICA__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__ICA__skewness] |
| pulse__pi__prox_little__ICA__snr_db | pulse | pi | no | yes | dB | ICA on prox_little: snr_db (section 6.3) |
| pulse__pi__prox_little__ICA__sqi | pulse | pi | no | yes | 0..1 | ICA on prox_little: sqi (section 6.3) |
| pulse__pi__prox_little__ICA__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__ICA__template_corr] |
| pulse__pi__prox_little__LGI__hr_bpm | pulse | pi | no | yes | bpm | LGI on prox_little: hr_bpm (section 6.3) |
| pulse__pi__prox_little__LGI__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__LGI__kurtosis] |
| pulse__pi__prox_little__LGI__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__LGI__n_windows]: count |
| pulse__pi__prox_little__LGI__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__LGI__skewness] |
| pulse__pi__prox_little__LGI__snr_db | pulse | pi | no | yes | dB | LGI on prox_little: snr_db (section 6.3) |
| pulse__pi__prox_little__LGI__sqi | pulse | pi | no | yes | 0..1 | LGI on prox_little: sqi (section 6.3) |
| pulse__pi__prox_little__LGI__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__LGI__template_corr] |
| pulse__pi__prox_little__OMIT__hr_bpm | pulse | pi | no | yes | bpm | OMIT on prox_little: hr_bpm (section 6.3) |
| pulse__pi__prox_little__OMIT__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__OMIT__kurtosis] |
| pulse__pi__prox_little__OMIT__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__OMIT__n_windows]: count |
| pulse__pi__prox_little__OMIT__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__OMIT__skewness] |
| pulse__pi__prox_little__OMIT__snr_db | pulse | pi | no | yes | dB | OMIT on prox_little: snr_db (section 6.3) |
| pulse__pi__prox_little__OMIT__sqi | pulse | pi | no | yes | 0..1 | OMIT on prox_little: sqi (section 6.3) |
| pulse__pi__prox_little__OMIT__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__OMIT__template_corr] |
| pulse__pi__prox_little__PBV__hr_bpm | pulse | pi | no | yes | bpm | PBV on prox_little: hr_bpm (section 6.3) |
| pulse__pi__prox_little__PBV__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__PBV__kurtosis] |
| pulse__pi__prox_little__PBV__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__PBV__n_windows]: count |
| pulse__pi__prox_little__PBV__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__PBV__skewness] |
| pulse__pi__prox_little__PBV__snr_db | pulse | pi | no | yes | dB | PBV on prox_little: snr_db (section 6.3) |
| pulse__pi__prox_little__PBV__sqi | pulse | pi | no | yes | 0..1 | PBV on prox_little: sqi (section 6.3) |
| pulse__pi__prox_little__PBV__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__PBV__template_corr] |
| pulse__pi__prox_little__PCA__hr_bpm | pulse | pi | no | yes | bpm | PCA on prox_little: hr_bpm (section 6.3) |
| pulse__pi__prox_little__PCA__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__PCA__kurtosis] |
| pulse__pi__prox_little__PCA__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__PCA__n_windows]: count |
| pulse__pi__prox_little__PCA__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__PCA__skewness] |
| pulse__pi__prox_little__PCA__snr_db | pulse | pi | no | yes | dB | PCA on prox_little: snr_db (section 6.3) |
| pulse__pi__prox_little__PCA__sqi | pulse | pi | no | yes | 0..1 | PCA on prox_little: sqi (section 6.3) |
| pulse__pi__prox_little__PCA__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__PCA__template_corr] |
| pulse__pi__prox_little__POS__hr_bpm | pulse | pi | no | yes | bpm | POS on prox_little: hr_bpm (section 6.3) |
| pulse__pi__prox_little__POS__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__POS__kurtosis] |
| pulse__pi__prox_little__POS__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__POS__n_windows]: count |
| pulse__pi__prox_little__POS__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__POS__skewness] |
| pulse__pi__prox_little__POS__snr_db | pulse | pi | no | yes | dB | POS on prox_little: snr_db (section 6.3) |
| pulse__pi__prox_little__POS__sqi | pulse | pi | no | yes | 0..1 | POS on prox_little: sqi (section 6.3) |
| pulse__pi__prox_little__POS__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__POS__template_corr] |
| pulse__pi__prox_middle__2SR__hr_bpm | pulse | pi | no | yes | bpm | 2SR on prox_middle: hr_bpm (section 6.3) |
| pulse__pi__prox_middle__2SR__snr_db | pulse | pi | no | yes | dB | 2SR on prox_middle: snr_db (section 6.3) |
| pulse__pi__prox_middle__2SR__sqi | pulse | pi | no | yes | 0..1 | 2SR on prox_middle: sqi (section 6.3) |
| pulse__pi__prox_middle__CHROM__hr_bpm | pulse | pi | no | yes | bpm | CHROM on prox_middle: hr_bpm (section 6.3) |
| pulse__pi__prox_middle__CHROM__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__CHROM__kurtosis] |
| pulse__pi__prox_middle__CHROM__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__CHROM__n_windows]: count |
| pulse__pi__prox_middle__CHROM__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__CHROM__skewness] |
| pulse__pi__prox_middle__CHROM__snr_db | pulse | pi | no | yes | dB | CHROM on prox_middle: snr_db (section 6.3) |
| pulse__pi__prox_middle__CHROM__sqi | pulse | pi | no | yes | 0..1 | CHROM on prox_middle: sqi (section 6.3) |
| pulse__pi__prox_middle__CHROM__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__CHROM__template_corr] |
| pulse__pi__prox_middle__GREEN__hr_bpm | pulse | pi | no | yes | bpm | GREEN on prox_middle: hr_bpm (section 6.3) |
| pulse__pi__prox_middle__GREEN__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__GREEN__kurtosis] |
| pulse__pi__prox_middle__GREEN__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__GREEN__n_windows]: count |
| pulse__pi__prox_middle__GREEN__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__GREEN__skewness] |
| pulse__pi__prox_middle__GREEN__snr_db | pulse | pi | no | yes | dB | GREEN on prox_middle: snr_db (section 6.3) |
| pulse__pi__prox_middle__GREEN__sqi | pulse | pi | no | yes | 0..1 | GREEN on prox_middle: sqi (section 6.3) |
| pulse__pi__prox_middle__GREEN__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__GREEN__template_corr] |
| pulse__pi__prox_middle__ICA__hr_bpm | pulse | pi | no | yes | bpm | ICA on prox_middle: hr_bpm (section 6.3) |
| pulse__pi__prox_middle__ICA__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__ICA__kurtosis] |
| pulse__pi__prox_middle__ICA__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__ICA__n_windows]: count |
| pulse__pi__prox_middle__ICA__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__ICA__skewness] |
| pulse__pi__prox_middle__ICA__snr_db | pulse | pi | no | yes | dB | ICA on prox_middle: snr_db (section 6.3) |
| pulse__pi__prox_middle__ICA__sqi | pulse | pi | no | yes | 0..1 | ICA on prox_middle: sqi (section 6.3) |
| pulse__pi__prox_middle__ICA__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__ICA__template_corr] |
| pulse__pi__prox_middle__LGI__hr_bpm | pulse | pi | no | yes | bpm | LGI on prox_middle: hr_bpm (section 6.3) |
| pulse__pi__prox_middle__LGI__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__LGI__kurtosis] |
| pulse__pi__prox_middle__LGI__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__LGI__n_windows]: count |
| pulse__pi__prox_middle__LGI__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__LGI__skewness] |
| pulse__pi__prox_middle__LGI__snr_db | pulse | pi | no | yes | dB | LGI on prox_middle: snr_db (section 6.3) |
| pulse__pi__prox_middle__LGI__sqi | pulse | pi | no | yes | 0..1 | LGI on prox_middle: sqi (section 6.3) |
| pulse__pi__prox_middle__LGI__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__LGI__template_corr] |
| pulse__pi__prox_middle__OMIT__hr_bpm | pulse | pi | no | yes | bpm | OMIT on prox_middle: hr_bpm (section 6.3) |
| pulse__pi__prox_middle__OMIT__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__OMIT__kurtosis] |
| pulse__pi__prox_middle__OMIT__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__OMIT__n_windows]: count |
| pulse__pi__prox_middle__OMIT__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__OMIT__skewness] |
| pulse__pi__prox_middle__OMIT__snr_db | pulse | pi | no | yes | dB | OMIT on prox_middle: snr_db (section 6.3) |
| pulse__pi__prox_middle__OMIT__sqi | pulse | pi | no | yes | 0..1 | OMIT on prox_middle: sqi (section 6.3) |
| pulse__pi__prox_middle__OMIT__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__OMIT__template_corr] |
| pulse__pi__prox_middle__PBV__hr_bpm | pulse | pi | no | yes | bpm | PBV on prox_middle: hr_bpm (section 6.3) |
| pulse__pi__prox_middle__PBV__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__PBV__kurtosis] |
| pulse__pi__prox_middle__PBV__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__PBV__n_windows]: count |
| pulse__pi__prox_middle__PBV__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__PBV__skewness] |
| pulse__pi__prox_middle__PBV__snr_db | pulse | pi | no | yes | dB | PBV on prox_middle: snr_db (section 6.3) |
| pulse__pi__prox_middle__PBV__sqi | pulse | pi | no | yes | 0..1 | PBV on prox_middle: sqi (section 6.3) |
| pulse__pi__prox_middle__PBV__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__PBV__template_corr] |
| pulse__pi__prox_middle__PCA__hr_bpm | pulse | pi | no | yes | bpm | PCA on prox_middle: hr_bpm (section 6.3) |
| pulse__pi__prox_middle__PCA__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__PCA__kurtosis] |
| pulse__pi__prox_middle__PCA__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__PCA__n_windows]: count |
| pulse__pi__prox_middle__PCA__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__PCA__skewness] |
| pulse__pi__prox_middle__PCA__snr_db | pulse | pi | no | yes | dB | PCA on prox_middle: snr_db (section 6.3) |
| pulse__pi__prox_middle__PCA__sqi | pulse | pi | no | yes | 0..1 | PCA on prox_middle: sqi (section 6.3) |
| pulse__pi__prox_middle__PCA__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__PCA__template_corr] |
| pulse__pi__prox_middle__POS__hr_bpm | pulse | pi | no | yes | bpm | POS on prox_middle: hr_bpm (section 6.3) |
| pulse__pi__prox_middle__POS__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__POS__kurtosis] |
| pulse__pi__prox_middle__POS__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__POS__n_windows]: count |
| pulse__pi__prox_middle__POS__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__POS__skewness] |
| pulse__pi__prox_middle__POS__snr_db | pulse | pi | no | yes | dB | POS on prox_middle: snr_db (section 6.3) |
| pulse__pi__prox_middle__POS__sqi | pulse | pi | no | yes | 0..1 | POS on prox_middle: sqi (section 6.3) |
| pulse__pi__prox_middle__POS__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__POS__template_corr] |
| pulse__pi__prox_ring__2SR__hr_bpm | pulse | pi | no | yes | bpm | 2SR on prox_ring: hr_bpm (section 6.3) |
| pulse__pi__prox_ring__2SR__snr_db | pulse | pi | no | yes | dB | 2SR on prox_ring: snr_db (section 6.3) |
| pulse__pi__prox_ring__2SR__sqi | pulse | pi | no | yes | 0..1 | 2SR on prox_ring: sqi (section 6.3) |
| pulse__pi__prox_ring__CHROM__hr_bpm | pulse | pi | no | yes | bpm | CHROM on prox_ring: hr_bpm (section 6.3) |
| pulse__pi__prox_ring__CHROM__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__CHROM__kurtosis] |
| pulse__pi__prox_ring__CHROM__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__CHROM__n_windows]: count |
| pulse__pi__prox_ring__CHROM__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__CHROM__skewness] |
| pulse__pi__prox_ring__CHROM__snr_db | pulse | pi | no | yes | dB | CHROM on prox_ring: snr_db (section 6.3) |
| pulse__pi__prox_ring__CHROM__sqi | pulse | pi | no | yes | 0..1 | CHROM on prox_ring: sqi (section 6.3) |
| pulse__pi__prox_ring__CHROM__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__CHROM__template_corr] |
| pulse__pi__prox_ring__GREEN__hr_bpm | pulse | pi | no | yes | bpm | GREEN on prox_ring: hr_bpm (section 6.3) |
| pulse__pi__prox_ring__GREEN__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__GREEN__kurtosis] |
| pulse__pi__prox_ring__GREEN__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__GREEN__n_windows]: count |
| pulse__pi__prox_ring__GREEN__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__GREEN__skewness] |
| pulse__pi__prox_ring__GREEN__snr_db | pulse | pi | no | yes | dB | GREEN on prox_ring: snr_db (section 6.3) |
| pulse__pi__prox_ring__GREEN__sqi | pulse | pi | no | yes | 0..1 | GREEN on prox_ring: sqi (section 6.3) |
| pulse__pi__prox_ring__GREEN__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__GREEN__template_corr] |
| pulse__pi__prox_ring__ICA__hr_bpm | pulse | pi | no | yes | bpm | ICA on prox_ring: hr_bpm (section 6.3) |
| pulse__pi__prox_ring__ICA__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__ICA__kurtosis] |
| pulse__pi__prox_ring__ICA__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__ICA__n_windows]: count |
| pulse__pi__prox_ring__ICA__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__ICA__skewness] |
| pulse__pi__prox_ring__ICA__snr_db | pulse | pi | no | yes | dB | ICA on prox_ring: snr_db (section 6.3) |
| pulse__pi__prox_ring__ICA__sqi | pulse | pi | no | yes | 0..1 | ICA on prox_ring: sqi (section 6.3) |
| pulse__pi__prox_ring__ICA__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__ICA__template_corr] |
| pulse__pi__prox_ring__LGI__hr_bpm | pulse | pi | no | yes | bpm | LGI on prox_ring: hr_bpm (section 6.3) |
| pulse__pi__prox_ring__LGI__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__LGI__kurtosis] |
| pulse__pi__prox_ring__LGI__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__LGI__n_windows]: count |
| pulse__pi__prox_ring__LGI__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__LGI__skewness] |
| pulse__pi__prox_ring__LGI__snr_db | pulse | pi | no | yes | dB | LGI on prox_ring: snr_db (section 6.3) |
| pulse__pi__prox_ring__LGI__sqi | pulse | pi | no | yes | 0..1 | LGI on prox_ring: sqi (section 6.3) |
| pulse__pi__prox_ring__LGI__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__LGI__template_corr] |
| pulse__pi__prox_ring__OMIT__hr_bpm | pulse | pi | no | yes | bpm | OMIT on prox_ring: hr_bpm (section 6.3) |
| pulse__pi__prox_ring__OMIT__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__OMIT__kurtosis] |
| pulse__pi__prox_ring__OMIT__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__OMIT__n_windows]: count |
| pulse__pi__prox_ring__OMIT__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__OMIT__skewness] |
| pulse__pi__prox_ring__OMIT__snr_db | pulse | pi | no | yes | dB | OMIT on prox_ring: snr_db (section 6.3) |
| pulse__pi__prox_ring__OMIT__sqi | pulse | pi | no | yes | 0..1 | OMIT on prox_ring: sqi (section 6.3) |
| pulse__pi__prox_ring__OMIT__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__OMIT__template_corr] |
| pulse__pi__prox_ring__PBV__hr_bpm | pulse | pi | no | yes | bpm | PBV on prox_ring: hr_bpm (section 6.3) |
| pulse__pi__prox_ring__PBV__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__PBV__kurtosis] |
| pulse__pi__prox_ring__PBV__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__PBV__n_windows]: count |
| pulse__pi__prox_ring__PBV__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__PBV__skewness] |
| pulse__pi__prox_ring__PBV__snr_db | pulse | pi | no | yes | dB | PBV on prox_ring: snr_db (section 6.3) |
| pulse__pi__prox_ring__PBV__sqi | pulse | pi | no | yes | 0..1 | PBV on prox_ring: sqi (section 6.3) |
| pulse__pi__prox_ring__PBV__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__PBV__template_corr] |
| pulse__pi__prox_ring__PCA__hr_bpm | pulse | pi | no | yes | bpm | PCA on prox_ring: hr_bpm (section 6.3) |
| pulse__pi__prox_ring__PCA__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__PCA__kurtosis] |
| pulse__pi__prox_ring__PCA__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__PCA__n_windows]: count |
| pulse__pi__prox_ring__PCA__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__PCA__skewness] |
| pulse__pi__prox_ring__PCA__snr_db | pulse | pi | no | yes | dB | PCA on prox_ring: snr_db (section 6.3) |
| pulse__pi__prox_ring__PCA__sqi | pulse | pi | no | yes | 0..1 | PCA on prox_ring: sqi (section 6.3) |
| pulse__pi__prox_ring__PCA__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__PCA__template_corr] |
| pulse__pi__prox_ring__POS__hr_bpm | pulse | pi | no | yes | bpm | POS on prox_ring: hr_bpm (section 6.3) |
| pulse__pi__prox_ring__POS__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__POS__kurtosis] |
| pulse__pi__prox_ring__POS__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__POS__n_windows]: count |
| pulse__pi__prox_ring__POS__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__POS__skewness] |
| pulse__pi__prox_ring__POS__snr_db | pulse | pi | no | yes | dB | POS on prox_ring: snr_db (section 6.3) |
| pulse__pi__prox_ring__POS__sqi | pulse | pi | no | yes | 0..1 | POS on prox_ring: sqi (section 6.3) |
| pulse__pi__prox_ring__POS__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__POS__template_corr] |
| pulse__pi__roi_set__2SR__hr_bpm | pulse | pi | no | yes | bpm | 2SR on roi_set: hr_bpm (section 6.3) |
| pulse__pi__roi_set__2SR__snr_db | pulse | pi | no | yes | dB | 2SR on roi_set: snr_db (section 6.3) |
| pulse__pi__roi_set__2SR__sqi | pulse | pi | no | yes | 0..1 | 2SR on roi_set: sqi (section 6.3) |
| pulse__pi__roi_set__CHROM__hr_bpm | pulse | pi | no | yes | bpm | CHROM on roi_set: hr_bpm (section 6.3) |
| pulse__pi__roi_set__CHROM__snr_db | pulse | pi | no | yes | dB | CHROM on roi_set: snr_db (section 6.3) |
| pulse__pi__roi_set__CHROM__sqi | pulse | pi | no | yes | 0..1 | CHROM on roi_set: sqi (section 6.3) |
| pulse__pi__roi_set__GREEN__hr_bpm | pulse | pi | no | yes | bpm | GREEN on roi_set: hr_bpm (section 6.3) |
| pulse__pi__roi_set__GREEN__snr_db | pulse | pi | no | yes | dB | GREEN on roi_set: snr_db (section 6.3) |
| pulse__pi__roi_set__GREEN__sqi | pulse | pi | no | yes | 0..1 | GREEN on roi_set: sqi (section 6.3) |
| pulse__pi__roi_set__ICA__hr_bpm | pulse | pi | no | yes | bpm | ICA on roi_set: hr_bpm (section 6.3) |
| pulse__pi__roi_set__ICA__snr_db | pulse | pi | no | yes | dB | ICA on roi_set: snr_db (section 6.3) |
| pulse__pi__roi_set__ICA__sqi | pulse | pi | no | yes | 0..1 | ICA on roi_set: sqi (section 6.3) |
| pulse__pi__roi_set__LGI__hr_bpm | pulse | pi | no | yes | bpm | LGI on roi_set: hr_bpm (section 6.3) |
| pulse__pi__roi_set__LGI__snr_db | pulse | pi | no | yes | dB | LGI on roi_set: snr_db (section 6.3) |
| pulse__pi__roi_set__LGI__sqi | pulse | pi | no | yes | 0..1 | LGI on roi_set: sqi (section 6.3) |
| pulse__pi__roi_set__OMIT__hr_bpm | pulse | pi | no | yes | bpm | OMIT on roi_set: hr_bpm (section 6.3) |
| pulse__pi__roi_set__OMIT__snr_db | pulse | pi | no | yes | dB | OMIT on roi_set: snr_db (section 6.3) |
| pulse__pi__roi_set__OMIT__sqi | pulse | pi | no | yes | 0..1 | OMIT on roi_set: sqi (section 6.3) |
| pulse__pi__roi_set__PBV__hr_bpm | pulse | pi | no | yes | bpm | PBV on roi_set: hr_bpm (section 6.3) |
| pulse__pi__roi_set__PBV__snr_db | pulse | pi | no | yes | dB | PBV on roi_set: snr_db (section 6.3) |
| pulse__pi__roi_set__PBV__sqi | pulse | pi | no | yes | 0..1 | PBV on roi_set: sqi (section 6.3) |
| pulse__pi__roi_set__PCA__hr_bpm | pulse | pi | no | yes | bpm | PCA on roi_set: hr_bpm (section 6.3) |
| pulse__pi__roi_set__PCA__snr_db | pulse | pi | no | yes | dB | PCA on roi_set: snr_db (section 6.3) |
| pulse__pi__roi_set__PCA__sqi | pulse | pi | no | yes | 0..1 | PCA on roi_set: sqi (section 6.3) |
| pulse__pi__roi_set__POS__hr_bpm | pulse | pi | no | yes | bpm | POS on roi_set: hr_bpm (section 6.3) |
| pulse__pi__roi_set__POS__snr_db | pulse | pi | no | yes | dB | POS on roi_set: snr_db (section 6.3) |
| pulse__pi__roi_set__POS__sqi | pulse | pi | no | yes | 0..1 | POS on roi_set: sqi (section 6.3) |
| pulse__pi__selection__agreement | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [selection__agreement] |
| pulse__pi__selection__consensus_hr_bpm | pulse | pi | no | yes | bpm | pulse extraction summary per method and ROI (protocol 6.3) [selection__consensus_hr_bpm]: rate in beats per minute |
| pulse__pi__selection__mode | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [selection__mode] |
| pulse__pi__selection__n_candidates | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [selection__n_candidates]: count |
| pulse__pi__selection__raw_sqi | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [selection__raw_sqi] |
| pulse__pi__selection__score | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [selection__score] |
| pulse__pi__thenar__2SR__hr_bpm | pulse | pi | no | yes | bpm | 2SR on thenar: hr_bpm (section 6.3) |
| pulse__pi__thenar__2SR__snr_db | pulse | pi | no | yes | dB | 2SR on thenar: snr_db (section 6.3) |
| pulse__pi__thenar__2SR__sqi | pulse | pi | no | yes | 0..1 | 2SR on thenar: sqi (section 6.3) |
| pulse__pi__thenar__CHROM__hr_bpm | pulse | pi | no | yes | bpm | CHROM on thenar: hr_bpm (section 6.3) |
| pulse__pi__thenar__CHROM__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__CHROM__kurtosis] |
| pulse__pi__thenar__CHROM__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [thenar__CHROM__n_windows]: count |
| pulse__pi__thenar__CHROM__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__CHROM__skewness] |
| pulse__pi__thenar__CHROM__snr_db | pulse | pi | no | yes | dB | CHROM on thenar: snr_db (section 6.3) |
| pulse__pi__thenar__CHROM__sqi | pulse | pi | no | yes | 0..1 | CHROM on thenar: sqi (section 6.3) |
| pulse__pi__thenar__CHROM__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__CHROM__template_corr] |
| pulse__pi__thenar__GREEN__hr_bpm | pulse | pi | no | yes | bpm | GREEN on thenar: hr_bpm (section 6.3) |
| pulse__pi__thenar__GREEN__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__GREEN__kurtosis] |
| pulse__pi__thenar__GREEN__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [thenar__GREEN__n_windows]: count |
| pulse__pi__thenar__GREEN__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__GREEN__skewness] |
| pulse__pi__thenar__GREEN__snr_db | pulse | pi | no | yes | dB | GREEN on thenar: snr_db (section 6.3) |
| pulse__pi__thenar__GREEN__sqi | pulse | pi | no | yes | 0..1 | GREEN on thenar: sqi (section 6.3) |
| pulse__pi__thenar__GREEN__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__GREEN__template_corr] |
| pulse__pi__thenar__ICA__hr_bpm | pulse | pi | no | yes | bpm | ICA on thenar: hr_bpm (section 6.3) |
| pulse__pi__thenar__ICA__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__ICA__kurtosis] |
| pulse__pi__thenar__ICA__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [thenar__ICA__n_windows]: count |
| pulse__pi__thenar__ICA__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__ICA__skewness] |
| pulse__pi__thenar__ICA__snr_db | pulse | pi | no | yes | dB | ICA on thenar: snr_db (section 6.3) |
| pulse__pi__thenar__ICA__sqi | pulse | pi | no | yes | 0..1 | ICA on thenar: sqi (section 6.3) |
| pulse__pi__thenar__ICA__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__ICA__template_corr] |
| pulse__pi__thenar__LGI__hr_bpm | pulse | pi | no | yes | bpm | LGI on thenar: hr_bpm (section 6.3) |
| pulse__pi__thenar__LGI__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__LGI__kurtosis] |
| pulse__pi__thenar__LGI__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [thenar__LGI__n_windows]: count |
| pulse__pi__thenar__LGI__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__LGI__skewness] |
| pulse__pi__thenar__LGI__snr_db | pulse | pi | no | yes | dB | LGI on thenar: snr_db (section 6.3) |
| pulse__pi__thenar__LGI__sqi | pulse | pi | no | yes | 0..1 | LGI on thenar: sqi (section 6.3) |
| pulse__pi__thenar__LGI__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__LGI__template_corr] |
| pulse__pi__thenar__OMIT__hr_bpm | pulse | pi | no | yes | bpm | OMIT on thenar: hr_bpm (section 6.3) |
| pulse__pi__thenar__OMIT__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__OMIT__kurtosis] |
| pulse__pi__thenar__OMIT__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [thenar__OMIT__n_windows]: count |
| pulse__pi__thenar__OMIT__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__OMIT__skewness] |
| pulse__pi__thenar__OMIT__snr_db | pulse | pi | no | yes | dB | OMIT on thenar: snr_db (section 6.3) |
| pulse__pi__thenar__OMIT__sqi | pulse | pi | no | yes | 0..1 | OMIT on thenar: sqi (section 6.3) |
| pulse__pi__thenar__OMIT__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__OMIT__template_corr] |
| pulse__pi__thenar__PBV__hr_bpm | pulse | pi | no | yes | bpm | PBV on thenar: hr_bpm (section 6.3) |
| pulse__pi__thenar__PBV__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__PBV__kurtosis] |
| pulse__pi__thenar__PBV__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [thenar__PBV__n_windows]: count |
| pulse__pi__thenar__PBV__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__PBV__skewness] |
| pulse__pi__thenar__PBV__snr_db | pulse | pi | no | yes | dB | PBV on thenar: snr_db (section 6.3) |
| pulse__pi__thenar__PBV__sqi | pulse | pi | no | yes | 0..1 | PBV on thenar: sqi (section 6.3) |
| pulse__pi__thenar__PBV__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__PBV__template_corr] |
| pulse__pi__thenar__PCA__hr_bpm | pulse | pi | no | yes | bpm | PCA on thenar: hr_bpm (section 6.3) |
| pulse__pi__thenar__PCA__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__PCA__kurtosis] |
| pulse__pi__thenar__PCA__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [thenar__PCA__n_windows]: count |
| pulse__pi__thenar__PCA__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__PCA__skewness] |
| pulse__pi__thenar__PCA__snr_db | pulse | pi | no | yes | dB | PCA on thenar: snr_db (section 6.3) |
| pulse__pi__thenar__PCA__sqi | pulse | pi | no | yes | 0..1 | PCA on thenar: sqi (section 6.3) |
| pulse__pi__thenar__PCA__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__PCA__template_corr] |
| pulse__pi__thenar__POS__hr_bpm | pulse | pi | no | yes | bpm | POS on thenar: hr_bpm (section 6.3) |
| pulse__pi__thenar__POS__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__POS__kurtosis] |
| pulse__pi__thenar__POS__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [thenar__POS__n_windows]: count |
| pulse__pi__thenar__POS__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__POS__skewness] |
| pulse__pi__thenar__POS__snr_db | pulse | pi | no | yes | dB | POS on thenar: snr_db (section 6.3) |
| pulse__pi__thenar__POS__sqi | pulse | pi | no | yes | 0..1 | POS on thenar: sqi (section 6.3) |
| pulse__pi__thenar__POS__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__POS__template_corr] |
| pulse__pi__volar_wrist__2SR__hr_bpm | pulse | pi | no | yes | bpm | 2SR on volar_wrist: hr_bpm (section 6.3) |
| pulse__pi__volar_wrist__2SR__snr_db | pulse | pi | no | yes | dB | 2SR on volar_wrist: snr_db (section 6.3) |
| pulse__pi__volar_wrist__2SR__sqi | pulse | pi | no | yes | 0..1 | 2SR on volar_wrist: sqi (section 6.3) |
| pulse__pi__volar_wrist__CHROM__hr_bpm | pulse | pi | no | yes | bpm | CHROM on volar_wrist: hr_bpm (section 6.3) |
| pulse__pi__volar_wrist__CHROM__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__CHROM__kurtosis] |
| pulse__pi__volar_wrist__CHROM__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__CHROM__n_windows]: count |
| pulse__pi__volar_wrist__CHROM__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__CHROM__skewness] |
| pulse__pi__volar_wrist__CHROM__snr_db | pulse | pi | no | yes | dB | CHROM on volar_wrist: snr_db (section 6.3) |
| pulse__pi__volar_wrist__CHROM__sqi | pulse | pi | no | yes | 0..1 | CHROM on volar_wrist: sqi (section 6.3) |
| pulse__pi__volar_wrist__CHROM__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__CHROM__template_corr] |
| pulse__pi__volar_wrist__GREEN__hr_bpm | pulse | pi | no | yes | bpm | GREEN on volar_wrist: hr_bpm (section 6.3) |
| pulse__pi__volar_wrist__GREEN__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__GREEN__kurtosis] |
| pulse__pi__volar_wrist__GREEN__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__GREEN__n_windows]: count |
| pulse__pi__volar_wrist__GREEN__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__GREEN__skewness] |
| pulse__pi__volar_wrist__GREEN__snr_db | pulse | pi | no | yes | dB | GREEN on volar_wrist: snr_db (section 6.3) |
| pulse__pi__volar_wrist__GREEN__sqi | pulse | pi | no | yes | 0..1 | GREEN on volar_wrist: sqi (section 6.3) |
| pulse__pi__volar_wrist__GREEN__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__GREEN__template_corr] |
| pulse__pi__volar_wrist__ICA__hr_bpm | pulse | pi | no | yes | bpm | ICA on volar_wrist: hr_bpm (section 6.3) |
| pulse__pi__volar_wrist__ICA__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__ICA__kurtosis] |
| pulse__pi__volar_wrist__ICA__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__ICA__n_windows]: count |
| pulse__pi__volar_wrist__ICA__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__ICA__skewness] |
| pulse__pi__volar_wrist__ICA__snr_db | pulse | pi | no | yes | dB | ICA on volar_wrist: snr_db (section 6.3) |
| pulse__pi__volar_wrist__ICA__sqi | pulse | pi | no | yes | 0..1 | ICA on volar_wrist: sqi (section 6.3) |
| pulse__pi__volar_wrist__ICA__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__ICA__template_corr] |
| pulse__pi__volar_wrist__LGI__hr_bpm | pulse | pi | no | yes | bpm | LGI on volar_wrist: hr_bpm (section 6.3) |
| pulse__pi__volar_wrist__LGI__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__LGI__kurtosis] |
| pulse__pi__volar_wrist__LGI__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__LGI__n_windows]: count |
| pulse__pi__volar_wrist__LGI__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__LGI__skewness] |
| pulse__pi__volar_wrist__LGI__snr_db | pulse | pi | no | yes | dB | LGI on volar_wrist: snr_db (section 6.3) |
| pulse__pi__volar_wrist__LGI__sqi | pulse | pi | no | yes | 0..1 | LGI on volar_wrist: sqi (section 6.3) |
| pulse__pi__volar_wrist__LGI__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__LGI__template_corr] |
| pulse__pi__volar_wrist__OMIT__hr_bpm | pulse | pi | no | yes | bpm | OMIT on volar_wrist: hr_bpm (section 6.3) |
| pulse__pi__volar_wrist__OMIT__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__OMIT__kurtosis] |
| pulse__pi__volar_wrist__OMIT__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__OMIT__n_windows]: count |
| pulse__pi__volar_wrist__OMIT__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__OMIT__skewness] |
| pulse__pi__volar_wrist__OMIT__snr_db | pulse | pi | no | yes | dB | OMIT on volar_wrist: snr_db (section 6.3) |
| pulse__pi__volar_wrist__OMIT__sqi | pulse | pi | no | yes | 0..1 | OMIT on volar_wrist: sqi (section 6.3) |
| pulse__pi__volar_wrist__OMIT__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__OMIT__template_corr] |
| pulse__pi__volar_wrist__PBV__hr_bpm | pulse | pi | no | yes | bpm | PBV on volar_wrist: hr_bpm (section 6.3) |
| pulse__pi__volar_wrist__PBV__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__PBV__kurtosis] |
| pulse__pi__volar_wrist__PBV__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__PBV__n_windows]: count |
| pulse__pi__volar_wrist__PBV__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__PBV__skewness] |
| pulse__pi__volar_wrist__PBV__snr_db | pulse | pi | no | yes | dB | PBV on volar_wrist: snr_db (section 6.3) |
| pulse__pi__volar_wrist__PBV__sqi | pulse | pi | no | yes | 0..1 | PBV on volar_wrist: sqi (section 6.3) |
| pulse__pi__volar_wrist__PBV__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__PBV__template_corr] |
| pulse__pi__volar_wrist__PCA__hr_bpm | pulse | pi | no | yes | bpm | PCA on volar_wrist: hr_bpm (section 6.3) |
| pulse__pi__volar_wrist__PCA__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__PCA__kurtosis] |
| pulse__pi__volar_wrist__PCA__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__PCA__n_windows]: count |
| pulse__pi__volar_wrist__PCA__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__PCA__skewness] |
| pulse__pi__volar_wrist__PCA__snr_db | pulse | pi | no | yes | dB | PCA on volar_wrist: snr_db (section 6.3) |
| pulse__pi__volar_wrist__PCA__sqi | pulse | pi | no | yes | 0..1 | PCA on volar_wrist: sqi (section 6.3) |
| pulse__pi__volar_wrist__PCA__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__PCA__template_corr] |
| pulse__pi__volar_wrist__POS__hr_bpm | pulse | pi | no | yes | bpm | POS on volar_wrist: hr_bpm (section 6.3) |
| pulse__pi__volar_wrist__POS__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__POS__kurtosis] |
| pulse__pi__volar_wrist__POS__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__POS__n_windows]: count |
| pulse__pi__volar_wrist__POS__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__POS__skewness] |
| pulse__pi__volar_wrist__POS__snr_db | pulse | pi | no | yes | dB | POS on volar_wrist: snr_db (section 6.3) |
| pulse__pi__volar_wrist__POS__sqi | pulse | pi | no | yes | 0..1 | POS on volar_wrist: sqi (section 6.3) |
| pulse__pi__volar_wrist__POS__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__POS__template_corr] |
| pulse__pi__whole_palm__2SR__hr_bpm | pulse | pi | no | yes | bpm | 2SR on whole_palm: hr_bpm (section 6.3) |
| pulse__pi__whole_palm__2SR__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__2SR__kurtosis] |
| pulse__pi__whole_palm__2SR__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__2SR__n_windows]: count |
| pulse__pi__whole_palm__2SR__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__2SR__skewness] |
| pulse__pi__whole_palm__2SR__snr_db | pulse | pi | no | yes | dB | 2SR on whole_palm: snr_db (section 6.3) |
| pulse__pi__whole_palm__2SR__sqi | pulse | pi | no | yes | 0..1 | 2SR on whole_palm: sqi (section 6.3) |
| pulse__pi__whole_palm__2SR__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__2SR__template_corr] |
| pulse__pi__whole_palm__CHROM__hr_bpm | pulse | pi | no | yes | bpm | CHROM on whole_palm: hr_bpm (section 6.3) |
| pulse__pi__whole_palm__CHROM__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__CHROM__kurtosis] |
| pulse__pi__whole_palm__CHROM__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__CHROM__n_windows]: count |
| pulse__pi__whole_palm__CHROM__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__CHROM__skewness] |
| pulse__pi__whole_palm__CHROM__snr_db | pulse | pi | no | yes | dB | CHROM on whole_palm: snr_db (section 6.3) |
| pulse__pi__whole_palm__CHROM__sqi | pulse | pi | no | yes | 0..1 | CHROM on whole_palm: sqi (section 6.3) |
| pulse__pi__whole_palm__CHROM__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__CHROM__template_corr] |
| pulse__pi__whole_palm__GREEN__hr_bpm | pulse | pi | no | yes | bpm | GREEN on whole_palm: hr_bpm (section 6.3) |
| pulse__pi__whole_palm__GREEN__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__GREEN__kurtosis] |
| pulse__pi__whole_palm__GREEN__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__GREEN__n_windows]: count |
| pulse__pi__whole_palm__GREEN__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__GREEN__skewness] |
| pulse__pi__whole_palm__GREEN__snr_db | pulse | pi | no | yes | dB | GREEN on whole_palm: snr_db (section 6.3) |
| pulse__pi__whole_palm__GREEN__sqi | pulse | pi | no | yes | 0..1 | GREEN on whole_palm: sqi (section 6.3) |
| pulse__pi__whole_palm__GREEN__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__GREEN__template_corr] |
| pulse__pi__whole_palm__ICA__hr_bpm | pulse | pi | no | yes | bpm | ICA on whole_palm: hr_bpm (section 6.3) |
| pulse__pi__whole_palm__ICA__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__ICA__kurtosis] |
| pulse__pi__whole_palm__ICA__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__ICA__n_windows]: count |
| pulse__pi__whole_palm__ICA__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__ICA__skewness] |
| pulse__pi__whole_palm__ICA__snr_db | pulse | pi | no | yes | dB | ICA on whole_palm: snr_db (section 6.3) |
| pulse__pi__whole_palm__ICA__sqi | pulse | pi | no | yes | 0..1 | ICA on whole_palm: sqi (section 6.3) |
| pulse__pi__whole_palm__ICA__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__ICA__template_corr] |
| pulse__pi__whole_palm__LGI__hr_bpm | pulse | pi | no | yes | bpm | LGI on whole_palm: hr_bpm (section 6.3) |
| pulse__pi__whole_palm__LGI__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__LGI__kurtosis] |
| pulse__pi__whole_palm__LGI__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__LGI__n_windows]: count |
| pulse__pi__whole_palm__LGI__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__LGI__skewness] |
| pulse__pi__whole_palm__LGI__snr_db | pulse | pi | no | yes | dB | LGI on whole_palm: snr_db (section 6.3) |
| pulse__pi__whole_palm__LGI__sqi | pulse | pi | no | yes | 0..1 | LGI on whole_palm: sqi (section 6.3) |
| pulse__pi__whole_palm__LGI__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__LGI__template_corr] |
| pulse__pi__whole_palm__OMIT__hr_bpm | pulse | pi | no | yes | bpm | OMIT on whole_palm: hr_bpm (section 6.3) |
| pulse__pi__whole_palm__OMIT__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__OMIT__kurtosis] |
| pulse__pi__whole_palm__OMIT__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__OMIT__n_windows]: count |
| pulse__pi__whole_palm__OMIT__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__OMIT__skewness] |
| pulse__pi__whole_palm__OMIT__snr_db | pulse | pi | no | yes | dB | OMIT on whole_palm: snr_db (section 6.3) |
| pulse__pi__whole_palm__OMIT__sqi | pulse | pi | no | yes | 0..1 | OMIT on whole_palm: sqi (section 6.3) |
| pulse__pi__whole_palm__OMIT__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__OMIT__template_corr] |
| pulse__pi__whole_palm__PBV__hr_bpm | pulse | pi | no | yes | bpm | PBV on whole_palm: hr_bpm (section 6.3) |
| pulse__pi__whole_palm__PBV__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__PBV__kurtosis] |
| pulse__pi__whole_palm__PBV__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__PBV__n_windows]: count |
| pulse__pi__whole_palm__PBV__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__PBV__skewness] |
| pulse__pi__whole_palm__PBV__snr_db | pulse | pi | no | yes | dB | PBV on whole_palm: snr_db (section 6.3) |
| pulse__pi__whole_palm__PBV__sqi | pulse | pi | no | yes | 0..1 | PBV on whole_palm: sqi (section 6.3) |
| pulse__pi__whole_palm__PBV__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__PBV__template_corr] |
| pulse__pi__whole_palm__PCA__hr_bpm | pulse | pi | no | yes | bpm | PCA on whole_palm: hr_bpm (section 6.3) |
| pulse__pi__whole_palm__PCA__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__PCA__kurtosis] |
| pulse__pi__whole_palm__PCA__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__PCA__n_windows]: count |
| pulse__pi__whole_palm__PCA__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__PCA__skewness] |
| pulse__pi__whole_palm__PCA__snr_db | pulse | pi | no | yes | dB | PCA on whole_palm: snr_db (section 6.3) |
| pulse__pi__whole_palm__PCA__sqi | pulse | pi | no | yes | 0..1 | PCA on whole_palm: sqi (section 6.3) |
| pulse__pi__whole_palm__PCA__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__PCA__template_corr] |
| pulse__pi__whole_palm__POS__hr_bpm | pulse | pi | no | yes | bpm | POS on whole_palm: hr_bpm (section 6.3) |
| pulse__pi__whole_palm__POS__kurtosis | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__POS__kurtosis] |
| pulse__pi__whole_palm__POS__n_windows | pulse | pi | no | yes | count | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__POS__n_windows]: count |
| pulse__pi__whole_palm__POS__skewness | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__POS__skewness] |
| pulse__pi__whole_palm__POS__snr_db | pulse | pi | no | yes | dB | POS on whole_palm: snr_db (section 6.3) |
| pulse__pi__whole_palm__POS__sqi | pulse | pi | no | yes | 0..1 | POS on whole_palm: sqi (section 6.3) |
| pulse__pi__whole_palm__POS__template_corr | pulse | pi | no | yes |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__POS__template_corr] |
| pulse__pi_proxy__best | pulse | pi_proxy | no | no | label | best method__roi by SQI |
| pulse__pi_proxy__best__hr_bpm | pulse | pi_proxy | no | no | bpm | pulse extraction summary per method and ROI (protocol 6.3) [best__hr_bpm]: pulse rate of the dominant spectral peak |
| pulse__pi_proxy__best__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [best__kurtosis] |
| pulse__pi_proxy__best__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [best__n_windows]: count |
| pulse__pi_proxy__best__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [best__skewness] |
| pulse__pi_proxy__best__snr_db | pulse | pi_proxy | no | no | dB | pulse extraction summary per method and ROI (protocol 6.3) [best__snr_db]: SNR of the dominant band peak versus the rest of the band |
| pulse__pi_proxy__best__sqi | pulse | pi_proxy | no | no | 0..1 | pulse extraction summary per method and ROI (protocol 6.3) [best__sqi]: signal quality index (snr_band, CONTRACTS section 6) |
| pulse__pi_proxy__best__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [best__template_corr] |
| pulse__pi_proxy__central_palm__2SR__hr_bpm | pulse | pi_proxy | no | no | bpm | 2SR on central_palm: hr_bpm (section 6.3) |
| pulse__pi_proxy__central_palm__2SR__snr_db | pulse | pi_proxy | no | no | dB | 2SR on central_palm: snr_db (section 6.3) |
| pulse__pi_proxy__central_palm__2SR__sqi | pulse | pi_proxy | no | no | 0..1 | 2SR on central_palm: sqi (section 6.3) |
| pulse__pi_proxy__central_palm__CHROM__hr_bpm | pulse | pi_proxy | no | no | bpm | CHROM on central_palm: hr_bpm (section 6.3) |
| pulse__pi_proxy__central_palm__CHROM__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__CHROM__kurtosis] |
| pulse__pi_proxy__central_palm__CHROM__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__CHROM__n_windows]: count |
| pulse__pi_proxy__central_palm__CHROM__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__CHROM__skewness] |
| pulse__pi_proxy__central_palm__CHROM__snr_db | pulse | pi_proxy | no | no | dB | CHROM on central_palm: snr_db (section 6.3) |
| pulse__pi_proxy__central_palm__CHROM__sqi | pulse | pi_proxy | no | no | 0..1 | CHROM on central_palm: sqi (section 6.3) |
| pulse__pi_proxy__central_palm__CHROM__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__CHROM__template_corr] |
| pulse__pi_proxy__central_palm__GREEN__hr_bpm | pulse | pi_proxy | no | no | bpm | GREEN on central_palm: hr_bpm (section 6.3) |
| pulse__pi_proxy__central_palm__GREEN__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__GREEN__kurtosis] |
| pulse__pi_proxy__central_palm__GREEN__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__GREEN__n_windows]: count |
| pulse__pi_proxy__central_palm__GREEN__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__GREEN__skewness] |
| pulse__pi_proxy__central_palm__GREEN__snr_db | pulse | pi_proxy | no | no | dB | GREEN on central_palm: snr_db (section 6.3) |
| pulse__pi_proxy__central_palm__GREEN__sqi | pulse | pi_proxy | no | no | 0..1 | GREEN on central_palm: sqi (section 6.3) |
| pulse__pi_proxy__central_palm__GREEN__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__GREEN__template_corr] |
| pulse__pi_proxy__central_palm__ICA__hr_bpm | pulse | pi_proxy | no | no | bpm | ICA on central_palm: hr_bpm (section 6.3) |
| pulse__pi_proxy__central_palm__ICA__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__ICA__kurtosis] |
| pulse__pi_proxy__central_palm__ICA__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__ICA__n_windows]: count |
| pulse__pi_proxy__central_palm__ICA__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__ICA__skewness] |
| pulse__pi_proxy__central_palm__ICA__snr_db | pulse | pi_proxy | no | no | dB | ICA on central_palm: snr_db (section 6.3) |
| pulse__pi_proxy__central_palm__ICA__sqi | pulse | pi_proxy | no | no | 0..1 | ICA on central_palm: sqi (section 6.3) |
| pulse__pi_proxy__central_palm__ICA__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__ICA__template_corr] |
| pulse__pi_proxy__central_palm__LGI__hr_bpm | pulse | pi_proxy | no | no | bpm | LGI on central_palm: hr_bpm (section 6.3) |
| pulse__pi_proxy__central_palm__LGI__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__LGI__kurtosis] |
| pulse__pi_proxy__central_palm__LGI__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__LGI__n_windows]: count |
| pulse__pi_proxy__central_palm__LGI__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__LGI__skewness] |
| pulse__pi_proxy__central_palm__LGI__snr_db | pulse | pi_proxy | no | no | dB | LGI on central_palm: snr_db (section 6.3) |
| pulse__pi_proxy__central_palm__LGI__sqi | pulse | pi_proxy | no | no | 0..1 | LGI on central_palm: sqi (section 6.3) |
| pulse__pi_proxy__central_palm__LGI__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__LGI__template_corr] |
| pulse__pi_proxy__central_palm__OMIT__hr_bpm | pulse | pi_proxy | no | no | bpm | OMIT on central_palm: hr_bpm (section 6.3) |
| pulse__pi_proxy__central_palm__OMIT__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__OMIT__kurtosis] |
| pulse__pi_proxy__central_palm__OMIT__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__OMIT__n_windows]: count |
| pulse__pi_proxy__central_palm__OMIT__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__OMIT__skewness] |
| pulse__pi_proxy__central_palm__OMIT__snr_db | pulse | pi_proxy | no | no | dB | OMIT on central_palm: snr_db (section 6.3) |
| pulse__pi_proxy__central_palm__OMIT__sqi | pulse | pi_proxy | no | no | 0..1 | OMIT on central_palm: sqi (section 6.3) |
| pulse__pi_proxy__central_palm__OMIT__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__OMIT__template_corr] |
| pulse__pi_proxy__central_palm__PBV__hr_bpm | pulse | pi_proxy | no | no | bpm | PBV on central_palm: hr_bpm (section 6.3) |
| pulse__pi_proxy__central_palm__PBV__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__PBV__kurtosis] |
| pulse__pi_proxy__central_palm__PBV__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__PBV__n_windows]: count |
| pulse__pi_proxy__central_palm__PBV__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__PBV__skewness] |
| pulse__pi_proxy__central_palm__PBV__snr_db | pulse | pi_proxy | no | no | dB | PBV on central_palm: snr_db (section 6.3) |
| pulse__pi_proxy__central_palm__PBV__sqi | pulse | pi_proxy | no | no | 0..1 | PBV on central_palm: sqi (section 6.3) |
| pulse__pi_proxy__central_palm__PBV__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__PBV__template_corr] |
| pulse__pi_proxy__central_palm__PCA__hr_bpm | pulse | pi_proxy | no | no | bpm | PCA on central_palm: hr_bpm (section 6.3) |
| pulse__pi_proxy__central_palm__PCA__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__PCA__kurtosis] |
| pulse__pi_proxy__central_palm__PCA__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__PCA__n_windows]: count |
| pulse__pi_proxy__central_palm__PCA__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__PCA__skewness] |
| pulse__pi_proxy__central_palm__PCA__snr_db | pulse | pi_proxy | no | no | dB | PCA on central_palm: snr_db (section 6.3) |
| pulse__pi_proxy__central_palm__PCA__sqi | pulse | pi_proxy | no | no | 0..1 | PCA on central_palm: sqi (section 6.3) |
| pulse__pi_proxy__central_palm__PCA__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__PCA__template_corr] |
| pulse__pi_proxy__central_palm__POS__hr_bpm | pulse | pi_proxy | no | no | bpm | POS on central_palm: hr_bpm (section 6.3) |
| pulse__pi_proxy__central_palm__POS__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__POS__kurtosis] |
| pulse__pi_proxy__central_palm__POS__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__POS__n_windows]: count |
| pulse__pi_proxy__central_palm__POS__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__POS__skewness] |
| pulse__pi_proxy__central_palm__POS__snr_db | pulse | pi_proxy | no | no | dB | POS on central_palm: snr_db (section 6.3) |
| pulse__pi_proxy__central_palm__POS__sqi | pulse | pi_proxy | no | no | 0..1 | POS on central_palm: sqi (section 6.3) |
| pulse__pi_proxy__central_palm__POS__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [central_palm__POS__template_corr] |
| pulse__pi_proxy__fused__2SR__hr_bpm | pulse | pi_proxy | no | no | bpm | 2SR on fused: hr_bpm (section 6.3) |
| pulse__pi_proxy__fused__2SR__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__2SR__kurtosis] |
| pulse__pi_proxy__fused__2SR__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [fused__2SR__n_windows]: count |
| pulse__pi_proxy__fused__2SR__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__2SR__skewness] |
| pulse__pi_proxy__fused__2SR__snr_db | pulse | pi_proxy | no | no | dB | 2SR on fused: snr_db (section 6.3) |
| pulse__pi_proxy__fused__2SR__sqi | pulse | pi_proxy | no | no | 0..1 | 2SR on fused: sqi (section 6.3) |
| pulse__pi_proxy__fused__2SR__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__2SR__template_corr] |
| pulse__pi_proxy__fused__CHROM__hr_bpm | pulse | pi_proxy | no | no | bpm | CHROM on fused: hr_bpm (section 6.3) |
| pulse__pi_proxy__fused__CHROM__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__CHROM__kurtosis] |
| pulse__pi_proxy__fused__CHROM__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [fused__CHROM__n_windows]: count |
| pulse__pi_proxy__fused__CHROM__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__CHROM__skewness] |
| pulse__pi_proxy__fused__CHROM__snr_db | pulse | pi_proxy | no | no | dB | CHROM on fused: snr_db (section 6.3) |
| pulse__pi_proxy__fused__CHROM__sqi | pulse | pi_proxy | no | no | 0..1 | CHROM on fused: sqi (section 6.3) |
| pulse__pi_proxy__fused__CHROM__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__CHROM__template_corr] |
| pulse__pi_proxy__fused__GREEN__hr_bpm | pulse | pi_proxy | no | no | bpm | GREEN on fused: hr_bpm (section 6.3) |
| pulse__pi_proxy__fused__GREEN__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__GREEN__kurtosis] |
| pulse__pi_proxy__fused__GREEN__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [fused__GREEN__n_windows]: count |
| pulse__pi_proxy__fused__GREEN__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__GREEN__skewness] |
| pulse__pi_proxy__fused__GREEN__snr_db | pulse | pi_proxy | no | no | dB | GREEN on fused: snr_db (section 6.3) |
| pulse__pi_proxy__fused__GREEN__sqi | pulse | pi_proxy | no | no | 0..1 | GREEN on fused: sqi (section 6.3) |
| pulse__pi_proxy__fused__GREEN__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__GREEN__template_corr] |
| pulse__pi_proxy__fused__ICA__hr_bpm | pulse | pi_proxy | no | no | bpm | ICA on fused: hr_bpm (section 6.3) |
| pulse__pi_proxy__fused__ICA__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__ICA__kurtosis] |
| pulse__pi_proxy__fused__ICA__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [fused__ICA__n_windows]: count |
| pulse__pi_proxy__fused__ICA__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__ICA__skewness] |
| pulse__pi_proxy__fused__ICA__snr_db | pulse | pi_proxy | no | no | dB | ICA on fused: snr_db (section 6.3) |
| pulse__pi_proxy__fused__ICA__sqi | pulse | pi_proxy | no | no | 0..1 | ICA on fused: sqi (section 6.3) |
| pulse__pi_proxy__fused__ICA__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__ICA__template_corr] |
| pulse__pi_proxy__fused__LGI__hr_bpm | pulse | pi_proxy | no | no | bpm | LGI on fused: hr_bpm (section 6.3) |
| pulse__pi_proxy__fused__LGI__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__LGI__kurtosis] |
| pulse__pi_proxy__fused__LGI__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [fused__LGI__n_windows]: count |
| pulse__pi_proxy__fused__LGI__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__LGI__skewness] |
| pulse__pi_proxy__fused__LGI__snr_db | pulse | pi_proxy | no | no | dB | LGI on fused: snr_db (section 6.3) |
| pulse__pi_proxy__fused__LGI__sqi | pulse | pi_proxy | no | no | 0..1 | LGI on fused: sqi (section 6.3) |
| pulse__pi_proxy__fused__LGI__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__LGI__template_corr] |
| pulse__pi_proxy__fused__OMIT__hr_bpm | pulse | pi_proxy | no | no | bpm | OMIT on fused: hr_bpm (section 6.3) |
| pulse__pi_proxy__fused__OMIT__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__OMIT__kurtosis] |
| pulse__pi_proxy__fused__OMIT__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [fused__OMIT__n_windows]: count |
| pulse__pi_proxy__fused__OMIT__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__OMIT__skewness] |
| pulse__pi_proxy__fused__OMIT__snr_db | pulse | pi_proxy | no | no | dB | OMIT on fused: snr_db (section 6.3) |
| pulse__pi_proxy__fused__OMIT__sqi | pulse | pi_proxy | no | no | 0..1 | OMIT on fused: sqi (section 6.3) |
| pulse__pi_proxy__fused__OMIT__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__OMIT__template_corr] |
| pulse__pi_proxy__fused__PBV__hr_bpm | pulse | pi_proxy | no | no | bpm | PBV on fused: hr_bpm (section 6.3) |
| pulse__pi_proxy__fused__PBV__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__PBV__kurtosis] |
| pulse__pi_proxy__fused__PBV__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [fused__PBV__n_windows]: count |
| pulse__pi_proxy__fused__PBV__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__PBV__skewness] |
| pulse__pi_proxy__fused__PBV__snr_db | pulse | pi_proxy | no | no | dB | PBV on fused: snr_db (section 6.3) |
| pulse__pi_proxy__fused__PBV__sqi | pulse | pi_proxy | no | no | 0..1 | PBV on fused: sqi (section 6.3) |
| pulse__pi_proxy__fused__PBV__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__PBV__template_corr] |
| pulse__pi_proxy__fused__PCA__hr_bpm | pulse | pi_proxy | no | no | bpm | PCA on fused: hr_bpm (section 6.3) |
| pulse__pi_proxy__fused__PCA__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__PCA__kurtosis] |
| pulse__pi_proxy__fused__PCA__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [fused__PCA__n_windows]: count |
| pulse__pi_proxy__fused__PCA__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__PCA__skewness] |
| pulse__pi_proxy__fused__PCA__snr_db | pulse | pi_proxy | no | no | dB | PCA on fused: snr_db (section 6.3) |
| pulse__pi_proxy__fused__PCA__sqi | pulse | pi_proxy | no | no | 0..1 | PCA on fused: sqi (section 6.3) |
| pulse__pi_proxy__fused__PCA__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__PCA__template_corr] |
| pulse__pi_proxy__fused__POS__hr_bpm | pulse | pi_proxy | no | no | bpm | POS on fused: hr_bpm (section 6.3) |
| pulse__pi_proxy__fused__POS__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__POS__kurtosis] |
| pulse__pi_proxy__fused__POS__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [fused__POS__n_windows]: count |
| pulse__pi_proxy__fused__POS__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__POS__skewness] |
| pulse__pi_proxy__fused__POS__snr_db | pulse | pi_proxy | no | no | dB | POS on fused: snr_db (section 6.3) |
| pulse__pi_proxy__fused__POS__sqi | pulse | pi_proxy | no | no | 0..1 | POS on fused: sqi (section 6.3) |
| pulse__pi_proxy__fused__POS__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [fused__POS__template_corr] |
| pulse__pi_proxy__fused__hr_bpm | pulse | pi_proxy | no | no | bpm | pulse extraction summary per method and ROI (protocol 6.3) [fused__hr_bpm]: pulse rate of the dominant spectral peak |
| pulse__pi_proxy__fused__method | pulse | pi_proxy | no | no | label | pulse extraction summary per method and ROI (protocol 6.3) [fused__method]: method name |
| pulse__pi_proxy__fused__snr_db | pulse | pi_proxy | no | no | dB | pulse extraction summary per method and ROI (protocol 6.3) [fused__snr_db]: SNR of the dominant band peak versus the rest of the band |
| pulse__pi_proxy__fused__sqi | pulse | pi_proxy | no | no | 0..1 | pulse extraction summary per method and ROI (protocol 6.3) [fused__sqi]: signal quality index (snr_band, CONTRACTS section 6) |
| pulse__pi_proxy__hypothenar__2SR__hr_bpm | pulse | pi_proxy | no | no | bpm | 2SR on hypothenar: hr_bpm (section 6.3) |
| pulse__pi_proxy__hypothenar__2SR__snr_db | pulse | pi_proxy | no | no | dB | 2SR on hypothenar: snr_db (section 6.3) |
| pulse__pi_proxy__hypothenar__2SR__sqi | pulse | pi_proxy | no | no | 0..1 | 2SR on hypothenar: sqi (section 6.3) |
| pulse__pi_proxy__hypothenar__CHROM__hr_bpm | pulse | pi_proxy | no | no | bpm | CHROM on hypothenar: hr_bpm (section 6.3) |
| pulse__pi_proxy__hypothenar__CHROM__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__CHROM__kurtosis] |
| pulse__pi_proxy__hypothenar__CHROM__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__CHROM__n_windows]: count |
| pulse__pi_proxy__hypothenar__CHROM__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__CHROM__skewness] |
| pulse__pi_proxy__hypothenar__CHROM__snr_db | pulse | pi_proxy | no | no | dB | CHROM on hypothenar: snr_db (section 6.3) |
| pulse__pi_proxy__hypothenar__CHROM__sqi | pulse | pi_proxy | no | no | 0..1 | CHROM on hypothenar: sqi (section 6.3) |
| pulse__pi_proxy__hypothenar__CHROM__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__CHROM__template_corr] |
| pulse__pi_proxy__hypothenar__GREEN__hr_bpm | pulse | pi_proxy | no | no | bpm | GREEN on hypothenar: hr_bpm (section 6.3) |
| pulse__pi_proxy__hypothenar__GREEN__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__GREEN__kurtosis] |
| pulse__pi_proxy__hypothenar__GREEN__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__GREEN__n_windows]: count |
| pulse__pi_proxy__hypothenar__GREEN__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__GREEN__skewness] |
| pulse__pi_proxy__hypothenar__GREEN__snr_db | pulse | pi_proxy | no | no | dB | GREEN on hypothenar: snr_db (section 6.3) |
| pulse__pi_proxy__hypothenar__GREEN__sqi | pulse | pi_proxy | no | no | 0..1 | GREEN on hypothenar: sqi (section 6.3) |
| pulse__pi_proxy__hypothenar__GREEN__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__GREEN__template_corr] |
| pulse__pi_proxy__hypothenar__ICA__hr_bpm | pulse | pi_proxy | no | no | bpm | ICA on hypothenar: hr_bpm (section 6.3) |
| pulse__pi_proxy__hypothenar__ICA__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__ICA__kurtosis] |
| pulse__pi_proxy__hypothenar__ICA__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__ICA__n_windows]: count |
| pulse__pi_proxy__hypothenar__ICA__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__ICA__skewness] |
| pulse__pi_proxy__hypothenar__ICA__snr_db | pulse | pi_proxy | no | no | dB | ICA on hypothenar: snr_db (section 6.3) |
| pulse__pi_proxy__hypothenar__ICA__sqi | pulse | pi_proxy | no | no | 0..1 | ICA on hypothenar: sqi (section 6.3) |
| pulse__pi_proxy__hypothenar__ICA__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__ICA__template_corr] |
| pulse__pi_proxy__hypothenar__LGI__hr_bpm | pulse | pi_proxy | no | no | bpm | LGI on hypothenar: hr_bpm (section 6.3) |
| pulse__pi_proxy__hypothenar__LGI__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__LGI__kurtosis] |
| pulse__pi_proxy__hypothenar__LGI__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__LGI__n_windows]: count |
| pulse__pi_proxy__hypothenar__LGI__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__LGI__skewness] |
| pulse__pi_proxy__hypothenar__LGI__snr_db | pulse | pi_proxy | no | no | dB | LGI on hypothenar: snr_db (section 6.3) |
| pulse__pi_proxy__hypothenar__LGI__sqi | pulse | pi_proxy | no | no | 0..1 | LGI on hypothenar: sqi (section 6.3) |
| pulse__pi_proxy__hypothenar__LGI__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__LGI__template_corr] |
| pulse__pi_proxy__hypothenar__OMIT__hr_bpm | pulse | pi_proxy | no | no | bpm | OMIT on hypothenar: hr_bpm (section 6.3) |
| pulse__pi_proxy__hypothenar__OMIT__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__OMIT__kurtosis] |
| pulse__pi_proxy__hypothenar__OMIT__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__OMIT__n_windows]: count |
| pulse__pi_proxy__hypothenar__OMIT__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__OMIT__skewness] |
| pulse__pi_proxy__hypothenar__OMIT__snr_db | pulse | pi_proxy | no | no | dB | OMIT on hypothenar: snr_db (section 6.3) |
| pulse__pi_proxy__hypothenar__OMIT__sqi | pulse | pi_proxy | no | no | 0..1 | OMIT on hypothenar: sqi (section 6.3) |
| pulse__pi_proxy__hypothenar__OMIT__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__OMIT__template_corr] |
| pulse__pi_proxy__hypothenar__PBV__hr_bpm | pulse | pi_proxy | no | no | bpm | PBV on hypothenar: hr_bpm (section 6.3) |
| pulse__pi_proxy__hypothenar__PBV__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__PBV__kurtosis] |
| pulse__pi_proxy__hypothenar__PBV__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__PBV__n_windows]: count |
| pulse__pi_proxy__hypothenar__PBV__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__PBV__skewness] |
| pulse__pi_proxy__hypothenar__PBV__snr_db | pulse | pi_proxy | no | no | dB | PBV on hypothenar: snr_db (section 6.3) |
| pulse__pi_proxy__hypothenar__PBV__sqi | pulse | pi_proxy | no | no | 0..1 | PBV on hypothenar: sqi (section 6.3) |
| pulse__pi_proxy__hypothenar__PBV__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__PBV__template_corr] |
| pulse__pi_proxy__hypothenar__PCA__hr_bpm | pulse | pi_proxy | no | no | bpm | PCA on hypothenar: hr_bpm (section 6.3) |
| pulse__pi_proxy__hypothenar__PCA__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__PCA__kurtosis] |
| pulse__pi_proxy__hypothenar__PCA__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__PCA__n_windows]: count |
| pulse__pi_proxy__hypothenar__PCA__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__PCA__skewness] |
| pulse__pi_proxy__hypothenar__PCA__snr_db | pulse | pi_proxy | no | no | dB | PCA on hypothenar: snr_db (section 6.3) |
| pulse__pi_proxy__hypothenar__PCA__sqi | pulse | pi_proxy | no | no | 0..1 | PCA on hypothenar: sqi (section 6.3) |
| pulse__pi_proxy__hypothenar__PCA__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__PCA__template_corr] |
| pulse__pi_proxy__hypothenar__POS__hr_bpm | pulse | pi_proxy | no | no | bpm | POS on hypothenar: hr_bpm (section 6.3) |
| pulse__pi_proxy__hypothenar__POS__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__POS__kurtosis] |
| pulse__pi_proxy__hypothenar__POS__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__POS__n_windows]: count |
| pulse__pi_proxy__hypothenar__POS__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__POS__skewness] |
| pulse__pi_proxy__hypothenar__POS__snr_db | pulse | pi_proxy | no | no | dB | POS on hypothenar: snr_db (section 6.3) |
| pulse__pi_proxy__hypothenar__POS__sqi | pulse | pi_proxy | no | no | 0..1 | POS on hypothenar: sqi (section 6.3) |
| pulse__pi_proxy__hypothenar__POS__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [hypothenar__POS__template_corr] |
| pulse__pi_proxy__mid_phalanges__2SR__hr_bpm | pulse | pi_proxy | no | no | bpm | 2SR on mid_phalanges: hr_bpm (section 6.3) |
| pulse__pi_proxy__mid_phalanges__2SR__snr_db | pulse | pi_proxy | no | no | dB | 2SR on mid_phalanges: snr_db (section 6.3) |
| pulse__pi_proxy__mid_phalanges__2SR__sqi | pulse | pi_proxy | no | no | 0..1 | 2SR on mid_phalanges: sqi (section 6.3) |
| pulse__pi_proxy__mid_phalanges__CHROM__hr_bpm | pulse | pi_proxy | no | no | bpm | CHROM on mid_phalanges: hr_bpm (section 6.3) |
| pulse__pi_proxy__mid_phalanges__CHROM__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__CHROM__kurtosis] |
| pulse__pi_proxy__mid_phalanges__CHROM__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__CHROM__n_windows]: count |
| pulse__pi_proxy__mid_phalanges__CHROM__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__CHROM__skewness] |
| pulse__pi_proxy__mid_phalanges__CHROM__snr_db | pulse | pi_proxy | no | no | dB | CHROM on mid_phalanges: snr_db (section 6.3) |
| pulse__pi_proxy__mid_phalanges__CHROM__sqi | pulse | pi_proxy | no | no | 0..1 | CHROM on mid_phalanges: sqi (section 6.3) |
| pulse__pi_proxy__mid_phalanges__CHROM__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__CHROM__template_corr] |
| pulse__pi_proxy__mid_phalanges__GREEN__hr_bpm | pulse | pi_proxy | no | no | bpm | GREEN on mid_phalanges: hr_bpm (section 6.3) |
| pulse__pi_proxy__mid_phalanges__GREEN__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__GREEN__kurtosis] |
| pulse__pi_proxy__mid_phalanges__GREEN__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__GREEN__n_windows]: count |
| pulse__pi_proxy__mid_phalanges__GREEN__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__GREEN__skewness] |
| pulse__pi_proxy__mid_phalanges__GREEN__snr_db | pulse | pi_proxy | no | no | dB | GREEN on mid_phalanges: snr_db (section 6.3) |
| pulse__pi_proxy__mid_phalanges__GREEN__sqi | pulse | pi_proxy | no | no | 0..1 | GREEN on mid_phalanges: sqi (section 6.3) |
| pulse__pi_proxy__mid_phalanges__GREEN__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__GREEN__template_corr] |
| pulse__pi_proxy__mid_phalanges__ICA__hr_bpm | pulse | pi_proxy | no | no | bpm | ICA on mid_phalanges: hr_bpm (section 6.3) |
| pulse__pi_proxy__mid_phalanges__ICA__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__ICA__kurtosis] |
| pulse__pi_proxy__mid_phalanges__ICA__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__ICA__n_windows]: count |
| pulse__pi_proxy__mid_phalanges__ICA__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__ICA__skewness] |
| pulse__pi_proxy__mid_phalanges__ICA__snr_db | pulse | pi_proxy | no | no | dB | ICA on mid_phalanges: snr_db (section 6.3) |
| pulse__pi_proxy__mid_phalanges__ICA__sqi | pulse | pi_proxy | no | no | 0..1 | ICA on mid_phalanges: sqi (section 6.3) |
| pulse__pi_proxy__mid_phalanges__ICA__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__ICA__template_corr] |
| pulse__pi_proxy__mid_phalanges__LGI__hr_bpm | pulse | pi_proxy | no | no | bpm | LGI on mid_phalanges: hr_bpm (section 6.3) |
| pulse__pi_proxy__mid_phalanges__LGI__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__LGI__kurtosis] |
| pulse__pi_proxy__mid_phalanges__LGI__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__LGI__n_windows]: count |
| pulse__pi_proxy__mid_phalanges__LGI__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__LGI__skewness] |
| pulse__pi_proxy__mid_phalanges__LGI__snr_db | pulse | pi_proxy | no | no | dB | LGI on mid_phalanges: snr_db (section 6.3) |
| pulse__pi_proxy__mid_phalanges__LGI__sqi | pulse | pi_proxy | no | no | 0..1 | LGI on mid_phalanges: sqi (section 6.3) |
| pulse__pi_proxy__mid_phalanges__LGI__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__LGI__template_corr] |
| pulse__pi_proxy__mid_phalanges__OMIT__hr_bpm | pulse | pi_proxy | no | no | bpm | OMIT on mid_phalanges: hr_bpm (section 6.3) |
| pulse__pi_proxy__mid_phalanges__OMIT__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__OMIT__kurtosis] |
| pulse__pi_proxy__mid_phalanges__OMIT__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__OMIT__n_windows]: count |
| pulse__pi_proxy__mid_phalanges__OMIT__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__OMIT__skewness] |
| pulse__pi_proxy__mid_phalanges__OMIT__snr_db | pulse | pi_proxy | no | no | dB | OMIT on mid_phalanges: snr_db (section 6.3) |
| pulse__pi_proxy__mid_phalanges__OMIT__sqi | pulse | pi_proxy | no | no | 0..1 | OMIT on mid_phalanges: sqi (section 6.3) |
| pulse__pi_proxy__mid_phalanges__OMIT__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__OMIT__template_corr] |
| pulse__pi_proxy__mid_phalanges__PBV__hr_bpm | pulse | pi_proxy | no | no | bpm | PBV on mid_phalanges: hr_bpm (section 6.3) |
| pulse__pi_proxy__mid_phalanges__PBV__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__PBV__kurtosis] |
| pulse__pi_proxy__mid_phalanges__PBV__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__PBV__n_windows]: count |
| pulse__pi_proxy__mid_phalanges__PBV__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__PBV__skewness] |
| pulse__pi_proxy__mid_phalanges__PBV__snr_db | pulse | pi_proxy | no | no | dB | PBV on mid_phalanges: snr_db (section 6.3) |
| pulse__pi_proxy__mid_phalanges__PBV__sqi | pulse | pi_proxy | no | no | 0..1 | PBV on mid_phalanges: sqi (section 6.3) |
| pulse__pi_proxy__mid_phalanges__PBV__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__PBV__template_corr] |
| pulse__pi_proxy__mid_phalanges__PCA__hr_bpm | pulse | pi_proxy | no | no | bpm | PCA on mid_phalanges: hr_bpm (section 6.3) |
| pulse__pi_proxy__mid_phalanges__PCA__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__PCA__kurtosis] |
| pulse__pi_proxy__mid_phalanges__PCA__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__PCA__n_windows]: count |
| pulse__pi_proxy__mid_phalanges__PCA__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__PCA__skewness] |
| pulse__pi_proxy__mid_phalanges__PCA__snr_db | pulse | pi_proxy | no | no | dB | PCA on mid_phalanges: snr_db (section 6.3) |
| pulse__pi_proxy__mid_phalanges__PCA__sqi | pulse | pi_proxy | no | no | 0..1 | PCA on mid_phalanges: sqi (section 6.3) |
| pulse__pi_proxy__mid_phalanges__PCA__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__PCA__template_corr] |
| pulse__pi_proxy__mid_phalanges__POS__hr_bpm | pulse | pi_proxy | no | no | bpm | POS on mid_phalanges: hr_bpm (section 6.3) |
| pulse__pi_proxy__mid_phalanges__POS__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__POS__kurtosis] |
| pulse__pi_proxy__mid_phalanges__POS__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__POS__n_windows]: count |
| pulse__pi_proxy__mid_phalanges__POS__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__POS__skewness] |
| pulse__pi_proxy__mid_phalanges__POS__snr_db | pulse | pi_proxy | no | no | dB | POS on mid_phalanges: snr_db (section 6.3) |
| pulse__pi_proxy__mid_phalanges__POS__sqi | pulse | pi_proxy | no | no | 0..1 | POS on mid_phalanges: sqi (section 6.3) |
| pulse__pi_proxy__mid_phalanges__POS__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [mid_phalanges__POS__template_corr] |
| pulse__pi_proxy__pad_index__2SR__hr_bpm | pulse | pi_proxy | no | no | bpm | 2SR on pad_index: hr_bpm (section 6.3) |
| pulse__pi_proxy__pad_index__2SR__snr_db | pulse | pi_proxy | no | no | dB | 2SR on pad_index: snr_db (section 6.3) |
| pulse__pi_proxy__pad_index__2SR__sqi | pulse | pi_proxy | no | no | 0..1 | 2SR on pad_index: sqi (section 6.3) |
| pulse__pi_proxy__pad_index__CHROM__hr_bpm | pulse | pi_proxy | no | no | bpm | CHROM on pad_index: hr_bpm (section 6.3) |
| pulse__pi_proxy__pad_index__CHROM__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__CHROM__kurtosis] |
| pulse__pi_proxy__pad_index__CHROM__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__CHROM__n_windows]: count |
| pulse__pi_proxy__pad_index__CHROM__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__CHROM__skewness] |
| pulse__pi_proxy__pad_index__CHROM__snr_db | pulse | pi_proxy | no | no | dB | CHROM on pad_index: snr_db (section 6.3) |
| pulse__pi_proxy__pad_index__CHROM__sqi | pulse | pi_proxy | no | no | 0..1 | CHROM on pad_index: sqi (section 6.3) |
| pulse__pi_proxy__pad_index__CHROM__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__CHROM__template_corr] |
| pulse__pi_proxy__pad_index__GREEN__hr_bpm | pulse | pi_proxy | no | no | bpm | GREEN on pad_index: hr_bpm (section 6.3) |
| pulse__pi_proxy__pad_index__GREEN__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__GREEN__kurtosis] |
| pulse__pi_proxy__pad_index__GREEN__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__GREEN__n_windows]: count |
| pulse__pi_proxy__pad_index__GREEN__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__GREEN__skewness] |
| pulse__pi_proxy__pad_index__GREEN__snr_db | pulse | pi_proxy | no | no | dB | GREEN on pad_index: snr_db (section 6.3) |
| pulse__pi_proxy__pad_index__GREEN__sqi | pulse | pi_proxy | no | no | 0..1 | GREEN on pad_index: sqi (section 6.3) |
| pulse__pi_proxy__pad_index__GREEN__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__GREEN__template_corr] |
| pulse__pi_proxy__pad_index__ICA__hr_bpm | pulse | pi_proxy | no | no | bpm | ICA on pad_index: hr_bpm (section 6.3) |
| pulse__pi_proxy__pad_index__ICA__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__ICA__kurtosis] |
| pulse__pi_proxy__pad_index__ICA__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__ICA__n_windows]: count |
| pulse__pi_proxy__pad_index__ICA__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__ICA__skewness] |
| pulse__pi_proxy__pad_index__ICA__snr_db | pulse | pi_proxy | no | no | dB | ICA on pad_index: snr_db (section 6.3) |
| pulse__pi_proxy__pad_index__ICA__sqi | pulse | pi_proxy | no | no | 0..1 | ICA on pad_index: sqi (section 6.3) |
| pulse__pi_proxy__pad_index__ICA__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__ICA__template_corr] |
| pulse__pi_proxy__pad_index__LGI__hr_bpm | pulse | pi_proxy | no | no | bpm | LGI on pad_index: hr_bpm (section 6.3) |
| pulse__pi_proxy__pad_index__LGI__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__LGI__kurtosis] |
| pulse__pi_proxy__pad_index__LGI__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__LGI__n_windows]: count |
| pulse__pi_proxy__pad_index__LGI__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__LGI__skewness] |
| pulse__pi_proxy__pad_index__LGI__snr_db | pulse | pi_proxy | no | no | dB | LGI on pad_index: snr_db (section 6.3) |
| pulse__pi_proxy__pad_index__LGI__sqi | pulse | pi_proxy | no | no | 0..1 | LGI on pad_index: sqi (section 6.3) |
| pulse__pi_proxy__pad_index__LGI__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__LGI__template_corr] |
| pulse__pi_proxy__pad_index__OMIT__hr_bpm | pulse | pi_proxy | no | no | bpm | OMIT on pad_index: hr_bpm (section 6.3) |
| pulse__pi_proxy__pad_index__OMIT__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__OMIT__kurtosis] |
| pulse__pi_proxy__pad_index__OMIT__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__OMIT__n_windows]: count |
| pulse__pi_proxy__pad_index__OMIT__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__OMIT__skewness] |
| pulse__pi_proxy__pad_index__OMIT__snr_db | pulse | pi_proxy | no | no | dB | OMIT on pad_index: snr_db (section 6.3) |
| pulse__pi_proxy__pad_index__OMIT__sqi | pulse | pi_proxy | no | no | 0..1 | OMIT on pad_index: sqi (section 6.3) |
| pulse__pi_proxy__pad_index__OMIT__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__OMIT__template_corr] |
| pulse__pi_proxy__pad_index__PBV__hr_bpm | pulse | pi_proxy | no | no | bpm | PBV on pad_index: hr_bpm (section 6.3) |
| pulse__pi_proxy__pad_index__PBV__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__PBV__kurtosis] |
| pulse__pi_proxy__pad_index__PBV__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__PBV__n_windows]: count |
| pulse__pi_proxy__pad_index__PBV__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__PBV__skewness] |
| pulse__pi_proxy__pad_index__PBV__snr_db | pulse | pi_proxy | no | no | dB | PBV on pad_index: snr_db (section 6.3) |
| pulse__pi_proxy__pad_index__PBV__sqi | pulse | pi_proxy | no | no | 0..1 | PBV on pad_index: sqi (section 6.3) |
| pulse__pi_proxy__pad_index__PBV__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__PBV__template_corr] |
| pulse__pi_proxy__pad_index__PCA__hr_bpm | pulse | pi_proxy | no | no | bpm | PCA on pad_index: hr_bpm (section 6.3) |
| pulse__pi_proxy__pad_index__PCA__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__PCA__kurtosis] |
| pulse__pi_proxy__pad_index__PCA__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__PCA__n_windows]: count |
| pulse__pi_proxy__pad_index__PCA__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__PCA__skewness] |
| pulse__pi_proxy__pad_index__PCA__snr_db | pulse | pi_proxy | no | no | dB | PCA on pad_index: snr_db (section 6.3) |
| pulse__pi_proxy__pad_index__PCA__sqi | pulse | pi_proxy | no | no | 0..1 | PCA on pad_index: sqi (section 6.3) |
| pulse__pi_proxy__pad_index__PCA__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__PCA__template_corr] |
| pulse__pi_proxy__pad_index__POS__hr_bpm | pulse | pi_proxy | no | no | bpm | POS on pad_index: hr_bpm (section 6.3) |
| pulse__pi_proxy__pad_index__POS__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__POS__kurtosis] |
| pulse__pi_proxy__pad_index__POS__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__POS__n_windows]: count |
| pulse__pi_proxy__pad_index__POS__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__POS__skewness] |
| pulse__pi_proxy__pad_index__POS__snr_db | pulse | pi_proxy | no | no | dB | POS on pad_index: snr_db (section 6.3) |
| pulse__pi_proxy__pad_index__POS__sqi | pulse | pi_proxy | no | no | 0..1 | POS on pad_index: sqi (section 6.3) |
| pulse__pi_proxy__pad_index__POS__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_index__POS__template_corr] |
| pulse__pi_proxy__pad_little__2SR__hr_bpm | pulse | pi_proxy | no | no | bpm | 2SR on pad_little: hr_bpm (section 6.3) |
| pulse__pi_proxy__pad_little__2SR__snr_db | pulse | pi_proxy | no | no | dB | 2SR on pad_little: snr_db (section 6.3) |
| pulse__pi_proxy__pad_little__2SR__sqi | pulse | pi_proxy | no | no | 0..1 | 2SR on pad_little: sqi (section 6.3) |
| pulse__pi_proxy__pad_little__CHROM__hr_bpm | pulse | pi_proxy | no | no | bpm | CHROM on pad_little: hr_bpm (section 6.3) |
| pulse__pi_proxy__pad_little__CHROM__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__CHROM__kurtosis] |
| pulse__pi_proxy__pad_little__CHROM__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__CHROM__n_windows]: count |
| pulse__pi_proxy__pad_little__CHROM__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__CHROM__skewness] |
| pulse__pi_proxy__pad_little__CHROM__snr_db | pulse | pi_proxy | no | no | dB | CHROM on pad_little: snr_db (section 6.3) |
| pulse__pi_proxy__pad_little__CHROM__sqi | pulse | pi_proxy | no | no | 0..1 | CHROM on pad_little: sqi (section 6.3) |
| pulse__pi_proxy__pad_little__CHROM__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__CHROM__template_corr] |
| pulse__pi_proxy__pad_little__GREEN__hr_bpm | pulse | pi_proxy | no | no | bpm | GREEN on pad_little: hr_bpm (section 6.3) |
| pulse__pi_proxy__pad_little__GREEN__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__GREEN__kurtosis] |
| pulse__pi_proxy__pad_little__GREEN__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__GREEN__n_windows]: count |
| pulse__pi_proxy__pad_little__GREEN__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__GREEN__skewness] |
| pulse__pi_proxy__pad_little__GREEN__snr_db | pulse | pi_proxy | no | no | dB | GREEN on pad_little: snr_db (section 6.3) |
| pulse__pi_proxy__pad_little__GREEN__sqi | pulse | pi_proxy | no | no | 0..1 | GREEN on pad_little: sqi (section 6.3) |
| pulse__pi_proxy__pad_little__GREEN__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__GREEN__template_corr] |
| pulse__pi_proxy__pad_little__ICA__hr_bpm | pulse | pi_proxy | no | no | bpm | ICA on pad_little: hr_bpm (section 6.3) |
| pulse__pi_proxy__pad_little__ICA__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__ICA__kurtosis] |
| pulse__pi_proxy__pad_little__ICA__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__ICA__n_windows]: count |
| pulse__pi_proxy__pad_little__ICA__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__ICA__skewness] |
| pulse__pi_proxy__pad_little__ICA__snr_db | pulse | pi_proxy | no | no | dB | ICA on pad_little: snr_db (section 6.3) |
| pulse__pi_proxy__pad_little__ICA__sqi | pulse | pi_proxy | no | no | 0..1 | ICA on pad_little: sqi (section 6.3) |
| pulse__pi_proxy__pad_little__ICA__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__ICA__template_corr] |
| pulse__pi_proxy__pad_little__LGI__hr_bpm | pulse | pi_proxy | no | no | bpm | LGI on pad_little: hr_bpm (section 6.3) |
| pulse__pi_proxy__pad_little__LGI__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__LGI__kurtosis] |
| pulse__pi_proxy__pad_little__LGI__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__LGI__n_windows]: count |
| pulse__pi_proxy__pad_little__LGI__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__LGI__skewness] |
| pulse__pi_proxy__pad_little__LGI__snr_db | pulse | pi_proxy | no | no | dB | LGI on pad_little: snr_db (section 6.3) |
| pulse__pi_proxy__pad_little__LGI__sqi | pulse | pi_proxy | no | no | 0..1 | LGI on pad_little: sqi (section 6.3) |
| pulse__pi_proxy__pad_little__LGI__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__LGI__template_corr] |
| pulse__pi_proxy__pad_little__OMIT__hr_bpm | pulse | pi_proxy | no | no | bpm | OMIT on pad_little: hr_bpm (section 6.3) |
| pulse__pi_proxy__pad_little__OMIT__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__OMIT__kurtosis] |
| pulse__pi_proxy__pad_little__OMIT__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__OMIT__n_windows]: count |
| pulse__pi_proxy__pad_little__OMIT__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__OMIT__skewness] |
| pulse__pi_proxy__pad_little__OMIT__snr_db | pulse | pi_proxy | no | no | dB | OMIT on pad_little: snr_db (section 6.3) |
| pulse__pi_proxy__pad_little__OMIT__sqi | pulse | pi_proxy | no | no | 0..1 | OMIT on pad_little: sqi (section 6.3) |
| pulse__pi_proxy__pad_little__OMIT__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__OMIT__template_corr] |
| pulse__pi_proxy__pad_little__PBV__hr_bpm | pulse | pi_proxy | no | no | bpm | PBV on pad_little: hr_bpm (section 6.3) |
| pulse__pi_proxy__pad_little__PBV__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__PBV__kurtosis] |
| pulse__pi_proxy__pad_little__PBV__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__PBV__n_windows]: count |
| pulse__pi_proxy__pad_little__PBV__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__PBV__skewness] |
| pulse__pi_proxy__pad_little__PBV__snr_db | pulse | pi_proxy | no | no | dB | PBV on pad_little: snr_db (section 6.3) |
| pulse__pi_proxy__pad_little__PBV__sqi | pulse | pi_proxy | no | no | 0..1 | PBV on pad_little: sqi (section 6.3) |
| pulse__pi_proxy__pad_little__PBV__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__PBV__template_corr] |
| pulse__pi_proxy__pad_little__PCA__hr_bpm | pulse | pi_proxy | no | no | bpm | PCA on pad_little: hr_bpm (section 6.3) |
| pulse__pi_proxy__pad_little__PCA__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__PCA__kurtosis] |
| pulse__pi_proxy__pad_little__PCA__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__PCA__n_windows]: count |
| pulse__pi_proxy__pad_little__PCA__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__PCA__skewness] |
| pulse__pi_proxy__pad_little__PCA__snr_db | pulse | pi_proxy | no | no | dB | PCA on pad_little: snr_db (section 6.3) |
| pulse__pi_proxy__pad_little__PCA__sqi | pulse | pi_proxy | no | no | 0..1 | PCA on pad_little: sqi (section 6.3) |
| pulse__pi_proxy__pad_little__PCA__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__PCA__template_corr] |
| pulse__pi_proxy__pad_little__POS__hr_bpm | pulse | pi_proxy | no | no | bpm | POS on pad_little: hr_bpm (section 6.3) |
| pulse__pi_proxy__pad_little__POS__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__POS__kurtosis] |
| pulse__pi_proxy__pad_little__POS__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__POS__n_windows]: count |
| pulse__pi_proxy__pad_little__POS__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__POS__skewness] |
| pulse__pi_proxy__pad_little__POS__snr_db | pulse | pi_proxy | no | no | dB | POS on pad_little: snr_db (section 6.3) |
| pulse__pi_proxy__pad_little__POS__sqi | pulse | pi_proxy | no | no | 0..1 | POS on pad_little: sqi (section 6.3) |
| pulse__pi_proxy__pad_little__POS__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_little__POS__template_corr] |
| pulse__pi_proxy__pad_middle__2SR__hr_bpm | pulse | pi_proxy | no | no | bpm | 2SR on pad_middle: hr_bpm (section 6.3) |
| pulse__pi_proxy__pad_middle__2SR__snr_db | pulse | pi_proxy | no | no | dB | 2SR on pad_middle: snr_db (section 6.3) |
| pulse__pi_proxy__pad_middle__2SR__sqi | pulse | pi_proxy | no | no | 0..1 | 2SR on pad_middle: sqi (section 6.3) |
| pulse__pi_proxy__pad_middle__CHROM__hr_bpm | pulse | pi_proxy | no | no | bpm | CHROM on pad_middle: hr_bpm (section 6.3) |
| pulse__pi_proxy__pad_middle__CHROM__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__CHROM__kurtosis] |
| pulse__pi_proxy__pad_middle__CHROM__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__CHROM__n_windows]: count |
| pulse__pi_proxy__pad_middle__CHROM__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__CHROM__skewness] |
| pulse__pi_proxy__pad_middle__CHROM__snr_db | pulse | pi_proxy | no | no | dB | CHROM on pad_middle: snr_db (section 6.3) |
| pulse__pi_proxy__pad_middle__CHROM__sqi | pulse | pi_proxy | no | no | 0..1 | CHROM on pad_middle: sqi (section 6.3) |
| pulse__pi_proxy__pad_middle__CHROM__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__CHROM__template_corr] |
| pulse__pi_proxy__pad_middle__GREEN__hr_bpm | pulse | pi_proxy | no | no | bpm | GREEN on pad_middle: hr_bpm (section 6.3) |
| pulse__pi_proxy__pad_middle__GREEN__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__GREEN__kurtosis] |
| pulse__pi_proxy__pad_middle__GREEN__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__GREEN__n_windows]: count |
| pulse__pi_proxy__pad_middle__GREEN__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__GREEN__skewness] |
| pulse__pi_proxy__pad_middle__GREEN__snr_db | pulse | pi_proxy | no | no | dB | GREEN on pad_middle: snr_db (section 6.3) |
| pulse__pi_proxy__pad_middle__GREEN__sqi | pulse | pi_proxy | no | no | 0..1 | GREEN on pad_middle: sqi (section 6.3) |
| pulse__pi_proxy__pad_middle__GREEN__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__GREEN__template_corr] |
| pulse__pi_proxy__pad_middle__ICA__hr_bpm | pulse | pi_proxy | no | no | bpm | ICA on pad_middle: hr_bpm (section 6.3) |
| pulse__pi_proxy__pad_middle__ICA__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__ICA__kurtosis] |
| pulse__pi_proxy__pad_middle__ICA__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__ICA__n_windows]: count |
| pulse__pi_proxy__pad_middle__ICA__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__ICA__skewness] |
| pulse__pi_proxy__pad_middle__ICA__snr_db | pulse | pi_proxy | no | no | dB | ICA on pad_middle: snr_db (section 6.3) |
| pulse__pi_proxy__pad_middle__ICA__sqi | pulse | pi_proxy | no | no | 0..1 | ICA on pad_middle: sqi (section 6.3) |
| pulse__pi_proxy__pad_middle__ICA__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__ICA__template_corr] |
| pulse__pi_proxy__pad_middle__LGI__hr_bpm | pulse | pi_proxy | no | no | bpm | LGI on pad_middle: hr_bpm (section 6.3) |
| pulse__pi_proxy__pad_middle__LGI__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__LGI__kurtosis] |
| pulse__pi_proxy__pad_middle__LGI__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__LGI__n_windows]: count |
| pulse__pi_proxy__pad_middle__LGI__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__LGI__skewness] |
| pulse__pi_proxy__pad_middle__LGI__snr_db | pulse | pi_proxy | no | no | dB | LGI on pad_middle: snr_db (section 6.3) |
| pulse__pi_proxy__pad_middle__LGI__sqi | pulse | pi_proxy | no | no | 0..1 | LGI on pad_middle: sqi (section 6.3) |
| pulse__pi_proxy__pad_middle__LGI__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__LGI__template_corr] |
| pulse__pi_proxy__pad_middle__OMIT__hr_bpm | pulse | pi_proxy | no | no | bpm | OMIT on pad_middle: hr_bpm (section 6.3) |
| pulse__pi_proxy__pad_middle__OMIT__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__OMIT__kurtosis] |
| pulse__pi_proxy__pad_middle__OMIT__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__OMIT__n_windows]: count |
| pulse__pi_proxy__pad_middle__OMIT__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__OMIT__skewness] |
| pulse__pi_proxy__pad_middle__OMIT__snr_db | pulse | pi_proxy | no | no | dB | OMIT on pad_middle: snr_db (section 6.3) |
| pulse__pi_proxy__pad_middle__OMIT__sqi | pulse | pi_proxy | no | no | 0..1 | OMIT on pad_middle: sqi (section 6.3) |
| pulse__pi_proxy__pad_middle__OMIT__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__OMIT__template_corr] |
| pulse__pi_proxy__pad_middle__PBV__hr_bpm | pulse | pi_proxy | no | no | bpm | PBV on pad_middle: hr_bpm (section 6.3) |
| pulse__pi_proxy__pad_middle__PBV__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__PBV__kurtosis] |
| pulse__pi_proxy__pad_middle__PBV__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__PBV__n_windows]: count |
| pulse__pi_proxy__pad_middle__PBV__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__PBV__skewness] |
| pulse__pi_proxy__pad_middle__PBV__snr_db | pulse | pi_proxy | no | no | dB | PBV on pad_middle: snr_db (section 6.3) |
| pulse__pi_proxy__pad_middle__PBV__sqi | pulse | pi_proxy | no | no | 0..1 | PBV on pad_middle: sqi (section 6.3) |
| pulse__pi_proxy__pad_middle__PBV__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__PBV__template_corr] |
| pulse__pi_proxy__pad_middle__PCA__hr_bpm | pulse | pi_proxy | no | no | bpm | PCA on pad_middle: hr_bpm (section 6.3) |
| pulse__pi_proxy__pad_middle__PCA__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__PCA__kurtosis] |
| pulse__pi_proxy__pad_middle__PCA__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__PCA__n_windows]: count |
| pulse__pi_proxy__pad_middle__PCA__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__PCA__skewness] |
| pulse__pi_proxy__pad_middle__PCA__snr_db | pulse | pi_proxy | no | no | dB | PCA on pad_middle: snr_db (section 6.3) |
| pulse__pi_proxy__pad_middle__PCA__sqi | pulse | pi_proxy | no | no | 0..1 | PCA on pad_middle: sqi (section 6.3) |
| pulse__pi_proxy__pad_middle__PCA__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__PCA__template_corr] |
| pulse__pi_proxy__pad_middle__POS__hr_bpm | pulse | pi_proxy | no | no | bpm | POS on pad_middle: hr_bpm (section 6.3) |
| pulse__pi_proxy__pad_middle__POS__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__POS__kurtosis] |
| pulse__pi_proxy__pad_middle__POS__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__POS__n_windows]: count |
| pulse__pi_proxy__pad_middle__POS__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__POS__skewness] |
| pulse__pi_proxy__pad_middle__POS__snr_db | pulse | pi_proxy | no | no | dB | POS on pad_middle: snr_db (section 6.3) |
| pulse__pi_proxy__pad_middle__POS__sqi | pulse | pi_proxy | no | no | 0..1 | POS on pad_middle: sqi (section 6.3) |
| pulse__pi_proxy__pad_middle__POS__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_middle__POS__template_corr] |
| pulse__pi_proxy__pad_ring__2SR__hr_bpm | pulse | pi_proxy | no | no | bpm | 2SR on pad_ring: hr_bpm (section 6.3) |
| pulse__pi_proxy__pad_ring__2SR__snr_db | pulse | pi_proxy | no | no | dB | 2SR on pad_ring: snr_db (section 6.3) |
| pulse__pi_proxy__pad_ring__2SR__sqi | pulse | pi_proxy | no | no | 0..1 | 2SR on pad_ring: sqi (section 6.3) |
| pulse__pi_proxy__pad_ring__CHROM__hr_bpm | pulse | pi_proxy | no | no | bpm | CHROM on pad_ring: hr_bpm (section 6.3) |
| pulse__pi_proxy__pad_ring__CHROM__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__CHROM__kurtosis] |
| pulse__pi_proxy__pad_ring__CHROM__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__CHROM__n_windows]: count |
| pulse__pi_proxy__pad_ring__CHROM__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__CHROM__skewness] |
| pulse__pi_proxy__pad_ring__CHROM__snr_db | pulse | pi_proxy | no | no | dB | CHROM on pad_ring: snr_db (section 6.3) |
| pulse__pi_proxy__pad_ring__CHROM__sqi | pulse | pi_proxy | no | no | 0..1 | CHROM on pad_ring: sqi (section 6.3) |
| pulse__pi_proxy__pad_ring__CHROM__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__CHROM__template_corr] |
| pulse__pi_proxy__pad_ring__GREEN__hr_bpm | pulse | pi_proxy | no | no | bpm | GREEN on pad_ring: hr_bpm (section 6.3) |
| pulse__pi_proxy__pad_ring__GREEN__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__GREEN__kurtosis] |
| pulse__pi_proxy__pad_ring__GREEN__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__GREEN__n_windows]: count |
| pulse__pi_proxy__pad_ring__GREEN__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__GREEN__skewness] |
| pulse__pi_proxy__pad_ring__GREEN__snr_db | pulse | pi_proxy | no | no | dB | GREEN on pad_ring: snr_db (section 6.3) |
| pulse__pi_proxy__pad_ring__GREEN__sqi | pulse | pi_proxy | no | no | 0..1 | GREEN on pad_ring: sqi (section 6.3) |
| pulse__pi_proxy__pad_ring__GREEN__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__GREEN__template_corr] |
| pulse__pi_proxy__pad_ring__ICA__hr_bpm | pulse | pi_proxy | no | no | bpm | ICA on pad_ring: hr_bpm (section 6.3) |
| pulse__pi_proxy__pad_ring__ICA__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__ICA__kurtosis] |
| pulse__pi_proxy__pad_ring__ICA__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__ICA__n_windows]: count |
| pulse__pi_proxy__pad_ring__ICA__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__ICA__skewness] |
| pulse__pi_proxy__pad_ring__ICA__snr_db | pulse | pi_proxy | no | no | dB | ICA on pad_ring: snr_db (section 6.3) |
| pulse__pi_proxy__pad_ring__ICA__sqi | pulse | pi_proxy | no | no | 0..1 | ICA on pad_ring: sqi (section 6.3) |
| pulse__pi_proxy__pad_ring__ICA__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__ICA__template_corr] |
| pulse__pi_proxy__pad_ring__LGI__hr_bpm | pulse | pi_proxy | no | no | bpm | LGI on pad_ring: hr_bpm (section 6.3) |
| pulse__pi_proxy__pad_ring__LGI__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__LGI__kurtosis] |
| pulse__pi_proxy__pad_ring__LGI__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__LGI__n_windows]: count |
| pulse__pi_proxy__pad_ring__LGI__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__LGI__skewness] |
| pulse__pi_proxy__pad_ring__LGI__snr_db | pulse | pi_proxy | no | no | dB | LGI on pad_ring: snr_db (section 6.3) |
| pulse__pi_proxy__pad_ring__LGI__sqi | pulse | pi_proxy | no | no | 0..1 | LGI on pad_ring: sqi (section 6.3) |
| pulse__pi_proxy__pad_ring__LGI__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__LGI__template_corr] |
| pulse__pi_proxy__pad_ring__OMIT__hr_bpm | pulse | pi_proxy | no | no | bpm | OMIT on pad_ring: hr_bpm (section 6.3) |
| pulse__pi_proxy__pad_ring__OMIT__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__OMIT__kurtosis] |
| pulse__pi_proxy__pad_ring__OMIT__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__OMIT__n_windows]: count |
| pulse__pi_proxy__pad_ring__OMIT__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__OMIT__skewness] |
| pulse__pi_proxy__pad_ring__OMIT__snr_db | pulse | pi_proxy | no | no | dB | OMIT on pad_ring: snr_db (section 6.3) |
| pulse__pi_proxy__pad_ring__OMIT__sqi | pulse | pi_proxy | no | no | 0..1 | OMIT on pad_ring: sqi (section 6.3) |
| pulse__pi_proxy__pad_ring__OMIT__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__OMIT__template_corr] |
| pulse__pi_proxy__pad_ring__PBV__hr_bpm | pulse | pi_proxy | no | no | bpm | PBV on pad_ring: hr_bpm (section 6.3) |
| pulse__pi_proxy__pad_ring__PBV__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__PBV__kurtosis] |
| pulse__pi_proxy__pad_ring__PBV__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__PBV__n_windows]: count |
| pulse__pi_proxy__pad_ring__PBV__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__PBV__skewness] |
| pulse__pi_proxy__pad_ring__PBV__snr_db | pulse | pi_proxy | no | no | dB | PBV on pad_ring: snr_db (section 6.3) |
| pulse__pi_proxy__pad_ring__PBV__sqi | pulse | pi_proxy | no | no | 0..1 | PBV on pad_ring: sqi (section 6.3) |
| pulse__pi_proxy__pad_ring__PBV__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__PBV__template_corr] |
| pulse__pi_proxy__pad_ring__PCA__hr_bpm | pulse | pi_proxy | no | no | bpm | PCA on pad_ring: hr_bpm (section 6.3) |
| pulse__pi_proxy__pad_ring__PCA__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__PCA__kurtosis] |
| pulse__pi_proxy__pad_ring__PCA__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__PCA__n_windows]: count |
| pulse__pi_proxy__pad_ring__PCA__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__PCA__skewness] |
| pulse__pi_proxy__pad_ring__PCA__snr_db | pulse | pi_proxy | no | no | dB | PCA on pad_ring: snr_db (section 6.3) |
| pulse__pi_proxy__pad_ring__PCA__sqi | pulse | pi_proxy | no | no | 0..1 | PCA on pad_ring: sqi (section 6.3) |
| pulse__pi_proxy__pad_ring__PCA__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__PCA__template_corr] |
| pulse__pi_proxy__pad_ring__POS__hr_bpm | pulse | pi_proxy | no | no | bpm | POS on pad_ring: hr_bpm (section 6.3) |
| pulse__pi_proxy__pad_ring__POS__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__POS__kurtosis] |
| pulse__pi_proxy__pad_ring__POS__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__POS__n_windows]: count |
| pulse__pi_proxy__pad_ring__POS__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__POS__skewness] |
| pulse__pi_proxy__pad_ring__POS__snr_db | pulse | pi_proxy | no | no | dB | POS on pad_ring: snr_db (section 6.3) |
| pulse__pi_proxy__pad_ring__POS__sqi | pulse | pi_proxy | no | no | 0..1 | POS on pad_ring: sqi (section 6.3) |
| pulse__pi_proxy__pad_ring__POS__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [pad_ring__POS__template_corr] |
| pulse__pi_proxy__prox_index__2SR__hr_bpm | pulse | pi_proxy | no | no | bpm | 2SR on prox_index: hr_bpm (section 6.3) |
| pulse__pi_proxy__prox_index__2SR__snr_db | pulse | pi_proxy | no | no | dB | 2SR on prox_index: snr_db (section 6.3) |
| pulse__pi_proxy__prox_index__2SR__sqi | pulse | pi_proxy | no | no | 0..1 | 2SR on prox_index: sqi (section 6.3) |
| pulse__pi_proxy__prox_index__CHROM__hr_bpm | pulse | pi_proxy | no | no | bpm | CHROM on prox_index: hr_bpm (section 6.3) |
| pulse__pi_proxy__prox_index__CHROM__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__CHROM__kurtosis] |
| pulse__pi_proxy__prox_index__CHROM__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__CHROM__n_windows]: count |
| pulse__pi_proxy__prox_index__CHROM__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__CHROM__skewness] |
| pulse__pi_proxy__prox_index__CHROM__snr_db | pulse | pi_proxy | no | no | dB | CHROM on prox_index: snr_db (section 6.3) |
| pulse__pi_proxy__prox_index__CHROM__sqi | pulse | pi_proxy | no | no | 0..1 | CHROM on prox_index: sqi (section 6.3) |
| pulse__pi_proxy__prox_index__CHROM__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__CHROM__template_corr] |
| pulse__pi_proxy__prox_index__GREEN__hr_bpm | pulse | pi_proxy | no | no | bpm | GREEN on prox_index: hr_bpm (section 6.3) |
| pulse__pi_proxy__prox_index__GREEN__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__GREEN__kurtosis] |
| pulse__pi_proxy__prox_index__GREEN__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__GREEN__n_windows]: count |
| pulse__pi_proxy__prox_index__GREEN__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__GREEN__skewness] |
| pulse__pi_proxy__prox_index__GREEN__snr_db | pulse | pi_proxy | no | no | dB | GREEN on prox_index: snr_db (section 6.3) |
| pulse__pi_proxy__prox_index__GREEN__sqi | pulse | pi_proxy | no | no | 0..1 | GREEN on prox_index: sqi (section 6.3) |
| pulse__pi_proxy__prox_index__GREEN__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__GREEN__template_corr] |
| pulse__pi_proxy__prox_index__ICA__hr_bpm | pulse | pi_proxy | no | no | bpm | ICA on prox_index: hr_bpm (section 6.3) |
| pulse__pi_proxy__prox_index__ICA__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__ICA__kurtosis] |
| pulse__pi_proxy__prox_index__ICA__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__ICA__n_windows]: count |
| pulse__pi_proxy__prox_index__ICA__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__ICA__skewness] |
| pulse__pi_proxy__prox_index__ICA__snr_db | pulse | pi_proxy | no | no | dB | ICA on prox_index: snr_db (section 6.3) |
| pulse__pi_proxy__prox_index__ICA__sqi | pulse | pi_proxy | no | no | 0..1 | ICA on prox_index: sqi (section 6.3) |
| pulse__pi_proxy__prox_index__ICA__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__ICA__template_corr] |
| pulse__pi_proxy__prox_index__LGI__hr_bpm | pulse | pi_proxy | no | no | bpm | LGI on prox_index: hr_bpm (section 6.3) |
| pulse__pi_proxy__prox_index__LGI__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__LGI__kurtosis] |
| pulse__pi_proxy__prox_index__LGI__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__LGI__n_windows]: count |
| pulse__pi_proxy__prox_index__LGI__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__LGI__skewness] |
| pulse__pi_proxy__prox_index__LGI__snr_db | pulse | pi_proxy | no | no | dB | LGI on prox_index: snr_db (section 6.3) |
| pulse__pi_proxy__prox_index__LGI__sqi | pulse | pi_proxy | no | no | 0..1 | LGI on prox_index: sqi (section 6.3) |
| pulse__pi_proxy__prox_index__LGI__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__LGI__template_corr] |
| pulse__pi_proxy__prox_index__OMIT__hr_bpm | pulse | pi_proxy | no | no | bpm | OMIT on prox_index: hr_bpm (section 6.3) |
| pulse__pi_proxy__prox_index__OMIT__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__OMIT__kurtosis] |
| pulse__pi_proxy__prox_index__OMIT__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__OMIT__n_windows]: count |
| pulse__pi_proxy__prox_index__OMIT__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__OMIT__skewness] |
| pulse__pi_proxy__prox_index__OMIT__snr_db | pulse | pi_proxy | no | no | dB | OMIT on prox_index: snr_db (section 6.3) |
| pulse__pi_proxy__prox_index__OMIT__sqi | pulse | pi_proxy | no | no | 0..1 | OMIT on prox_index: sqi (section 6.3) |
| pulse__pi_proxy__prox_index__OMIT__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__OMIT__template_corr] |
| pulse__pi_proxy__prox_index__PBV__hr_bpm | pulse | pi_proxy | no | no | bpm | PBV on prox_index: hr_bpm (section 6.3) |
| pulse__pi_proxy__prox_index__PBV__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__PBV__kurtosis] |
| pulse__pi_proxy__prox_index__PBV__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__PBV__n_windows]: count |
| pulse__pi_proxy__prox_index__PBV__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__PBV__skewness] |
| pulse__pi_proxy__prox_index__PBV__snr_db | pulse | pi_proxy | no | no | dB | PBV on prox_index: snr_db (section 6.3) |
| pulse__pi_proxy__prox_index__PBV__sqi | pulse | pi_proxy | no | no | 0..1 | PBV on prox_index: sqi (section 6.3) |
| pulse__pi_proxy__prox_index__PBV__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__PBV__template_corr] |
| pulse__pi_proxy__prox_index__PCA__hr_bpm | pulse | pi_proxy | no | no | bpm | PCA on prox_index: hr_bpm (section 6.3) |
| pulse__pi_proxy__prox_index__PCA__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__PCA__kurtosis] |
| pulse__pi_proxy__prox_index__PCA__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__PCA__n_windows]: count |
| pulse__pi_proxy__prox_index__PCA__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__PCA__skewness] |
| pulse__pi_proxy__prox_index__PCA__snr_db | pulse | pi_proxy | no | no | dB | PCA on prox_index: snr_db (section 6.3) |
| pulse__pi_proxy__prox_index__PCA__sqi | pulse | pi_proxy | no | no | 0..1 | PCA on prox_index: sqi (section 6.3) |
| pulse__pi_proxy__prox_index__PCA__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__PCA__template_corr] |
| pulse__pi_proxy__prox_index__POS__hr_bpm | pulse | pi_proxy | no | no | bpm | POS on prox_index: hr_bpm (section 6.3) |
| pulse__pi_proxy__prox_index__POS__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__POS__kurtosis] |
| pulse__pi_proxy__prox_index__POS__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__POS__n_windows]: count |
| pulse__pi_proxy__prox_index__POS__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__POS__skewness] |
| pulse__pi_proxy__prox_index__POS__snr_db | pulse | pi_proxy | no | no | dB | POS on prox_index: snr_db (section 6.3) |
| pulse__pi_proxy__prox_index__POS__sqi | pulse | pi_proxy | no | no | 0..1 | POS on prox_index: sqi (section 6.3) |
| pulse__pi_proxy__prox_index__POS__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_index__POS__template_corr] |
| pulse__pi_proxy__prox_little__2SR__hr_bpm | pulse | pi_proxy | no | no | bpm | 2SR on prox_little: hr_bpm (section 6.3) |
| pulse__pi_proxy__prox_little__2SR__snr_db | pulse | pi_proxy | no | no | dB | 2SR on prox_little: snr_db (section 6.3) |
| pulse__pi_proxy__prox_little__2SR__sqi | pulse | pi_proxy | no | no | 0..1 | 2SR on prox_little: sqi (section 6.3) |
| pulse__pi_proxy__prox_little__CHROM__hr_bpm | pulse | pi_proxy | no | no | bpm | CHROM on prox_little: hr_bpm (section 6.3) |
| pulse__pi_proxy__prox_little__CHROM__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__CHROM__kurtosis] |
| pulse__pi_proxy__prox_little__CHROM__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__CHROM__n_windows]: count |
| pulse__pi_proxy__prox_little__CHROM__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__CHROM__skewness] |
| pulse__pi_proxy__prox_little__CHROM__snr_db | pulse | pi_proxy | no | no | dB | CHROM on prox_little: snr_db (section 6.3) |
| pulse__pi_proxy__prox_little__CHROM__sqi | pulse | pi_proxy | no | no | 0..1 | CHROM on prox_little: sqi (section 6.3) |
| pulse__pi_proxy__prox_little__CHROM__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__CHROM__template_corr] |
| pulse__pi_proxy__prox_little__GREEN__hr_bpm | pulse | pi_proxy | no | no | bpm | GREEN on prox_little: hr_bpm (section 6.3) |
| pulse__pi_proxy__prox_little__GREEN__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__GREEN__kurtosis] |
| pulse__pi_proxy__prox_little__GREEN__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__GREEN__n_windows]: count |
| pulse__pi_proxy__prox_little__GREEN__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__GREEN__skewness] |
| pulse__pi_proxy__prox_little__GREEN__snr_db | pulse | pi_proxy | no | no | dB | GREEN on prox_little: snr_db (section 6.3) |
| pulse__pi_proxy__prox_little__GREEN__sqi | pulse | pi_proxy | no | no | 0..1 | GREEN on prox_little: sqi (section 6.3) |
| pulse__pi_proxy__prox_little__GREEN__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__GREEN__template_corr] |
| pulse__pi_proxy__prox_little__ICA__hr_bpm | pulse | pi_proxy | no | no | bpm | ICA on prox_little: hr_bpm (section 6.3) |
| pulse__pi_proxy__prox_little__ICA__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__ICA__kurtosis] |
| pulse__pi_proxy__prox_little__ICA__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__ICA__n_windows]: count |
| pulse__pi_proxy__prox_little__ICA__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__ICA__skewness] |
| pulse__pi_proxy__prox_little__ICA__snr_db | pulse | pi_proxy | no | no | dB | ICA on prox_little: snr_db (section 6.3) |
| pulse__pi_proxy__prox_little__ICA__sqi | pulse | pi_proxy | no | no | 0..1 | ICA on prox_little: sqi (section 6.3) |
| pulse__pi_proxy__prox_little__ICA__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__ICA__template_corr] |
| pulse__pi_proxy__prox_little__LGI__hr_bpm | pulse | pi_proxy | no | no | bpm | LGI on prox_little: hr_bpm (section 6.3) |
| pulse__pi_proxy__prox_little__LGI__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__LGI__kurtosis] |
| pulse__pi_proxy__prox_little__LGI__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__LGI__n_windows]: count |
| pulse__pi_proxy__prox_little__LGI__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__LGI__skewness] |
| pulse__pi_proxy__prox_little__LGI__snr_db | pulse | pi_proxy | no | no | dB | LGI on prox_little: snr_db (section 6.3) |
| pulse__pi_proxy__prox_little__LGI__sqi | pulse | pi_proxy | no | no | 0..1 | LGI on prox_little: sqi (section 6.3) |
| pulse__pi_proxy__prox_little__LGI__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__LGI__template_corr] |
| pulse__pi_proxy__prox_little__OMIT__hr_bpm | pulse | pi_proxy | no | no | bpm | OMIT on prox_little: hr_bpm (section 6.3) |
| pulse__pi_proxy__prox_little__OMIT__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__OMIT__kurtosis] |
| pulse__pi_proxy__prox_little__OMIT__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__OMIT__n_windows]: count |
| pulse__pi_proxy__prox_little__OMIT__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__OMIT__skewness] |
| pulse__pi_proxy__prox_little__OMIT__snr_db | pulse | pi_proxy | no | no | dB | OMIT on prox_little: snr_db (section 6.3) |
| pulse__pi_proxy__prox_little__OMIT__sqi | pulse | pi_proxy | no | no | 0..1 | OMIT on prox_little: sqi (section 6.3) |
| pulse__pi_proxy__prox_little__OMIT__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__OMIT__template_corr] |
| pulse__pi_proxy__prox_little__PBV__hr_bpm | pulse | pi_proxy | no | no | bpm | PBV on prox_little: hr_bpm (section 6.3) |
| pulse__pi_proxy__prox_little__PBV__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__PBV__kurtosis] |
| pulse__pi_proxy__prox_little__PBV__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__PBV__n_windows]: count |
| pulse__pi_proxy__prox_little__PBV__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__PBV__skewness] |
| pulse__pi_proxy__prox_little__PBV__snr_db | pulse | pi_proxy | no | no | dB | PBV on prox_little: snr_db (section 6.3) |
| pulse__pi_proxy__prox_little__PBV__sqi | pulse | pi_proxy | no | no | 0..1 | PBV on prox_little: sqi (section 6.3) |
| pulse__pi_proxy__prox_little__PBV__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__PBV__template_corr] |
| pulse__pi_proxy__prox_little__PCA__hr_bpm | pulse | pi_proxy | no | no | bpm | PCA on prox_little: hr_bpm (section 6.3) |
| pulse__pi_proxy__prox_little__PCA__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__PCA__kurtosis] |
| pulse__pi_proxy__prox_little__PCA__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__PCA__n_windows]: count |
| pulse__pi_proxy__prox_little__PCA__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__PCA__skewness] |
| pulse__pi_proxy__prox_little__PCA__snr_db | pulse | pi_proxy | no | no | dB | PCA on prox_little: snr_db (section 6.3) |
| pulse__pi_proxy__prox_little__PCA__sqi | pulse | pi_proxy | no | no | 0..1 | PCA on prox_little: sqi (section 6.3) |
| pulse__pi_proxy__prox_little__PCA__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__PCA__template_corr] |
| pulse__pi_proxy__prox_little__POS__hr_bpm | pulse | pi_proxy | no | no | bpm | POS on prox_little: hr_bpm (section 6.3) |
| pulse__pi_proxy__prox_little__POS__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__POS__kurtosis] |
| pulse__pi_proxy__prox_little__POS__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__POS__n_windows]: count |
| pulse__pi_proxy__prox_little__POS__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__POS__skewness] |
| pulse__pi_proxy__prox_little__POS__snr_db | pulse | pi_proxy | no | no | dB | POS on prox_little: snr_db (section 6.3) |
| pulse__pi_proxy__prox_little__POS__sqi | pulse | pi_proxy | no | no | 0..1 | POS on prox_little: sqi (section 6.3) |
| pulse__pi_proxy__prox_little__POS__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_little__POS__template_corr] |
| pulse__pi_proxy__prox_middle__2SR__hr_bpm | pulse | pi_proxy | no | no | bpm | 2SR on prox_middle: hr_bpm (section 6.3) |
| pulse__pi_proxy__prox_middle__2SR__snr_db | pulse | pi_proxy | no | no | dB | 2SR on prox_middle: snr_db (section 6.3) |
| pulse__pi_proxy__prox_middle__2SR__sqi | pulse | pi_proxy | no | no | 0..1 | 2SR on prox_middle: sqi (section 6.3) |
| pulse__pi_proxy__prox_middle__CHROM__hr_bpm | pulse | pi_proxy | no | no | bpm | CHROM on prox_middle: hr_bpm (section 6.3) |
| pulse__pi_proxy__prox_middle__CHROM__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__CHROM__kurtosis] |
| pulse__pi_proxy__prox_middle__CHROM__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__CHROM__n_windows]: count |
| pulse__pi_proxy__prox_middle__CHROM__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__CHROM__skewness] |
| pulse__pi_proxy__prox_middle__CHROM__snr_db | pulse | pi_proxy | no | no | dB | CHROM on prox_middle: snr_db (section 6.3) |
| pulse__pi_proxy__prox_middle__CHROM__sqi | pulse | pi_proxy | no | no | 0..1 | CHROM on prox_middle: sqi (section 6.3) |
| pulse__pi_proxy__prox_middle__CHROM__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__CHROM__template_corr] |
| pulse__pi_proxy__prox_middle__GREEN__hr_bpm | pulse | pi_proxy | no | no | bpm | GREEN on prox_middle: hr_bpm (section 6.3) |
| pulse__pi_proxy__prox_middle__GREEN__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__GREEN__kurtosis] |
| pulse__pi_proxy__prox_middle__GREEN__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__GREEN__n_windows]: count |
| pulse__pi_proxy__prox_middle__GREEN__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__GREEN__skewness] |
| pulse__pi_proxy__prox_middle__GREEN__snr_db | pulse | pi_proxy | no | no | dB | GREEN on prox_middle: snr_db (section 6.3) |
| pulse__pi_proxy__prox_middle__GREEN__sqi | pulse | pi_proxy | no | no | 0..1 | GREEN on prox_middle: sqi (section 6.3) |
| pulse__pi_proxy__prox_middle__GREEN__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__GREEN__template_corr] |
| pulse__pi_proxy__prox_middle__ICA__hr_bpm | pulse | pi_proxy | no | no | bpm | ICA on prox_middle: hr_bpm (section 6.3) |
| pulse__pi_proxy__prox_middle__ICA__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__ICA__kurtosis] |
| pulse__pi_proxy__prox_middle__ICA__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__ICA__n_windows]: count |
| pulse__pi_proxy__prox_middle__ICA__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__ICA__skewness] |
| pulse__pi_proxy__prox_middle__ICA__snr_db | pulse | pi_proxy | no | no | dB | ICA on prox_middle: snr_db (section 6.3) |
| pulse__pi_proxy__prox_middle__ICA__sqi | pulse | pi_proxy | no | no | 0..1 | ICA on prox_middle: sqi (section 6.3) |
| pulse__pi_proxy__prox_middle__ICA__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__ICA__template_corr] |
| pulse__pi_proxy__prox_middle__LGI__hr_bpm | pulse | pi_proxy | no | no | bpm | LGI on prox_middle: hr_bpm (section 6.3) |
| pulse__pi_proxy__prox_middle__LGI__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__LGI__kurtosis] |
| pulse__pi_proxy__prox_middle__LGI__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__LGI__n_windows]: count |
| pulse__pi_proxy__prox_middle__LGI__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__LGI__skewness] |
| pulse__pi_proxy__prox_middle__LGI__snr_db | pulse | pi_proxy | no | no | dB | LGI on prox_middle: snr_db (section 6.3) |
| pulse__pi_proxy__prox_middle__LGI__sqi | pulse | pi_proxy | no | no | 0..1 | LGI on prox_middle: sqi (section 6.3) |
| pulse__pi_proxy__prox_middle__LGI__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__LGI__template_corr] |
| pulse__pi_proxy__prox_middle__OMIT__hr_bpm | pulse | pi_proxy | no | no | bpm | OMIT on prox_middle: hr_bpm (section 6.3) |
| pulse__pi_proxy__prox_middle__OMIT__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__OMIT__kurtosis] |
| pulse__pi_proxy__prox_middle__OMIT__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__OMIT__n_windows]: count |
| pulse__pi_proxy__prox_middle__OMIT__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__OMIT__skewness] |
| pulse__pi_proxy__prox_middle__OMIT__snr_db | pulse | pi_proxy | no | no | dB | OMIT on prox_middle: snr_db (section 6.3) |
| pulse__pi_proxy__prox_middle__OMIT__sqi | pulse | pi_proxy | no | no | 0..1 | OMIT on prox_middle: sqi (section 6.3) |
| pulse__pi_proxy__prox_middle__OMIT__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__OMIT__template_corr] |
| pulse__pi_proxy__prox_middle__PBV__hr_bpm | pulse | pi_proxy | no | no | bpm | PBV on prox_middle: hr_bpm (section 6.3) |
| pulse__pi_proxy__prox_middle__PBV__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__PBV__kurtosis] |
| pulse__pi_proxy__prox_middle__PBV__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__PBV__n_windows]: count |
| pulse__pi_proxy__prox_middle__PBV__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__PBV__skewness] |
| pulse__pi_proxy__prox_middle__PBV__snr_db | pulse | pi_proxy | no | no | dB | PBV on prox_middle: snr_db (section 6.3) |
| pulse__pi_proxy__prox_middle__PBV__sqi | pulse | pi_proxy | no | no | 0..1 | PBV on prox_middle: sqi (section 6.3) |
| pulse__pi_proxy__prox_middle__PBV__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__PBV__template_corr] |
| pulse__pi_proxy__prox_middle__PCA__hr_bpm | pulse | pi_proxy | no | no | bpm | PCA on prox_middle: hr_bpm (section 6.3) |
| pulse__pi_proxy__prox_middle__PCA__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__PCA__kurtosis] |
| pulse__pi_proxy__prox_middle__PCA__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__PCA__n_windows]: count |
| pulse__pi_proxy__prox_middle__PCA__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__PCA__skewness] |
| pulse__pi_proxy__prox_middle__PCA__snr_db | pulse | pi_proxy | no | no | dB | PCA on prox_middle: snr_db (section 6.3) |
| pulse__pi_proxy__prox_middle__PCA__sqi | pulse | pi_proxy | no | no | 0..1 | PCA on prox_middle: sqi (section 6.3) |
| pulse__pi_proxy__prox_middle__PCA__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__PCA__template_corr] |
| pulse__pi_proxy__prox_middle__POS__hr_bpm | pulse | pi_proxy | no | no | bpm | POS on prox_middle: hr_bpm (section 6.3) |
| pulse__pi_proxy__prox_middle__POS__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__POS__kurtosis] |
| pulse__pi_proxy__prox_middle__POS__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__POS__n_windows]: count |
| pulse__pi_proxy__prox_middle__POS__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__POS__skewness] |
| pulse__pi_proxy__prox_middle__POS__snr_db | pulse | pi_proxy | no | no | dB | POS on prox_middle: snr_db (section 6.3) |
| pulse__pi_proxy__prox_middle__POS__sqi | pulse | pi_proxy | no | no | 0..1 | POS on prox_middle: sqi (section 6.3) |
| pulse__pi_proxy__prox_middle__POS__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_middle__POS__template_corr] |
| pulse__pi_proxy__prox_ring__2SR__hr_bpm | pulse | pi_proxy | no | no | bpm | 2SR on prox_ring: hr_bpm (section 6.3) |
| pulse__pi_proxy__prox_ring__2SR__snr_db | pulse | pi_proxy | no | no | dB | 2SR on prox_ring: snr_db (section 6.3) |
| pulse__pi_proxy__prox_ring__2SR__sqi | pulse | pi_proxy | no | no | 0..1 | 2SR on prox_ring: sqi (section 6.3) |
| pulse__pi_proxy__prox_ring__CHROM__hr_bpm | pulse | pi_proxy | no | no | bpm | CHROM on prox_ring: hr_bpm (section 6.3) |
| pulse__pi_proxy__prox_ring__CHROM__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__CHROM__kurtosis] |
| pulse__pi_proxy__prox_ring__CHROM__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__CHROM__n_windows]: count |
| pulse__pi_proxy__prox_ring__CHROM__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__CHROM__skewness] |
| pulse__pi_proxy__prox_ring__CHROM__snr_db | pulse | pi_proxy | no | no | dB | CHROM on prox_ring: snr_db (section 6.3) |
| pulse__pi_proxy__prox_ring__CHROM__sqi | pulse | pi_proxy | no | no | 0..1 | CHROM on prox_ring: sqi (section 6.3) |
| pulse__pi_proxy__prox_ring__CHROM__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__CHROM__template_corr] |
| pulse__pi_proxy__prox_ring__GREEN__hr_bpm | pulse | pi_proxy | no | no | bpm | GREEN on prox_ring: hr_bpm (section 6.3) |
| pulse__pi_proxy__prox_ring__GREEN__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__GREEN__kurtosis] |
| pulse__pi_proxy__prox_ring__GREEN__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__GREEN__n_windows]: count |
| pulse__pi_proxy__prox_ring__GREEN__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__GREEN__skewness] |
| pulse__pi_proxy__prox_ring__GREEN__snr_db | pulse | pi_proxy | no | no | dB | GREEN on prox_ring: snr_db (section 6.3) |
| pulse__pi_proxy__prox_ring__GREEN__sqi | pulse | pi_proxy | no | no | 0..1 | GREEN on prox_ring: sqi (section 6.3) |
| pulse__pi_proxy__prox_ring__GREEN__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__GREEN__template_corr] |
| pulse__pi_proxy__prox_ring__ICA__hr_bpm | pulse | pi_proxy | no | no | bpm | ICA on prox_ring: hr_bpm (section 6.3) |
| pulse__pi_proxy__prox_ring__ICA__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__ICA__kurtosis] |
| pulse__pi_proxy__prox_ring__ICA__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__ICA__n_windows]: count |
| pulse__pi_proxy__prox_ring__ICA__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__ICA__skewness] |
| pulse__pi_proxy__prox_ring__ICA__snr_db | pulse | pi_proxy | no | no | dB | ICA on prox_ring: snr_db (section 6.3) |
| pulse__pi_proxy__prox_ring__ICA__sqi | pulse | pi_proxy | no | no | 0..1 | ICA on prox_ring: sqi (section 6.3) |
| pulse__pi_proxy__prox_ring__ICA__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__ICA__template_corr] |
| pulse__pi_proxy__prox_ring__LGI__hr_bpm | pulse | pi_proxy | no | no | bpm | LGI on prox_ring: hr_bpm (section 6.3) |
| pulse__pi_proxy__prox_ring__LGI__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__LGI__kurtosis] |
| pulse__pi_proxy__prox_ring__LGI__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__LGI__n_windows]: count |
| pulse__pi_proxy__prox_ring__LGI__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__LGI__skewness] |
| pulse__pi_proxy__prox_ring__LGI__snr_db | pulse | pi_proxy | no | no | dB | LGI on prox_ring: snr_db (section 6.3) |
| pulse__pi_proxy__prox_ring__LGI__sqi | pulse | pi_proxy | no | no | 0..1 | LGI on prox_ring: sqi (section 6.3) |
| pulse__pi_proxy__prox_ring__LGI__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__LGI__template_corr] |
| pulse__pi_proxy__prox_ring__OMIT__hr_bpm | pulse | pi_proxy | no | no | bpm | OMIT on prox_ring: hr_bpm (section 6.3) |
| pulse__pi_proxy__prox_ring__OMIT__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__OMIT__kurtosis] |
| pulse__pi_proxy__prox_ring__OMIT__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__OMIT__n_windows]: count |
| pulse__pi_proxy__prox_ring__OMIT__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__OMIT__skewness] |
| pulse__pi_proxy__prox_ring__OMIT__snr_db | pulse | pi_proxy | no | no | dB | OMIT on prox_ring: snr_db (section 6.3) |
| pulse__pi_proxy__prox_ring__OMIT__sqi | pulse | pi_proxy | no | no | 0..1 | OMIT on prox_ring: sqi (section 6.3) |
| pulse__pi_proxy__prox_ring__OMIT__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__OMIT__template_corr] |
| pulse__pi_proxy__prox_ring__PBV__hr_bpm | pulse | pi_proxy | no | no | bpm | PBV on prox_ring: hr_bpm (section 6.3) |
| pulse__pi_proxy__prox_ring__PBV__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__PBV__kurtosis] |
| pulse__pi_proxy__prox_ring__PBV__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__PBV__n_windows]: count |
| pulse__pi_proxy__prox_ring__PBV__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__PBV__skewness] |
| pulse__pi_proxy__prox_ring__PBV__snr_db | pulse | pi_proxy | no | no | dB | PBV on prox_ring: snr_db (section 6.3) |
| pulse__pi_proxy__prox_ring__PBV__sqi | pulse | pi_proxy | no | no | 0..1 | PBV on prox_ring: sqi (section 6.3) |
| pulse__pi_proxy__prox_ring__PBV__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__PBV__template_corr] |
| pulse__pi_proxy__prox_ring__PCA__hr_bpm | pulse | pi_proxy | no | no | bpm | PCA on prox_ring: hr_bpm (section 6.3) |
| pulse__pi_proxy__prox_ring__PCA__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__PCA__kurtosis] |
| pulse__pi_proxy__prox_ring__PCA__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__PCA__n_windows]: count |
| pulse__pi_proxy__prox_ring__PCA__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__PCA__skewness] |
| pulse__pi_proxy__prox_ring__PCA__snr_db | pulse | pi_proxy | no | no | dB | PCA on prox_ring: snr_db (section 6.3) |
| pulse__pi_proxy__prox_ring__PCA__sqi | pulse | pi_proxy | no | no | 0..1 | PCA on prox_ring: sqi (section 6.3) |
| pulse__pi_proxy__prox_ring__PCA__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__PCA__template_corr] |
| pulse__pi_proxy__prox_ring__POS__hr_bpm | pulse | pi_proxy | no | no | bpm | POS on prox_ring: hr_bpm (section 6.3) |
| pulse__pi_proxy__prox_ring__POS__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__POS__kurtosis] |
| pulse__pi_proxy__prox_ring__POS__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__POS__n_windows]: count |
| pulse__pi_proxy__prox_ring__POS__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__POS__skewness] |
| pulse__pi_proxy__prox_ring__POS__snr_db | pulse | pi_proxy | no | no | dB | POS on prox_ring: snr_db (section 6.3) |
| pulse__pi_proxy__prox_ring__POS__sqi | pulse | pi_proxy | no | no | 0..1 | POS on prox_ring: sqi (section 6.3) |
| pulse__pi_proxy__prox_ring__POS__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [prox_ring__POS__template_corr] |
| pulse__pi_proxy__roi_set__2SR__hr_bpm | pulse | pi_proxy | no | no | bpm | 2SR on roi_set: hr_bpm (section 6.3) |
| pulse__pi_proxy__roi_set__2SR__snr_db | pulse | pi_proxy | no | no | dB | 2SR on roi_set: snr_db (section 6.3) |
| pulse__pi_proxy__roi_set__2SR__sqi | pulse | pi_proxy | no | no | 0..1 | 2SR on roi_set: sqi (section 6.3) |
| pulse__pi_proxy__roi_set__CHROM__hr_bpm | pulse | pi_proxy | no | no | bpm | CHROM on roi_set: hr_bpm (section 6.3) |
| pulse__pi_proxy__roi_set__CHROM__snr_db | pulse | pi_proxy | no | no | dB | CHROM on roi_set: snr_db (section 6.3) |
| pulse__pi_proxy__roi_set__CHROM__sqi | pulse | pi_proxy | no | no | 0..1 | CHROM on roi_set: sqi (section 6.3) |
| pulse__pi_proxy__roi_set__GREEN__hr_bpm | pulse | pi_proxy | no | no | bpm | GREEN on roi_set: hr_bpm (section 6.3) |
| pulse__pi_proxy__roi_set__GREEN__snr_db | pulse | pi_proxy | no | no | dB | GREEN on roi_set: snr_db (section 6.3) |
| pulse__pi_proxy__roi_set__GREEN__sqi | pulse | pi_proxy | no | no | 0..1 | GREEN on roi_set: sqi (section 6.3) |
| pulse__pi_proxy__roi_set__ICA__hr_bpm | pulse | pi_proxy | no | no | bpm | ICA on roi_set: hr_bpm (section 6.3) |
| pulse__pi_proxy__roi_set__ICA__snr_db | pulse | pi_proxy | no | no | dB | ICA on roi_set: snr_db (section 6.3) |
| pulse__pi_proxy__roi_set__ICA__sqi | pulse | pi_proxy | no | no | 0..1 | ICA on roi_set: sqi (section 6.3) |
| pulse__pi_proxy__roi_set__LGI__hr_bpm | pulse | pi_proxy | no | no | bpm | LGI on roi_set: hr_bpm (section 6.3) |
| pulse__pi_proxy__roi_set__LGI__snr_db | pulse | pi_proxy | no | no | dB | LGI on roi_set: snr_db (section 6.3) |
| pulse__pi_proxy__roi_set__LGI__sqi | pulse | pi_proxy | no | no | 0..1 | LGI on roi_set: sqi (section 6.3) |
| pulse__pi_proxy__roi_set__OMIT__hr_bpm | pulse | pi_proxy | no | no | bpm | OMIT on roi_set: hr_bpm (section 6.3) |
| pulse__pi_proxy__roi_set__OMIT__snr_db | pulse | pi_proxy | no | no | dB | OMIT on roi_set: snr_db (section 6.3) |
| pulse__pi_proxy__roi_set__OMIT__sqi | pulse | pi_proxy | no | no | 0..1 | OMIT on roi_set: sqi (section 6.3) |
| pulse__pi_proxy__roi_set__PBV__hr_bpm | pulse | pi_proxy | no | no | bpm | PBV on roi_set: hr_bpm (section 6.3) |
| pulse__pi_proxy__roi_set__PBV__snr_db | pulse | pi_proxy | no | no | dB | PBV on roi_set: snr_db (section 6.3) |
| pulse__pi_proxy__roi_set__PBV__sqi | pulse | pi_proxy | no | no | 0..1 | PBV on roi_set: sqi (section 6.3) |
| pulse__pi_proxy__roi_set__PCA__hr_bpm | pulse | pi_proxy | no | no | bpm | PCA on roi_set: hr_bpm (section 6.3) |
| pulse__pi_proxy__roi_set__PCA__snr_db | pulse | pi_proxy | no | no | dB | PCA on roi_set: snr_db (section 6.3) |
| pulse__pi_proxy__roi_set__PCA__sqi | pulse | pi_proxy | no | no | 0..1 | PCA on roi_set: sqi (section 6.3) |
| pulse__pi_proxy__roi_set__POS__hr_bpm | pulse | pi_proxy | no | no | bpm | POS on roi_set: hr_bpm (section 6.3) |
| pulse__pi_proxy__roi_set__POS__snr_db | pulse | pi_proxy | no | no | dB | POS on roi_set: snr_db (section 6.3) |
| pulse__pi_proxy__roi_set__POS__sqi | pulse | pi_proxy | no | no | 0..1 | POS on roi_set: sqi (section 6.3) |
| pulse__pi_proxy__selection__agreement | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [selection__agreement] |
| pulse__pi_proxy__selection__consensus_hr_bpm | pulse | pi_proxy | no | no | bpm | pulse extraction summary per method and ROI (protocol 6.3) [selection__consensus_hr_bpm]: rate in beats per minute |
| pulse__pi_proxy__selection__mode | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [selection__mode] |
| pulse__pi_proxy__selection__n_candidates | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [selection__n_candidates]: count |
| pulse__pi_proxy__selection__raw_sqi | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [selection__raw_sqi] |
| pulse__pi_proxy__selection__score | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [selection__score] |
| pulse__pi_proxy__thenar__2SR__hr_bpm | pulse | pi_proxy | no | no | bpm | 2SR on thenar: hr_bpm (section 6.3) |
| pulse__pi_proxy__thenar__2SR__snr_db | pulse | pi_proxy | no | no | dB | 2SR on thenar: snr_db (section 6.3) |
| pulse__pi_proxy__thenar__2SR__sqi | pulse | pi_proxy | no | no | 0..1 | 2SR on thenar: sqi (section 6.3) |
| pulse__pi_proxy__thenar__CHROM__hr_bpm | pulse | pi_proxy | no | no | bpm | CHROM on thenar: hr_bpm (section 6.3) |
| pulse__pi_proxy__thenar__CHROM__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__CHROM__kurtosis] |
| pulse__pi_proxy__thenar__CHROM__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [thenar__CHROM__n_windows]: count |
| pulse__pi_proxy__thenar__CHROM__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__CHROM__skewness] |
| pulse__pi_proxy__thenar__CHROM__snr_db | pulse | pi_proxy | no | no | dB | CHROM on thenar: snr_db (section 6.3) |
| pulse__pi_proxy__thenar__CHROM__sqi | pulse | pi_proxy | no | no | 0..1 | CHROM on thenar: sqi (section 6.3) |
| pulse__pi_proxy__thenar__CHROM__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__CHROM__template_corr] |
| pulse__pi_proxy__thenar__GREEN__hr_bpm | pulse | pi_proxy | no | no | bpm | GREEN on thenar: hr_bpm (section 6.3) |
| pulse__pi_proxy__thenar__GREEN__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__GREEN__kurtosis] |
| pulse__pi_proxy__thenar__GREEN__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [thenar__GREEN__n_windows]: count |
| pulse__pi_proxy__thenar__GREEN__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__GREEN__skewness] |
| pulse__pi_proxy__thenar__GREEN__snr_db | pulse | pi_proxy | no | no | dB | GREEN on thenar: snr_db (section 6.3) |
| pulse__pi_proxy__thenar__GREEN__sqi | pulse | pi_proxy | no | no | 0..1 | GREEN on thenar: sqi (section 6.3) |
| pulse__pi_proxy__thenar__GREEN__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__GREEN__template_corr] |
| pulse__pi_proxy__thenar__ICA__hr_bpm | pulse | pi_proxy | no | no | bpm | ICA on thenar: hr_bpm (section 6.3) |
| pulse__pi_proxy__thenar__ICA__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__ICA__kurtosis] |
| pulse__pi_proxy__thenar__ICA__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [thenar__ICA__n_windows]: count |
| pulse__pi_proxy__thenar__ICA__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__ICA__skewness] |
| pulse__pi_proxy__thenar__ICA__snr_db | pulse | pi_proxy | no | no | dB | ICA on thenar: snr_db (section 6.3) |
| pulse__pi_proxy__thenar__ICA__sqi | pulse | pi_proxy | no | no | 0..1 | ICA on thenar: sqi (section 6.3) |
| pulse__pi_proxy__thenar__ICA__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__ICA__template_corr] |
| pulse__pi_proxy__thenar__LGI__hr_bpm | pulse | pi_proxy | no | no | bpm | LGI on thenar: hr_bpm (section 6.3) |
| pulse__pi_proxy__thenar__LGI__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__LGI__kurtosis] |
| pulse__pi_proxy__thenar__LGI__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [thenar__LGI__n_windows]: count |
| pulse__pi_proxy__thenar__LGI__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__LGI__skewness] |
| pulse__pi_proxy__thenar__LGI__snr_db | pulse | pi_proxy | no | no | dB | LGI on thenar: snr_db (section 6.3) |
| pulse__pi_proxy__thenar__LGI__sqi | pulse | pi_proxy | no | no | 0..1 | LGI on thenar: sqi (section 6.3) |
| pulse__pi_proxy__thenar__LGI__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__LGI__template_corr] |
| pulse__pi_proxy__thenar__OMIT__hr_bpm | pulse | pi_proxy | no | no | bpm | OMIT on thenar: hr_bpm (section 6.3) |
| pulse__pi_proxy__thenar__OMIT__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__OMIT__kurtosis] |
| pulse__pi_proxy__thenar__OMIT__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [thenar__OMIT__n_windows]: count |
| pulse__pi_proxy__thenar__OMIT__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__OMIT__skewness] |
| pulse__pi_proxy__thenar__OMIT__snr_db | pulse | pi_proxy | no | no | dB | OMIT on thenar: snr_db (section 6.3) |
| pulse__pi_proxy__thenar__OMIT__sqi | pulse | pi_proxy | no | no | 0..1 | OMIT on thenar: sqi (section 6.3) |
| pulse__pi_proxy__thenar__OMIT__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__OMIT__template_corr] |
| pulse__pi_proxy__thenar__PBV__hr_bpm | pulse | pi_proxy | no | no | bpm | PBV on thenar: hr_bpm (section 6.3) |
| pulse__pi_proxy__thenar__PBV__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__PBV__kurtosis] |
| pulse__pi_proxy__thenar__PBV__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [thenar__PBV__n_windows]: count |
| pulse__pi_proxy__thenar__PBV__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__PBV__skewness] |
| pulse__pi_proxy__thenar__PBV__snr_db | pulse | pi_proxy | no | no | dB | PBV on thenar: snr_db (section 6.3) |
| pulse__pi_proxy__thenar__PBV__sqi | pulse | pi_proxy | no | no | 0..1 | PBV on thenar: sqi (section 6.3) |
| pulse__pi_proxy__thenar__PBV__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__PBV__template_corr] |
| pulse__pi_proxy__thenar__PCA__hr_bpm | pulse | pi_proxy | no | no | bpm | PCA on thenar: hr_bpm (section 6.3) |
| pulse__pi_proxy__thenar__PCA__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__PCA__kurtosis] |
| pulse__pi_proxy__thenar__PCA__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [thenar__PCA__n_windows]: count |
| pulse__pi_proxy__thenar__PCA__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__PCA__skewness] |
| pulse__pi_proxy__thenar__PCA__snr_db | pulse | pi_proxy | no | no | dB | PCA on thenar: snr_db (section 6.3) |
| pulse__pi_proxy__thenar__PCA__sqi | pulse | pi_proxy | no | no | 0..1 | PCA on thenar: sqi (section 6.3) |
| pulse__pi_proxy__thenar__PCA__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__PCA__template_corr] |
| pulse__pi_proxy__thenar__POS__hr_bpm | pulse | pi_proxy | no | no | bpm | POS on thenar: hr_bpm (section 6.3) |
| pulse__pi_proxy__thenar__POS__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__POS__kurtosis] |
| pulse__pi_proxy__thenar__POS__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [thenar__POS__n_windows]: count |
| pulse__pi_proxy__thenar__POS__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__POS__skewness] |
| pulse__pi_proxy__thenar__POS__snr_db | pulse | pi_proxy | no | no | dB | POS on thenar: snr_db (section 6.3) |
| pulse__pi_proxy__thenar__POS__sqi | pulse | pi_proxy | no | no | 0..1 | POS on thenar: sqi (section 6.3) |
| pulse__pi_proxy__thenar__POS__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [thenar__POS__template_corr] |
| pulse__pi_proxy__volar_wrist__2SR__hr_bpm | pulse | pi_proxy | no | no | bpm | 2SR on volar_wrist: hr_bpm (section 6.3) |
| pulse__pi_proxy__volar_wrist__2SR__snr_db | pulse | pi_proxy | no | no | dB | 2SR on volar_wrist: snr_db (section 6.3) |
| pulse__pi_proxy__volar_wrist__2SR__sqi | pulse | pi_proxy | no | no | 0..1 | 2SR on volar_wrist: sqi (section 6.3) |
| pulse__pi_proxy__volar_wrist__CHROM__hr_bpm | pulse | pi_proxy | no | no | bpm | CHROM on volar_wrist: hr_bpm (section 6.3) |
| pulse__pi_proxy__volar_wrist__CHROM__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__CHROM__kurtosis] |
| pulse__pi_proxy__volar_wrist__CHROM__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__CHROM__n_windows]: count |
| pulse__pi_proxy__volar_wrist__CHROM__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__CHROM__skewness] |
| pulse__pi_proxy__volar_wrist__CHROM__snr_db | pulse | pi_proxy | no | no | dB | CHROM on volar_wrist: snr_db (section 6.3) |
| pulse__pi_proxy__volar_wrist__CHROM__sqi | pulse | pi_proxy | no | no | 0..1 | CHROM on volar_wrist: sqi (section 6.3) |
| pulse__pi_proxy__volar_wrist__CHROM__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__CHROM__template_corr] |
| pulse__pi_proxy__volar_wrist__GREEN__hr_bpm | pulse | pi_proxy | no | no | bpm | GREEN on volar_wrist: hr_bpm (section 6.3) |
| pulse__pi_proxy__volar_wrist__GREEN__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__GREEN__kurtosis] |
| pulse__pi_proxy__volar_wrist__GREEN__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__GREEN__n_windows]: count |
| pulse__pi_proxy__volar_wrist__GREEN__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__GREEN__skewness] |
| pulse__pi_proxy__volar_wrist__GREEN__snr_db | pulse | pi_proxy | no | no | dB | GREEN on volar_wrist: snr_db (section 6.3) |
| pulse__pi_proxy__volar_wrist__GREEN__sqi | pulse | pi_proxy | no | no | 0..1 | GREEN on volar_wrist: sqi (section 6.3) |
| pulse__pi_proxy__volar_wrist__GREEN__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__GREEN__template_corr] |
| pulse__pi_proxy__volar_wrist__ICA__hr_bpm | pulse | pi_proxy | no | no | bpm | ICA on volar_wrist: hr_bpm (section 6.3) |
| pulse__pi_proxy__volar_wrist__ICA__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__ICA__kurtosis] |
| pulse__pi_proxy__volar_wrist__ICA__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__ICA__n_windows]: count |
| pulse__pi_proxy__volar_wrist__ICA__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__ICA__skewness] |
| pulse__pi_proxy__volar_wrist__ICA__snr_db | pulse | pi_proxy | no | no | dB | ICA on volar_wrist: snr_db (section 6.3) |
| pulse__pi_proxy__volar_wrist__ICA__sqi | pulse | pi_proxy | no | no | 0..1 | ICA on volar_wrist: sqi (section 6.3) |
| pulse__pi_proxy__volar_wrist__ICA__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__ICA__template_corr] |
| pulse__pi_proxy__volar_wrist__LGI__hr_bpm | pulse | pi_proxy | no | no | bpm | LGI on volar_wrist: hr_bpm (section 6.3) |
| pulse__pi_proxy__volar_wrist__LGI__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__LGI__kurtosis] |
| pulse__pi_proxy__volar_wrist__LGI__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__LGI__n_windows]: count |
| pulse__pi_proxy__volar_wrist__LGI__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__LGI__skewness] |
| pulse__pi_proxy__volar_wrist__LGI__snr_db | pulse | pi_proxy | no | no | dB | LGI on volar_wrist: snr_db (section 6.3) |
| pulse__pi_proxy__volar_wrist__LGI__sqi | pulse | pi_proxy | no | no | 0..1 | LGI on volar_wrist: sqi (section 6.3) |
| pulse__pi_proxy__volar_wrist__LGI__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__LGI__template_corr] |
| pulse__pi_proxy__volar_wrist__OMIT__hr_bpm | pulse | pi_proxy | no | no | bpm | OMIT on volar_wrist: hr_bpm (section 6.3) |
| pulse__pi_proxy__volar_wrist__OMIT__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__OMIT__kurtosis] |
| pulse__pi_proxy__volar_wrist__OMIT__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__OMIT__n_windows]: count |
| pulse__pi_proxy__volar_wrist__OMIT__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__OMIT__skewness] |
| pulse__pi_proxy__volar_wrist__OMIT__snr_db | pulse | pi_proxy | no | no | dB | OMIT on volar_wrist: snr_db (section 6.3) |
| pulse__pi_proxy__volar_wrist__OMIT__sqi | pulse | pi_proxy | no | no | 0..1 | OMIT on volar_wrist: sqi (section 6.3) |
| pulse__pi_proxy__volar_wrist__OMIT__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__OMIT__template_corr] |
| pulse__pi_proxy__volar_wrist__PBV__hr_bpm | pulse | pi_proxy | no | no | bpm | PBV on volar_wrist: hr_bpm (section 6.3) |
| pulse__pi_proxy__volar_wrist__PBV__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__PBV__kurtosis] |
| pulse__pi_proxy__volar_wrist__PBV__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__PBV__n_windows]: count |
| pulse__pi_proxy__volar_wrist__PBV__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__PBV__skewness] |
| pulse__pi_proxy__volar_wrist__PBV__snr_db | pulse | pi_proxy | no | no | dB | PBV on volar_wrist: snr_db (section 6.3) |
| pulse__pi_proxy__volar_wrist__PBV__sqi | pulse | pi_proxy | no | no | 0..1 | PBV on volar_wrist: sqi (section 6.3) |
| pulse__pi_proxy__volar_wrist__PBV__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__PBV__template_corr] |
| pulse__pi_proxy__volar_wrist__PCA__hr_bpm | pulse | pi_proxy | no | no | bpm | PCA on volar_wrist: hr_bpm (section 6.3) |
| pulse__pi_proxy__volar_wrist__PCA__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__PCA__kurtosis] |
| pulse__pi_proxy__volar_wrist__PCA__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__PCA__n_windows]: count |
| pulse__pi_proxy__volar_wrist__PCA__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__PCA__skewness] |
| pulse__pi_proxy__volar_wrist__PCA__snr_db | pulse | pi_proxy | no | no | dB | PCA on volar_wrist: snr_db (section 6.3) |
| pulse__pi_proxy__volar_wrist__PCA__sqi | pulse | pi_proxy | no | no | 0..1 | PCA on volar_wrist: sqi (section 6.3) |
| pulse__pi_proxy__volar_wrist__PCA__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__PCA__template_corr] |
| pulse__pi_proxy__volar_wrist__POS__hr_bpm | pulse | pi_proxy | no | no | bpm | POS on volar_wrist: hr_bpm (section 6.3) |
| pulse__pi_proxy__volar_wrist__POS__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__POS__kurtosis] |
| pulse__pi_proxy__volar_wrist__POS__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__POS__n_windows]: count |
| pulse__pi_proxy__volar_wrist__POS__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__POS__skewness] |
| pulse__pi_proxy__volar_wrist__POS__snr_db | pulse | pi_proxy | no | no | dB | POS on volar_wrist: snr_db (section 6.3) |
| pulse__pi_proxy__volar_wrist__POS__sqi | pulse | pi_proxy | no | no | 0..1 | POS on volar_wrist: sqi (section 6.3) |
| pulse__pi_proxy__volar_wrist__POS__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [volar_wrist__POS__template_corr] |
| pulse__pi_proxy__whole_palm__2SR__hr_bpm | pulse | pi_proxy | no | no | bpm | 2SR on whole_palm: hr_bpm (section 6.3) |
| pulse__pi_proxy__whole_palm__2SR__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__2SR__kurtosis] |
| pulse__pi_proxy__whole_palm__2SR__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__2SR__n_windows]: count |
| pulse__pi_proxy__whole_palm__2SR__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__2SR__skewness] |
| pulse__pi_proxy__whole_palm__2SR__snr_db | pulse | pi_proxy | no | no | dB | 2SR on whole_palm: snr_db (section 6.3) |
| pulse__pi_proxy__whole_palm__2SR__sqi | pulse | pi_proxy | no | no | 0..1 | 2SR on whole_palm: sqi (section 6.3) |
| pulse__pi_proxy__whole_palm__2SR__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__2SR__template_corr] |
| pulse__pi_proxy__whole_palm__CHROM__hr_bpm | pulse | pi_proxy | no | no | bpm | CHROM on whole_palm: hr_bpm (section 6.3) |
| pulse__pi_proxy__whole_palm__CHROM__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__CHROM__kurtosis] |
| pulse__pi_proxy__whole_palm__CHROM__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__CHROM__n_windows]: count |
| pulse__pi_proxy__whole_palm__CHROM__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__CHROM__skewness] |
| pulse__pi_proxy__whole_palm__CHROM__snr_db | pulse | pi_proxy | no | no | dB | CHROM on whole_palm: snr_db (section 6.3) |
| pulse__pi_proxy__whole_palm__CHROM__sqi | pulse | pi_proxy | no | no | 0..1 | CHROM on whole_palm: sqi (section 6.3) |
| pulse__pi_proxy__whole_palm__CHROM__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__CHROM__template_corr] |
| pulse__pi_proxy__whole_palm__GREEN__hr_bpm | pulse | pi_proxy | no | no | bpm | GREEN on whole_palm: hr_bpm (section 6.3) |
| pulse__pi_proxy__whole_palm__GREEN__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__GREEN__kurtosis] |
| pulse__pi_proxy__whole_palm__GREEN__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__GREEN__n_windows]: count |
| pulse__pi_proxy__whole_palm__GREEN__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__GREEN__skewness] |
| pulse__pi_proxy__whole_palm__GREEN__snr_db | pulse | pi_proxy | no | no | dB | GREEN on whole_palm: snr_db (section 6.3) |
| pulse__pi_proxy__whole_palm__GREEN__sqi | pulse | pi_proxy | no | no | 0..1 | GREEN on whole_palm: sqi (section 6.3) |
| pulse__pi_proxy__whole_palm__GREEN__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__GREEN__template_corr] |
| pulse__pi_proxy__whole_palm__ICA__hr_bpm | pulse | pi_proxy | no | no | bpm | ICA on whole_palm: hr_bpm (section 6.3) |
| pulse__pi_proxy__whole_palm__ICA__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__ICA__kurtosis] |
| pulse__pi_proxy__whole_palm__ICA__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__ICA__n_windows]: count |
| pulse__pi_proxy__whole_palm__ICA__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__ICA__skewness] |
| pulse__pi_proxy__whole_palm__ICA__snr_db | pulse | pi_proxy | no | no | dB | ICA on whole_palm: snr_db (section 6.3) |
| pulse__pi_proxy__whole_palm__ICA__sqi | pulse | pi_proxy | no | no | 0..1 | ICA on whole_palm: sqi (section 6.3) |
| pulse__pi_proxy__whole_palm__ICA__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__ICA__template_corr] |
| pulse__pi_proxy__whole_palm__LGI__hr_bpm | pulse | pi_proxy | no | no | bpm | LGI on whole_palm: hr_bpm (section 6.3) |
| pulse__pi_proxy__whole_palm__LGI__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__LGI__kurtosis] |
| pulse__pi_proxy__whole_palm__LGI__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__LGI__n_windows]: count |
| pulse__pi_proxy__whole_palm__LGI__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__LGI__skewness] |
| pulse__pi_proxy__whole_palm__LGI__snr_db | pulse | pi_proxy | no | no | dB | LGI on whole_palm: snr_db (section 6.3) |
| pulse__pi_proxy__whole_palm__LGI__sqi | pulse | pi_proxy | no | no | 0..1 | LGI on whole_palm: sqi (section 6.3) |
| pulse__pi_proxy__whole_palm__LGI__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__LGI__template_corr] |
| pulse__pi_proxy__whole_palm__OMIT__hr_bpm | pulse | pi_proxy | no | no | bpm | OMIT on whole_palm: hr_bpm (section 6.3) |
| pulse__pi_proxy__whole_palm__OMIT__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__OMIT__kurtosis] |
| pulse__pi_proxy__whole_palm__OMIT__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__OMIT__n_windows]: count |
| pulse__pi_proxy__whole_palm__OMIT__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__OMIT__skewness] |
| pulse__pi_proxy__whole_palm__OMIT__snr_db | pulse | pi_proxy | no | no | dB | OMIT on whole_palm: snr_db (section 6.3) |
| pulse__pi_proxy__whole_palm__OMIT__sqi | pulse | pi_proxy | no | no | 0..1 | OMIT on whole_palm: sqi (section 6.3) |
| pulse__pi_proxy__whole_palm__OMIT__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__OMIT__template_corr] |
| pulse__pi_proxy__whole_palm__PBV__hr_bpm | pulse | pi_proxy | no | no | bpm | PBV on whole_palm: hr_bpm (section 6.3) |
| pulse__pi_proxy__whole_palm__PBV__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__PBV__kurtosis] |
| pulse__pi_proxy__whole_palm__PBV__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__PBV__n_windows]: count |
| pulse__pi_proxy__whole_palm__PBV__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__PBV__skewness] |
| pulse__pi_proxy__whole_palm__PBV__snr_db | pulse | pi_proxy | no | no | dB | PBV on whole_palm: snr_db (section 6.3) |
| pulse__pi_proxy__whole_palm__PBV__sqi | pulse | pi_proxy | no | no | 0..1 | PBV on whole_palm: sqi (section 6.3) |
| pulse__pi_proxy__whole_palm__PBV__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__PBV__template_corr] |
| pulse__pi_proxy__whole_palm__PCA__hr_bpm | pulse | pi_proxy | no | no | bpm | PCA on whole_palm: hr_bpm (section 6.3) |
| pulse__pi_proxy__whole_palm__PCA__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__PCA__kurtosis] |
| pulse__pi_proxy__whole_palm__PCA__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__PCA__n_windows]: count |
| pulse__pi_proxy__whole_palm__PCA__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__PCA__skewness] |
| pulse__pi_proxy__whole_palm__PCA__snr_db | pulse | pi_proxy | no | no | dB | PCA on whole_palm: snr_db (section 6.3) |
| pulse__pi_proxy__whole_palm__PCA__sqi | pulse | pi_proxy | no | no | 0..1 | PCA on whole_palm: sqi (section 6.3) |
| pulse__pi_proxy__whole_palm__PCA__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__PCA__template_corr] |
| pulse__pi_proxy__whole_palm__POS__hr_bpm | pulse | pi_proxy | no | no | bpm | POS on whole_palm: hr_bpm (section 6.3) |
| pulse__pi_proxy__whole_palm__POS__kurtosis | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__POS__kurtosis] |
| pulse__pi_proxy__whole_palm__POS__n_windows | pulse | pi_proxy | no | no | count | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__POS__n_windows]: count |
| pulse__pi_proxy__whole_palm__POS__skewness | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__POS__skewness] |
| pulse__pi_proxy__whole_palm__POS__snr_db | pulse | pi_proxy | no | no | dB | POS on whole_palm: snr_db (section 6.3) |
| pulse__pi_proxy__whole_palm__POS__sqi | pulse | pi_proxy | no | no | 0..1 | POS on whole_palm: sqi (section 6.3) |
| pulse__pi_proxy__whole_palm__POS__template_corr | pulse | pi_proxy | no | no |  | pulse extraction summary per method and ROI (protocol 6.3) [whole_palm__POS__template_corr] |
| qc__phone__drop_flag | qc | phone | no | no | bool | drop_pct above qc.drop_pct_max |
| qc__phone__drop_pct | qc | phone | no | no | % | dropped frames relative to expected |
| qc__phone__duration_s | qc | phone | no | no | s | clip duration on the reference clock |
| qc__phone__eis_flag | qc | phone | no | no | bool | eis_warp_px above qc.eis_warp_px_max |
| qc__phone__eis_warp_px | qc | phone | no | no | px | residual EIS warp (90th percentile of sampled pair warps) |
| qc__phone__flicker_flag | qc | phone | no | no | bool | mains flicker peak found (50/100 Hz or aliased 10 Hz) |
| qc__phone__flicker_peaks_hz | qc | phone | no | no | Hz | ingest quality-control flag or measurement (protocol 6.1) [flicker_peaks_hz]: frequency |
| qc__phone__flicker_peaks_hz__n | qc | phone | no | no |  | ingest quality-control flag or measurement (protocol 6.1) [flicker_peaks_hz__n] |
| qc__phone__fs_median | qc | phone | no | no | Hz | median frame rate from true frame times |
| qc__phone__hand_detected | qc | phone | no | no | bool | ingest quality-control flag or measurement (protocol 6.1) [hand_detected]: boolean flag |
| qc__phone__hand_is_left | qc | phone | no | no |  | ingest quality-control flag or measurement (protocol 6.1) [hand_is_left] |
| qc__phone__hand_palmar | qc | phone | no | no |  | ingest quality-control flag or measurement (protocol 6.1) [hand_palmar] |
| qc__phone__landmark_jitter_px | qc | phone | no | no | px | hand landmark jitter, motion proxy |
| qc__phone__landmark_source | qc | phone | no | no |  | ingest quality-control flag or measurement (protocol 6.1) [landmark_source] |
| qc__phone__lighting_drift_flag | qc | phone | no | no | bool | abs(lighting_drift_pct) above qc.lighting_drift_pct_max |
| qc__phone__lighting_drift_pct | qc | phone | no | no | % | linear trend of mean intensity over the clip relative to its mean |
| qc__phone__motion_flag | qc | phone | no | no | bool | motion proxy above threshold |
| qc__phone__n_frames | qc | phone | no | no | frames | number of frames with a timestamp |
| qc__phone__qc_series_source | qc | phone | no | no |  | ingest quality-control flag or measurement (protocol 6.1) [qc_series_source] |
| qc__phone__reasons | qc | phone | no | no | list | ingest quality-control flag or measurement (protocol 6.1) [reasons]: failing QC flag names, ';'-joined |
| qc__phone__reasons__n | qc | phone | no | no |  | ingest quality-control flag or measurement (protocol 6.1) [reasons__n] |
| qc__phone__saturation_flag | qc | phone | no | no | bool | saturation_frac above qc.saturation_frac_max |
| qc__phone__saturation_frac | qc | phone | no | no | fraction | saturated pixel fraction in the skin mask |
| qc__phone__sqi_best | qc | phone | no | no | 0..1 | best signal quality index of the clip |
| qc__phone__sqi_flag | qc | phone | no | no | bool | sqi_best below the pilot-frozen threshold |
| qc__phone__sync_grade | qc | phone | no | no |  | ingest quality-control flag or measurement (protocol 6.1) [sync_grade] |
| qc__phone__valid_clip | qc | phone | no | no | bool | hand detected and no drop/saturation/flicker flag and sqi above threshold |
| qc__phone__vignetting_flag | qc | phone | no | no | bool | vignetting_residual_pct above qc.vignetting_residual_pct_max |
| qc__phone__vignetting_residual_pct | qc | phone | no | no | % | residual non-uniformity of the corrected flat over the aperture |
| qc__pi__drop_flag | qc | pi | no | yes | bool | drop_pct above qc.drop_pct_max |
| qc__pi__drop_pct | qc | pi | no | yes | % | dropped frames relative to expected |
| qc__pi__duration_s | qc | pi | no | yes | s | clip duration on the reference clock |
| qc__pi__eis_flag | qc | pi | no | yes | bool | eis_warp_px above qc.eis_warp_px_max |
| qc__pi__eis_warp_px | qc | pi | no | yes | px | residual EIS warp (90th percentile of sampled pair warps) |
| qc__pi__flicker_flag | qc | pi | no | yes | bool | mains flicker peak found (50/100 Hz or aliased 10 Hz) |
| qc__pi__flicker_peaks_hz | qc | pi | no | yes | Hz | ingest quality-control flag or measurement (protocol 6.1) [flicker_peaks_hz]: frequency |
| qc__pi__flicker_peaks_hz__n | qc | pi | no | yes |  | ingest quality-control flag or measurement (protocol 6.1) [flicker_peaks_hz__n] |
| qc__pi__fs_median | qc | pi | no | yes | Hz | median frame rate from true frame times |
| qc__pi__hand_detected | qc | pi | no | yes | bool | ingest quality-control flag or measurement (protocol 6.1) [hand_detected]: boolean flag |
| qc__pi__hand_is_left | qc | pi | no | yes |  | ingest quality-control flag or measurement (protocol 6.1) [hand_is_left] |
| qc__pi__hand_palmar | qc | pi | no | yes |  | ingest quality-control flag or measurement (protocol 6.1) [hand_palmar] |
| qc__pi__landmark_jitter_px | qc | pi | no | yes | px | hand landmark jitter, motion proxy |
| qc__pi__landmark_source | qc | pi | no | yes |  | ingest quality-control flag or measurement (protocol 6.1) [landmark_source] |
| qc__pi__lighting_drift_flag | qc | pi | no | yes | bool | abs(lighting_drift_pct) above qc.lighting_drift_pct_max |
| qc__pi__lighting_drift_pct | qc | pi | no | yes | % | linear trend of mean intensity over the clip relative to its mean |
| qc__pi__motion_flag | qc | pi | no | yes | bool | motion proxy above threshold |
| qc__pi__n_frames | qc | pi | no | yes | frames | number of frames with a timestamp |
| qc__pi__qc_series_source | qc | pi | no | yes |  | ingest quality-control flag or measurement (protocol 6.1) [qc_series_source] |
| qc__pi__reasons | qc | pi | no | yes | list | ingest quality-control flag or measurement (protocol 6.1) [reasons]: failing QC flag names, ';'-joined |
| qc__pi__reasons__n | qc | pi | no | yes |  | ingest quality-control flag or measurement (protocol 6.1) [reasons__n] |
| qc__pi__saturation_flag | qc | pi | no | yes | bool | saturation_frac above qc.saturation_frac_max |
| qc__pi__saturation_frac | qc | pi | no | yes | fraction | saturated pixel fraction in the skin mask |
| qc__pi__sqi_best | qc | pi | no | yes | 0..1 | best signal quality index of the clip |
| qc__pi__sqi_flag | qc | pi | no | yes | bool | sqi_best below the pilot-frozen threshold |
| qc__pi__sync_grade | qc | pi | no | yes |  | ingest quality-control flag or measurement (protocol 6.1) [sync_grade] |
| qc__pi__valid_clip | qc | pi | no | yes | bool | hand detected and no drop/saturation/flicker flag and sqi above threshold |
| qc__pi__vignetting_flag | qc | pi | no | yes | bool | vignetting_residual_pct above qc.vignetting_residual_pct_max |
| qc__pi__vignetting_residual_pct | qc | pi | no | yes | % | residual non-uniformity of the corrected flat over the aperture |
| qc__pi_proxy__drop_flag | qc | pi_proxy | no | no | bool | drop_pct above qc.drop_pct_max |
| qc__pi_proxy__drop_pct | qc | pi_proxy | no | no | % | dropped frames relative to expected |
| qc__pi_proxy__duration_s | qc | pi_proxy | no | no | s | clip duration on the reference clock |
| qc__pi_proxy__eis_flag | qc | pi_proxy | no | no | bool | eis_warp_px above qc.eis_warp_px_max |
| qc__pi_proxy__eis_warp_px | qc | pi_proxy | no | no | px | residual EIS warp (90th percentile of sampled pair warps) |
| qc__pi_proxy__flicker_flag | qc | pi_proxy | no | no | bool | mains flicker peak found (50/100 Hz or aliased 10 Hz) |
| qc__pi_proxy__flicker_peaks_hz | qc | pi_proxy | no | no | Hz | ingest quality-control flag or measurement (protocol 6.1) [flicker_peaks_hz]: frequency |
| qc__pi_proxy__flicker_peaks_hz__n | qc | pi_proxy | no | no |  | ingest quality-control flag or measurement (protocol 6.1) [flicker_peaks_hz__n] |
| qc__pi_proxy__fs_median | qc | pi_proxy | no | no | Hz | median frame rate from true frame times |
| qc__pi_proxy__hand_detected | qc | pi_proxy | no | no | bool | ingest quality-control flag or measurement (protocol 6.1) [hand_detected]: boolean flag |
| qc__pi_proxy__hand_is_left | qc | pi_proxy | no | no |  | ingest quality-control flag or measurement (protocol 6.1) [hand_is_left] |
| qc__pi_proxy__hand_palmar | qc | pi_proxy | no | no |  | ingest quality-control flag or measurement (protocol 6.1) [hand_palmar] |
| qc__pi_proxy__landmark_jitter_px | qc | pi_proxy | no | no | px | hand landmark jitter, motion proxy |
| qc__pi_proxy__landmark_source | qc | pi_proxy | no | no |  | ingest quality-control flag or measurement (protocol 6.1) [landmark_source] |
| qc__pi_proxy__lighting_drift_flag | qc | pi_proxy | no | no | bool | abs(lighting_drift_pct) above qc.lighting_drift_pct_max |
| qc__pi_proxy__lighting_drift_pct | qc | pi_proxy | no | no | % | linear trend of mean intensity over the clip relative to its mean |
| qc__pi_proxy__motion_flag | qc | pi_proxy | no | no | bool | motion proxy above threshold |
| qc__pi_proxy__n_frames | qc | pi_proxy | no | no | frames | number of frames with a timestamp |
| qc__pi_proxy__qc_series_source | qc | pi_proxy | no | no |  | ingest quality-control flag or measurement (protocol 6.1) [qc_series_source] |
| qc__pi_proxy__reasons | qc | pi_proxy | no | no | list | ingest quality-control flag or measurement (protocol 6.1) [reasons]: failing QC flag names, ';'-joined |
| qc__pi_proxy__reasons__n | qc | pi_proxy | no | no |  | ingest quality-control flag or measurement (protocol 6.1) [reasons__n] |
| qc__pi_proxy__saturation_flag | qc | pi_proxy | no | no | bool | saturation_frac above qc.saturation_frac_max |
| qc__pi_proxy__saturation_frac | qc | pi_proxy | no | no | fraction | saturated pixel fraction in the skin mask |
| qc__pi_proxy__sqi_best | qc | pi_proxy | no | no | 0..1 | best signal quality index of the clip |
| qc__pi_proxy__sqi_flag | qc | pi_proxy | no | no | bool | sqi_best below the pilot-frozen threshold |
| qc__pi_proxy__sync_grade | qc | pi_proxy | no | no |  | ingest quality-control flag or measurement (protocol 6.1) [sync_grade] |
| qc__pi_proxy__valid_clip | qc | pi_proxy | no | no | bool | hand detected and no drop/saturation/flicker flag and sqi above threshold |
| qc__pi_proxy__vignetting_flag | qc | pi_proxy | no | no | bool | vignetting_residual_pct above qc.vignetting_residual_pct_max |
| qc__pi_proxy__vignetting_residual_pct | qc | pi_proxy | no | no | % | residual non-uniformity of the corrected flat over the aperture |
| resp__phone__resp_power_ratio | resp | phone | no | no | ratio | respiratory modulation proxy (protocol 6.5) [resp_power_ratio]: dimensionless ratio or index |
| resp__phone__resp_rate_am_bpm | resp | phone | no | no | bpm | respiratory modulation proxy (protocol 6.5) [resp_rate_am_bpm]: rate in beats per minute |
| resp__phone__resp_rate_bpm | resp | phone | no | no | bpm | respiratory modulation proxy (protocol 6.5) [resp_rate_bpm]: rate in beats per minute |
| resp__phone__resp_rate_ibi_bpm | resp | phone | no | no | bpm | respiratory modulation proxy (protocol 6.5) [resp_rate_ibi_bpm]: rate in beats per minute |
| resp__pi__resp_power_ratio | resp | pi | no | yes | ratio | respiratory modulation proxy (protocol 6.5) [resp_power_ratio]: dimensionless ratio or index |
| resp__pi__resp_rate_am_bpm | resp | pi | no | yes | bpm | respiratory modulation proxy (protocol 6.5) [resp_rate_am_bpm]: rate in beats per minute |
| resp__pi__resp_rate_bpm | resp | pi | no | yes | bpm | respiratory modulation proxy (protocol 6.5) [resp_rate_bpm]: rate in beats per minute |
| resp__pi__resp_rate_ibi_bpm | resp | pi | no | yes | bpm | respiratory modulation proxy (protocol 6.5) [resp_rate_ibi_bpm]: rate in beats per minute |
| resp__pi_proxy__resp_power_ratio | resp | pi_proxy | no | no | ratio | respiratory modulation proxy (protocol 6.5) [resp_power_ratio]: dimensionless ratio or index |
| resp__pi_proxy__resp_rate_am_bpm | resp | pi_proxy | no | no | bpm | respiratory modulation proxy (protocol 6.5) [resp_rate_am_bpm]: rate in beats per minute |
| resp__pi_proxy__resp_rate_bpm | resp | pi_proxy | no | no | bpm | respiratory modulation proxy (protocol 6.5) [resp_rate_bpm]: rate in beats per minute |
| resp__pi_proxy__resp_rate_ibi_bpm | resp | pi_proxy | no | no | bpm | respiratory modulation proxy (protocol 6.5) [resp_rate_ibi_bpm]: rate in beats per minute |
| static_colour__phone__central_palm__B_mean | static_colour | phone | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [central_palm__B_mean] |
| static_colour__phone__central_palm__G_mean | static_colour | phone | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [central_palm__G_mean] |
| static_colour__phone__central_palm__R_mean | static_colour | phone | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [central_palm__R_mean] |
| static_colour__phone__central_palm__bg | static_colour | phone | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [central_palm__bg]: chromaticity ratio |
| static_colour__phone__central_palm__melanin_proxy | static_colour | phone | no | no | a.u. | static colour feature from the first seconds of the clip (protocol 6.2) [central_palm__melanin_proxy]: log(R) - log(B); a camera-space proxy, not a melanin measurement |
| static_colour__phone__central_palm__rg | static_colour | phone | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [central_palm__rg]: chromaticity ratio |
| static_colour__phone__central_palm_pallor_index | static_colour | phone | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [central_palm_pallor_index]: dimensionless ratio or index |
| static_colour__phone__colour_space | static_colour | phone | no | no | label | static colour feature from the first seconds of the clip (protocol 6.2) [colour_space]: linear_raw or inverted_srgb (phone values are linearised from sRGB) |
| static_colour__phone__hypothenar__B_mean | static_colour | phone | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [hypothenar__B_mean] |
| static_colour__phone__hypothenar__G_mean | static_colour | phone | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [hypothenar__G_mean] |
| static_colour__phone__hypothenar__R_mean | static_colour | phone | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [hypothenar__R_mean] |
| static_colour__phone__hypothenar__bg | static_colour | phone | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [hypothenar__bg]: chromaticity ratio |
| static_colour__phone__hypothenar__melanin_proxy | static_colour | phone | no | no | a.u. | static colour feature from the first seconds of the clip (protocol 6.2) [hypothenar__melanin_proxy]: log(R) - log(B); a camera-space proxy, not a melanin measurement |
| static_colour__phone__hypothenar__rg | static_colour | phone | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [hypothenar__rg]: chromaticity ratio |
| static_colour__phone__linearised_from_srgb | static_colour | phone | no | no | bool | static colour feature from the first seconds of the clip (protocol 6.2) [linearised_from_srgb]: values were inverted from sRGB (CONTRACTS 0.4), not truly linear |
| static_colour__phone__mid_phalanges__B_mean | static_colour | phone | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [mid_phalanges__B_mean] |
| static_colour__phone__mid_phalanges__G_mean | static_colour | phone | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [mid_phalanges__G_mean] |
| static_colour__phone__mid_phalanges__R_mean | static_colour | phone | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [mid_phalanges__R_mean] |
| static_colour__phone__mid_phalanges__bg | static_colour | phone | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [mid_phalanges__bg]: chromaticity ratio |
| static_colour__phone__mid_phalanges__melanin_proxy | static_colour | phone | no | no | a.u. | static colour feature from the first seconds of the clip (protocol 6.2) [mid_phalanges__melanin_proxy]: log(R) - log(B); a camera-space proxy, not a melanin measurement |
| static_colour__phone__mid_phalanges__rg | static_colour | phone | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [mid_phalanges__rg]: chromaticity ratio |
| static_colour__phone__n_frames_used | static_colour | phone | no | no | bool | static colour feature from the first seconds of the clip (protocol 6.2) [n_frames_used]: boolean flag |
| static_colour__phone__pad_index__B_mean | static_colour | phone | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [pad_index__B_mean] |
| static_colour__phone__pad_index__G_mean | static_colour | phone | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [pad_index__G_mean] |
| static_colour__phone__pad_index__R_mean | static_colour | phone | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [pad_index__R_mean] |
| static_colour__phone__pad_index__bg | static_colour | phone | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [pad_index__bg]: chromaticity ratio |
| static_colour__phone__pad_index__melanin_proxy | static_colour | phone | no | no | a.u. | static colour feature from the first seconds of the clip (protocol 6.2) [pad_index__melanin_proxy]: log(R) - log(B); a camera-space proxy, not a melanin measurement |
| static_colour__phone__pad_index__rg | static_colour | phone | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [pad_index__rg]: chromaticity ratio |
| static_colour__phone__pad_little__B_mean | static_colour | phone | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [pad_little__B_mean] |
| static_colour__phone__pad_little__G_mean | static_colour | phone | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [pad_little__G_mean] |
| static_colour__phone__pad_little__R_mean | static_colour | phone | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [pad_little__R_mean] |
| static_colour__phone__pad_little__bg | static_colour | phone | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [pad_little__bg]: chromaticity ratio |
| static_colour__phone__pad_little__melanin_proxy | static_colour | phone | no | no | a.u. | static colour feature from the first seconds of the clip (protocol 6.2) [pad_little__melanin_proxy]: log(R) - log(B); a camera-space proxy, not a melanin measurement |
| static_colour__phone__pad_little__rg | static_colour | phone | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [pad_little__rg]: chromaticity ratio |
| static_colour__phone__pad_middle__B_mean | static_colour | phone | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [pad_middle__B_mean] |
| static_colour__phone__pad_middle__G_mean | static_colour | phone | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [pad_middle__G_mean] |
| static_colour__phone__pad_middle__R_mean | static_colour | phone | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [pad_middle__R_mean] |
| static_colour__phone__pad_middle__bg | static_colour | phone | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [pad_middle__bg]: chromaticity ratio |
| static_colour__phone__pad_middle__melanin_proxy | static_colour | phone | no | no | a.u. | static colour feature from the first seconds of the clip (protocol 6.2) [pad_middle__melanin_proxy]: log(R) - log(B); a camera-space proxy, not a melanin measurement |
| static_colour__phone__pad_middle__rg | static_colour | phone | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [pad_middle__rg]: chromaticity ratio |
| static_colour__phone__pad_ring__B_mean | static_colour | phone | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [pad_ring__B_mean] |
| static_colour__phone__pad_ring__G_mean | static_colour | phone | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [pad_ring__G_mean] |
| static_colour__phone__pad_ring__R_mean | static_colour | phone | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [pad_ring__R_mean] |
| static_colour__phone__pad_ring__bg | static_colour | phone | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [pad_ring__bg]: chromaticity ratio |
| static_colour__phone__pad_ring__melanin_proxy | static_colour | phone | no | no | a.u. | static colour feature from the first seconds of the clip (protocol 6.2) [pad_ring__melanin_proxy]: log(R) - log(B); a camera-space proxy, not a melanin measurement |
| static_colour__phone__pad_ring__rg | static_colour | phone | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [pad_ring__rg]: chromaticity ratio |
| static_colour__phone__prox_index__B_mean | static_colour | phone | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [prox_index__B_mean] |
| static_colour__phone__prox_index__G_mean | static_colour | phone | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [prox_index__G_mean] |
| static_colour__phone__prox_index__R_mean | static_colour | phone | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [prox_index__R_mean] |
| static_colour__phone__prox_index__bg | static_colour | phone | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [prox_index__bg]: chromaticity ratio |
| static_colour__phone__prox_index__melanin_proxy | static_colour | phone | no | no | a.u. | static colour feature from the first seconds of the clip (protocol 6.2) [prox_index__melanin_proxy]: log(R) - log(B); a camera-space proxy, not a melanin measurement |
| static_colour__phone__prox_index__rg | static_colour | phone | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [prox_index__rg]: chromaticity ratio |
| static_colour__phone__prox_little__B_mean | static_colour | phone | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [prox_little__B_mean] |
| static_colour__phone__prox_little__G_mean | static_colour | phone | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [prox_little__G_mean] |
| static_colour__phone__prox_little__R_mean | static_colour | phone | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [prox_little__R_mean] |
| static_colour__phone__prox_little__bg | static_colour | phone | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [prox_little__bg]: chromaticity ratio |
| static_colour__phone__prox_little__melanin_proxy | static_colour | phone | no | no | a.u. | static colour feature from the first seconds of the clip (protocol 6.2) [prox_little__melanin_proxy]: log(R) - log(B); a camera-space proxy, not a melanin measurement |
| static_colour__phone__prox_little__rg | static_colour | phone | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [prox_little__rg]: chromaticity ratio |
| static_colour__phone__prox_middle__B_mean | static_colour | phone | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [prox_middle__B_mean] |
| static_colour__phone__prox_middle__G_mean | static_colour | phone | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [prox_middle__G_mean] |
| static_colour__phone__prox_middle__R_mean | static_colour | phone | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [prox_middle__R_mean] |
| static_colour__phone__prox_middle__bg | static_colour | phone | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [prox_middle__bg]: chromaticity ratio |
| static_colour__phone__prox_middle__melanin_proxy | static_colour | phone | no | no | a.u. | static colour feature from the first seconds of the clip (protocol 6.2) [prox_middle__melanin_proxy]: log(R) - log(B); a camera-space proxy, not a melanin measurement |
| static_colour__phone__prox_middle__rg | static_colour | phone | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [prox_middle__rg]: chromaticity ratio |
| static_colour__phone__prox_ring__B_mean | static_colour | phone | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [prox_ring__B_mean] |
| static_colour__phone__prox_ring__G_mean | static_colour | phone | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [prox_ring__G_mean] |
| static_colour__phone__prox_ring__R_mean | static_colour | phone | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [prox_ring__R_mean] |
| static_colour__phone__prox_ring__bg | static_colour | phone | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [prox_ring__bg]: chromaticity ratio |
| static_colour__phone__prox_ring__melanin_proxy | static_colour | phone | no | no | a.u. | static colour feature from the first seconds of the clip (protocol 6.2) [prox_ring__melanin_proxy]: log(R) - log(B); a camera-space proxy, not a melanin measurement |
| static_colour__phone__prox_ring__rg | static_colour | phone | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [prox_ring__rg]: chromaticity ratio |
| static_colour__phone__spatial_rg_variance | static_colour | phone | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [spatial_rg_variance]: dimensionless ratio or index |
| static_colour__phone__thenar__B_mean | static_colour | phone | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [thenar__B_mean] |
| static_colour__phone__thenar__G_mean | static_colour | phone | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [thenar__G_mean] |
| static_colour__phone__thenar__R_mean | static_colour | phone | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [thenar__R_mean] |
| static_colour__phone__thenar__bg | static_colour | phone | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [thenar__bg]: chromaticity ratio |
| static_colour__phone__thenar__melanin_proxy | static_colour | phone | no | no | a.u. | static colour feature from the first seconds of the clip (protocol 6.2) [thenar__melanin_proxy]: log(R) - log(B); a camera-space proxy, not a melanin measurement |
| static_colour__phone__thenar__rg | static_colour | phone | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [thenar__rg]: chromaticity ratio |
| static_colour__phone__volar_wrist__B_mean | static_colour | phone | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [volar_wrist__B_mean] |
| static_colour__phone__volar_wrist__G_mean | static_colour | phone | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [volar_wrist__G_mean] |
| static_colour__phone__volar_wrist__R_mean | static_colour | phone | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [volar_wrist__R_mean] |
| static_colour__phone__volar_wrist__bg | static_colour | phone | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [volar_wrist__bg]: chromaticity ratio |
| static_colour__phone__volar_wrist__melanin_proxy | static_colour | phone | no | no | a.u. | static colour feature from the first seconds of the clip (protocol 6.2) [volar_wrist__melanin_proxy]: log(R) - log(B); a camera-space proxy, not a melanin measurement |
| static_colour__phone__volar_wrist__rg | static_colour | phone | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [volar_wrist__rg]: chromaticity ratio |
| static_colour__phone__whole_palm__B_mean | static_colour | phone | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [whole_palm__B_mean] |
| static_colour__phone__whole_palm__G_mean | static_colour | phone | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [whole_palm__G_mean] |
| static_colour__phone__whole_palm__R_mean | static_colour | phone | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [whole_palm__R_mean] |
| static_colour__phone__whole_palm__bg | static_colour | phone | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [whole_palm__bg]: chromaticity ratio |
| static_colour__phone__whole_palm__melanin_proxy | static_colour | phone | no | no | a.u. | static colour feature from the first seconds of the clip (protocol 6.2) [whole_palm__melanin_proxy]: log(R) - log(B); a camera-space proxy, not a melanin measurement |
| static_colour__phone__whole_palm__rg | static_colour | phone | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [whole_palm__rg]: chromaticity ratio |
| static_colour__pi__central_palm__B_mean | static_colour | pi | no | yes |  | static colour feature from the first seconds of the clip (protocol 6.2) [central_palm__B_mean] |
| static_colour__pi__central_palm__G_mean | static_colour | pi | no | yes |  | static colour feature from the first seconds of the clip (protocol 6.2) [central_palm__G_mean] |
| static_colour__pi__central_palm__R_mean | static_colour | pi | no | yes |  | static colour feature from the first seconds of the clip (protocol 6.2) [central_palm__R_mean] |
| static_colour__pi__central_palm__bg | static_colour | pi | no | yes | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [central_palm__bg]: chromaticity ratio |
| static_colour__pi__central_palm__melanin_proxy | static_colour | pi | no | yes | a.u. | static colour feature from the first seconds of the clip (protocol 6.2) [central_palm__melanin_proxy]: log(R) - log(B); a camera-space proxy, not a melanin measurement |
| static_colour__pi__central_palm__rg | static_colour | pi | no | yes | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [central_palm__rg]: chromaticity ratio |
| static_colour__pi__central_palm_pallor_index | static_colour | pi | no | yes | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [central_palm_pallor_index]: dimensionless ratio or index |
| static_colour__pi__colour_space | static_colour | pi | no | yes | label | static colour feature from the first seconds of the clip (protocol 6.2) [colour_space]: linear_raw or inverted_srgb (phone values are linearised from sRGB) |
| static_colour__pi__hypothenar__B_mean | static_colour | pi | no | yes |  | static colour feature from the first seconds of the clip (protocol 6.2) [hypothenar__B_mean] |
| static_colour__pi__hypothenar__G_mean | static_colour | pi | no | yes |  | static colour feature from the first seconds of the clip (protocol 6.2) [hypothenar__G_mean] |
| static_colour__pi__hypothenar__R_mean | static_colour | pi | no | yes |  | static colour feature from the first seconds of the clip (protocol 6.2) [hypothenar__R_mean] |
| static_colour__pi__hypothenar__bg | static_colour | pi | no | yes | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [hypothenar__bg]: chromaticity ratio |
| static_colour__pi__hypothenar__melanin_proxy | static_colour | pi | no | yes | a.u. | static colour feature from the first seconds of the clip (protocol 6.2) [hypothenar__melanin_proxy]: log(R) - log(B); a camera-space proxy, not a melanin measurement |
| static_colour__pi__hypothenar__rg | static_colour | pi | no | yes | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [hypothenar__rg]: chromaticity ratio |
| static_colour__pi__linearised_from_srgb | static_colour | pi | no | yes | bool | static colour feature from the first seconds of the clip (protocol 6.2) [linearised_from_srgb]: values were inverted from sRGB (CONTRACTS 0.4), not truly linear |
| static_colour__pi__mid_phalanges__B_mean | static_colour | pi | no | yes |  | static colour feature from the first seconds of the clip (protocol 6.2) [mid_phalanges__B_mean] |
| static_colour__pi__mid_phalanges__G_mean | static_colour | pi | no | yes |  | static colour feature from the first seconds of the clip (protocol 6.2) [mid_phalanges__G_mean] |
| static_colour__pi__mid_phalanges__R_mean | static_colour | pi | no | yes |  | static colour feature from the first seconds of the clip (protocol 6.2) [mid_phalanges__R_mean] |
| static_colour__pi__mid_phalanges__bg | static_colour | pi | no | yes | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [mid_phalanges__bg]: chromaticity ratio |
| static_colour__pi__mid_phalanges__melanin_proxy | static_colour | pi | no | yes | a.u. | static colour feature from the first seconds of the clip (protocol 6.2) [mid_phalanges__melanin_proxy]: log(R) - log(B); a camera-space proxy, not a melanin measurement |
| static_colour__pi__mid_phalanges__rg | static_colour | pi | no | yes | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [mid_phalanges__rg]: chromaticity ratio |
| static_colour__pi__n_frames_used | static_colour | pi | no | yes | bool | static colour feature from the first seconds of the clip (protocol 6.2) [n_frames_used]: boolean flag |
| static_colour__pi__pad_index__B_mean | static_colour | pi | no | yes |  | static colour feature from the first seconds of the clip (protocol 6.2) [pad_index__B_mean] |
| static_colour__pi__pad_index__G_mean | static_colour | pi | no | yes |  | static colour feature from the first seconds of the clip (protocol 6.2) [pad_index__G_mean] |
| static_colour__pi__pad_index__R_mean | static_colour | pi | no | yes |  | static colour feature from the first seconds of the clip (protocol 6.2) [pad_index__R_mean] |
| static_colour__pi__pad_index__bg | static_colour | pi | no | yes | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [pad_index__bg]: chromaticity ratio |
| static_colour__pi__pad_index__melanin_proxy | static_colour | pi | no | yes | a.u. | static colour feature from the first seconds of the clip (protocol 6.2) [pad_index__melanin_proxy]: log(R) - log(B); a camera-space proxy, not a melanin measurement |
| static_colour__pi__pad_index__rg | static_colour | pi | no | yes | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [pad_index__rg]: chromaticity ratio |
| static_colour__pi__pad_little__B_mean | static_colour | pi | no | yes |  | static colour feature from the first seconds of the clip (protocol 6.2) [pad_little__B_mean] |
| static_colour__pi__pad_little__G_mean | static_colour | pi | no | yes |  | static colour feature from the first seconds of the clip (protocol 6.2) [pad_little__G_mean] |
| static_colour__pi__pad_little__R_mean | static_colour | pi | no | yes |  | static colour feature from the first seconds of the clip (protocol 6.2) [pad_little__R_mean] |
| static_colour__pi__pad_little__bg | static_colour | pi | no | yes | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [pad_little__bg]: chromaticity ratio |
| static_colour__pi__pad_little__melanin_proxy | static_colour | pi | no | yes | a.u. | static colour feature from the first seconds of the clip (protocol 6.2) [pad_little__melanin_proxy]: log(R) - log(B); a camera-space proxy, not a melanin measurement |
| static_colour__pi__pad_little__rg | static_colour | pi | no | yes | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [pad_little__rg]: chromaticity ratio |
| static_colour__pi__pad_middle__B_mean | static_colour | pi | no | yes |  | static colour feature from the first seconds of the clip (protocol 6.2) [pad_middle__B_mean] |
| static_colour__pi__pad_middle__G_mean | static_colour | pi | no | yes |  | static colour feature from the first seconds of the clip (protocol 6.2) [pad_middle__G_mean] |
| static_colour__pi__pad_middle__R_mean | static_colour | pi | no | yes |  | static colour feature from the first seconds of the clip (protocol 6.2) [pad_middle__R_mean] |
| static_colour__pi__pad_middle__bg | static_colour | pi | no | yes | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [pad_middle__bg]: chromaticity ratio |
| static_colour__pi__pad_middle__melanin_proxy | static_colour | pi | no | yes | a.u. | static colour feature from the first seconds of the clip (protocol 6.2) [pad_middle__melanin_proxy]: log(R) - log(B); a camera-space proxy, not a melanin measurement |
| static_colour__pi__pad_middle__rg | static_colour | pi | no | yes | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [pad_middle__rg]: chromaticity ratio |
| static_colour__pi__pad_ring__B_mean | static_colour | pi | no | yes |  | static colour feature from the first seconds of the clip (protocol 6.2) [pad_ring__B_mean] |
| static_colour__pi__pad_ring__G_mean | static_colour | pi | no | yes |  | static colour feature from the first seconds of the clip (protocol 6.2) [pad_ring__G_mean] |
| static_colour__pi__pad_ring__R_mean | static_colour | pi | no | yes |  | static colour feature from the first seconds of the clip (protocol 6.2) [pad_ring__R_mean] |
| static_colour__pi__pad_ring__bg | static_colour | pi | no | yes | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [pad_ring__bg]: chromaticity ratio |
| static_colour__pi__pad_ring__melanin_proxy | static_colour | pi | no | yes | a.u. | static colour feature from the first seconds of the clip (protocol 6.2) [pad_ring__melanin_proxy]: log(R) - log(B); a camera-space proxy, not a melanin measurement |
| static_colour__pi__pad_ring__rg | static_colour | pi | no | yes | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [pad_ring__rg]: chromaticity ratio |
| static_colour__pi__prox_index__B_mean | static_colour | pi | no | yes |  | static colour feature from the first seconds of the clip (protocol 6.2) [prox_index__B_mean] |
| static_colour__pi__prox_index__G_mean | static_colour | pi | no | yes |  | static colour feature from the first seconds of the clip (protocol 6.2) [prox_index__G_mean] |
| static_colour__pi__prox_index__R_mean | static_colour | pi | no | yes |  | static colour feature from the first seconds of the clip (protocol 6.2) [prox_index__R_mean] |
| static_colour__pi__prox_index__bg | static_colour | pi | no | yes | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [prox_index__bg]: chromaticity ratio |
| static_colour__pi__prox_index__melanin_proxy | static_colour | pi | no | yes | a.u. | static colour feature from the first seconds of the clip (protocol 6.2) [prox_index__melanin_proxy]: log(R) - log(B); a camera-space proxy, not a melanin measurement |
| static_colour__pi__prox_index__rg | static_colour | pi | no | yes | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [prox_index__rg]: chromaticity ratio |
| static_colour__pi__prox_little__B_mean | static_colour | pi | no | yes |  | static colour feature from the first seconds of the clip (protocol 6.2) [prox_little__B_mean] |
| static_colour__pi__prox_little__G_mean | static_colour | pi | no | yes |  | static colour feature from the first seconds of the clip (protocol 6.2) [prox_little__G_mean] |
| static_colour__pi__prox_little__R_mean | static_colour | pi | no | yes |  | static colour feature from the first seconds of the clip (protocol 6.2) [prox_little__R_mean] |
| static_colour__pi__prox_little__bg | static_colour | pi | no | yes | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [prox_little__bg]: chromaticity ratio |
| static_colour__pi__prox_little__melanin_proxy | static_colour | pi | no | yes | a.u. | static colour feature from the first seconds of the clip (protocol 6.2) [prox_little__melanin_proxy]: log(R) - log(B); a camera-space proxy, not a melanin measurement |
| static_colour__pi__prox_little__rg | static_colour | pi | no | yes | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [prox_little__rg]: chromaticity ratio |
| static_colour__pi__prox_middle__B_mean | static_colour | pi | no | yes |  | static colour feature from the first seconds of the clip (protocol 6.2) [prox_middle__B_mean] |
| static_colour__pi__prox_middle__G_mean | static_colour | pi | no | yes |  | static colour feature from the first seconds of the clip (protocol 6.2) [prox_middle__G_mean] |
| static_colour__pi__prox_middle__R_mean | static_colour | pi | no | yes |  | static colour feature from the first seconds of the clip (protocol 6.2) [prox_middle__R_mean] |
| static_colour__pi__prox_middle__bg | static_colour | pi | no | yes | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [prox_middle__bg]: chromaticity ratio |
| static_colour__pi__prox_middle__melanin_proxy | static_colour | pi | no | yes | a.u. | static colour feature from the first seconds of the clip (protocol 6.2) [prox_middle__melanin_proxy]: log(R) - log(B); a camera-space proxy, not a melanin measurement |
| static_colour__pi__prox_middle__rg | static_colour | pi | no | yes | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [prox_middle__rg]: chromaticity ratio |
| static_colour__pi__prox_ring__B_mean | static_colour | pi | no | yes |  | static colour feature from the first seconds of the clip (protocol 6.2) [prox_ring__B_mean] |
| static_colour__pi__prox_ring__G_mean | static_colour | pi | no | yes |  | static colour feature from the first seconds of the clip (protocol 6.2) [prox_ring__G_mean] |
| static_colour__pi__prox_ring__R_mean | static_colour | pi | no | yes |  | static colour feature from the first seconds of the clip (protocol 6.2) [prox_ring__R_mean] |
| static_colour__pi__prox_ring__bg | static_colour | pi | no | yes | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [prox_ring__bg]: chromaticity ratio |
| static_colour__pi__prox_ring__melanin_proxy | static_colour | pi | no | yes | a.u. | static colour feature from the first seconds of the clip (protocol 6.2) [prox_ring__melanin_proxy]: log(R) - log(B); a camera-space proxy, not a melanin measurement |
| static_colour__pi__prox_ring__rg | static_colour | pi | no | yes | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [prox_ring__rg]: chromaticity ratio |
| static_colour__pi__spatial_rg_variance | static_colour | pi | no | yes | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [spatial_rg_variance]: dimensionless ratio or index |
| static_colour__pi__thenar__B_mean | static_colour | pi | no | yes |  | static colour feature from the first seconds of the clip (protocol 6.2) [thenar__B_mean] |
| static_colour__pi__thenar__G_mean | static_colour | pi | no | yes |  | static colour feature from the first seconds of the clip (protocol 6.2) [thenar__G_mean] |
| static_colour__pi__thenar__R_mean | static_colour | pi | no | yes |  | static colour feature from the first seconds of the clip (protocol 6.2) [thenar__R_mean] |
| static_colour__pi__thenar__bg | static_colour | pi | no | yes | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [thenar__bg]: chromaticity ratio |
| static_colour__pi__thenar__melanin_proxy | static_colour | pi | no | yes | a.u. | static colour feature from the first seconds of the clip (protocol 6.2) [thenar__melanin_proxy]: log(R) - log(B); a camera-space proxy, not a melanin measurement |
| static_colour__pi__thenar__rg | static_colour | pi | no | yes | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [thenar__rg]: chromaticity ratio |
| static_colour__pi__volar_wrist__B_mean | static_colour | pi | no | yes |  | static colour feature from the first seconds of the clip (protocol 6.2) [volar_wrist__B_mean] |
| static_colour__pi__volar_wrist__G_mean | static_colour | pi | no | yes |  | static colour feature from the first seconds of the clip (protocol 6.2) [volar_wrist__G_mean] |
| static_colour__pi__volar_wrist__R_mean | static_colour | pi | no | yes |  | static colour feature from the first seconds of the clip (protocol 6.2) [volar_wrist__R_mean] |
| static_colour__pi__volar_wrist__bg | static_colour | pi | no | yes | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [volar_wrist__bg]: chromaticity ratio |
| static_colour__pi__volar_wrist__melanin_proxy | static_colour | pi | no | yes | a.u. | static colour feature from the first seconds of the clip (protocol 6.2) [volar_wrist__melanin_proxy]: log(R) - log(B); a camera-space proxy, not a melanin measurement |
| static_colour__pi__volar_wrist__rg | static_colour | pi | no | yes | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [volar_wrist__rg]: chromaticity ratio |
| static_colour__pi__whole_palm__B_mean | static_colour | pi | no | yes |  | static colour feature from the first seconds of the clip (protocol 6.2) [whole_palm__B_mean] |
| static_colour__pi__whole_palm__G_mean | static_colour | pi | no | yes |  | static colour feature from the first seconds of the clip (protocol 6.2) [whole_palm__G_mean] |
| static_colour__pi__whole_palm__R_mean | static_colour | pi | no | yes |  | static colour feature from the first seconds of the clip (protocol 6.2) [whole_palm__R_mean] |
| static_colour__pi__whole_palm__bg | static_colour | pi | no | yes | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [whole_palm__bg]: chromaticity ratio |
| static_colour__pi__whole_palm__melanin_proxy | static_colour | pi | no | yes | a.u. | static colour feature from the first seconds of the clip (protocol 6.2) [whole_palm__melanin_proxy]: log(R) - log(B); a camera-space proxy, not a melanin measurement |
| static_colour__pi__whole_palm__rg | static_colour | pi | no | yes | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [whole_palm__rg]: chromaticity ratio |
| static_colour__pi_proxy__central_palm__B_mean | static_colour | pi_proxy | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [central_palm__B_mean] |
| static_colour__pi_proxy__central_palm__G_mean | static_colour | pi_proxy | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [central_palm__G_mean] |
| static_colour__pi_proxy__central_palm__R_mean | static_colour | pi_proxy | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [central_palm__R_mean] |
| static_colour__pi_proxy__central_palm__bg | static_colour | pi_proxy | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [central_palm__bg]: chromaticity ratio |
| static_colour__pi_proxy__central_palm__melanin_proxy | static_colour | pi_proxy | no | no | a.u. | static colour feature from the first seconds of the clip (protocol 6.2) [central_palm__melanin_proxy]: log(R) - log(B); a camera-space proxy, not a melanin measurement |
| static_colour__pi_proxy__central_palm__rg | static_colour | pi_proxy | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [central_palm__rg]: chromaticity ratio |
| static_colour__pi_proxy__central_palm_pallor_index | static_colour | pi_proxy | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [central_palm_pallor_index]: dimensionless ratio or index |
| static_colour__pi_proxy__colour_space | static_colour | pi_proxy | no | no | label | static colour feature from the first seconds of the clip (protocol 6.2) [colour_space]: linear_raw or inverted_srgb (phone values are linearised from sRGB) |
| static_colour__pi_proxy__hypothenar__B_mean | static_colour | pi_proxy | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [hypothenar__B_mean] |
| static_colour__pi_proxy__hypothenar__G_mean | static_colour | pi_proxy | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [hypothenar__G_mean] |
| static_colour__pi_proxy__hypothenar__R_mean | static_colour | pi_proxy | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [hypothenar__R_mean] |
| static_colour__pi_proxy__hypothenar__bg | static_colour | pi_proxy | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [hypothenar__bg]: chromaticity ratio |
| static_colour__pi_proxy__hypothenar__melanin_proxy | static_colour | pi_proxy | no | no | a.u. | static colour feature from the first seconds of the clip (protocol 6.2) [hypothenar__melanin_proxy]: log(R) - log(B); a camera-space proxy, not a melanin measurement |
| static_colour__pi_proxy__hypothenar__rg | static_colour | pi_proxy | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [hypothenar__rg]: chromaticity ratio |
| static_colour__pi_proxy__linearised_from_srgb | static_colour | pi_proxy | no | no | bool | static colour feature from the first seconds of the clip (protocol 6.2) [linearised_from_srgb]: values were inverted from sRGB (CONTRACTS 0.4), not truly linear |
| static_colour__pi_proxy__mid_phalanges__B_mean | static_colour | pi_proxy | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [mid_phalanges__B_mean] |
| static_colour__pi_proxy__mid_phalanges__G_mean | static_colour | pi_proxy | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [mid_phalanges__G_mean] |
| static_colour__pi_proxy__mid_phalanges__R_mean | static_colour | pi_proxy | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [mid_phalanges__R_mean] |
| static_colour__pi_proxy__mid_phalanges__bg | static_colour | pi_proxy | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [mid_phalanges__bg]: chromaticity ratio |
| static_colour__pi_proxy__mid_phalanges__melanin_proxy | static_colour | pi_proxy | no | no | a.u. | static colour feature from the first seconds of the clip (protocol 6.2) [mid_phalanges__melanin_proxy]: log(R) - log(B); a camera-space proxy, not a melanin measurement |
| static_colour__pi_proxy__mid_phalanges__rg | static_colour | pi_proxy | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [mid_phalanges__rg]: chromaticity ratio |
| static_colour__pi_proxy__n_frames_used | static_colour | pi_proxy | no | no | bool | static colour feature from the first seconds of the clip (protocol 6.2) [n_frames_used]: boolean flag |
| static_colour__pi_proxy__pad_index__B_mean | static_colour | pi_proxy | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [pad_index__B_mean] |
| static_colour__pi_proxy__pad_index__G_mean | static_colour | pi_proxy | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [pad_index__G_mean] |
| static_colour__pi_proxy__pad_index__R_mean | static_colour | pi_proxy | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [pad_index__R_mean] |
| static_colour__pi_proxy__pad_index__bg | static_colour | pi_proxy | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [pad_index__bg]: chromaticity ratio |
| static_colour__pi_proxy__pad_index__melanin_proxy | static_colour | pi_proxy | no | no | a.u. | static colour feature from the first seconds of the clip (protocol 6.2) [pad_index__melanin_proxy]: log(R) - log(B); a camera-space proxy, not a melanin measurement |
| static_colour__pi_proxy__pad_index__rg | static_colour | pi_proxy | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [pad_index__rg]: chromaticity ratio |
| static_colour__pi_proxy__pad_little__B_mean | static_colour | pi_proxy | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [pad_little__B_mean] |
| static_colour__pi_proxy__pad_little__G_mean | static_colour | pi_proxy | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [pad_little__G_mean] |
| static_colour__pi_proxy__pad_little__R_mean | static_colour | pi_proxy | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [pad_little__R_mean] |
| static_colour__pi_proxy__pad_little__bg | static_colour | pi_proxy | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [pad_little__bg]: chromaticity ratio |
| static_colour__pi_proxy__pad_little__melanin_proxy | static_colour | pi_proxy | no | no | a.u. | static colour feature from the first seconds of the clip (protocol 6.2) [pad_little__melanin_proxy]: log(R) - log(B); a camera-space proxy, not a melanin measurement |
| static_colour__pi_proxy__pad_little__rg | static_colour | pi_proxy | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [pad_little__rg]: chromaticity ratio |
| static_colour__pi_proxy__pad_middle__B_mean | static_colour | pi_proxy | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [pad_middle__B_mean] |
| static_colour__pi_proxy__pad_middle__G_mean | static_colour | pi_proxy | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [pad_middle__G_mean] |
| static_colour__pi_proxy__pad_middle__R_mean | static_colour | pi_proxy | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [pad_middle__R_mean] |
| static_colour__pi_proxy__pad_middle__bg | static_colour | pi_proxy | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [pad_middle__bg]: chromaticity ratio |
| static_colour__pi_proxy__pad_middle__melanin_proxy | static_colour | pi_proxy | no | no | a.u. | static colour feature from the first seconds of the clip (protocol 6.2) [pad_middle__melanin_proxy]: log(R) - log(B); a camera-space proxy, not a melanin measurement |
| static_colour__pi_proxy__pad_middle__rg | static_colour | pi_proxy | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [pad_middle__rg]: chromaticity ratio |
| static_colour__pi_proxy__pad_ring__B_mean | static_colour | pi_proxy | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [pad_ring__B_mean] |
| static_colour__pi_proxy__pad_ring__G_mean | static_colour | pi_proxy | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [pad_ring__G_mean] |
| static_colour__pi_proxy__pad_ring__R_mean | static_colour | pi_proxy | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [pad_ring__R_mean] |
| static_colour__pi_proxy__pad_ring__bg | static_colour | pi_proxy | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [pad_ring__bg]: chromaticity ratio |
| static_colour__pi_proxy__pad_ring__melanin_proxy | static_colour | pi_proxy | no | no | a.u. | static colour feature from the first seconds of the clip (protocol 6.2) [pad_ring__melanin_proxy]: log(R) - log(B); a camera-space proxy, not a melanin measurement |
| static_colour__pi_proxy__pad_ring__rg | static_colour | pi_proxy | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [pad_ring__rg]: chromaticity ratio |
| static_colour__pi_proxy__prox_index__B_mean | static_colour | pi_proxy | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [prox_index__B_mean] |
| static_colour__pi_proxy__prox_index__G_mean | static_colour | pi_proxy | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [prox_index__G_mean] |
| static_colour__pi_proxy__prox_index__R_mean | static_colour | pi_proxy | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [prox_index__R_mean] |
| static_colour__pi_proxy__prox_index__bg | static_colour | pi_proxy | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [prox_index__bg]: chromaticity ratio |
| static_colour__pi_proxy__prox_index__melanin_proxy | static_colour | pi_proxy | no | no | a.u. | static colour feature from the first seconds of the clip (protocol 6.2) [prox_index__melanin_proxy]: log(R) - log(B); a camera-space proxy, not a melanin measurement |
| static_colour__pi_proxy__prox_index__rg | static_colour | pi_proxy | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [prox_index__rg]: chromaticity ratio |
| static_colour__pi_proxy__prox_little__B_mean | static_colour | pi_proxy | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [prox_little__B_mean] |
| static_colour__pi_proxy__prox_little__G_mean | static_colour | pi_proxy | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [prox_little__G_mean] |
| static_colour__pi_proxy__prox_little__R_mean | static_colour | pi_proxy | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [prox_little__R_mean] |
| static_colour__pi_proxy__prox_little__bg | static_colour | pi_proxy | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [prox_little__bg]: chromaticity ratio |
| static_colour__pi_proxy__prox_little__melanin_proxy | static_colour | pi_proxy | no | no | a.u. | static colour feature from the first seconds of the clip (protocol 6.2) [prox_little__melanin_proxy]: log(R) - log(B); a camera-space proxy, not a melanin measurement |
| static_colour__pi_proxy__prox_little__rg | static_colour | pi_proxy | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [prox_little__rg]: chromaticity ratio |
| static_colour__pi_proxy__prox_middle__B_mean | static_colour | pi_proxy | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [prox_middle__B_mean] |
| static_colour__pi_proxy__prox_middle__G_mean | static_colour | pi_proxy | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [prox_middle__G_mean] |
| static_colour__pi_proxy__prox_middle__R_mean | static_colour | pi_proxy | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [prox_middle__R_mean] |
| static_colour__pi_proxy__prox_middle__bg | static_colour | pi_proxy | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [prox_middle__bg]: chromaticity ratio |
| static_colour__pi_proxy__prox_middle__melanin_proxy | static_colour | pi_proxy | no | no | a.u. | static colour feature from the first seconds of the clip (protocol 6.2) [prox_middle__melanin_proxy]: log(R) - log(B); a camera-space proxy, not a melanin measurement |
| static_colour__pi_proxy__prox_middle__rg | static_colour | pi_proxy | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [prox_middle__rg]: chromaticity ratio |
| static_colour__pi_proxy__prox_ring__B_mean | static_colour | pi_proxy | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [prox_ring__B_mean] |
| static_colour__pi_proxy__prox_ring__G_mean | static_colour | pi_proxy | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [prox_ring__G_mean] |
| static_colour__pi_proxy__prox_ring__R_mean | static_colour | pi_proxy | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [prox_ring__R_mean] |
| static_colour__pi_proxy__prox_ring__bg | static_colour | pi_proxy | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [prox_ring__bg]: chromaticity ratio |
| static_colour__pi_proxy__prox_ring__melanin_proxy | static_colour | pi_proxy | no | no | a.u. | static colour feature from the first seconds of the clip (protocol 6.2) [prox_ring__melanin_proxy]: log(R) - log(B); a camera-space proxy, not a melanin measurement |
| static_colour__pi_proxy__prox_ring__rg | static_colour | pi_proxy | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [prox_ring__rg]: chromaticity ratio |
| static_colour__pi_proxy__spatial_rg_variance | static_colour | pi_proxy | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [spatial_rg_variance]: dimensionless ratio or index |
| static_colour__pi_proxy__thenar__B_mean | static_colour | pi_proxy | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [thenar__B_mean] |
| static_colour__pi_proxy__thenar__G_mean | static_colour | pi_proxy | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [thenar__G_mean] |
| static_colour__pi_proxy__thenar__R_mean | static_colour | pi_proxy | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [thenar__R_mean] |
| static_colour__pi_proxy__thenar__bg | static_colour | pi_proxy | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [thenar__bg]: chromaticity ratio |
| static_colour__pi_proxy__thenar__melanin_proxy | static_colour | pi_proxy | no | no | a.u. | static colour feature from the first seconds of the clip (protocol 6.2) [thenar__melanin_proxy]: log(R) - log(B); a camera-space proxy, not a melanin measurement |
| static_colour__pi_proxy__thenar__rg | static_colour | pi_proxy | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [thenar__rg]: chromaticity ratio |
| static_colour__pi_proxy__volar_wrist__B_mean | static_colour | pi_proxy | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [volar_wrist__B_mean] |
| static_colour__pi_proxy__volar_wrist__G_mean | static_colour | pi_proxy | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [volar_wrist__G_mean] |
| static_colour__pi_proxy__volar_wrist__R_mean | static_colour | pi_proxy | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [volar_wrist__R_mean] |
| static_colour__pi_proxy__volar_wrist__bg | static_colour | pi_proxy | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [volar_wrist__bg]: chromaticity ratio |
| static_colour__pi_proxy__volar_wrist__melanin_proxy | static_colour | pi_proxy | no | no | a.u. | static colour feature from the first seconds of the clip (protocol 6.2) [volar_wrist__melanin_proxy]: log(R) - log(B); a camera-space proxy, not a melanin measurement |
| static_colour__pi_proxy__volar_wrist__rg | static_colour | pi_proxy | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [volar_wrist__rg]: chromaticity ratio |
| static_colour__pi_proxy__whole_palm__B_mean | static_colour | pi_proxy | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [whole_palm__B_mean] |
| static_colour__pi_proxy__whole_palm__G_mean | static_colour | pi_proxy | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [whole_palm__G_mean] |
| static_colour__pi_proxy__whole_palm__R_mean | static_colour | pi_proxy | no | no |  | static colour feature from the first seconds of the clip (protocol 6.2) [whole_palm__R_mean] |
| static_colour__pi_proxy__whole_palm__bg | static_colour | pi_proxy | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [whole_palm__bg]: chromaticity ratio |
| static_colour__pi_proxy__whole_palm__melanin_proxy | static_colour | pi_proxy | no | no | a.u. | static colour feature from the first seconds of the clip (protocol 6.2) [whole_palm__melanin_proxy]: log(R) - log(B); a camera-space proxy, not a melanin measurement |
| static_colour__pi_proxy__whole_palm__rg | static_colour | pi_proxy | no | no | ratio | static colour feature from the first seconds of the clip (protocol 6.2) [whole_palm__rg]: chromaticity ratio |
| sync__analysis_window_end_s | sync | any | no | no | s | analysis window end (P2 onset, D-002) |
| sync__analysis_window_start_s | sync | any | no | no | s | analysis window start |
| sync__capture_mode | sync | any | no | no |  | simultaneous\|sequential |
| sync__ecg_map_method | sync | any | yes | no | label | ECG clock map method |
| sync__ecg_offset_s | sync | any | yes | no | s | ECG native -> reference offset |
| sync__ecg_uncertainty_s | sync | any | yes | no | s | ECG map stated uncertainty |
| sync__gpio_all_ok | sync | any | no | no | bool | marker GPIO self-check passed for every edge |
| sync__grade | sync | any | yes | no | label | sync quality grade fine\|coarse\|none (section 4.4) |
| sync__p1_found | sync | any | no | no | bool | P1 detected in the Pi LED block |
| sync__p2_found | sync | any | no | no | bool | P2 detected in the Pi LED block |
| sync__phone_audio_offset_s | sync | any | no | no | s | phone audio (video time) -> reference offset |
| sync__phone_audio_residual_max_ms | sync | any | no | no | ms | beep edge residual |
| sync__phone_frame_pairing_allowed | sync | any | no | no | bool | phone frames may be paired to Pi frames |
| sync__phone_video_accepted | sync | any | no | no |  | phone LED fit accepted (D-003) |
| sync__phone_video_drift | sync | any | no | no |  | phone video clock drift (fraction) |
| sync__phone_video_offset_s | sync | any | no | no | s | phone video -> reference offset |
| sync__phone_video_residual_max_frames | sync | any | no | no | frames | phone LED edge residual |
| sync__pi_video_residual_max_frames | sync | any | no | no | frames | Pi video vs log LED edge residual |
| sync__thumb_contact_t_ref_s | sync | any | no | no | s | thumb-contact frame time |
| sync__thumb_lift_t_ref_s | sync | any | no | no | s | thumb-lift frame time near P2 |
| sync__wall_vs_thumb_disagreement_s | sync | any | yes | no | s | wall-clock vs thumb anchor |
| sync__wall_vs_thumb_flag | sync | any | yes | no | bool | disagreement above clock.wall_vs_meta_disagreement_s |
| sync__xcorr_accepted | sync | any | yes | no |  | cross-correlation acceptance rule |
| sync__xcorr_lag_s | sync | any | yes | no | s | HR cross-correlation lag (includes mean PAT) |
| sync__xcorr_margin | sync | any | yes | no |  | peak minus second-best peak |
| sync__xcorr_peak | sync | any | yes | no | r | HR cross-correlation peak |
