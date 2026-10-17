"""Late fusion with ridge-learned out-of-fold weights and cross-attention fusion (protocol 9)."""
import numpy as np
import pandas as pd
import pytest

from palmppg.core.config import rng
from palmppg.models.fusion import LateFusion, make_cross_attention_regressor
from palmppg.models.tabular import PredictMeanBaseline, make_gbdt, make_ridge


@pytest.fixture(scope="module")
def tab():
    g = rng(2, "fus")
    n = 300
    X = pd.DataFrame(g.normal(size=(n, 4)), columns=list("abcd"))
    y = (2 * X["a"] + np.sin(2 * X["b"]) + 0.2 * g.normal(size=n)).to_numpy()
    groups = np.repeat(np.arange(60), 5)
    return X, y, groups


def test_late_fusion_weights_follow_base_quality(tab):
    X, y, groups = tab
    lf = LateFusion({"ridge": make_ridge(), "mean": PredictMeanBaseline()}, seed=0, ridge_alpha=1e-3)
    lf.fit(X[:240], y[:240], groups=groups[:240])
    assert lf.oof_predictions_.shape == (240, 2) and np.isfinite(lf.oof_predictions_).all()
    assert abs(lf.weights_["ridge"] - 1.0) < 0.1
    # the mean member's out-of-fold predictions are nearly constant: its contribution must be negligible
    assert abs(lf.weights_["mean"]) * lf.oof_predictions_[:, 1].std() < 0.05 * y[:240].std()
    fused = np.mean((lf.predict(X[240:]) - y[240:]) ** 2)
    ridge = np.mean((lf.estimators_["ridge"].predict(X[240:]) - y[240:]) ** 2)
    assert fused < 1.05 * ridge
    lf2 = LateFusion({"ridge": make_ridge(), "lgb": make_gbdt("lightgbm", n_estimators=40)}, seed=0).fit(
        X[:240], y[:240], groups=groups[:240])
    assert lf2.weights_["lgb"] > lf2.weights_["ridge"] > 0
    assert np.mean((lf2.predict(X[240:]) - y[240:]) ** 2) < ridge


def test_late_fusion_dict_inputs_and_classification(tab):
    X, y, groups = tab
    inputs = {"left": X[["a", "b"]], "right": X[["c", "d"]]}
    lf = LateFusion({"left": make_ridge(), "right": make_ridge()}, seed=0).fit(inputs, y)
    assert lf.weights_["left"] > lf.weights_["right"]
    assert lf.predict(inputs).shape == (300,)
    with pytest.raises(KeyError):
        lf.predict({"left": X[["a", "b"]]})
    yc = (y > np.median(y)).astype(int)
    clf = LateFusion({"a": make_gbdt("lightgbm", "classification", n_estimators=20),
                      "b": make_gbdt("xgboost", "classification", n_estimators=20)}, task="classification", seed=0)
    clf.fit(X, yc, groups=groups)
    p = clf.predict_proba(X)
    assert p.shape == (300, 2) and (clf.predict(X) == yc).mean() > 0.8
    with pytest.raises(ValueError):
        LateFusion({"a": make_ridge()}, task="ranking").fit(X, y)


def test_cross_attention_fusion_beats_mean_baseline():
    pytest.importorskip("torch")
    g = rng(3, "xattn")

    def make(n):
        A, B, Y = [], [], []
        for _ in range(n):
            f = g.uniform(0.5, 1.5)
            T = int(g.integers(15, 30))
            t = np.arange(T)
            A.append(np.stack([np.sin(2 * np.pi * f * t / 10) + 0.1 * g.normal(size=T)], 1))
            B.append(np.stack([np.cos(2 * np.pi * f * np.arange(T + 5) / 10)], 1))
            Y.append(f)
        return A, B, np.array(Y)

    A, B, Y = make(80)
    model = make_cross_attention_regressor(epochs=20, lr=3e-3, seed=0, model_kw={"d_model": 16, "n_heads": 2})
    model.fit((A[:60], B[:60]), Y[:60])
    mse = np.mean((model.predict((A[60:], B[60:])) - Y[60:]) ** 2)
    base = np.mean((PredictMeanBaseline().fit(A[:60], Y[:60]).predict(A[60:]) - Y[60:]) ** 2)
    assert mse < 0.3 * base, f"mse {mse:.4f} vs baseline {base:.4f}"
    assert model.transform((A[:2], B[:2])).shape == (2, 32)
    with pytest.raises(ValueError):
        model.predict((A[:3], B[:2]))
    with pytest.raises(ValueError):
        model.predict(A[:3])
