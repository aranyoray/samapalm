# Hypotheses and the CRF fields that serve them

Maps each hypothesis in the frontier-hypotheses brief (H1 to H11 plus the antenatal add-on) to the onboarding-app
fields (`configs/crf_schema.json`), the reference they need, and the experiment that reads them. Fields marked *new*
were added for the brief; the rest come from protocol section 3.1.

| hypothesis | CRF fields | reference | experiment |
|---|---|---|---|
| H1 temporal palm pulse beyond colour and priors | age, sex, height_cm, weight_kg, mst_band, bp1-bp3, recovery, bracket_flag | cuff mean (BP1 dropped when it is the outlier) | E5 four arms + pulse-shuffled control |
| H1b range-dependent error | bp1-bp3 | cuff mean, tertiles from the development stream | E3 error by reference tertile |
| H2 equity: coverage and accuracy | mst_band, ita_deg (*new*, optional) | QC validity, cuff mean | E2, E6 (frozen margins) |
| H2b melanin versus disease as the coverage driver | mst_band, ita_deg, flags, on_dialysis (*new*) | QC validity | E2 failure model |
| H3 AF versus hard non-AF controls | cohort_tags af_nested / hard_control_nested (*new*), arr_type (*new* subtypes: frequent PAC, frequent PVC, flutter, PSVT, sinus brady/tachy, paced, heart block), arr_status (*new*: present today versus history only) | clinician read of the Kardia strip (clinician.json), 12-lead where unclear | E7 |
| H4 anaemia changes the pulse and BP error | cohort_tags anaemia_nested (*new*), haem_type (*new*: beta-thal trait, thal disease, HbE, sickle, iron deficiency, other non-thal), hb_gdl + hb_date (required when anaemia is ticked), transfusion_30d, days_since_transfusion (*new*) | chart Hb with date (no new labs) | E8, E3 stratified by anaemia |
| H5 vascular age beyond age and BP | age, flags, antihtn_today, n_antihtn_drugs (*new*), egfr (*new*) | cross-sectional disease status | E9 |
| H6 foundation-model transfer | none beyond core | as H1/H3/H4 | E10 (needs weights) |
| H7 shortcut audit | operator, unit_id, dept, stream, device_code, app_ver, screen_log timestamps | n/a | E11 |
| H8 current elevated BP screening | bp1-bp3, antihtn_today | cuff mean, single visit (not confirmed hypertension) | E12 |
| H9 glucose boundary (negative expected) | glucose_mgdl (optional CBG), last_meal_h, dm_type (*new*), on_insulin (*new*), hba1c + date | CBG, chart HbA1c | E13 |
| H10 within-visit repeatability, second clip | clip plan `2x30`, clip1/clip2 (+ re-shoots) | the other clip | E14 |
| H11 CKD signature | flags, on_dialysis, egfr | chart eGFR | E15 extras |
| Antenatal add-on | cohort_tags antenatal_addon, pregnant, gestational_age_weeks, ga_source, trimester (derived), gravida, parity, hdp_status (current classification in the antenatal notes), urine_protein, anc_hb_gdl + date, anc_clinic_sbp/dbp (all *new*) | routine antenatal records, cuff | transfer test (non-pregnant model on pregnant women); cross-sectional HDP and anaemia association; trimester contrasts |

## Where the brief and the protocol differ

* **Clip plan.** The brief uses two ~30 s clips bracketed by BP readings (BP1, clip 1, BP2, clip 2, BP3); the protocol
  uses one ~60 s clip (BP1, rest, BP2, clip, BP3). The app supports both as a per-tablet setting (`clip_plan`), and
  each choice is a fixed flow in the schema. The analysis window logic already adapts to sync events (D-002).
* **Pulse arrival time.** The brief rejects PAT because the Kardia card shares no clock with the video. The protocol
  adds a frame-level sync (LED and beep markers plus the thumb-lift artefact), and the positive control measured its
  error at about 18 ms (D-020). PAT therefore stays an exploratory, ECG-requiring science-track analysis (E17) for
  clips graded `fine`, never a product feature; the brief's caution about absolute PAT values stands.
* **Antenatal add-on.** The brief places it outside the core 8,000. The app tags it (`cohort_tags`) so the add-on
  can be counted and analysed separately, and the antenatal screen appears only for pregnant women aged 18-55.
* **Arrhythmia labels.** The brief separates history of arrhythmia from rhythm present today; `arr_status` records
  that, and the clinician read of today's strip remains the rhythm reference.

Nothing in the CRF changes the pre-registered endpoints, margins or the frozen go/no-go.
