# Google Sheets and CSV export

`Code.gs` pulls the `participant_export` view (one row per PID with the enrol and scan parts side by side, no names)
into a Google Sheet, fills a `Targets` tab with recruitment-cell fill, and saves CSV snapshots to Drive. It needs
`supabase/migrations/0002_two_parts.sql` on the project.

1. Create a Google Sheet (owned by the study account). Extensions → Apps Script → replace `Code.gs` with this file.
2. Project Settings → Script properties: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `EXPORTER_EMAIL`, `EXPORTER_PASSWORD`
   (the exporter account from `supabase/README.md`), optional `CSV_FOLDER_ID` (a Drive folder for snapshots).
3. Reload the sheet → menu **SamaHealth** → **Install hourly refresh + weekly CSV** (authorise once).

Menu items: **Refresh now** rewrites the `CRF` and `Targets` tabs; **Save CSV snapshot to Drive** writes
`participant_export_YYYY-MM-DD_HHMM.csv` (the participant table) and links to it (open it in Drive and use File →
Download). The `Sync log` tab records every run. The hourly refresh keeps the free Supabase project from pausing; the
Monday 07:00 CSV is the backup.

Tabs:

* `CRF`: one row per PID. `parts` says which records exist (`enrol;scan`, `enrol`, `scan`, or `full` for a v1
  record). Per part: status, operator, device, app version, created / submitted / uploaded times. Then every exported
  question (BP readings as `bp1_sbp` ... `bp3_ts`; clips as `clip1_start`, `clip1_quality`, `clip1_video_grade`,
  `clip1_ecg_grade`, `clip1_kardia_determination`, `clip1_snr_db`, ...). Lists are joined with `;`. `enrol_json` and
  `scan_json` hold each part's full record.
* `Targets`: one row per active cell of `recruitment_targets`: key, group, label, n (distinct PIDs with a submitted
  record carrying that strata key, all streams), target, fill % (capped at 100).

Tests (mocked Google services): `node --test appscript/test/code.test.js`.
