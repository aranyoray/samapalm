# SamaHealth onboarding app (SWHT-PP-003)

Android tablet/phone app that runs the visit CRF as a conditional survey, works offline, and uploads to Supabase.
The survey is not hard-coded: every screen, question, branch and validation rule comes from
`configs/crf_schema.json`, the same file the Python pipeline reads. A change to the CRF is a change to that file plus a
regenerated fixture set (`python tools/make_crf_fixtures.py`); the app picks it up at the next build.

## What the operator sees

Sign in (one account per operator) → participant list with upload status → **New participant** →

| flow `1x60` (protocol) | flow `2x30` (two short clips) |
|---|---|
| Enrolment (PID, consent, stream, department, cohort tags, hand) | same |
| Identity (name, hospital reg no, phone), stored apart from the CRF | same |
| BP1 on seating, rest timer starts | same |
| Demographics → antenatal screen only for women 18-55 who are pregnant | same |
| Skin tone (MST swatches, optional ITA) | same |
| History with branches (hypertension, diabetes, CKD, arrhythmia type and status, anaemia/haemoglobinopathy type, transfusion) | same |
| Chart values (Hb, HbA1c, required when the matching condition is ticked), last 30 min, optional CBG and SpO2 | same |
| BP2 with live "time since BP1" | Clip 1 (re-shoot screen only if it failed) |
| Clip 1 (Kardia on, beeps heard, quality; re-shoot once) | BP2, then Clip 2 (re-shoot once) |
| BP3 with the bracket flag | same |
| Review: problems per screen with Edit links, flags, Submit | same |

No consent or age under 18 stops the flow; the visit can be saved as a screen failure (it counts in the STARD flow).
Next moves only when the screen is clean; Back is always allowed; drafts autosave and reopen where they were left.

## Data handling

* Name, registration number and phone live in a separate local table and a separate server table (`identity`).
  The CRF uploaded to `visits` never contains them (the server rejects a CRF that does). Operators can create identity
  rows but cannot read them back; only admins can. With "Remove names after upload" on (default), names are deleted
  from the tablet once the server has them.
* Each visit has a tablet-generated `visit_uuid`, so retried uploads never duplicate. The CRF is uploaded first; the
  identity record only after the server accepted the CRF, so a PID clash can never attach a name to someone else.
* PIDs: each tablet owns a block (Settings), so tablets offline at the same time cannot collide; typed or scanned
  folder labels also work. The server's unique PID constraint is the final check; a clash shows as
  "PID already used on server" and the visit can be re-opened to fix it.
* Settings and the session are stored with EncryptedSharedPreferences (Android Keystore).

## Build

```
cd android
./gradlew :crf-core:test          # shared engine + Supabase client tests, any JVM (no Android SDK needed)
./gradlew :app:assembleDebug      # needs the Android SDK (Android Studio sets local.properties sdk.dir)
```

`:app` is included only when an Android SDK is configured, and the Android Gradle plugin is put on the build
classpath only then, so `:crf-core` builds anywhere. GitHub Actions (`.github/workflows/onboarding.yml`) builds the
APK on every push and attaches it as the `samahealth-onboarding-debug-apk` artifact.

Install: download the artifact, copy `app-debug.apk` to the tablet and open it (allow installs from this source).

## First run on each tablet (study admin)

Settings: Supabase project URL and anon key, device code (as entered in the `devices` table), PID block, unit id,
clip plan (`1x60` or `2x30`), seated rest in seconds (default 300), default stream, capture mode, name purge.
Then sign in with the operator's account.

## Phone clip

Each clip screen can launch the built-in Camera2 recorder (1080p30, H.264, audio on, AE/AWB/AF locked after the
settle, stabilisation off, per-frame SENSOR_TIMESTAMP log). Files go to
`Android/data/org.samahealth.onboarding/files/<PID>/`. The recorder must pass the bench acceptance (protocol 4.5)
before study use; Open Camera remains the fallback (`palmppg/capture/phone_settings.md`).

Pressing REC starts the Kardia capture first and holds for a 10 s lead-in, spent metering the palm, before the
encoder opens; the ECG keeps running for 10 s after the clip ends. The clip is therefore a window inside a longer
ECG record, and `<clip>_sync.json` says where (D-040). One beep marks the clip starting and a double beep marks it
finishing, both outside the recorded audio so neither is mistaken for the rig buzzer (D-042). `Nudge Kardia` pokes
a device that has gone quiet without waiting for the watchdog, escalating a rung each press: re-send the mode, try
the other mode, re-subscribe, reconnect (D-041).

## Layout

```
crf-core/   pure Kotlin: CrfEngine (schema engine), SurveyNavigator, PidAllocator, SupabaseClient (+ tests)
app/        Compose UI, Room (visits, identity), WorkManager SyncWorker, Settings, PalmRecorderActivity
```
