"""Shared CRF schema and engine (onboarding app <-> pipeline): lint, golden fixtures, flow selection by part, export
contract (no identity), v2 derivations against hand-computed answers."""
import copy
import datetime as dt
import json
from pathlib import Path

import pytest

from palmppg.core.crf import derive, validate_crf
from palmppg.core.crf_schema import (
    CONDITION_ORDER,
    CrfEngine,
    anaemia_grade,
    dm_label,
    eval_condition,
    haem_cell,
    hplc_reflex,
    lint_schema,
    load_schema,
    parse_ts,
    scan_strata,
    strata,
)

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = json.loads((ROOT / "configs" / "crf_fixtures" / "golden.json").read_text())
CASES = {c["name"]: c for c in GOLDEN["cases"]}
CTX = {"operator": "op1", "unit_id": "unit_01", "app_ver": "test"}


def test_schema_lints_clean_and_matches_golden_version():
    s = load_schema()
    assert s["schema_version"] == "2026-10-24.1"
    assert lint_schema(s) == []
    assert GOLDEN["schema_version"] == s["schema_version"], "regenerate fixtures: python tools/make_crf_fixtures.py"
    assert len(GOLDEN["cases"]) >= 24


@pytest.mark.parametrize("case", GOLDEN["cases"], ids=[c["name"] for c in GOLDEN["cases"]])
def test_engine_reproduces_golden_case(case):
    eng = CrfEngine(load_schema(), case["settings"])
    now = parse_ts(case["now"])
    ev = eng.evaluate(case["answers"], now)
    crf = eng.export(case["answers"], CTX, now=now)
    f = case["full"]
    assert ev.visible_screens == f["visible_screens"]
    assert ev.visible_questions == f["visible_questions"]
    assert sorted(i.key() for i in ev.errors) == f["errors"]
    assert sorted(i.key() for i in ev.warnings) == f["warnings"]
    assert (ev.stopped.q if ev.stopped else None) == f["stopped"]
    assert {k: v for k, v in ev.derived.items() if k != "rest_elapsed"} == f["derived"]
    assert crf == f["export"]
    assert eng.initial_answers() == f["initial"]


def test_flow_selection_by_part_and_clip_plan():
    s = load_schema()
    assert CrfEngine(s).flow_key() == "enrol"
    assert CrfEngine(s, {"clip_plan": "2x30"}).flow_key() == "enrol"
    assert CrfEngine(s, {"part": "scan"}).flow() == ["pid", "s_setup", "bp1", "bp2", "clip1", "clip1b", "bp3", "s_review"]
    assert CrfEngine(s, {"part": "scan", "clip_plan": "2x30"}).flow_key() == "scan_2x30"
    with pytest.raises(ValueError, match="scan_3x20"):
        CrfEngine(s, {"part": "scan", "clip_plan": "3x20"}).flow()
    with pytest.raises(ValueError, match="triage"):
        CrfEngine(s, {"part": "triage"}).flow()


def test_schema_has_no_identity_and_enrol_stays_short():
    s = load_schema()
    ids = {q["id"] for sc in s["screens"] for q in sc["questions"]}
    assert not ids & {"name", "phone", "hospital_reg_no", "ita_deg", "handedness", "cohort_tags", "spo2", "flags"}
    assert not any(q.get("store") == "identity" for sc in s["screens"] for q in sc["questions"])
    screens = {sc["id"]: sc for sc in s["screens"]}
    asked = [q for sid in s["flows"]["enrol"] for q in screens[sid]["questions"] if q["type"] not in ("computed", "info")]
    # every enrol question is in design table 2.2; the always-visible core a healthy participant answers is small
    always = [q["id"] for q in asked if "show_if" not in q and (q.get("required") or q.get("default"))]
    assert always == ["study_id", "consent", "stream", "dept", "age", "sex", "height_cm", "weight_kg", "mst_band",
                      "conditions", "transfusion_3m", "acute_30m"]
    assert [c["value"] for c in s["choices"]["sex"]] == ["F", "M", "Other"]
    assert [c["value"] for c in s["choices"]["conditions"]] == list(CONDITION_ORDER)
    assert "Cardio OPD" in [c["value"] for c in s["choices"]["dept"]]
    assert len(s["choices"]["kardia"]) == 11


def test_export_has_no_identity_and_feeds_the_pipeline():
    case = CASES["complete_male_1x60"]
    eng = CrfEngine(load_schema(), case["settings"])
    crf = eng.export(case["answers"], {**CTX, "name": None}, now=parse_ts(case["now"]))
    assert isinstance(crf, dict) and crf["part"] == "scan" and crf["clip_plan"] == "1x60"
    for k in ("name", "phone", "hospital_reg_no", "initials"):
        assert k not in crf
    assert validate_crf(crf) == []
    d = derive(crf, {"bracket_mmhg": 10, "bp1_outlier_mmhg": 15})
    assert d["bp_target_sbp"] == pytest.approx((138 + 132 + 130) / 3) and d["bracket_flag"] is False
    enrol = CASES["enrol_complete_male"]
    e = CrfEngine(load_schema(), enrol["settings"]).export(enrol["answers"], CTX, now=parse_ts(enrol["now"]))
    assert e["part"] == "enrol" and "clip_plan" not in e and validate_crf(e) == []


def test_answers_to_other_parts_never_leak():
    # an enrol engine given scan answers (shared phone, same answer map) exports none of them, and vice versa
    both = {**CASES["enrol_complete_male"]["answers"], **CASES["complete_male_1x60"]["answers"]}
    now = parse_ts(CASES["enrol_complete_male"]["now"])
    e = CrfEngine(load_schema()).export(both, now=now)
    s = CrfEngine(load_schema(), {"part": "scan"}).export(both, now=now)
    assert "bp1" not in e and "clip1" not in e and "sex" not in s and "conditions" not in s
    assert e["strata"][0] == "sex:M" and s["scan_strata"] == ["rhythm:nsr", "scan:done"]


def test_who_grades_hand_computed():
    assert [anaemia_grade(x, "F", "no", None) for x in (12.0, 11.99, 11.0, 10.99, 8.0, 7.99)] == \
        ["none", "mild", "mild", "moderate", "moderate", "severe"]
    assert [anaemia_grade(x, "M", None, None) for x in (13.0, 12.9, 11.0, 10.9, 8.0, 7.9)] == \
        ["none", "mild", "mild", "moderate", "moderate", "severe"]
    assert [anaemia_grade(x, "F", "yes", 2) for x in (10.5, 10.4, 9.5, 9.4, 7.0, 6.9)] == \
        ["none", "mild", "mild", "moderate", "moderate", "severe"]
    for tri in (1, 3, None):
        assert [anaemia_grade(x, "F", "yes", tri) for x in (11.0, 10.9, 10.0, 9.9, 7.0, 6.9)] == \
            ["none", "mild", "mild", "moderate", "moderate", "severe"]
    assert anaemia_grade(9.0, "Other", None, None) is None and anaemia_grade(None, "F", None, None) is None


def test_haem_cell_precedence_and_dm_label():
    base = {"conditions": ["thal", "ida", "anaemia_other"]}
    assert haem_cell({**base, "thal_type": "beta_trait", "hplc_result": "hbe_beta"}, True, 15) == "thal_disease"
    assert haem_cell({**base, "hplc_result": "hbe_trait"}, True, 15) == "thal_trait"
    assert haem_cell(base, True, 15) == "thal_unspecified"
    assert haem_cell({"conditions": ["anaemia_other"], "ferritin_ngml": 10}, True, 15) == "ida"
    assert haem_cell({"conditions": ["none"], "ferritin_ngml": 10}, None, 15) is None    # ferritin alone needs anaemia
    assert haem_cell({"conditions": ["anaemia_other"]}, False, 15) == "anaemia_other"
    assert haem_cell({"conditions": ["none"]}, False, 15) == "non_anaemic"
    assert [dm_label(c, h, 6.5) for c, h in ((["diabetes"], 6.5), (["diabetes"], None), (["none"], 6.5), (["none"], 6.49), (None, 9.0))] == \
        ["documented_hba1c", "documented", "hba1c_only", "no_known", None]
    assert (hplc_reflex(None, 26.9), hplc_reflex(80.0, None), hplc_reflex(79.9, 30.0), hplc_reflex(None, None)) == (True, False, True, None)


def test_strata_order_and_scan_strata():
    eff = {"sex": "M", "mst_band": 5, "conditions": ["ckd", "htn"], "pregnant": "yes"}
    assert strata(eff, "ida", "no_known") == ["sex:M", "mst:5", "mstgrp:medium", "cond:htn", "cond:ckd", "haem:ida", "dm:no_known",
                                               "preg:yes", "sex_mst:M:5", "cond_mstgrp:htn:medium", "cond_mstgrp:ckd:medium",
                                               "haem_mstgrp:ida:medium"]
    assert strata({"conditions": ["none"], "mst_band": 4}, None, "no_known") == ["mst:4", "mstgrp:light", "cond:none", "dm:no_known"]
    assert strata({}, None, None) is None
    c = {"quality": "fail", "kardia_determination": "unreadable"}
    assert scan_strata({"clip1": c, "clip1b": {"kardia_determination": " "}}) == ["rhythm:unreadable"]
    assert scan_strata({"clip1": c, "clip1b": {"kardia_determination": "af"}, "bp3": {"sbp": 1}}) == ["rhythm:af", "scan:done"]


def test_lint_catches_part_and_order_problems():
    s = copy.deepcopy(load_schema())
    s["choices"]["conditions"].reverse()
    s["flows"]["triage"] = s["flows"]["enrol"]
    s["flows"]["scan_1x60"].append("e_today")
    del s["flows"]["scan_2x30"]
    probs = lint_schema(s)
    assert any(p.startswith("choices conditions must be") for p in probs)
    assert "flow triage: not a part or part_clipplan key" in probs
    assert "screen e_today is used by both parts" in probs
    assert any("scan_2x30" in p for p in probs)
    s = copy.deepcopy(load_schema())
    s["screens"][0]["questions"].append({"id": "x", "type": "computed", "compute": "initials"})
    assert "x: unknown derivation initials" in lint_schema(s)


def test_transfusion_days_follow_the_clock():
    eng = CrfEngine(load_schema())
    a = dict(CASES["enrol_complete_male"]["answers"], transfusion_3m="yes", last_transfusion_date="2026-10-01")
    tz = dt.timezone(dt.timedelta(hours=5, minutes=30))
    assert eng.evaluate(a, dt.datetime(2026, 10, 31, 9, 0, tzinfo=tz)).derived["days_since_transfusion"] == 30
    d = eng.evaluate(a, dt.datetime(2026, 11, 1, 0, 30, tzinfo=tz)).derived
    assert d["days_since_transfusion"] == 31 and d["transfusion_30d"] is False


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
