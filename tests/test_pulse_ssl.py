"""Self-supervised losses (finite, lower for matched pairs), STMap MAE, and the denoising GANs (6.3, 9)."""
import numpy as np
import pytest

torch = pytest.importorskip("torch")

from palmppg.pulse.denoise import (  # noqa: E402
    DualGANLite,
    PulseDiscriminator1D,
    PulseGenerator1D,
    denoise,
    train_dual_gan_lite,
    train_pulsegan,
)
from palmppg.pulse.learned.ssl import (  # noqa: E402
    STMapMAE,
    band_psd,
    contrast_phys_plus_loss,
    frequency_augment,
    periodicity_similarity,
    sample_st_signals,
    simper_loss,
)

FS = 30.0
BAND = (0.5, 4.0)
torch.set_num_threads(2)


def _sine(f, n=256, phase=0.0, noise=0.05, seed=0):
    g = torch.Generator().manual_seed(seed)
    t = torch.arange(n) / FS
    return torch.sin(2 * np.pi * f * t + phase) + noise * torch.randn(n, generator=g)


def test_band_psd_and_frequency_augment_scale_the_peak():
    x = _sine(1.0, n=600, noise=0.0)[None]
    f, p = band_psd(x, FS, BAND)
    assert abs(float(f[p[0].argmax()]) - 1.0) < 0.03 and abs(float(p.sum()) - 1.0) < 1e-5
    y = frequency_augment(x, torch.tensor([2.0]), 300)
    f2, p2 = band_psd(y, FS, BAND)
    assert abs(float(f2[p2[0].argmax()]) - 2.0) < 0.03
    assert torch.allclose(frequency_augment(x, torch.tensor([1.0]), 600), x)
    with pytest.raises(ValueError):
        frequency_augment(x, torch.tensor([3.0]), 300)
    assert float(periodicity_similarity(x[:, :300], y, FS, BAND)) < float(periodicity_similarity(x[:, :300], x[:, 300:], FS, BAND))


def test_contrast_phys_plus_matched_lower_than_mismatched():
    matched = torch.stack([torch.stack([_sine(1.1, phase=p, seed=i) for i, p in enumerate(torch.linspace(0, 3, 6))]),
                           torch.stack([_sine(1.7, phase=p, seed=10 + i) for i, p in enumerate(torch.linspace(0, 3, 6))])])
    mismatched = torch.stack([torch.stack([_sine(f, seed=i) for i, f in enumerate(torch.linspace(0.8, 2.5, 6))]),
                              torch.stack([_sine(f, seed=10 + i) for i, f in enumerate(torch.linspace(0.9, 2.6, 6))])])
    g = torch.Generator().manual_seed(1)
    lm = contrast_phys_plus_loss(matched, FS, BAND, crop_len=128, generator=g)
    g = torch.Generator().manual_seed(1)
    lmm = contrast_phys_plus_loss(mismatched, FS, BAND, crop_len=128, generator=g)
    for d in (lm, lmm):
        assert all(torch.isfinite(d[k]) for k in ("loss", "pos", "neg"))
    assert float(lm["loss"]) < float(lmm["loss"]) and float(lm["pos"]) < float(lmm["pos"])
    good_labels = torch.stack([_sine(1.1, seed=20), _sine(1.7, seed=21)])
    wrong_labels = torch.stack([_sine(2.4, seed=20), _sine(0.7, seed=21)])
    g = torch.Generator().manual_seed(1)
    l_good = contrast_phys_plus_loss(matched, FS, BAND, crop_len=128, labels=good_labels, generator=g)
    g = torch.Generator().manual_seed(1)
    l_wrong = contrast_phys_plus_loss(matched, FS, BAND, crop_len=128, labels=wrong_labels, generator=g)
    assert float(l_good["pos"]) < float(l_wrong["pos"])
    sig, sp, st = sample_st_signals(matched, 2, 3, 100, torch.Generator().manual_seed(0))
    assert sig.shape == (2, 6, 100) and sp.shape == (2, 2) and st.shape == (2, 3)
    with pytest.raises(ValueError):
        sample_st_signals(matched, 1, 1, 999)


def test_simper_consistent_speed_labels_score_lower():
    x = torch.stack([_sine(1.0, n=320, noise=0.0), _sine(1.5, n=320, noise=0.0)])
    speeds = torch.tensor([[1.0, 1.2, 1.5], [1.0, 1.2, 1.5]])
    views = torch.stack([frequency_augment(x, speeds[:, k], 200) for k in range(3)], dim=1)
    good = simper_loss(views, speeds, FS, BAND)
    shuffled = simper_loss(views, speeds[:, [2, 0, 1]], FS, BAND)
    assert torch.isfinite(good) and torch.isfinite(shuffled) and float(good) < float(shuffled)
    with pytest.raises(ValueError):
        simper_loss(views[:, :1], speeds[:, :1], FS, BAND)


def test_stmap_mae_masks_and_learns():
    torch.manual_seed(0)
    mae = STMapMAE(in_channels=3, patch=(8, 8), dim=32, depth=1, heads=4, dec_dim=16, mask_ratio=0.75)
    t = torch.arange(64) / FS
    base = torch.sin(2 * np.pi * 1.2 * t)[None, None, None, :] * torch.linspace(0.5, 1.5, 48)[None, None, :, None]
    x = base.expand(2, 3, 48, 64).clone() + 0.1 * torch.randn(2, 3, 48, 64)
    out = mae(x, generator=torch.Generator().manual_seed(0))
    assert out["pred"].shape == (2, 48, 192) and out["embedding"].shape == (2, 32) and torch.isfinite(out["loss"])
    assert abs(float(out["mask"].mean()) - 0.75) < 0.05
    assert mae.embedding(x).shape == (2, 32)
    opt = torch.optim.Adam(mae.parameters(), lr=1e-3)
    first = float(out["loss"])
    for i in range(15):
        opt.zero_grad()
        loss = mae(x, generator=torch.Generator().manual_seed(i))["loss"]
        loss.backward()
        opt.step()
    assert float(mae(x, generator=torch.Generator().manual_seed(0))["loss"]) < first


def test_denoise_generator_discriminator_shapes():
    gen = PulseGenerator1D(width=8)
    assert gen(torch.randn(2, 1, 300)).shape == (2, 1, 300)
    assert gen(torch.randn(1, 1, 97)).shape == (1, 1, 97)
    assert PulseDiscriminator1D(width=8, in_channels=2)(torch.randn(2, 2, 300)).shape == (2, 1)
    assert PulseDiscriminator1D(width=8, in_channels=1)(torch.randn(3, 1, 240)).shape == (3, 1)
    p, n = DualGANLite(width=8)(torch.randn(2, 1, 300))
    assert p.shape == (2, 1, 300) and n.shape == (2, 1, 300)


def test_gan_trainers_run_with_fixed_seeds_and_denoise_shapes():
    t = np.arange(240) / FS
    clean = np.stack([np.sin(2 * np.pi * 1.2 * t + ph) for ph in np.linspace(0, 6, 16)])
    noisy = clean + 0.8 * np.random.default_rng(0).normal(size=clean.shape)
    gen, disc, hist = train_pulsegan(noisy, clean, width=8, epochs=2, seed=0)
    assert len(hist["g_loss"]) == 2 and all(np.isfinite(hist[k]).all() for k in ("g_loss", "d_loss", "l1"))
    gen2, _, hist2 = train_pulsegan(noisy, clean, width=8, epochs=2, seed=0)
    assert hist["l1"] == pytest.approx(hist2["l1"], rel=1e-5)
    out = denoise(gen, noisy[0])
    assert out.shape == (240,) and abs(out.mean()) < 1e-5 and abs(out.std() - 1) < 1e-4
    model, disc2, h2 = train_dual_gan_lite(noisy, clean, width=8, epochs=2, seed=0)
    assert len(h2["rec"]) == 2 and np.isfinite(h2["cons"]).all()
    assert denoise(model, noisy[:3]).shape == (3, 240)
