# Google Sheets and CSV export

`Code.gs` pulls the `crf_export` view (one flat row per visit, no names) into a Google Sheet and saves CSV
snapshots to Drive.

1. Create a Google Sheet (owned by the study account). Extensions → Apps Script → replace `Code.gs` with this file.
2. Project Settings → Script properties: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `EXPORTER_EMAIL`, `EXPORTER_PASSWORD`
   (the exporter account from `supabase/README.md`), optional `CSV_FOLDER_ID` (a Drive folder for snapshots).
3. Reload the sheet → menu **SamaHealth** → **Install hourly refresh + weekly CSV** (authorise once).

Menu items: **Refresh now** rewrites the `CRF` tab; **Save CSV snapshot to Drive** writes
`crf_export_YYYY-MM-DD_HHMM.csv` and links to it (open it in Drive and use File → Download). The `Sync log` tab
records every run. The hourly refresh keeps the free Supabase project from pausing; the Monday 07:00 CSV is the backup.

Tests (mocked Google services): `node --test appscript/test/code.test.js`.
