"""Non-inferiority: a clearly inferior arm fails and a clearly non-inferior arm passes for both coverage methods
and both error-SD methods; Farrington-Manning at margin zero reduces to the pooled two-proportion z-test; the
Wald-cc and F-test numbers match hand calculations."""
from __future__ import annotations

import numpy as np
import pytest
from scipy import stats

from palmppg.core.config import rng
from palmppg.eval.noninferiority import (
    coverage_noninferiority,
    error_sd_ratio_noninferiority,
    error_sd_ratio_noninferiority_bootstrap,
    fm_restricted_mle,
)


@pytest.mark.parametrize("method", ["farrington_manning", "wald_cc"])
def test_coverage_clear_cases(method):
    good = coverage_noninferiority(94.0, 300, 95.0, 300, margin_points=10.0, alpha=0.05, method=method)
    assert good["noninferior"] is True and good["p"] < 0.001 and good["ci_bound"] > -10.0
    assert good["estimate"] == pytest.approx(-1.0)
    bad = coverage_noninferiority(70.0, 300, 95.0, 300, margin_points=10.0, alpha=0.05, method=method)
    assert bad["noninferior"] is False and bad["p"] > 0.5 and bad["ci_bound"] < -10.0
    assert set(good) >= {"estimate", "ci_bound", "margin", "noninferior", "p"}


def test_farrington_manning_at_zero_margin_equals_pooled_z_test():
    p1, p2, n = 0.90, 0.95, 200
    r = coverage_noninferiority(100 * p1, n, 100 * p2, n, margin_points=0.0, alpha=0.05)
    pooled = (p1 * n + p2 * n) / (2 * n)
    se = np.sqrt(pooled * (1 - pooled) * (2 / n))
    z = (p1 - p2) / se
    assert r["z"] == pytest.approx(z, abs=1e-5)
    assert r["p"] == pytest.approx(stats.norm.sf(z), abs=1e-5)
    t1, t2 = fm_restricted_mle(p1, p2, n, n, 0.0)
    assert t1 == pytest.approx(pooled, abs=1e-6) and t2 == pytest.approx(pooled, abs=1e-6)
    t1, t2 = fm_restricted_mle(p1, p2, n, n, -0.1)
    assert t1 - t2 == pytest.approx(-0.1, abs=1e-9)


def test_wald_cc_matches_hand_calculation():
    p1, p2, n = 0.90, 0.95, 200
    r = coverage_noninferiority(90.0, n, 95.0, n, margin_points=10.0, alpha=0.05, method="wald_cc")
    se = np.sqrt(p1 * (1 - p1) / n + p2 * (1 - p2) / n)
    cc = 0.5 * (1 / n + 1 / n)
    z = (p1 - p2 + 0.10 - cc) / se
    assert r["z"] == pytest.approx(z)
    assert r["p"] == pytest.approx(stats.norm.sf(z))
    assert r["ci_bound"] == pytest.approx(100 * (p1 - p2 - cc - stats.norm.ppf(0.95) * se))
    assert r["noninferior"] is (r["ci_bound"] > -10.0)


def test_coverage_edge_cases():
    r = coverage_noninferiority(100.0, 50, 100.0, 50, 10.0, 0.05, method="wald_cc")  # se == 0 falls back to FM
    assert r["method"] == "farrington_manning" and r["noninferior"] is True
    r0 = coverage_noninferiority(90.0, 0, 95.0, 10, 10.0, 0.05)
    assert r0["noninferior"] is False and np.isnan(r0["p"])
    with pytest.raises(ValueError):
        coverage_noninferiority(90.0, 10, 95.0, 10, 10.0, 0.6)


def _errors(sd, n, seed):
    e = rng(seed, "ni").normal(0.0, 1.0, n)
    return (e - e.mean()) / e.std(ddof=1) * sd  # exact SD


def test_error_sd_ratio_f_test_hand_calculation_and_clear_cases():
    a, b = _errors(8.0, 300, 1), _errors(8.0, 300, 2)
    r = error_sd_ratio_noninferiority(a, b, margin_ratio=1.15, alpha=0.05)
    assert r["estimate"] == pytest.approx(1.0)
    f_stat = 1.0 / 1.15**2
    assert r["p"] == pytest.approx(stats.f.cdf(f_stat, 299, 299))
    assert r["ci_bound"] == pytest.approx(np.sqrt(1.0 / stats.f.ppf(0.05, 299, 299)))
    assert r["noninferior"] is True and r["p"] < 0.05
    worse = error_sd_ratio_noninferiority(_errors(12.0, 300, 3), b, margin_ratio=1.15, alpha=0.05)
    assert worse["estimate"] == pytest.approx(1.5) and worse["noninferior"] is False and worse["p"] > 0.5
    tiny = error_sd_ratio_noninferiority([1.0], b, 1.15, 0.05)
    assert tiny["noninferior"] is False and np.isnan(tiny["p"])


def test_error_sd_ratio_bootstrap_agrees_with_f_test_on_clear_cases():
    a, b = _errors(8.0, 300, 1), _errors(8.0, 300, 2)
    ids_a = np.repeat(np.arange(100), 3)
    ids_b = np.repeat(np.arange(100), 3)
    good = error_sd_ratio_noninferiority_bootstrap(a, b, 1.15, 0.05, ids_a, ids_b, n_resamples=400, seed=5)
    assert good["estimate"] == pytest.approx(1.0) and good["noninferior"] is True and good["p"] < 0.05
    assert good["n_participants_cmp"] == 100 and good["n_resamples"] == 400
    bad = error_sd_ratio_noninferiority_bootstrap(_errors(12.0, 300, 3), b, 1.15, 0.05, ids_a, ids_b, n_resamples=400, seed=5)
    assert bad["estimate"] == pytest.approx(1.5) and bad["noninferior"] is False and bad["p"] > 0.9
    again = error_sd_ratio_noninferiority_bootstrap(a, b, 1.15, 0.05, ids_a, ids_b, n_resamples=400, seed=5)
    assert again == good
