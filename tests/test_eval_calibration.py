"""Calibration and decision curves on synthetic probabilities with hand-computed expectations."""
from __future__ import annotations

import numpy as np
import pytest

from palmppg.core.config import rng
from palmppg.eval.calibration import (
    brier_score,
    decision_curve,
    expected_calibration_error,
    logistic_calibration,
    regression_calibration,
    reliability_table,
)


def test_reliability_table_and_ece_by_hand():
    p = np.array([0.05, 0.15, 0.15, 0.95, 0.85])
    y = np.array([0, 0, 1, 1, 1])
    t = reliability_table(y, p, bins=[0.0, 0.5, 1.0])
    assert t["n"].tolist() == [3, 2]
    assert t.loc[0, "mean_pred"] == pytest.approx(0.35 / 3) and t.loc[0, "frac_pos"] == pytest.approx(1 / 3)
    assert t.loc[1, "mean_pred"] == pytest.approx(0.9) and t.loc[1, "frac_pos"] == pytest.approx(1.0)
    ece = 0.6 * abs(1 / 3 - 0.35 / 3) + 0.4 * abs(1.0 - 0.9)
    assert expected_calibration_error(y, p, bins=[0.0, 0.5, 1.0]) == pytest.approx(ece)
    assert brier_score(y, p) == pytest.approx(np.mean((p - y) ** 2))
    with pytest.raises(ValueError):
        reliability_table(y, p, bins=[0.5, 0.2])


def test_calibrated_probabilities_have_lower_ece_than_distorted_ones():
    g = rng(11, "calib")
    p = g.uniform(0.02, 0.98, 20000)
    y = (g.uniform(size=p.size) < p).astype(int)
    good = expected_calibration_error(y, p, bins=10)
    bad = expected_calibration_error(y, p**3, bins=10)
    assert good < 0.02 and bad > 0.1
    lc = logistic_calibration(y, p)
    assert lc["slope"] == pytest.approx(1.0, abs=0.08) and lc["intercept"] == pytest.approx(0.0, abs=0.08)
    quant = reliability_table(y, p, bins=5, strategy="quantile")
    assert quant["n"].min() > 3500


def test_decision_curve_by_hand():
    y = np.array([1, 1, 0, 0])
    p = np.array([0.9, 0.4, 0.6, 0.1])
    dc = decision_curve(y, p, thresholds=[0.2, 0.5, 1.0])
    r = dc.set_index("threshold")
    assert r.loc[0.2, "net_benefit_model"] == pytest.approx(0.5 - 0.25 * 0.25)
    assert r.loc[0.2, "net_benefit_all"] == pytest.approx(0.5 - 0.5 * 0.25)
    assert r.loc[0.5, "net_benefit_model"] == pytest.approx(0.0)
    assert r.loc[0.5, "net_benefit_all"] == pytest.approx(0.0)
    assert (r["net_benefit_none"] == 0.0).all()
    assert np.isnan(r.loc[1.0, "net_benefit_model"])


def test_regression_calibration_recovers_slope_and_intercept():
    pred = np.linspace(90, 160, 50)
    y = 2.0 * pred + 1.0
    r = regression_calibration(y, pred)
    assert r["slope"] == pytest.approx(2.0) and r["intercept"] == pytest.approx(1.0) and r["r2"] == pytest.approx(1.0)
    assert r["in_the_large"] == pytest.approx(np.mean(y) - np.mean(pred))
    flat = regression_calibration(y, np.full(50, 120.0))
    assert np.isnan(flat["slope"]) and flat["n"] == 50
