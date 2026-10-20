-- SWHT-PP-003 onboarding backend (Supabase, free tier). Run once in the Supabase SQL editor.
--
-- Design
--   * identity (name, hospital registration number, phone) and visits (the CRF, keyed by PID) are separate tables.
--     Operators can create identity rows only through submit_identity() and can never read them back; only admins
--     can read identity. The CRF table refuses rows that carry identity keys.
--   * One visit per participant (unique PID). The tablet generates visit_uuid, so retried uploads are idempotent.
--   * Every insert and update of a visit is copied to visit_audit (old and new CRF, who, when).
--   * PIDs: each tablet owns a non-overlapping block (devices); allocate_pid() issues the next free number online,
--     the app issues from the same block offline.
--   * Explicit GRANTs are included: Supabase projects created after 2026-05-30 need them for the REST API.

-- ------------------------------------------------------------------------------------------------ tables
create table if not exists public.operators (
  user_id uuid primary key references auth.users (id) on delete cascade,
  operator_code text not null unique,
  display_name text,
  role text not null default 'operator' check (role in ('operator', 'admin', 'exporter')),
  active boolean not null default true,
  created_at timestamptz not null default now()
);

create table if not exists public.devices (
  device_code text primary key,
  unit_id text not null,
  pid_block_start int not null,
  pid_block_end int not null,
  next_pid int not null,
  check (pid_block_start >= 1 and pid_block_end >= pid_block_start and pid_block_end <= 9999),
  check (next_pid between pid_block_start and pid_block_end + 1),
  exclude using gist (int4range(pid_block_start, pid_block_end, '[]') with &&)
);

create table if not exists public.identity (
  pid text primary key check (pid ~ '^SWHT-PP-003-[0-9]{4}$'),
  name text not null check (length(btrim(name)) > 0),
  hospital_reg_no text,
  phone text,
  created_by uuid not null default auth.uid(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.visits (
  visit_uuid uuid primary key,
  pid text not null unique check (pid ~ '^SWHT-PP-003-[0-9]{4}$'),
  status text not null check (status in ('draft', 'submitted', 'screen_fail', 'void')),
  crf jsonb not null,
  schema_version text not null,
  app_ver text,
  device_code text,
  operator_code text,
  stream text check (stream in ('pilot', 'development', 'model_selection', 'test')),
  created_at timestamptz not null,
  updated_at timestamptz not null,
  submitted_at timestamptz,
  screen_fail_reason text,
  uploaded_by uuid not null default auth.uid(),
  server_received_at timestamptz not null default now(),
  locked boolean not null default false,
  constraint crf_pid_matches check (crf ->> 'study_id' = pid),
  constraint crf_has_no_identity check (not (crf ?| array['name', 'phone', 'hospital_reg_no']))
);
create index if not exists visits_status_idx on public.visits (status);
create index if not exists visits_received_idx on public.visits (server_received_at);

create table if not exists public.visit_audit (
  id bigserial primary key,
  visit_uuid uuid not null,
  pid text not null,
  action text not null,
  changed_by uuid,
  changed_at timestamptz not null default now(),
  old_status text,
  new_status text,
  old_crf jsonb,
  new_crf jsonb
);

-- ------------------------------------------------------------------------------------------------ helpers
create or replace function public.app_role() returns text
  language sql stable security definer set search_path = public as $$
  select role from public.operators where user_id = auth.uid() and active
$$;

create or replace function public.app_operator_code() returns text
  language sql stable security definer set search_path = public as $$
  select operator_code from public.operators where user_id = auth.uid() and active
$$;

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
    new.uploaded_by := old.uploaded_by;
  end if;
  if new.locked and public.app_role() is distinct from 'admin' and (tg_op = 'INSERT' or not old.locked) then
    raise exception 'only an admin can lock a visit' using errcode = '42501';
  end if;
  new.server_received_at := now();
  return new;
end $$;

create or replace function public.visits_audit() returns trigger
  language plpgsql security definer set search_path = public as $$
begin
  insert into public.visit_audit (visit_uuid, pid, action, changed_by, old_status, new_status, old_crf, new_crf)
  values (new.visit_uuid, new.pid, lower(tg_op), auth.uid(),
          case when tg_op = 'UPDATE' then old.status end, new.status,
          case when tg_op = 'UPDATE' then old.crf end, new.crf);
  return new;
end $$;

drop trigger if exists visits_guard on public.visits;
create trigger visits_guard before insert or update on public.visits for each row execute function public.visits_guard();
drop trigger if exists visits_audit on public.visits;
create trigger visits_audit after insert or update on public.visits for each row execute function public.visits_audit();

-- Identity is written only through this function: operators can create and correct the rows they created, never read.
create or replace function public.submit_identity(p_pid text, p_name text, p_hospital_reg_no text default null, p_phone text default null)
  returns void language plpgsql security definer set search_path = public as $$
declare
  r text := public.app_role();
  owner uuid;
begin
  if r is null or r not in ('operator', 'admin') then
    raise exception 'not allowed' using errcode = '42501';
  end if;
  select created_by into owner from public.identity where pid = p_pid;
  if owner is null then
    insert into public.identity (pid, name, hospital_reg_no, phone, created_by)
    values (p_pid, p_name, p_hospital_reg_no, p_phone, auth.uid());
  elsif owner = auth.uid() or r = 'admin' then
    update public.identity set name = p_name, hospital_reg_no = p_hospital_reg_no, phone = p_phone, updated_at = now()
     where pid = p_pid;
  else
    raise exception 'identity for % was created by another operator', p_pid using errcode = '42501';
  end if;
end $$;

-- Next free PID in the calling tablet's block (skips numbers already used by typed labels).
create or replace function public.allocate_pid(p_device text) returns text
  language plpgsql security definer set search_path = public as $$
declare
  d public.devices%rowtype;
  candidate text;
begin
  if public.app_role() is null or public.app_role() not in ('operator', 'admin') then
    raise exception 'not allowed' using errcode = '42501';
  end if;
  loop
    select * into d from public.devices where device_code = p_device for update;
    if not found then
      raise exception 'unknown device %', p_device using errcode = 'P0002';
    end if;
    if d.next_pid > d.pid_block_end then
      raise exception 'PID block of % is exhausted (%-%)', p_device, d.pid_block_start, d.pid_block_end using errcode = 'P0001';
    end if;
    candidate := 'SWHT-PP-003-' || lpad(d.next_pid::text, 4, '0');
    update public.devices set next_pid = next_pid + 1 where device_code = p_device;
    exit when not exists (select 1 from public.visits where pid = candidate)
          and not exists (select 1 from public.identity where pid = candidate);
  end loop;
  return candidate;
end $$;

-- ------------------------------------------------------------------------------------------------ export view
-- One flat row per visit for Google Sheets / CSV. No identity columns. security_invoker: the caller's RLS applies.
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
  v.crf::text as crf_json
from public.visits v
where v.status <> 'void';

-- ------------------------------------------------------------------------------------------------ row-level security
alter table public.operators enable row level security;
alter table public.devices enable row level security;
alter table public.identity enable row level security;
alter table public.visits enable row level security;
alter table public.visit_audit enable row level security;

drop policy if exists operators_read on public.operators;
create policy operators_read on public.operators for select to authenticated
  using (user_id = auth.uid() or public.app_role() = 'admin');

drop policy if exists devices_read on public.devices;
create policy devices_read on public.devices for select to authenticated using (public.app_role() is not null);
drop policy if exists devices_admin on public.devices;
create policy devices_admin on public.devices for all to authenticated
  using (public.app_role() = 'admin') with check (public.app_role() = 'admin');

drop policy if exists identity_admin on public.identity;
create policy identity_admin on public.identity for all to authenticated
  using (public.app_role() = 'admin') with check (public.app_role() = 'admin');

drop policy if exists visits_read on public.visits;
create policy visits_read on public.visits for select to authenticated
  using (public.app_role() in ('operator', 'admin', 'exporter'));
drop policy if exists visits_insert on public.visits;
create policy visits_insert on public.visits for insert to authenticated
  with check (public.app_role() in ('operator', 'admin') and uploaded_by = auth.uid());
drop policy if exists visits_update on public.visits;
create policy visits_update on public.visits for update to authenticated
  using (public.app_role() in ('operator', 'admin')) with check (public.app_role() in ('operator', 'admin'));
drop policy if exists visits_delete on public.visits;
create policy visits_delete on public.visits for delete to authenticated using (public.app_role() = 'admin');

drop policy if exists audit_read on public.visit_audit;
create policy audit_read on public.visit_audit for select to authenticated using (public.app_role() = 'admin');

-- ------------------------------------------------------------------------------------------------ grants
revoke all on public.operators, public.devices, public.identity, public.visits, public.visit_audit, public.crf_export from anon;
grant usage on schema public to authenticated;
grant select on public.operators to authenticated;
grant select, insert, update, delete on public.devices to authenticated;
grant select, update, delete on public.identity to authenticated;
grant select, insert, update, delete on public.visits to authenticated;
grant select on public.visit_audit to authenticated;
grant select on public.crf_export to authenticated;
revoke execute on function public.submit_identity(text, text, text, text), public.allocate_pid(text),
  public.app_role(), public.app_operator_code() from public, anon;
grant execute on function public.submit_identity(text, text, text, text), public.allocate_pid(text),
  public.app_role(), public.app_operator_code() to authenticated;
