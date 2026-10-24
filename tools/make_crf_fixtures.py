"""Build configs/crf_fixtures/golden.json: hand-written answer sets with hand-checked expectations ("hand") plus the
full engine output ("full") that the Kotlin engine must reproduce exactly. Re-run after a schema change and review
the diff; the hand expectations are asserted before anything is written."""
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from palmppg.core.crf_schema import CrfEngine, load_schema, parse_ts  # noqa: E402

NOW = "2026-10-24T11:00:00+05:30"
SCAN = {"part": "scan"}
SCAN_2X30 = {"part": "scan", "clip_plan": "2x30"}


def bp(s, d, h, t):
    return {"sbp": s, "dbp": d, "hr": h, "wall_ts": t}


def clip(a, b, q="pass", kardia=None):
    c = {"started_at": a, "ended_at": b, "quality": q, "kardia_on": True, "beep_heard": True, "notes": ""}
    if kardia:
        c["kardia_determination"] = kardia
    return c


ENROL = {
    "study_id": "SWHT-PP-003-0042", "consent": "yes", "stream": "pilot", "dept": "Medicine OPD",
    "age": 52, "sex": "M", "height_cm": 168.0, "weight_kg": 70.0, "mst_band": 7,
    "conditions": ["none"], "transfusion_3m": "no", "acute_30m": ["none"], "last_meal_h": 2.5,
}
FEMALE = {"sex": "F", "age": 30, "pregnant": "no"}
SCAN_BASE = {
    "study_id": "SWHT-PP-003-0042", "imaged_hand": "left", "arm_circumference_cm": 30.0, "cuff_size": "adult",
    "bp1": bp(138, 86, 78, "2026-10-24T10:00:00+05:30"),
    "bp2": bp(132, 84, 74, "2026-10-24T10:06:00+05:30"), "irregular_pulse": "no",
    "clip1": clip("2026-10-24T10:07:00+05:30", "2026-10-24T10:08:00+05:30", kardia="nsr"),
    "bp3": bp(130, 82, 73, "2026-10-24T10:09:30+05:30"),
}
HB = {"hb_date": "2026-10-01"}


def case(name, answers, settings=None, hand=None):
    return {"name": name, "settings": settings or {}, "now": NOW, "answers": answers, "hand": hand or {}}


def mk(base, *overlays, **kw):
    a = copy.deepcopy(base)
    for o in overlays:
        a.update(copy.deepcopy(o))
    for k, v in kw.items():
        if v is None:
            a.pop(k, None)
        else:
            a[k] = v
    return a


def enrol(*o, **kw):
    return mk(ENROL, *o, **kw)


def scan(*o, **kw):
    return mk(SCAN_BASE, *o, **kw)


def grade(g, anaemic):
    return {"anaemia_grade": g, "anaemic": anaemic}


HAEM_Q = ["rbc_mill", "mcv_fl", "mch_pg", "rdw_pct", "mentzer", "hplc_reflex", "ferritin_ngml", "ferritin_date"]

CASES = [
    # ---------------------------------------------------------------- enrol part: complete record, strata, export
    case("enrol_complete_male", enrol(), hand={
        "errors": [], "stopped": None,
        "screens": ["pid", "e_consent", "e_basics", "e_conditions", "e_labs", "e_today", "e_review"],
        "derived": {"bmi": 24.8, "eligible": True, "anaemia_grade": None, "haem_cell": None, "dm_label": "no_known",
                    "strata": ["sex:M", "mst:7", "mstgrp:dark", "cond:none", "dm:no_known", "sex_mst:M:7"], "scan_strata": None},
        "export_values": {"part": "enrol", "schema_version": "2026-10-24.1", "dm_label": "no_known", "bmi": 24.8, "transfusion_3m": "no",
                          "strata": ["sex:M", "mst:7", "mstgrp:dark", "cond:none", "dm:no_known", "sex_mst:M:7"]},
        "export_lacks": ["consent", "clip_plan", "anaemia_grade", "haem_cell", "pregnant", "initials", "name", "bp1"]}),
    case("enrol_ignores_clip_plan", enrol(), settings={"clip_plan": "2x30"},
         hand={"errors": [], "export_lacks": ["clip_plan"], "export_values": {"part": "enrol"}}),
    case("strata_order_and_cross_keys", enrol(FEMALE, HB, pregnant="yes", age=29, gestational_age_weeks=20.0, mst_band=9,
                                              conditions=["diabetes", "af", "htn"], htn_meds="one", htn_meds_today="yes",
                                              af_pattern="paroxysmal", anticoagulant="no", cardiac_device="no", dm_type="t2",
                                              dm_treatment="tablets", hb_gdl=9.0), hand={
        "errors": [],
        "derived": {"trimester": 2, "anaemia_grade": "moderate", "anaemic": True, "haem_cell": "anaemia_other", "dm_label": "documented",
                    "strata": ["sex:F", "mst:9", "mstgrp:dark", "cond:htn", "cond:af", "cond:diabetes", "haem:anaemia_other",
                               "dm:documented", "preg:yes", "sex_mst:F:9", "cond_mstgrp:htn:dark", "cond_mstgrp:af:dark",
                               "cond_mstgrp:diabetes:dark", "haem_mstgrp:anaemia_other:dark"]},
        "questions_include": {"e_conditions": ["htn_meds", "htn_meds_today", "af_pattern", "anticoagulant", "cardiac_device", "dm_type",
                                               "dm_years", "dm_treatment"], "e_labs": HAEM_Q},
        "export_values": {"pregnant": "yes", "trimester": 2, "gestational_age_weeks": 20.0}}),
    case("sex_other_low_mst", enrol(sex="Other", mst_band=3, hb_gdl=9.5, **HB), hand={
        "errors": [], "warnings": ["mst_band:warn"],
        "derived": {"anaemia_grade": None, "anaemic": None, "haem_cell": None,
                    "strata": ["sex:Other", "mst:3", "mstgrp:light", "cond:none", "dm:no_known", "sex_mst:Other:3"]}}),
    # ---------------------------------------------------------------- WHO grades (non-pregnant)
    case("male_hb_13_0_none", enrol(hb_gdl=13.0, **HB), hand={"errors": [], "derived": {**grade("none", False), "haem_cell": "non_anaemic",
         "strata": ["sex:M", "mst:7", "mstgrp:dark", "cond:none", "haem:non_anaemic", "dm:no_known", "sex_mst:M:7",
                    "haem_mstgrp:non_anaemic:dark"]}, "questions_exclude": {"e_labs": HAEM_Q + ["hplc_result"]}}),
    case("male_hb_12_9_mild_needs_date", enrol(hb_gdl=12.9), hand={"errors": ["hb_date:required"],
         "derived": {**grade("mild", True), "haem_cell": "anaemia_other"}, "questions_include": {"e_labs": HAEM_Q}}),
    case("male_hb_11_0_mild", enrol(hb_gdl=11.0, **HB), hand={"errors": [], "derived": grade("mild", True)}),
    case("male_hb_10_9_moderate", enrol(hb_gdl=10.9, **HB), hand={"errors": [], "derived": grade("moderate", True)}),
    case("female_hb_12_0_none", enrol(FEMALE, HB, hb_gdl=12.0), hand={"errors": [], "derived": {**grade("none", False), "haem_cell": "non_anaemic"}}),
    case("female_hb_11_9_mild", enrol(FEMALE, HB, hb_gdl=11.9), hand={"errors": [], "derived": grade("mild", True)}),
    case("female_hb_8_0_moderate", enrol(FEMALE, HB, hb_gdl=8.0), hand={"errors": [], "derived": grade("moderate", True)}),
    case("female_hb_7_9_severe", enrol(FEMALE, HB, hb_gdl=7.9), hand={"errors": [], "derived": grade("severe", True)}),
    case("female_pregnancy_unknown_uses_nonpregnant", enrol(FEMALE, HB, pregnant="unknown", hb_gdl=11.5),
         hand={"errors": [], "derived": {**grade("mild", True), "trimester": None}, "export_values": {"pregnant": "unknown"}}),
    # ---------------------------------------------------------------- WHO grades (pregnant, by trimester)
    case("pregnant_t1_hb_11_0_none", enrol(FEMALE, HB, pregnant="yes", gestational_age_weeks=13.9, hb_gdl=11.0),
         hand={"errors": [], "derived": {"trimester": 1, **grade("none", False)}}),
    case("pregnant_t1_hb_10_9_mild", enrol(FEMALE, HB, pregnant="yes", gestational_age_weeks=8.0, hb_gdl=10.9),
         hand={"errors": [], "derived": {"trimester": 1, **grade("mild", True)}}),
    case("pregnant_t2_hb_10_5_none", enrol(FEMALE, HB, pregnant="yes", gestational_age_weeks=14.0, hb_gdl=10.5),
         hand={"errors": [], "derived": {"trimester": 2, **grade("none", False)}}),
    case("pregnant_t2_hb_10_4_mild", enrol(FEMALE, HB, pregnant="yes", gestational_age_weeks=27.9, hb_gdl=10.4),
         hand={"errors": [], "derived": {"trimester": 2, **grade("mild", True)}}),
    case("pregnant_t2_hb_9_4_moderate", enrol(FEMALE, HB, pregnant="yes", gestational_age_weeks=20.0, hb_gdl=9.4),
         hand={"errors": [], "derived": {"trimester": 2, **grade("moderate", True)}}),
    case("pregnant_t3_hb_10_9_mild", enrol(FEMALE, HB, pregnant="yes", gestational_age_weeks=28.0, hb_gdl=10.9),
         hand={"errors": [], "derived": {"trimester": 3, **grade("mild", True)}}),
    case("pregnant_t3_hb_6_9_severe", enrol(FEMALE, HB, pregnant="yes", gestational_age_weeks=36.0, hb_gdl=6.9),
         hand={"errors": [], "derived": {"trimester": 3, **grade("severe", True)}}),
    case("pregnant_unknown_trimester_uses_t13", enrol(FEMALE, HB, pregnant="yes", hb_gdl=10.7),
         hand={"errors": ["gestational_age_weeks:required"], "derived": {"trimester": None, **grade("mild", True)}}),
    case("pregnancy_branch_switch_drops_stale", enrol(FEMALE, HB, pregnant="no", gestational_age_weeks=20.0, hb_gdl=10.7),
         hand={"errors": [], "derived": {"trimester": None, **grade("moderate", True)},
               "export_lacks": ["gestational_age_weeks", "trimester"], "export_values": {"pregnant": "no"}}),
    case("female_60_no_pregnancy_question", enrol(sex="F", age=60, pregnant="yes"),
         hand={"errors": [], "export_lacks": ["pregnant"], "questions_exclude": {"e_basics": ["pregnant", "gestational_age_weeks"]}}),
    # ---------------------------------------------------------------- Mentzer and HPLC reflex
    case("mentzer_mcv_80_not_microcytic", enrol(conditions=["anaemia_other"], mcv_fl=80.0, rbc_mill=4.0, mch_pg=28.0),
         hand={"errors": [], "derived": {"mentzer_index": 20.0, "mentzer_pattern": "not_microcytic", "hplc_reflex": False,
                                         "haem_cell": "anaemia_other"},
               "questions_exclude": {"e_labs": ["hplc_result"]}, "export_values": {"mentzer": 20.0, "hplc_reflex": False}}),
    case("mentzer_index_13_iron_pattern", enrol(conditions=["anaemia_other"], mcv_fl=65.0, rbc_mill=5.0),
         hand={"errors": [], "derived": {"mentzer_index": 13.0, "mentzer_pattern": "iron_deficiency_pattern", "hplc_reflex": True},
               "questions_include": {"e_labs": ["hplc_result"]}}),
    case("mentzer_index_12_9_thal_pattern", enrol(conditions=["anaemia_other"], mcv_fl=64.5, rbc_mill=5.0, mch_pg=27.0),
         hand={"errors": [], "derived": {"mentzer_index": 12.9, "mentzer_pattern": "thal_trait_pattern", "hplc_reflex": True}}),
    case("hplc_reflex_mch_only", enrol(conditions=["ida"], iron_therapy="oral", mch_pg=26.9),
         hand={"errors": [], "derived": {"mentzer_index": None, "mentzer_pattern": None, "hplc_reflex": True, "haem_cell": "ida"}}),
    case("hplc_reflex_mcv_only_false", enrol(conditions=["anaemia_other"], mcv_fl=85.0),
         hand={"errors": [], "derived": {"hplc_reflex": False, "mentzer_index": None}, "questions_exclude": {"e_labs": ["hplc_result"]}}),
    case("hplc_reflex_none_without_indices", enrol(conditions=["anaemia_other"], rbc_mill=4.5, rdw_pct=15.0),
         hand={"errors": [], "derived": {"hplc_reflex": None, "mentzer_index": None}, "export_lacks": ["hplc_reflex", "mentzer"]}),
    # ---------------------------------------------------------------- haem_cell precedence
    case("haem_hplc_trait_beats_ida", enrol(conditions=["ida"], iron_therapy="none", mcv_fl=66.0, rbc_mill=5.6, hplc_result="beta_trait",
                                            hba2_pct=5.1, hplc_date="2026-08-01"),
         hand={"errors": [], "derived": {"haem_cell": "thal_trait", "mentzer_index": 11.8, "mentzer_pattern": "thal_trait_pattern"},
               "questions_include": {"e_labs": ["hplc_result", "hba2_pct", "hbf_pct", "hbe_pct", "hplc_date"]}}),
    case("haem_disease_beats_trait_and_hplc_date_required", enrol(conditions=["thal", "ida"], thal_type="beta_trait", thal_transfusions="regular",
                                                                   iron_therapy="none", hplc_result="hbe_beta"),
         hand={"errors": ["hplc_date:required"], "derived": {"haem_cell": "thal_disease"}}),
    case("haem_thal_unspecified", enrol(conditions=["thal"], thal_type="other_unknown", thal_transfusions="none", hplc_result="not_done",
                                        hba2_pct=3.0),
         hand={"errors": [], "derived": {"haem_cell": "thal_unspecified"}, "export_lacks": ["hba2_pct"],
               "questions_exclude": {"e_labs": ["hba2_pct", "hplc_date"]}}),
    case("haem_ida_by_ferritin", enrol(FEMALE, HB, hb_gdl=10.0, ferritin_ngml=14.9, ferritin_date="2026-10-01"),
         hand={"errors": [], "derived": {"haem_cell": "ida", **grade("moderate", True)}}),
    case("haem_ferritin_at_cutoff_is_other", enrol(FEMALE, HB, hb_gdl=10.0, ferritin_ngml=15.0),
         hand={"errors": ["ferritin_date:required"], "derived": {"haem_cell": "anaemia_other"}}),
    case("haem_ferritin_cutoff_setting", enrol(FEMALE, HB, hb_gdl=10.0, ferritin_ngml=20.0, ferritin_date="2026-10-01"),
         settings={"ferritin_id_cutoff": 30}, hand={"errors": [], "derived": {"haem_cell": "ida"}}),
    case("haem_stale_answers_dropped_when_not_anaemic", enrol(hb_gdl=14.0, hplc_result="beta_trait", thal_type="beta_major_intermedia",
                                                              ferritin_ngml=5.0, **HB),
         hand={"errors": [], "derived": {"haem_cell": "non_anaemic"}, "export_lacks": ["hplc_result", "thal_type", "ferritin_ngml"]}),
    # ---------------------------------------------------------------- dm_label
    case("dm_documented_hba1c_at_cutoff", enrol(conditions=["htn", "diabetes"], htn_meds="two", htn_meds_today="yes", dm_type="t2",
                                                dm_years=8, dm_treatment="tablets", hba1c_pct=6.5, hba1c_date="2026-09-01"),
         hand={"errors": [], "derived": {"dm_label": "documented_hba1c"}, "export_values": {"dm_years": 8, "htn_meds": "two"}}),
    case("dm_documented_below_cutoff", enrol(conditions=["diabetes"], dm_type="t1", dm_treatment="insulin", hba1c_pct=6.4, hba1c_date="2026-09-01"),
         hand={"errors": [], "derived": {"dm_label": "documented"}}),
    case("dm_hba1c_only_needs_date", enrol(hba1c_pct=7.0), hand={"errors": ["hba1c_date:required"], "derived": {"dm_label": "hba1c_only"}}),
    case("dm_cutoff_setting", enrol(hba1c_pct=7.0, hba1c_date="2026-09-01"), settings={"hba1c_dm_cutoff": 7.5},
         hand={"errors": [], "derived": {"dm_label": "no_known"}}),
    # ---------------------------------------------------------------- conditions branches, transfusion
    case("condition_followups_required", enrol(conditions=["af", "ckd", "heart_other"]), hand={
        "errors": ["af_pattern:required", "anticoagulant:required", "cardiac_device:required", "on_dialysis:required"],
        "questions_exclude": {"e_conditions": ["arrhythmia_type", "htn_meds", "dm_type"]}}),
    case("htn_meds_none_drops_today", enrol(conditions=["htn"], htn_meds="none", htn_meds_today="yes"),
         hand={"errors": [], "export_lacks": ["htn_meds_today"], "export_values": {"htn_meds": "none"}}),
    case("transfusion_30_days", enrol(transfusion_3m="yes", last_transfusion_date="2026-09-24"),
         hand={"errors": [], "derived": {"days_since_transfusion": 30, "transfusion_30d": True}}),
    case("transfusion_31_days", enrol(transfusion_3m="yes", last_transfusion_date="2026-09-23"),
         hand={"errors": [], "derived": {"days_since_transfusion": 31, "transfusion_30d": False}}),
    case("transfusion_date_required_and_stale", enrol(transfusion_3m="yes"),
         hand={"errors": ["last_transfusion_date:required"], "derived": {"days_since_transfusion": None, "transfusion_30d": None}}),
    case("transfusion_no_drops_date", enrol(transfusion_3m="no", last_transfusion_date="2026-10-20"),
         hand={"errors": [], "derived": {"days_since_transfusion": None}, "export_lacks": ["last_transfusion_date"]}),
    # ---------------------------------------------------------------- stops, exclusivity, formats
    case("no_consent_stops", enrol(consent="no"), hand={"stopped": "consent", "errors": ["consent:stop"], "export_lacks": ["consent"]}),
    case("under_18_stops", enrol(age=16), hand={"stopped": "age", "errors": ["age:min", "age:stop"], "derived": {"eligible": False}}),
    case("exclusive_none", enrol(conditions=["none", "diabetes"], dm_type="t2", dm_treatment="diet", acute_30m=["none", "caffeine"]),
         hand={"errors": ["acute_30m:exclusive", "conditions:exclusive"]}),
    case("formats_and_dates", enrol(study_id="SWHT-PP-3-42", hb_gdl="11.2", hb_date="2026-12-01", mst_band=11, age=30.5),
         hand={"errors": ["age:type", "hb_date:future", "hb_gdl:type", "mst_band:max", "study_id:pattern"],
               "derived": {"strata": ["sex:M", "cond:none", "dm:no_known"]}}),
    # ---------------------------------------------------------------- scan part
    case("complete_male_1x60", scan(), settings=SCAN, hand={
        "errors": [], "stopped": None, "screens": ["pid", "s_setup", "bp1", "bp2", "clip1", "bp3", "s_review"],
        "derived": {"bracket_flag": False, "recovery": "pass", "bp1_outlier": False, "cuff_suggestion": "adult",
                    "scan_strata": ["rhythm:nsr", "scan:done"], "strata": None, "dm_label": None},
        "export_values": {"part": "scan", "clip_plan": "1x60", "irregular_pulse": False, "imaged_hand": "left",
                          "scan_strata": ["rhythm:nsr", "scan:done"], "recovery": "pass", "bracket_flag": False},
        "export_lacks": ["sex", "strata", "clip1b", "cuff_suggestion"]}),
    case("scan_2x30_reshoot_uses_clip1b_rhythm", scan(clip1=clip("2026-10-24T10:07:00+05:30", "2026-10-24T10:07:30+05:30", "fail", "unreadable"),
                                                     clip1b=clip("2026-10-24T10:08:00+05:30", "2026-10-24T10:08:30+05:30", kardia="af"),
                                                     clip2=clip("2026-10-24T10:10:00+05:30", "2026-10-24T10:10:30+05:30", kardia="af")),
         settings=SCAN_2X30, hand={"errors": [], "screens": ["pid", "s_setup", "bp1", "clip1", "clip1b", "bp2", "clip2", "bp3", "s_review"],
                                   "derived": {"scan_strata": ["rhythm:af", "scan:done"]}, "export_values": {"clip_plan": "2x30"}}),
    case("scan_clip1b_without_rhythm_falls_back", scan(clip1=clip("2026-10-24T10:07:00+05:30", "2026-10-24T10:08:00+05:30", "fail", "too_short"),
                                                       clip1b=clip("2026-10-24T10:08:30+05:30", "2026-10-24T10:09:00+05:30"), bp3=None),
         settings=SCAN, hand={"errors": ["bp3:required"], "derived": {"scan_strata": ["rhythm:too_short"]}}),
    case("scan_stale_reshoot_dropped", scan(clip1b=clip("2026-10-24T10:08:30+05:30", "2026-10-24T10:09:00+05:30", kardia="af")),
         settings=SCAN, hand={"errors": [], "derived": {"scan_strata": ["rhythm:nsr", "scan:done"]}, "export_lacks": ["clip1b"]}),
    case("scan_2x30_reshoot_screen_order", scan(clip2=clip("2026-10-24T10:10:00+05:30", "2026-10-24T10:10:30+05:30", "fail")),
         settings=SCAN_2X30, hand={"errors": ["clip2b:required"], "order": ["clip1", "bp2", "clip2", "clip2b", "bp3"],
                                   "screens_exclude": ["clip1b"]}),
    case("scan_bp_problems_and_warnings", scan(bp1=bp(170, 100, 90, "2026-10-24T10:00:00+05:30"), bp2=bp(80, 90, 70, "2026-10-24T10:06:00+05:30"),
                                               bp3=bp(140, 88, 72, None)),
         settings=SCAN, hand={"errors": ["bp2:bp_order", "bp3:bp_time"], "warnings": ["bp2:warn", "bp3:warn"],
                              "derived": {"bracket_flag": True, "bp1_outlier": True}}),
    case("scan_short_rest_and_incomplete_clip", scan(clip1={"started_at": "2026-10-24T10:03:00+05:30", "quality": "pass"}, arm_circumference_cm=None),
         settings=SCAN, hand={"errors": ["arm_circumference_cm:required", "clip1:clip_incomplete"], "derived": {"recovery": "short_rest",
                                                                                                                "scan_strata": ["scan:done"]}}),
    case("scan_hand_default_from_settings", scan(imaged_hand=None), settings={"part": "scan", "imaged_hand": "right"},
         hand={"errors": ["imaged_hand:required"], "export_lacks": ["imaged_hand"]}),
]


def full(engine, c):
    now = parse_ts(c["now"])
    ev = engine.evaluate(c["answers"], now)
    crf = engine.export(c["answers"], {"operator": "op1", "unit_id": "unit_01", "app_ver": "test"}, now=now)
    return {"visible_screens": ev.visible_screens, "visible_questions": ev.visible_questions,
            "errors": sorted(i.key() for i in ev.errors), "warnings": sorted(i.key() for i in ev.warnings),
            "stopped": ev.stopped.q if ev.stopped else None,
            "derived": {k: v for k, v in ev.derived.items() if k != "rest_elapsed"}, "export": crf,
            "initial": engine.initial_answers()}


def check_hand(c, f):
    h = c["hand"]
    probs = []
    if "errors" in h and sorted(h["errors"]) != f["errors"]:
        probs.append(f"errors {f['errors']} != {sorted(h['errors'])}")
    if "warnings" in h and sorted(h["warnings"]) != f["warnings"]:
        probs.append(f"warnings {f['warnings']} != {sorted(h['warnings'])}")
    if "stopped" in h and h["stopped"] != f["stopped"]:
        probs.append(f"stopped {f['stopped']} != {h['stopped']}")
    for k, v in h.get("derived", {}).items():
        if k not in f["derived"] or f["derived"][k] != v or type(f["derived"][k]) is not type(v):
            probs.append(f"derived {k} {f['derived'].get(k)} != {v}")
    if "screens" in h and h["screens"] != f["visible_screens"]:
        probs.append(f"screens {f['visible_screens']} != {h['screens']}")
    for s in h.get("screens_include", []):
        if s not in f["visible_screens"]:
            probs.append(f"screen {s} not visible")
    for s in h.get("screens_exclude", []):
        if s in f["visible_screens"]:
            probs.append(f"screen {s} visible")
    if "order" in h:
        idx = [f["visible_screens"].index(s) for s in h["order"]]
        if idx != sorted(idx):
            probs.append(f"order {h['order']} not respected")
    for sid, qs in h.get("questions_include", {}).items():
        for q in qs:
            if q not in f["visible_questions"].get(sid, []):
                probs.append(f"question {q} not visible on {sid}")
    for sid, qs in h.get("questions_exclude", {}).items():
        for q in qs:
            if q in f["visible_questions"].get(sid, []):
                probs.append(f"question {q} visible on {sid}")
    for k in h.get("export_has", []):
        if k not in f["export"]:
            probs.append(f"export lacks {k}")
    for k in h.get("export_lacks", []):
        if k in f["export"]:
            probs.append(f"export has {k}")
    for k, v in h.get("export_values", {}).items():
        if k not in f["export"] or f["export"][k] != v or type(f["export"][k]) is not type(v):
            probs.append(f"export {k} {f['export'].get(k)} != {v}")
    return probs


def main():
    schema = load_schema()
    out, bad = [], {}
    for c in CASES:
        eng = CrfEngine(schema, c["settings"])
        f = full(eng, c)
        p = check_hand(c, f)
        if p:
            bad[c["name"]] = p
        out.append({**c, "full": f})
    if bad:
        print(json.dumps(bad, indent=1))
        raise SystemExit(1)
    parts = {(c["settings"].get("part", "enrol"), c["settings"].get("clip_plan", "1x60")) for c in CASES}
    assert {("enrol", "1x60"), ("scan", "1x60"), ("scan", "2x30")} <= parts and len(CASES) >= 24
    path = ROOT / "configs" / "crf_fixtures" / "golden.json"
    path.write_text(json.dumps({"schema_version": schema["schema_version"], "cases": out}, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {path} ({len(out)} cases)")


if __name__ == "__main__":
    main()
