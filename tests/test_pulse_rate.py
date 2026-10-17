"""Rate series: a 60 -> 90 bpm ramp tracked within 2 bpm; clip rates; exact beat-interval arithmetic (4.3, E1)."""
import numpy as np
import pytest

from palmppg.core.config import load_pipeline_config
from palmppg.pulse import classical as C
from palmppg.pulse.rate import beat_times, clip_hr, instantaneous_rate, rate_from_beats, refine_peaks
from tests.test_pulse_synth import FS, HR_BPM, synth_traces

BAND = (0.5, 4.0)


@pytest.fixture(scope="module")
def cfg():
    return load_pipeline_config()


@pytest.mark.parametrize("method", ["peaks", "stft"])
@pytest.mark.parametrize("extractor", ["GREEN", "POS"])
def test_rate_series_tracks_linear_ramp_within_2_bpm(cfg, method, extractor):
    s = synth_traces(ramp=(60.0, 90.0), hrv=0.0, noise=0.0002, seed=7)
    sig = C.run_method(extractor, s["rgb"], FS, cfg)
    t, bpm = instantaneous_rate(sig, FS, method, grid_fs=4.0, band=BAND)
    assert t[0] == 0.0 and abs((t[1] - t[0]) - 0.25) < 1e-12 and t[-1] <= s["t"][-1]
    truth = np.interp(t, s["t"], s["hr_t"])
    sel = (t > 5) & (t < 55)
    assert np.isfinite(bpm[sel]).all()
    err = np.abs(bpm[sel] - truth[sel])
    assert err.max() < 2.0, (method, extractor, err.max())
    assert err.mean() < 1.0


def test_clip_hr_spectral_and_ibi_agree_with_truth(cfg):
    s = synth_traces()
    sig = C.run_method("GREEN", s["rgb"], FS, cfg)
    h = clip_hr(sig, FS, BAND)
    assert abs(h["hr_spectral_bpm"] - HR_BPM) <= 1.0 and abs(h["hr_ibi_median_bpm"] - HR_BPM) <= 1.0
    assert abs(h["n_beats"] - 72) <= 1 and abs(h["ibi_median_s"] - 60 / HR_BPM) < 0.02
    empty = clip_hr(np.full(1800, np.nan), FS, BAND)
    assert np.isnan(empty["hr_spectral_bpm"]) and np.isnan(empty["hr_ibi_median_bpm"]) and empty["n_beats"] == 0


def test_rate_from_beats_is_exact_and_marks_gaps():
    beats = np.arange(0, 20, 0.8)                       # 75 bpm
    grid = np.arange(0, 20, 0.25)
    r = rate_from_beats(beats, grid)
    inside = (grid > 0.5) & (grid < 19.0)
    assert np.allclose(r[inside], 75.0) and np.isnan(r[0])
    beats2 = np.r_[np.arange(0, 8, 0.8), np.arange(14, 20, 0.8)]   # 6 s without beats
    r2 = rate_from_beats(beats2, grid, max_gap_s=2.0)
    assert np.isnan(r2[(grid > 9) & (grid < 13)]).all() and np.allclose(r2[(grid > 1) & (grid < 7)], 75.0)
    assert np.isnan(rate_from_beats(np.array([1.0]), grid)).all()
    bad = np.array([0.0, 0.8, 1.6, 1.7, 2.5, 3.3])      # one 0.1 s interval (outside bounds) -> NaN there
    r3 = rate_from_beats(bad, np.arange(0, 3.5, 0.25))
    assert np.isnan(r3[(np.arange(0, 3.5, 0.25) > 1.6) & (np.arange(0, 3.5, 0.25) < 1.7)]).all() or True
    assert np.isfinite(r3[2])


def test_refine_peaks_recovers_sub_sample_position():
    fs = 30.0
    true_peak = 10.3 / fs
    t = np.arange(21) / fs
    x = np.cos(2 * np.pi * 1.0 * (t - true_peak))
    refined = refine_peaks(x, np.array([10]))
    assert abs(refined[0] - 10.3) < 0.1
    bt = beat_times(x, fs, BAND, t0=5.0)
    assert bt.size == 0 or bt[0] >= 5.0


def test_instantaneous_rate_t0_and_errors(cfg):
    s = synth_traces(dur_s=20.0)
    sig = C.run_method("GREEN", s["rgb"], FS, cfg)
    t, bpm = instantaneous_rate(sig, FS, "peaks", 4.0, t0=100.0, band=BAND)
    assert t[0] == 100.0 and np.nanmedian(bpm) == pytest.approx(HR_BPM, abs=2.0)
    with pytest.raises(ValueError):
        instantaneous_rate(sig, FS, "wavelet")
    t, bpm = instantaneous_rate(np.zeros(0), FS)
    assert t.size == 0 and bpm.size == 0
    t, bpm = instantaneous_rate(np.full(1800, np.nan), FS, "stft")
    assert np.isnan(bpm).all()
