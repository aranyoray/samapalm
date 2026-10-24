# Onboarding v2: where the work stopped (2026-10-24)

Branch `wip/onboarding-v2`. `master` holds only the finished, CI-green part (design doc + recorder fix 8dee245).

## Done on this branch
* Design contract: `docs/onboarding_v2_design.md` (read first).
* Schema v2 + both CRF engines (two parts enrol/scan, no names, condition modules, WHO 2024 anaemia grade,
  Mentzer, HPLC reflex, haem cell, diabetes label, strata keys) + golden fixtures. Recruitment targets and priority
  (`configs/recruitment_targets.json`, `palmppg/core/strata.py`, `crf-core/Strata.kt`, shared fixtures).
  Targets are DEFAULTS: the PI must confirm the numbers.
* Supabase `0002_two_parts.sql` (parts, unique (pid, part), recruitment_targets, strata_counts, scan_queue,
  participant_export), tests on local Postgres; Apps Script reads participant_export + Targets sheet; `crf pull`
  merges parts; `SupabaseClient` new calls (strataCounts, scanQueue, targets, AuthFailedException).
* ECGFounder single-lead runner `palmppg/ecg/founder.py`, CLI `palmppg ecg founder`, ONNX export
  `tools/export_ecgfounder_onnx.py` (Concat pad fix), `docs/ecg_model.md`, tests on random weights.
* Tests at pause: crf-core and quality-core Gradle tests pass; schema, strata, supabase, crf pull, lint, founder
  pytest files pass. Full pytest not re-run at the pause (2 known failures in tests/test_capture_pi.py come from
  master's 50 Hz exposure change d881359: expectation 8000 vs 10000 us).

## Not finished
1. quality-core (agent stopped mid-way): `android/quality-core/src/main/.../{Dsp,EcgQuality,Readers,Types,
   VideoQuality}.kt` and `palmppg/quality/onsite.py` exist but are unreviewed; missing: Kotlin tests, Python
   tests (`tests/test_quality_onsite.py`), fixtures (`tools/make_quality_fixtures.py`,
   `configs/quality_fixtures/`), `KardiaPdf` vector reader. Brief: `quality.md` here.
2. `palmppg/core/crf.py` v2 covariates: check against the engine brief (`engine.md`) and that `crf pull`'s
   merged v2 records validate (operator/unit_id now under `parts.<part>`).
3. Android app (not started): `app_media.md` and `app_data_ui.md` briefs. Two call sites break against the new
   SupabaseClient: `app/.../sync/SyncWorker.kt` (VisitPayload.part) and `app/.../ui/SurveyViewModel.kt`
   (pidTakenElsewhere now takes part). Apply the review findings listed in the design doc section 6.
4. ECGFounder on the phone (requested): ONNX Runtime Android (`com.microsoft.onnxruntime:onnxruntime-android`,
   Maven Central) rather than TFLite. A GitHub Actions job downloads `1_lead_ECGFounder.pth` from HuggingFace
   (blocked in the cloud sandbox), runs the export tool, checks torch vs ORT, and packages the ~123 MB ONNX into
   the APK assets. Port the preprocessing (300->500 Hz resample_poly(5,3), 50 Hz notch Q30, Butterworth 0.67-40 Hz
   filtfilt, 0.4 s median subtraction, per-window z-score, polarity) to Kotlin with Python golden fixtures
   (strip in -> model input and probabilities out); three 10 s windows, mean for rhythms, max for ectopy. Show it
   as a research pre-read for the study clinician only; the graph contains Einsum (keep it in any reduced ORT build).
5. CI: add `:quality-core:test` and the ECGFounder job to `.github/workflows/onboarding.yml`; build until green.
6. Docs: README/DECISIONS/CONTRACTS entries for v2, staff field guide (two-station workflow, priority badge,
   quality tab, ECG summary).

## Tooling
* `compile_app.sh` + `README.txt` + `stubs/`: local compile check for the app without the Android SDK, using
  Robolectric's `org.robolectric:android-all:15-robolectric-13954326` jar from Maven Central as the framework
  classpath plus AndroidX stubs and Compose desktop 1.7.1 jars. Paths inside point at the old sandbox; edit
  `S=` to your copy. On a machine with the Android SDK, just run `./gradlew :app:assembleDebug`.
* Briefs (`common.md`, `engine.md`, `strata.md`, `quality.md`, `backend.md`, `ecgmodel.md`, `app_media.md`,
  `app_data_ui.md`) refer to `/tmp/.../scratchpad/prompts/`; read them from this folder instead.
