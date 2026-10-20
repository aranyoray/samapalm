"""Shared CRF schema and engine (onboarding app <-> pipeline): lint, golden fixtures, export contract, identity split."""
import json
from pathlib import Path

import pytest

from palmppg.core.crf import derive, validate_crf
from palmppg.core.crf_schema import CrfEngine, eval_condition, lint_schema, load_schema, parse_ts

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = json.loads((ROOT / "configs" / "crf_fixtures" / "golden.json").read_text())


def test_schema_lints_clean_and_matches_golden_version():
    s = load_schema()
    assert lint_schema(s) == []
    assert GOLDEN["schema_version"] == s["schema_version"], "regenerate fixtures: python tools/make_crf_fixtures.py"


@pytest.mark.parametrize("case", GOLDEN["cases"], ids=[c["name"] for c in GOLDEN["cases"]])
def test_engine_reproduces_golden_case(case):
    eng = CrfEngine(load_schema(), case["settings"])
    now = parse_ts(case["now"])
    ev = eng.evaluate(case["answers"], now)
    crf, ident = eng.export(case["answers"], {"operator": "op1", "unit_id": "unit_01", "app_ver": "test"}, now=now)
    f = case["full"]
    assert ev.visible_screens == f["visible_screens"]
    assert ev.visible_questions == f["visible_questions"]
    assert sorted(i.key() for i in ev.errors) == f["errors"]
    assert sorted(i.key() for i in ev.warnings) == f["warnings"]
    assert (ev.stopped.q if ev.stopped else None) == f["stopped"]
    assert {k: v for k, v in ev.derived.items() if k != "rest_elapsed"} == f["derived"]
    assert crf == f["export"] and ident == f["identity"]


def test_export_never_carries_identity_and_feeds_the_pipeline():
    case = next(c for c in GOLDEN["cases"] if c["name"] == "complete_male_1x60")
    eng = CrfEngine(load_schema())
    crf, ident = eng.export(case["answers"], {"operator": "op1", "unit_id": "unit_01", "app_ver": "1.0"}, now=parse_ts(case["now"]))
    for k in ("name", "phone", "hospital_reg_no"):
        assert k not in crf and k in ident
    assert ident["pid"] == crf["study_id"]
    assert validate_crf(crf) == []
    d = derive(crf, {"bracket_mmhg": 10, "bp1_outlier_mmhg": 15})
    assert d["bp_target_sbp"] == pytest.approx((138 + 132 + 130) / 3) and d["bracket_flag"] is False


def test_pipeline_derives_add_on_fields():
    case = next(c for c in GOLDEN["cases"] if c["name"] == "pregnant_branch")
    crf = case["full"]["export"]
    d = derive(crf)
    assert d["trimester"] == 2 and d["cohort_antenatal_addon"] is True and d["hdp_present"] is False and d["pregnant"] is True


def test_condition_operators():
    a = {"x": 5, "flags": ["diabetes"], "c": {"quality": "fail"}, "s": "F"}
    assert eval_condition({"q": "x", "between": [5, 6]}, a, {})
    assert not eval_condition({"q": "missing", "gt": 1}, a, {})
    assert eval_condition({"q": "missing", "ne": "F"}, a, {})
    assert eval_condition({"q": "flags", "contains": "diabetes"}, a, {})
    assert eval_condition({"q": "c", "field": "quality", "eq": "fail"}, a, {})
    assert eval_condition({"setting": "clip_plan", "eq": "2x30"}, a, {"clip_plan": "2x30"})
    assert eval_condition({"not": {"any": [{"q": "s", "eq": "M"}, {"q": "x", "lt": 0}]}}, a, {})
    assert eval_condition({"derived": "bracket_flag", "eq": True}, a, {}, {"bracket_flag": True})
    assert not eval_condition({"derived": "bracket_flag", "eq": True}, a, {}, {"bracket_flag": None})
    with pytest.raises(ValueError):
        eval_condition({"q": "x", "approx": 5}, a, {})
