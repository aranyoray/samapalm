from palmppg.core.crf import derive, validate_crf


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
    assert d["dm_label"] == "hba1c_below_threshold"
    assert d["flag_hypertension"] and not d["flag_diabetes"]


def test_out_of_scope_and_problems():
    crf = base_crf(mst_band=2, dept="Unknown", stream="x")
    problems = validate_crf(crf)
    assert any("dept" in p for p in problems) and any("stream" in p for p in problems)
    d = derive(crf)
    assert d["equity_scope"] == "out" and d["mst_group"] == "1-3" and d["mst_equity_arm"] is None
