"""sync_marker: pattern specs, schedule placement, MockPin edges, log format and the compressed CLI run (section 4.2)."""
from __future__ import annotations

import csv
import itertools
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from palmppg.capture import sync_marker as sm

ROOT = Path(__file__).resolve().parents[1]
UNIT_CONFIG = ROOT / "configs" / "unit_config.yaml"
T0 = 4_000_000_000_000  # some CLOCK_BOOTTIME ns


@pytest.fixture
def patterns():
    return sm.load_marker_patterns(UNIT_CONFIG)


def _read(csv_path: Path) -> list[dict]:
    with open(csv_path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _expected_sequence(patterns) -> list[tuple[str, str, float]]:
    """(pattern, kind, nominal gap to the previous edge in s) for the 10 edges of one P1 + P2 run."""
    seq = []
    for name in ("P1", "P2"):
        prev = None
        for off, kind in sm.pattern_edge_offsets_s(patterns[name]):
            seq.append((name, kind, (off - prev) if prev is not None else None))
            prev = off
    return seq


# --------------------------------------------------------------------------- specs and planning
def test_pattern_specs_from_unit_config(patterns):
    assert patterns["P1"]["pulses"] == 3 and patterns["P1"]["on_ms"] == 100 and patterns["P1"]["off_ms"] == 200
    assert patterns["P2"]["pulses"] == 2 and patterns["P2"]["on_ms"] == 300 and patterns["P2"]["off_ms"] == 300
    e1 = sm.pattern_edge_offsets_s(patterns["P1"])
    assert e1 == [(0.0, "start"), (0.1, "end"), (0.3, "start"), (0.4, "end"), (0.6, "start"), (0.7, "end")]
    assert sm.pattern_duration_s(patterns["P1"]) == pytest.approx(0.7)
    assert sm.pattern_duration_s(patterns["P2"]) == pytest.approx(0.9)


def test_load_marker_patterns_rejects_missing_keys():
    with pytest.raises(KeyError):
        sm.load_marker_patterns({"marker": {"p1": {"pulses": 3, "on_ms": 100, "off_ms": 200}}})
    with pytest.raises(KeyError):
        sm.load_marker_patterns({"marker": {"p1": {"pulses": 3, "on_ms": 100}, "p2": {"pulses": 2, "on_ms": 1, "off_ms": 1}}})


def test_plan_schedule_before_end_and_kardia_fallback(patterns):
    plan = sm.plan_schedule(patterns, T0, 60.0, kardia_duration_s=60.0)
    assert plan["p1_mono_ns"] == T0 + 2_000_000_000
    assert plan["p2_mono_ns"] == T0 + 55_000_000_000
    assert plan["p2_mode"] == "before_end" and not plan["overlap"]
    assert [n for _, n in plan["order"]] == ["P1", "P2"]
    # 30 s Kardia app: P2 moves to t_start + 28 s (section 4.3) and the effective mode says so
    plan30 = sm.plan_schedule(patterns, T0, 60.0, kardia_duration_s=30.0)
    assert plan30["p2_mono_ns"] == T0 + 28_000_000_000
    assert plan30["p2_mode"] == "after_start" and plan30["p2_mode_requested"] == "before_end"
    # explicit after_start mode from config
    pats = {k: dict(v) for k, v in patterns.items()}
    pats["P2"]["mode"] = "after_start"
    assert sm.plan_schedule(pats, T0, 60.0)["p2_mono_ns"] == T0 + 28_000_000_000
    # compressed 8 s clip: P2 at 3 s, no overlap with P1 (2.0 .. 2.7 s)
    plan8 = sm.plan_schedule(patterns, T0, 8.0)
    assert plan8["p2_mono_ns"] == T0 + 3_000_000_000 and not plan8["overlap"]
    # 7 s clip: P2 at 2 s overlaps P1
    assert sm.plan_schedule(patterns, T0, 7.0)["overlap"]
    pats["P2"]["mode"] = "sideways"
    with pytest.raises(ValueError):
        sm.plan_schedule(pats, T0, 60.0)


# --------------------------------------------------------------------------- timing primitives
def test_sleep_until_overshoot_and_cancel():
    target = sm.mono_ns() + 20_000_000
    assert sm.sleep_until(target) is True
    overshoot_ms = (sm.mono_ns() - target) / 1e6
    assert 0.0 <= overshoot_ms < 2.0
    ev = threading.Event()
    ev.set()
    t = time.perf_counter()
    assert sm.sleep_until(sm.mono_ns() + 2_000_000_000, cancel=ev) is False
    assert time.perf_counter() - t < 0.5


# --------------------------------------------------------------------------- emit on MockPins
def test_emit_logs_edges_matching_pin_history(tmp_path, patterns):
    path = tmp_path / "sync_events.csv"
    with sm.SyncMarker(17, 27, patterns, path, simulate=True) as m:
        assert m.hardware is False and isinstance(m.led, sm.MockPin) and isinstance(m.buzzer, sm.MockPin)
        rows = m.emit("P1")
        assert len(rows) == 6
        assert [r["kind"] for r in rows] == ["start", "end"] * 3
        assert all(r["pattern"] == "P1" and r["gpio_ok"] is True for r in rows)
        assert [r["event_id"] for r in rows] == [1, 2, 3, 4, 5, 6]
        # LED and buzzer are driven from the same call: identical edge counts, same states, same instants
        assert [s for _, s in m.led.history] == [1, 0, 1, 0, 1, 0]
        assert [s for _, s in m.buzzer.history] == [1, 0, 1, 0, 1, 0]
        for row, (t_led, _), (t_bz, _) in zip(rows, m.led.history, m.buzzer.history):
            assert abs(row["mono_ns"] - t_led) < 1_000_000 and abs(row["mono_ns"] - t_bz) < 1_000_000
        assert m.led_is_on is False
        # spacing against the spec, within 5 ms
        t = [r["mono_ns"] / 1e9 for r in rows]
        for j, (a, b) in enumerate(itertools.pairwise(t)):
            nominal = 0.1 if j % 2 == 0 else 0.2
            assert abs((b - a) - nominal) < 0.005, (j, b - a)
        assert "P1" in m.emitted
    disk = _read(path)
    assert len(disk) == 6 and list(disk[0].keys()) == list(sm.SYNC_EVENT_COLUMNS)
    assert disk[0]["gpio_ok"] == "True"
    assert path.read_text().count("event_id") == 1


def test_log_append_continues_event_ids(tmp_path, patterns):
    path = tmp_path / "sync_events.csv"
    with sm.SyncMarker(17, 27, patterns, path, simulate=True) as m:
        m.emit("P1")
    with sm.SyncMarker(17, 27, patterns, path, simulate=True) as m2:
        rows = m2.emit("P2")
    assert [r["event_id"] for r in rows] == [7, 8, 9, 10]
    disk = _read(path)
    assert [int(r["event_id"]) for r in disk] == list(range(1, 11))
    assert path.read_text().count("event_id") == 1
    assert [r["pattern"] for r in disk] == ["P1"] * 6 + ["P2"] * 4


def test_schedule_thread_places_patterns_and_cancel_stops_it(tmp_path, patterns):
    pats = {k: dict(v) for k, v in patterns.items()}
    pats["P1"]["at_s_after_start"] = 0.2
    pats["P2"]["mode"] = "after_start"
    pats["P2"]["at_s_after_start"] = 1.2
    path = tmp_path / "sync_events.csv"
    with sm.SyncMarker(17, 27, pats, path, simulate=True) as m:
        t0 = sm.mono_ns()
        info = m.schedule(t0, 60.0)
        with pytest.raises(RuntimeError):
            m.schedule(t0, 60.0)
        assert m.wait(timeout_s=5.0)
        rows = m.rows
    assert len(rows) == 10
    assert abs(rows[0]["mono_ns"] - info["p1_mono_ns"]) < 5_000_000
    assert abs(rows[6]["mono_ns"] - info["p2_mono_ns"]) < 5_000_000
    assert abs((rows[6]["mono_ns"] - rows[0]["mono_ns"]) / 1e9 - 1.0) < 0.005
    # cancel before P1
    with sm.SyncMarker(17, 27, patterns, tmp_path / "c.csv", simulate=True) as mc:
        mc.schedule(sm.mono_ns(), 60.0)
        mc.cancel()
        assert mc.wait(timeout_s=2.0)
        assert mc.rows == []


# --------------------------------------------------------------------------- the CLI (compressed schedule)
def test_cli_simulate_eight_seconds_writes_ten_edges(tmp_path, patterns):
    out = tmp_path / "sync_events.csv"
    t = time.perf_counter()
    proc = subprocess.run([sys.executable, "-m", "palmppg.capture.sync_marker", "--simulate", "--seconds", "8",
                           "--out", str(out)], capture_output=True, text=True, cwd=ROOT, timeout=30, check=False)
    elapsed = time.perf_counter() - t
    assert proc.returncode == 0, proc.stderr
    assert elapsed < 8.0
    rows = _read(out)
    assert len(rows) == 10
    assert list(rows[0].keys()) == ["event_id", "kind", "pattern", "mono_ns", "wall_ns", "gpio_ok"]
    seq = _expected_sequence(patterns)
    assert [(r["pattern"], r["kind"]) for r in rows] == [(p, k) for p, k, _ in seq]
    assert all(r["gpio_ok"] == "True" for r in rows)
    assert [int(r["event_id"]) for r in rows] == list(range(1, 11))
    mono = [int(r["mono_ns"]) for r in rows]
    wall = [int(r["wall_ns"]) for r in rows]
    assert mono == sorted(mono)
    # inter-edge spacing within 5 ms of the pattern spec (gaps inside each pattern)
    for i, (_, _, gap) in enumerate(seq):
        if gap is None:
            continue
        measured = (mono[i] - mono[i - 1]) / 1e9
        assert abs(measured - gap) < 0.005, (i, measured, gap)
        assert abs((wall[i] - wall[i - 1]) / 1e9 - gap) < 0.005
    # compressed placement: P2 onset at t_end - 5 s = 3 s, P1 at 2 s -> 1.0 s apart
    assert abs((mono[6] - mono[0]) / 1e9 - 1.0) < 0.005
