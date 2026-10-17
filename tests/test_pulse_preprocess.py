"""Preprocessing ground truth: smoothness-prior cut-off, band-pass gains, NaN bridging (section 6.3)."""
import numpy as np
import pytest

from palmppg.pulse.preprocess import (
    VOLUME_SIGN,
    bandpass,
    bridge_nans,
    detrend_smoothness_prior,
    hann_window,
    intensity_to_volume,
    preprocess,
    restore_nans,
    window_iter,
    zscore,
)

FS = 30.0


def _amp(t, x, hz):
    a = np.column_stack([np.sin(2 * np.pi * hz * t), np.cos(2 * np.pi * hz * t)])
    coef, *_ = np.linalg.lstsq(a, x - x.mean(), rcond=None)
    return float(np.hypot(*coef))


def test_detrend_removes_cubic_trend_and_keeps_pulse():
    t = np.arange(int(60 * FS)) / FS
    pulse = np.sin(2 * np.pi * 1.2 * t)
    trend = 5.0 * ((t / 60) ** 3 - 0.5 * (t / 60)) + 2.0
    y = detrend_smoothness_prior(pulse + trend, 300)
    mid = slice(int(5 * FS), int(55 * FS))
    assert np.corrcoef(y[mid], pulse[mid])[0, 1] > 0.999
    assert abs(_amp(t[mid], y[mid], 1.2) - 1.0) < 0.03
    assert np.std((y - pulse)[mid]) < 0.1


@pytest.mark.parametrize("lam", [300.0, 1000.0])
def test_detrend_response_matches_formula(lam):
    # H(w) = 16 lam^2 sin^4(w/2) / (1 + 16 lam^2 sin^4(w/2)): gain 1/2 where 16 lam^2 sin^4(w/2) = 1,
    # i.e. f_half = fs / (2 pi sqrt(lam)); half power (1/sqrt 2) where 16 lam^2 sin^4(w/2) = 1 + sqrt 2
    fc = FS / (2 * np.pi * np.sqrt(lam))
    w_hp = 2 * np.arcsin(((1 + np.sqrt(2)) / (16 * lam**2)) ** 0.25)
    f_hp = w_hp * FS / (2 * np.pi)
    assert abs(f_hp / fc - 1.25) < 0.01
    t = np.arange(int(240 * FS)) / FS
    mid = slice(int(60 * FS), int(180 * FS))

    def gain(f):
        return _amp(t[mid], detrend_smoothness_prior(np.sin(2 * np.pi * f * t), lam)[mid], f)

    assert abs(gain(fc) - 0.5) < 0.02
    assert abs(gain(f_hp) - 1 / np.sqrt(2)) < 0.02
    assert gain(0.2 * fc) < 0.05 and gain(4 * fc) > 0.98


def test_detrend_is_nan_safe_by_bridging():
    t = np.arange(int(20 * FS)) / FS
    x = np.sin(2 * np.pi * 1.0 * t) + 0.5 * t
    ref = detrend_smoothness_prior(x, 300)
    xn = x.copy()
    xn[200:230] = np.nan
    y = detrend_smoothness_prior(xn, 300)
    assert np.isnan(y[200:230]).all() and np.isfinite(np.delete(y, np.arange(200, 230))).all()
    far = np.r_[0:150, 280:600]
    assert np.max(np.abs(y[far] - ref[far])) < 0.05
    assert detrend_smoothness_prior(np.array([np.nan, np.nan]), 300).size == 2


def test_bandpass_gains_and_zero_phase():
    t = np.arange(int(60 * FS)) / FS
    mid = slice(int(5 * FS), int(55 * FS))
    for hz, lo_gain, hi_gain in [(1.2, 0.97, 1.03), (0.1, 0.0, 0.05), (10.0, 0.0, 0.05)]:
        x = np.sin(2 * np.pi * hz * t)
        y = bandpass(x, FS, 0.5, 4.0)
        g = _amp(t[mid], y[mid], hz)
        assert lo_gain <= g <= hi_gain, (hz, g)
    x = np.sin(2 * np.pi * 1.2 * t)
    y = bandpass(x, FS, 0.5, 4.0)
    lags = np.arange(-5, 6)
    cors = [np.corrcoef(x[mid], np.roll(y, k)[mid])[0, 1] for k in lags]
    assert lags[int(np.argmax(cors))] == 0


def test_bandpass_morph_band_passes_harmonics_rate_band_does_not():
    t = np.arange(int(60 * FS)) / FS
    x = np.sin(2 * np.pi * 6.0 * t)
    mid = slice(int(5 * FS), int(55 * FS))
    assert _amp(t[mid], bandpass(x, FS, 0.4, 8.0)[mid], 6.0) > 0.95
    assert _amp(t[mid], bandpass(x, FS, 0.5, 4.0)[mid], 6.0) < 0.1


def test_bandpass_short_signal_and_nans_and_bad_band():
    x = np.sin(2 * np.pi * 1.0 * np.arange(10) / FS)
    y = bandpass(x, FS, 0.5, 4.0)
    assert y.shape == (10,) and np.isfinite(y).all()
    xn = np.sin(2 * np.pi * 1.0 * np.arange(300) / FS)
    xn[50:60] = np.nan
    y = bandpass(xn, FS, 0.5, 4.0)
    assert np.isnan(y[50:60]).all() and np.isfinite(y[:50]).all()
    with pytest.raises(ValueError):
        bandpass(xn, FS, 4.0, 0.5)
    assert bandpass(np.zeros(0), FS, 0.5, 4.0).size == 0


def test_zscore_and_bridging_helpers():
    x = np.array([1.0, np.nan, 3.0, np.nan, np.nan, 9.0, np.nan])
    b, m = bridge_nans(x)
    assert np.allclose(b, [1, 2, 3, 5, 7, 9, 9]) and m.tolist() == [False, True, False, True, True, False, True]
    assert np.isnan(restore_nans(b, m)).sum() == 4
    z = zscore(x)
    ok = np.isfinite(z)
    assert abs(z[ok].mean()) < 1e-12 and abs(z[ok].std() - 1) < 1e-12 and np.isnan(z[~ok]).all()
    assert np.all(zscore(np.full(5, 3.0)) == 0)
    assert np.isnan(zscore(np.full(3, np.nan))).all()
    b2, m2 = bridge_nans(np.full(4, np.nan))
    assert np.all(b2 == 0) and m2.all()


def test_window_iter_counts_and_short_signal():
    x = np.arange(int(60 * FS))
    wins = list(window_iter(x, FS, 10.0, 1.0))
    assert len(wins) == 51 and wins[0][:2] == (0, 300) and wins[-1][:2] == (1500, 1800)
    assert all(seg.size == 300 for _, _, seg in wins)
    short = list(window_iter(np.arange(50), FS, 10.0, 1.0))
    assert len(short) == 1 and short[0][1] == 50


def test_polarity_helpers_and_hann():
    assert VOLUME_SIGN == -1.0
    assert np.all(intensity_to_volume(np.array([1.0, -2.0])) == np.array([-1.0, 2.0]))
    w = hann_window(48)
    assert abs((w[:24] + w[24:]).max() - 1.0) < 1e-12 and abs((w[:24] + w[24:]).min() - 1.0) < 1e-12


def test_preprocess_chain_is_zscored_and_bandlimited():
    t = np.arange(int(60 * FS)) / FS
    y = preprocess(np.sin(2 * np.pi * 1.2 * t) + 3 * t, FS, (0.5, 4.0), 300)
    assert abs(np.nanmean(y)) < 1e-9 and abs(np.nanstd(y) - 1) < 1e-9
    mid = slice(int(5 * FS), int(55 * FS))
    assert np.corrcoef(y[mid], np.sin(2 * np.pi * 1.2 * t)[mid])[0, 1] > 0.999
