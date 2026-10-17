"""Frame times from sensor timestamps / PTS, drops with known gaps, grid resampling, clock-sync log drift."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from palmppg.core.timeline import ClockMap
from palmppg.ingest.timestamps import (
    PHONE_FRAME_TIME_COLUMNS,
    PI_FRAME_TIME_COLUMNS,
    daily_offsets,
    drop_summary,
    dropped_before_from_times,
    frame_grid,
    offset_at,
    phone_frame_times,
    pi_frame_times,
    read_clock_sync_log,
    read_frame_times,
    read_pi_pts,
    resample_frame,
    resample_series,
    write_frame_times,
)
from tests.test_ingest_helpers import write_synthetic_pi_clip

DROPPED = (10, 11, 50, 70)  # gaps of 2, 1, 1 frames -> 3 gaps, 4 frames dropped


def test_pi_frame_times_with_three_known_gaps(tmp_path, cfg):
    clip = write_synthetic_pi_clip(tmp_path / "pi", n_frames=100, width=16, height=8, dropped=DROPPED)
    df = read_pi_pts(tmp_path / "pi" / "clip1_pts.csv")
    assert list(df.columns) == ["frame_idx", "sensor_ts_ns", "wall_ns", "exposure_us", "analogue_gain", "digital_gain", "lux"]
    assert len(df) == 96 and df["sensor_ts_ns"].dtype == np.int64
    ft = pi_frame_times(df, nominal_fs=cfg.get("pi.nominal_fps"), drop_factor=cfg.get("qc.drop_factor"))
    assert list(ft.columns) == list(PI_FRAME_TIME_COLUMNS)
    assert ft.attrs["t0_ref_ns"] == clip["t0_ns"]
    assert ft["t_ref_s"].iloc[0] == 0.0
    # true times are the sensor timestamps, so frame 12 (after two dropped) sits at 12 periods
    row12 = ft[ft["frame_idx"] == 12].iloc[0]
    assert abs(row12["t_ref_s"] - 12 / 30.0) < 1e-6
    assert row12["dropped_before"] == 2
    assert ft[ft["frame_idx"] == 51]["dropped_before"].iloc[0] == 1
    assert ft[ft["frame_idx"] == 71]["dropped_before"].iloc[0] == 1
    assert int(ft["dropped_before"].sum()) == 4
    assert int((ft["dropped_before"] > 0).sum()) == 3
    d = drop_summary(ft["t_ref_s"], cfg.get("pi.nominal_fps"), cfg.get("qc.drop_factor"), cfg.get("qc.drop_pct_max"))
    assert d["n_dropped"] == 4 and len(d["gaps_idx"]) == 3
    assert abs(d["drop_pct"] - 4.0) < 0.05 and d["drop_flag"] is True
    assert abs(d["fs_median"] - 30.0) < 1e-6
    # explicit t0 shifts everything
    ft2 = pi_frame_times(df, t0_ref_ns=clip["t0_ns"] - 1_000_000_000)
    assert abs(ft2["t_ref_s"].iloc[0] - 1.0) < 1e-9
    p = write_frame_times(ft, tmp_path / "work" / "frame_times.parquet")
    back = read_frame_times(p)
    pd.testing.assert_frame_equal(back, ft)


def test_read_pi_pts_rejects_missing_columns_and_dedups(tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text("frame_idx,sensor_ts_ns\n0,1\n")
    with pytest.raises(ValueError):
        read_pi_pts(p)
    p.write_text("frame_idx,sensor_ts_ns,wall_ns,exposure_us,analogue_gain,digital_gain,lux\n"
                 "1,200,2,8000,2,1,400\n0,100,1,8000,2,1,400\n0,100,1,8000,2,1,400\n")
    df = read_pi_pts(p)
    assert df["frame_idx"].tolist() == [0, 1]


def test_dropped_before_rule_matches_detect_drops():
    t = np.arange(40) / 30.0
    t = np.delete(t, [5, 6, 7, 20])
    db = dropped_before_from_times(t, 30.0, 1.5)
    assert db.sum() == 4 and db[5] == 3 and db[20 - 3] == 1
    assert dropped_before_from_times(t[:1], 30.0, 1.5).tolist() == [0]


def test_resample_series_nan_in_gaps(cfg):
    t = np.arange(60) / 30.0
    t = np.delete(t, [20, 21])
    grid = frame_grid(t, cfg.get("grid.fs"))
    assert grid[0] == t[0] and abs(grid[-1] - t[-1]) < 1e-9 and abs(grid[1] - grid[0] - 1 / 30.0) < 1e-12
    v = resample_series(t, 2.0 * t + 1.0, grid, cfg.get("pi.nominal_fps"), cfg.get("qc.drop_factor"))
    assert np.isnan(v[20]) and np.isnan(v[21])
    ok = np.isfinite(v)
    np.testing.assert_allclose(v[ok], 2.0 * grid[ok] + 1.0, atol=1e-9)
    assert ok.sum() == grid.size - 2
    # NaN input sample becomes a gap when the surrounding interval exceeds the gap width;
    # array index 30 is the frame at t = 32/30 (two frames were deleted before it), i.e. grid slot 32
    vals = 2.0 * t + 1.0
    vals[30] = np.nan
    assert abs(t[30] - 32 / 30.0) < 1e-12
    v2 = resample_series(t, vals, grid, 30.0, 1.5)
    assert np.isnan(v2[32]) and np.isfinite(v2[31]) and np.isfinite(v2[33])
    assert np.isnan(v2).sum() == 3
    df = pd.DataFrame({"t_ref_s": t, "a": vals, "b": -vals})
    out = resample_frame(df, ["a", "b"], grid, 30.0, 1.5)
    assert list(out.columns) == ["t_ref_s", "a", "b"] and np.isnan(out["b"][32])
    with pytest.raises(ValueError):
        resample_series(t, vals[:-1], grid, 30.0, 1.5)


def test_phone_frame_times_apply_clockmap(cfg):
    pts = np.arange(50) / 30.0 + 0.2
    pts = np.delete(pts, [7, 8, 30])
    cm = ClockMap.fit([0.0, 10.0], [1.5, 11.5 + 1e-3], "phone_video", "led_pattern")
    ft = phone_frame_times(pts, cm, nominal_fs=cfg.get("phone.nominal_fps"), drop_factor=cfg.get("qc.drop_factor"))
    assert list(ft.columns) == list(PHONE_FRAME_TIME_COLUMNS)
    assert ft["frame_idx"].tolist() == list(range(47))
    np.testing.assert_allclose(ft["t_ref_s"], cm.to_ref(pts))
    assert abs(ft["t_ref_s"].iloc[0] - (0.2 * (1 + cm.drift) + cm.offset_s)) < 1e-9
    assert ft["dropped_before"].tolist()[7] == 2 and ft["dropped_before"].tolist()[28] == 1
    assert ft.attrs["clockmap"]["method"] == "led_pattern"
    ident = phone_frame_times(pts)
    np.testing.assert_allclose(ident["t_ref_s"], pts)
    assert ident.attrs["clockmap"]["method"] == "identity"
    empty = phone_frame_times([])
    assert len(empty) == 0


CLOCK_LOG = """date,time_utc,device,offset_ms_vs_phone,method,operator
2026-10-17,03:05:00,pi_unit_01,12.0,chronyc,op1
2026-10-17,03:05:30,kardia_tablet,-350.0,ntp_app,op1
2026-10-17,11:05:00,pi_unit_01,112.0,chronyc,op1
2026-10-17,11:05:30,kardia_tablet,-2050.0,ntp_app,op1
2026-10-18,03:00:00,pi_unit_01,5.0,chronyc,op2
"""


def test_clock_sync_log_daily_offsets_and_drift_flag(tmp_path, cfg):
    p = tmp_path / "clock_sync_log.csv"
    p.write_text(CLOCK_LOG)
    df = read_clock_sync_log(p)
    assert len(df) == 5 and df["ts_utc"].dt.tz is not None
    thr = cfg.get("clock.drift_flag_s_per_8h")
    pi = daily_offsets(df, "2026-10-17", "pi_unit_01", thr)
    assert pi["start_ms"] == 12.0 and pi["end_ms"] == 112.0 and pi["n_entries"] == 2
    assert abs(pi["hours_between"] - 8.0) < 1e-9
    assert abs(pi["drift_ms_per_8h"] - 100.0) < 1e-9 and pi["flag"] is False
    kd = daily_offsets(df, "2026-10-17", "kardia_tablet", thr)
    assert abs(kd["drift_ms_per_8h"] - (-1700.0)) < 1e-9 and kd["flag"] is True
    one = daily_offsets(df, "2026-10-18", "pi_unit_01", thr)
    assert one["n_entries"] == 1 and one["end_ms"] is None and np.isnan(one["drift_ms_per_8h"]) and one["flag"] is None
    none = daily_offsets(df, "2026-10-19", "pi_unit_01", thr)
    assert none["n_entries"] == 0 and none["flag"] is None
    mid = offset_at(df, "pi_unit_01", "2026-10-17T07:05:00Z")
    assert abs(mid["offset_ms"] - 62.0) < 1e-9 and mid["method"] == "interpolated"
    single = offset_at(df, "pi_unit_01", "2026-10-18T09:00:00Z")
    assert single["offset_ms"] == 5.0 and single["n_entries"] == 1
    assert offset_at(df, "pi_unit_02", "2026-10-18T09:00:00Z")["offset_ms"] is None
    bad = tmp_path / "bad.csv"
    bad.write_text("date,device\n2026-10-17,x\n")
    with pytest.raises(ValueError):
        read_clock_sync_log(bad)
