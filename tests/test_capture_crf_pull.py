"""palmppg crf pull against a local fake of Supabase auth + PostgREST (Range paging, statuses, change detection)."""
import csv
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from palmppg.capture.crf_pull import PullError, pull
from palmppg.core.crf import validate_crf

ROOT = Path(__file__).resolve().parents[1]
GOOD = next(c for c in json.loads((ROOT / "configs/crf_fixtures/golden.json").read_text())["cases"] if c["name"] == "complete_male_1x60")["full"]["export"]


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
    assert crf["study_id"] == "SWHT-PP-003-0001" and validate_crf(crf) == [] and "name" not in crf
    assert not (tmp_path / "participants" / "SWHT-PP-003-0050").exists()
    fails = list(csv.DictReader(open(tmp_path / "onboarding" / "screen_failures.csv")))
    assert len(fails) == n_fail and fails[0]["reason"] == "no consent"
    assert Path(r["snapshot"]).exists() and r["problems"] == {}


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
