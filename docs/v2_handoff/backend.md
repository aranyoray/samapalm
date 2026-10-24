# Task: server and export for two-part records (Supabase 0002, Apps Script, crf pull, SupabaseClient)

Read /tmp/claude-0/-home-user-samapalm/1767d121-93b8-57dc-bbea-5d5b03c9a3eb/scratchpad/prompts/common.md first,
then docs/onboarding_v2_design.md (all of sections 2, 3, 5, 7), then the existing supabase/migrations/0001_init.sql,
supabase/tests/local_auth_stub.sql, tests/test_supabase_schema.py (how a local Postgres is started and RLS is
tested), appscript/Code.gs + appscript/test/code.test.js + tests/test_appscript_exporter.py,
palmppg/capture/crf_pull.py + tests/test_capture_crf_pull.py, android/crf-core/.../SupabaseClient.kt +
SupabaseClientTest.kt, supabase/README.md, appscript/README.md.

Context: names stay on paper; the app sends one record per part (enrol, scan) per PID; the Google Sheet must show
one row per PID with both parts side by side, plus a Targets sheet (cell fill vs targets); the scan phone needs a
list of today's enrolments without a scan; the Targets tab needs server-wide strata counts. A free Supabase
project, about 2,000 participants, 5-6 operator accounts.

You own:
* supabase/migrations/0002_two_parts.sql: idempotent where reasonable, applied after 0001 on a database that may
  already hold v1 rows. Exactly per design section 5: visits.part ('enrol','scan','full', existing rows 'full'),
  unique (pid, part) replacing unique (pid), part immutable in visits_guard, crf_pid_matches kept; table
  recruitment_targets seeded from configs/recruitment_targets.json (another agent is writing that JSON now: read it
  if present, else follow the design's section 3 and the defaults in
  /tmp/claude-0/-home-user-samapalm/1767d121-93b8-57dc-bbea-5d5b03c9a3eb/scratchpad/prompts/strata.md; add a test
  that the seed equals the JSON); functions strata_counts(p_stream text default null) and scan_queue(p_days int
  default 2), security definer, search_path pinned, executable by active operators/admins/exporters only;
  view participant_export (security_invoker) with stable typed columns for every exported question of both parts
  of the v2 schema (design 2.2-2.4; clip columns: start, end, quality, video_grade, ecg_grade, ecg_samples,
  kardia_determination, phone_duration_s, phone_interrupted, and the key metrics snr_db/pulse_bpm/hr_bpm), list
  columns joined with ';', plus enrol_json and scan_json, statuses and upload times per part; grants; RLS on the
  new table. Keep crf_export working for legacy rows.
* supabase/tests/* and tests/test_supabase_schema.py: extend: parts can coexist per PID, duplicate (pid, part)
  rejected with 23505, part immutable, strata_counts counts distinct PIDs of submitted enrol parts (drafts and
  screen failures excluded; scan keys from scan parts), scan_queue excludes PIDs with a submitted scan, exporter
  can read participant_export but not write, anon gets nothing, the coverage test: every exported question id in
  configs/crf_schema.json (v2, being written by another agent; if it is still v1 when you run, test against the
  design tables and re-run at the end) has a participant_export column.
* appscript/Code.gs (+ tests): read participant_export instead of crf_export (VIEW constant), add a "Targets"
  sheet: recruitment_targets joined with strata_counts (key, group, label, n, target, fill %), refreshed with the
  data; keep hourly refresh + weekly CSV; update appscript/README.md.
* palmppg/capture/crf_pull.py (+ tests): fetch visits with part; merge per PID into participants/<PID>/crf.json
  as design section 7 says (enrol fields and scan fields at top level, `parts: {enrol: {...}, scan: {...}}` holding
  each part's context keys: part, operator, unit_id, app_ver, device_code, capture_mode, schema_version,
  status, submitted_at); legacy 'full' rows unchanged; screen failures still go to onboarding/screen_failures.csv.
* android/crf-core/src/main/kotlin/org/samahealth/crf/SupabaseClient.kt (+ SupabaseClientTest.kt): VisitPayload
  gains `part`; duplicate detection for (pid, part); new calls strataCounts(token, stream: String?): Map<String,
  Int>, scanQueue(token, days: Int): List<ScanQueueItem(pid, enrolledAt, sex, age, mstBand, conditions)>,
  targets(token): String? (raw JSON array of recruitment_targets rows), pidTakenElsewhere(token, pid, part,
  visitUuid); refresh() must distinguish an auth failure (HTTP 400/401 invalid_grant -> throw AuthFailedException)
  from network trouble (IOException), and the SyncResult mapping stays. Keep submitIdentity but mark it unused by
  v2 in a comment.
* supabase/README.md: how to apply 0002 on an existing project, and on a fresh one (0001 then 0002).

Not yours: configs/crf_schema.json, palmppg/core/*, the app module, quality-core. Run your tests, the lint test,
and `cd android && ./gradlew --offline -q :crf-core:test` (another agent edits other crf-core files at the same
time; if their in-progress files break compilation, report it rather than editing their files).
