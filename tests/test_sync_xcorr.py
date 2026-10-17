"""Heart-rate cross-correlation: rate series, 0.8 s lag recovery, acceptance edge cases (section 4.3)."""
import numpy as np
import pytest

from palmppg.core.config import rng
from palmppg.core.timeline import uniform_grid
from palmppg.ingest.xcorr import agree_with_fine, rate_series_from_events, xcorr_lag


def _beats_with_hrv(duration_s, gen, hr=72.0):
    """Beat times with respiratory (0.25 Hz) and slow (0.08 Hz) rate modulation plus beat-to-beat noise."""
    t, beats = 0.0, []
    while t < duration_s:
        rate = hr + 6.0 * np.sin(2 * np.pi * 0.25 * t) + 4.0 * np.sin(2 * np.pi * 0.08 * t + 1.0)
        t += 60.0 / rate + gen.normal(0, 0.01)
        beats.append(t)
    return np.array(beats)


def test_rate_series_from_events_known_rate(cfg):
    fs = cfg.get("sync.xcorr.rate_fs")
    beats = np.arange(0, 30, 0.8)  # 75 bpm exactly
    t, r = rate_series_from_events(beats, fs)
    assert t[0] == pytest.approx(0.4) and abs(t[1] - t[0] - 1 / fs) < 1e-12
    assert np.nanmax(np.abs(r - 75.0)) < 1e-9
    # a gap longer than max_gap_s leaves NaN, outside the beats is NaN
    beats2 = np.r_[np.arange(0, 10, 0.8), np.arange(14, 20, 0.8)]
    grid = uniform_grid(-1, 21, fs)
    _, r2 = rate_series_from_events(beats2, fs, grid, max_gap_s=2.0)
    assert np.isnan(r2[0]) and np.isnan(r2[-1])
    assert np.isnan(r2[np.argmin(np.abs(grid - 12.0))])
    assert r2[np.argmin(np.abs(grid - 5.0))] == pytest.approx(75.0)
    _, r3 = rate_series_from_events([1.0], fs, grid)
    assert np.all(np.isnan(r3))


def test_xcorr_recovers_0p8s_shift_with_hrv(cfg):
    fs = cfg.get("sync.xcorr.rate_fs")
    gen = rng(31, "hrv")
    ecg_beats = _beats_with_hrv(60.0, gen)
    ppg_beats = ecg_beats + 0.8          # pulse series lags the ECG by 0.8 s
    grid = uniform_grid(2.0, 58.0, fs)
    _, a = rate_series_from_events(ecg_beats, fs, grid)
    _, b = rate_series_from_events(ppg_beats, fs, grid)
    res = xcorr_lag(a, b, fs, cfg.get("sync.xcorr.lag_s"), cfg.get("sync.xcorr.min_peak"), cfg.get("sync.xcorr.min_margin"))
    assert res["accepted"], res["reason"]
    assert abs(res["lag_s"] - 0.8) < 0.15
    assert res["peak"] > 0.9 and res["margin"] > 0.15
    # the opposite sign when the roles are swapped
    res2 = xcorr_lag(b, a, fs, 3.0, 0.6, 0.15)
    assert abs(res2["lag_s"] + 0.8) < 0.15
    assert len(res["lags_s"]) == 2 * round(3.0 * fs) + 1


def test_xcorr_acceptance_edge_cases(cfg):
    fs = cfg.get("sync.xcorr.rate_fs")
    gen = rng(32, "edge")
    grid = uniform_grid(0, 60, fs)
    # 1. unrelated series: peak below min_peak
    a = 70 + gen.normal(0, 3, size=grid.size)
    b = 70 + gen.normal(0, 3, size=grid.size)
    r = xcorr_lag(a, b, fs, 3.0, 0.6, 0.15)
    assert not r["accepted"] and "peak" in r["reason"]
    # 2. strictly periodic rate modulation: equal peaks every period -> margin ~ 0 -> rejected despite a high peak
    p = 70 + 5 * np.sin(2 * np.pi * 0.5 * grid)
    r2 = xcorr_lag(p, np.roll(p, 2), fs, 3.0, 0.6, 0.15)
    assert r2["peak"] > 0.95 and r2["margin"] < 0.15 and not r2["accepted"] and "margin" in r2["reason"]
    # 3. second peak must be searched outside the exclusion zone: widening it to cover the 2 s period makes it pass
    r3 = xcorr_lag(p, np.roll(p, 2), fs, 3.0, 0.6, 0.15, second_peak_exclusion_s=2.6)
    assert r3["accepted"] and r3["second_peak"] is not None
    # 4. too little overlap
    r4 = xcorr_lag(a[:20], b[:20], fs, 3.0, 0.6, 0.15)
    assert not r4["accepted"] and r4["lag_s"] is None and r4["reason"] == "insufficient overlap"
    # 5. identical series: lag 0, peak 1, accepted; thresholds exactly at the boundary count as met
    r5 = xcorr_lag(a, a, fs, 3.0, 1.0, 0.0)
    assert r5["accepted"] and r5["lag_s"] == pytest.approx(0.0, abs=1e-9) and r5["peak"] == pytest.approx(1.0)
    with pytest.raises(ValueError):
        xcorr_lag(a, a[:-1], fs, 3.0, 0.6, 0.15)


def test_agree_with_fine(cfg):
    s = cfg.get("sync.xcorr.agree_s")
    assert agree_with_fine(0.25, s) and agree_with_fine(-0.3, s)
    assert not agree_with_fine(0.31, s) and not agree_with_fine(None, s) and not agree_with_fine(float("nan"), s)
