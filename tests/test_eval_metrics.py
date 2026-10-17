"""bp_metrics on known arrays (bias, SD, LoA exact), coverage counting abstentions and failed clips as failures,
format tables labelled, rhythm metrics with exact Clopper-Pearson CIs checked against scipy.stats.beta, and the
pulse-rate within-tolerance percentage."""
from __future__ import annotations

import numpy as np
import pytest
from scipy import stats

from palmppg.eval.metrics import (
    FORMAT_LABEL,
    bp_metrics,
    clopper_pearson,
    error_by_reference_tertile,
    pulse_rate_metrics,
    reference_tertile_cuts,
    rhythm_metrics,
    threshold_for_target,
)

Y = np.array([100.0, 110.0, 120.0, 130.0])
P = np.array([102.0, 108.0, 125.0, 128.0])  # errors +2, -2, +5, -2


def test_bp_metrics_exact_numbers():
    m = bp_metrics(Y, P)
    sd = np.sqrt(34.75 / 3.0)
    z = stats.norm.ppf(0.975)
    assert m["bias"] == pytest.approx(0.75)
    assert m["error_sd"] == pytest.approx(sd)
    assert m["mae"] == pytest.approx(2.75)
    assert m["rmse"] == pytest.approx(np.sqrt(9.25))
    assert m["loa_low"] == pytest.approx(0.75 - z * sd)
    assert m["loa_high"] == pytest.approx(0.75 + z * sd)
    assert m["n"] == 4 and m["n_abstained"] == 0 and m["n_failed"] == 0 and m["coverage_pct"] == 100.0


def test_coverage_counts_abstentions_and_failed_clips_as_failures():
    y = np.arange(100.0, 110.0)
    p = y + 1.0
    p[3] = np.nan  # failed clip
    p[7] = np.nan  # failed clip
    abst = np.zeros(10, dtype=bool)
    abst[[0, 1]] = True  # abstained
    m = bp_metrics(y, p, abstain_mask=abst)
    assert m["n"] == 6 and m["n_abstained"] == 2 and m["n_failed"] == 2 and m["n_attempted"] == 10
    assert m["coverage_pct"] == pytest.approx(60.0)
    assert m["bias"] == pytest.approx(1.0)
    # failed clips dropped before scoring still count when n_attempted is passed
    m2 = bp_metrics(y[:5], y[:5] + 1.0, n_attempted=8)
    assert m2["coverage_pct"] == pytest.approx(100.0 * 5 / 8)
    with pytest.raises(ValueError):
        bp_metrics(y, p, n_attempted=5)


def test_reference_tertiles_with_passed_cuts():
    t = error_by_reference_tertile(Y, P, cuts=(110.0, 125.0))
    assert t["n"].tolist() == [1, 2, 1]
    assert t["bias"].tolist() == pytest.approx([2.0, 1.5, -2.0])
    assert t["mae"].tolist() == pytest.approx([2.0, 3.5, 2.0])
    m = bp_metrics(Y, P, tertile_cuts=(110.0, 125.0))
    assert m["error_by_reference_tertile"]["n"].tolist() == [1, 2, 1]
    c1, c2 = reference_tertile_cuts(np.arange(1.0, 10.0))
    assert c1 == pytest.approx(np.percentile(np.arange(1.0, 10.0), 100 / 3))
    assert c2 == pytest.approx(np.percentile(np.arange(1.0, 10.0), 200 / 3))


def test_format_tables_are_labelled_and_graded():
    m = bp_metrics(Y, P)
    a = m["aami_format_table"]
    assert a.loc[0, "label"] == FORMAT_LABEL and "compliance" in FORMAT_LABEL
    assert a.loc[0, "mean_error"] == pytest.approx(0.75) and a.loc[0, "n"] == 4
    i = m["ieee1708_format_table"]
    assert i.loc[0, "label"] == FORMAT_LABEL
    assert i.loc[0, "mad"] == pytest.approx(2.75) and i.loc[0, "grade"] == "A"
    assert i.loc[0, "pct_within_5"] == 100.0
    i2 = bp_metrics(Y, Y + np.array([6.5, -6.5, 6.5, -6.5]))["ieee1708_format_table"]
    assert i2.loc[0, "grade"] == "C" and i2.loc[0, "pct_within_5"] == 0.0 and i2.loc[0, "pct_within_10"] == 100.0
    i3 = bp_metrics(Y, Y + 20.0)["ieee1708_format_table"]
    assert i3.loc[0, "grade"] == "D" and i3.loc[0, "pct_within_15"] == 0.0


def test_rhythm_metrics_exact_binomial_cis_and_auc():
    y = np.array([1, 1, 1, 1, 1, 0, 0, 0, 0, 0])
    s = np.array([0.9, 0.8, 0.7, 0.4, 0.2, 0.1, 0.3, 0.6, 0.45, 0.05])
    r = rhythm_metrics(y, s, operating_point=0.5)
    assert (r["tp"], r["fp"], r["fn"], r["tn"]) == (3, 1, 2, 4)
    assert r["sensitivity"] == pytest.approx(0.6) and r["specificity"] == pytest.approx(0.8)
    assert r["ppv"] == pytest.approx(0.75) and r["npv"] == pytest.approx(4 / 6)
    assert r["sensitivity_lo"] == pytest.approx(stats.beta.ppf(0.025, 3, 3))
    assert r["sensitivity_hi"] == pytest.approx(stats.beta.ppf(0.975, 4, 2))
    assert r["specificity_lo"] == pytest.approx(stats.beta.ppf(0.025, 4, 2))
    assert r["specificity_hi"] == pytest.approx(stats.beta.ppf(0.975, 5, 1))
    assert r["auc"] == pytest.approx(20 / 25)  # 20 of 25 positive-negative pairs ordered correctly
    assert 0 < r["auprc"] <= 1
    assert clopper_pearson(0, 10) == (0.0, pytest.approx(stats.beta.ppf(0.975, 1, 10)))
    assert clopper_pearson(10, 10) == (pytest.approx(stats.beta.ppf(0.025, 10, 1)), 1.0)
    # NaN scores count as negative predictions and are reported
    s2 = s.copy()
    s2[0] = np.nan
    r2 = rhythm_metrics(y, s2, 0.5)
    assert r2["n_failed"] == 1 and r2["tp"] == 2


def test_threshold_for_target_on_development_scores():
    y = np.array([1, 1, 1, 1, 0, 0, 0, 0])
    s = np.array([0.9, 0.8, 0.6, 0.3, 0.7, 0.2, 0.1, 0.05])
    t = threshold_for_target(y, s, sensitivity_target=0.75)
    assert t == pytest.approx(0.6)  # 3 of 4 positives at or above 0.6
    t2 = threshold_for_target(y, s, specificity_target=0.75)
    assert t2 == pytest.approx(0.3)  # negatives 0.2, 0.1, 0.05 fall below 0.3
    with pytest.raises(ValueError):
        threshold_for_target(y, s)


def test_pulse_rate_within_tolerance_counts_failed_clips():
    r = pulse_rate_metrics([70, 72, 80, np.nan, 90], [70, 76, 78, 80, 100], tol_bpm=3.0)
    assert r["within_tol_pct"] == pytest.approx(40.0)
    assert r["mae"] == pytest.approx(4.0) and r["bias"] == pytest.approx(-3.0)
    assert r["n"] == 4 and r["n_attempted"] == 5 and r["n_failed"] == 1 and r["tol_bpm"] == 3.0
