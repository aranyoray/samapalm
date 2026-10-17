"""Baselines: predict-the-mean, demographics-only ridge fitted in-fold, and the pulse-shuffled control that
moves pulse features across participants within a fold and never leaves a participant with their own."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from palmppg.core.config import rng
from palmppg.eval.baselines import (
    DemographicsRidge,
    demographics_columns,
    demographics_only,
    predict_mean_predictions,
    pulse_shuffled_control,
)


def test_predict_mean():
    assert predict_mean_predictions([1.0, 2.0, 3.0, np.nan], 3).tolist() == [2.0, 2.0, 2.0]
    with pytest.raises(ValueError):
        predict_mean_predictions([np.nan], 2)


def _demo(n, seed):
    g = rng(seed, "demo")
    df = pd.DataFrame({"age": g.uniform(20, 80, n), "sex": g.choice(["F", "M"], n), "bmi": g.uniform(18, 35, n),
                       "mst_band": g.integers(4, 11, n)})
    y = 100 + 0.5 * df["age"] + 6.0 * (df["sex"] == "M") + 0.8 * df["bmi"] + g.normal(0, 0.5, n)
    return df, y.to_numpy()


def test_demographics_ridge_recovers_a_linear_target_in_fold():
    train, ytr = _demo(400, 1)
    test, yte = _demo(100, 2)
    model = DemographicsRidge(["age", "sex", "bmi"], alpha=1e-3).fit(train, ytr)
    pred = model.predict(test)
    assert np.sqrt(np.mean((pred - yte) ** 2)) < 1.0
    fp = demographics_only(["age", "sex", "bmi"], alpha=1e-3)
    assert fp(train, ytr, test).tolist() == pytest.approx(pred.tolist())
    test2 = test.copy()
    test2.loc[test2.index[:5], "age"] = np.nan  # imputed with the training median, never fails
    assert np.isfinite(fp(train, ytr, test2)).all()
    assert "age" in demographics_columns()
    assert demographics_columns("/nonexistent.yaml") == ["age", "sex", "bmi"]
    with pytest.raises(RuntimeError):
        DemographicsRidge().predict(test)


def test_demographics_columns_read_from_experiment_yaml(tmp_path):
    good = tmp_path / "experiments.yaml"
    good.write_text("defaults:\n  demographics_columns: [age, sex, bmi, mst_band]\n")
    assert demographics_columns(good) == ["age", "sex", "bmi", "mst_band"]
    broken = tmp_path / "broken.yaml"
    broken.write_text("defaults: [unterminated: : :\n")
    assert demographics_columns(broken) == ["age", "sex", "bmi"]
    (tmp_path / "nokey.yaml").write_text("defaults: {}\n")
    assert demographics_columns(tmp_path / "nokey.yaml") == ["age", "sex", "bmi"]


def test_pulse_shuffled_control_is_a_within_fold_derangement():
    ids = [f"P{i:02d}" for i in range(12)]
    rows = []
    for i, sid in enumerate(ids):
        for k in range(1 + (i % 2)):
            rows.append({"study_id": sid, "fold": i % 2, "clip": k, "p1": float(i), "p2": float(10 * i), "static": float(i) ** 2})
    df = pd.DataFrame(rows)
    out, mapping = pulse_shuffled_control(df, ["p1", "p2"], fold_col="fold", seed=3)
    assert (out["p1"] != df["p1"]).all()  # nobody keeps their own pulse features
    assert out["static"].tolist() == df["static"].tolist() and out["study_id"].tolist() == df["study_id"].tolist()
    assert (out["p2"] == 10 * out["p1"]).all()  # feature rows move together
    for f in (0, 1):
        m = mapping[mapping["fold"] == f]
        assert sorted(m["donor"]) == sorted(m["study_id"])
        assert set(df.loc[df["fold"] == f, "study_id"]) == set(m["study_id"])
        assert set(out.loc[out["fold"] == f, "p1"]) == set(df.loc[df["fold"] == f, "p1"])
    again, _ = pulse_shuffled_control(df, ["p1", "p2"], fold_col="fold", seed=3)
    pd.testing.assert_frame_equal(out, again)
    other, _ = pulse_shuffled_control(df, ["p1", "p2"], fold_col="fold", seed=4)
    assert not out["p1"].equals(other["p1"])
    with pytest.raises(KeyError):
        pulse_shuffled_control(df, ["nope"], fold_col="fold")
