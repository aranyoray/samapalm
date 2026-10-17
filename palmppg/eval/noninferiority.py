"""One-sided non-inferiority tests for the equity analysis (protocol section 7 and go/no-go of section 10).

Coverage: H0 p_cmp - p_ref <= -margin (inferior) against H1 p_cmp - p_ref > -margin, where margin is in
proportion units (``margin_points`` / 100). Two test statistics are offered: Wald with continuity correction, and
Farrington-Manning (score test with restricted maximum-likelihood variance). The reported ``ci_bound`` is the
lower one-sided (1 - alpha) bound on the difference in points; non-inferior when it exceeds -margin.

Error SD: H0 sd_cmp / sd_ref >= margin_ratio against H1 sd_cmp / sd_ref < margin_ratio. The parametric version is
a one-sided F-test on the variance ratio (assumes near-normal errors); ``ci_bound`` is the upper one-sided
(1 - alpha) bound on the SD ratio. The bootstrap version resamples participants and uses the (1 - alpha)
percentile of the ratio as the bound; it needs no normality assumption and is the one reported alongside.

Margins and alpha are read from the frozen config by the callers (``palmppg.audits.equity``); this module never
chooses them.
"""
from __future__ import annotations

from typing import Any

import numpy as np
from scipy import optimize, stats

from palmppg.core.config import rng


def _check_alpha(alpha: float) -> float:
    if not (0.0 < alpha < 0.5):
        raise ValueError("alpha must be in (0, 0.5)")
    return float(alpha)


def _result(estimate, ci_bound, margin, noninferior, p, **extra) -> dict[str, Any]:
    out = {"estimate": float(estimate), "ci_bound": float(ci_bound), "margin": float(margin),
           "noninferior": bool(noninferior), "p": float(p)}
    out.update(extra)
    return out


# --------------------------------------------------------------------------- coverage (proportions)
def fm_restricted_mle(p1: float, p2: float, n1: int, n2: int, d0: float) -> tuple[float, float]:
    """Restricted MLEs (p1~, p2~) of two binomial proportions under the constraint p1 - p2 = d0
    (Farrington & Manning 1990), found by bounded maximisation of the constrained log-likelihood."""
    x1, x2 = p1 * n1, p2 * n2
    lo = max(0.0, -d0) + 1e-12
    hi = min(1.0, 1.0 - d0) - 1e-12
    if hi <= lo:
        raise ValueError("no feasible restricted proportions for this margin")

    def nll(q2: float) -> float:
        q1 = q2 + d0
        q1 = min(max(q1, 1e-12), 1 - 1e-12)
        q2 = min(max(q2, 1e-12), 1 - 1e-12)
        return -(x1 * np.log(q1) + (n1 - x1) * np.log1p(-q1) + x2 * np.log(q2) + (n2 - x2) * np.log1p(-q2))

    res = optimize.minimize_scalar(nll, bounds=(lo, hi), method="bounded", options={"xatol": 1e-12})
    q2 = float(res.x)
    return q2 + d0, q2


def _fm_z(p1: float, p2: float, n1: int, n2: int, d0: float) -> float:
    t1, t2 = fm_restricted_mle(p1, p2, n1, n2, d0)
    var = t1 * (1 - t1) / n1 + t2 * (1 - t2) / n2
    if var <= 0:
        return float("inf") if (p1 - p2 - d0) >= 0 else float("-inf")
    return (p1 - p2 - d0) / np.sqrt(var)


def coverage_noninferiority(cov_cmp: float, n_cmp: int, cov_ref: float, n_ref: int, margin_points: float,
                            alpha: float, method: str = "farrington_manning") -> dict[str, Any]:
    """One-sided non-inferiority of coverage (section 7: MST 7-10 versus 4-6, margin from the frozen config).

    ``cov_cmp``/``cov_ref`` are coverage percentages (0..100) of the comparison and reference arms with
    ``n_cmp``/``n_ref`` attempted readings; ``margin_points`` is in percentage points. ``method`` is
    ``"farrington_manning"`` (default) or ``"wald_cc"`` (Wald with continuity correction (1/n1 + 1/n2)/2).
    Returns estimate (difference cmp - ref in points), ci_bound (lower one-sided bound in points), margin,
    noninferior, p, plus method and inputs.
    """
    alpha = _check_alpha(alpha)
    n1, n2 = int(n_cmp), int(n_ref)
    if n1 <= 0 or n2 <= 0:
        return _result(float("nan"), float("nan"), margin_points, False, float("nan"), method=method,
                       n_cmp=n1, n_ref=n2, note="empty arm")
    p1, p2 = float(cov_cmp) / 100.0, float(cov_ref) / 100.0
    if not (0 <= p1 <= 1 and 0 <= p2 <= 1):
        raise ValueError("coverages must be percentages in 0..100")
    delta = float(margin_points) / 100.0
    diff = p1 - p2
    z_a = float(stats.norm.ppf(1.0 - alpha))
    if method == "wald_cc":
        se = np.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
        cc = 0.5 * (1.0 / n1 + 1.0 / n2)
        if se == 0:  # degenerate (all or none covered in both arms): fall back to the score test
            return coverage_noninferiority(cov_cmp, n_cmp, cov_ref, n_ref, margin_points, alpha, "farrington_manning")
        z = (diff + delta - cc) / se
        bound = diff - cc - z_a * se
        p = float(stats.norm.sf(z))
    elif method == "farrington_manning":
        z = _fm_z(p1, p2, n1, n2, -delta)
        p = float(stats.norm.sf(z))

        def f(d):
            return _fm_z(p1, p2, n1, n2, d) - z_a

        lo_d, hi_d = -1.0 + 1e-9, 1.0 - 1e-9
        try:
            bound = float(optimize.brentq(f, lo_d, hi_d, xtol=1e-10, maxiter=200))
        except ValueError:
            bound = lo_d if f(lo_d) < 0 else hi_d
    else:
        raise ValueError(f"unknown method {method}")
    return _result(100.0 * diff, 100.0 * bound, margin_points, bound > -delta, p, method=method, z=float(z),
                   n_cmp=n1, n_ref=n2, cov_cmp=float(cov_cmp), cov_ref=float(cov_ref), alpha=alpha)


# --------------------------------------------------------------------------- error SD ratio
def _finite(a) -> np.ndarray:
    x = np.asarray(a, dtype=float).ravel()
    return x[np.isfinite(x)]


def error_sd_ratio_noninferiority(err_cmp, err_ref, margin_ratio: float, alpha: float) -> dict[str, Any]:
    """One-sided F-test that the error SD of the comparison arm is not worse than ``margin_ratio`` times the
    reference arm's (section 7, ratio margin from the frozen config). Errors are pred - true; SD uses ddof=1.
    Returns estimate (sd_cmp / sd_ref), ci_bound (upper one-sided bound on the ratio), margin, noninferior, p."""
    alpha = _check_alpha(alpha)
    a, b = _finite(err_cmp), _finite(err_ref)
    if a.size < 2 or b.size < 2:
        return _result(float("nan"), float("nan"), margin_ratio, False, float("nan"), method="f_test",
                       n_cmp=int(a.size), n_ref=int(b.size), note="fewer than two errors in an arm")
    s1, s2 = np.std(a, ddof=1), np.std(b, ddof=1)
    if s2 == 0:
        return _result(float("inf") if s1 > 0 else 1.0, float("inf"), margin_ratio, False, float("nan"),
                       method="f_test", n_cmp=int(a.size), n_ref=int(b.size), note="reference SD is zero")
    ratio = float(s1 / s2)
    df1, df2 = a.size - 1, b.size - 1
    f_stat = (ratio**2) / (float(margin_ratio) ** 2)
    p = float(stats.f.cdf(f_stat, df1, df2))
    upper_var = (ratio**2) / float(stats.f.ppf(alpha, df1, df2))
    bound = float(np.sqrt(upper_var))
    return _result(ratio, bound, margin_ratio, bound < float(margin_ratio), p, method="f_test", f=float(f_stat),
                   df1=int(df1), df2=int(df2), sd_cmp=float(s1), sd_ref=float(s2), n_cmp=int(a.size),
                   n_ref=int(b.size), alpha=alpha)


def error_sd_ratio_noninferiority_bootstrap(err_cmp, err_ref, margin_ratio: float, alpha: float,
                                            ids_cmp=None, ids_ref=None, n_resamples: int = 2000,
                                            seed: int | None = 0, salt: str = "sd_ratio_ni") -> dict[str, Any]:
    """Bootstrap counterpart of ``error_sd_ratio_noninferiority``: participants (``ids_*``; rows when None) are
    resampled with replacement in each arm, the SD ratio is recomputed, ``ci_bound`` is the (1 - alpha)
    percentile of the ratio, ``p`` is the fraction of resamples with ratio >= margin (a one-sided bootstrap
    p-value), and non-inferior means ci_bound < margin."""
    alpha = _check_alpha(alpha)
    a = np.asarray(err_cmp, dtype=float).ravel()
    b = np.asarray(err_ref, dtype=float).ravel()
    ia = np.arange(a.size) if ids_cmp is None else np.asarray(ids_cmp)
    ib = np.arange(b.size) if ids_ref is None else np.asarray(ids_ref)
    if ia.shape != a.shape or ib.shape != b.shape:
        raise ValueError("ids must match the error arrays")
    ka = ia[np.isfinite(a)]
    kb = ib[np.isfinite(b)]
    a, b = a[np.isfinite(a)], b[np.isfinite(b)]
    if a.size < 2 or b.size < 2:
        return _result(float("nan"), float("nan"), margin_ratio, False, float("nan"), method="bootstrap",
                       n_cmp=int(a.size), n_ref=int(b.size), note="fewer than two errors in an arm")
    ua, inva = np.unique(ka.astype(str), return_inverse=True)
    ub, invb = np.unique(kb.astype(str), return_inverse=True)
    ga = [np.flatnonzero(inva == j) for j in range(len(ua))]
    gb = [np.flatnonzero(invb == j) for j in range(len(ub))]
    g = rng(seed, salt)
    ratios = np.empty(int(n_resamples), dtype=float)
    for r in range(int(n_resamples)):
        xa = np.concatenate([ga[j] for j in g.integers(0, len(ua), size=len(ua))])
        xb = np.concatenate([gb[j] for j in g.integers(0, len(ub), size=len(ub))])
        sa, sb = np.std(a[xa], ddof=1), np.std(b[xb], ddof=1)
        ratios[r] = sa / sb if sb > 0 else np.nan
    ok = np.isfinite(ratios)
    point = float(np.std(a, ddof=1) / np.std(b, ddof=1))
    if ok.sum() == 0:
        return _result(point, float("nan"), margin_ratio, False, float("nan"), method="bootstrap", note="all resamples degenerate")
    bound = float(np.percentile(ratios[ok], 100.0 * (1.0 - alpha)))
    p = float(np.mean(ratios[ok] >= float(margin_ratio)))
    return _result(point, bound, margin_ratio, bound < float(margin_ratio), p, method="bootstrap",
                   n_resamples=int(ok.sum()), n_cmp=int(a.size), n_ref=int(b.size),
                   n_participants_cmp=len(ua), n_participants_ref=len(ub), alpha=alpha)
