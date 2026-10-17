"""Fixed-sequence hierarchy from the frozen config; exploratory tables get n_tests_run."""
from __future__ import annotations

import pandas as pd
import pytest

from palmppg.eval.multiplicity import (
    annotate_exploratory,
    fixed_sequence,
    load_hierarchy,
    multiplicity_report,
)


def test_fixed_sequence_stops_at_first_non_rejection():
    t = fixed_sequence({"a": 0.01, "b": 0.2, "c": 0.001, "d": 0.3}, ["a", "b", "c", "d"], alpha=0.05)
    assert t["rejected"].tolist() == [True, False, False, False]
    assert t["tested"].tolist() == [True, True, False, False]
    assert t.loc[2, "note"] == "not tested (sequence stopped)"
    t2 = fixed_sequence({"a": 0.01, "b": 0.02, "c": 0.03}, ["a", "b", "c"], alpha=0.05)
    assert t2["rejected"].all()
    t3 = fixed_sequence({"a": 0.01}, ["a", "b", "c"], alpha=0.05)
    assert t3["rejected"].tolist() == [True, False, False] and "missing" in t3.loc[1, "note"]
    t4 = fixed_sequence({"a": 0.01, "zz": 0.001}, ["a"], alpha=0.05)
    assert t4.loc[1, "endpoint"] == "zz" and not t4.loc[1, "rejected"] and "exploratory" in t4.loc[1, "note"]
    with pytest.raises(ValueError):
        fixed_sequence({}, ["a"], alpha=1.5)


def test_hierarchy_from_frozen_and_exploratory_annotation():
    hier, alpha = load_hierarchy()
    assert hier == ["sbp_error_sd_reduction", "dbp_error_sd_reduction", "af_vs_sinus_auc", "af_vs_hard_non_af_auc"]
    assert alpha == 0.05
    rep = multiplicity_report({"sbp_error_sd_reduction": 0.01, "dbp_error_sd_reduction": 0.3},
                              {"glucose_boundary": 0.4, "anaemia": 0.02, "vascular_age": 0.5})
    h = rep["hierarchy"]
    assert h["rejected"].tolist() == [True, False, False, False]
    e = rep["exploratory"]
    assert (e["n_tests_run"] == 3).all() and "exploratory" in e["family"].iloc[0]
    e2 = annotate_exploratory(pd.DataFrame({"endpoint": ["x"], "p": [0.1]}), n_tests_run=12)
    assert e2["n_tests_run"].iloc[0] == 12
