"""StrataEngine pools small cells, emits every stratum in cfg with the overall row first, derives the MST
groupings and BP tertiles, and refuses a table without both baselines."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from palmppg.core.config import rng
from palmppg.eval.metrics import bp_metrics
from palmppg.eval.strata import (
    StrataEngine,
    normalise_level_column,
    pooled_label,
    write_markdown,
    write_parquet,
)


def _frame(n=150, seed=5):
    g = rng(seed, "strata")
    bands = np.concatenate([np.repeat([4, 5, 6, 7, 8], 27), np.repeat(9, 8), np.repeat(10, 5), np.repeat(4, 2)])[:n]
    df = pd.DataFrame({
        "study_id": [f"SWHT-PP-003-{i + 1:04d}" for i in range(n)],
        "mst_band": bands,
        "sex": np.where(g.uniform(size=n) < 0.5, "F", "M"),
        "age_band": g.choice(["<40", "40-59", "60+"], n),
        "dept": g.choice(["Cardio OPD", "Medicine OPD", "Dialysis"], n, p=[0.45, 0.45, 0.10]),
        "acute_30m": [["caffeine", "meal"] if i % 2 else ["none"] for i in range(n)],
        "flag_hypertension": g.uniform(size=n) < 0.4,
        "bp_target_sbp": g.normal(130, 15, n),
    })
    df["pred"] = df["bp_target_sbp"] + g.normal(0, 8, n)
    df["pred_mean"] = df["bp_target_sbp"].mean()
    df["pred_demo"] = df["bp_target_sbp"] + g.normal(0, 12, n)
    return df


def _sd(d):
    return bp_metrics(d["bp_target_sbp"].to_numpy(), d["pred"].to_numpy())["error_sd"]


def test_overall_first_every_stratum_present_and_small_cells_pooled(cfg):
    eng = StrataEngine(cfg)
    df = _frame()
    t = eng.metric_table(df, _sd, bootstrap=False, tertile_cuts=(120.0, 140.0), metric_name="error_sd")
    assert (t.loc[0, "stratum"], t.loc[0, "level"]) == ("overall", "all")
    assert t.loc[0, "n"] == len(df) and t.loc[0, "n_participants"] == len(df)
    assert t.loc[0, "point"] == pytest.approx(_sd(df))
    assert set(t["stratum"]) == set(cfg.get("strata")) | {"overall"}
    assert list(t.columns) == ["metric", "stratum", "level", "n", "n_participants", "point", "lo", "hi", "pooled", "note"]
    band = t[t["stratum"] == "mst_band"]
    assert band[~band["pooled"]]["level"].tolist() == ["4", "5", "6", "7", "8"]
    pooled = band[band["pooled"]]
    assert len(pooled) == 1 and pooled["level"].iloc[0] == pooled_label(cfg.get("bootstrap.min_cell_n"))
    assert pooled["n"].iloc[0] == 13 and "9 (n=8)" in pooled["note"].iloc[0] and "10 (n=5)" in pooled["note"].iloc[0]
    assert pooled["point"].iloc[0] == pytest.approx(_sd(df[df["mst_band"] >= 9]))
    assert band["n"].sum() == len(df)
    grp = t[t["stratum"] == "mst_group"]
    assert set(grp["level"]) == {"4-5", "6-7", "8-10"} and not grp["pooled"].any()
    assert t[t["stratum"] == "equity_scope"]["level"].tolist() == ["in"]
    tert = t[t["stratum"] == "bp_tertile"]
    assert len(tert) == 3 and tert["level"].str.startswith("T").all()
    absent = t[t["note"] == "column absent from table"]
    assert "operator" in set(absent["stratum"]) and (absent["n"] == 0).all() and absent["level"].isna().all()
    acute = t[t["stratum"] == "acute_30m"]
    assert set(acute["level"]) == {"caffeine+meal", "none"}
    flag = t[t["stratum"] == "flag_hypertension"]
    assert set(flag["level"]) == {"True", "False"}
    dept = t[t["stratum"] == "dept"]
    assert dept[dept["pooled"]]["note"].str.contains("Dialysis").all()


def test_bootstrap_cis_bracket_the_point_and_are_deterministic(cfg):
    eng = StrataEngine(cfg)
    df = _frame()
    a = eng.metric_table(df, _sd, strata=["sex"], bootstrap=40, seed=3)
    b = eng.metric_table(df, _sd, strata=["sex"], bootstrap=40, seed=3)
    pd.testing.assert_frame_equal(a, b)
    assert (a["lo"] <= a["point"]).all() and (a["point"] <= a["hi"]).all()
    assert np.isfinite(a[["lo", "hi"]].to_numpy()).all()
    none = eng.metric_table(df, _sd, strata=["sex"], bootstrap=0)
    assert none["lo"].isna().all()


def test_both_baselines_are_mandatory(cfg):
    eng = StrataEngine(cfg)
    df = _frame()

    def sd(y, p):
        return bp_metrics(y, p)["error_sd"]

    t = eng.metric_table_with_baselines(df, sd, {"model": "pred", "predict_mean": "pred_mean", "demographics_only": "pred_demo"},
                                        strata=["sex", "mst_group"], bootstrap=False)
    assert t.columns[0] == "model" and set(t["model"]) == {"model", "predict_mean", "demographics_only"}
    for name in ("model", "predict_mean", "demographics_only"):
        sub = t[t["model"] == name].reset_index(drop=True)
        assert (sub.loc[0, "stratum"], sub.loc[0, "level"]) == ("overall", "all")
    pm = t[(t["model"] == "predict_mean") & (t["stratum"] == "overall")]["point"].iloc[0]
    assert pm == pytest.approx(df["bp_target_sbp"].std(ddof=1))
    with pytest.raises(ValueError):
        eng.metric_table_with_baselines(df, sd, {"model": "pred", "predict_mean": "pred_mean"}, strata=["sex"], bootstrap=False)
    with pytest.raises(ValueError):
        eng.metric_table_with_baselines(df, sd, {"predict_mean": "pred_mean", "demographics_only": "pred_demo"}, strata=[], bootstrap=False)
    df["abst"] = np.arange(len(df)) < 10
    t2 = eng.metric_table_with_baselines(df, lambda y, p: bp_metrics(y, p)["coverage_pct"],
                                         {"model": "pred", "predict_mean": "pred_mean", "demographics_only": "pred_demo"},
                                         abstain_cols={"model": "abst"}, strata=[], bootstrap=False)
    assert t2[t2["model"] == "model"]["point"].iloc[0] == pytest.approx(100.0 * (len(df) - 10) / len(df))
    assert t2[t2["model"] == "predict_mean"]["point"].iloc[0] == pytest.approx(100.0)


def test_writers_roundtrip(cfg, tmp_path):
    eng = StrataEngine(cfg)
    t = eng.metric_table(_frame(), _sd, strata=["sex", "operator"], bootstrap=False, metric_name="error_sd")
    md = write_markdown(t, tmp_path / "t.md", title="SBP error SD")
    text = md.read_text()
    assert "| overall | all |" in text and "### SBP error SD" in text and "pooled" in text
    pq = write_parquet(t, tmp_path / "t.parquet")
    back = pd.read_parquet(pq)
    assert len(back) == len(t) and back["point"].tolist() == pytest.approx(t["point"].tolist(), nan_ok=True)
    assert back["pooled"].dtype == bool


def test_normalise_level_column():
    s = pd.Series([1.0, 2.5, None, True, ["b", "a"], "x"], dtype=object)
    assert normalise_level_column(s).tolist() == ["1", "2.5", "missing", "True", "a+b", "x"]
