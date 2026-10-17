"""Shortcut audit finds a planted operator shortcut, reports chance when there is none, and measures the
association of residuals with each nuisance."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from palmppg.audits._cv import chance_macro_f1, grouped_folds
from palmppg.audits.shortcut import residual_association, shortcut_audit


def _frame(n=200, seed=0):
    from palmppg.core.config import rng

    g = rng(seed, "shortcut")
    df = pd.DataFrame({"study_id": [f"SWHT-PP-003-{i + 1:04d}" for i in range(n)],
                       "operator": g.choice(["opA", "opB", "opC", "opD"], n),
                       "unit_id": g.choice(["unit_01", "unit_02"], n),
                       "camera": "pi",
                       "dept": g.choice(["Cardio OPD", "Medicine OPD", "Other"], n, p=[0.49, 0.49, 0.02])})
    for k in range(5):
        df[f"f{k}"] = g.normal(0, 1, n)
    df["f0"] += 5.0 * df["operator"].map({"opA": 0, "opB": 1, "opC": 2, "opD": 3})  # planted shortcut
    df["residual"] = g.normal(0, 1, n) + 2.0 * (df["operator"] == "opA")
    return df


def test_planted_operator_shortcut_is_found_and_unit_is_at_chance():
    df = _frame()
    feats = [f"f{k}" for k in range(5)]
    res = shortcut_audit(df, feats, nuisance_cols=["operator", "unit_id", "camera", "dept", "time_of_day"], cv=5, seed=1,
                         residual_col="residual")
    t = res.table.set_index("nuisance")
    assert t.loc["operator", "balanced_accuracy"] > 0.9 and t.loc["operator", "chance"] == pytest.approx(0.25)
    assert t.loc["operator", "excess"] == pytest.approx(t.loc["operator", "balanced_accuracy"] - 0.25)
    assert t.loc["unit_id", "chance"] == pytest.approx(0.5)
    assert abs(t.loc["unit_id", "balanced_accuracy"] - 0.5) < 0.12
    assert np.isnan(t.loc["camera", "balanced_accuracy"]) and "not testable" in t.loc["camera", "note"]
    assert t.loc["time_of_day", "note"] == "column absent from table" and t.loc["time_of_day", "n"] == 0
    assert "Other" in t.loc["dept", "note"] and t.loc["dept", "n_levels"] == 2
    assert t.loc["operator", "residual_anova_p"] < 1e-4 and t.loc["operator", "residual_kruskal_p"] < 1e-4
    assert t.loc["unit_id", "residual_anova_p"] > 0.01
    assert 0 < t.loc["operator", "residual_eta_sq"] < 1
    assert "| operator |" in res.markdown and "Shortcut audit" in res.markdown
    with pytest.raises(KeyError):
        shortcut_audit(df, ["missing_feature"])


def test_no_shortcut_reports_chance_and_permutation_p_is_large():
    df = _frame(seed=5)
    df["f0"] = df["f0"] - 5.0 * df["operator"].map({"opA": 0, "opB": 1, "opC": 2, "opD": 3})  # remove the plant
    res = shortcut_audit(df, [f"f{k}" for k in range(5)], nuisance_cols=["operator"], cv=5, seed=2, n_permutations=3)
    r = res.table.iloc[0]
    assert abs(r["balanced_accuracy"] - 0.25) < 0.1
    assert r["perm_p"] >= 0.25
    assert "perm_p" in res.markdown


def test_residual_association_by_hand_and_grouped_folds():
    r = residual_association([1, 2, 3, 11, 12, 13], ["a", "a", "a", "b", "b", "b"])
    # between SS = 2 * 3 * 5^2 = 150, total SS = 150 + 4 = 154
    assert r["eta_sq"] == pytest.approx(150 / 154)
    assert r["anova_p"] < 1e-3 and r["kruskal_p"] < 0.1
    nan = residual_association([1, 2, 3], ["a", "a", "a"])
    assert np.isnan(nan["anova_f"])
    groups = np.repeat([f"p{i}" for i in range(10)], 2)
    folds = grouped_folds(groups, 5, seed=0)
    assert len(folds) == 5
    for tr, te in folds:
        assert not set(groups[tr]) & set(groups[te]) and len(te) == 4
    assert sorted(np.concatenate([te for _, te in folds]).tolist()) == list(range(20))
    assert chance_macro_f1(["a", "a", "b", "b"]) == pytest.approx(0.5)
    with pytest.raises(ValueError):
        grouped_folds(["only"], 5, seed=0)
