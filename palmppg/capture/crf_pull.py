"""Pull onboarding-app CRFs from Supabase into the study tree the pipeline reads (CONTRACTS section 3.7).

    SUPABASE_URL=... SUPABASE_ANON_KEY=... SUPABASE_EXPORTER_EMAIL=... SUPABASE_EXPORTER_PASSWORD=... \\
        palmppg crf pull --study-root data/study

Signs in as the read-only exporter account, pages through public.visits (1000 rows a request), and for every
submitted visit writes participants/<PID>/crf.json when its content changed. Screen failures go to
onboarding/screen_failures.csv (STARD flow counts); every pull writes onboarding/crf_export_<UTC>.csv as a snapshot
(the free Supabase plan keeps no backups) and appends onboarding/pull_log.jsonl. Identity is never requested: the
exporter account cannot read it and the CRF table refuses identity keys.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from palmppg.core.crf import validate_crf

PAGE = 1000
SELECT = "visit_uuid,pid,status,crf,schema_version,app_ver,device_code,operator_code,stream,created_at,updated_at,submitted_at,screen_fail_reason,server_received_at,locked"


class PullError(RuntimeError):
    pass


def _request(url: str, headers: dict, data: bytes | None = None, method: str | None = None) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def sign_in(url: str, anon_key: str, email: str, password: str) -> str:
    code, body = _request(f"{url.rstrip('/')}/auth/v1/token?grant_type=password",
                          {"apikey": anon_key, "Content-Type": "application/json"},
                          json.dumps({"email": email, "password": password}).encode(), "POST")
    if code != 200:
        raise PullError(f"sign-in failed: HTTP {code} {body[:200]!r}")
    return json.loads(body)["access_token"]


def fetch_visits(url: str, anon_key: str, token: str, page: int = PAGE) -> list[dict]:
    rows: list[dict] = []
    start = 0
    while True:
        code, body = _request(f"{url.rstrip('/')}/rest/v1/visits?select={SELECT}&order=pid.asc",
                              {"apikey": anon_key, "Authorization": f"Bearer {token}", "Range-Unit": "items",
                               "Range": f"{start}-{start + page - 1}"})
        if code == 416:
            break
        if code not in (200, 206):
            raise PullError(f"fetch failed: HTTP {code} {body[:200]!r}")
        part = json.loads(body)
        rows.extend(part)
        if len(part) < page:
            break
        start += page
    return rows


def _sha(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def write_study_tree(rows: list[dict], study_root: str | Path, now: dt.datetime | None = None) -> dict:
    """Write crf.json per submitted visit (only when changed), the screen-failure list and a CSV snapshot."""
    now = now or dt.datetime.now(dt.timezone.utc)
    root = Path(study_root)
    onboarding = root / "onboarding"
    onboarding.mkdir(parents=True, exist_ok=True)
    summary = {"pulled_utc": now.isoformat(), "n_rows": len(rows), "written": [], "unchanged": 0, "screen_fail": 0,
               "draft": 0, "void": 0, "problems": {}}
    fails = []
    for r in rows:
        status, pid, crf = r.get("status"), r.get("pid"), r.get("crf") or {}
        if any(k in crf for k in ("name", "phone", "hospital_reg_no")):
            raise PullError(f"{pid}: identity keys found in a CRF; refusing to write")
        if status == "screen_fail":
            summary["screen_fail"] += 1
            fails.append({"pid": pid, "dept": crf.get("dept"), "stream": r.get("stream"), "created_at": r.get("created_at"),
                          "reason": r.get("screen_fail_reason"), "operator_code": r.get("operator_code")})
            continue
        if status in ("draft", "void"):
            summary[status] += 1
            continue
        probs = validate_crf(crf)
        if probs:
            summary["problems"][pid] = probs
        path = root / "participants" / pid / "crf.json"
        if path.exists() and _sha(json.loads(path.read_text(encoding="utf-8"))) == _sha(crf):
            summary["unchanged"] += 1
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(crf, indent=1, ensure_ascii=False), encoding="utf-8")
        summary["written"].append(pid)
    with open(onboarding / "screen_failures.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["pid", "dept", "stream", "created_at", "reason", "operator_code"])
        w.writeheader()
        w.writerows(fails)
    snap = onboarding / f"crf_export_{now.strftime('%Y%m%dT%H%M%SZ')}.csv"
    cols = [c for c in SELECT.split(",") if c != "crf"] + ["crf_json"]
    with open(snap, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({**{c: r.get(c) for c in cols if c != "crf_json"}, "crf_json": json.dumps(r.get("crf"), ensure_ascii=False)})
    summary["snapshot"] = str(snap)
    with open(onboarding / "pull_log.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps({k: v for k, v in summary.items() if k != "written"} | {"n_written": len(summary["written"])}) + "\n")
    return summary


def pull(study_root: str | Path, url: str | None = None, anon_key: str | None = None, email: str | None = None,
         password: str | None = None) -> dict:
    url = url or os.environ.get("SUPABASE_URL")
    anon_key = anon_key or os.environ.get("SUPABASE_ANON_KEY")
    email = email or os.environ.get("SUPABASE_EXPORTER_EMAIL")
    password = password or os.environ.get("SUPABASE_EXPORTER_PASSWORD")
    missing = [n for n, v in (("SUPABASE_URL", url), ("SUPABASE_ANON_KEY", anon_key), ("SUPABASE_EXPORTER_EMAIL", email),
                              ("SUPABASE_EXPORTER_PASSWORD", password)) if not v]
    if missing:
        raise PullError("missing settings: " + ", ".join(missing))
    token = sign_in(url, anon_key, email, password)
    return write_study_tree(fetch_visits(url, anon_key, token), study_root)
