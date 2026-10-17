"""Equity audit end to end on synthetic data with a planted MST effect and without; MST leakage probe."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from palmppg.audits.equity import (
    equity_arm_from_band,
    equity_audit,
    error_on_mst_regression,
    mst_leakage_probe,
)
from palmppg.core.config import rng


def _results(effect: bool, n_per_arm=400, seed=0):
    g = rng(seed, "equity")
    rows = []
    for arm, bands in (("4-6", [4, 5, 6]), ("7-10", [7, 8, 9, 10])):
        band = np.resize(np.array(bands), n_per_arm)
        sd = 12.0 if (effect and arm == "7-10") else 8.0
        covered = (np.arange(n_per_arm) % 25) != 0  # 96 percent
        if effect and arm == "7-10":
            covered = (np.arange(n_per_arm) % 5) != 0  # 80 percent
        e = g.normal(0, 1, n_per_arm)
        e[covered] = (e[covered] - e[covered].mean()) / e[covered].std(ddof=1) * sd  # exact SD on covered rows
        if effect:
            e = e + 1.5 * (band - 4)
        for i in range(n_per_arm):
            rows.append({"study_id": f"{arm}-{i:04d}", "mst_band": int(band[i]), "mst_equity_arm": arm,
                         "error": float(e[i]) if covered[i] else np.nan, "covered": bool(covered[i]),
                         "age": float(g.uniform(20, 80)), "sex": str(g.choice(["F", "M"])),
                         "bmi": float(g.uniform(18, 35)), "bp_target_sbp": float(g.normal(130, 15))})
    return pd.DataFrame(rows)


def test_no_planted_effect_passes_both_ni_tests():
    res = equity_audit(_results(effect=False), n_resamples=200, seed=1)
    assert res["settings"]["coverage_margin_points"] == 10.0 and res["settings"]["error_sd_ratio_margin"] == 1.15
    arms = res["arms"].set_index("arm")
    assert arms.loc["4-6", "coverage_pct"] == pytest.approx(96.0) and arms.loc["7-10", "coverage_pct"] == pytest.approx(96.0)
    assert arms.loc["4-6", "error_sd"] == pytest.approx(8.0) and arms.loc["7-10", "error_sd"] == pytest.approx(8.0)
    assert res["coverage_ni"]["noninferior"] is True and res["coverage_ni_wald"]["noninferior"] is True
    assert res["coverage_ni"]["estimate"] == pytest.approx(0.0)
    assert res["sd_ratio_ni_f"]["noninferior"] is True and res["sd_ratio_ni_f"]["estimate"] == pytest.approx(1.0)
    assert res["sd_ratio_ni_bootstrap"]["noninferior"] is True
    reg = res["regression"]
    assert reg["n_clusters"] == 768 and reg["band_p"] > 0.01 and abs(reg["band_coef"]) < 1.0
    assert "mst_band" in reg["formula"] and "C(sex)" in reg["formula"]
    assert "Equity audit" in res["markdown"] and "| 7-10 | comparison |" in res["markdown"]


def test_planted_effect_fails_both_ni_tests_and_shows_in_regression():
    df = _results(effect=True)
    res = equity_audit(df, n_resamples=200, seed=1)
    arms = res["arms"].set_index("arm")
    assert arms.loc["7-10", "coverage_pct"] == pytest.approx(80.0)
    assert res["coverage_ni"]["estimate"] == pytest.approx(-16.0)
    assert res["coverage_ni"]["noninferior"] is False and res["coverage_ni_wald"]["noninferior"] is False
    sd = df.groupby("mst_equity_arm")["error"].std(ddof=1)  # the band shift adds spread on top of the 1.5 ratio
    assert res["sd_ratio_ni_f"]["estimate"] == pytest.approx(sd["7-10"] / sd["4-6"]) and sd["7-10"] / sd["4-6"] > 1.45
    assert res["sd_ratio_ni_f"]["noninferior"] is False
    assert res["sd_ratio_ni_bootstrap"]["noninferior"] is False
    reg = res["regression"]
    assert reg["band_coef"] == pytest.approx(1.5, abs=0.35) and reg["band_p"] < 1e-6
    assert "| 7-10 | comparison |" in res["markdown"] and "| no |" in res["markdown"]


def test_arm_derivation_and_regression_helpers():
    assert equity_arm_from_band([3, 4, 6, 7, 10, 11, None]).tolist() == [None, "4-6", "4-6", "7-10", "7-10", None, None]
    df = _results(effect=False, n_per_arm=60)
    r = error_on_mst_regression(df.dropna(subset=["error"]), covariates=("age", "sex", "nonexistent"))
    assert "nonexistent" in r["note"] and len(r["table"]) == 4  # intercept, band, sex, age
    tiny = error_on_mst_regression(df.head(3))
    assert "too few" in tiny["note"]
    noarm = equity_audit(df.drop(columns=["mst_equity_arm", "covered"]), n_resamples=20, seed=0)
    assert noarm["arms"]["n_attempted"].tolist() == [60, 60]
    with pytest.raises(KeyError):
        equity_audit(df.drop(columns=["mst_equity_arm", "mst_band"]), n_resamples=5)


def _features(leak: bool, n_per_band=40, seed=0):
    g = rng(seed, "probe")
    bands = np.repeat(np.arange(4, 11), n_per_band)
    df = pd.DataFrame({"study_id": [f"P{i:04d}" for i in range(len(bands))], "mst_band": bands})
    for k in range(4):
        df[f"f{k}"] = g.normal(0, 1, len(bands))
    if leak:
        df["f0"] = bands + g.normal(0, 0.15, len(bands))
    return df


def test_mst_leakage_probe_chance_without_leak_and_high_with_leak():
    clean = mst_leakage_probe(_features(False), ["f0", "f1", "f2", "f3"], cv=5, seed=3)
    assert clean["band"]["chance"] == pytest.approx(1 / 7) and clean["band"]["n_classes"] == 7
    assert clean["band"]["balanced_accuracy"] < 1 / 7 + 0.1
    assert clean["arm"]["chance"] == pytest.approx(0.5) and abs(clean["arm"]["balanced_accuracy"] - 0.5) < 0.12
    leaky = mst_leakage_probe(_features(True), ["f0", "f1", "f2", "f3"], cv=5, seed=3)
    assert leaky["band"]["balanced_accuracy"] > 0.8 and leaky["band"]["macro_f1"] > 0.8
    assert leaky["arm"]["balanced_accuracy"] > 0.95
    assert leaky["table"]["target"].tolist() == ["mst_band", "mst_equity_arm"]
    with pytest.raises(KeyError):
        mst_leakage_probe(_features(False), ["nope"])
