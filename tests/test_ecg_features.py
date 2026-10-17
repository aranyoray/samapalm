"""ECG rate and rhythm features on IBI series with known statistics; instantaneous rate; registry."""
from __future__ import annotations

import math

import numpy as np
import pytest

from palmppg.core.config import rng
from palmppg.core.tracks import REGISTRY, FeatureRegistry
from palmppg.ecg.features import (
    FEATURE_NAMES,
    column_name,
    ecg_features,
    instantaneous_rate,
    poincare_sd,
    register_features,
    sample_entropy,
    turning_point_ratio,
)


def _peaks_from_ibis(ibis):
    return np.concatenate([[0.0], np.cumsum(ibis)])


def test_constant_ibi_series(cfg):
    t = _peaks_from_ibis(np.full(60, 0.8))
    f = ecg_features(t, cfg=cfg)
    assert f["n_beats"] == 61 and f["n_ibi"] == 60 and f["n_ibi_rejected"] == 0
    assert abs(f["hr_mean_bpm"] - 75.0) < 1e-9 and abs(f["hr_median_bpm"] - 75.0) < 1e-9
    assert abs(f["ibi_mean_ms"] - 800.0) < 1e-9
    for k in ("sdnn_ms", "rmssd_ms", "pnn50", "ibi_cv", "ibi_succ_diff_gt50_frac", "turning_point_ratio", "poincare_sd1_ms"):
        assert abs(f[k]) < 1e-9, k
    assert math.isnan(f["sampen"])                       # zero tolerance: undefined
    assert abs(f["window_span_s"] - 48.0) < 1e-9


def test_alternating_ibi_series_has_known_rmssd_pnn50_sd1_tpr(cfg):
    n = 80
    ibis = np.where(np.arange(n) % 2 == 0, 0.76, 0.84)
    f = ecg_features(_peaks_from_ibis(ibis), cfg=cfg)
    assert abs(f["hr_mean_bpm"] - 75.0) < 1e-9
    assert abs(f["rmssd_ms"] - 80.0) < 1e-9
    assert abs(f["pnn50"] - 100.0) < 1e-9 and abs(f["ibi_succ_diff_gt50_frac"] - 1.0) < 1e-9
    assert abs(f["sdnn_ms"] - 40.0 * math.sqrt(n / (n - 1))) < 1e-9
    assert abs(f["ibi_cv"] - f["sdnn_ms"] / 800.0) < 1e-12
    sd1_expected = math.sqrt(0.5 * np.var(np.diff(ibis * 1000), ddof=1))
    assert abs(f["poincare_sd1_ms"] - sd1_expected) < 1e-9
    assert abs(f["turning_point_ratio"] - 1.0) < 1e-12
    # alternating 40 ms steps stay below the 50 ms pNN threshold
    g = ecg_features(_peaks_from_ibis(np.where(np.arange(n) % 2 == 0, 0.78, 0.82)), cfg=cfg)
    assert g["pnn50"] == 0.0 and abs(g["rmssd_ms"] - 40.0) < 1e-9


def test_sample_entropy_matches_reference_implementation(cfg):
    nk = pytest.importorskip("neurokit2")
    g = rng(7, "sampen")
    x = 800 + 40 * g.normal(size=200)
    r = 0.2 * np.std(x, ddof=1)
    mine = sample_entropy(x, m=2, r=r)
    ref, _ = nk.entropy_sample(x, delay=1, dimension=2, tolerance=r)
    assert abs(mine - ref) < 1e-9
    assert abs(sample_entropy(x) - mine) < 1e-9                 # default r = 0.2 SD
    y = 800 + 30 * np.sin(np.arange(200) * 0.4)
    assert sample_entropy(y) < mine                             # periodic is more regular than noise
    assert math.isnan(sample_entropy(np.arange(5)))             # too short
    assert abs(turning_point_ratio([1, 3, 2, 4, 3, 5]) - 1.0) < 1e-12
    assert abs(turning_point_ratio([1, 2, 3, 4, 5]) - 0.0) < 1e-12
    sd1, sd2 = poincare_sd(np.full(10, 800.0), np.zeros(9))
    assert sd1 == 0.0 and sd2 == 0.0


def test_window_mask_and_out_of_bounds_intervals(cfg):
    t = _peaks_from_ibis(np.full(19, 0.9))          # 20 peaks
    mask = np.ones(20, dtype=bool)
    mask[10:15] = False                              # two kept blocks: 10 and 5 peaks
    f = ecg_features(t, window_mask=mask, cfg=cfg)
    assert f["n_beats"] == 15 and f["n_ibi"] == 9 + 4   # no interval bridges the masked gap
    assert abs(f["hr_mean_bpm"] - 60 / 0.9) < 1e-9
    ibis = np.full(30, 0.8)
    ibis[10] = 0.2                                   # outside beats.ibi_bounds_s
    g = ecg_features(_peaks_from_ibis(ibis), cfg=cfg)
    assert g["n_ibi_rejected"] == 1 and abs(g["hr_mean_bpm"] - 75.0) < 1e-9
    assert g["n_ibi"] == 30
    agree = np.ones(31, dtype=bool)
    agree[:3] = False
    h = ecg_features(_peaks_from_ibis(ibis), agree=agree, cfg=cfg)
    assert abs(h["detector_agree_frac"] - 28 / 31) < 1e-12
    with pytest.raises(ValueError):
        ecg_features(t, window_mask=mask[:5], cfg=cfg)
    few = ecg_features(np.array([1.0]), cfg=cfg)
    assert few["n_beats"] == 1 and math.isnan(few["hr_mean_bpm"])


def test_r_amplitude_features(cfg):
    fs = 300.0
    t = _peaks_from_ibis(np.full(20, 0.8)) + 0.5
    x = np.zeros(int(20 * fs))
    x[np.round(t * fs).astype(int)] = 1.2
    f = ecg_features(t, x, fs, cfg=cfg)
    assert abs(f["r_amp_median_mv"] - 1.2) < 1e-12 and abs(f["r_amp_cv"]) < 1e-12


def test_instantaneous_rate_on_grid(cfg):
    fs = float(cfg.get("sync.xcorr.rate_fs"))
    t = _peaks_from_ibis(np.full(40, 0.8))
    grid, bpm = instantaneous_rate(t, cfg=cfg)
    assert grid[0] == t[0] and abs(grid[1] - grid[0] - 1 / fs) < 1e-12
    inside = (grid >= t[1]) & (grid <= t[-1])
    assert np.allclose(bpm[inside], 75.0) and np.isnan(bpm[grid < t[1]]).all()
    # linearly changing IBIs: the rate at each beat time equals 60 / its IBI
    ibis = np.linspace(0.6, 1.0, 50)
    t2 = _peaks_from_ibis(ibis)
    _, b2 = instantaneous_rate(t2, grid=t2[1:], cfg=cfg)
    assert np.allclose(b2, 60.0 / ibis)
    # a missed beat (interval above the bound) leaves NaN inside the gap
    ibis3 = np.full(30, 0.8)
    ibis3[15] = 2.4
    t3 = _peaks_from_ibis(ibis3)
    g3, b3 = instantaneous_rate(t3, cfg=cfg)
    gap = (g3 > t3[15] + 0.01) & (g3 < t3[16] - 0.01)
    assert np.isnan(b3[gap]).all() and np.isfinite(b3[(g3 > t3[2]) & (g3 < t3[14])]).all()
    _, b4 = instantaneous_rate(np.array([1.0]), fs=4.0, cfg=cfg)
    assert np.isnan(b4).all()


def test_register_features_is_idempotent_and_requires_ecg():
    cols = register_features()
    cols2 = register_features()
    assert cols == cols2 and len(cols) == len(FEATURE_NAMES) == len(set(cols))
    for name in FEATURE_NAMES:
        meta = REGISTRY.get(column_name(name))
        assert meta is not None and meta.requires_ecg is True and meta.group == "ecg" and meta.camera == "any"
        assert not meta.allowed_in("product_candidate") and meta.allowed_in("science")
    local = FeatureRegistry()
    assert register_features(local) == cols and "ecg__hr_mean_bpm" in local
    assert "label" in REGISTRY.get("ecg__clinician_rhythm").tags
