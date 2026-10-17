"""sync_events: log reading, expected edges, clip bounds, pattern specs and pulse matching (section 4.2)."""
import numpy as np
import pandas as pd
import pytest

from palmppg.ingest.sync_events import (
    check_sync_events,
    clip_bounds_s,
    expected_edges,
    gpio_ok_summary,
    match_pulse_pattern,
    nominal_pattern_onset_s,
    pattern_duration_s,
    pattern_edges,
    pattern_onsets_from_log,
    pattern_spec,
    read_sync_events,
)

T0 = 5_000_000_000_000  # first Pi frame, CLOCK_BOOTTIME ns


def _log_rows(cfg, p1_onset_s=2.0, p2_onset_s=55.0, gpio_ok=True):
    rows = []
    eid = 0
    for name, onset in (("P1", p1_onset_s), ("P2", p2_onset_s)):
        for t, kind in pattern_edges(onset, pattern_spec(cfg, name)):
            eid += 1
            mono = T0 + round(t * 1e9)
            rows.append({"event_id": eid, "kind": kind, "pattern": name, "mono_ns": mono,
                         "wall_ns": 1_760_000_000_000_000_000 + (mono - T0), "gpio_ok": gpio_ok})
    return rows


def test_read_sync_events_types_and_order(cfg, tmp_path):
    rows = _log_rows(cfg)
    rows[0]["gpio_ok"] = "True"
    rows[1]["gpio_ok"] = "false"
    df_in = pd.DataFrame(rows[::-1])  # reversed on disk: must come back time-sorted
    p = tmp_path / "sync_events.csv"
    df_in.to_csv(p, index=False)
    df = read_sync_events(p)
    assert list(df.columns) == ["event_id", "kind", "pattern", "mono_ns", "wall_ns", "gpio_ok"]
    assert df["mono_ns"].is_monotonic_increasing
    assert df["mono_ns"].dtype == np.int64
    assert df["gpio_ok"].dtype == bool
    assert df.loc[df["event_id"] == 2, "gpio_ok"].item() is np.False_ or not df.loc[df["event_id"] == 2, "gpio_ok"].item()
    assert len(df) == 10
    s = gpio_ok_summary(df)
    assert s["n_events"] == 10 and s["n_bad"] == 1 and s["bad_event_ids"] == [2] and not s["all_ok"]


def test_read_sync_events_rejects_bad_kind(cfg):
    rows = _log_rows(cfg)
    rows[3]["kind"] = "rising"
    with pytest.raises(ValueError):
        read_sync_events(pd.DataFrame(rows))


def test_expected_edges_and_onsets_on_reference_clock(cfg):
    df = read_sync_events(pd.DataFrame(_log_rows(cfg, 2.0, 55.0)))
    edges = expected_edges(df, T0)
    assert set(edges) == {"P1", "P2"}
    assert len(edges["P1"]) == 6 and len(edges["P2"]) == 4
    t1 = [t for t, _ in edges["P1"]]
    assert t1 == pytest.approx([2.0, 2.1, 2.3, 2.4, 2.6, 2.7], abs=1e-9)
    assert [k for _, k in edges["P1"]] == ["start", "end"] * 3
    t2 = [t for t, _ in edges["P2"]]
    assert t2 == pytest.approx([55.0, 55.3, 55.6, 55.9], abs=1e-9)
    assert pattern_onsets_from_log(df, T0) == pytest.approx({"P1": 2.0, "P2": 55.0}, abs=1e-9)
    # a different t0 shifts every time by the same amount
    e2 = expected_edges(df, T0 + 1_000_000_000)
    assert e2["P1"][0][0] == pytest.approx(1.0, abs=1e-9)


def test_check_sync_events_flags_timing_and_gpio(cfg):
    df = read_sync_events(pd.DataFrame(_log_rows(cfg)))
    assert check_sync_events(df, cfg) == []
    bad = df.copy()
    bad.loc[1, "mono_ns"] += 25_000_000  # 25 ms late falling edge on P1
    bad.loc[7, "gpio_ok"] = False
    issues = check_sync_events(bad, cfg)
    assert any("P1: interval 0" in s for s in issues)
    assert any("gpio_ok false" in s for s in issues)
    assert any("P2: no rows" in s for s in check_sync_events(df[df["pattern"] == "P1"], cfg))


def test_clip_bounds_from_meta():
    meta = {"start_mono_ns": T0 - 10_000_000, "stop_mono_ns": T0 + 60_000_000_000}
    cs, ce = clip_bounds_s(meta, T0)
    assert cs == pytest.approx(-0.010) and ce == pytest.approx(60.0)
    with pytest.raises(KeyError):
        clip_bounds_s({"start_mono_ns": T0}, T0)


def test_pattern_spec_and_nominal_onsets(cfg):
    p1 = pattern_spec(cfg, "P1")
    p2 = pattern_spec(cfg, "p2")
    assert p1 == {"name": "P1", "pulses": 3, "on_s": 0.1, "off_s": 0.2}
    assert p2 == {"name": "P2", "pulses": 2, "on_s": 0.3, "off_s": 0.3}
    assert pattern_duration_s(p1) == pytest.approx(0.7) and pattern_duration_s(p2) == pytest.approx(0.9)
    assert nominal_pattern_onset_s(cfg, "P1", 0.0, 60.0) == pytest.approx(2.0)
    assert nominal_pattern_onset_s(cfg, "P2", 0.0, 60.0) == pytest.approx(55.0)
    cfg30 = cfg.with_overrides({"sync": {"p2": {"mode": "after_start"}}})
    assert nominal_pattern_onset_s(cfg30, "P2", 0.0, 60.0) == pytest.approx(28.0)


def test_match_pulse_pattern_picks_best_run_and_rejects_mismatch():
    spec = {"name": "P1", "pulses": 3, "on_s": 0.1, "off_s": 0.2}
    # a stray short pulse, then the true P1 slightly early/late on each edge, then a P2-like pair
    pulses = [(0.5, 0.52), (2.0, 2.105), (2.302, 2.4), (2.6, 2.71), (5.0, 5.3), (5.6, 5.9)]
    m = match_pulse_pattern(pulses, spec, tol_on_s=0.05, tol_off_s=0.05)
    assert m is not None and m["indices"] == [1, 2, 3]
    assert m["score"] < 1.0
    assert match_pulse_pattern(pulses, {"name": "P2", "pulses": 2, "on_s": 0.3, "off_s": 0.3}, 0.05, 0.05)["indices"] == [4, 5]
    # too few pulses, or durations off by more than the tolerance
    assert match_pulse_pattern(pulses[:2], spec, 0.05, 0.05) is None
    assert match_pulse_pattern([(0, 0.1), (0.5, 0.6), (1.0, 1.1)], spec, 0.05, 0.05) is None
    # two candidate runs: the better-timed one wins
    good = [(10.0, 10.1), (10.3, 10.4), (10.6, 10.7)]
    worse = [(20.0, 20.14), (20.34, 20.44), (20.64, 20.74)]
    m2 = match_pulse_pattern(worse + good, spec, 0.05, 0.05)
    assert m2["indices"] == [3, 4, 5] and m2["score"] == pytest.approx(0.0, abs=1e-9)
