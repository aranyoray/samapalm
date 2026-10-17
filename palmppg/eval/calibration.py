"""Probability calibration, decision curves and regression calibration (protocol section 10: rhythm models
report calibration and decision curves; BP models report calibration slope/intercept).

All inputs are plain arrays; nothing here chooses thresholds or bins from the frozen config, callers do.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd


def _xy(y, p) -> tuple[np.ndarray, np.ndarray]:
    y = np.asarray(y, dtype=float).ravel()
    p = np.asarray(p, dtype=float).ravel()
    if y.shape != p.shape:
        raise ValueError("y and p must have the same length")
    ok = np.isfinite(y) & np.isfinite(p)
    return y[ok], p[ok]


def _edges(p: np.ndarray, bins: int | Sequence[float], strategy: str) -> np.ndarray:
    if not isinstance(bins, (int, np.integer)):
        e = np.asarray(bins, dtype=float)
        if e.ndim != 1 or e.size < 2 or np.any(np.diff(e) <= 0):
            raise ValueError("bin edges must be increasing")
        return e
    if strategy == "uniform":
        return np.linspace(0.0, 1.0, int(bins) + 1)
    if strategy == "quantile":
        qs = np.quantile(p, np.linspace(0, 1, int(bins) + 1))
        qs[0], qs[-1] = min(qs[0], 0.0), max(qs[-1], 1.0)
        return np.unique(qs)
    raise ValueError("strategy must be 'uniform' or 'quantile'")


def reliability_table(y, p, bins: int | Sequence[float] = 10, strategy: str = "uniform") -> pd.DataFrame:
    """Reliability (calibration) table: per probability bin, n, mean predicted probability, observed fraction of
    positives and their gap. ``bins`` is a count (uniform or quantile edges) or explicit edges in [0, 1]."""
    y, p = _xy(y, p)
    edges = _edges(p, bins, strategy)
    idx = np.clip(np.searchsorted(edges, p, side="right") - 1, 0, len(edges) - 2)
    rows = []
    for b in range(len(edges) - 1):
        m = idx == b
        n = int(m.sum())
        mp = float(np.mean(p[m])) if n else float("nan")
        fp = float(np.mean(y[m])) if n else float("nan")
        rows.append({"bin": b, "lo": float(edges[b]), "hi": float(edges[b + 1]), "n": n, "mean_pred": mp,
                     "frac_pos": fp, "gap": (fp - mp) if n else float("nan")})
    return pd.DataFrame(rows)


def expected_calibration_error(y, p, bins: int | Sequence[float] = 10, strategy: str = "uniform") -> float:
    """ECE = sum over bins of (n_bin / n) * |observed fraction - mean predicted| (in probability units)."""
    t = reliability_table(y, p, bins, strategy)
    n = t["n"].sum()
    if n == 0:
        return float("nan")
    nz = t[t["n"] > 0]
    return float(np.sum(nz["n"].to_numpy() / n * np.abs(nz["gap"].to_numpy())))


def brier_score(y, p) -> float:
    """Mean squared difference between outcome and predicted probability."""
    y, p = _xy(y, p)
    return float(np.mean((p - y) ** 2)) if y.size else float("nan")


def decision_curve(y, p, thresholds: Sequence[float]) -> pd.DataFrame:
    """Net benefit of acting on p >= threshold versus treat-all and treat-none (Vickers & Elkin 2006).

    net_benefit = TP/N - FP/N * pt / (1 - pt). Treat-none is 0 by definition; treat-all uses TP = all positives,
    FP = all negatives. Thresholds of 1.0 or above are reported with NaN model/all net benefit (the odds are
    undefined there)."""
    y, p = _xy(y, p)
    n = y.size
    rows = []
    n_pos = float(np.sum(y == 1))
    n_neg = float(np.sum(y == 0))
    for pt in thresholds:
        pt = float(pt)
        if n == 0 or pt >= 1.0 or pt < 0.0:
            rows.append({"threshold": pt, "n": n, "tp": np.nan, "fp": np.nan, "net_benefit_model": np.nan,
                         "net_benefit_all": np.nan, "net_benefit_none": 0.0})
            continue
        w = pt / (1.0 - pt)
        pred = p >= pt
        tp = float(np.sum(pred & (y == 1)))
        fp = float(np.sum(pred & (y == 0)))
        rows.append({"threshold": pt, "n": n, "tp": tp, "fp": fp,
                     "net_benefit_model": tp / n - fp / n * w,
                     "net_benefit_all": n_pos / n - n_neg / n * w,
                     "net_benefit_none": 0.0})
    return pd.DataFrame(rows)


def regression_calibration(y_true, y_pred) -> dict[str, Any]:
    """Calibration of a continuous prediction: OLS of y_true on y_pred gives slope (1 = ideal) and intercept
    (0 = ideal), plus calibration-in-the-large (mean(y_true) - mean(y_pred)) and R^2."""
    y, p = _xy(y_true, y_pred)
    if y.size < 2 or np.std(p) == 0:
        return {"slope": float("nan"), "intercept": float("nan"), "in_the_large": float(np.mean(y) - np.mean(p)) if y.size else float("nan"),
                "r2": float("nan"), "n": int(y.size)}
    slope, intercept = np.polyfit(p, y, 1)
    resid = y - (slope * p + intercept)
    ss_res = float(np.sum(resid**2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    return {"slope": float(slope), "intercept": float(intercept), "in_the_large": float(np.mean(y) - np.mean(p)),
            "r2": (1.0 - ss_res / ss_tot) if ss_tot > 0 else float("nan"), "n": int(y.size)}


def logistic_calibration(y, p, eps: float = 1e-6) -> dict[str, Any]:
    """Logistic calibration slope/intercept: logit(y) ~ a + b * logit(p) fitted by maximum likelihood
    (b = 1, a = 0 is ideal). Probabilities are clipped to [eps, 1 - eps] before the logit."""
    import statsmodels.api as sm
    from statsmodels.tools.sm_exceptions import PerfectSeparationError

    y, p = _xy(y, p)
    if y.size < 2 or np.unique(y).size < 2:
        return {"slope": float("nan"), "intercept": float("nan"), "n": int(y.size)}
    lp = np.log(np.clip(p, eps, 1 - eps) / (1 - np.clip(p, eps, 1 - eps)))
    X = sm.add_constant(lp)
    try:
        fit = sm.GLM(y, X, family=sm.families.Binomial()).fit()
        a, b = float(fit.params[0]), float(fit.params[1])
    except (ValueError, np.linalg.LinAlgError, PerfectSeparationError):  # separated or singular design
        a, b = float("nan"), float("nan")
    return {"slope": b, "intercept": a, "n": int(y.size)}
