"""Participant bootstrap: CI contains the truth on synthetic clustered data, is deterministic under the seed,
is wider than a row-level resample when rows cluster within participants, and reads its defaults from cfg."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from palmppg.core.config import rng
from palmppg.eval.bootstrap import participant_bootstrap, participant_bootstrap_difference, participant_groups


def _clustered(n_part=60, per=4, seed=3):
    g = rng(seed, "clustered")
    u = g.normal(0.0, 1.0, n_part)
    rows = []
    for i in range(n_part):
        for _ in range(per):
            rows.append({"study_id": f"SWHT-PP-003-{i + 1:04d}", "value": u[i] + g.normal(0.0, 0.5)})
    return pd.DataFrame(rows)


def test_ci_contains_truth_and_point_is_sample_metric():
    df = _clustered()
    r = participant_bootstrap(df, lambda d: d["value"].mean(), n=300, seed=1)
    assert r.point == pytest.approx(df["value"].mean())
    assert r.lo <= 0.0 <= r.hi
    assert r.n_participants == 60 and r.n_rows == 240 and r.n_resamples == 300 and r.ci == 0.95
    assert r.lo < r.point < r.hi


def test_deterministic_under_seed_and_salt():
    df = _clustered()
    a = participant_bootstrap(df, lambda d: d["value"].mean(), n=100, seed=7)
    b = participant_bootstrap(df, lambda d: d["value"].mean(), n=100, seed=7)
    c = participant_bootstrap(df, lambda d: d["value"].mean(), n=100, seed=8)
    d = participant_bootstrap(df, lambda d: d["value"].mean(), n=100, seed=7, salt="other")
    assert a == b
    assert (a.lo, a.hi) != (c.lo, c.hi) and (a.lo, a.hi) != (d.lo, d.hi)


def test_cluster_resample_is_wider_than_row_resample():
    df = _clustered()
    df["row_id"] = np.arange(len(df))
    clustered = participant_bootstrap(df, lambda d: d["value"].mean(), n=300, seed=2)
    rowwise = participant_bootstrap(df, lambda d: d["value"].mean(), id_col="row_id", n=300, seed=2)
    assert (clustered.hi - clustered.lo) > 1.3 * (rowwise.hi - rowwise.lo)


def test_defaults_from_cfg_and_edge_cases(cfg):
    df = _clustered(n_part=5, per=2)
    small = cfg.with_overrides({"bootstrap": {"n_resamples": 25}})
    r = participant_bootstrap(df, lambda d: d["value"].mean(), cfg=small)
    assert r.n_resamples == 25
    one = df[df["study_id"] == df["study_id"].iloc[0]]
    r1 = participant_bootstrap(one, lambda d: d["value"].mean(), n=10, seed=0)
    assert np.isnan(r1.lo) and np.isnan(r1.hi) and r1.n_participants == 1
    uniq, groups = participant_groups(["b", "a", "b", "c"])
    assert uniq.tolist() == ["a", "b", "c"] and [g.tolist() for g in groups] == [[1], [0, 2], [3]]
    with pytest.raises(KeyError):
        participant_bootstrap(df.drop(columns="study_id"), lambda d: 0.0, n=5, seed=0)


def test_paired_difference_resamples_both_arms_together():
    df = _clustered()
    df["other"] = df["value"] + 2.0
    r = participant_bootstrap_difference(df, lambda d: d["other"].mean(), lambda d: d["value"].mean(), n=50, seed=4)
    assert r.point == pytest.approx(2.0) and r.lo == pytest.approx(2.0) and r.hi == pytest.approx(2.0)
