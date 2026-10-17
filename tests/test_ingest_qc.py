"""QC numbers against ground truth: saturation, injected flicker, lighting drift, valid_clip logic, qc_table upsert."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from palmppg.core.config import rng
from palmppg.core.tracks import REGISTRY
from palmppg.ingest.qc import (
    QC_KEYS,
    append_qc_table,
    build_qc,
    flicker_peaks,
    lighting_drift_pct,
    read_qc_table,
    register_features,
    saturation_fraction,
    saturation_fraction_planes,
    write_qc_json,
)


def test_register_features_idempotent():
    names = register_features()
    names2 = register_features()
    assert names == names2 and "qc__phone__drop_pct" in names and "qc__pi__valid_clip" in names
    assert REGISTRY.get("qc__pi__drop_pct").requires_raw is True
    assert REGISTRY.get("qc__phone__drop_pct").requires_raw is False
    assert REGISTRY.get("qc__pi_proxy__sqi_best").allowed_in("product_candidate")
    assert not REGISTRY.get("qc__pi__sqi_best").allowed_in("product_candidate")


def test_saturation_fraction_known(cfg):
    white = cfg.get("pi.white_level")
    plane = np.full((10, 10), 500, np.uint16)
    plane[0, :3] = white
    assert saturation_fraction(plane, white_level=white) == pytest.approx(0.03)
    mask = np.zeros((10, 10), bool)
    mask[0, :6] = True
    assert saturation_fraction(plane, mask, white) == pytest.approx(0.5)
    rgb = np.zeros((4, 4, 3), np.uint8)
    rgb[1, 1, 2] = 255
    rgb[2, 2, :] = 255
    assert saturation_fraction(rgb, white_level=255) == pytest.approx(2 / 16)
    planes = {"R": plane, "G1": plane.copy(), "G2": plane.copy(), "B": np.full((10, 10), 10, np.uint16)}
    planes["G1"][5, 5] = white
    assert saturation_fraction_planes(planes, white_level=white) == pytest.approx(0.04)
    assert np.isnan(saturation_fraction(plane, np.zeros((10, 10), bool), white))
    with pytest.raises(ValueError):
        saturation_fraction(plane, np.zeros((3, 3), bool), white)


def _series(fs=30.0, seconds=60.0, hr_bpm=72.0, flicker_hz=None, flicker_pct=0.0, drift_pct=0.0, noise_pct=0.3, seed=4):
    gen = rng(seed, "flicker")
    t = np.arange(int(seconds * fs)) / fs
    base = 400.0
    x = base * (1.0 + 0.01 * np.sin(2 * np.pi * hr_bpm / 60.0 * t))  # pulse-like 1 % at the heart rate
    x = x * (1.0 + drift_pct / 100.0 * (t - t[0]) / (t[-1] - t[0]))
    if flicker_hz is not None:
        x = x * (1.0 + flicker_pct / 100.0 * np.sin(2 * np.pi * flicker_hz * t + 0.3))
    x = x + gen.normal(0.0, base * noise_pct / 100.0, size=t.size)
    return t, x


def test_flicker_injected_10hz_detected_and_clean_not_flagged(cfg):
    targets, tol, snr = cfg.get("qc.flicker_hz"), cfg.get("qc.flicker_tolerance_hz"), cfg.get("qc.flicker_snr_db_min")
    _t, x = _series(fs=30.0, flicker_hz=10.0, flicker_pct=1.0)
    res = flicker_peaks(x, 30.0, targets, tol, snr)
    assert res["flag"] is True and res["peaks_hz"] == [10.0]
    assert sorted(res["skipped_hz"]) == [50.0, 100.0] and res["tested_hz"] == [10.0]
    assert res["snr_db"]["10.0"] > snr + 10
    assert abs(res["peak_hz"]["10.0"] - 10.0) <= tol
    assert abs(res["modulation_pct"]["10.0"] - 1.0) < 0.2  # recovers the injected 1 % amplitude
    _t, x = _series(fs=30.0)
    clean = flicker_peaks(x, 30.0, targets, tol, snr)
    assert clean["flag"] is False and clean["peaks_hz"] == []
    assert clean["snr_db"]["10.0"] < snr
    # NaN gaps (dropped frames) do not break the test
    xg = x.copy()
    xg[100:103] = np.nan
    assert flicker_peaks(xg, 30.0, targets, tol, snr)["flag"] is False


def test_flicker_50hz_at_higher_fps(cfg):
    targets, tol, snr = cfg.get("qc.flicker_hz"), cfg.get("qc.flicker_tolerance_hz"), cfg.get("qc.flicker_snr_db_min")
    _t, x = _series(fs=240.0, seconds=20.0, flicker_hz=50.0, flicker_pct=0.5)
    res = flicker_peaks(x, 240.0, targets, tol, snr)
    assert res["flag"] is True and res["peaks_hz"] == [50.0]
    assert sorted(res["tested_hz"]) == [10.0, 50.0, 100.0]
    assert abs(res["modulation_pct"]["50.0"] - 0.5) < 0.15
    short = flicker_peaks(x[:5], 240.0, targets, tol, snr)
    assert short["flag"] is False and sorted(short["skipped_hz"]) == [10.0, 50.0, 100.0]


def test_lighting_drift_pct_known_slope():
    t, x = _series(fs=30.0, drift_pct=3.0, noise_pct=0.0, hr_bpm=72.0)
    d = lighting_drift_pct(x, t)
    assert abs(d - 3.0) < 0.1
    t, x = _series(fs=30.0, drift_pct=-1.0, noise_pct=0.0)
    assert abs(lighting_drift_pct(x, t) + 1.0) < 0.1
    assert abs(lighting_drift_pct(np.full(100, 5.0), np.arange(100) / 30.0)) < 1e-9
    xn = x.copy()
    xn[::7] = np.nan
    assert abs(lighting_drift_pct(xn, t) + 1.0) < 0.1
    assert np.isnan(lighting_drift_pct([1.0], [0.0]))
    with pytest.raises(ValueError):
        lighting_drift_pct([1.0, 2.0], [0.0])


def _frame_times(n=1800, fs=30.0, dropped=()):
    t = np.arange(n) / fs
    t = np.delete(t, list(dropped))
    return pd.DataFrame({"frame_idx": np.arange(t.size), "t_ref_s": t})


HAND_OK = {"hand_detected": True, "hand_is_left": True, "hand_palmar": True, "landmark_source": "mediapipe",
           "landmark_jitter_px": 0.8, "motion_flag": False}


def _good_inputs(cfg):
    _t, x = _series(fs=cfg.get("grid.fs"))
    return {"frame_times_df": _frame_times(), "mean_intensity_on_grid": x, "saturation_frac": 0.001, "hand_summary": HAND_OK,
            "vignetting_pct": 1.0, "eis": None, "sync_grade": "fine", "sqi_best": 0.7, "cfg": cfg, "sqi_threshold": 0.35}


def test_build_qc_valid_and_each_failing_flag(cfg):
    good = _good_inputs(cfg)
    qc = build_qc("pi", "SWHT-PP-003-0001", "clip1", **good)
    assert tuple(qc.keys()) == QC_KEYS
    assert qc["valid_clip"] is True and qc["reasons"] == []
    assert qc["n_frames"] == 1800 and abs(qc["duration_s"] - 60.0) < 1e-6 and abs(qc["fs_median"] - 30.0) < 1e-6
    assert qc["drop_pct"] == 0.0 and qc["drop_flag"] is False
    assert qc["flicker_flag"] is False and qc["flicker_peaks_hz"] == []
    assert qc["lighting_drift_flag"] is False and qc["vignetting_flag"] is False
    assert qc["eis_warp_px"] is None and qc["eis_flag"] is None
    assert qc["sync_grade"] == "fine" and qc["sqi_flag"] is False and qc["hand_is_left"] is True

    # each failing condition alone makes valid_clip False with exactly that reason
    bad = dict(good, hand_summary=dict(HAND_OK, hand_detected=False))
    q = build_qc("pi", "s", "clip1", **bad)
    assert q["valid_clip"] is False and q["reasons"] == ["hand_detected"]

    n_drop = int(np.ceil(1800 * cfg.get("qc.drop_pct_max") / 100.0)) + 2
    bad = dict(good, frame_times_df=_frame_times(dropped=range(100, 100 + n_drop)))
    q = build_qc("pi", "s", "clip1", **bad)
    assert q["drop_flag"] is True and q["reasons"] == ["drop_flag"] and q["drop_pct"] > cfg.get("qc.drop_pct_max")

    bad = dict(good, saturation_frac=cfg.get("qc.saturation_frac_max") * 1.5)
    q = build_qc("pi", "s", "clip1", **bad)
    assert q["saturation_flag"] is True and q["reasons"] == ["saturation_flag"]

    _, flick = _series(fs=cfg.get("grid.fs"), flicker_hz=10.0, flicker_pct=1.0)
    bad = dict(good, mean_intensity_on_grid=flick)
    q = build_qc("pi", "s", "clip1", **bad)
    assert q["flicker_flag"] is True and q["flicker_peaks_hz"] == [10.0] and q["reasons"] == ["flicker_flag"]

    bad = dict(good, sqi_best=0.2)
    q = build_qc("pi", "s", "clip1", **bad)
    assert q["sqi_flag"] is True and q["reasons"] == ["sqi_flag"]
    bad = dict(good, sqi_best=None)
    q = build_qc("pi", "s", "clip1", **bad)
    assert q["sqi_flag"] is None and q["sqi_best"] is None and q["reasons"] == ["sqi_flag"]

    # informational flags do not affect valid_clip
    _, drifting = _series(fs=cfg.get("grid.fs"), drift_pct=5.0)
    info = dict(good, mean_intensity_on_grid=drifting, vignetting_pct=cfg.get("qc.vignetting_residual_pct_max") + 1,
                eis={"warp_px_median": 1.2, "warp_px_p90": 2.0, "flag": True}, hand_summary=dict(HAND_OK, motion_flag=True))
    q = build_qc("phone", "s", "clip1", **info)
    assert q["lighting_drift_flag"] is True and q["vignetting_flag"] is True and q["eis_flag"] is True
    assert q["eis_warp_px"] == 2.0 and q["motion_flag"] is True
    assert q["valid_clip"] is True and q["reasons"] == []

    # hand stage not run: valid_clip False, hand fields None
    q = build_qc("phone", "s", "clip1", **dict(good, hand_summary=None))
    assert q["hand_detected"] is None and q["valid_clip"] is False and q["reasons"] == ["hand_detected"]
    # two failures -> two reasons in flag order
    q = build_qc("pi", "s", "clip1", **dict(good, hand_summary=None, sqi_best=0.1))
    assert q["reasons"] == ["hand_detected", "sqi_flag"]
    with pytest.raises(ValueError):
        build_qc("webcam", "s", "clip1", **good)


def test_qc_json_and_table_upsert(tmp_path, cfg):
    good = _good_inputs(cfg)
    qc = build_qc("pi", "SWHT-PP-003-0001", "clip1", **good)
    p = write_qc_json(qc, tmp_path / "pi" / "qc.json")
    back = json.loads(p.read_text())
    assert back["valid_clip"] is True and back["eis_warp_px"] is None and back["reasons"] == []
    table = tmp_path / "qc_table.parquet"
    append_qc_table(qc, table)
    append_qc_table(build_qc("phone", "SWHT-PP-003-0001", "clip1", **dict(good, sqi_best=0.1,
                                                                         eis={"warp_px_p90": 0.1, "flag": False})), table)
    df = read_qc_table(table)
    assert len(df) == 2 and set(df["camera"]) == {"pi", "phone"}
    # upsert replaces the pi row rather than duplicating it
    qc2 = build_qc("pi", "SWHT-PP-003-0001", "clip1", **dict(good, sqi_best=0.9))
    df = append_qc_table(qc2, table)
    assert len(df) == 2
    assert df[df["camera"] == "pi"]["sqi_best"].iloc[0] == pytest.approx(0.9)
    assert df[df["camera"] == "phone"]["valid_clip"].iloc[0] == np.False_
    assert df[df["camera"] == "phone"]["reasons"].iloc[0].tolist() == ["sqi_flag"]
    assert df["eis_flag"].dtype == object or df["eis_flag"].dtype == bool
    assert list(df.columns) == list(QC_KEYS)
    # a different clip appends
    append_qc_table(build_qc("pi", "SWHT-PP-003-0002", "clip1", **good), table)
    assert len(read_qc_table(table)) == 3
