-- SWHT-PP-003 onboarding backend, v2: two parts per participant (enrol, scan), recruitment targets, per-PID export.
-- Run once in the Supabase SQL editor after 0001_init.sql. Safe on a project that already holds v1 rows (they become
-- part 'full') and safe to run again.
--
--   * visits.part: 'enrol' | 'scan' | 'full' (v1 single record). One row per (pid, part); part never changes.
--     A PID holds either one 'full' record or split parts, never both.
--   * recruitment_targets: cells of configs/recruitment_targets.json (seeded below; tests/test_supabase_schema.py
--     checks the seed equals the file). Read by active accounts, written by admins.
--   * strata_counts(p_stream): distinct PIDs per strata key over submitted records (enrol 'strata', scan
--     'scan_strata'; legacy 'full' rows give sex/MST keys). scan_queue(p_days): recent submitted enrol parts that
--     have no submitted scan part, for the scan phone's PID picker.
--   * participant_export: one row per PID, enrol and scan side by side with typed columns. crf_export stays (one row
--     per visit; gains a trailing `part` column).

-- ------------------------------------------------------------------------------------------------ typed jsonb readers
-- NULL instead of an error when a value has the wrong type, so one odd record cannot break the whole export.
create or replace function public.crf_num(j jsonb) returns numeric
  language sql immutable set search_path = public, pg_temp as $$
  select case when jsonb_typeof(j) = 'number' then j::numeric end
$$;

create or replace function public.crf_int(j jsonb) returns int
  language sql immutable set search_path = public, pg_temp as $$
  select case when jsonb_typeof(j) = 'number' and abs(j::numeric) < 2e9 then round(j::numeric)::int end
$$;

create or replace function public.crf_bool(j jsonb) returns boolean
  language sql immutable set search_path = public, pg_temp as $$
  select case when jsonb_typeof(j) = 'boolean' then j::boolean end
$$;

create or replace function public.crf_list(j jsonb) returns text
  language sql immutable set search_path = public, pg_temp as $$
  select case when jsonb_typeof(j) = 'array' then (select string_agg(x, ';') from jsonb_array_elements_text(j) x) end
$$;

create or replace function public.crf_date(j jsonb) returns date
  language plpgsql immutable set search_path = public, pg_temp as $$
begin
  if jsonb_typeof(j) = 'string' and (j #>> '{}') ~ '^\d{4}-\d{2}-\d{2}$' then
    return (j #>> '{}')::date;
  end if;
  return null;
exception when others then
  return null;
end $$;

-- Strata keys of a record: its 'strata' list, or for a v1 record the sex / MST keys it can give (design 2.5 order).
create or replace function public.crf_legacy_strata(c jsonb) returns jsonb
  language sql immutable set search_path = public, pg_temp as $$
  select case when jsonb_typeof(c -> 'strata') = 'array' then c -> 'strata' else (
    select coalesce(jsonb_agg(k order by o), '[]'::jsonb)
      from (select public.crf_int(c -> 'mst_band') as b, c ->> 'sex' as sx) i,
           lateral (values
             (1, 'sex:' || i.sx),
             (2, 'mst:' || i.b),
             (3, 'mstgrp:' || case when i.b between 1 and 4 then 'light' when i.b between 5 and 6 then 'medium'
                                   when i.b between 7 and 10 then 'dark' end),
             (4, 'sex_mst:' || i.sx || ':' || i.b)) t(o, k)
     where k is not null and (o = 1 or i.b between 1 and 10)) end
$$;

-- ------------------------------------------------------------------------------------------------ visits: parts
alter table public.visits add column if not exists part text not null default 'full';

do $$ begin
  if not exists (select 1 from pg_constraint where conname = 'visits_part_check' and conrelid = 'public.visits'::regclass) then
    alter table public.visits add constraint visits_part_check check (part in ('enrol', 'scan', 'full'));
  end if;
  if not exists (select 1 from pg_constraint where conname = 'crf_part_matches' and conrelid = 'public.visits'::regclass) then
    alter table public.visits add constraint crf_part_matches check (part = 'full' or not (crf ? 'part') or crf ->> 'part' = part);
  end if;
  if not exists (select 1 from pg_constraint where conname = 'visits_pid_part_key' and conrelid = 'public.visits'::regclass) then
    alter table public.visits add constraint visits_pid_part_key unique (pid, part);
  end if;
end $$;
alter table public.visits drop constraint if exists visits_pid_key;

create or replace function public.visits_guard() returns trigger
  language plpgsql security definer set search_path = public as $$
begin
  if tg_op = 'UPDATE' then
    if old.locked and public.app_role() is distinct from 'admin' then
      raise exception 'visit % is locked', old.pid using errcode = '42501';
    end if;
    if new.pid <> old.pid then
      raise exception 'PID of a visit cannot change (% -> %)', old.pid, new.pid using errcode = '23514';
    end if;
    if new.part <> old.part then
      raise exception 'part of a visit cannot change (% -> %)', old.part, new.part using errcode = '23514';
    end if;
    new.uploaded_by := old.uploaded_by;
  end if;
  if tg_op = 'INSERT' and exists (select 1 from public.visits v where v.pid = new.pid and v.visit_uuid <> new.visit_uuid
                                    and (v.part = 'full') <> (new.part = 'full')) then
    raise exception 'duplicate key: % already has a % record (visits_pid_part_key)', new.pid,
      case when new.part = 'full' then 'split' else 'full' end using errcode = '23505';
  end if;
  if new.locked and public.app_role() is distinct from 'admin' and (tg_op = 'INSERT' or not old.locked) then
    raise exception 'only an admin can lock a visit' using errcode = '42501';
  end if;
  new.server_received_at := now();
  return new;
end $$;

-- ------------------------------------------------------------------------------------------------ recruitment targets
create table if not exists public.recruitment_targets (
  key text primary key,
  group_id text not null,
  group_label text not null,
  label text not null,
  target int not null check (target > 0),
  weight numeric not null check (weight between 0 and 1),
  sort_order int not null default 0,
  active boolean not null default true,
  updated_at timestamptz not null default now()
);

create or replace function public.touch_updated_at() returns trigger
  language plpgsql set search_path = public, pg_temp as $$
begin
  new.updated_at := now();
  return new;
end $$;
drop trigger if exists recruitment_targets_touch on public.recruitment_targets;
create trigger recruitment_targets_touch before update on public.recruitment_targets
  for each row execute function public.touch_updated_at();

-- Seed = configs/recruitment_targets.json (groups and cells in file order). Re-running brings the table back to the file.
insert into public.recruitment_targets (key, group_id, group_label, label, target, weight, sort_order) values
  ('sex:F', 'sex', 'Sex', 'Female', 1000, 1.0, 1),
  ('sex:M', 'sex', 'Sex', 'Male', 1000, 1.0, 2),
  ('mst:4', 'mst', 'Skin tone (MST band)', 'MST 4', 200, 1.0, 3),
  ('mst:5', 'mst', 'Skin tone (MST band)', 'MST 5', 200, 1.0, 4),
  ('mst:6', 'mst', 'Skin tone (MST band)', 'MST 6', 200, 1.0, 5),
  ('mst:7', 'mst', 'Skin tone (MST band)', 'MST 7', 200, 1.0, 6),
  ('mst:8', 'mst', 'Skin tone (MST band)', 'MST 8', 200, 1.0, 7),
  ('mst:9', 'mst', 'Skin tone (MST band)', 'MST 9', 200, 1.0, 8),
  ('mst:10', 'mst', 'Skin tone (MST band)', 'MST 10', 200, 1.0, 9),
  ('cond:htn', 'condition', 'Condition', 'High blood pressure', 400, 1.0, 10),
  ('cond:af', 'condition', 'Condition', 'Atrial fibrillation', 300, 1.0, 11),
  ('cond:arrhythmia_other', 'condition', 'Condition', 'Other rhythm problem', 150, 1.0, 12),
  ('cond:heart_other', 'condition', 'Condition', 'Other heart disease', 150, 1.0, 13),
  ('cond:diabetes', 'condition', 'Condition', 'Diabetes', 400, 1.0, 14),
  ('haem:thal_trait', 'condition', 'Condition', 'Thalassaemia or HbE trait', 150, 1.0, 15),
  ('haem:thal_disease', 'condition', 'Condition', 'Thalassaemia or HbE disease', 60, 1.0, 16),
  ('haem:ida', 'condition', 'Condition', 'Iron-deficiency anaemia', 150, 1.0, 17),
  ('haem:anaemia_other', 'condition', 'Condition', 'Other anaemia', 100, 1.0, 18),
  ('haem:non_anaemic', 'condition', 'Condition', 'Not anaemic (comparator)', 300, 1.0, 19),
  ('sex_mst:F:4', 'sex_mst', 'Sex by skin tone', 'Female, MST 4', 100, 0.7, 20),
  ('sex_mst:F:5', 'sex_mst', 'Sex by skin tone', 'Female, MST 5', 100, 0.7, 21),
  ('sex_mst:F:6', 'sex_mst', 'Sex by skin tone', 'Female, MST 6', 100, 0.7, 22),
  ('sex_mst:F:7', 'sex_mst', 'Sex by skin tone', 'Female, MST 7', 100, 0.7, 23),
  ('sex_mst:F:8', 'sex_mst', 'Sex by skin tone', 'Female, MST 8', 100, 0.7, 24),
  ('sex_mst:F:9', 'sex_mst', 'Sex by skin tone', 'Female, MST 9', 100, 0.7, 25),
  ('sex_mst:F:10', 'sex_mst', 'Sex by skin tone', 'Female, MST 10', 100, 0.7, 26),
  ('sex_mst:M:4', 'sex_mst', 'Sex by skin tone', 'Male, MST 4', 100, 0.7, 27),
  ('sex_mst:M:5', 'sex_mst', 'Sex by skin tone', 'Male, MST 5', 100, 0.7, 28),
  ('sex_mst:M:6', 'sex_mst', 'Sex by skin tone', 'Male, MST 6', 100, 0.7, 29),
  ('sex_mst:M:7', 'sex_mst', 'Sex by skin tone', 'Male, MST 7', 100, 0.7, 30),
  ('sex_mst:M:8', 'sex_mst', 'Sex by skin tone', 'Male, MST 8', 100, 0.7, 31),
  ('sex_mst:M:9', 'sex_mst', 'Sex by skin tone', 'Male, MST 9', 100, 0.7, 32),
  ('sex_mst:M:10', 'sex_mst', 'Sex by skin tone', 'Male, MST 10', 100, 0.7, 33),
  ('cond_mstgrp:htn:dark', 'condition_dark', 'Condition in darker skin (MST 7-10)', 'High blood pressure, MST 7-10', 120, 0.7, 34),
  ('cond_mstgrp:af:dark', 'condition_dark', 'Condition in darker skin (MST 7-10)', 'Atrial fibrillation, MST 7-10', 120, 0.7, 35),
  ('cond_mstgrp:diabetes:dark', 'condition_dark', 'Condition in darker skin (MST 7-10)', 'Diabetes, MST 7-10', 120, 0.7, 36),
  ('haem_mstgrp:thal_trait:dark', 'condition_dark', 'Condition in darker skin (MST 7-10)', 'Thalassaemia or HbE trait, MST 7-10', 50, 0.7, 37),
  ('haem_mstgrp:ida:dark', 'condition_dark', 'Condition in darker skin (MST 7-10)', 'Iron-deficiency anaemia, MST 7-10', 50, 0.7, 38),
  ('rhythm:af', 'scan', 'Rhythm at the scan (dashboard only)', 'Kardia: possible AF', 300, 0.0, 39),
  ('rhythm:nsr', 'scan', 'Rhythm at the scan (dashboard only)', 'Kardia: normal sinus rhythm', 500, 0.0, 40)

on conflict (key) do update set group_id = excluded.group_id, group_label = excluded.group_label, label = excluded.label,
  target = excluded.target, weight = excluded.weight, sort_order = excluded.sort_order;

-- ------------------------------------------------------------------------------------------------ counts and scan queue
-- Distinct PIDs per strata key over submitted records. Scan parts take the stream of their PID's enrol part.
create or replace function public.strata_counts(p_stream text default null)
  returns table (key text, n bigint)
  language plpgsql stable security definer set search_path = public, pg_temp as $$
#variable_conflict use_column
begin
  if public.app_role() is null then
    raise exception 'not allowed' using errcode = '42501';
  end if;
  return query
  with pid_stream as (
    select v.pid, max(v.stream) filter (where v.part in ('enrol', 'full')) as stream
      from public.visits v group by v.pid
  ), keyed as (
    select v.pid, case v.part
             when 'enrol' then v.crf -> 'strata'
             when 'scan' then v.crf -> 'scan_strata'
             else public.crf_legacy_strata(v.crf) end as keys
      from public.visits v join pid_stream ps on ps.pid = v.pid
     where v.status = 'submitted' and (p_stream is null or coalesce(ps.stream, v.stream) = p_stream)
  )
  select k.value, count(distinct keyed.pid)
    from keyed cross join lateral jsonb_array_elements_text(
           case when jsonb_typeof(keyed.keys) = 'array' then keyed.keys else '[]'::jsonb end) k
   group by k.value
   order by k.value;
end $$;

-- Submitted enrol parts from the last p_days x 24 h whose PID has no submitted scan (or v1 full) record, newest first.
create or replace function public.scan_queue(p_days int default 2)
  returns table (pid text, enrolled_at timestamptz, sex text, age int, mst_band int, conditions text[])
  language plpgsql stable security definer set search_path = public, pg_temp as $$
#variable_conflict use_column
begin
  if public.app_role() is null then
    raise exception 'not allowed' using errcode = '42501';
  end if;
  return query
  select e.pid, coalesce(e.submitted_at, e.created_at), e.crf ->> 'sex', public.crf_int(e.crf -> 'age'),
         public.crf_int(e.crf -> 'mst_band'),
         case when jsonb_typeof(e.crf -> 'conditions') = 'array'
              then array(select jsonb_array_elements_text(e.crf -> 'conditions')) end
    from public.visits e
   where e.part = 'enrol' and e.status = 'submitted'
     and coalesce(e.submitted_at, e.created_at) >= now() - make_interval(days => greatest(coalesce(p_days, 2), 0))
     and not exists (select 1 from public.visits s
                      where s.pid = e.pid and s.part in ('scan', 'full') and s.status = 'submitted')
   order by 2 desc, 1;
end $$;

-- ------------------------------------------------------------------------------------------------ export views
-- v1 view, unchanged apart from the trailing part column (one row per visit, so a v2 PID appears once per part).
create or replace view public.crf_export with (security_invoker = true) as
select
  v.pid, v.status, v.stream, v.crf ->> 'dept' as dept, v.operator_code, v.device_code, v.schema_version, v.app_ver,
  v.created_at, v.submitted_at, v.server_received_at, v.screen_fail_reason, v.locked,
  (v.crf ->> 'age')::numeric as age, v.crf ->> 'sex' as sex, (v.crf ->> 'pregnant')::boolean as pregnant,
  (v.crf ->> 'height_cm')::numeric as height_cm, (v.crf ->> 'weight_kg')::numeric as weight_kg,
  round((v.crf ->> 'weight_kg')::numeric / nullif(((v.crf ->> 'height_cm')::numeric / 100) ^ 2, 0), 1) as bmi,
  v.crf ->> 'handedness' as handedness, v.crf ->> 'imaged_hand' as imaged_hand, v.crf ->> 'cuff_size' as cuff_size,
  (v.crf ->> 'mst_band')::int as mst_band, (v.crf ->> 'ita_deg')::numeric as ita_deg,
  (select string_agg(x, ';') from jsonb_array_elements_text(coalesce(v.crf -> 'cohort_tags', '[]')) x) as cohort_tags,
  (select string_agg(x, ';') from jsonb_array_elements_text(coalesce(v.crf -> 'flags', '[]')) x) as flags,
  v.crf ->> 'antihtn_today' as antihtn_today, (v.crf ->> 'n_antihtn_drugs')::int as n_antihtn_drugs,
  v.crf ->> 'dm_type' as dm_type, (v.crf ->> 'on_insulin')::boolean as on_insulin, (v.crf ->> 'on_dialysis')::boolean as on_dialysis,
  (v.crf ->> 'egfr')::numeric as egfr, v.crf ->> 'arr_type' as arr_type, v.crf ->> 'arr_status' as arr_status,
  v.crf ->> 'haem_type' as haem_type, (v.crf ->> 'transfusion_30d')::boolean as transfusion_30d,
  (v.crf ->> 'days_since_transfusion')::int as days_since_transfusion,
  (v.crf ->> 'hb_gdl')::numeric as hb_gdl, v.crf ->> 'hb_date' as hb_date, (v.crf ->> 'hba1c')::numeric as hba1c, v.crf ->> 'hba1c_date' as hba1c_date,
  (select string_agg(x, ';') from jsonb_array_elements_text(coalesce(v.crf -> 'acute_30m', '[]')) x) as acute_30m,
  (v.crf ->> 'last_meal_h')::numeric as last_meal_h, (v.crf ->> 'glucose_mgdl')::numeric as glucose_mgdl, (v.crf ->> 'spo2')::int as spo2,
  (v.crf -> 'bp1' ->> 'sbp')::int as bp1_sbp, (v.crf -> 'bp1' ->> 'dbp')::int as bp1_dbp, (v.crf -> 'bp1' ->> 'hr')::int as bp1_hr, v.crf -> 'bp1' ->> 'wall_ts' as bp1_ts,
  (v.crf -> 'bp2' ->> 'sbp')::int as bp2_sbp, (v.crf -> 'bp2' ->> 'dbp')::int as bp2_dbp, (v.crf -> 'bp2' ->> 'hr')::int as bp2_hr, v.crf -> 'bp2' ->> 'wall_ts' as bp2_ts,
  (v.crf -> 'bp3' ->> 'sbp')::int as bp3_sbp, (v.crf -> 'bp3' ->> 'dbp')::int as bp3_dbp, (v.crf -> 'bp3' ->> 'hr')::int as bp3_hr, v.crf -> 'bp3' ->> 'wall_ts' as bp3_ts,
  (v.crf ->> 'irregular_pulse')::boolean as irregular_pulse, v.crf ->> 'recovery' as recovery, (v.crf ->> 'bracket_flag')::boolean as bracket_flag,
  (v.crf ->> 'gestational_age_weeks')::numeric as gestational_age_weeks, (v.crf ->> 'trimester')::int as trimester, v.crf ->> 'ga_source' as ga_source,
  (v.crf ->> 'gravida')::int as gravida, (v.crf ->> 'parity')::int as parity, v.crf ->> 'hdp_status' as hdp_status, v.crf ->> 'urine_protein' as urine_protein,
  (v.crf ->> 'anc_hb_gdl')::numeric as anc_hb_gdl, v.crf ->> 'anc_hb_date' as anc_hb_date,
  (v.crf ->> 'anc_clinic_sbp')::int as anc_clinic_sbp, (v.crf ->> 'anc_clinic_dbp')::int as anc_clinic_dbp,
  v.crf -> 'clip1' ->> 'started_at' as clip1_start, v.crf -> 'clip1' ->> 'ended_at' as clip1_end, v.crf -> 'clip1' ->> 'quality' as clip1_quality,
  v.crf -> 'clip1b' ->> 'started_at' as clip1b_start, v.crf -> 'clip1b' ->> 'quality' as clip1b_quality,
  v.crf -> 'clip2' ->> 'started_at' as clip2_start, v.crf -> 'clip2' ->> 'ended_at' as clip2_end, v.crf -> 'clip2' ->> 'quality' as clip2_quality,
  v.crf -> 'clip2b' ->> 'started_at' as clip2b_start, v.crf -> 'clip2b' ->> 'quality' as clip2b_quality,
  v.crf ->> 'clip_plan' as clip_plan, v.crf ->> 'adverse_event' as adverse_event, v.crf ->> 'operator_notes' as operator_notes,
  v.crf::text as crf_json,
  v.part
from public.visits v
where v.status <> 'void';

-- One row per PID (void records left out). e = the enrol part, s = the scan part; a v1 'full' record fills both
-- sides (parts = 'full'), its CRF goes to enrol_json and scan_json stays empty. Lists are joined with ';'.
-- security_invoker: the caller's row-level security applies.
drop view if exists public.participant_export;
create view public.participant_export with (security_invoker = true) as
select
  p.pid,
  p.parts,
  coalesce(e.crf ->> 'stream', e.stream, s.stream) as stream,
  e.status as enrol_status,
  coalesce(e.crf ->> 'operator', e.operator_code) as enrol_operator,
  e.crf ->> 'unit_id' as enrol_unit_id,
  coalesce(e.crf ->> 'device_code', e.device_code) as enrol_device_code,
  coalesce(e.crf ->> 'app_ver', e.app_ver) as enrol_app_ver,
  e.crf ->> 'capture_mode' as enrol_capture_mode,
  e.schema_version as enrol_schema_version,
  e.created_at as enrol_created_at,
  e.submitted_at as enrol_submitted_at,
  e.server_received_at as enrol_uploaded_at,
  e.screen_fail_reason as enrol_screen_fail_reason,
  e.locked as enrol_locked,
  s.status as scan_status,
  coalesce(s.crf ->> 'operator', s.operator_code) as scan_operator,
  s.crf ->> 'unit_id' as scan_unit_id,
  coalesce(s.crf ->> 'device_code', s.device_code) as scan_device_code,
  coalesce(s.crf ->> 'app_ver', s.app_ver) as scan_app_ver,
  s.crf ->> 'capture_mode' as scan_capture_mode,
  s.schema_version as scan_schema_version,
  s.created_at as scan_created_at,
  s.submitted_at as scan_submitted_at,
  s.server_received_at as scan_uploaded_at,
  s.screen_fail_reason as scan_screen_fail_reason,
  s.locked as scan_locked,
  e.crf ->> 'dept' as dept,
  public.crf_int(e.crf -> 'age') as age,
  e.crf ->> 'sex' as sex,
  e.crf ->> 'pregnant' as pregnant,
  public.crf_num(e.crf -> 'gestational_age_weeks') as gestational_age_weeks,
  public.crf_int(e.crf -> 'trimester') as trimester,
  public.crf_num(e.crf -> 'height_cm') as height_cm,
  public.crf_num(e.crf -> 'weight_kg') as weight_kg,
  public.crf_num(e.crf -> 'bmi') as bmi,
  public.crf_int(e.crf -> 'mst_band') as mst_band,
  public.crf_list(e.crf -> 'conditions') as conditions,
  e.crf ->> 'htn_meds' as htn_meds,
  e.crf ->> 'htn_meds_today' as htn_meds_today,
  e.crf ->> 'af_pattern' as af_pattern,
  e.crf ->> 'anticoagulant' as anticoagulant,
  e.crf ->> 'arrhythmia_type' as arrhythmia_type,
  e.crf ->> 'cardiac_device' as cardiac_device,
  e.crf ->> 'dm_type' as dm_type,
  public.crf_int(e.crf -> 'dm_years') as dm_years,
  e.crf ->> 'dm_treatment' as dm_treatment,
  e.crf ->> 'thal_type' as thal_type,
  e.crf ->> 'thal_transfusions' as thal_transfusions,
  e.crf ->> 'iron_therapy' as iron_therapy,
  e.crf ->> 'on_dialysis' as on_dialysis,
  e.crf ->> 'transfusion_3m' as transfusion_3m,
  public.crf_date(e.crf -> 'last_transfusion_date') as last_transfusion_date,
  public.crf_num(e.crf -> 'hb_gdl') as hb_gdl,
  public.crf_date(e.crf -> 'hb_date') as hb_date,
  public.crf_num(e.crf -> 'rbc_mill') as rbc_mill,
  public.crf_num(e.crf -> 'mcv_fl') as mcv_fl,
  public.crf_num(e.crf -> 'mch_pg') as mch_pg,
  public.crf_num(e.crf -> 'rdw_pct') as rdw_pct,
  public.crf_num(e.crf -> 'mentzer') as mentzer,
  public.crf_bool(e.crf -> 'hplc_reflex') as hplc_reflex,
  public.crf_num(e.crf -> 'ferritin_ngml') as ferritin_ngml,
  public.crf_date(e.crf -> 'ferritin_date') as ferritin_date,
  e.crf ->> 'hplc_result' as hplc_result,
  public.crf_num(e.crf -> 'hba2_pct') as hba2_pct,
  public.crf_num(e.crf -> 'hbf_pct') as hbf_pct,
  public.crf_num(e.crf -> 'hbe_pct') as hbe_pct,
  public.crf_date(e.crf -> 'hplc_date') as hplc_date,
  public.crf_num(e.crf -> 'hba1c_pct') as hba1c_pct,
  public.crf_date(e.crf -> 'hba1c_date') as hba1c_date,
  e.crf ->> 'anaemia_grade' as anaemia_grade,
  e.crf ->> 'haem_cell' as haem_cell,
  e.crf ->> 'dm_label' as dm_label,
  public.crf_list(e.crf -> 'acute_30m') as acute_30m,
  public.crf_num(e.crf -> 'last_meal_h') as last_meal_h,
  public.crf_num(e.crf -> 'glucose_mgdl') as glucose_mgdl,
  public.crf_list(e.crf -> 'strata') as strata,
  e.crf ->> 'enrol_notes' as enrol_notes,
  s.crf ->> 'clip_plan' as clip_plan,
  s.crf ->> 'imaged_hand' as imaged_hand,
  public.crf_num(s.crf -> 'arm_circumference_cm') as arm_circumference_cm,
  s.crf ->> 'cuff_size' as cuff_size,
  public.crf_int(s.crf -> 'bp1' -> 'sbp') as bp1_sbp,
  public.crf_int(s.crf -> 'bp1' -> 'dbp') as bp1_dbp,
  public.crf_int(s.crf -> 'bp1' -> 'hr') as bp1_hr,
  s.crf -> 'bp1' ->> 'wall_ts' as bp1_ts,
  public.crf_int(s.crf -> 'bp2' -> 'sbp') as bp2_sbp,
  public.crf_int(s.crf -> 'bp2' -> 'dbp') as bp2_dbp,
  public.crf_int(s.crf -> 'bp2' -> 'hr') as bp2_hr,
  s.crf -> 'bp2' ->> 'wall_ts' as bp2_ts,
  public.crf_int(s.crf -> 'bp3' -> 'sbp') as bp3_sbp,
  public.crf_int(s.crf -> 'bp3' -> 'dbp') as bp3_dbp,
  public.crf_int(s.crf -> 'bp3' -> 'hr') as bp3_hr,
  s.crf -> 'bp3' ->> 'wall_ts' as bp3_ts,
  s.crf -> 'clip1' ->> 'started_at' as clip1_start,
  s.crf -> 'clip1' ->> 'ended_at' as clip1_end,
  s.crf -> 'clip1' ->> 'quality' as clip1_quality,
  s.crf -> 'clip1' ->> 'video_grade' as clip1_video_grade,
  s.crf -> 'clip1' ->> 'ecg_grade' as clip1_ecg_grade,
  public.crf_int(s.crf -> 'clip1' -> 'ecg_samples') as clip1_ecg_samples,
  s.crf -> 'clip1' ->> 'kardia_determination' as clip1_kardia_determination,
  public.crf_int(s.crf -> 'clip1' -> 'kardia_hr') as clip1_kardia_hr,
  public.crf_num(s.crf -> 'clip1' -> 'phone_duration_s') as clip1_phone_duration_s,
  public.crf_bool(s.crf -> 'clip1' -> 'phone_interrupted') as clip1_phone_interrupted,
  public.crf_num(s.crf -> 'clip1' -> 'video_metrics' -> 'snr_db') as clip1_snr_db,
  public.crf_num(s.crf -> 'clip1' -> 'video_metrics' -> 'pulse_bpm') as clip1_pulse_bpm,
  public.crf_num(s.crf -> 'clip1' -> 'ecg_metrics' -> 'hr_bpm') as clip1_hr_bpm,
  s.crf -> 'clip1b' ->> 'started_at' as clip1b_start,
  s.crf -> 'clip1b' ->> 'ended_at' as clip1b_end,
  s.crf -> 'clip1b' ->> 'quality' as clip1b_quality,
  s.crf -> 'clip1b' ->> 'video_grade' as clip1b_video_grade,
  s.crf -> 'clip1b' ->> 'ecg_grade' as clip1b_ecg_grade,
  public.crf_int(s.crf -> 'clip1b' -> 'ecg_samples') as clip1b_ecg_samples,
  s.crf -> 'clip1b' ->> 'kardia_determination' as clip1b_kardia_determination,
  public.crf_int(s.crf -> 'clip1b' -> 'kardia_hr') as clip1b_kardia_hr,
  public.crf_num(s.crf -> 'clip1b' -> 'phone_duration_s') as clip1b_phone_duration_s,
  public.crf_bool(s.crf -> 'clip1b' -> 'phone_interrupted') as clip1b_phone_interrupted,
  public.crf_num(s.crf -> 'clip1b' -> 'video_metrics' -> 'snr_db') as clip1b_snr_db,
  public.crf_num(s.crf -> 'clip1b' -> 'video_metrics' -> 'pulse_bpm') as clip1b_pulse_bpm,
  public.crf_num(s.crf -> 'clip1b' -> 'ecg_metrics' -> 'hr_bpm') as clip1b_hr_bpm,
  s.crf -> 'clip2' ->> 'started_at' as clip2_start,
  s.crf -> 'clip2' ->> 'ended_at' as clip2_end,
  s.crf -> 'clip2' ->> 'quality' as clip2_quality,
  s.crf -> 'clip2' ->> 'video_grade' as clip2_video_grade,
  s.crf -> 'clip2' ->> 'ecg_grade' as clip2_ecg_grade,
  public.crf_int(s.crf -> 'clip2' -> 'ecg_samples') as clip2_ecg_samples,
  s.crf -> 'clip2' ->> 'kardia_determination' as clip2_kardia_determination,
  public.crf_int(s.crf -> 'clip2' -> 'kardia_hr') as clip2_kardia_hr,
  public.crf_num(s.crf -> 'clip2' -> 'phone_duration_s') as clip2_phone_duration_s,
  public.crf_bool(s.crf -> 'clip2' -> 'phone_interrupted') as clip2_phone_interrupted,
  public.crf_num(s.crf -> 'clip2' -> 'video_metrics' -> 'snr_db') as clip2_snr_db,
  public.crf_num(s.crf -> 'clip2' -> 'video_metrics' -> 'pulse_bpm') as clip2_pulse_bpm,
  public.crf_num(s.crf -> 'clip2' -> 'ecg_metrics' -> 'hr_bpm') as clip2_hr_bpm,
  s.crf -> 'clip2b' ->> 'started_at' as clip2b_start,
  s.crf -> 'clip2b' ->> 'ended_at' as clip2b_end,
  s.crf -> 'clip2b' ->> 'quality' as clip2b_quality,
  s.crf -> 'clip2b' ->> 'video_grade' as clip2b_video_grade,
  s.crf -> 'clip2b' ->> 'ecg_grade' as clip2b_ecg_grade,
  public.crf_int(s.crf -> 'clip2b' -> 'ecg_samples') as clip2b_ecg_samples,
  s.crf -> 'clip2b' ->> 'kardia_determination' as clip2b_kardia_determination,
  public.crf_int(s.crf -> 'clip2b' -> 'kardia_hr') as clip2b_kardia_hr,
  public.crf_num(s.crf -> 'clip2b' -> 'phone_duration_s') as clip2b_phone_duration_s,
  public.crf_bool(s.crf -> 'clip2b' -> 'phone_interrupted') as clip2b_phone_interrupted,
  public.crf_num(s.crf -> 'clip2b' -> 'video_metrics' -> 'snr_db') as clip2b_snr_db,
  public.crf_num(s.crf -> 'clip2b' -> 'video_metrics' -> 'pulse_bpm') as clip2b_pulse_bpm,
  public.crf_num(s.crf -> 'clip2b' -> 'ecg_metrics' -> 'hr_bpm') as clip2b_hr_bpm,
  public.crf_bool(s.crf -> 'irregular_pulse') as irregular_pulse,
  s.crf ->> 'adverse_event' as adverse_event,
  s.crf ->> 'recovery' as recovery,
  public.crf_bool(s.crf -> 'bracket_flag') as bracket_flag,
  public.crf_list(s.crf -> 'scan_strata') as scan_strata,
  s.crf ->> 'scan_notes' as scan_notes,
  e.crf::text as enrol_json,
  case when s.part = 'scan' then s.crf::text end as scan_json

from (select v.pid, string_agg(distinct v.part, ';' order by v.part) as parts
        from public.visits v where v.status <> 'void' group by v.pid) p
left join lateral (select * from public.visits x where x.pid = p.pid and x.status <> 'void' and x.part in ('enrol', 'full')
                    order by x.part = 'enrol' desc limit 1) e on true
left join lateral (select * from public.visits x where x.pid = p.pid and x.status <> 'void' and x.part in ('scan', 'full')
                    order by x.part = 'scan' desc limit 1) s on true;

-- ------------------------------------------------------------------------------------------------ row-level security
alter table public.recruitment_targets enable row level security;

drop policy if exists targets_read on public.recruitment_targets;
create policy targets_read on public.recruitment_targets for select to authenticated using (public.app_role() is not null);
drop policy if exists targets_admin on public.recruitment_targets;
create policy targets_admin on public.recruitment_targets for all to authenticated
  using (public.app_role() = 'admin') with check (public.app_role() = 'admin');

-- ------------------------------------------------------------------------------------------------ grants
revoke all on public.recruitment_targets, public.participant_export, public.crf_export from anon;
grant select, insert, update, delete on public.recruitment_targets to authenticated;
grant select on public.participant_export, public.crf_export to authenticated;
revoke execute on function public.strata_counts(text), public.scan_queue(int), public.crf_num(jsonb), public.crf_int(jsonb),
  public.crf_bool(jsonb), public.crf_list(jsonb), public.crf_date(jsonb), public.crf_legacy_strata(jsonb),
  public.touch_updated_at() from public, anon;
grant execute on function public.strata_counts(text), public.scan_queue(int) to authenticated;
grant execute on function public.crf_num(jsonb), public.crf_int(jsonb), public.crf_bool(jsonb), public.crf_list(jsonb),
  public.crf_date(jsonb), public.crf_legacy_strata(jsonb) to authenticated, service_role;
