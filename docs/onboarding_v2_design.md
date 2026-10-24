# Onboarding app v2: two stations, quality check, recruitment targets, ECG summary

Status: design contract for the v2 build (2026-10-24). Every agent working on v2 codes against this file. Where it
says "exactly", the Python and Kotlin sides must agree byte for byte (golden fixtures pin them).

## 1. What changes for the team

* **Names stay on paper.** The app never asks for a name, phone or hospital number. The PID links the paper consent
  form to the app record. The identity screen, the identity table upload and the "remove names" setting go away.
* **Two stations, one PID.** Each participant has up to two records, called parts:
  * `enrol` (Enrol & history, about 5 minutes): consent, stream, department, age, sex, pregnancy, height, weight,
    skin tone, known conditions with short follow-ups, existing lab values, today's caffeine/meal, review.
  * `scan` (Scan station): imaged hand, arm circumference and cuff, BP1, rest timer, BP2, palm clip(s) with the
    Kardia ECG, BP3, review.
  One operator can do enrolment while the other sets up the scan. They may use two phones; records meet on the
  server by PID. A single operator can run both parts on one phone (scan part first for BP1, then the enrol part
  during the rest, then back to the scan part).
* **Quality tab.** Lists the latest phone clips and imported Kardia PDFs with an automatic grade (Good /
  Borderline / Retake) and the reasons. The grades are rule-based signal-quality checks with published
  thresholds, not a trained model; the operator decides.
* **Targets tab.** Shows how full each recruitment cell is (sex, skin tone, condition, and their key
  combinations) and a quick priority check for a person being considered: High / Medium / Low with the cells they
  would fill. Counts come from the server (all phones) plus this phone's not-yet-uploaded records.
* **Recorder fixes.** Screen kept on, auto-stop at the clip length, the file is finalised if the app is
  interrupted, double taps ignored, both permissions checked, and truncated clips are flagged by the quality check.
* **ECG summary for participants.** A one-page summary (PID, date, heart rate, the Kardia app's own
  determination as transcribed, signal quality, clinician-review status) that can be printed or shared. Research
  model outputs (ECGFounder) are for the study clinician and the research comparison only; see section 9.

## 2. Schema v2 (`configs/crf_schema.json`, schema_version `2026-10-24.1`)

### 2.1 Flow selection (both engines, exactly)

`settings.part` (default `"enrol"`) and `settings.clip_plan` (default `"1x60"`) pick the flow:
`flow_key = part if part in flows else part + "_" + clip_plan`. Unknown keys raise. Flows:

```
enrol:      pid, e_consent, e_basics, e_conditions, e_labs, e_today, e_review
scan_1x60:  pid, s_setup, bp1, bp2, clip1, clip1b, bp3, s_review
scan_2x30:  pid, s_setup, bp1, clip1, clip1b, bp2, clip2, clip2b, bp3, s_review
```

The `pid` screen (one question, `study_id`) is shared by both parts. Export adds `part` (from settings),
`schema_version`, `clip_plan` (scan part only) and the context keys (`operator`, `unit_id`, `app_ver`,
`device_code`, `capture_mode`). There is no identity export any more: `export()` returns the CRF only.
`settings_defaults` gains `part: "enrol"`, `ferritin_id_cutoff: 15`, `hba1c_dm_cutoff: 6.5`.

### 2.2 Enrol part questions (ids are contracts)

| screen | id | type | rule |
|---|---|---|---|
| pid | study_id | pid | required |
| e_consent | consent | single yes_no | required; stop_if no ("No consent: save as a screen failure"); export false |
| | stream | single stream | required; default `$settings.stream` |
| | dept | single dept | required |
| e_basics | age | integer 18-110 | required; stop_if < 18 |
| | sex | single sex (M, F, O) | required |
| | pregnant | single yes_no_unknown | show_if sex F and age 18-55; required |
| | gestational_age_weeks | decimal 4-42 | show_if pregnant yes; required |
| | trimester | computed trimester | show_if pregnant yes; export true |
| | height_cm | decimal 100-220 | required |
| | weight_kg | decimal 25-250 | required |
| | bmi | computed bmi | export true |
| | mst_band | mst 1-10 | required; warn_if < 4 ("outside the target bands 4-10") |
| e_conditions | conditions | multi conditions | required; exclusive [none] |
| | htn_meds | single htn_meds | show_if conditions contains htn; required |
| | htn_meds_today | single yes_no | show_if htn_meds in [one, two, three_plus]; required |
| | af_pattern | single af_pattern | show_if contains af; required |
| | anticoagulant | single yes_no_unknown | show_if contains af; required |
| | arrhythmia_type | single arrhythmia_type | show_if contains arrhythmia_other; required |
| | cardiac_device | single yes_no | show_if contains af, arrhythmia_other or heart_other; required |
| | dm_type | single dm_type | show_if contains diabetes; required |
| | dm_years | integer 0-80 | show_if contains diabetes; optional |
| | dm_treatment | single dm_treatment | show_if contains diabetes; required |
| | thal_type | single thal_type | show_if contains thal; required |
| | thal_transfusions | single thal_transfusions | show_if contains thal; required |
| | iron_therapy | single iron_therapy | show_if contains ida; required |
| | on_dialysis | single yes_no | show_if contains ckd; required |
| | transfusion_3m | single yes_no_unknown | required (everyone) |
| | last_transfusion_date | date | show_if transfusion_3m yes; required |
| e_labs | labs_note | info | "Copy from records only. Leave blank if not on record." |
| | hb_gdl | decimal 2-25 | optional |
| | hb_date | date | required_if hb_gdl answered |
| | rbc_mill | decimal 1-9 | show_if HAEM_DETAIL; optional |
| | mcv_fl | decimal 40-130 | show_if HAEM_DETAIL; optional |
| | mch_pg | decimal 10-45 | show_if HAEM_DETAIL; optional |
| | rdw_pct | decimal 8-35 | show_if HAEM_DETAIL; optional |
| | mentzer | computed mentzer_index | show_if HAEM_DETAIL; export true |
| | hplc_reflex | computed hplc_reflex | show_if HAEM_DETAIL; export true |
| | ferritin_ngml | decimal 1-5000 | show_if HAEM_DETAIL; optional |
| | ferritin_date | date | required_if ferritin_ngml answered |
| | hplc_result | single hplc_result | show_if contains thal or derived hplc_reflex true; optional |
| | hba2_pct | decimal 0-20 | show_if hplc_result in HPLC_DONE; optional |
| | hbf_pct | decimal 0-100 | show_if hplc_result in HPLC_DONE; optional |
| | hbe_pct | decimal 0-100 | show_if hplc_result in HPLC_DONE; optional |
| | hplc_date | date | required_if hplc_result in HPLC_DONE |
| | hba1c_pct | decimal 3-20 | optional (everyone) |
| | hba1c_date | date | required_if hba1c_pct answered |
| | anaemia_grade | computed anaemia_grade | export true |
| | haem_cell | computed haem_cell | export true |
| | dm_label | computed dm_label | export true |
| e_today | acute_30m | multi acute | required; exclusive [none] |
| | last_meal_h | decimal 0-48 | optional |
| | glucose_mgdl | decimal 20-600 | optional (nested subset, separate consent) |
| e_review | strata | computed strata | export true |
| | enrol_notes | text | optional |

`HAEM_DETAIL` = conditions contains thal, ida or anaemia_other, or derived `anaemic` is true.
`HPLC_DONE` = [normal, beta_trait, hbe_trait, hbe_beta, beta_major_intermedia, other].

Choice lists (values are contracts; labels may be reworded):

* `conditions`: htn (High blood pressure), af (Atrial fibrillation), arrhythmia_other (Other rhythm problem:
  flutter, ectopics, SVT), heart_other (Other heart disease: heart attack, angina, heart failure, valve),
  diabetes (Diabetes), thal (Thalassaemia or HbE, trait or disease), ida (Iron-deficiency anaemia),
  anaemia_other (Other or unknown-cause anaemia), ckd (Chronic kidney disease), none (None of these).
* `htn_meds`: none, one, two, three_plus, unsure.
* `af_pattern`: paroxysmal, persistent, permanent, unknown.
* `arrhythmia_type`: flutter, ectopics, svt, other, unknown.
* `dm_type`: t1, t2, other, unknown.
* `dm_treatment`: diet, tablets, insulin, tablets_insulin, none_unknown.
* `thal_type`: beta_trait, beta_major_intermedia, hbe_trait, hbe_beta, hbe_disease, other_unknown.
* `thal_transfusions`: none, occasional, regular.
* `iron_therapy`: none, oral, iv_3m, unknown.
* `hplc_result`: not_done, normal, beta_trait, hbe_trait, hbe_beta, beta_major_intermedia, other.
* `acute`: caffeine, tobacco, exercise, meal, none.
* `dept`: cardiology, medicine, endocrinology, haematology, antenatal, nephrology, general_opd, ward, other.
* `yes_no`, `yes_no_unknown`, `stream`, `sex`, `hand`, `cuff_size`: as in v1.

### 2.3 Scan part questions

| screen | id | type | rule |
|---|---|---|---|
| s_setup | imaged_hand | single hand | required; default `$settings.imaged_hand` if set |
| | arm_circumference_cm | decimal 15-55 | required |
| | cuff_suggestion | computed cuff_suggestion | |
| | cuff_size | single cuff_size | required |
| bp1 | bp1 | bp | required |
| | rest_note | info | "Rest starts now. Enrolment and history happen during the rest." |
| bp2 | rest_elapsed | computed rest_elapsed | |
| | bp2 | bp | required; warn_if derived bp1_outlier true |
| | irregular_pulse | single yes_no | required; export_as bool_yes_no |
| clip1 | clip1 | clip | required |
| clip1b | clip1b | clip | screen show_if clip1.quality fail; required |
| clip2 / clip2b | clip2 / clip2b | clip | as clip1 / clip1b (2x30 only) |
| bp3 | bp3 | bp | required; warn_if derived bracket_flag true |
| | adverse_event | text | optional |
| s_review | recovery | computed recovery | export true |
| | bracket_flag | computed bracket_flag | export true |
| | scan_strata | computed scan_strata | export true |
| | scan_notes | text | optional |

### 2.4 Clip record (value of a `clip` question)

Engine validation is unchanged: `started_at`, `ended_at` (ISO 8601 with offset) and `quality` in {pass, fail} are
required; end after start. Other keys are free-form for the engines but are contracts for the app, the server
view and the pipeline:

```
started_at, ended_at          ISO 8601 (filled by the in-app recorder, or by the Start/End buttons)
quality                       "pass" | "fail"  (operator decision; pre-filled from the grades: retake -> fail)
kardia_on, beep_heard         booleans
notes                         text
phone_file                    path relative to the app's external files dir, e.g. "visits/<visit_uuid>/clip1.mp4"
phone_duration_s              number (from the recorder / container)
phone_interrupted             boolean (recording stopped early because the app was interrupted)
video_grade                   "good" | "borderline" | "retake" | null
video_reasons                 [string]
video_metrics                 {duration_s, fps, dropped_frac, mean_level, clipped_frac, dark_frac, motion,
                               snr_db, pulse_bpm, skewness}
ecg_file                      path relative to the app's external files dir ("visits/<visit_uuid>/clip1_ecg.pdf")
ecg_grade, ecg_reasons        as for video
ecg_metrics                   {duration_s, hr_bpm, n_beats, rr_max_s, rr_ratio, template_corr, ksqi,
                               flat_frac, irregular_flag, rmssd_ratio, tpr, shannon}
kardia_determination          kardia choice value (what the Kardia app showed), see `kardia` list
kardia_hr                     integer bpm as shown by the Kardia app (optional)
```

Choice list `kardia`: nsr, af, bradycardia, tachycardia, sinus_sve, sinus_pvc, sinus_wide_qrs, unclassified,
unreadable, too_short, not_recorded (labels in plain words; final list confirmed against AliveCor docs).

### 2.5 New derivations (both engines, exactly)

All return null (None) when inputs are missing. Numbers rounded half-even to 1 decimal where noted.

* `anaemic`, `anaemia_grade`: WHO 2024 haemoglobin thresholds (g/dL) for people aged 15 and over.
  Non-pregnant female: none >= 12.0, mild 11.0-11.9, moderate 8.0-10.9, severe < 8.0.
  Male: none >= 13.0, mild 11.0-12.9, moderate 8.0-10.9, severe < 8.0.
  Pregnant, trimester 1 or 3: none >= 11.0, mild 10.0-10.9, moderate 7.0-9.9, severe < 7.0.
  Pregnant, trimester 2: none >= 10.5, mild 9.5-10.4, moderate 7.0-9.4, severe < 7.0.
  Pregnant with unknown trimester uses the trimester 1/3 cut-offs. Sex O or missing: null.
  `anaemic` = grade != "none" (null when grade is null).
* `mentzer_index` = round1(mcv_fl / rbc_mill) when both are numbers and rbc_mill > 0.
* `mentzer_pattern`: null without both; "not_microcytic" when mcv_fl >= 80; else "thal_trait_pattern" when the
  index < 13, else "iron_deficiency_pattern". Shown as a hint only; HPLC decides.
* `hplc_reflex`: true when mcv_fl < 80 or mch_pg < 27; false when at least one of them is present and neither
  condition holds; null when both are missing.
* `days_since_transfusion` = (today - last_transfusion_date) in days; `transfusion_30d` = days <= 30.
* `haem_cell`, first match wins:
  1. thal_disease: thal_type in [beta_major_intermedia, hbe_beta, hbe_disease] or hplc_result in
     [beta_major_intermedia, hbe_beta];
  2. thal_trait: thal_type in [beta_trait, hbe_trait] or hplc_result in [beta_trait, hbe_trait];
  3. thal_unspecified: conditions contains thal;
  4. ida: conditions contains ida, or anaemic is true and ferritin_ngml < settings.ferritin_id_cutoff;
  5. anaemia_other: anaemic is true, or conditions contains anaemia_other;
  6. non_anaemic: anaemic is false;
  7. null.
* `dm_label`: documented_hba1c (conditions contains diabetes and hba1c_pct >= cutoff), documented (contains
  diabetes), hba1c_only (no diabetes in conditions and hba1c_pct >= cutoff), no_known (otherwise, including no
  HbA1c). Cutoff = settings.hba1c_dm_cutoff.
* `strata` (enrol part): list of strings in this exact order, each block only when its inputs exist:
  1. `sex:<M|F|O>`
  2. `mst:<1..10>` then `mstgrp:<light|medium|dark>` (1-4 light, 5-6 medium, 7-10 dark)
  3. one `cond:<value>` per ticked condition, in the order of the `conditions` choice list (`cond:none` when none)
  4. `haem:<haem_cell>` when haem_cell is not null
  5. `dm:<dm_label>`
  6. `preg:yes` when pregnant is yes
  7. `sex_mst:<sex>:<band>` (needs both)
  8. `cond_mstgrp:<value>:<group>` per ticked condition except none (needs mst)
  9. `haem_mstgrp:<haem_cell>:<group>` (needs both)
* `scan_strata` (scan part): `rhythm:<kardia_determination>` of the last clip of clip1 / clip1b (clip1b when it
  exists and has a determination), then `scan:done` when bp3 is answered.

`bmi`, `cuff_suggestion`, `trimester`, `rest_elapsed(_s)`, `recovery`, `bracket_flag`, `bp1_outlier`,
`eligible` are unchanged. `initials` is removed.

## 3. Recruitment targets and priority

`configs/recruitment_targets.json` (defaults from the concept note; the PI must confirm the numbers):

```json
{
  "version": "2026-10-24.1",
  "note": "Defaults derived from the concept note; confirm with the PI.",
  "levels": {"high": 0.5, "medium": 0.2},
  "groups": [
    {"id": "sex", "label": "Sex", "weight": 1.0, "cells": [{"key": "sex:F", "label": "Female", "target": 1000}, ...]},
    ...
  ]
}
```

Each cell: `key` (a strata key), `label`, `target` (> 0). Each group: `id`, `label`, `weight` (0-1), `cells`.
A `scan` group may hold `rhythm:*` keys (shown on the dashboard; they never enter the enrol priority because
enrol strata never contain rhythm keys).

Priority for a candidate with strata keys K, given counts n (exactly, both languages):

```
for each group g, cell c with c.key in K:
    deficit = max(0, 1 - n[c.key] / c.target)        (n missing = 0)
    contribution = g.weight * deficit
score = max(contributions), or 0 when none
level = "none"   if no cell matched
        "met"    if cells matched and every deficit == 0
        "high"   if score >= levels.high
        "medium" if score >= levels.medium
        "low"    otherwise
reasons = matched cells sorted by contribution desc, then key asc; the first 3 as
          {key, label, group, n, target, contribution rounded to 3 decimals}
```

Counts: server function `strata_counts(p_stream)` returns `{key, n}` over submitted enrol (and legacy full)
records, counting distinct PIDs; `rhythm:*`/`scan:*` keys come from submitted scan parts. The app adds this phone's
submitted records that are not yet synced. Python: `palmppg/core/strata.py`; Kotlin: `org.samahealth.crf.Strata`.
Shared fixtures: `configs/crf_fixtures/strata_golden.json`.

## 4. Quality scoring (pure code, both languages)

Kotlin module `android/quality-core` (package `org.samahealth.quality`, plain JVM, no Android imports); Python
reference `palmppg/quality/onsite.py`; fixtures `configs/quality_fixtures/*.json` generated by Python and checked
by Kotlin tests within stated tolerances. Thresholds live in one config object per signal with documented
defaults and citations.

```kotlin
data class Grade(val level: String, val reasons: List<String>, val metrics: Map<String, Double?>)
// level: "good" | "borderline" | "retake"

class FrameStats(...)   // per-frame ROI statistics from Y/U/V planes (skin-mask ROI with whole-frame fallback)
object FrameStatsCalc { fun fromYuv(y: ByteArray, u: ByteArray, v: ByteArray, w: Int, h: Int, yRowStride: Int,
    uvRowStride: Int, uvPixelStride: Int, step: Int = 8, prevY: ByteArray? = null): FrameStats }
object VideoQuality { fun score(tS: DoubleArray, frames: List<FrameStats>, expectedSeconds: Double,
    refHrBpm: Double? = null, cfg: VideoQualityConfig = VideoQualityConfig()): Grade }
object EcgDigitiser { fun digitise(argb: IntArray, width: Int, height: Int, pxPerMm: Double,
    speedMmS: Double = 25.0, gainMmMv: Double = 10.0, fsOut: Double = 300.0): EcgTrace }
data class EcgTrace(val fs: Double, val mv: DoubleArray, val rows: Int, val warnings: List<String>)
object EcgQuality { fun score(mv: DoubleArray, fs: Double, cfg: EcgQualityConfig = EcgQualityConfig()): Grade
    fun detectQrs(mv: DoubleArray, fs: Double): IntArray }
```

The irregular-rhythm flag is a screening heuristic for clinician review, never a rhythm label.

## 5. Server (Supabase migration `0002_two_parts.sql`, applied on top of 0001)

* `visits.part` text not null default 'full', check in ('enrol', 'scan', 'full'); existing rows are 'full'.
  Unique (pid) becomes unique (pid, part). `part` is immutable like `pid`.
* `recruitment_targets(key pk, group_id, group_label, label, target > 0, weight, active, updated_at)`; read by
  authenticated users, written by admins; seeded from `configs/recruitment_targets.json` (a test checks they match).
* `strata_counts(p_stream text default null)` security definer, for active operators/admins/exporters.
* `scan_queue(p_days int default 2)`: submitted enrol parts from the last p_days days without a submitted scan
  part: pid, enrolled_at, sex, age, mst_band, conditions.
* `participant_export` view (security_invoker): one row per PID, enrol and scan parts side by side with stable,
  typed columns for every exported question (a test checks coverage), plus `enrol_json` and `scan_json`.
  `crf_export` stays for legacy rows.
* The identity table and `submit_identity` stay in place but the v2 app never calls them.

## 6. Android app v2 (package `org.samahealth.onboarding`)

* Navigation: bottom tabs **Enrol**, **Scan**, **Quality**, **Targets**; Settings and Login from the top bar.
  Settings gains "Station" (enrol / scan / both: which tab opens first) and clip plan.
* Visits: `VisitEntity` gains `part`, `settingsJson` (engine settings snapshot taken at creation; the visit's
  engine is built from it), `serverAccepted`, `everSubmitted`. Room migration 1 -> 2 adds the columns and drops
  the identity table. Saves go through one serial writer; `saveDraft` is a conditional update
  (`WHERE visitUuid = ? AND status = 'draft'`).
* Scan part PID picker: today's enrolments from `scan_queue` when online, this phone's enrol parts, or typed.
* Enrol review shows the stratum chips and the priority badge.
* Clip widget: launches the recorder with the clip length, receives start/end/duration/interrupted, runs the video
  grade, accepts a Kardia PDF (share sheet or file picker), runs the ECG grade, records the Kardia determination,
  pre-fills quality from the grades.
* Recorder: state machine (idle, settling, recording, stopping), FLAG_KEEP_SCREEN_ON, auto-stop via
  `setMaxDuration` plus `OnInfoListener`, finalise on `onPause`, both permissions checked, files under
  `visits/<visit_uuid>/`, bitrate clamped to the encoder's supported range.
* Quality tab: recent clips and ECGs with grade, reasons and metrics; re-analyse; open the visit.
* Targets tab: quick check (sex, MST, conditions -> priority), cells table with progress bars, "most needed".
* Sync: KEEP policy and a process-wide mutex; permanent errors leave the automatic queue (manual retry);
  auth failures raise a "Sign in again" banner; PID locked once the server accepted the visit; discard only for
  never-submitted drafts, with confirmation.
* ECG summary: one-page PDF (android.graphics.pdf.PdfDocument), shared through a FileProvider.

### 6.1 Internal Android contracts (file owners in brackets)

```kotlin
// [recorder] recorder/PalmRecorderActivity.kt
object RecorderContract {
    const val EXTRA_VISIT_UUID = "visit_uuid"      // files go to <externalFilesDir>/visits/<visit_uuid>/
    const val EXTRA_STUDY_ID = "study_id"          // written into <clip>_meta.json only
    const val EXTRA_CLIP_ID = "clip_id"            // clip1, clip1b, clip2, clip2b
    const val EXTRA_CAPTURE_MODE = "capture_mode"
    const val EXTRA_SECONDS = "seconds"            // Int: auto-stop length (60 for 1x60, 30 for 2x30)
    const val RESULT_REL_PATH = "rel_path"         // "visits/<visit_uuid>/<clip>.mp4"
    const val RESULT_STARTED_AT = "started_at"     // ISO 8601 with offset, first recorded frame
    const val RESULT_ENDED_AT = "ended_at"
    const val RESULT_DURATION_S = "duration_s"     // Double
    const val RESULT_INTERRUPTED = "interrupted"   // Boolean: stopped early (pause, error, user stop)
}

// [media] quality/QualityRunner.kt (uses android/quality-core)
data class VideoResult(val grade: org.samahealth.quality.Grade, val durationS: Double)
data class EcgResult(val grade: org.samahealth.quality.Grade?, val source: String, val error: String?)
object QualityRunner {
    fun appFile(context: Context, relPath: String): File            // <externalFilesDir>/<relPath>
    suspend fun gradeVideo(context: Context, file: File, expectedSeconds: Double, refHrBpm: Double? = null,
                           onProgress: (Float) -> Unit = {}): VideoResult
    suspend fun gradeEcg(context: Context, file: File): EcgResult   // PDF (PdfRenderer + digitiser) or ATC
    fun importEcg(context: Context, source: Uri, visitUuid: String, clipId: String): String   // returns rel path
}
fun Grade.toJson(): JsonObject   // {"grade","reasons","metrics"} helpers used by the clip widget

// [media] ecg/ParticipantSummary.kt
object ParticipantSummary {
    fun write(context: Context, pid: String, clip: JsonObject, clinicianReviewed: Boolean): File  // one-page PDF
    fun shareIntent(context: Context, pdf: File): Intent
}

// [media] ecg/EcgShareActivity.kt: receives ACTION_SEND (application/pdf, application/octet-stream),
// lists active scan drafts via repo.activeScanDrafts(), and on pick calls repo.addEcgInbox(...), then opens
// MainActivity on that visit (extra "open_visit").

// [data] data/Repository.kt
suspend fun activeScanDrafts(): List<VisitEntity>
suspend fun addEcgInbox(visitUuid: String, clipId: String, relPath: String)
fun observeEcgInbox(visitUuid: String): Flow<List<EcgInboxEntity>>   // the survey applies and consumes these
suspend fun consumeEcgInbox(id: Long)
```

The survey screen (the only writer of a visit's answers while it is open) applies inbox items to the clip record,
so no other component writes a visit's answers concurrently.

## 7. Pipeline side

* `palmppg crf pull` merges the parts per PID into `participants/<PID>/crf.json`: the enrol fields and scan fields
  at top level (question ids are unique across parts) and `parts: {enrol: {...context}, scan: {...context}}`.
* `palmppg/core/crf.py` covariates follow the v2 fields (conditions, haem_cell, dm_label, anaemia_grade, ...).

## 8. Recording reliability checklist (Open Camera fallback)

Kept in `palmppg/capture/phone_settings.md`: Keep display on, no maximum duration or file size, system screen
timeout at least 10 minutes on the scan phone, battery optimisation off for the recording app, enough storage.

## 9. ECG results for participants

* What participants receive at the visit: the Kardia app's own result (its FDA-cleared determination and heart
  rate) on the one-page summary, with the signal-quality grade and a note that a study clinician reviews the
  strip. Research model output is not shown to participants unless the ethics committee approves it and a
  clinician has reviewed the strip.
* Research model: ECGFounder single-lead (lead I) run offline on the analysis laptop (`palmppg ecg founder`),
  compared with the clinician read (hypothesis H6). Optional on-phone inference via ONNX Runtime when an exported
  model file is present.
