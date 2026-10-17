"""DANN: domain accuracy falls below the no-adversary baseline on a synthetic domain shift (E11)."""
import numpy as np
import pytest

from palmppg.core.config import rng
from palmppg.core.tracks import FeatureRegistry
from palmppg.models import adversarial


def _dataset(seed, n=400):
    g = rng(seed, "dann")
    z = g.normal(size=(n, 3))                                   # physiology
    dom = g.integers(0, 2, n)                                   # unit / operator label
    y = z @ np.array([1.0, -0.5, 0.8]) + 0.1 * g.normal(size=n)
    shift = 2.0 * (dom - 0.5)
    X = np.column_stack([z, shift + 0.3 * g.normal(size=n), shift + 0.3 * g.normal(size=n)])
    return X, y, dom


def test_domain_accuracy_drops_with_adversary():
    pytest.importorskip("torch")
    X, y, dom = _dataset(12)
    Xtr, ytr, dtr = X[:300], y[:300], dom[:300]
    Xte, yte, dte = X[300:], y[300:], dom[300:]
    base = adversarial.DANNEstimator(lambda_domain=0.0, epochs=30, lr=3e-3, seed=0, emb_dim=8).fit(Xtr, ytr, dtr)
    dann = adversarial.DANNEstimator(lambda_domain=1.0, epochs=40, lr=3e-3, seed=0, emb_dim=8).fit(Xtr, ytr, dtr)
    base_probe = base.probe_domain_accuracy(Xte, dte)
    dann_probe = dann.probe_domain_accuracy(Xte, dte)
    assert base_probe > 0.75                                     # embeddings carry the domain without an adversary
    assert dann_probe < base_probe - 0.3 and dann_probe < 0.6    # and much less with it
    assert dann.domain_accuracy_ < base.domain_accuracy_
    assert abs(dann.domain_chance_ - 0.5) < 0.1
    var = np.var(yte)
    assert np.mean((dann.predict(Xte) - yte) ** 2) < 0.15 * var  # the endpoint is still predicted
    assert np.mean((base.predict(Xte) - yte) ** 2) < 0.15 * var
    Z = dann.transform(Xte)
    assert Z.shape == (100, 8) and len(dann.history_domain_) == 40
    assert np.array_equal(dann.domain_classes_, [0, 1])


def test_sequence_extractor_and_validation():
    pytest.importorskip("torch")
    g = rng(5, "dann-seq")
    X = [np.stack([np.sin(np.arange(20) / 3 + g.uniform(0, 6))], 1) for _ in range(40)]
    y = g.normal(size=40)
    dom = np.array(["unit_01", "unit_02"] * 20)
    m = adversarial.DANNEstimator(extractor="conv1d", emb_dim=4, epochs=2, seed=0, lambda_schedule="ramp",
                                  domain_hidden=8, model_kw={"hidden": 8, "n_layers": 1}).fit(X, y, dom)
    assert m.transform(X[:3]).shape == (3, 4) and m.predict(X[:3]).shape == (3,)
    assert list(m.domain_classes_) == ["unit_01", "unit_02"]
    assert 0.0 <= m.domain_accuracy(X, dom) <= 1.0
    with pytest.raises(ValueError, match="domains"):
        adversarial.DANNEstimator(epochs=1).fit(np.zeros((4, 2)), np.zeros(4))


def test_feature_columns_registered():
    reg = FeatureRegistry()
    names = adversarial.register_features(reg, cameras=("phone",), rois=("fused",), dann_dim=4)
    assert names == adversarial.feature_columns("phone", dim=4) == [f"embedding__phone__fused__dann__d00{i}" for i in range(4)]
    assert adversarial.register_features(reg, cameras=("phone",), rois=("fused",), dann_dim=4) == names
