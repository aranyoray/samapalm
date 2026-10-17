"""Partition balance: a random split is balanced, a planted imbalance is detected, numeric and categorical
strata are handled, and participants (not clips) are the unit."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from palmppg.audits.partition import partition_balance, partition_level_table, smd_numeric, smd_proportion
from palmppg.core.config import rng


def _frame(n=300, seed=0):
    g = rng(seed, "partition")
    df = pd.DataFrame({"study_id": [f"P{i:04d}" for i in range(n)], "fold": np.arange(n) % 5,
                       "sex": g.choice(["F", "M"], n), "age": g.uniform(20, 80, n),
                       "dept": g.choice(["Cardio OPD", "Medicine OPD", "Dialysis"], n),
                       "flag_diabetes": g.uniform(size=n) < 0.3})
    return df


def test_random_split_is_balanced_and_planted_imbalance_is_detected():
    df = _frame()
    t = partition_balance(df, "fold", ["sex", "age", "dept", "flag_diabetes", "operator"]).set_index("stratum")
    assert t.loc["sex", "kind"] == "categorical" and t.loc["age", "kind"] == "numeric"
    assert t.loc["operator", "kind"] == "absent" and t.loc["operator", "note"] == "column absent from table"
    for s in ("sex", "age", "dept", "flag_diabetes"):
        assert t.loc[s, "max_abs_smd"] < 0.35 and t.loc[s, "p"] > 0.01
    assert t.loc["sex", "dof"] == 4 and t.loc["age", "dof"] == 4 and (t["n_splits"] == 5).all()
    bad = df.copy()
    bad.loc[bad["fold"] == 0, "sex"] = "F"
    bad.loc[bad["fold"] == 1, "age"] = 95.0
    tb = partition_balance(bad, "fold", ["sex", "age"]).set_index("stratum")
    assert tb.loc["sex", "p"] < 1e-6 and tb.loc["sex", "max_abs_smd"] > 1.0 and tb.loc["sex", "cramers_v"] > 0.25
    assert tb.loc["age", "p"] < 1e-6 and tb.loc["age", "max_abs_smd"] > 1.5


def test_participants_are_the_unit_and_level_table():
    df = _frame(n=100)
    clips = pd.concat([df, df.assign(clip="clip1b")], ignore_index=True)
    t = partition_balance(clips, "fold", ["sex"]).set_index("stratum")
    assert t.loc["sex", "n"] == 100 and "one row per participant" in t.loc["sex", "note"]
    t2 = partition_balance(clips, "fold", ["sex"], per_participant=False).set_index("stratum")
    assert t2.loc["sex", "n"] == 200
    lt = partition_level_table(df, "fold", ["sex", "age"])
    assert set(lt["stratum"]) == {"sex"} and lt.groupby("split")["n"].sum().tolist() == [20] * 5
    assert lt.groupby("split")["pct"].sum().round(6).tolist() == [100.0] * 5
    with pytest.raises(KeyError):
        partition_balance(df, "nope", ["sex"])


def test_smd_formulas():
    assert smd_numeric([1, 2, 3], [1, 2, 3]) == 0.0
    assert smd_numeric([0, 0, 2, 2], [1, 1, 3, 3]) == pytest.approx(-1 / np.sqrt((4 / 3 + 4 / 3) / 2))
    assert smd_proportion(0.5, 0.5) == 0.0
    assert smd_proportion(0.8, 0.2) == pytest.approx(0.6 / np.sqrt(0.16))
    assert np.isnan(smd_numeric([1], [1, 2]))
