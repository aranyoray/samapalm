"""Experiment runner on a hand-built feature frame: both baselines present, failures count, tracks enforced."""
import numpy as np
import pandas as pd
import pytest

from palmppg.core.tracks import REGISTRY, TrackViolation


def _frames(n=40, seed=0):
    r = np.random.default_rng(seed)
    age = r.uniform(25, 75, n)
    hr = r.uniform(55, 100, n)
    sbp = 100 + 0.5 * age + r.normal(0, 8, n)
    rows = []
    for cam in ("pi", "phone"):
        df = pd.DataFrame({"study_id": [f"SWHT-PP-003-{i:04d}" for i in range(1, n + 1)], "clip_id": "clip1", "camera": cam, "stream": "pilot",
                           "age": age, "sex": np.where(r.random(n) < 0.5, "F", "M"), "bmi": r.uniform(18, 32, n), "mst_band": r.integers(4, 11, n),
                           "bp_target_sbp": sbp, "bp_target_dbp": 0.6 * sbp + r.normal(0, 5, n), "ecg__hr_median_bpm": hr,
                           f"hrv__{cam}__median_ibi_ms": 60000 / (hr + r.normal(0, 1, n)), f"hrv__{cam}__sdnn_ms": r.uniform(20, 60, n),
                           f"morphology__{cam}__upstroke_time_s": 0.1 + 0.001 * sbp + r.normal(0, 0.005, n),
                           f"static_colour__{cam}__thenar__rg": r.uniform(1.1, 1.4, n),
                           f"qc__{cam}__valid_clip": np.r_[np.zeros(4, bool), np.ones(n - 4, bool)], "clinician__rhythm": "sinus"})
        df["sex_f"] = (df["sex"] == "F").astype(float)
        rows.append((cam, df))
    return dict(rows)


@pytest.fixture
def ctx(tmp_path, cfg):
    from palmppg.experiments.data import restore_registry
    from palmppg.experiments.runner import Context

    frames = _frames()
    for cam, df in frames.items():
        restore_registry(df.columns, cam)
    return Context(cfg, tmp_path, frames=frames, synthetic=True)


def test_e5_has_both_baselines_and_counts_failures(ctx):
    from palmppg.experiments.runner import e5_static_vs_temporal

    res = e5_static_vs_temporal(ctx)
    models = {r["model"] for r in res["rows"]}
    assert {"predict_mean", "demographics_only", "static_only", "temporal_only", "static_plus_temporal", "pulse_shuffled_control"} <= models
    t = next(r for r in res["rows"] if r["model"] == "temporal_only" and r["camera"] == "phone" and r["target"] == "bp_target_sbp")
    assert t["metrics"]["n_attempted"] == 40 and t["metrics"]["n"] <= 36          # the four failed clips never count as covered
    assert (ctx.out / "E5" / "results.md").exists()


def test_e1_uses_median_rates_and_valid_subset(ctx):
    from palmppg.experiments.runner import e1_pulse_rate

    res = e1_pulse_rate(ctx)
    row = next(r for r in res["rows"] if r["camera"] == "pi" and r["subset"] == "valid clips")
    assert row["n"] == 36 and row["within_tol_pct"] > 90


def test_track_guard_blocks_ecg_columns_in_product_track(ctx):
    from palmppg.experiments import cv as cvm

    df = ctx.frame("phone")
    REGISTRY.add("ecg__hr_median_bpm", "ecg", requires_ecg=True)
    X = df[["ecg__hr_median_bpm", "age"]]
    with pytest.raises(TrackViolation):
        cvm.cv_predict(df, X, df["bp_target_sbp"].to_numpy(), np.ones(len(df), bool), cvm.ridge_model, "product_candidate", 5, 0)


def test_gonogo_reads_results_and_never_changes_thresholds(ctx, tmp_path):
    from palmppg.core.config import verify_frozen
    from palmppg.experiments.gonogo import run_gonogo
    from palmppg.experiments.runner import e1_pulse_rate, e5_static_vs_temporal

    e1_pulse_rate(ctx)
    e5_static_vs_temporal(ctx)
    before = verify_frozen()["signature"]["sha256"]
    g = run_gonogo(ctx.cfg, interim=True, work_root=tmp_path, synthetic=True)
    assert verify_frozen()["signature"]["sha256"] == before
    assert "coverage_overall_pct" in g["markdown"] and isinstance(g["go"], bool)
