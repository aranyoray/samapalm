# Onboarding v2: where the work stands (2026-10-24)

Branch `wip/onboarding-v2`, merged to `master` once CI is green. Read `docs/onboarding_v2_design.md` first.

## Done
* **Schema v2 and both CRF engines**: two parts (enrol/scan), no names, condition modules, WHO 2024 anaemia
  grade, Mentzer, HPLC reflex, haem cell, diabetes label, strata keys, golden fixtures.
* **Recruitment targets and priority**: `configs/recruitment_targets.json` (DEFAULTS: the PI must still confirm
  the numbers), `palmppg/core/strata.py`, `crf-core/Strata.kt`, shared fixtures.
* **Supabase `0002_two_parts.sql`**: parts, unique (pid, part), recruitment_targets, strata_counts, scan_queue,
  participant_export; Apps Script reads participant_export and the Targets sheet; `crf pull` merges parts, and
  a test checks the merged record validates and derives.
* **quality-core**: the grades and readers, plus `KardiaPdf`, a pure-Kotlin reader of the vector trace in a
  Kardia PDF export. Python and Kotlin agree to 1e-9 relative on the shared fixtures, and the PDF to 1e-12.
  46 Python tests, 29 Kotlin.
* **Android app v2**: Enrol | Scan | Quality | Targets tabs; two parts per PID with the scan started from an
  enrolled PID; Room 1 -> 2 migration (v1 rows survive as the legacy part "full", read-only but still
  uploadable; the identity table and its names are dropped); one serial writer for every visit write;
  conditional autosave; sync fixes (KEEP policy, process-wide mutex, rejected rows leave the automatic queue,
  "Sign in again" banner); clip grades after each clip with Kardia import and the share-sheet inbox; the
  participant ECG summary PDF; the enrol priority badge. 33 JVM tests.
* **ECGFounder on the phone**: `palmppg/ecg/founder_prep.py` (the chain, torch-free), `android/ecg-model` (the
  Kotlin port, checked against golden fixtures), `FounderOnnx` (ONNX Runtime Android, model file optional),
  shown only as a research pre-read in the Quality tab. The ONNX export was checked against the **real**
  weights: ONNX Runtime matches torch to 2.1e-6.
* **CI**: `:quality-core:test`, `:ecg-model:test` and the app JVM tests run on every push, plus the Python
  quality, strata and lint tests. A `model` job (manual, `build_model: true`) downloads the weights, exports
  and builds an APK with the model in it.

## Still open
1. **The PI must confirm the recruitment target numbers** in `configs/recruitment_targets.json`. They are
   defaults taken from the concept note, and the Targets tab presents them as if they were agreed.
2. **The quality thresholds are PROVISIONAL** (`VideoQualityConfig`, `EcgQualityConfig`), to be calibrated on
   pilot clips as DECISIONS D-008 says. They have only been exercised on synthetic signals.
3. **Not yet run on a participant**: the app installs and runs on the OnePlus 12, but the camera, the Kardia
   and the full two-station flow have not been exercised hands-on. That is the next thing to do.
4. **The scan station's "Do enrolment for this PID now"** shortcut from the BP1 screen (design section 6) is
   not built; a single operator can still run both parts by switching tabs.
5. **The Kardia PDF reader has only been checked against a synthetic export.** Point it at a real Kardia PDF
   before relying on it; it reports what it assumed in `warnings`.
6. **Known test failures on macOS only** (all of them fail on `master` too, and all are environment, not code):
   `test_capture_pi.py` and `test_capture_sync_marker.py` need Linux's `time.CLOCK_BOOTTIME`;
   `test_capture_offload.py` needs GNU rsync (`--info=progress2`); `test_pulse_run.py` recovers 85.6 bpm
   instead of 72 on arm64. They pass, or are expected to pass, on the Linux CI image.
7. **Do not install torch into the main virtual environment on macOS.** It deadlocks lightgbm inside
   `LGBM_DatasetCreateFromMat` (duelling OpenMP runtimes), which hangs `pytest tests/` part way through. Use a
   separate environment for the ECGFounder work; `palmppg/ecg/founder_prep.py` and the fixtures need no torch.

## Tooling
* `python tools/make_quality_fixtures.py` and `python tools/make_founder_fixtures.py` regenerate the shared
  fixtures; both test suites then check against them.
* `cd android && ./gradlew :app:assembleDebug` on a machine with the Android SDK. `compile_app.sh` here is the
  older SDK-free compile check and is no longer needed when the SDK is present.
* The ECGFounder weights are 370 MB and the exported graph 123 MB: neither is in the repository.
