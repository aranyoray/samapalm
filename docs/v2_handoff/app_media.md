# Task: Android app - quality runner, MP4 reader, Kardia import, participant ECG summary (media side)

Read /tmp/claude-0/-home-user-samapalm/1767d121-93b8-57dc-bbea-5d5b03c9a3eb/scratchpad/prompts/common.md and
the compile harness README (scratchpad/kc/README.txt) first, then docs/onboarding_v2_design.md fully (sections 4,
6, 6.1 and 9 are yours), the quality-core module (android/quality-core, its public API and tests), the recorder
(android/app/.../recorder/PalmRecorderActivity.kt: what files it writes under <externalFilesDir>/<PID>/), and the
existing app code (App.kt, data/, ui/SurveyScreen.kt) to match style. Another agent (app_data_ui) rewrites data/,
sync/, ui/ and App.kt at the same time and calls your API exactly as section 6.1 defines it.

You own (create or edit only these):
* android/app/build.gradle.kts: add implementation(project(":quality-core")); copy configs/recruitment_targets.json
  into the generated assets next to crf_schema.json (extend the existing copy task); nothing else.
* android/app/src/main/AndroidManifest.xml: register ecg.EcgShareActivity (exported, ACTION_SEND for
  application/pdf and application/octet-stream, label "Attach to SamaHealth visit"), a FileProvider
  (androidx.core.content.FileProvider, authority "${applicationId}.files", res/xml/file_paths.xml covering the
  external files dir and cache), android:dataExtractionRules + android:fullBackupContent pointing at XML that
  excludes everything (res/xml/data_extraction_rules.xml, res/xml/backup_rules.xml). Keep existing entries.
* android/app/src/main/res/xml/*.xml (the three files above).
* quality/QualityRunner.kt: exactly the 6.1 API (appFile, gradeVideo, gradeEcg, importEcg, gradeClip,
  Grade.toJson, data classes VideoResult, EcgResult, ClipGrades). gradeClip reads <PID>/<clip>_roi.csv,
  _frames.csv, _ecg_samples.csv (or the imported <clip>_kardia.pdf/.atc when present and no BLE samples), uses
  the ECG heart rate as refHr for the video SNR, returns both grades + RhythmSummary + notes ("No ROI log: the clip
  was recorded outside the app" etc.). All file work on Dispatchers.IO; never crash on a missing/odd file.
* quality/Mp4Roi.kt: external MP4 -> RoiSeries with MediaExtractor + MediaCodec (ByteBuffer mode,
  getOutputImage, YUV_420_888 planes with strides, centred ROI = recorder's ROI_FRACTION 0.40, subsample every
  4th pixel, BT.601 limited-range to RGB, clip fraction Y>=250, presentation time -> seconds), progress callback,
  handles rotation-agnostic geometry; used by gradeVideo.
* ecg/ParticipantSummary.kt: one-page A4 PDF with android.graphics.pdf.PdfDocument: title "Your heart recording
  (research study)", PID, date, heart rate, the RhythmSummary sentences, the Kardia app's own determination if
  the clip record has kardia_determination (label it as the Kardia app's result), signal quality in plain words,
  clinician-review status line, and a fixed disclaimer ("This is not a medical result... speak to a doctor if you have
  symptoms"). Optional Bengali line is welcome if the default typeface renders it; keep English authoritative.
  shareIntent via FileProvider (ACTION_SEND application/pdf, FLAG_GRANT_READ_URI_PERMISSION).
* ecg/EcgShareActivity.kt: plain Activity or ComponentActivity with a simple Compose list: shows active scan
  drafts from `context.container.repo.activeScanDrafts()` with their PID and the clip slots (clip1, clip1b,
  clip2, clip2b); on pick: QualityRunner.importEcg(...) then repo.addEcgInbox(visitUuid, clipId, relPath), then
  startActivity(MainActivity with extra "open_visit" = visitUuid) and finish. If the repo methods are not present
  yet when you compile (the other agent is writing them), add them to a temporary file
  quality/RepoContractShim.kt as extension functions with TODO bodies so you can compile, and list that file in
  your report; the lead will delete the shim when integrating.
* AndroidX stubs for the compile harness if you need them (scratchpad/stubs/java/androidx/core/content/
  FileProvider.java etc.): signature-accurate, minimal.
* android/app/src/test/java/org/samahealth/onboarding/quality/*Test.kt: JVM unit tests for any pure logic you
  add (YUV->RGB maths, ROI geometry) - they run in CI with junit4 (already a testImplementation).

Run the compile harness until it reports no errors in your files (errors in the other agent's in-progress files:
report, do not edit). Run `cd android && ./gradlew --offline -q :quality-core:test :crf-core:test`.
