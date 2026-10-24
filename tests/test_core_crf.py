import copy
import json
from pathlib import Path

import pytest

from palmppg.core.crf import covariate_columns, derive, validate_crf

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = {c["name"]: c for c in json.loads((ROOT / "configs" / "crf_fixtures" / "golden.json").read_text())["cases"]}
CONTEXT = ("part", "operator", "unit_id", "app_ver", "device_code", "capture_mode", "schema_version", "clip_plan")


def merged(enrol_case: str, scan_case: str | None, **over) -> dict:
    """A per-PID crf.json as `palmppg crf pull` writes it (design section 7): both parts' fields at top level, each
    part's context under `parts`."""
    out, parts = {}, {}
    for name, op in ((enrol_case, "op_enrol"), (scan_case, "op_scan")):
        if name is None:
            continue
        ex = dict(GOLDEN[name]["full"]["export"], operator=op)
        parts[ex["part"]] = {k: ex[k] for k in CONTEXT if k in ex}
        out.update({k: v for k, v in ex.items() if k not in CONTEXT})
    out["parts"] = parts
    out.update(over)
    return out


def base_crf(**over):
    crf = {
        "study_id": "SWHT-PP-003-0001", "initials": "AB", "age": 52, "sex": "F", "pregnant": False, "height_cm": 158,
        "weight_kg": 62, "handedness": "right", "cuff_size": "adult", "mst_band": 7, "dept": "Medicine OPD",
        "flags": ["hypertension"], "antihtn_today": "yes >2 h", "acute_30m": ["none"], "hba1c": 5.6,
        "bp1": {"sbp": 150, "dbp": 92, "hr": 76, "wall_ts": "2026-10-17T09:00:00+05:30"},
        "bp2": {"sbp": 134, "dbp": 86, "hr": 74, "wall_ts": "2026-10-17T09:06:00+05:30"},
        "bp3": {"sbp": 132, "dbp": 84, "hr": 73, "wall_ts": "2026-10-17T09:09:00+05:30"},
        "spo2": 97, "irregular_pulse": False, "recovery": "pass", "imaged_hand": "left", "operator": "op1",
        "unit_id": "unit_01", "stream": "pilot", "app_ver": "1.0",
    }
    crf.update(over)
    return crf


def test_valid_and_derived():
    crf = base_crf()
    assert validate_crf(crf) == []
    d = derive(crf, {"bracket_mmhg": 10, "bp1_outlier_mmhg": 15})
    assert d["bp_target_rule_sbp"] == "mean_bp2_bp3_bp1_outlier"  # 150 vs mean(134,132)=133 -> 17 > 15
    assert d["bp_target_sbp"] == 133
    assert d["bp_target_rule_dbp"] == "mean_bp1_bp2_bp3"           # 92 vs 85 -> 7 <= 15
    assert d["bp_target_dbp"] == (92 + 86 + 84) / 3
    assert d["bp_target_23_sbp"] == 133
    assert d["bracket_flag"] is True
    assert d["bp_category"] == "stage 1"
    assert d["age_band"] == "40-59"
    assert d["bmi_class"] == "overweight"  # 24.8 under Asia-Pacific
    assert d["equity_scope"] == "in" and d["mst_group"] == "6-7" and d["mst_equity_arm"] == "7-10"
    assert d["dm_label"] == "no_known"  # v2 labels for v1 records too: no diabetes flag, HbA1c 5.6 < 6.5
    assert d["flag_hypertension"] and not d["flag_diabetes"]
    assert d["conditions"] == ["htn"] and d["cond_htn"] and not d["cond_diabetes"]
    assert d["pregnant"] is False and d["anaemia_grade"] is None and d["haem_cell"] is None


def test_out_of_scope_and_problems():
    crf = base_crf(mst_band=2, dept="Unknown", stream="x")
    problems = validate_crf(crf)
    assert any("dept" in p for p in problems) and any("stream" in p for p in problems)
    d = derive(crf)
    assert d["equity_scope"] == "out" and d["mst_group"] == "1-3" and d["mst_equity_arm"] is None


def test_v1_haematology_maps_onto_v2_cells():
    crf = base_crf(flags=["anaemia/thalassaemia", "arrhythmia"], haem_type="beta thal trait", arr_type="af", hb_gdl=10.5)
    d = derive(crf)
    assert d["conditions"] == ["af", "thal"]
    assert d["anaemia_grade"] == "moderate" and d["anaemic"] is True     # female, 8.0 <= 10.5 < 11.0
    assert d["haem_cell"] == "thal_trait"                                 # haem_type beta thal trait -> thal_type beta_trait
    d = derive(base_crf(flags=["diabetes"], hba1c=7.1))
    assert d["dm_label"] == "documented_hba1c" and d["cond_diabetes"] and d["flag_diabetes"]


def test_merged_v2_record_validates_and_derives():
    crf = merged("strata_order_and_cross_keys", "scan_2x30_reshoot_uses_clip1b_rhythm")
    assert "operator" not in crf and crf["parts"]["scan"]["clip_plan"] == "2x30"
    assert validate_crf(crf) == []
    d = derive(crf, {"bracket_mmhg": 10, "bp1_outlier_mmhg": 15})
    assert crf["conditions"] == ["diabetes", "af", "htn"] and d["conditions"] == ["htn", "af", "diabetes"]  # list order
    assert d["cond_htn"] and d["cond_af"] and d["cond_diabetes"] and not d["cond_thal"]
    assert d["flags"] == ["hypertension", "diabetes", "arrhythmia"] and d["flag_arrhythmia"]
    assert d["pregnant"] is True and d["trimester"] == 2
    assert d["anaemia_grade"] == "moderate" and d["haem_cell"] == "anaemia_other" and d["dm_label"] == "documented"
    assert d["mstgrp"] == "dark" and d["equity_scope"] == "in" and d["kardia_determination"] == "af"
    assert d["operator"] == "op_scan" and d["unit_id"] == "unit_01"   # the capture's operator, from the scan part
    assert d["bp_target_sbp"] == pytest.approx((138 + 132 + 130) / 3) and d["bracket_flag"] is False
    assert d["htn_meds_today"] is True and d["cardiac_device"] is False and d["on_insulin"] is False
    for c in covariate_columns():
        assert c in d or c in ("hdp_status", "urine_protein", "arr_type", "haem_type", "antihtn_today", "handedness",
                               "arr_status", "transfusion_30d", "dm_type", "on_dialysis", "thal_type", "thal_transfusions",
                               "iron_therapy", "arrhythmia_type", "af_pattern", "anticoagulant", "hplc_result",
                               "spo2", "glucose_mgdl", "irregular_pulse"), c


def test_merged_v2_mentzer_hplc_and_transfusion():
    crf = merged("haem_hplc_trait_beats_ida", "complete_male_1x60", transfusion_3m="yes", last_transfusion_date="2026-09-24")
    d = derive(crf)
    assert d["haem_cell"] == "thal_trait" and d["cond_ida"] and d["mentzer_index"] == 11.8
    assert d["mentzer_pattern"] == "thal_trait_pattern" and d["hplc_reflex"] is True and d["mcv_fl"] == 66.0
    assert d["days_since_transfusion"] == 30 and d["transfusion_30d"] is True   # BP1 on 2026-10-24
    # without the exported values the same cells are recomputed from the raw fields
    raw = {k: v for k, v in crf.items() if k not in ("haem_cell", "mentzer", "hplc_reflex", "anaemia_grade", "dm_label")}
    r = derive(raw)
    assert (r["haem_cell"], r["mentzer_index"], r["hplc_reflex"], r["dm_label"]) == ("thal_trait", 11.8, True, "no_known")


def test_v2_parts_validated_separately():
    scan = GOLDEN["complete_male_1x60"]["full"]["export"]
    enrol = GOLDEN["enrol_complete_male"]["full"]["export"]
    assert validate_crf(scan) == [] and validate_crf(enrol) == []
    bad = dict(enrol, stream=None, conditions=["flags"], sex="O")
    probs = validate_crf(bad)
    assert probs[:2] == ["missing stream", "sex must be one of ['F', 'M', 'Other']"] and len(probs) == 4
    assert probs[2].startswith("conditions must be a list of") and probs[3].startswith("stream must be one of")
    only_enrol = merged("enrol_complete_male", None)
    assert validate_crf(only_enrol) == ["scan part missing"]
    no_bp = copy.deepcopy(scan)
    no_bp["bp3"] = {"sbp": None}
    assert validate_crf(no_bp) == ["bp3 missing sbp/dbp"]
    assert derive(only_enrol)["pregnant"] is None and derive(merged("female_pregnancy_unknown_uses_nonpregnant", None))["pregnant"] is None
    assert derive(merged("pregnancy_branch_switch_drops_stale", None))["pregnant"] is False
