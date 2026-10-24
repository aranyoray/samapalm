# Task: schema v2 + both CRF engines + golden fixtures (+ recruitment priority)

Read $P/common.md (path: /tmp/claude-0/-home-user-samapalm/1767d121-93b8-57dc-bbea-5d5b03c9a3eb/scratchpad/prompts/common.md)
first, then docs/onboarding_v2_design.md sections 1-3 and 7 completely.

Part A - schema and engines. You own:
* configs/crf_schema.json: rewrite to v2 exactly per design sections 2.1-2.4 (schema_version "2026-10-24.1").
  Keep v1 choice values where the v2 tables say "as in v1": sex values are F, M, Other (NOT "O": use "Other"
  everywhere the design says O, including strata keys `sex:Other`); dept keeps the v1 list (Cardio OPD, Endo OPD,
  Haem OPD, Thal Day Care, ANC (OBG) ...) instead of the design's lowercase list; hand left/right with default
  "left"; cuff_size v1 values; stream v1 values. Add the new choice lists from section 2.2 and a `kardia` list
  (2.4). Labels: short plain English an operator reads aloud; help text only where it prevents an error. The
  enrol part must be fast (about 5 minutes): no question beyond the tables. Remove the identity screen, ita_deg,
  handedness, cohort_tags, antenatal details, spo2, old flags/history screens.
* palmppg/core/crf_schema.py and android/crf-core/src/main/kotlin/org/samahealth/crf/{CrfEngine.kt, Derive.kt,
  Conditions.kt, SurveyNavigator.kt, Json.kt}: flow selection by settings.part (2.1), export without identity
  (Python `export` returns only the crf dict; Kotlin `Exported` keeps a crf field; drop identity/initials; update
  SurveyNavigator and every caller inside crf-core), export keys `part`, `clip_plan` (scan only), new derivations
  (2.5) with identical results in both languages, lint updates (known derivations, flows per part). Derived
  values must be computed on the effective answers so far, as today.
* tools/make_crf_fixtures.py + configs/crf_fixtures/golden.json: regenerate with >= 24 cases covering both parts
  and both clip plans: each derivation's edge cases (WHO grade boundaries incl. pregnancy trimesters, Mentzer
  pattern at MCV 80 and index 13, hplc_reflex with one missing input, haem_cell precedence, dm_label, transfusion
  days, strata ordering incl. cross keys, scan_strata with clip1b), branch switches dropping stale answers,
  stop rules, required_if, exclusive none.
* tests/test_core_crf_schema.py, android/crf-core/src/test/kotlin/org/samahealth/crf/{CrfEngineGoldenTest.kt,
  CoreUnitTest.kt}: update; keep tests meaningful.
* palmppg/core/crf.py (+ its existing tests, find them with grep): covariates for v2 fields (cond_* flags from
  `conditions`, haem_cell, dm_label, anaemia_grade, mentzer_index, hplc fields, htn_meds, dm_treatment, ...). It
  must read a merged per-PID crf.json (enrol + scan fields at top level, see design section 7) and still read old
  v1 crf.json files (keep v1 field handling where cheap). Run the whole pytest suite at the end because other
  pipeline modules read crf.json (fix anything you broke in files that read CRF fields; list them).
* CONTRACTS.md section 9 and the crf.json section 3.7: update the text for v2 (only those sections).

Part B - recruitment targets and priority: do everything in
/tmp/claude-0/-home-user-samapalm/1767d121-93b8-57dc-bbea-5d5b03c9a3eb/scratchpad/prompts/strata.md (you own
those files too).

Not yours: the Android app module, SupabaseClient.kt, supabase/, appscript/, palmppg/capture/crf_pull.py,
android/quality-core. Run: full pytest, `cd android && ./gradlew --offline -q :crf-core:test`, lint test.
