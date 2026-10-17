"""Ensembles, MC dropout plumbing, split conformal coverage and the abstain policy (protocol 10, 11.3)."""
import numpy as np
import pytest
from sklearn.linear_model import LinearRegression, Ridge

from palmppg.core.config import rng
from palmppg.models.uncertainty import (
    AbstainPolicy,
    DeepEnsemble,
    MCDropout,
    SplitConformal,
    abstentions_as_failures,
    conformal_quantile,
    derived_seed,
)


class NoisyMean:
    """Toy member: training mean plus a seed-dependent offset, so an ensemble has spread."""

    def __init__(self, seed):
        self.seed = seed

    def fit(self, X, y):
        self.value_ = float(np.mean(y)) + float(rng(self.seed, "member").normal(0, 0.5))
        return self

    def predict(self, X):
        return np.full(len(X), self.value_)


def test_conformal_quantile_known_values():
    scores = np.arange(1, 11, dtype=float)
    assert conformal_quantile(scores, 0.1) == 10.0          # ceil(11 * 0.9) = 10th smallest
    assert conformal_quantile(scores, 0.5) == 6.0           # ceil(11 * 0.5) = 6th
    assert conformal_quantile(scores, 0.01) == np.inf       # ceil(11 * 0.99) = 11 > n
    assert conformal_quantile([3.0, 1.0, 2.0], 0.5) == 2.0
    with pytest.raises(ValueError):
        conformal_quantile([], 0.1)


def test_split_conformal_coverage_within_five_points():
    g = rng(1, "conf")
    n = 4000
    X = g.normal(size=(n, 2))
    y = 2.0 * X[:, 0] - X[:, 1] + g.normal(size=n)
    alpha = 0.1
    sc = SplitConformal(LinearRegression(), alpha=alpha).fit(X[:300], y[:300]).calibrate(X[300:800], y[300:800])
    assert sc.n_calibration_ == 500
    cov = sc.coverage(X[800:], y[800:])
    assert abs(cov - (1 - alpha)) < 0.05
    lo, hi = sc.predict_interval(X[800:810])
    assert np.allclose(hi - lo, 2 * sc.q_)
    assert abs(sc.q_ - 1.645) < 0.2                            # 90% of |N(0,1)| within +/- 1.645
    with pytest.raises(RuntimeError):
        SplitConformal(LinearRegression(), 0.1).fit(X[:50], y[:50]).predict_interval(X[:5])
    with pytest.raises(ValueError):
        SplitConformal(LinearRegression(), 1.5).fit(X[:50], y[:50])


def test_scaled_conformal_adapts_width_and_keeps_coverage():
    g = rng(2, "hetero")
    n = 5000
    x = g.uniform(-3, 3, n)
    y = x + (0.3 + np.abs(x)) * g.normal(size=n)
    X = np.column_stack([x, np.abs(x)])
    sc = SplitConformal(LinearRegression(), alpha=0.1, scale_estimator=Ridge(alpha=1e-3)).fit(X[:500], y[:500])
    sc.calibrate(X[500:1500], y[500:1500])
    lo, hi = sc.predict_interval(X[1500:])
    width = hi - lo
    assert np.corrcoef(width, np.abs(x[1500:]))[0, 1] > 0.9
    assert abs(sc.coverage(X[1500:], y[1500:]) - 0.9) < 0.05


def test_deep_ensemble_mean_and_spread():
    y = np.arange(10, dtype=float)
    ens = DeepEnsemble(n=8, model_fn=NoisyMean, seed=3).fit(np.zeros((10, 1)), y)
    assert len(set(ens.member_seeds_)) == 8 and ens.member_seeds_[0] == derived_seed(3, "ensemble:0")
    mean, std = ens.predict_with_uncertainty(np.zeros((4, 1)))
    assert np.allclose(mean, ens.predict(np.zeros((4, 1)))) and np.all(std > 0)
    assert abs(mean[0] - 4.5) < 0.6
    assert ens.predict_samples(np.zeros((4, 1))).shape == (8, 4)
    with pytest.raises(ValueError):
        DeepEnsemble(n=0, model_fn=NoisyMean).fit(np.zeros((2, 1)), [0, 1])
    with pytest.raises(ValueError):
        DeepEnsemble(n=2).fit(np.zeros((2, 1)), [0, 1])


def test_mc_dropout_wrapper_statistics():
    class Fake:
        module_ = object()

        def predict_samples(self, X, n_samples, seed):
            g = rng(seed, "fake")
            return 5.0 + g.normal(0, 1.0, size=(n_samples, len(X)))

    mc = MCDropout(Fake(), n_samples=400, seed=0).fit(np.zeros((3, 1)), np.zeros(3))
    mean, std = mc.predict_with_uncertainty(np.zeros((3, 1)))
    assert np.allclose(mean, 5.0, atol=0.2) and np.allclose(std, 1.0, atol=0.2)
    assert mc.predict_samples(np.zeros((3, 1))).shape == (400, 3)
    with pytest.raises(TypeError):
        MCDropout(LinearRegression()).fit(np.zeros((3, 1)), np.zeros(3))


def test_abstain_policy_mask_and_failure_counting():
    pred = np.array([120.0, 130.0, np.nan, 125.0, 140.0])
    lo = np.array([110.0, 100.0, 120.0, 120.0, 130.0])
    hi = np.array([130.0, 160.0, 130.0, 130.0, 150.0])
    sqi = np.array([0.9, 0.9, 0.9, 0.2, np.nan])
    res = AbstainPolicy(max_width=30.0, min_sqi=0.35).apply(pred, lo, hi, sqi)
    assert res.abstained.tolist() == [False, True, True, True, True]
    assert np.isnan(res.prediction[1]) and res.prediction[0] == 120.0
    assert res.n == 5 and res.n_abstained == 4 and res.abstain_rate == pytest.approx(0.8)
    assert res.reasons == {"non_finite": 1, "interval_too_wide": 1, "sqi_too_low": 2}
    assert "failures" in res.note
    only_width = AbstainPolicy(max_width=30.0).apply(pred, lo, hi)
    assert only_width.abstained.tolist() == [False, True, True, False, False]
    with pytest.raises(ValueError):
        AbstainPolicy()
    with pytest.raises(ValueError):
        AbstainPolicy(max_width=1.0).apply(pred)
    with pytest.raises(ValueError):
        AbstainPolicy(min_sqi=0.5).apply(pred)
    counts = abstentions_as_failures(np.array([False, True, False, False, False, False, True, False, False, False]), 1)
    assert counts == {"n_attempted": 11, "n_abstained": 2, "n_failed_upstream": 1, "n_failures": 3, "n_delivered": 8,
                      "coverage_pct": pytest.approx(100 * 8 / 11)}
