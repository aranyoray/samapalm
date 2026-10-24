"""supabase/migrations/0001_init.sql + 0002_two_parts.sql on a real throwaway Postgres 16 with a stub of Supabase's auth
schema.

Each check runs as the `authenticated` role with a JWT subject set, the way PostgREST runs a request, so row-level
security, grants, triggers and the security-definer functions are exercised for real. 0002 is applied to a database
that already holds a v1 visit, then applied a second time (it must be re-runnable).
"""
import json
import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PGBIN = Path("/usr/lib/postgresql/16/bin")
pytestmark = pytest.mark.skipif(not (PGBIN / "initdb").exists() or shutil.which("psql") is None, reason="Postgres 16 not installed")

MIG2 = ROOT / "supabase" / "migrations" / "0002_two_parts.sql"
OPS = {"op1": str(uuid.uuid4()), "op2": str(uuid.uuid4()), "admin": str(uuid.uuid4()), "exporter": str(uuid.uuid4()), "stranger": str(uuid.uuid4())}


def _as_pg(cmd):
    return (["runuser", "-u", "postgres", "--"] + cmd) if os.geteuid() == 0 else cmd


@pytest.fixture(scope="module")
def pg():
    d = Path(tempfile.mkdtemp(prefix="pgtest_"))
    data, sock = d / "data", d / "sock"
    sock.mkdir()
    if os.geteuid() == 0:
        shutil.chown(d, "postgres")
        shutil.chown(sock, "postgres")
    subprocess.run(_as_pg([str(PGBIN / "initdb"), "-D", str(data), "-A", "trust", "-U", "postgres"]), check=True, capture_output=True)
    # -l: the server must not inherit our pipes, or subprocess.run waits for it to exit
    subprocess.run(_as_pg([str(PGBIN / "pg_ctl"), "-D", str(data), "-l", str(d / "server.log"), "-o", f"-k {sock} -c listen_addresses=''",
                           "-w", "start"]), check=True, capture_output=True, timeout=60)

    def psql(sql, user=None, check=True):
        prefix = ""
        if user is not None:
            prefix = f"set role authenticated; set request.jwt.claim.sub = '{OPS[user]}';\n"
        # VERBOSITY=verbose puts the SQLSTATE into error messages ("ERROR:  23505: ...")
        r = subprocess.run(["psql", "-h", str(sock), "-U", "postgres", "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-v", "VERBOSITY=verbose",
                            "-q", "-t", "-A", "-c", prefix + sql], capture_output=True, text=True)
        if check and r.returncode != 0:
            raise AssertionError(r.stderr)
        return r

    def apply(f):
        r = subprocess.run(["psql", "-h", str(sock), "-U", "postgres", "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-q", "-f", str(f)],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stderr

    apply(ROOT / "supabase" / "tests" / "local_auth_stub.sql")
    apply(ROOT / "supabase" / "migrations" / "0001_init.sql")
    users = ",".join(f"('{u}', '{k}@x.org')" for k, u in OPS.items())
    psql(f"insert into auth.users (id, email) values {users};")
    psql(f"""insert into public.operators (user_id, operator_code, role) values
      ('{OPS['op1']}', 'op1', 'operator'), ('{OPS['op2']}', 'op2', 'operator'), ('{OPS['admin']}', 'adm', 'admin'),
      ('{OPS['exporter']}', 'exp', 'exporter');
      insert into public.devices values ('tab-A', 'unit_01', 1, 3, 1), ('tab-B', 'unit_01', 1000, 1999, 1000);""")
    # a v1 visit uploaded before 0002 (its own stream, so the legacy strata count below is not disturbed by other tests)
    psql(_visit("SWHT-PP-003-0900", extra=', "sex": "M", "mst_band": 8')[1].replace("'pilot'", "'model_selection'"), "op1")
    apply(MIG2)
    apply(MIG2)                                                       # re-runnable
    yield psql
    subprocess.run(_as_pg([str(PGBIN / "pg_ctl"), "-D", str(data), "-m", "immediate", "stop"]), capture_output=True)
    shutil.rmtree(d, ignore_errors=True)


def _visit(pid, vu=None, status="submitted", extra=""):
    vu = vu or str(uuid.uuid4())
    crf = '{"study_id": "%s", "age": 40, "sex": "F", "mst_band": 7, "flags": ["none"]%s}' % (pid, extra)
    # what PostgREST runs for POST /rest/v1/visits?on_conflict=visit_uuid with Prefer: resolution=merge-duplicates
    return vu, f"""insert into public.visits (visit_uuid, pid, status, crf, schema_version, app_ver, device_code, operator_code, stream, created_at, updated_at)
      values ('{vu}', '{pid}', '{status}', '{crf}'::jsonb, 'v1', '1.0', 'tab-A', 'op1', 'pilot', now(), now())
      on conflict (visit_uuid) do update set status = excluded.status, crf = excluded.crf, updated_at = excluded.updated_at;"""


def test_operator_upserts_are_idempotent_and_audited(pg):
    vu, sql = _visit("SWHT-PP-003-0101")
    pg(sql, "op1")
    pg(sql, "op1")                                                    # retried upload: no error, still one row
    assert pg("select count(*) from public.visits where pid = 'SWHT-PP-003-0101';", "op1").stdout.strip() == "1"
    _, upd = _visit("SWHT-PP-003-0101", vu, extra=', "age": 41')
    pg(upd, "op2")                                                    # another operator can continue the visit
    assert pg("select count(*) from public.visit_audit where pid = 'SWHT-PP-003-0101';").stdout.strip() == "3"
    assert pg(f"select uploaded_by from public.visits where visit_uuid = '{vu}';").stdout.strip() == OPS["op1"]


def test_duplicate_pid_from_another_visit_is_rejected(pg):
    pg(_visit("SWHT-PP-003-0102")[1], "op1")
    r = pg(_visit("SWHT-PP-003-0102")[1], "op2", check=False)
    assert r.returncode != 0 and "23505" in r.stderr and "visits_pid_part_key" in r.stderr


def test_crf_cannot_carry_identity_or_a_mismatched_pid(pg):
    r = pg(_visit("SWHT-PP-003-0103", extra=', "name": "Leak"')[1], "op1", check=False)
    assert r.returncode != 0 and "crf_has_no_identity" in r.stderr
    vu = str(uuid.uuid4())
    bad = _visit("SWHT-PP-003-0104", vu)[1].replace('"study_id": "SWHT-PP-003-0104"', '"study_id": "SWHT-PP-003-9999"')
    r = pg(bad, "op1", check=False)
    assert r.returncode != 0 and "crf_pid_matches" in r.stderr


def test_identity_is_write_only_for_operators(pg):
    pg("select public.submit_identity('SWHT-PP-003-0105', 'Mita Roy', 'MCH-1', '9830000000');", "op1")
    assert pg("select count(*) from public.identity;", "op1").stdout.strip() == "0"          # RLS hides it
    assert pg("select name from public.identity where pid = 'SWHT-PP-003-0105';", "admin").stdout.strip() == "Mita Roy"
    pg("select public.submit_identity('SWHT-PP-003-0105', 'Mita Roy Das');", "op1")         # creator may correct
    r = pg("select public.submit_identity('SWHT-PP-003-0105', 'Someone Else');", "op2", check=False)
    assert r.returncode != 0 and "another operator" in r.stderr
    r = pg("insert into public.identity (pid, name) values ('SWHT-PP-003-0106', 'X');", "op1", check=False)
    assert r.returncode != 0
    assert pg("select count(*) from public.identity;", "exporter").stdout.strip() == "0"


def test_exporter_reads_the_flat_view_but_cannot_write(pg):
    pg(_visit("SWHT-PP-003-0107", extra=', "bp1": {"sbp": 130, "dbp": 85, "hr": 70, "wall_ts": "2026-10-20T10:00:00+05:30"}, '
                                          '"height_cm": 160, "weight_kg": 64')[1], "op1")
    out = pg("select pid, bp1_sbp, bmi, flags from public.crf_export where pid = 'SWHT-PP-003-0107';", "exporter").stdout.strip()
    assert out == "SWHT-PP-003-0107|130|25.0|none"
    cols = pg("select string_agg(column_name, ',') from information_schema.columns where table_name = 'crf_export';").stdout
    assert "name" not in cols.split(",") and "phone" not in cols.split(",")
    r = pg(_visit("SWHT-PP-003-0108")[1], "exporter", check=False)
    assert r.returncode != 0


def test_strangers_and_anon_see_nothing(pg):
    assert pg("select count(*) from public.visits;", "stranger").stdout.strip() == "0"
    r = pg(_visit("SWHT-PP-003-0109")[1], "stranger", check=False)
    assert r.returncode != 0
    r = pg("set role anon; select count(*) from public.visits;", check=False)
    assert r.returncode != 0 and "permission denied" in r.stderr


def test_allocate_pid_respects_blocks_and_skips_used_numbers(pg):
    pg(_visit("SWHT-PP-003-0002")[1], "op1")                           # a typed label already used 0002
    got = [pg("select public.allocate_pid('tab-A');", "op1").stdout.strip() for _ in range(2)]
    assert got == ["SWHT-PP-003-0001", "SWHT-PP-003-0003"]
    r = pg("select public.allocate_pid('tab-A');", "op1", check=False)
    assert r.returncode != 0 and "exhausted" in r.stderr
    assert pg("select public.allocate_pid('tab-B');", "op2").stdout.strip() == "SWHT-PP-003-1000"
    r = pg("insert into public.devices values ('tab-C', 'unit_01', 1500, 2500, 1500);", check=False)
    assert r.returncode != 0 and "conflicting key value violates exclusion constraint" in r.stderr
    r = pg("select public.allocate_pid('tab-B');", "exporter", check=False)
    assert r.returncode != 0 and "not allowed" in r.stderr


def test_locked_visits_are_frozen_except_for_admin(pg):
    vu, sql = _visit("SWHT-PP-003-0110")
    pg(sql, "op1")
    r = pg(f"update public.visits set locked = true where visit_uuid = '{vu}';", "op1", check=False)
    assert r.returncode != 0 and "only an admin" in r.stderr
    pg(f"update public.visits set locked = true where visit_uuid = '{vu}';", "admin")
    r = pg(_visit("SWHT-PP-003-0110", vu, extra=', "age": 50')[1], "op1", check=False)
    assert r.returncode != 0 and "locked" in r.stderr
    r = pg(f"update public.visits set pid = 'SWHT-PP-003-0111' where visit_uuid = '{vu}';", "admin", check=False)
    assert r.returncode != 0 and "cannot change" in r.stderr


# ---------------------------------------------------------------------------------------------- 0002: two parts per PID
def _part(pid, part, crf=None, status="submitted", stream="development", vu=None, user_op="op1", submitted="now()"):
    """A v2 part upload (enrol or scan) as the app sends it; crf gets study_id and part like the engine's export."""
    vu = vu or str(uuid.uuid4())
    body = json.dumps({"study_id": pid, "part": part, **(crf or {})}).replace("'", "''")
    st = "null" if stream is None else f"'{stream}'"
    return vu, f"""insert into public.visits (visit_uuid, pid, part, status, crf, schema_version, app_ver, device_code, operator_code, stream,
        created_at, updated_at, submitted_at)
      values ('{vu}', '{pid}', '{part}', '{status}', '{body}'::jsonb, '2026-10-24.1', '2.0', 'tab-A', '{user_op}', {st}, {submitted}, {submitted},
        {submitted if status == 'submitted' else 'null'})
      on conflict (visit_uuid) do update set status = excluded.status, crf = excluded.crf, updated_at = excluded.updated_at;"""


ENROL_CRF = {"stream": "development", "dept": "cardiology", "age": 58, "sex": "F", "height_cm": 155.0, "weight_kg": 60.0,
             "bmi": 25.0, "mst_band": 8, "conditions": ["htn", "diabetes"], "htn_meds": "two", "htn_meds_today": "yes",
             "dm_type": "t2", "dm_years": 6, "dm_treatment": "tablets", "transfusion_3m": "no", "hb_gdl": 11.4,
             "hb_date": "2026-09-30", "hba1c_pct": 7.2, "hba1c_date": "2026-09-30", "anaemia_grade": "mild",
             "haem_cell": "anaemia_other", "dm_label": "documented_hba1c", "acute_30m": ["none"],
             "strata": ["sex:F", "mst:8", "mstgrp:dark", "cond:htn", "cond:diabetes", "haem:anaemia_other",
                        "dm:documented_hba1c", "sex_mst:F:8", "cond_mstgrp:htn:dark", "cond_mstgrp:diabetes:dark",
                        "haem_mstgrp:anaemia_other:dark"],
             "operator": "op1", "unit_id": "unit_01", "app_ver": "2.0", "device_code": "tab-A", "capture_mode": "simultaneous",
             "schema_version": "2026-10-24.1"}
SCAN_CRF = {"imaged_hand": "left", "arm_circumference_cm": 29.5, "cuff_size": "adult",
            "bp1": {"sbp": 142, "dbp": 88, "hr": 76, "wall_ts": "2026-10-24T10:00:00+05:30"},
            "bp2": {"sbp": 136, "dbp": 84, "hr": 72, "wall_ts": "2026-10-24T10:06:00+05:30"}, "irregular_pulse": False,
            "clip1": {"started_at": "2026-10-24T10:07:00+05:30", "ended_at": "2026-10-24T10:08:00+05:30", "quality": "pass",
                      "video_grade": "good", "ecg_grade": "borderline", "ecg_samples": 18012, "kardia_determination": "nsr",
                      "kardia_hr": 71, "phone_duration_s": 60.2, "phone_interrupted": False,
                      "video_metrics": {"snr_db": 4.5, "pulse_bpm": 70.8}, "ecg_metrics": {"hr_bpm": 71.3}},
            "bp3": {"sbp": 134, "dbp": 83, "hr": 70, "wall_ts": "2026-10-24T10:09:30+05:30"},
            "recovery": "pass", "bracket_flag": False, "scan_strata": ["rhythm:nsr", "scan:done"], "clip_plan": "1x60",
            "operator": "op2", "unit_id": "unit_01", "app_ver": "2.0", "device_code": "tab-B", "capture_mode": "simultaneous",
            "schema_version": "2026-10-24.1"}


def test_v1_rows_become_full_and_parts_coexist_per_pid(pg):
    assert pg("select part from public.visits where pid = 'SWHT-PP-003-0900';").stdout.strip() == "full"
    pg(_part("SWHT-PP-003-0201", "enrol", ENROL_CRF)[1], "op1")
    pg(_part("SWHT-PP-003-0201", "scan", SCAN_CRF, user_op="op2")[1], "op2")      # second phone, same PID
    assert pg("select string_agg(part, ',' order by part) from public.visits where pid = 'SWHT-PP-003-0201';").stdout.strip() == "enrol,scan"
    r = pg(_part("SWHT-PP-003-0201", "scan", SCAN_CRF)[1], "op1", check=False)    # another scan record for the PID
    assert r.returncode != 0 and "23505" in r.stderr and "visits_pid_part_key" in r.stderr
    r = pg(_visit("SWHT-PP-003-0201")[1], "op1", check=False)                    # a v1 full record next to split parts
    assert r.returncode != 0 and "23505" in r.stderr
    r = pg(_part("SWHT-PP-003-0900", "enrol", {})[1], "op1", check=False)         # split part next to a v1 full record
    assert r.returncode != 0 and "23505" in r.stderr
    r = pg(_part("SWHT-PP-003-0202", "scan", {"part": "enrol"})[1].replace('"part": "scan", ', ""), "op1", check=False)
    assert r.returncode != 0 and "crf_part_matches" in r.stderr
    r = pg(_part("SWHT-PP-003-0202", "both")[1], "op1", check=False)
    assert r.returncode != 0 and "visits_part_check" in r.stderr


def test_part_is_immutable_and_retries_stay_idempotent(pg):
    vu, sql = _part("SWHT-PP-003-0203", "enrol", ENROL_CRF, status="draft")
    pg(sql, "op1")
    pg(_part("SWHT-PP-003-0203", "enrol", ENROL_CRF, vu=vu)[1], "op1")           # same visit_uuid: an update, no conflict
    assert pg("select status from public.visits where visit_uuid = '%s';" % vu).stdout.strip() == "submitted"
    r = pg(f"update public.visits set part = 'scan' where visit_uuid = '{vu}';", "admin", check=False)
    assert r.returncode != 0 and "part of a visit cannot change" in r.stderr


def test_strata_counts_distinct_submitted_pids(pg):
    s = "model_selection"
    assert pg("select key || '=' || n from public.strata_counts('model_selection') order by key;", "op1").stdout.split() == [
        "mst:8=1", "mstgrp:dark=1", "sex:M=1", "sex_mst:M:8=1"]                    # the v1 record: sex / MST keys only
    rows = [("0301", "enrol", "submitted", ["sex:F", "mst:5", "cond:htn", "cond:htn"]),   # a repeated key counts once
            ("0302", "enrol", "submitted", ["sex:F", "mst:7", "cond:af"]),
            ("0303", "enrol", "draft", ["sex:F", "mst:7"]),                        # drafts and screen failures excluded
            ("0304", "enrol", "screen_fail", ["sex:M"]),
            ("0301", "scan", "submitted", None),
            ("0302", "scan", "draft", None)]
    for n, part, status, keys in rows:
        crf = {"strata": keys} if part == "enrol" else {"scan_strata": ["rhythm:af", "scan:done"], "strata": ["sex:M"]}
        # scan parts carry no stream: they take their PID's enrol stream
        pg(_part(f"SWHT-PP-003-{n}", part, crf, status=status, stream=(s if part == "enrol" else None))[1], "op1")
    got = dict(line.split("|") for line in pg(f"select key, n from public.strata_counts('{s}');", "exporter").stdout.split())
    assert got == {"sex:F": "2", "mst:5": "1", "mst:7": "1", "cond:htn": "1", "cond:af": "1", "rhythm:af": "1", "scan:done": "1",
                   "sex:M": "1", "mst:8": "1", "mstgrp:dark": "1", "sex_mst:M:8": "1"}
    everything = dict(line.split("|") for line in pg("select key, n from public.strata_counts();", "admin").stdout.split())
    assert int(everything["sex:F"]) >= 2 and everything["rhythm:af"] == "1"
    r = pg("select * from public.strata_counts();", "stranger", check=False)
    assert r.returncode != 0 and "not allowed" in r.stderr
    r = pg("set role anon; select * from public.strata_counts();", check=False)
    assert r.returncode != 0 and "permission denied" in r.stderr


def test_scan_queue_lists_recent_enrolments_without_a_submitted_scan(pg):
    base = {"sex": "M", "age": 47, "mst_band": 6, "conditions": ["af"]}
    pg(_part("SWHT-PP-003-0401", "enrol", base)[1], "op1")                                    # waiting
    pg(_part("SWHT-PP-003-0402", "enrol", base)[1], "op1")
    pg(_part("SWHT-PP-003-0402", "scan", {})[1], "op2")                                       # scanned: gone
    pg(_part("SWHT-PP-003-0403", "enrol", base)[1], "op1")
    pg(_part("SWHT-PP-003-0403", "scan", {}, status="draft")[1], "op2")                      # scan still a draft: listed
    pg(_part("SWHT-PP-003-0404", "enrol", base, submitted="now() - interval '5 days'")[1], "op1")  # too old
    pg(_part("SWHT-PP-003-0405", "enrol", base, status="draft")[1], "op1")                   # enrolment not submitted
    out = pg("select pid, sex, age, mst_band, array_to_string(conditions, ';') from public.scan_queue() "
             "where pid between 'SWHT-PP-003-0400' and 'SWHT-PP-003-0499' order by pid;", "op2").stdout.split()
    assert out == ["SWHT-PP-003-0401|M|47|6|af", "SWHT-PP-003-0403|M|47|6|af"]
    out = pg("select count(*) from public.scan_queue(7) where pid between 'SWHT-PP-003-0400' and 'SWHT-PP-003-0499';", "op2").stdout.strip()
    assert out == "3"
    r = pg("select * from public.scan_queue();", "stranger", check=False)
    assert r.returncode != 0 and "not allowed" in r.stderr


def test_participant_export_puts_both_parts_on_one_row(pg):
    pg(_part("SWHT-PP-003-0501", "enrol", ENROL_CRF)[1], "op1")
    pg(_part("SWHT-PP-003-0501", "scan", SCAN_CRF)[1], "op2")
    cols = "pid, parts, stream, enrol_status, scan_status, enrol_operator, scan_operator, scan_device_code, age, sex, bmi, " \
           "conditions, hb_date, hplc_reflex, bp1_sbp, bp3_hr, irregular_pulse, clip1_video_grade, clip1_ecg_samples, " \
           "clip1_kardia_determination, clip1_phone_duration_s, clip1_phone_interrupted, clip1_snr_db, clip1_pulse_bpm, " \
           "clip1_hr_bpm, clip1b_start, scan_strata, clip_plan, enrol_uploaded_at is not null, scan_uploaded_at is not null"
    out = pg(f"select {cols} from public.participant_export where pid = 'SWHT-PP-003-0501';", "exporter").stdout.strip()
    assert out == ("SWHT-PP-003-0501|enrol;scan|development|submitted|submitted|op1|op2|tab-B|58|F|25.0|htn;diabetes|2026-09-30||"
                   "142|70|f|good|18012|nsr|60.2|f|4.5|70.8|71.3||rhythm:nsr;scan:done|1x60|t|t")
    types = dict(line.split("|") for line in pg(
        "select column_name, data_type from information_schema.columns where table_name = 'participant_export';").stdout.split("\n") if line)
    assert (types["age"], types["bmi"], types["hb_date"], types["irregular_pulse"], types["conditions"]) == (
        "integer", "numeric", "date", "boolean", "text")
    back = json.loads(pg("select enrol_json from public.participant_export where pid = 'SWHT-PP-003-0501';", "exporter").stdout)
    assert back["strata"] == ENROL_CRF["strata"]
    # an odd value (a string where a number belongs) gives an empty cell instead of breaking the export
    pg(_part("SWHT-PP-003-0502", "enrol", dict(ENROL_CRF, age="fifty", hb_date="2026-02-30"))[1], "op1")
    assert pg("select coalesce(age::text, '-') || coalesce(hb_date::text, '-') from public.participant_export "
              "where pid = 'SWHT-PP-003-0502';", "exporter").stdout.strip() == "--"
    # a v1 record shows on one row as 'full', with its CRF in enrol_json
    out = pg("select parts, enrol_status, scan_status, mst_band, scan_json is null, enrol_json::jsonb ->> 'study_id' "
             "from public.participant_export where pid = 'SWHT-PP-003-0900';", "exporter").stdout.strip()
    assert out == "full|submitted|submitted|8|t|SWHT-PP-003-0900"
    assert pg("select count(*) from public.participant_export group by pid having count(*) > 1;", "admin").stdout.strip() == ""
    assert pg("select part from public.crf_export where pid = 'SWHT-PP-003-0900';", "exporter").stdout.strip() == "full"


def test_export_and_targets_are_read_only_for_exporter_and_closed_to_anon(pg):
    r = pg("insert into public.participant_export (pid) values ('SWHT-PP-003-0601');", "exporter", check=False)
    assert r.returncode != 0
    r = pg("update public.recruitment_targets set target = 1 where key = 'sex:F' returning key;", "exporter")
    assert r.stdout.strip() == ""                                                           # RLS: nothing to update
    assert pg("select target from public.recruitment_targets where key = 'sex:F';").stdout.strip() != "1"
    r = pg("insert into public.recruitment_targets (key, group_id, group_label, label, target, weight) "
           "values ('x:y', 'g', 'G', 'X', 1, 0.5);", "op1", check=False)
    assert r.returncode != 0 and "row-level security" in r.stderr
    assert int(pg("select count(*) from public.recruitment_targets;", "op1").stdout) > 0
    assert pg("select count(*) from public.recruitment_targets;", "stranger").stdout.strip() == "0"
    pg("update public.recruitment_targets set target = target where key = 'sex:F';", "admin")
    for obj in ("public.participant_export", "public.recruitment_targets", "public.crf_export"):
        r = pg(f"set role anon; select count(*) from {obj};", check=False)
        assert r.returncode != 0 and "permission denied" in r.stderr
    r = pg("set role anon; select * from public.scan_queue();", check=False)
    assert r.returncode != 0 and "permission denied" in r.stderr
    assert pg("select count(*) from public.participant_export;", "stranger").stdout.strip() == "0"


TARGETS = ROOT / "configs" / "recruitment_targets.json"


@pytest.mark.skipif(not TARGETS.exists(), reason="configs/recruitment_targets.json not written yet")
def test_recruitment_targets_seed_equals_the_config(pg):
    t = json.loads(TARGETS.read_text())
    want = [(c["key"], g["id"], g["label"], c["label"], c["target"], float(g["weight"]), i)
            for i, (g, c) in enumerate(((g, c) for g in t["groups"] for c in g["cells"]), start=1)]
    out = pg("select key, group_id, group_label, label, target, weight, sort_order from public.recruitment_targets "
             "where active order by sort_order;", "op1").stdout.strip().split("\n")
    got = [(k, gi, gl, lab, int(n), float(w), int(o)) for k, gi, gl, lab, n, w, o in (line.split("|") for line in out)]
    assert got == want


# Exported question ids of the v2 design (sections 2.2-2.4), used while configs/crf_schema.json is still v1.
DESIGN_ENROL = ("study_id stream dept age sex pregnant gestational_age_weeks trimester height_cm weight_kg bmi mst_band conditions "
                "htn_meds htn_meds_today af_pattern anticoagulant arrhythmia_type cardiac_device dm_type dm_years dm_treatment "
                "thal_type thal_transfusions iron_therapy on_dialysis transfusion_3m last_transfusion_date hb_gdl hb_date rbc_mill "
                "mcv_fl mch_pg rdw_pct mentzer hplc_reflex ferritin_ngml ferritin_date hplc_result hba2_pct hbf_pct hbe_pct "
                "hplc_date hba1c_pct hba1c_date anaemia_grade haem_cell dm_label acute_30m last_meal_h glucose_mgdl strata "
                "enrol_notes").split()
DESIGN_SCAN = ("imaged_hand arm_circumference_cm cuff_size bp1 bp2 irregular_pulse clip1 clip1b clip2 clip2b bp3 adverse_event "
               "recovery bracket_flag scan_strata scan_notes").split()
BP_TYPE = {"bp1", "bp2", "bp3"}
CLIP_TYPE = {"clip1", "clip1b", "clip2", "clip2b"}
CLIP_COLS = ("start", "end", "quality", "video_grade", "ecg_grade", "ecg_samples", "kardia_determination", "phone_duration_s",
             "phone_interrupted", "snr_db", "pulse_bpm", "hr_bpm")
CONTEXT = ("status", "operator", "unit_id", "app_ver", "device_code", "capture_mode", "schema_version", "submitted_at", "uploaded_at")


def _exported(schema):
    """(id, type) of every question the engine's export() writes: computed only with export true, never info,
    never export false or identity-store questions."""
    for sc in schema["screens"]:
        for q in sc["questions"]:
            if q["type"] == "info" or q.get("export") is False or q.get("store") == "identity":
                continue
            if q["type"] == "computed" and not q.get("export"):
                continue
            yield q.get("export_key", q["id"]), q["type"]


def _columns_for(qid, qtype):
    if qid == "study_id":
        return ["pid"]
    if qtype == "bp" or qid in BP_TYPE:
        return [f"{qid}_{k}" for k in ("sbp", "dbp", "hr", "ts")]
    if qtype == "clip" or qid in CLIP_TYPE:
        return [f"{qid}_{k}" for k in CLIP_COLS]
    return [qid]


def test_participant_export_has_a_column_for_every_exported_question(pg):
    cols = set(pg("select column_name from information_schema.columns where table_name = 'participant_export';").stdout.split())
    schema = json.loads((ROOT / "configs" / "crf_schema.json").read_text())
    design = [(q, None) for q in DESIGN_ENROL + DESIGN_SCAN]
    sources = [design] + ([list(_exported(schema))] if "enrol" in schema.get("flows", {}) else [])   # v2 schema: check it too
    for qs in sources:
        missing = [c for q, t in qs for c in _columns_for(q, t) if c not in cols]
        assert not missing, f"participant_export lacks columns for: {missing}"
    missing = [f"{p}_{k}" for p in ("enrol", "scan") for k in CONTEXT if f"{p}_{k}" not in cols]
    assert not missing and {"clip_plan", "enrol_json", "scan_json", "parts"} <= cols
