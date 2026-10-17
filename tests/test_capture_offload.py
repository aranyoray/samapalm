"""offload.sh and clock_sync.sh on temporary trees via subprocess (sections 4.1 and 4.6)."""
from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from palmppg.capture import capture_pi as cp

ROOT = Path(__file__).resolve().parents[1]
OFFLOAD = ROOT / "palmppg" / "capture" / "offload.sh"
CLOCK = ROOT / "palmppg" / "capture" / "clock_sync.sh"


def _run(args, env=None, timeout=60):
    e = dict(os.environ)
    if env:
        e.update(env)
    return subprocess.run([str(a) for a in args], capture_output=True, text=True, env=e, timeout=timeout, check=False)


def _touch(p: Path, content: bytes = b"x") -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)


def make_tree(root: Path) -> dict[str, Path]:
    """Three participants: A complete (ATC), B missing the phone part, C complete (PDF fallback)."""
    (root / "units" / "unit_01").mkdir(parents=True)
    _touch(root / "units" / "unit_01" / "luxmap.json", b'{"rows": 1, "cols": 1, "lux_grid": [[400]]}')
    _touch(root / "clock_sync_log.csv", b"date,time_utc,device,offset_ms_vs_phone,method,operator\n")
    parts = {}
    for sid, phone, atc in (("SWHT-PP-003-0001", True, True), ("SWHT-PP-003-0002", False, True), ("SWHT-PP-003-0003", True, False)):
        p = root / "participants" / sid
        _touch(p / "crf.json", json.dumps({"study_id": sid}).encode())
        _touch(p / "clinician.json", b"{}")
        _touch(p / "pi" / "clip1.raw", bytes(range(256)) * 4)
        _touch(p / "pi" / "clip1_pts.csv", b"frame_idx,sensor_ts_ns,wall_ns,exposure_us,analogue_gain,digital_gain,lux\n")
        _touch(p / "pi" / "clip1_meta.json", b"{}")
        _touch(p / "pi" / "sync_events.csv", b"event_id,kind,pattern,mono_ns,wall_ns,gpio_ok\n")
        if phone:
            _touch(p / "phone" / "clip1.mp4", b"\x00" * 64)
            _touch(p / "phone" / "clip1_meta.json", b"{}")
        _touch(p / "ecg" / "kardia_meta.json", b"{}")
        _touch(p / "ecg" / ("kardia_0001.atc" if atc else "kardia_0001.pdf"), b"ALIVE" if atc else b"%PDF")
        parts[sid] = p
    return parts


def n_files(root: Path, exclude: str = "MANIFEST.sha256") -> int:
    return sum(1 for p in root.rglob("*") if p.is_file() and p.name != exclude)


# --------------------------------------------------------------------------- offload.sh --check
def test_check_marks_only_complete_participants(tmp_path):
    src = tmp_path / "study"
    parts = make_tree(src)
    stale = parts["SWHT-PP-003-0002"] / "COMPLETE.flag"
    stale.write_text("bogus")
    r = _run([OFFLOAD, "--check", src])
    assert r.returncode == 0, r.stderr
    assert (parts["SWHT-PP-003-0001"] / "COMPLETE.flag").exists()
    assert (parts["SWHT-PP-003-0003"] / "COMPLETE.flag").exists()
    assert not stale.exists()
    assert "stale COMPLETE.flag removed" in r.stdout
    assert "participants: 3, complete: 2, incomplete: 1" in r.stdout
    lines = {ln.split()[0]: ln for ln in r.stdout.splitlines() if ln.startswith("SWHT-PP-003-")}
    assert lines["SWHT-PP-003-0002"].split()[1:5] == ["yes", "no", "yes", "yes"]
    assert "INCOMPLETE" in lines["SWHT-PP-003-0002"] and "COMPLETE" in lines["SWHT-PP-003-0001"]
    flag = (parts["SWHT-PP-003-0001"] / "COMPLETE.flag").read_text()
    assert "parts=pi,phone,ecg,crf" in flag and "complete_utc=" in flag
    # strict mode refuses while anything is incomplete; completing B flips it
    assert _run([OFFLOAD, "--strict", "--check", src]).returncode == 4
    _touch(parts["SWHT-PP-003-0002"] / "phone" / "clip1.mp4", b"\x00")
    _touch(parts["SWHT-PP-003-0002"] / "phone" / "clip1_meta.json", b"{}")
    r2 = _run([OFFLOAD, "--strict", "--check", src])
    assert r2.returncode == 0 and (parts["SWHT-PP-003-0002"] / "COMPLETE.flag").exists()
    # a tree without participants/ is an error, not a silent success
    assert _run([OFFLOAD, "--check", tmp_path / "nowhere"]).returncode == 1


# --------------------------------------------------------------------------- offload.sh copy + manifest + verify
def test_offload_copies_builds_manifest_and_verifies(tmp_path):
    src = tmp_path / "study"
    parts = make_tree(src)
    dest = tmp_path / "ssd"
    r = _run([OFFLOAD, src, dest])
    assert r.returncode == 0, r.stderr + r.stdout
    if shutil.which("rsync") is None:
        assert "falling back to 'cp -a'" in r.stderr
    copy = dest / "study"
    manifest = copy / "MANIFEST.sha256"
    assert manifest.exists()
    entries = [ln.split(maxsplit=1) for ln in manifest.read_text().splitlines() if ln.strip()]
    assert len(entries) == n_files(src)
    assert n_files(copy) == n_files(src)
    hashes = {rel.lstrip("*"): h for h, rel in entries}
    crf_rel = "./participants/SWHT-PP-003-0001/crf.json"
    assert hashes[crf_rel] == hashlib.sha256((parts["SWHT-PP-003-0001"] / "crf.json").read_bytes()).hexdigest()
    assert hashlib.sha256((copy / "participants/SWHT-PP-003-0001/crf.json").read_bytes()).hexdigest() == hashes[crf_rel]
    assert "./participants/SWHT-PP-003-0001/COMPLETE.flag" in hashes
    assert "./participants/SWHT-PP-003-0002/COMPLETE.flag" not in hashes
    assert "verify: all" in r.stdout
    assert _run([OFFLOAD, "--verify", copy]).returncode == 0
    # tampering with the copy is caught
    (copy / "participants/SWHT-PP-003-0003/pi/clip1.raw").write_bytes(b"corrupt")
    rv = _run([OFFLOAD, "--verify", copy])
    assert rv.returncode == 3
    assert "FAILED" in rv.stderr
    # a second offload to the same destination is a resync and verifies again (the copy is repaired)
    r3 = _run([OFFLOAD, src, dest])
    assert r3.returncode == 0, r3.stderr + r3.stdout
    assert _run([OFFLOAD, "--verify", copy]).returncode == 0
    # destination equal to the source is refused
    assert _run([OFFLOAD, src, src.parent]).returncode == 1


def test_offload_usage_errors():
    assert _run([OFFLOAD]).returncode == 1
    assert _run([OFFLOAD, "--check"]).returncode == 1


# --------------------------------------------------------------------------- clock_sync.sh
def test_clock_sync_simulate_rows_and_sign_convention(tmp_path):
    log = tmp_path / "clock_sync_log.csv"
    slow = "System time     : 0.001234567 seconds slow of NTP time"
    r = _run([CLOCK, "--simulate", "RB", "unit_01", log], env={"CLOCK_SYNC_FAKE_TRACKING": slow,
                                                               "CLOCK_SYNC_NOW_UTC": "2026-10-17 03:31:12"})
    assert r.returncode == 0, r.stderr
    fast = "Reference ID    : C0A80001 (phone)\nSystem time     : 0.250000000 seconds fast of NTP time\nLast offset     : +0.0001 seconds"
    r2 = _run([CLOCK, "--simulate", "RB", "unit_01", log], env={"CLOCK_SYNC_FAKE_TRACKING": fast,
                                                                "CLOCK_SYNC_NOW_UTC": "2026-10-17 11:31:12"})
    assert r2.returncode == 0, r2.stderr
    assert "drift since 03:31:12 today" in r2.stdout and "251.2 ms" in r2.stdout and "within" in r2.stdout
    r3 = _run([CLOCK, "--kardia", "-340", "RB", log], env={"CLOCK_SYNC_NOW_UTC": "2026-10-17 03:32:40"})
    assert r3.returncode == 0, r3.stderr
    with open(log, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert list(rows[0].keys()) == ["date", "time_utc", "device", "offset_ms_vs_phone", "method", "operator"]
    assert [r["device"] for r in rows] == ["pi_unit_01", "pi_unit_01", "kardia_tablet"]
    assert [float(r["offset_ms_vs_phone"]) for r in rows] == [-1.235, 250.0, -340.0]
    assert [r["method"] for r in rows] == ["chronyd_makestep", "chronyd_makestep", "manual_ntp_app"]
    assert all(r["date"] == "2026-10-17" and r["operator"] == "RB" for r in rows)
    assert rows[1]["time_utc"] == "11:31:12"
    assert log.read_text().count("date,time_utc") == 1
    # the row the script wrote satisfies capture_pi's gate for that day and refuses for the next day
    assert cp.check_clock_stepped_today(log, "unit_01", "2026-10-17")["ok"] is True
    assert cp.check_clock_stepped_today(log, "unit_01", "2026-10-18")["ok"] is False


def test_clock_sync_drift_flag_and_errors(tmp_path):
    log = tmp_path / "clock_sync_log.csv"
    env0 = {"CLOCK_SYNC_FAKE_TRACKING": "System time     : 0.000000000 seconds fast of NTP time",
            "CLOCK_SYNC_NOW_UTC": "2026-10-17 03:00:00"}
    assert _run([CLOCK, "--simulate", "RB", "unit_01", log], env=env0).returncode == 0
    env1 = {"CLOCK_SYNC_FAKE_TRACKING": "System time     : 0.900000000 seconds fast of NTP time",
            "CLOCK_SYNC_NOW_UTC": "2026-10-17 07:00:00"}
    r = _run([CLOCK, "--simulate", "RB", "unit_01", log], env=env1)
    assert r.returncode == 0 and "1800.0 ms per 8 h" in r.stdout and "FLAG" in r.stdout
    # errors: missing operator, bad Kardia offset, missing System time line
    assert _run([CLOCK]).returncode == 1
    assert _run([CLOCK, "--kardia", "abc", "RB", log]).returncode == 1
    bad = _run([CLOCK, "--simulate", "RB", "unit_01", log], env={"CLOCK_SYNC_FAKE_TRACKING": "Stratum : 3"})
    assert bad.returncode == 1 and "System time" in bad.stderr
    assert _run([CLOCK, "--simulate", "R,B", "unit_01", log]).returncode == 1
    with open(log, encoding="utf-8", newline="") as fh:
        assert len(list(csv.DictReader(fh))) == 2


@pytest.mark.skipif(shutil.which("chronyc") is not None, reason="chronyc present: the real path would run")
def test_clock_sync_without_chronyc_refuses_clearly(tmp_path):
    r = _run([CLOCK, "RB", "unit_01", tmp_path / "log.csv"])
    assert r.returncode == 1 and "chronyc not found" in r.stderr
    assert not (tmp_path / "log.csv").exists()
