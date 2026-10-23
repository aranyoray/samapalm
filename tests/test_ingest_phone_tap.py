"""The optional SamaPalmRecorder files: ROI tap, control log, and their join to frame times (CONTRACTS 3.5)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from palmppg.ingest import phone_tap


def _frames(n: int, t0: int = 2_000_000_000_000) -> pd.DataFrame:
    ts = t0 + np.arange(n) * 33_333_333
    return pd.DataFrame({"frame_idx": np.arange(n), "sensor_ts_ns": ts, "wall_ns": ts + 10**18, "iso": 130, "exposure_ns": 9_998_229})


def _roi(frames: pd.DataFrame, luma: float = 140.0) -> pd.DataFrame:
    n = len(frames)
    y = luma + 0.6 * np.sin(2 * np.pi * 1.2 * np.arange(n) / 30)
    df = pd.DataFrame({
        "roi_idx": np.arange(n), "sensor_ts_ns_raw": frames["sensor_ts_ns"], "t_ref_ns": frames["sensor_ts_ns"],
        "n_px": 49152, "y_mean": y, "u_mean": 110.0, "v_mean": 160.0,
        "r_mean": y + 44.9, "g_mean": y - 16.6, "b_mean": y - 31.9, "clip_frac": 0.0,
    })
    for g in phone_tap.ROI_GRID:
        df[g] = y
    return df


def _controls(frames: pd.DataFrame) -> pd.DataFrame:
    n = len(frames)
    return pd.DataFrame({
        "frame_idx": frames["frame_idx"], "sensor_ts_ns": frames["sensor_ts_ns"], "iso": 130, "exposure_ns": 9_998_229,
        "focus_diopters": 5.8824, "lens_state": 0, "zoom_ratio": 1.0,
        "gain_r": 1.8, "gain_g_even": 1.0, "gain_g_odd": 1.0, "gain_b": 1.6,
        "awb_mode": 0, "ae_mode": 0, "af_mode": 0, "tonemap_mode": 0, "shading_mode": 0, "flash_state": 3,
    })


def test_roi_reader_validates_and_sorts(tmp_path):
    frames = _frames(10)
    roi = _roi(frames).iloc[::-1]          # written out of order
    p = tmp_path / "clip1_roi.csv"
    roi.to_csv(p, index=False)
    df = phone_tap.read_phone_roi_csv(p)
    assert df["t_ref_ns"].is_monotonic_increasing
    assert df["t_phone_s"].iloc[0] == 0.0
    assert abs(df["t_phone_s"].iloc[-1] - 9 / 30) < 1e-6
    roi.drop(columns=["g_mean"]).to_csv(p, index=False)
    with pytest.raises(ValueError, match="g_mean"):
        phone_tap.read_phone_roi_csv(p)


def test_tap_table_joins_frames_and_reference_times(tmp_path):
    frames = _frames(30)
    roi = _roi(frames)
    # the encoder dropped two frames: frame_times has 28 rows, the logger still has all 30
    ft = pd.DataFrame({"frame_idx": [i for i in range(30) if i not in (7, 19)], "t_ref_s": 100.0 + np.arange(28) / 30})
    tap = phone_tap.roi_tap_table(roi, frames, ft)
    assert len(tap) == 30
    assert tap["frame_idx"].notna().all(), "every tap row shares a sensor timestamp with the frame log"
    assert int(tap["t_ref_s"].isna().sum()) == 2, "rows for dropped frames keep NaN rather than an invented time"
    assert np.isclose(tap.loc[tap["frame_idx"] == 0, "t_ref_s"].item(), 100.0)
    assert list(tap.columns[:3]) == ["roi_idx", "sensor_ts_ns", "t_phone_s"]
    assert np.allclose(tap["mean_R"] - tap["mean_G"], 61.5)


def test_tap_table_without_frames_keeps_phone_clock_only():
    frames = _frames(5)
    tap = phone_tap.roi_tap_table(_roi(frames))
    assert tap["frame_idx"].isna().all()
    assert tap["t_ref_s"].isna().all()
    assert np.isclose(tap["t_phone_s"].iloc[-1], 4 / 30)


def test_controls_summary_counts_departures_from_a_pinned_clip():
    frames = _frames(40)
    c = _controls(frames)
    s = phone_tap.controls_summary(c)
    assert s["iso_distinct"] == 1 and s["exposure_ns_distinct"] == 1 and s["focus_diopters_distinct"] == 1
    assert s["lens_moving_frames"] == 0 and s["af_mode_off_frames"] == 40 and s["flash_fired_frames"] == 40
    assert s["colour_gains_distinct"] == 1

    c.loc[10:14, "lens_state"] = 1
    c.loc[20, "exposure_ns"] = 11_000_000
    c.loc[30:, ["gain_r"]] = 1.9
    s = phone_tap.controls_summary(c)
    assert s["lens_moving_frames"] == 5
    assert s["exposure_ns_distinct"] == 2 and s["exposure_ns_max"] == 11_000_000
    assert s["colour_gains_distinct"] == 2
    assert phone_tap.controls_summary(c.iloc[0:0]) == {"n_rows": 0}


def test_ingest_tap_files_writes_parquet_and_reports_a_dark_roi(tmp_path):
    phone = tmp_path / "phone"
    phone.mkdir()
    frames = _frames(60)
    frames.to_csv(phone / "clip1_frames.csv", index=False)
    roi = _roi(frames, luma=11.0)          # what every real clip so far looked like
    roi.to_csv(phone / "clip1_roi.csv", index=False)
    _controls(frames).to_csv(phone / "clip1_controls.csv", index=False)
    out = tmp_path / "work"
    r = phone_tap.ingest_tap_files(phone, "clip1", out)
    assert r is not None
    assert (out / "mean_intensity_tap.parquet").exists()
    assert r["n_roi_rows"] == 60 and r["n_joined_to_frames"] == 60 and r["n_with_t_ref"] == 0
    assert r["roi_dark_fraction"] == 1.0
    assert r["controls"]["n_rows"] == 60
    assert "not linearised" in r["units"]
    back = pd.read_parquet(out / "mean_intensity_tap.parquet")
    assert len(back) == 60 and "mean_G" in back


def test_ingest_tap_files_is_none_for_the_open_camera_route(tmp_path):
    phone = tmp_path / "phone"
    phone.mkdir()
    (phone / "clip1.mp4").write_bytes(b"")
    assert phone_tap.ingest_tap_files(phone, "clip1", tmp_path / "work") is None
