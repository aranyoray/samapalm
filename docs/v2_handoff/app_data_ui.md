# Task: Android app - two stations, data layer, sync fixes, survey, Quality and Targets tabs (UI side)

Read /tmp/claude-0/-home-user-samapalm/1767d121-93b8-57dc-bbea-5d5b03c9a3eb/scratchpad/prompts/common.md and
the compile harness README (scratchpad/kc/README.txt) first, then docs/onboarding_v2_design.md fully (sections 1,
2, 3, 6 and 6.1), configs/crf_schema.json (v2), configs/recruitment_targets.json, crf-core (CrfEngine,
SurveyNavigator, Strata, SupabaseClient), quality-core's public API, and ALL current app code
(android/app/src/main/java/org/samahealth/onboarding/**) - you are rewriting most of it. Another agent
(app_media) writes quality/QualityRunner.kt, quality/Mp4Roi.kt, ecg/ParticipantSummary.kt, ecg/EcgShareActivity.kt,
the manifest, res/xml and app/build.gradle.kts at the same time; call its API exactly as section 6.1 defines it.

Users: two research staff at a Kolkata hospital. One enrols and takes history (~5 min) while the other sets up the
palm scan; sometimes one person does both on one phone. Names stay on paper (no name/phone/hospital number in the
app any more). Data goes to Supabase and from there to a Google Sheet.

You own: App.kt, data/**, sync/**, ui/** (all screens), and android/app/src/test/** for your logic. Not the
recorder package except reading its companion constants.

Required behaviour:
1. Stations: bottom navigation tabs Enrol | Scan | Quality | Targets; top bar to Settings/Login. Settings: station
   (enrol/scan/both: chooses the start tab and whether "Next PID" is offered: only enrol or both), clip plan,
   existing server settings. Remove identity (screen, table use, purge setting, identity upload).
2. Visits per part: VisitEntity gains part ("enrol"/"scan"), settingsJson (engine settings snapshot at creation,
   incl. part and clip_plan: the visit's engine is always built from it), serverAccepted, everSubmitted; new
   EcgInboxEntity(id, visitUuid, clipId, relPath, createdAt, consumed). Room version 2 with a real Migration(1,2)
   (add columns, create inbox table, DROP the identity table) - phones may hold un-uploaded v1 visits: v1 rows
   become part "full" and keep working (their engine settings fall back to the v1 flow if the v2 schema lacks it:
   simplest correct choice is to show them read-only with upload still possible; say what you chose).
3. Repository: the 6.1 methods; saveDraft as a conditional UPDATE (WHERE visitUuid = ? AND status = 'draft');
   one serial writer (a Mutex or a single-thread dispatcher) for all visit writes including submit; submit takes
   the answers snapshot built on the main thread; markSync conditional (skip if the row changed during upload);
   discard only for never-submitted drafts, with a confirmation dialog naming the PID; PID read-only once the
   server accepted the visit; a screen failure needs a valid PID before it can be saved.
4. Sync: payload with part; unique work with ExistingWorkPolicy.KEEP and a process-wide Mutex; 'error' rows leave
   the automatic queue (Home shows them with "Retry upload"); SupabaseClient's AuthFailedException -> persistent
   "Sign in again" banner + no endless retry; the online duplicate-PID check refreshes the token first and keeps
   its warning on screen until the PID changes.
5. Survey: keep the screen on for scan-part visits (window FLAG_KEEP_SCREEN_ON while the survey is shown); scan
   part PID picker: today's enrolments without a scan (SupabaseClient.scanQueue when online, cached) plus this
   phone's enrol parts, or type it (warn if not found, never block); in station "both", the scan visit's BP1 screen
   offers "Do enrolment for this PID now" (opens/creates the enrol part with the PID filled, returns afterwards).
   Enrol review screen: stratum chips (from the `strata` derived value) and the priority badge (Strata.priority
   with server counts + this phone's unsynced submitted enrol parts; targets from the server cache or the bundled
   asset recruitment_targets.json).
   Clip widget: launch PalmRecorderActivity with EXTRA_SECONDS (30 for 2x30 else 60), EXTRA_STUDY_ID,
   EXTRA_CLIP_ID, EXTRA_CAPTURE_MODE; on result store phone_file, started_at, ended_at, phone_duration_s,
   phone_interrupted, ecg_samples, ecg_seconds (keep the logic already there), then run QualityRunner.gradeClip
   and store video_grade/video_reasons/video_metrics, ecg_grade/ecg_reasons/ecg_metrics, ecg_file/ecg_source,
   pre-select quality (retake or interrupted -> fail, else pass; operator can change); show both grades with
   reasons in plain words; "Import Kardia ECG" (system file picker ACTION_OPEN_DOCUMENT pdf/octet-stream ->
   QualityRunner.importEcg + grade); apply and consume EcgInbox items for this visit; kardia_determination picker
   (schema `kardia` list) and kardia_hr; "ECG summary for participant" button -> ParticipantSummary.write +
   shareIntent. Manual Start/End buttons stay as a fallback when the in-app recorder is not used.
6. Quality tab: newest-first list of clips from this phone's scan visits (PID, clip, time, video grade, ECG grade,
   duration, interrupted), tap -> detail with reasons/metrics + "Re-analyse" + "Open visit"; "Check a video from
   the phone" (picker -> QualityRunner.gradeVideo with progress) and "Check an ECG file" (picker -> gradeEcg),
   results shown, not stored.
7. Targets tab: quick priority check (sex, MST band swatches, condition chips -> build a partial answers map ->
   derive strata with the crf-core engine (v2 enrol settings) -> Strata.priority) showing High/Medium/Low/Met with
   the top reasons; a table of cells by group with n/target and progress bars; "Most needed now"; refresh from the
   server (strataCounts + targets) with the last-updated time; works offline from cache.
8. Keep the existing working pieces (login, settings, autosave, PID blocks, read-only after submit, review summary,
   MST swatches, BP widget, text inputs that follow external changes).

Compile with the harness until clean (errors in app_media's in-progress files: report, do not edit; if its API is
missing when you compile, add temporary extension shims in ui/MediaContractShim.kt and list the file). Add JVM
tests for pure logic (e.g. building quick-check answers, priority inputs, migration SQL strings). Run
`cd android && ./gradlew --offline -q :crf-core:test :quality-core:test`.
