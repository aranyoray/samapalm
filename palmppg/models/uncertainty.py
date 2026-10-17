"""Uncertainty and abstention (protocol section 10 "deep ensembles, MC dropout and conformal intervals
with an abstain option"; protocol 11.3 "failed and abstained readings count as failures").

* ``DeepEnsemble(n, model_fn)``: ``n`` members built by ``model_fn(seed_i)`` with distinct derived seeds;
  mean prediction, member spread as the uncertainty.
* ``MCDropout(model, n_samples)``: repeated stochastic forward passes of a fitted torch wrapper that
  implements ``predict_samples`` (every wrapper in this package does).
* ``SplitConformal(point_estimator, alpha)``: split conformal prediction with the finite-sample
  corrected quantile of absolute residuals (optionally scaled by a spread estimate), giving intervals
  whose marginal coverage is at least 1 - alpha under exchangeability.
* ``AbstainPolicy(max_width, min_sqi)``: NaN predictions plus a boolean mask for the readings the
  model declines. **Every abstention is a failure for coverage**: the coverage denominator is the
  number of attempted readings, and the numerator excludes abstentions and non-finite predictions.
  ``abstentions_as_failures`` gives the counts in that convention for the evaluation layer.
"""
from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np
from sklearn.base import BaseEstimator

from palmppg.core.config import rng


def derived_seed(seed: int, salt: str) -> int:
    """A deterministic 31-bit seed derived from ``(seed, salt)`` through ``core.config.rng``."""
    return int(rng(seed, salt).integers(0, 2**31 - 1))


# --------------------------------------------------------------------------- ensembles
class DeepEnsemble(BaseEstimator):
    """Ensemble of ``n`` independently seeded members (protocol 10).

    ``model_fn(seed) -> estimator`` builds one member; works for torch wrappers and for GBDTs alike.
    ``predict`` is the member mean; ``predict_with_uncertainty`` returns ``(mean, std)`` with the
    population standard deviation across members (units of ``y``); ``predict_proba`` is the mean
    probability.
    """

    def __init__(self, n: int = 5, model_fn: Callable[[int], BaseEstimator] | None = None, seed: int = 0):
        self.n = n
        self.model_fn = model_fn
        self.seed = seed

    def fit(self, X, y, **fit_params):
        if self.model_fn is None:
            raise ValueError("DeepEnsemble needs model_fn(seed) -> estimator")
        if self.n < 1:
            raise ValueError("n must be >= 1")
        self.member_seeds_ = [derived_seed(self.seed, f"ensemble:{i}") for i in range(self.n)]
        self.members_ = [self.model_fn(s).fit(X, y, **fit_params) for s in self.member_seeds_]
        if hasattr(self.members_[0], "classes_"):
            self.classes_ = self.members_[0].classes_
        return self

    def predict_samples(self, X, n_samples: int | None = None, seed: int | None = None) -> np.ndarray:
        """(n_members, N) member predictions; ``n_samples``/``seed`` are accepted for API symmetry."""
        return np.stack([np.asarray(m.predict(X), dtype=float).ravel() for m in self.members_])

    def predict(self, X):
        return self.predict_samples(X).mean(axis=0)

    def predict_with_uncertainty(self, X) -> tuple[np.ndarray, np.ndarray]:
        s = self.predict_samples(X)
        return s.mean(axis=0), s.std(axis=0)

    def predict_proba(self, X):
        return np.mean([m.predict_proba(X) for m in self.members_], axis=0)


class MCDropout(BaseEstimator):
    """Monte-Carlo dropout over a torch wrapper that implements ``predict_samples(X, n_samples, seed)``.

    ``fit`` fits the wrapped model when it is not fitted yet; ``predict`` is the mean over
    ``n_samples`` stochastic passes and ``predict_with_uncertainty`` adds the standard deviation.
    The wrapped model must contain dropout layers for the spread to be non-zero. Protocol 10.
    """

    def __init__(self, model, n_samples: int = 20, seed: int = 0):
        self.model = model
        self.n_samples = n_samples
        self.seed = seed

    def fit(self, X, y, **fit_params):
        if not hasattr(self.model, "predict_samples"):
            raise TypeError("MCDropout needs a model with predict_samples(X, n_samples, seed)")
        if not getattr(self.model, "is_fitted_", False) and not hasattr(self.model, "module_"):
            self.model.fit(X, y, **fit_params)
        self.model_ = self.model
        return self

    def predict_samples(self, X, n_samples: int | None = None, seed: int | None = None) -> np.ndarray:
        model = getattr(self, "model_", self.model)
        return np.asarray(model.predict_samples(X, n_samples or self.n_samples, self.seed if seed is None else seed))

    def predict(self, X):
        return self.predict_samples(X).mean(axis=0)

    def predict_with_uncertainty(self, X) -> tuple[np.ndarray, np.ndarray]:
        s = self.predict_samples(X)
        return s.mean(axis=0), s.std(axis=0)


# --------------------------------------------------------------------------- conformal
def conformal_quantile(scores, alpha: float) -> float:
    """Finite-sample corrected (1 - alpha) quantile: the ``ceil((n + 1)(1 - alpha))``-th smallest score,
    ``inf`` when that exceeds ``n`` (fewer calibration points than 1/alpha - 1)."""
    s = np.sort(np.asarray(scores, dtype=float).ravel())
    n = s.size
    if n == 0:
        raise ValueError("no calibration scores")
    k = math.ceil((n + 1) * (1.0 - alpha))
    if k > n:
        return float("inf")
    return float(s[k - 1])


class SplitConformal(BaseEstimator):
    """Split conformal prediction intervals around any point estimator (protocol 10).

    ``fit(X, y)`` fits the point estimator (and the optional ``scale_estimator`` on absolute residuals,
    for locally adaptive widths); ``calibrate(X_cal, y_cal)`` computes the conformity scores
    ``|y - f(x)| / s(x)`` on held-out data and their corrected quantile ``q_``;
    ``predict_interval(X)`` returns ``(f(x) - q s(x), f(x) + q s(x))``. ``scale="ensemble_std"`` uses the
    point estimator's ``predict_with_uncertainty`` spread as ``s(x)`` (plus ``scale_floor``).
    Calibration and fit data must be disjoint and split by participant (protocol 11.1).
    """

    def __init__(self, point_estimator, alpha: float = 0.1, scale_estimator=None, scale: str = "none",
                 scale_floor: float = 1e-6):
        self.point_estimator = point_estimator
        self.alpha = alpha
        self.scale_estimator = scale_estimator
        self.scale = scale
        self.scale_floor = scale_floor

    def fit(self, X, y, **fit_params):
        if not 0.0 < self.alpha < 1.0:
            raise ValueError("alpha must be in (0, 1)")
        self.point_estimator_ = self.point_estimator.fit(X, y, **fit_params)
        if self.scale_estimator is not None:
            resid = np.abs(np.asarray(y, dtype=float).ravel() - self._point(X))
            self.scale_estimator_ = self.scale_estimator.fit(X, resid)
        return self

    def _point(self, X) -> np.ndarray:
        return np.asarray(self.point_estimator_.predict(X), dtype=float).ravel()

    def _scale(self, X) -> np.ndarray:
        n = len(X)
        if self.scale_estimator is not None:
            s = np.asarray(self.scale_estimator_.predict(X), dtype=float).ravel()
        elif self.scale == "ensemble_std":
            _, s = self.point_estimator_.predict_with_uncertainty(X)
            s = np.asarray(s, dtype=float).ravel()
        else:
            return np.ones(n, dtype=float)
        return np.maximum(np.abs(s), self.scale_floor)

    def calibrate(self, X_cal, y_cal):
        y = np.asarray(y_cal, dtype=float).ravel()
        self.scores_ = np.abs(y - self._point(X_cal)) / self._scale(X_cal)
        self.q_ = conformal_quantile(self.scores_, self.alpha)
        self.n_calibration_ = int(self.scores_.size)
        return self

    def predict(self, X):
        return self._point(X)

    def predict_interval(self, X) -> tuple[np.ndarray, np.ndarray]:
        if not hasattr(self, "q_"):
            raise RuntimeError("call calibrate(X_cal, y_cal) before predict_interval")
        f = self._point(X)
        half = self.q_ * self._scale(X)
        return f - half, f + half

    def coverage(self, X, y) -> float:
        """Empirical fraction of ``y`` inside the interval (for reporting, not for tuning)."""
        lo, hi = self.predict_interval(X)
        y = np.asarray(y, dtype=float).ravel()
        return float(np.mean((y >= lo) & (y <= hi)))


# --------------------------------------------------------------------------- abstention
@dataclass
class AbstainResult:
    """Predictions with NaN at abstentions, the abstain mask and the counts in the failure convention."""

    prediction: np.ndarray
    abstained: np.ndarray
    n: int
    n_abstained: int
    reasons: dict[str, int] = field(default_factory=dict)
    note: str = "abstentions count as failures for coverage (protocol 11.3)"

    @property
    def abstain_rate(self) -> float:
        return self.n_abstained / self.n if self.n else 0.0


class AbstainPolicy:
    """Decline a reading when its interval is too wide or its signal quality too low (protocol 10).

    ``max_width``: abstain when ``hi - lo > max_width`` (units of the target, e.g. mmHg);
    ``min_sqi``: abstain when ``sqi < min_sqi`` (0..1 ``snr_band`` scale, threshold from the frozen config).
    Non-finite predictions are abstentions too. The returned predictions carry NaN at every abstention
    and the mask is True there. Downstream, abstentions are failures: they stay in the denominator of
    coverage and never in the numerator of accuracy (protocol 11.3); use ``abstentions_as_failures``.
    """

    def __init__(self, max_width: float | None = None, min_sqi: float | None = None):
        if max_width is None and min_sqi is None:
            raise ValueError("AbstainPolicy needs max_width and/or min_sqi")
        self.max_width = max_width
        self.min_sqi = min_sqi

    def apply(self, prediction, lo=None, hi=None, sqi=None) -> AbstainResult:
        pred = np.array(prediction, dtype=float).ravel()
        n = pred.size
        mask = ~np.isfinite(pred)
        reasons = {"non_finite": int(mask.sum())}
        if self.max_width is not None:
            if lo is None or hi is None:
                raise ValueError("max_width policy needs lo and hi intervals")
            width = np.asarray(hi, dtype=float).ravel() - np.asarray(lo, dtype=float).ravel()
            wide = ~np.isfinite(width) | (width > self.max_width)
            reasons["interval_too_wide"] = int(wide.sum())
            mask |= wide
        if self.min_sqi is not None:
            if sqi is None:
                raise ValueError("min_sqi policy needs sqi")
            s = np.asarray(sqi, dtype=float).ravel()
            low = ~np.isfinite(s) | (s < self.min_sqi)
            reasons["sqi_too_low"] = int(low.sum())
            mask |= low
        out = pred.copy()
        out[mask] = np.nan
        return AbstainResult(out, mask, int(n), int(mask.sum()), reasons)


def abstentions_as_failures(abstained, n_failed_upstream: int = 0) -> dict[str, float | int]:
    """Counts in the protocol 11.3 convention: attempted = len(mask) + upstream failures,
    delivered = attempted - abstained - upstream failures, coverage_pct = 100 * delivered / attempted."""
    mask = np.asarray(abstained, dtype=bool).ravel()
    attempted = int(mask.size + n_failed_upstream)
    failures = int(mask.sum() + n_failed_upstream)
    delivered = attempted - failures
    return {"n_attempted": attempted, "n_abstained": int(mask.sum()), "n_failed_upstream": int(n_failed_upstream),
            "n_failures": failures, "n_delivered": delivered,
            "coverage_pct": (100.0 * delivered / attempted) if attempted else float("nan")}


__all__ = [
    "AbstainPolicy",
    "AbstainResult",
    "DeepEnsemble",
    "MCDropout",
    "SplitConformal",
    "abstentions_as_failures",
    "conformal_quantile",
    "derived_seed",
]
