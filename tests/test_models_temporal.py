"""Sequence models fit a synthetic frequency target far better than the mean baseline (protocol 9, E4/E5)."""
import numpy as np
import pytest

from palmppg.core.config import rng
from palmppg.models._torchbase import pad_sequences
from palmppg.models.tabular import PredictMeanBaseline
from palmppg.models.temporal import ARCHITECTURES, make_sequence_regressor
from palmppg.models.uncertainty import MCDropout

MODEL_KW = {
    "conv1d": {"hidden": 16, "n_layers": 2},
    "tcn": {"hidden": 16, "n_levels": 2},
    "gru": {"hidden": 16},
    "small_transformer": {"d_model": 16, "n_heads": 2, "n_layers": 1, "dim_ff": 32},
}


def _make(n, seed):
    g = rng(seed, "seq")
    X, y = [], []
    for _ in range(n):
        T = int(g.integers(20, 40))
        f = g.uniform(0.5, 1.5)
        t = np.arange(T)
        X.append(np.stack([np.sin(2 * np.pi * f * t / 10) + 0.1 * g.normal(size=T), np.cos(2 * np.pi * f * t / 10)], 1))
        y.append(f)
    return X, np.array(y)


@pytest.fixture(scope="module")
def data():
    pytest.importorskip("torch")
    Xtr, ytr = _make(90, 1)
    Xte, yte = _make(30, 2)
    return Xtr, ytr, Xte, yte


def test_pad_sequences_ground_truth():
    x, mask = pad_sequences([np.ones((2, 1), np.float32), np.full((3, 1), 2.0, np.float32)])
    assert x.shape == (2, 3, 1) and mask.tolist() == [[True, True, False], [True, True, True]]
    assert x[0, 2, 0] == 0.0 and x[1, 2, 0] == 2.0


@pytest.mark.parametrize("arch", list(ARCHITECTURES))
def test_sequence_models_beat_mean_baseline(arch, data):
    Xtr, ytr, Xte, yte = data
    model = make_sequence_regressor(arch, epochs=25, lr=5e-3, seed=0, batch_size=16, model_kw=MODEL_KW[arch])
    model.fit(Xtr, ytr)
    assert len(model.history_) == 25 and model.history_[-1] < model.history_[0]
    mse = np.mean((model.predict(Xte) - yte) ** 2)
    base = np.mean((PredictMeanBaseline().fit(Xtr, ytr).predict(Xte) - yte) ** 2)
    assert mse < 0.3 * base, f"{arch}: mse {mse:.4f} vs mean baseline {base:.4f}"
    assert model.transform(Xte[:3]).shape[0] == 3


def test_deterministic_seeding(data):
    Xtr, ytr, Xte, _ = data
    a = make_sequence_regressor("tcn", epochs=3, seed=7, model_kw=MODEL_KW["tcn"]).fit(Xtr, ytr).predict(Xte)
    b = make_sequence_regressor("tcn", epochs=3, seed=7, model_kw=MODEL_KW["tcn"]).fit(Xtr, ytr).predict(Xte)
    c = make_sequence_regressor("tcn", epochs=3, seed=8, model_kw=MODEL_KW["tcn"]).fit(Xtr, ytr).predict(Xte)
    assert np.array_equal(a, b) and not np.array_equal(a, c)


def test_classification_and_mc_dropout(data):
    Xtr, ytr, Xte, yte = data
    clf = make_sequence_regressor("gru", epochs=25, lr=5e-3, seed=0, task="classification",
                                  model_kw=MODEL_KW["gru"]).fit(Xtr, (ytr > 1.0).astype(int))
    p = clf.predict_proba(Xte)
    assert p.shape == (30, 2) and np.allclose(p.sum(axis=1), 1.0)
    assert (clf.predict(Xte) == (yte > 1.0)).mean() > 0.7
    assert clf.predict_samples(Xte[:4], n_samples=3).shape == (3, 4, 2)
    reg = make_sequence_regressor("conv1d", epochs=8, seed=0, model_kw={"hidden": 16, "dropout": 0.3}).fit(Xtr, ytr)
    samples = reg.predict_samples(Xte[:5], n_samples=6, seed=1)
    assert samples.shape == (6, 5) and samples.std(axis=0).max() > 0
    assert np.array_equal(samples, reg.predict_samples(Xte[:5], n_samples=6, seed=1))
    mc = MCDropout(reg, n_samples=6, seed=1).fit(Xtr, ytr)
    mean, std = mc.predict_with_uncertainty(Xte[:5])
    assert np.allclose(mean, samples.mean(axis=0)) and np.all(std >= 0)
    with pytest.raises(AttributeError):
        reg.predict_proba(Xte[:2])


def test_input_validation(data):
    Xtr, ytr, _, _ = data
    model = make_sequence_regressor("tcn", epochs=1, model_kw=MODEL_KW["tcn"]).fit(Xtr, ytr)
    with pytest.raises(ValueError):
        model.predict([np.zeros((10, 3))])
    with pytest.raises(ValueError):
        make_sequence_regressor("tcn", epochs=1).fit(Xtr, ytr[:-1])
    with pytest.raises(KeyError):
        make_sequence_regressor("lstm")
