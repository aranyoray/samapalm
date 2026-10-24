"""palmppg crf pull against a local fake of Supabase auth + PostgREST (Range paging, statuses, change detection)."""
import csv
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from palmppg.capture.crf_pull import CONTEXT as CONTEXT_KEYS
from palmppg.capture.crf_pull import PullError, pull
from palmppg.core.crf import validate_crf

ROOT = Path(__file__).resolve().parents[1]
# a v1 single-visit export (schema 2026-10-20.1, part 'full'), as v1 phones uploaded it
GOOD = {"study_id": "SWHT-PP-003-0042", "stream": "pilot", "dept": "Medicine OPD", "cohort_tags": ["core"], "imaged_hand": "left",
        "bp1": {"sbp": 138, "dbp": 86, "hr": 78, "wall_ts": "2026-10-20T10:00:00+05:30"}, "age": 52, "sex": "M", "height_cm": 168.0,
        "weight_kg": 70.0, "handedness": "right", "arm_circumference_cm": 30.0, "cuff_size": "adult", "mst_band": 7, "flags": ["none"],
        "acute_30m": ["none"], "last_meal_h": 2.5, "bp2": {"sbp": 132, "dbp": 84, "hr": 74, "wall_ts": "2026-10-20T10:06:00+05:30"},
        "irregular_pulse": False, "clip1": {"started_at": "2026-10-20T10:07:00+05:30", "ended_at": "2026-10-20T10:08:00+05:30",
                                            "quality": "pass", "kardia_on": True, "beep_heard": True, "notes": ""},
        "bp3": {"sbp": 130, "dbp": 82, "hr": 73, "wall_ts": "2026-10-20T10:09:30+05:30"}, "recovery": "pass", "bracket_flag": False,
        "operator": "op1", "unit_id": "unit_01", "app_ver": "test", "schema_version": "2026-10-20.1", "clip_plan": "1x60"}
GOLDEN = {c["name"]: c for c in json.loads((ROOT / "configs/crf_fixtures/golden.json").read_text())["cases"]}


def _rows(n):
    out = []
    for i in range(1, n + 1):
        pid = f"SWHT-PP-003-{i:04d}"
        status = "screen_fail" if i % 50 == 0 else ("draft" if i % 77 == 0 else "submitted")
        crf = dict(GOOD, study_id=pid)
        out.append({"visit_uuid": f"u{i}", "pid": pid, "status": status, "crf": crf, "stream": "pilot", "created_at": "2026-10-20T10:00:00+05:30",
                    "screen_fail_reason": "no consent" if status == "screen_fail" else None, "operator_code": "op1"})
    return out


@pytest.fixture
def server():
    state = {"rows": _rows(2100), "ranges": []}

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, obj):
            b = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            if body.get("password") != "pw":
                return self._send(400, {"error": "invalid_grant"})
            self._send(200, {"access_token": "jwt"})

        def do_GET(self):
            assert self.headers["Authorization"] == "Bearer jwt" and self.headers["apikey"] == "anon"
            assert "identity" not in self.path
            state["paths"] = state.get("paths", []) + [self.path]
            a, b = map(int, self.headers["Range"].split("-"))
            state["ranges"].append((a, b))
            rows = state["rows"]
            if a >= len(rows):
                return self._send(416, {})
            self._send(206, rows[a:b + 1])

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}", state
    srv.shutdown()


def test_pull_writes_submitted_crfs_and_lists_screen_failures(server, tmp_path):
    url, state = server
    r = pull(tmp_path, url, "anon", "exp@x.org", "pw")
    assert state["ranges"] == [(0, 999), (1000, 1999), (2000, 2999)]
    n_fail = len([i for i in range(1, 2101) if i % 50 == 0])
    n_draft = len([i for i in range(1, 2101) if i % 77 == 0 and i % 50 != 0])
    assert r["screen_fail"] == n_fail and r["draft"] == n_draft and len(r["written"]) == 2100 - n_fail - n_draft
    crf = json.loads((tmp_path / "participants" / "SWHT-PP-003-0001" / "crf.json").read_text())
    assert crf == dict(GOOD, study_id="SWHT-PP-003-0001") and "name" not in crf
    assert not (tmp_path / "participants" / "SWHT-PP-003-0050").exists()
    fails = list(csv.DictReader(open(tmp_path / "onboarding" / "screen_failures.csv")))
    assert len(fails) == n_fail and fails[0]["reason"] == "no consent"
    assert Path(r["snapshot"]).exists()
    assert r["problems"] == {} or validate_crf(GOOD) != []       # problems only if palmppg.core.crf no longer reads v1


def test_second_pull_only_writes_changes(server, tmp_path):
    url, state = server
    pull(tmp_path, url, "anon", "exp@x.org", "pw")
    state["rows"][2]["crf"] = dict(state["rows"][2]["crf"], age=53)
    r = pull(tmp_path, url, "anon", "exp@x.org", "pw")
    assert r["written"] == ["SWHT-PP-003-0003"]
    assert len((tmp_path / "onboarding" / "pull_log.jsonl").read_text().splitlines()) == 2


def test_refuses_identity_and_bad_credentials(server, tmp_path):
    url, state = server
    with pytest.raises(PullError, match="sign-in failed"):
        pull(tmp_path, url, "anon", "exp@x.org", "wrong")
    state["rows"][0]["crf"] = dict(state["rows"][0]["crf"], name="Leak")
    with pytest.raises(PullError, match="identity keys"):
        pull(tmp_path, url, "anon", "exp@x.org", "pw")


def test_missing_settings_are_named(tmp_path, monkeypatch):
    for k in ("SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_EXPORTER_EMAIL", "SUPABASE_EXPORTER_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(PullError, match="SUPABASE_URL"):
        pull(tmp_path)


def _v2(pid, part, status, crf, **row):
    ctx = {"operator": "op1" if part == "enrol" else "op2", "unit_id": "unit_01", "app_ver": "2.0",
           "device_code": "tab-A" if part == "enrol" else "tab-B", "capture_mode": "simultaneous", "schema_version": "2026-10-24.1"}
    return {"visit_uuid": f"{pid}-{part}", "pid": pid, "part": part, "status": status, "crf": {"study_id": pid, "part": part, **crf, **ctx},
            "stream": "development", "created_at": "2026-10-24T09:00:00+05:30", "operator_code": ctx["operator"],
            "submitted_at": "2026-10-24T09:20:00+05:30" if status == "submitted" else None, **row}


ENROL = {"stream": "development", "dept": "cardiology", "age": 61, "sex": "M", "mst_band": 9, "conditions": ["af"],
         "strata": ["sex:M", "mst:9", "mstgrp:dark", "cond:af"]}
SCAN = {"bp1": {"sbp": 128, "dbp": 80, "hr": 90}, "clip1": {"started_at": "2026-10-24T10:07:00+05:30", "quality": "pass",
        "kardia_determination": "af"}, "scan_strata": ["rhythm:af", "scan:done"], "clip_plan": "1x60"}


def test_parts_merge_per_pid_and_legacy_rows_stay_as_they_are(server, tmp_path):
    url, state = server
    legacy = _rows(1)[0]                                                  # v1 row: no part column value at all
    state["rows"] = [legacy,
                     _v2("SWHT-PP-003-0002", "enrol", "submitted", ENROL), _v2("SWHT-PP-003-0002", "scan", "submitted", SCAN),
                     _v2("SWHT-PP-003-0003", "enrol", "submitted", ENROL), _v2("SWHT-PP-003-0003", "scan", "draft", SCAN),
                     _v2("SWHT-PP-003-0004", "enrol", "screen_fail", {"dept": "medicine"}, screen_fail_reason="no consent"),
                     _v2("SWHT-PP-003-0005", "enrol", "submitted", dict(ENROL, age=40)),
                     _v2("SWHT-PP-003-0005", "scan", "submitted", dict(SCAN, age=41))]
    r = pull(tmp_path, url, "anon", "exp@x.org", "pw")
    assert "select=visit_uuid,pid,part,status" in state["paths"][0]
    assert r["written"] == ["SWHT-PP-003-0001", "SWHT-PP-003-0002", "SWHT-PP-003-0003", "SWHT-PP-003-0005"]
    read = lambda pid: json.loads((tmp_path / "participants" / pid / "crf.json").read_text())
    assert read("SWHT-PP-003-0001") == legacy["crf"]
    both = read("SWHT-PP-003-0002")
    assert both["study_id"] == "SWHT-PP-003-0002" and both["age"] == 61 and both["conditions"] == ["af"]
    assert both["bp1"] == SCAN["bp1"] and both["scan_strata"] == ["rhythm:af", "scan:done"] and both["clip_plan"] == "1x60"
    assert not set(CONTEXT_KEYS) & set(both) - {"parts"}
    assert both["parts"] == {
        "enrol": {"part": "enrol", "operator": "op1", "unit_id": "unit_01", "app_ver": "2.0", "device_code": "tab-A",
                  "capture_mode": "simultaneous", "schema_version": "2026-10-24.1", "status": "submitted",
                  "submitted_at": "2026-10-24T09:20:00+05:30"},
        "scan": {"part": "scan", "operator": "op2", "unit_id": "unit_01", "app_ver": "2.0", "device_code": "tab-B",
                 "capture_mode": "simultaneous", "schema_version": "2026-10-24.1", "status": "submitted",
                 "submitted_at": "2026-10-24T09:20:00+05:30"}}
    only_enrol = read("SWHT-PP-003-0003")
    assert list(only_enrol["parts"]) == ["enrol"] and "bp1" not in only_enrol
    assert r["incomplete"] == {"SWHT-PP-003-0003": "no submitted scan part yet"} and r["draft"] == 1
    assert read("SWHT-PP-003-0005")["age"] == 40
    assert "age differs between the enrol and scan parts" in r["problems"]["SWHT-PP-003-0005"]
    assert not (tmp_path / "participants" / "SWHT-PP-003-0004").exists()
    fails = list(csv.DictReader(open(tmp_path / "onboarding" / "screen_failures.csv")))
    assert [(f["pid"], f["part"], f["dept"], f["reason"]) for f in fails] == [("SWHT-PP-003-0004", "enrol", "medicine", "no consent")]
    snap = list(csv.DictReader(open(r["snapshot"])))
    assert [s["part"] for s in snap] == ["", "enrol", "scan", "enrol", "scan", "enrol", "enrol", "scan"]

    state["rows"][4] = _v2("SWHT-PP-003-0003", "scan", "submitted", SCAN)    # the scan is submitted later
    r = pull(tmp_path, url, "anon", "exp@x.org", "pw")
    assert r["written"] == ["SWHT-PP-003-0003"] and r["incomplete"] == {}
    assert list(read("SWHT-PP-003-0003")["parts"]) == ["enrol", "scan"]


def test_real_engine_exports_of_both_parts_merge_without_clashes():
    from palmppg.capture.crf_pull import merge_parts
    enrol = GOLDEN.get("enrol_complete_male", {}).get("full", {}).get("export")
    scan = GOLDEN.get("complete_male_1x60", {}).get("full", {}).get("export")
    if not (enrol and scan and enrol.get("part") == "enrol" and scan.get("part") == "scan"):
        pytest.skip("golden fixtures are not v2 two-part exports")
    rows = {p: {"pid": enrol["study_id"], "part": p, "status": "submitted", "submitted_at": "2026-10-24T10:20:00+05:30", "crf": c}
            for p, c in (("enrol", enrol), ("scan", scan))}
    rec, probs = merge_parts(rows)
    assert probs == []
    fields = lambda c: {k for k in c if k not in CONTEXT_KEYS}
    assert set(rec) == fields(enrol) | fields(scan) | {"parts"}
    assert rec["parts"]["enrol"]["operator"] == enrol["operator"] and rec["parts"]["scan"]["schema_version"] == scan["schema_version"]
