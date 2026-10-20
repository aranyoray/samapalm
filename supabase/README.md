# Supabase backend for the onboarding app

One free Supabase project holds the study's CRFs: 2,000 participants need roughly 20 MB of the free plan's 500 MB
database. Free projects pause after 7 days without activity and have no automatic backups; the hourly Google Sheets
refresh (`appscript/`) keeps the project active and its weekly CSV snapshot in Drive is the off-site backup.
`palmppg crf pull` also writes a CSV snapshot on every pull.

## Set up (about 15 minutes)

1. Create a project at supabase.com (region: Mumbai, `ap-south-1`). Note the project URL and the anon key
   (Project Settings → API).
2. SQL editor → paste `migrations/0001_init.sql` → Run.
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

## What the database enforces

| rule | how |
|---|---|
| name and PID stored apart | `identity` table; operators write it only through `submit_identity()` and cannot read it; admins can |
| no identity inside a CRF | check constraint `crf_has_no_identity` on `visits` |
| one visit per participant | unique `visits.pid`; a second tablet using the same PID gets HTTP 409 |
| idempotent uploads | primary key `visit_uuid` generated on the tablet; upload is an upsert |
| edit trail | trigger copies every insert and update (old and new CRF, who, when) into `visit_audit` |
| locking | admins set `locked`; locked visits refuse edits and the PID can never change |
| PID blocks | `devices` blocks cannot overlap (exclusion constraint); `allocate_pid()` skips numbers already used |
| read-only export | `crf_export` view (no identity columns) for the `exporter` role |

The anon key is safe in the app: without a signed-in account the API returns nothing (grants are revoked from `anon`
and every table has row-level security). Explicit grants are included because Supabase projects created after
2026-05-30 need them for the REST API.

`supabase/tests/local_auth_stub.sql` plus `tests/test_supabase_schema.py` run this migration on a plain Postgres 16
with a stub of Supabase's `auth` schema and check every rule above as different users.

## If you ever outgrow one free project

Two free projects are allowed per account. The simplest split is by stream (pilot and development in one, the locked
test stream in another), which also keeps test-stream data physically separate. Point the tablets for each stream at
the matching project.
