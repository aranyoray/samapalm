"""GBDTs with monotone constraints, linear and quantile baselines, the two mandatory baselines (protocol 9, 10, 11.2)."""
import numpy as np
import pandas as pd
import pytest
from scipy.stats import norm

from palmppg.core.config import rng
from palmppg.models.tabular import (
    DemographicsOnlyBaseline,
    PredictMeanBaseline,
    QuantileIntervalRegressor,
    make_elastic_net,
    make_gbdt,
    make_linear,
    make_quantile_pair,
    make_ridge,
    resolve_monotone_constraints,
)

KINDS = ["lightgbm", "xgboost", "catboost"]


@pytest.fixture(scope="module")
def monotone_data():
    g = rng(1, "mono")
    n = 400
    x1 = g.uniform(0, 1, n)
    x2 = g.normal(size=n)
    y = 3.0 * x1 + np.sin(3.0 * x2) + 0.3 * g.normal(size=n)
    X = pd.DataFrame({"x1": x1, "x2": x2})
    grid = pd.DataFrame({"x1": np.linspace(0, 1, 200), "x2": np.full(200, 0.3)})
    return X, y, grid


@pytest.mark.parametrize("kind", KINDS)
def test_monotone_constraint_honoured(kind, monotone_data):
    X, y, grid = monotone_data
    m = make_gbdt(kind, "regression", monotone_constraints={"x1": 1}, seed=0, n_estimators=60).fit(X, y)
    assert m.monotone_resolved_ == [1, 0]
    p = m.predict(grid)
    assert np.all(np.diff(p) >= -1e-9), f"{kind}: predictions must be non-decreasing in x1"
    assert p[-1] - p[0] > 1.5                               # and the slope (3 per unit) is largely captured
    m_dec = make_gbdt(kind, "regression", monotone_constraints={"x1": -1}, seed=0, n_estimators=60).fit(X, -y)
    assert np.all(np.diff(m_dec.predict(grid)) <= 1e-9)


def test_unconstrained_lightgbm_violates_monotonicity(monotone_data):
    X, y, grid = monotone_data
    m = make_gbdt("lightgbm", "regression", seed=0, n_estimators=60).fit(X, y)
    assert not np.all(np.diff(m.predict(grid)) >= -1e-9)   # shows the constraint above is doing work


def test_constraint_resolution_errors():
    assert resolve_monotone_constraints({"b": -1}, ["a", "b", "c"]) == [0, -1, 0]
    assert resolve_monotone_constraints(None, ["a"]) == [0]
    with pytest.raises(KeyError):
        resolve_monotone_constraints({"zz": 1}, ["a"])
    with pytest.raises(ValueError):
        resolve_monotone_constraints({"a": 2}, ["a"])
    with pytest.raises(ValueError, match="LightGBM cannot combine"):
        make_gbdt("lightgbm", "quantile", quantile_alpha=0.1, monotone_constraints={"a": 1}).fit(
            pd.DataFrame({"a": np.arange(30.0)}), np.arange(30.0))
    with pytest.raises(ValueError):
        make_gbdt("nope")._validate()
    with pytest.raises(ValueError):
        make_gbdt("lightgbm", "quantile")._validate()


@pytest.mark.parametrize("kind", KINDS)
def test_gbdt_classification_with_string_labels(kind):
    g = rng(3, "clf")
    n = 300
    X = pd.DataFrame({"a": g.normal(size=n), "b": g.normal(size=n)})
    y = np.where(X["a"] + 0.5 * X["b"] > 0, "af", "sinus")
    m = make_gbdt(kind, "classification", seed=0, n_estimators=40).fit(X, y)
    assert list(m.classes_) == ["af", "sinus"]
    p = m.predict_proba(X)
    assert p.shape == (n, 2) and np.allclose(p.sum(axis=1), 1.0)
    assert (m.predict(X) == y).mean() > 0.9
    y3 = np.array(["low", "mid", "high"])[np.digitize(X["a"], [-0.5, 0.5])]
    m3 = make_gbdt(kind, "classification", seed=0, n_estimators=30).fit(X, y3)
    assert m3.predict_proba(X).shape == (n, 3)
    assert (m3.predict(X) == y3).mean() > 0.85


def test_linear_quantile_pair_recovers_known_quantiles():
    g = rng(4, "quant")
    n = 2000
    x = g.uniform(-2, 2, n)
    y = 2.0 * x + g.normal(size=n)                     # true q_a(x) = 2x + z_a
    X = pd.DataFrame({"x": x})
    alpha = 0.2
    q = make_quantile_pair(alpha, kind="linear").fit(X, y)
    grid = pd.DataFrame({"x": np.linspace(-1.5, 1.5, 7)})
    lo, hi = q.predict_interval(grid)
    z = norm.ppf(1 - alpha / 2)
    assert np.allclose(lo, 2 * grid["x"] - z, atol=0.15)
    assert np.allclose(hi, 2 * grid["x"] + z, atol=0.15)
    assert np.allclose(q.predict(grid), 2 * grid["x"], atol=0.15)
    assert np.all(lo <= hi) and q.crossing_rate_ == 0.0
    cover = np.mean((y >= q.predict_interval(X)[0]) & (y <= q.predict_interval(X)[1]))
    assert abs(cover - (1 - alpha)) < 0.03


@pytest.mark.parametrize("kind", KINDS)
def test_gbdt_quantile_pair_ordering_and_coverage(kind):
    g = rng(5, "gq")
    n = 500
    x = g.uniform(-2, 2, n)
    y = np.sin(2 * x) + 0.5 * g.normal(size=n)
    X = pd.DataFrame({"x": x})
    q = make_quantile_pair(0.2, kind=kind, seed=0, n_estimators=50).fit(X, y)
    lo, hi = q.predict_interval(X)
    assert np.all(lo <= hi)
    assert abs(np.mean((y >= lo) & (y <= hi)) - 0.8) < 0.1
    mid = q.predict(X)
    assert np.mean((mid >= lo) & (mid <= hi)) > 0.9


def test_quantile_pair_repairs_crossings():
    class Const:
        def __init__(self, v):
            self.v = v

        def get_params(self, deep=True):
            return {"v": self.v}

        def set_params(self, **kw):
            self.v = kw.get("v", self.v)
            return self

        def fit(self, X, y):
            return self

        def predict(self, X):
            return np.full(len(X), self.v)

    q = QuantileIntervalRegressor(Const(2.0), Const(1.0), alpha=0.1).fit(np.zeros((3, 1)), np.zeros(3))
    lo, hi = q.predict_interval(np.zeros((3, 1)))
    assert np.all(lo == 1.0) and np.all(hi == 2.0) and q.crossing_rate_ == 1.0
    assert np.allclose(q.predict(np.zeros((3, 1))), 1.5)
    with pytest.raises(ValueError):
        make_quantile_pair(1.5)


def test_linear_baselines_recover_linear_truth():
    g = rng(6, "lin")
    n = 300
    X = pd.DataFrame({"a": g.normal(size=n), "b": g.normal(size=n)})
    y = 3.0 * X["a"] - 2.0 * X["b"] + 0.05 * g.normal(size=n)
    for est in (make_ridge(alpha=1e-3), make_elastic_net(alpha=1e-3), make_linear("ridge"),
                make_linear("elastic_net", alpha=1e-3)):
        est.fit(X, y)
        assert np.sqrt(np.mean((est.predict(X) - y) ** 2)) < 0.2
    yc = (y > 0).astype(int)
    for est in (make_linear("ridge", "classification"), make_linear("elastic_net", "classification")):
        est.fit(X, yc)
        assert (est.predict(X) == yc).mean() > 0.95
    with pytest.raises(ValueError):
        make_linear("lasso")
    with pytest.raises(ValueError):
        make_linear("ridge", "ranking")


def test_predict_mean_baseline():
    g = rng(7, "mean")
    y = g.normal(10.0, 2.0, 50)
    b = PredictMeanBaseline().fit(np.zeros((50, 2)), y)
    assert np.allclose(b.predict(np.zeros((7, 2))), y.mean())
    yc = np.array(["sinus"] * 30 + ["af"] * 20)
    c = PredictMeanBaseline(task="classification").fit(np.zeros((50, 1)), yc)
    assert list(c.classes_) == ["af", "sinus"] and np.allclose(c.prior_, [0.4, 0.6])
    assert (c.predict(np.zeros((3, 1))) == "sinus").all()
    assert np.allclose(c.predict_proba(np.zeros((2, 1))), [[0.4, 0.6], [0.4, 0.6]])
    assert PredictMeanBaseline().fit([np.zeros((3, 1)), np.zeros((5, 1))], [1.0, 3.0]).predict([None]) == [2.0]
    with pytest.raises(ValueError):
        PredictMeanBaseline(task="x").fit(np.zeros((2, 1)), [0, 1])


def test_demographics_only_baseline():
    g = rng(8, "demo")
    n = 300
    df = pd.DataFrame({"age": g.uniform(20, 80, n), "sex": g.choice(["F", "M"], n), "bmi": g.uniform(18, 35, n),
                       "pulse__phone__x": g.normal(size=n)})
    y = 0.5 * df["age"] + 5.0 * (df["sex"] == "M") + 0.1 * df["bmi"] + 0.1 * g.normal(size=n)
    df.loc[:5, "bmi"] = np.nan                            # imputed, not fatal
    b = DemographicsOnlyBaseline(alpha=1e-3).fit(df, y)
    assert b.numeric_columns_ == ["age", "bmi"] and b.categorical_columns_ == ["sex"]
    r2 = 1 - np.var(y - b.predict(df)) / np.var(y)
    assert r2 > 0.99
    with pytest.raises(KeyError, match="missing"):
        DemographicsOnlyBaseline(columns=("age", "height_cm")).fit(df, y)
    with pytest.raises(TypeError):
        DemographicsOnlyBaseline().fit(df.to_numpy(), y)
    c = DemographicsOnlyBaseline(task="classification").fit(df, (y > y.median()).astype(int))
    assert c.predict_proba(df).shape == (n, 2) and (c.predict(df) == (y > y.median())).mean() > 0.9
