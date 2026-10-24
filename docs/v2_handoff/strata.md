# Task: recruitment targets and priority (Python + Kotlin, shared fixtures)

Read /tmp/claude-0/-home-user-samapalm/1767d121-93b8-57dc-bbea-5d5b03c9a3eb/scratchpad/prompts/common.md first,
then docs/onboarding_v2_design.md sections 2.5 (`strata` keys) and 3 (targets and priority).

Context: the study recruits adults stratified by sex, Monk Skin Tone (MST bands 4-10, 7-10 oversampled) and
condition (cardiology: hypertension, AF, other arrhythmia; diabetes; haematology: thalassaemia trait/disease vs
iron-deficiency anaemia vs other anaemia vs non-anaemic comparator). Staff need a live priority for a candidate
(High/Medium/Low + which under-filled cells they would fill) and a dashboard of cell fill.

Files you own (create):
* configs/recruitment_targets.json - groups and cells exactly as the contract describes. Defaults (the PI will
  confirm; say so in "note"): sex F 1000, M 1000; MST bands 4..10 at 200 each (labels "MST 4".."MST 10");
  conditions: cond:htn 400, cond:af 300, cond:arrhythmia_other 150, cond:heart_other 150, cond:diabetes 400,
  haem:thal_trait 150, haem:thal_disease 60, haem:ida 150, haem:anaemia_other 100, haem:non_anaemic 300
  (one group "condition", weight 1.0); "sex_mst" group weight 0.7 with sex_mst:F:<b> and sex_mst:M:<b> at 100 each
  for b in 4..10; "condition_dark" group weight 0.7 with cond_mstgrp:<c>:dark for c in htn, af, diabetes at 120,
  and haem_mstgrp:thal_trait:dark 50, haem_mstgrp:ida:dark 50; a "scan" group weight 0 with rhythm:af 300 and
  rhythm:nsr 500 (dashboard only). levels: high 0.5, medium 0.2.
* palmppg/core/strata.py - load_targets(path=None), priority(keys, counts, targets) -> dict exactly per the
  contract (score, level, reasons[{key,label,group,n,target,contribution}]), cell_table(counts, targets) -> rows
  for a dashboard (group, key, label, n, target, fill = min(1, n/target)), most_needed(counts, targets, k=5).
  Validate the targets file (unique keys, target > 0, weight in [0,1]) with clear errors.
* tests/test_core_strata.py - hand-computed cases: no matching cell -> none; all full -> met; weighting; tie
  ordering by key; missing counts treated as 0; reasons capped at 3; contribution rounding; validation errors;
  and that every key in recruitment_targets.json is a key the schema's `strata`/`scan_strata` derivations can
  produce (check prefixes and value sets against configs/crf_schema.json choice lists: conditions, sex; MST 1-10;
  haem cells; mst groups light/medium/dark; kardia list for rhythm:*). If configs/crf_schema.json does not yet have
  the v2 choice lists (another agent is writing it), write that test so it reads the lists from the schema at run
  time and skip it with a clear reason only if the v2 lists are absent.
* tools/make_strata_fixtures.py and configs/crf_fixtures/strata_golden.json - at least 12 cases (inputs: keys,
  counts; expected output) produced by the Python implementation using the real targets file.
* android/crf-core/src/main/kotlin/org/samahealth/crf/Strata.kt - `object Strata` with
  `fun parseTargets(json: String): Targets`, `fun priority(keys: List<String>, counts: Map<String, Int>,
  targets: Targets): Priority`, `fun cellTable(...)`, `fun mostNeeded(...)`; data classes Targets, Group, Cell,
  Priority(score: Double, level: String, reasons: List<Reason>), Reason(key, label, group, n, target,
  contribution). Use kotlinx.serialization JsonObject parsing like the rest of crf-core (see Json.kt).
* android/crf-core/src/test/kotlin/org/samahealth/crf/StrataGoldenTest.kt - reads the shared fixture (see how
  CrfEngineGoldenTest locates configs/) and asserts identical output, plus a few direct unit tests.

Do not edit any other file. Run: the Python tests, `cd android && ./gradlew --offline -q :crf-core:test`, and
tests/test_core_lint.py.
