"""Every classical method recovers the synthetic 72 bpm pulse within 1 bpm, in the volume polarity (6.3)."""
import numpy as np
import pytest
from scipy.signal import find_peaks

from palmppg.core.config import load_pipeline_config, rng
from palmppg.pulse import classical as C
from palmppg.pulse.rate import clip_hr
from palmppg.pulse.sqi import periodogram, snr_band_sqi
from tests.test_pulse_synth import AC_RATIOS, DC, FS, HR_BPM, synth_pixels, synth_traces

BAND = (0.5, 4.0)


@pytest.fixture(scope="module")
def cfg():
    return load_pipeline_config()


@pytest.fixture(scope="module")
def traces():
    return synth_traces()


@pytest.fixture(scope="module")
def pixels():
    return synth_pixels()


def _run(name, cfg, traces, pixels, **kw):
    x = pixels["pix"] if name == "2SR" else traces["rgb"]
    return C.run_method(name, x, FS, cfg, **kw)


def _hr(sig):
    s = snr_band_sqi(sig, FS, BAND, 10.0, 1.0)
    return s["hr_bpm"], clip_hr(sig, FS, BAND)["hr_spectral_bpm"], s


@pytest.mark.parametrize("name", C.METHODS)
def test_method_recovers_hr_within_1_bpm(name, cfg, traces, pixels):
    sig = _run(name, cfg, traces, pixels)
    assert sig.shape == (1800,) and np.isfinite(sig).all()
    assert abs(np.mean(sig)) < 1e-9 and abs(np.std(sig) - 1) < 1e-9
    hr_win, hr_spec, s = _hr(sig)
    assert abs(hr_win - HR_BPM) <= 1.0, (name, hr_win)
    assert abs(hr_spec - HR_BPM) <= 1.0, (name, hr_spec)
    assert s["sqi"] > 0.55, (name, s["sqi"])
    v = pixels["volume"] if name == "2SR" else traces["volume"]
    assert np.corrcoef(sig, v)[0, 1] > 0.75, name


@pytest.mark.parametrize("name", C.METHODS)
def test_polarity_peak_coincides_with_volume_maximum(name, cfg, traces, pixels):
    sig = _run(name, cfg, traces, pixels)
    v = pixels["volume"] if name == "2SR" else traces["volume"]
    vp, _ = find_peaks(v, distance=int(0.5 * FS), prominence=0.5)
    sp, _ = find_peaks(sig, distance=int(0.5 * FS), prominence=0.5)
    vp = vp[(vp > 2 * FS) & (vp < 58 * FS)]
    hits = sum(np.min(np.abs(sp - p)) <= 2 for p in vp)
    assert hits / vp.size >= 0.9, (name, hits, vp.size)
    lags = np.arange(-6, 7)
    cors = [np.corrcoef(np.roll(sig, k), v)[0, 1] for k in lags]
    assert abs(lags[int(np.argmax(cors))]) <= 1, name


@pytest.mark.parametrize("name", ["GREEN", "CHROM", "POS", "PBV", "LGI", "OMIT"])
def test_documented_native_sign_without_alignment(name, cfg, traces):
    sig = C.run_method(name, traces["rgb"], FS, cfg, align=False)
    assert np.corrcoef(sig, traces["volume"])[0, 1] > 0.7, name


def test_align_polarity_flips_only_negative_correlation(traces):
    v = traces["volume"]
    out, flipped = C.align_polarity(-v, v)
    assert flipped and np.allclose(out, v)
    out, flipped = C.align_polarity(v, v)
    assert not flipped
    out, flipped = C.align_polarity(np.full(5, np.nan), v[:5])
    assert not flipped


def test_nan_gap_is_restored_and_hr_survives(cfg, traces):
    rgb = traces["rgb"].copy()
    rgb[600:750] = np.nan
    for name in ("GREEN", "POS", "CHROM", "ICA"):
        sig = C.run_method(name, rgb, FS, cfg)
        assert np.isnan(sig[600:750]).all() and np.isfinite(np.delete(sig, np.arange(600, 750))).all()
        hr_win, _, _ = _hr(sig)
        assert abs(hr_win - HR_BPM) <= 1.0, name


def test_jade_separates_known_sources():
    t = np.arange(3000) / FS
    g = rng(4, "jade")
    s1 = np.sin(2 * np.pi * 1.0 * t)
    s2 = (np.mod(0.37 * t, 1.0) - 0.5) * 2
    s3 = g.uniform(-1, 1, t.size)
    sources = np.vstack([s1, s2, s3])
    mix = np.array([[1.0, 0.6, 0.3], [0.4, 1.0, 0.5], [0.2, 0.3, 1.0]])
    x = mix @ sources
    rec, w = C.jade(x, 3)
    assert rec.shape == (3, t.size) and w.shape == (3, 3)
    for s in sources:
        assert max(abs(np.corrcoef(s, r)[0, 1]) for r in rec) > 0.98


def test_jade_handles_rank_deficient_input():
    t = np.arange(900) / FS
    a, b = np.sin(2 * np.pi * 1.2 * t), np.sin(2 * np.pi * 0.3 * t)
    x = np.vstack([a + b, 2 * a - b, 3 * a])   # rank 2
    rec, w = C.jade(x, 3)
    assert rec.shape[0] == 2 and np.isfinite(rec).all()


def test_pca_and_ica_ignore_numerically_empty_components(cfg):
    s = synth_traces(hrv=0.0, drift_amp=0.02, noise=0.0)    # rank-2 trace: pulse + drift
    for name in ("PCA", "ICA"):
        sig = C.run_method(name, s["rgb"], FS, cfg)
        assert abs(clip_hr(sig, FS, BAND)["hr_spectral_bpm"] - HR_BPM) <= 1.0
        assert np.corrcoef(sig, s["volume"])[0, 1] > 0.9


def test_ica_fastica_option_and_pbv_vector_override(cfg, traces):
    sig = C.run_method("ICA", traces["rgb"], FS, cfg, algorithm="fastica")
    assert abs(clip_hr(sig, FS, BAND)["hr_spectral_bpm"] - HR_BPM) <= 1.0
    sig = C.run_method("PBV", traces["rgb"], FS, cfg, pbv_vector=AC_RATIOS)
    assert abs(clip_hr(sig, FS, BAND)["hr_spectral_bpm"] - HR_BPM) <= 1.0
    assert np.corrcoef(sig, traces["volume"])[0, 1] > 0.75
    with pytest.raises(ValueError):
        C.run_method("ICA", traces["rgb"], FS, cfg, algorithm="nope")


def test_ssr_fallback_on_roi_stack_and_input_checks(cfg, traces):
    g = rng(8, "roi_stack")
    rgb = traces["rgb"]
    stack = np.stack([rgb * (1 + 0.2 * g.uniform(-1, 1, 3)) for _ in range(5)], axis=1)   # (T, 5, 3) "pixels"
    sig = C.run_method("ssr", stack, FS, cfg)
    assert abs(clip_hr(sig, FS, BAND)["hr_spectral_bpm"] - HR_BPM) <= 1.0
    with pytest.raises(ValueError):
        C.run_method("2SR", rgb, FS, cfg)
    with pytest.raises(ValueError):
        C.ssr(np.full((100, 2, 3), 1.0), FS, BAND)
    pix = np.array(stack, copy=True)
    pix[:, 1, :] = np.nan                                            # one pixel absent throughout
    pix[100:110] = np.nan                                            # a dropped-frame gap
    sig = C.ssr(pix, FS, BAND)
    assert np.isnan(sig[100:110]).all() and np.isfinite(np.delete(sig, np.arange(100, 110))).all()


def test_dispatcher_names_bands_and_config_overrides(cfg, traces):
    assert C.canonical_name("ssr") == "2SR" and C.canonical_name("chrome") == "CHROM"
    with pytest.raises(ValueError):
        C.canonical_name("MAGIC")
    rate = C.run_method("POS", traces["rgb"], FS, cfg)
    morph = C.run_method("POS", traces["rgb"], FS, cfg, band=tuple(cfg.get("pulse.band_morph")))
    f, p_rate = periodogram(rate, FS)
    _, p_morph = periodogram(morph, FS)
    hi = f > 4.5
    assert p_morph[hi].sum() / p_morph.sum() > 5 * p_rate[hi].sum() / p_rate.sum()
    cfg2 = cfg.with_overrides({"pulse": {"chrom_window_s": 3.2, "pos_window_s": 2.0, "ica_algorithm": "jade"}})
    for name in ("CHROM", "POS", "ICA"):
        sig = C.run_method(name, traces["rgb"], FS, cfg2)
        assert abs(clip_hr(sig, FS, BAND)["hr_spectral_bpm"] - HR_BPM) <= 1.0
    out = C.run_all(traces["rgb"], FS, cfg)
    assert set(out) == set(C.METHODS) - {"2SR"}
    out = C.run_all(synth_pixels()["pix"], FS, cfg, methods=["GREEN", "2SR"])
    assert set(out) == {"GREEN", "2SR"}
    plain = {"pulse": {"band_rate": [0.5, 4.0], "detrend_lambda": 300, "methods": ["GREEN"]}}
    assert np.isfinite(C.run_method("GREEN", traces["rgb"], FS, plain)).all()


def test_patch_input_is_averaged_for_mean_methods(cfg, pixels):
    sig = C.run_method("GREEN", pixels["pix"], FS, cfg)
    ref = C.run_method("GREEN", np.nanmean(pixels["pix"], axis=1), FS, cfg)
    assert np.allclose(sig, ref)


def test_normalisation_and_constants():
    cn = C._normalise(np.column_stack([DC[0] * np.ones(10), DC[1] * np.ones(10), DC[2] * np.ones(10)]))
    assert np.allclose(cn, 0.0)
    assert C.PBV_STANDARD == (0.33, 0.77, 0.53) and C.CHROM_WINDOW_S == 1.6 and C.POS_WINDOW_S == 1.6
