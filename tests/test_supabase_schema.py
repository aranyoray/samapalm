"""supabase/migrations/0001_init.sql on a real throwaway Postgres 16 with a stub of Supabase's auth schema.

Each check runs as the `authenticated` role with a JWT subject set, the way PostgREST runs a request, so row-level
security, grants, triggers and the security-definer functions are exercised for real.
"""
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
        r = subprocess.run(["psql", "-h", str(sock), "-U", "postgres", "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-q", "-t", "-A", "-c", prefix + sql],
                           capture_output=True, text=True)
        if check and r.returncode != 0:
            raise AssertionError(r.stderr)
        return r

    for f in (ROOT / "supabase" / "tests" / "local_auth_stub.sql", ROOT / "supabase" / "migrations" / "0001_init.sql"):
        r = subprocess.run(["psql", "-h", str(sock), "-U", "postgres", "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-q", "-f", str(f)],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
    users = ",".join(f"('{u}', '{k}@x.org')" for k, u in OPS.items())
    psql(f"insert into auth.users (id, email) values {users};")
    psql(f"""insert into public.operators (user_id, operator_code, role) values
      ('{OPS['op1']}', 'op1', 'operator'), ('{OPS['op2']}', 'op2', 'operator'), ('{OPS['admin']}', 'adm', 'admin'),
      ('{OPS['exporter']}', 'exp', 'exporter');
      insert into public.devices values ('tab-A', 'unit_01', 1, 3, 1), ('tab-B', 'unit_01', 1000, 1999, 1000);""")
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
    assert r.returncode != 0 and "visits_pid_key" in r.stderr


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
