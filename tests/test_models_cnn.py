"""STMap construction and the from-scratch ResNet-18 (protocol 9 "ResNet-18 on STMaps")."""
import numpy as np
import pytest

from palmppg.core.config import rng
from palmppg.models.cnn import make_stmap_regressor, stmap_from_patches
from palmppg.models.tabular import PredictMeanBaseline


def _patches(g, f, T=64, rows=4, cols=6, n_ch=3):
    t = np.arange(T) / 30.0
    base = np.sin(2 * np.pi * f * t)
    p = np.zeros((T, rows, cols, n_ch), np.float32)
    for r in range(rows):
        for c in range(cols):
            for ch in range(n_ch):
                p[:, r, c, ch] = 100 + (0.5 + 0.5 * ch) * base * (1 + 0.1 * r) + 0.3 * g.normal(size=T)
    return p


def test_stmap_from_patches_exact_values():
    p = np.zeros((4, 1, 2, 1), np.float32)
    p[:, 0, 0, 0] = [1.0, 3.0, 2.0, 5.0]
    p[:, 0, 1, 0] = [2.0, np.nan, 4.0, 4.0]
    s = stmap_from_patches(p)
    assert s.shape == (1, 2, 4)
    assert np.allclose(s[0, 0], [0.0, 0.5, 0.25, 1.0])
    assert np.allclose(s[0, 1], [0.0, 0.5, 1.0, 1.0])            # NaN bridged by interpolation (2 -> 3 -> 4)
    raw = stmap_from_patches(p, normalise=False)
    assert np.allclose(raw[0, 1], [2.0, 3.0, 4.0, 4.0])
    all_nan = np.full((3, 1, 1, 1), np.nan, np.float32)
    assert np.all(stmap_from_patches(all_nan) == 0.0)
    with pytest.raises(ValueError):
        stmap_from_patches(np.zeros((3, 2, 2)))


def test_resnet18_matches_canonical_parameter_count():
    torch = pytest.importorskip("torch")
    from palmppg.models.nets.cnn import ResNet18

    m = ResNet18(3, 1000, width=64, small_input=False, dropout=0.0)
    assert sum(p.numel() for p in m.parameters()) == 11_689_512       # torchvision resnet18, 1000 classes
    x = torch.zeros(2, 3, 64, 64)
    assert m(x).shape == (2, 1000) and m.embed(x).shape == (2, 512)
    small = ResNet18(4, 1, width=8)
    assert small.embed_dim == 64 and small(torch.zeros(2, 4, 24, 64)).shape == (2, 1)


def test_stmap_regressor_beats_mean_baseline():
    pytest.importorskip("torch")
    g = rng(7, "cnn")
    fs = g.uniform(0.7, 2.0, 60)
    X = np.stack([stmap_from_patches(_patches(g, f)) for f in fs])
    assert X.shape == (60, 3, 24, 64)
    model = make_stmap_regressor(width=8, epochs=12, lr=3e-3, seed=0, batch_size=12).fit(X[:48], fs[:48])
    assert model.n_parameters_ < 200_000
    mse = np.mean((model.predict(X[48:]) - fs[48:]) ** 2)
    base = np.mean((PredictMeanBaseline().fit(X[:48], fs[:48]).predict(X[48:]) - fs[48:]) ** 2)
    assert mse < 0.3 * base, f"mse {mse:.4f} vs baseline {base:.4f}"
    assert model.transform(X[:2]).shape == (2, 64)
    with pytest.raises(ValueError):
        model.predict(np.zeros((2, 2, 24, 64)))
