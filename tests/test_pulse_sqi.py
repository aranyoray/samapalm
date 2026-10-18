"""SQI ground truth (logistic map, SNR of a known sine in known noise, clean versus noise) and fusion weights."""
import numpy as np
import pytest

from palmppg.core.config import load_pipeline_config, rng
from palmppg.pulse import classical as C
from palmppg.pulse.fusion import snr_weighted_fusion, weight_from_quality
from palmppg.pulse.sqi import (
    band_snr_db,
    db_from_sqi,
    detect_beats,
    skewness_kurtosis_sqi,
    snr_band_sqi,
    spectral_peak,
    sqi_from_db,
    template_correlation_sqi,
)
from tests.test_pulse_synth import DC, FS, HR_BPM, synth_traces

BAND = (0.5, 4.0)


@pytest.fixture(scope="module")
def cfg():
    return load_pipeline_config()


@pytest.fixture(scope="module")
def clean(cfg):
    s = synth_traces()
    return C.run_method("GREEN", s["rgb"], FS, cfg), s["volume"]


@pytest.fixture(scope="module")
def noise(cfg):
    g = rng(5, "noise")
    rgb = DC * (1 + g.normal(0, 0.01, (1800, 3)))
    return C.run_method("GREEN", rgb, FS, cfg)


def test_logistic_map_centre_and_scale():
    assert sqi_from_db(0.0) == pytest.approx(0.5)
    assert sqi_from_db(4.0) == pytest.approx(1 / (1 + np.exp(-1)))
    assert sqi_from_db(-4.0) == pytest.approx(1 / (1 + np.exp(1)))
    assert sqi_from_db(float("inf")) == 1.0 and np.isnan(sqi_from_db(np.nan))
    for v in (-7.0, 0.0, 3.3):
        assert db_from_sqi(sqi_from_db(v)) == pytest.approx(v, abs=1e-9)
    assert sqi_from_db(np.array([0.0, 4.0])).shape == (2,)


def test_spectral_peak_of_known_sine():
    t = np.arange(int(20 * FS)) / FS
    f0, p = spectral_peak(np.sin(2 * np.pi * 1.2 * t), FS, BAND)
    assert abs(f0 - 1.2) < 0.005 and p > 0
    f0, _ = spectral_peak(np.zeros(600), FS, BAND)
    assert np.isnan(f0)


def test_band_snr_of_sine_in_white_noise_matches_expectation():
    # signal power A^2/2 = 0.5 (plus the noise inside its +/- 0.1 Hz windows); noise power in the rest of
    # the band = sigma^2 * (band width - 2 x 0.2 Hz) / (fs / 2)
    t = np.arange(int(60 * FS)) / FS
    g = rng(2, "snr")
    sigma = 0.5
    x = np.sin(2 * np.pi * 1.2 * t) + g.normal(0, sigma, t.size)
    snr_db, f0 = band_snr_db(x, FS, BAND)
    n_rest = sigma**2 * (3.5 - 0.4) / (FS / 2)
    s_win = 0.5 + sigma**2 * 0.4 / (FS / 2)
    expected = 10 * np.log10(s_win / n_rest)
    assert abs(f0 - 1.2) < 0.01
    assert abs(snr_db - expected) < 2.5, (snr_db, expected)
    pure, _ = band_snr_db(np.sin(2 * np.pi * 1.2 * t), FS, BAND)
    assert pure > 25


def test_sqi_high_on_clean_low_on_noise(clean, noise):
    sig, v = clean
    s = snr_band_sqi(sig, FS, BAND, 10.0, 1.0)
    assert s["sqi"] > 0.6 and s["snr_db"] > 2.0 and abs(s["hr_bpm"] - HR_BPM) <= 1.0
    assert s["n_windows"] == 51 and len(s["snr_db_windows"]) == 51 and s["window_start_s"][1] == pytest.approx(1.0)
    assert s["template_corr"] > 0.85
    n = snr_band_sqi(noise, FS, BAND, 10.0, 1.0)
    assert n["sqi"] < 0.4 and n["snr_db"] < 0.0
    # template correlation (secondary SQI) on noise band-limited to 0.5-4 Hz stays moderate (aligned band-limited
    # segments resemble each other); it must still rank the clean pulse clearly above noise
    assert np.isnan(n["template_corr"]) or n["template_corr"] < s["template_corr"] - 0.15
    assert s["sqi"] > n["sqi"] + 0.3


def test_sqi_window_bookkeeping_with_nans(clean):
    sig = clean[0].copy()
    sig[:900] = np.nan
    s = snr_band_sqi(sig, FS, BAND, 10.0, 1.0)
    assert 0 < s["n_windows"] < 51 and abs(s["hr_bpm"] - HR_BPM) <= 1.0
    empty = snr_band_sqi(np.full(1800, np.nan), FS, BAND, 10.0, 1.0)
    assert empty["sqi"] == 0.0 and empty["snr_db"] == float("-inf") and np.isnan(empty["hr_bpm"]) and empty["n_windows"] == 0


def test_skewness_kurtosis_of_known_shapes():
    t = np.arange(3000) / FS
    sk, ku = skewness_kurtosis_sqi(np.sin(2 * np.pi * 1.0 * t))
    assert abs(sk) < 0.02 and abs(ku - (-1.5)) < 0.02
    assert all(np.isnan(v) for v in skewness_kurtosis_sqi(np.ones(10)))


def test_detect_beats_counts_systolic_peaks_only(clean):
    sig, v = clean
    peaks = detect_beats(sig, FS, BAND)
    assert abs(peaks.size - 72) <= 1
    assert template_correlation_sqi(sig, FS, BAND) > 0.85
    assert np.isnan(template_correlation_sqi(np.zeros(100), FS, BAND))


def test_fusion_weights_sum_to_one_and_favour_clean(clean, cfg):
    sig, v = clean
    g = rng(9, "fusion")
    noisy = sig + 3.0 * g.normal(0, 1, sig.size)
    q = {"thenar": snr_band_sqi(sig, FS, BAND, 10.0, 1.0), "hypothenar": snr_band_sqi(noisy, FS, BAND, 10.0, 1.0)}
    fused, w = snr_weighted_fusion({"thenar": sig, "hypothenar": noisy}, q)
    assert sum(w.values()) == pytest.approx(1.0) and w["thenar"] > 0.8 > w["hypothenar"]
    assert np.corrcoef(fused, v)[0, 1] > np.corrcoef(noisy, v)[0, 1]
    assert np.corrcoef(fused, v)[0, 1] > 0.9 and abs(np.nanstd(fused) - 1) < 1e-9
    # polarity of an inverted input is aligned before fusing
    fused2, _ = snr_weighted_fusion({"thenar": sig, "hypothenar": -noisy}, q)
    assert np.corrcoef(fused, fused2)[0, 1] > 0.999
    # NaN in one input: the other carries that stretch
    sig_gap = sig.copy()
    sig_gap[100:200] = np.nan
    fused3, _ = snr_weighted_fusion({"thenar": sig_gap, "hypothenar": noisy}, q)
    assert np.isfinite(fused3[100:200]).all()


def test_weight_from_quality_rules():
    assert weight_from_quality({"snr_db": 10.0}) / weight_from_quality({"snr_db": 0.0}) == pytest.approx(10.0)
    assert weight_from_quality(0.5) == pytest.approx(1.0) and weight_from_quality({"sqi": 0.75}) == pytest.approx(3.0)
    assert weight_from_quality(None) == 0.0 and weight_from_quality({"snr_db": float("nan"), "sqi": 0.0}) == 0.0
    fused, w = snr_weighted_fusion({"a": np.ones(10), "b": np.ones(10)}, {"a": 0.0, "b": 0.0})
    assert np.isnan(fused).all() and all(v == 0.0 for v in w.values())
    with pytest.raises(ValueError):
        snr_weighted_fusion({"a": np.ones(10)}, {"zzz": 1.0})
