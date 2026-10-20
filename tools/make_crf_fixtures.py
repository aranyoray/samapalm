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

NOW = "2026-10-20T11:00:00+05:30"


def bp(s, d, h, t):
    return {"sbp": s, "dbp": d, "hr": h, "wall_ts": t}


def clip(a, b, q="pass"):
    return {"started_at": a, "ended_at": b, "quality": q, "kardia_on": True, "beep_heard": True, "notes": ""}


BASE = {
    "study_id": "SWHT-PP-003-0042", "consent": "yes", "stream": "pilot", "dept": "Medicine OPD", "cohort_tags": ["core"], "imaged_hand": "left",
    "name": "Rahul Kumar Das", "hospital_reg_no": "MCH-12345", "phone": "9830012345",
    "bp1": bp(138, 86, 78, "2026-10-20T10:00:00+05:30"),
    "age": 52, "sex": "M", "height_cm": 168.0, "weight_kg": 70.0, "handedness": "right", "arm_circumference_cm": 30.0, "cuff_size": "adult",
    "mst_band": 7, "flags": ["none"], "acute_30m": ["none"], "last_meal_h": 2.5,
    "bp2": bp(132, 84, 74, "2026-10-20T10:06:00+05:30"), "irregular_pulse": "no",
    "clip1": clip("2026-10-20T10:07:00+05:30", "2026-10-20T10:08:00+05:30"),
    "bp3": bp(130, 82, 73, "2026-10-20T10:09:30+05:30"),
}


def case(name, answers, settings=None, hand=None):
    return {"name": name, "settings": settings or {}, "now": NOW, "answers": answers, "hand": hand or {}}


def with_(**kw):
    a = copy.deepcopy(BASE)
    for k, v in kw.items():
        if v is None:
            a.pop(k, None)
        else:
            a[k] = v
    return a


CASES = [
    case("complete_male_1x60", with_(), hand={"errors": [], "stopped": None, "derived": {"bmi": 24.8, "bracket_flag": False, "recovery": "pass",
         "bp1_outlier": False, "cuff_suggestion": "adult", "eligible": True}, "export_has": ["bp1", "bp2", "bp3", "flags", "mst_band", "initials"],
         "export_lacks": ["name", "phone", "hospital_reg_no", "consent", "pregnant"], "export_values": {"initials": "RKD", "irregular_pulse": False}}),
    case("pregnant_branch", with_(sex="F", age=28, pregnant="yes", gestational_age_weeks=20.0, ga_source="usg", parity=0, hdp_status="none",
                                  urine_protein="trace", dept="ANC (OBG)", cohort_tags=["core", "antenatal_addon"]),
         hand={"screens_include": ["pregnancy"], "errors": ["gravida:required"], "derived": {"trimester": 2}, "export_values": {"pregnant": True, "trimester": 2}}),
    case("branch_switch_drops_stale", with_(sex="F", age=34, pregnant="no", gestational_age_weeks=30.0, gravida=2, hdp_status="preeclampsia"),
         hand={"screens_exclude": ["pregnancy"], "errors": [], "export_lacks": ["gestational_age_weeks", "gravida", "hdp_status", "trimester"],
               "export_values": {"pregnant": False}}),
    case("female_60_no_pregnancy_question", with_(sex="F", age=60), hand={"errors": [], "export_lacks": ["pregnant"]}),
    case("flag_conditionals", with_(flags=["hypertension", "arrhythmia", "anaemia/thalassaemia"], arr_type="frequent pvc", arr_status="present today",
                                    haem_type="beta thal trait", transfusion_30d="yes", cohort_tags=["core", "hard_control_nested"]),
         hand={"errors": ["antihtn_today:required", "days_since_transfusion:required", "hb_gdl:required"],
               "questions_include": {"history": ["antihtn_today", "arr_type", "arr_status", "haem_type", "transfusion_30d", "days_since_transfusion"]}}),
    case("diabetes_requires_hba1c_and_date", with_(flags=["diabetes"], dm_type="type 2", on_insulin="no", hba1c=7.9),
         hand={"errors": ["hba1c_date:required"], "export_values": {"on_insulin": False}}),
    case("exclusive_none", with_(flags=["none", "diabetes"], dm_type="type 2", on_insulin="yes", hba1c=8.1, hba1c_date="2026-09-01"),
         hand={"errors": ["flags:exclusive"]}),
    case("no_consent_stops", with_(consent="no"), hand={"stopped": "consent", "errors": ["consent:stop"], "export_lacks": ["consent"]}),
    case("under_18_stops", with_(age=16), hand={"stopped": "age", "errors": ["age:stop"], "derived": {"eligible": False}}),
    case("bp_problems_and_warnings", with_(bp1=bp(170, 100, 90, "2026-10-20T10:00:00+05:30"), bp2=bp(80, 90, 70, "2026-10-20T10:06:00+05:30"),
                                           bp3=bp(140, 88, 72, None)),
         hand={"errors": ["bp2:bp_order", "bp3:bp_time"], "warnings": ["bp2:warn", "bp3:warn"], "derived": {"bracket_flag": True, "bp1_outlier": True}}),
    case("two_clip_plan", with_(clip1=clip("2026-10-20T10:07:00+05:30", "2026-10-20T10:07:30+05:30", "fail"),
                                clip1b=clip("2026-10-20T10:08:00+05:30", "2026-10-20T10:08:30+05:30"),
                                clip2=clip("2026-10-20T10:10:00+05:30", "2026-10-20T10:10:30+05:30")),
         settings={"clip_plan": "2x30"},
         hand={"errors": [], "screens_include": ["clip1b", "clip2"], "screens_exclude": ["clip2b"], "order": ["clip1", "clip1b", "bp2", "clip2", "bp3"]}),
    case("formats_and_dates", with_(study_id="SWHT-PP-3-42", phone="abc", hb_gdl="11.2", hb_date="2026-12-01", mst_band=11),
         hand={"errors": ["study_id:pattern", "phone:pattern", "hb_gdl:type", "hb_date:future", "mst_band:max"]}),
    case("future_date", with_(hb_gdl=11.2, hb_date="2026-12-01"), hand={"errors": ["hb_date:future"]}),
    case("short_rest", with_(clip1=clip("2026-10-20T10:03:00+05:30", "2026-10-20T10:04:00+05:30")), hand={"errors": [], "derived": {"recovery": "short_rest"}}),
    case("missing_required_bp3_and_clip", with_(bp3=None, clip1={"started_at": "2026-10-20T10:07:00+05:30", "quality": "pass"}),
         hand={"errors": ["bp3:required", "clip1:clip_incomplete"]}),
    case("mst_low_warning", with_(mst_band=3), hand={"errors": [], "warnings": ["mst_band:warn"]}),
]


def full(engine, c):
    from datetime import datetime

    now = parse_ts(c["now"])
    ev = engine.evaluate(c["answers"], now)
    crf, ident = engine.export(c["answers"], {"operator": "op1", "unit_id": "unit_01", "app_ver": "test"}, now=now)
    return {"visible_screens": ev.visible_screens, "visible_questions": ev.visible_questions,
            "errors": sorted(i.key() for i in ev.errors), "warnings": sorted(i.key() for i in ev.warnings),
            "stopped": ev.stopped.q if ev.stopped else None,
            "derived": {k: v for k, v in ev.derived.items() if k != "rest_elapsed"}, "export": crf, "identity": ident}


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
        if f["derived"].get(k) != v:
            probs.append(f"derived {k} {f['derived'].get(k)} != {v}")
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
    for k in h.get("export_has", []):
        if k not in f["export"]:
            probs.append(f"export lacks {k}")
    for k in h.get("export_lacks", []):
        if k in f["export"]:
            probs.append(f"export has {k}")
    for k, v in h.get("export_values", {}).items():
        if f["export"].get(k) != v:
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
    path = ROOT / "configs" / "crf_fixtures" / "golden.json"
    path.write_text(json.dumps({"schema_version": schema["schema_version"], "cases": out}, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {path} ({len(out)} cases)")


if __name__ == "__main__":
    main()
