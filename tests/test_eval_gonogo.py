"""Go/no-go: a passing result dict, a failing one, and refusal when the frozen config is tampered."""
from __future__ import annotations

import shutil

import pytest
import yaml

from palmppg.core.config import CONFIG_DIR, ConfigError, load_frozen_config
from palmppg.eval.gonogo import RESULT_KEYS, evaluate_go_no_go

PASSING = {"coverage_overall_pct": 93.0, "coverage_mst_4_6_pct": 94.0, "coverage_mst_7_10_pct": 90.0,
           "pulse_rate_within_tolerance_pct_pi": 97.0, "pulse_rate_within_tolerance_pct_phone": 91.0,
           "pulse_rate_tolerance_bpm": 3.0, "sbp_error_sd_demographics_only": 12.0, "sbp_error_sd_temporal": 9.5}


def test_passing_result_is_go(tmp_path):
    rep = evaluate_go_no_go(PASSING, markdown_path=tmp_path / "gonogo.md")
    assert rep.go is True and rep.n_failed == 0 and rep.n_criteria == 4
    t = rep.table.set_index("criterion")
    assert t.loc["coverage_overall_pct", "threshold"] == 90.0 and t.loc["coverage_overall_pct", "passed"] is True
    assert t.loc["coverage_drop_points_mst_4_6_minus_7_10", "measured"] == pytest.approx(4.0)
    assert t.loc["sbp_error_sd_reduction_temporal_vs_demographics_mmhg", "measured"] == pytest.approx(2.5)
    assert t.loc["pulse_rate_within_tolerance_pct_phone", "passed"] is None  # reported alongside only
    text = (tmp_path / "gonogo.md").read_text()
    assert "GO" in text and "NO-GO" not in text and rep.frozen_sha256 in text
    assert set(RESULT_KEYS) == set(PASSING)


def test_failing_results_are_no_go():
    bad = dict(PASSING, coverage_overall_pct=85.0)
    rep = evaluate_go_no_go(bad)
    assert rep.go is False and rep.n_failed == 1 and "NO-GO" in rep.markdown
    t = rep.table.set_index("criterion")
    assert t.loc["coverage_overall_pct", "passed"] is False
    drop = dict(PASSING, coverage_mst_7_10_pct=80.0)
    assert evaluate_go_no_go(drop).table.set_index("criterion").loc["coverage_drop_points_mst_4_6_minus_7_10", "passed"] is False
    weak = dict(PASSING, sbp_error_sd_temporal=11.0)
    assert evaluate_go_no_go(weak).go is False
    wrong_tol = dict(PASSING, pulse_rate_tolerance_bpm=5.0)
    r = evaluate_go_no_go(wrong_tol).table.set_index("criterion")
    assert r.loc["pulse_rate_within_tolerance_pct_pi", "passed"] is False and "frozen tolerance" in r.loc["pulse_rate_within_tolerance_pct_pi", "note"]
    missing = {k: v for k, v in PASSING.items() if k != "sbp_error_sd_temporal"}
    rm = evaluate_go_no_go(missing)
    assert rm.go is False and "missing" in rm.table.set_index("criterion").loc["sbp_error_sd_reduction_temporal_vs_demographics_mmhg", "note"]


def test_tampered_frozen_config_is_refused(tmp_path):
    src = CONFIG_DIR / "frozen_config.yaml"
    dst = tmp_path / "frozen_config.yaml"
    shutil.copy(src, dst)
    assert evaluate_go_no_go(PASSING, frozen_path=dst).go is True  # untouched copy verifies
    data = yaml.safe_load(dst.read_text())
    data["go_no_go"]["coverage_min_pct"] = 50.0
    dst.write_text(yaml.safe_dump(data, sort_keys=False))
    with pytest.raises(ConfigError):
        evaluate_go_no_go(dict(PASSING, coverage_overall_pct=60.0), frozen_path=dst)
    tampered_obj = load_frozen_config().with_overrides({"go_no_go": {"coverage_min_pct": 50.0}})
    with pytest.raises(ConfigError):
        evaluate_go_no_go(PASSING, frozen=tampered_obj)
    assert evaluate_go_no_go(PASSING, frozen=load_frozen_config()).go is True
