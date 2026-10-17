"""PulseGAN and Dual-GAN trainers judged by a downstream metric only (protocol 9, 11.10)."""
import numpy as np
import pytest

from palmppg.core.config import rng
from palmppg.models import gan


def _corr(a, b):
    return float(np.corrcoef(a, b)[0, 1])


@pytest.fixture(scope="module")
def windows():
    pytest.importorskip("torch")
    g = rng(4, "gan")
    L = 128
    t = np.arange(L) / 30.0
    clean = [np.sin(2 * np.pi * g.uniform(0.8, 1.6) * t + g.uniform(0, 6)) for _ in range(64)]
    noisy = [c + 0.8 * g.normal(size=L) + 0.5 * np.sin(2 * np.pi * 10 * t) for c in clean]   # white noise + mains alias
    return noisy, clean


def test_module_docstring_states_the_rule():
    doc = " ".join(gan.__doc__.split())
    assert "never appear in a headline result" in doc
    assert "judged" in doc and "downstream metrics" in doc


def test_pulsegan_improves_correlation_with_clean(windows):
    noisy, clean = windows
    tr = gan.PulseGANTrainer(epochs=30, seed=0, hidden=8).fit(noisy[:48], clean[:48])
    assert set(tr.history_) == {"d", "g_adv", "g_time", "g_spec"} and len(tr.history_["d"]) == 30
    assert tr.history_["g_time"][-1] < tr.history_["g_time"][0]
    den = tr.denoise(noisy[48:])
    assert den.shape == (16, 128)
    before = np.mean([_corr(a, b) for a, b in zip(noisy[48:], clean[48:])])
    after = np.mean([_corr(a, b) for a, b in zip(den, clean[48:])])
    assert after > before + 0.05 and after > 0.65
    single = tr.denoise(noisy[48])
    assert single.shape == (128,) and np.allclose(single, den[0], atol=1e-5)
    with pytest.raises(ValueError):
        tr.fit(noisy[:4], clean[:3])


def test_dualgan_improves_correlation_with_clean(windows):
    noisy, clean = windows
    tr = gan.DualGANTrainer(epochs=30, seed=0, hidden=8).fit(noisy[:48], clean[:48])
    assert set(tr.history_) == {"d", "g_adv", "g_rec", "g_cycle"}
    assert tr.history_["g_rec"][-1] < tr.history_["g_rec"][0]
    den = tr.denoise(noisy[48:])
    before = np.mean([_corr(a, b) for a, b in zip(noisy[48:], clean[48:])])
    after = np.mean([_corr(a, b) for a, b in zip(den, clean[48:])])
    assert after > before and after > 0.6
    assert all(hasattr(tr, a) for a in ("G_", "Gn_", "D_", "Dn_"))
