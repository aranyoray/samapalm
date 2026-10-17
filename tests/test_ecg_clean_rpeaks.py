"""Cleaning (band-pass + notch) and R-peak detection with the two-detector agreement check against a
synthetic ECG with exactly known R times (protocol 6.4)."""
from __future__ import annotations

import numpy as np
import pytest

from palmppg.ecg.clean import bandpass, bridge_nan, clean_ecg, notch
from palmppg.ecg.rpeaks import detect_rpeaks, ibi_series, match_peaks, snap_to_apex
from tests.test_ecg_helpers import FS, nearest_offsets, synthetic_ecg


def _band_power(x, fs, hz, width=0.5):
    f = np.fft.rfftfreq(x.size, 1 / fs)
    p = np.abs(np.fft.rfft(x - x.mean())) ** 2
    return float(p[(f >= hz - width) & (f <= hz + width)].sum())


def test_clean_removes_mains_and_wander_and_keeps_r_timing(cfg):
    syn = synthetic_ecg(duration_s=40.0, hr_bpm=65.0, mains_mv=0.15, wander_mv=0.6, noise_mv=0.01, seed=2)
    x, fs = syn["x"], syn["fs"]
    y = clean_ecg(x, fs, cfg=cfg)
    assert y.dtype == np.float32 and y.shape == x.shape and np.isfinite(y).all()
    notch_hz = float(cfg.get("ecg.notch_hz"))
    assert _band_power(y.astype(float), fs, notch_hz) < 0.01 * _band_power(x, fs, notch_hz)      # > 20 dB down
    assert _band_power(y.astype(float), fs, 0.2) < 0.02 * _band_power(x, fs, 0.2)                # wander gone
    # zero-phase: the R apices of the cleaned signal sit on the true R times within one sample
    idx = np.round(syn["r_times_s"] * fs).astype(int)
    apex = np.array([lo + int(np.argmax(y[lo:lo + 13])) for lo in idx - 6])
    assert np.max(np.abs(apex - idx)) <= 1
    # the R amplitude survives the 0.5-40 Hz band within 25 % (a 9 ms sigma R wave has energy above 40 Hz)
    assert 0.75 < np.median(y[apex]) / 1.0 < 1.05


def test_clean_uses_config_band_and_bridges_nan(cfg):
    syn = synthetic_ecg(duration_s=10.0, seed=3)
    x = syn["x"].copy()
    x[1000:1010] = np.nan
    y = clean_ecg(x, FS, cfg=cfg)
    assert np.isnan(y[1000:1010]).all() and np.isfinite(np.delete(y, np.arange(1000, 1010))).all()
    y2 = clean_ecg(syn["x"], FS, band=tuple(cfg.get("ecg.band")), notch_hz=cfg.get("ecg.notch_hz"))
    assert np.allclose(y2, clean_ecg(syn["x"], FS, cfg=cfg))
    filled, bad = bridge_nan(x)
    assert bad.sum() == 10 and np.isfinite(filled).all()
    assert np.isnan(clean_ecg(np.full(50, np.nan), FS, cfg=cfg)).all()
    with pytest.raises(ValueError):
        bandpass(syn["x"], FS, 40.0, 0.5)
    assert np.allclose(notch(syn["x"], FS, 0.0), syn["x"])                   # notch skipped


def test_rpeaks_known_hr_and_detector_agreement(cfg):
    syn = synthetic_ecg(duration_s=60.0, hr_bpm=65.0, rsa_bpm=3.0, noise_mv=0.02, seed=4)
    y = clean_ecg(syn["x"], FS, cfg=cfg)
    rp = detect_rpeaks(y, FS, cfg=cfg)
    assert rp["primary"] == cfg.get("ecg.detectors")[0] and rp["detectors_run"] == list(cfg.get("ecg.detectors"))
    assert rp["n_peaks"] == syn["r_times_s"].size
    off = nearest_offsets(syn["r_times_s"], rp["t_s"])
    assert np.max(np.abs(off)) <= 0.010                                       # every R within 10 ms
    hr = 60.0 / np.mean(np.diff(rp["t_s"]))
    assert abs(hr - syn["hr_true_bpm"]) < 1.0
    assert rp["agree_frac"] > 0.95 and rp["agree"].dtype == bool and rp["agree"].shape == rp["idx"].shape
    for name, res in rp["per_detector"].items():
        assert res["error"] is None and res["n_peaks"] >= syn["r_times_s"].size - 2, name
        assert res["matched_frac"] > 0.95
    assert rp["agreement_ms"] == float(cfg.get("ecg.agreement_ms"))


def test_snap_to_apex_and_one_to_one_matching():
    x = np.zeros(1000)
    x[[100, 400, 700]] = 1.0
    assert snap_to_apex(x, [112, 388, 705], 300.0, window_ms=80).tolist() == [100, 400, 700]
    assert snap_to_apex(x, [103, 97], 300.0).tolist() == [100]               # duplicates collapse
    mp, mo = match_peaks(np.array([100, 400, 700]), np.array([97, 102, 420, 900]), tol=15)
    assert mp.tolist() == [True, False, False] and mo.tolist() == [False, True, False, False]   # nearest wins
    mp, mo = match_peaks(np.array([]), np.array([1, 2]), tol=5)
    assert mp.size == 0 and not mo.any()


def test_detector_failure_is_recorded_not_raised(cfg):
    syn = synthetic_ecg(duration_s=20.0, seed=5)
    rp = detect_rpeaks(clean_ecg(syn["x"], FS, cfg=cfg), FS, detectors=["neurokit", "no_such_method"], agreement_ms=50)
    assert rp["per_detector"]["no_such_method"]["error"] is not None
    assert np.isnan(rp["agree_frac"]) and rp["n_secondary_ran"] == 0 and rp["n_peaks"] > 10
    with pytest.raises(ValueError):
        detect_rpeaks(syn["x"], FS, detectors=[], agreement_ms=50)


def test_ibi_series_bounds(cfg):
    t = np.array([0.0, 0.8, 1.6, 1.8, 2.6, 5.0])        # 0.2 s (doubled beat) and 2.4 s (missed beat) intervals
    s = ibi_series(t, cfg=cfg)
    lo, hi = cfg.get("beats.ibi_bounds_s")
    assert s["bounds_s"] == (lo, hi) and s["n"] == 5 and s["n_rejected"] == 2
    assert s["valid"].tolist() == [True, True, False, True, False]
    assert np.allclose(s["ibi_valid_s"], [0.8, 0.8, 0.8]) and np.allclose(s["t_valid_s"], [0.8, 1.6, 2.6])
    assert ibi_series([1.0], cfg=cfg)["n"] == 0
