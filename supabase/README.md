# Supabase backend for the onboarding app

One free Supabase project holds the study's CRFs: 2,000 participants need roughly 20 MB of the free plan's 500 MB
database. Free projects pause after 7 days without activity and have no automatic backups; the hourly Google Sheets
refresh (`appscript/`) keeps the project active and its weekly CSV snapshot in Drive is the off-site backup.
`palmppg crf pull` also writes a CSV snapshot on every pull.

## Set up (about 15 minutes)

1. Create a project at supabase.com (region: Mumbai, `ap-south-1`). Note the project URL and the anon key
   (Project Settings → API).
2. SQL editor → paste `migrations/0001_init.sql` → Run; then paste `migrations/0002_two_parts.sql` → Run (always in
   this order: 0002 changes tables that 0001 creates).
3. Authentication → Providers: keep Email on; turn off "Allow new users to sign up" so only accounts you create exist.
4. Authentication → Users → Add user, once per person (operators, one admin, one exporter for Sheets and the pipeline).
5. SQL editor, once per account (copy each user id from the Users page):
   ```sql
   insert into public.operators (user_id, operator_code, display_name, role) values
     ('<uuid>', 'op1', 'Operator one', 'operator'),
     ('<uuid>', 'adm', 'Study admin', 'admin'),
     ('<uuid>', 'exp', 'Sheets and pipeline export', 'exporter');
   insert into public.devices (device_code, unit_id, pid_block_start, pid_block_end, next_pid) values
     ('tab-A', 'unit_01', 1, 999, 1),
     ('tab-B', 'unit_01', 1000, 1999, 1000);
   ```
6. On each tablet: Settings → project URL, anon key, device code and the same PID block.

## Upgrading an existing project to v2 (two parts per PID)

The v2 app sends one record per part (`enrol` from the enrolment station, `scan` from the scan station) for each PID,
so the server needs `migrations/0002_two_parts.sql` before any v2 phone syncs.

1. Optional but cheap: Table editor → `visits` → Export to CSV (or run the Sheets "Save CSV snapshot" once).
2. SQL editor → paste `migrations/0002_two_parts.sql` → Run. Existing visits keep their data and become part `full`;
   `crf_export` keeps working (one row per visit, with a new trailing `part` column). The script can be run again
   safely; a second run also resets `recruitment_targets` to `configs/recruitment_targets.json`.
3. Check: `select part, count(*) from public.visits group by part;` shows your old rows as `full`, and
   `select count(*) from public.recruitment_targets;` shows the seeded cells.
4. Update the Google Sheet's `Code.gs` from `appscript/` (it reads `participant_export` and adds a `Targets` tab).

Changing targets later: edit `configs/recruitment_targets.json` (the app bundles it too), make the same change in the
`insert into public.recruitment_targets` block of 0002, and run that block; or, for a quick change, an admin edits the row
in the Table editor (set `active = false` to hide a cell). `tests/test_supabase_schema.py` fails while the seed in
0002 and the JSON differ.

## What the database enforces

| rule | how |
|---|---|
| name and PID stored apart | `identity` table; operators write it only through `submit_identity()` and cannot read it; admins can |
| no identity inside a CRF | check constraint `crf_has_no_identity` on `visits` |
| one record per participant and part | unique `visits (pid, part)`; a second record for the same PID and part gets HTTP 409 (23505); a PID holds either one v1 `full` record or `enrol`/`scan` parts, never both |
| idempotent uploads | primary key `visit_uuid` generated on the tablet; upload is an upsert |
| edit trail | trigger copies every insert and update (old and new CRF, who, when) into `visit_audit` |
| locking | admins set `locked`; locked visits refuse edits; the PID and part of a visit can never change |
| part matches CRF | check `crf_part_matches`: a CRF that names its `part` must match the row |
| PID blocks | `devices` blocks cannot overlap (exclusion constraint); `allocate_pid()` skips numbers already used |
| read-only export | `participant_export` view (one row per PID, both parts side by side, typed columns, no identity) and the v1 `crf_export` view, for the `exporter` role |
| recruitment targets | `recruitment_targets` readable by active accounts, writable by admins only |
| counts and scan list | `strata_counts(p_stream)` and `scan_queue(p_days)`: security definer, active operators / admins / exporters only |

The anon key is safe in the app: without a signed-in account the API returns nothing (grants are revoked from `anon`
and every table has row-level security). Explicit grants are included because Supabase projects created after
2026-05-30 need them for the REST API.

`supabase/tests/local_auth_stub.sql` plus `tests/test_supabase_schema.py` run 0001, insert a v1 visit, run 0002 twice
on a plain Postgres 16 with a stub of Supabase's `auth` schema, and check every rule above as different users, plus
that `participant_export` has a column for every exported question of `configs/crf_schema.json` and that the seeded
targets equal `configs/recruitment_targets.json`.

## Functions the v2 app and the Sheet call

| call | returns |
|---|---|
| `POST /rest/v1/rpc/strata_counts` `{"p_stream": null}` | `[{key, n}]`: distinct PIDs per strata key over submitted records (enrol `strata`, scan `scan_strata`; v1 records give sex / MST keys); drafts, screen failures and void records are left out. A scan part counts in its PID's enrol stream |
| `POST /rest/v1/rpc/scan_queue` `{"p_days": 2}` | `[{pid, enrolled_at, sex, age, mst_band, conditions}]`: submitted enrol parts from the last `p_days` x 24 h whose PID has no submitted scan part, newest first |
| `GET /rest/v1/recruitment_targets?active=eq.true&order=sort_order` | the target cells (`key, group_id, group_label, label, target, weight, sort_order, active, updated_at`) |
| `GET /rest/v1/participant_export` | the per-PID export (Sheets, CSV) |

## If you ever outgrow one free project

Two free projects are allowed per account. The simplest split is by stream (pilot and development in one, the locked
test stream in another), which also keeps test-stream data physically separate. Point the tablets for each stream at
the matching project.
