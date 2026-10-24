"""CRF (case report form) parsing, validation and derived fields.

Field names follow section 3.1 of the protocol exactly. Derived fields:
  bmi, bp_target_sbp/dbp (mean of the three cuff readings, BP1 dropped when it is the clear outlier),
  bp_target_23 (mean of BP2 and BP3, sensitivity analysis), bracket_flag, equity_scope, dm_label,
  bp_category, age_band, bmi_class, hr_cuff_mean, bp_target_rule (which rule fired).
Cuff BP is intermittent and bracketing; nothing here pretends otherwise.

Two record versions are read. v1 (schema 2026-10-20, one record per visit): `flags`, `hba1c`, boolean `pregnant`.
v2 (schema 2026-10-24, onboarding design section 7): the per-PID crf.json merged from the enrol and scan parts, with
both parts' questions at top level and `parts: {enrol: {...context}, scan: {...context}}`; a single exported part
(`part` key) is read too. v2 covariates come from `conditions` (cond_* flags) and the engine's derivations
(haem_cell, dm_label, anaemia_grade, mentzer, hplc_reflex), recomputed with palmppg.core.crf_schema when absent.
v1 flags are mapped onto conditions (and v2 conditions onto the v1 flag_* columns) so both feed the same columns.
"""
from __future__ import annotations

import datetime as dt
import json
import math
from pathlib import Path
from typing import Any, Mapping

from palmppg.core.crf_schema import CONDITION_ORDER, anaemia_grade, dm_label, haem_cell, hplc_reflex, mst_group, parse_ts

DEPT_TAGS = ["Cardio OPD", "Medicine OPD", "Nephro OPD", "Endo OPD", "Haem OPD", "Thal Day Care", "Dialysis",
             "ANC (OBG)", "Medicine Ward", "Cardio Ward/CCU", "Other"]
FLAGS = ["none", "hypertension", "diabetes", "chronic kidney disease", "arrhythmia", "anaemia/thalassaemia"]
ANTIHTN = ["yes <=2 h", "yes >2 h", "no"]
ACUTE = ["none", "caffeine", "tobacco", "exercise", "meal"]
STREAMS = ["pilot", "development", "model_selection", "test"]
REQUIRED = ["study_id", "age", "sex", "mst_band", "dept", "flags", "bp1", "bp2", "bp3", "operator", "unit_id", "stream"]
BP_KEYS = ("sbp", "dbp", "hr")
# v2 (onboarding design section 2): conditions replace flags; the record is split into enrol and scan parts.
CONDITIONS = list(CONDITION_ORDER)
SEXES = ["F", "M", "Other"]
REQUIRED_V2 = {"enrol": ["study_id", "age", "sex", "mst_band", "dept", "conditions", "stream"],
               "scan": ["study_id", "bp1", "bp2", "bp3"]}
CONTEXT_REQUIRED = ["operator", "unit_id"]
CONTEXT_KEYS = ["operator", "unit_id", "app_ver", "device_code", "capture_mode", "schema_version"]
# v1 flag <-> v2 condition. A v1 arrhythmia is AF when arr_type says so; a v1 anaemia/thalassaemia uses haem_type.
FLAG_TO_CONDITION = {"hypertension": "htn", "diabetes": "diabetes", "chronic kidney disease": "ckd", "none": "none"}
V1_HAEM_TO_CONDITION = {"beta thal trait": "thal", "thal disease": "thal", "hbe": "thal", "iron deficiency": "ida"}
V1_HAEM_TO_THAL_TYPE = {"beta thal trait": "beta_trait", "thal disease": "beta_major_intermedia", "hbe": "hbe_beta"}
CONDITION_TO_FLAG = {"htn": "hypertension", "diabetes": "diabetes", "ckd": "chronic kidney disease", "af": "arrhythmia",
                     "arrhythmia_other": "arrhythmia", "thal": "anaemia/thalassaemia", "ida": "anaemia/thalassaemia",
                     "anaemia_other": "anaemia/thalassaemia"}
YES_NO = {"yes": True, "no": False}


class CRFError(ValueError):
    pass


def _num(x) -> float | None:
    if x is None or x == "" or (isinstance(x, float) and math.isnan(x)):
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _reading(crf: Mapping, key: str) -> dict | None:
    r = crf.get(key)
    if not isinstance(r, Mapping):
        return None
    out = {k: _num(r.get(k)) for k in BP_KEYS}
    out["wall_ts"] = r.get("wall_ts") or r.get("wall_ns") or r.get("ts")
    if out["sbp"] is None or out["dbp"] is None:
        return None
    return out


def load_crf(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def is_v2(crf: Mapping) -> bool:
    """A v2 record: a single exported part, a merged per-PID record, or anything carrying `conditions`."""
    return crf.get("part") in REQUIRED_V2 or isinstance(crf.get("parts"), Mapping) or "conditions" in crf


def crf_parts(crf: Mapping) -> list[str]:
    """Which v2 parts a record holds: its `part`, the keys of a merged record's `parts`, else inferred from fields."""
    if crf.get("part") in REQUIRED_V2:
        return [crf["part"]]
    if isinstance(crf.get("parts"), Mapping):
        return [p for p in REQUIRED_V2 if p in crf["parts"]]
    return [p for p, keys in (("enrol", ("conditions", "sex")), ("scan", ("bp1", "clip1"))) if any(k in crf for k in keys)]


def context_value(crf: Mapping, key: str, prefer: tuple[str, ...] = ("scan", "enrol")) -> Any:
    """A context key (operator, unit_id, ...) at top level, else from a merged record's parts (scan part first:
    the capture's operator and unit are the nuisance variables that matter for the PPG)."""
    if crf.get(key) not in (None, ""):
        return crf[key]
    parts = crf.get("parts") if isinstance(crf.get("parts"), Mapping) else {}
    for p in prefer:
        v = parts.get(p, {}).get(key) if isinstance(parts.get(p), Mapping) else None
        if v not in (None, ""):
            return v
    return None


def _validate_v2(crf: Mapping) -> list[str]:
    problems = []
    parts = crf_parts(crf)
    if not parts:
        return ["no enrol or scan fields found"]
    if isinstance(crf.get("parts"), Mapping):
        problems += [f"{p} part missing" for p in REQUIRED_V2 if p not in parts]
    for p in parts:
        for k in REQUIRED_V2[p]:
            if k not in crf or crf[k] in (None, ""):
                problems.append(f"missing {k}")
        for k in CONTEXT_REQUIRED:
            if context_value(crf, k, (p,)) is None:
                problems.append(f"missing {k} ({p} part)")
    if "enrol" in parts:
        mst = _num(crf.get("mst_band"))
        if mst is None or not (1 <= mst <= 10):
            problems.append("mst_band must be 1..10")
        if crf.get("dept") not in DEPT_TAGS:
            problems.append(f"dept not in MCK tag list: {crf.get('dept')}")
        if crf.get("sex") not in SEXES:
            problems.append(f"sex must be one of {SEXES}")
        conds = crf.get("conditions")
        if not isinstance(conds, list) or any(c not in CONDITIONS for c in conds):
            problems.append(f"conditions must be a list of {CONDITIONS}")
        if crf.get("stream") not in STREAMS:
            problems.append(f"stream must be one of {STREAMS}")
    if "scan" in parts:
        for k in ("bp1", "bp2", "bp3"):
            if _reading(crf, k) is None:
                problems.append(f"{k} missing sbp/dbp")
    return sorted(set(problems), key=problems.index)


def validate_crf(crf: Mapping) -> list[str]:
    """Return a list of problems (empty when the CRF is usable). v2 records are checked part by part."""
    if is_v2(crf):
        return _validate_v2(crf)
    problems = []
    for k in REQUIRED:
        if k not in crf or crf[k] in (None, ""):
            problems.append(f"missing {k}")
    mst = _num(crf.get("mst_band"))
    if mst is None or not (1 <= mst <= 10):
        problems.append("mst_band must be 1..10")
    if crf.get("dept") not in DEPT_TAGS:
        problems.append(f"dept not in MCK tag list: {crf.get('dept')}")
    flags = crf.get("flags") or []
    if isinstance(flags, str):
        flags = [flags]
    for f in flags:
        if f not in FLAGS:
            problems.append(f"unknown flag {f}")
    if crf.get("stream") not in STREAMS:
        problems.append(f"stream must be one of {STREAMS}")
    if crf.get("antihtn_today") not in (None, *ANTIHTN):
        problems.append("antihtn_today invalid")
    for k in ("bp1", "bp2", "bp3"):
        if _reading(crf, k) is None:
            problems.append(f"{k} missing sbp/dbp")
    return problems


def bp_category(sbp: float | None, dbp: float | None) -> str | None:
    """ACC/AHA 2017 bands on the cuff mean (format for stratification, not a clinical statement)."""
    if sbp is None or dbp is None:
        return None
    if sbp >= 140 or dbp >= 90:
        return "stage 2"
    if sbp >= 130 or dbp >= 80:
        return "stage 1"
    if sbp >= 120:
        return "elevated"
    return "normal"


def age_band(age: float | None) -> str | None:
    if age is None:
        return None
    return "<40" if age < 40 else ("40-59" if age < 60 else "60+")


def bmi_class(bmi: float | None, cutoffs: str = "asia_pacific") -> str | None:
    if bmi is None:
        return None
    if cutoffs == "asia_pacific":  # WHO Asia-Pacific, the convention in Indian cohorts
        bands = [(18.5, "underweight"), (23.0, "normal"), (25.0, "overweight"), (math.inf, "obese")]
    else:  # WHO international
        bands = [(18.5, "underweight"), (25.0, "normal"), (30.0, "overweight"), (math.inf, "obese")]
    for hi, name in bands:
        if bmi < hi:
            return name
    return None


def bp_target(r1: dict | None, r2: dict | None, r3: dict | None, outlier_mmhg: float = 15.0, key: str = "sbp") -> tuple[float | None, str]:
    """Mean of three cuff readings; BP1 dropped if it deviates > outlier_mmhg from the BP2/BP3 mean."""
    vals = [r[key] for r in (r1, r2, r3) if r is not None and r.get(key) is not None]
    if r2 is not None and r3 is not None and r2.get(key) is not None and r3.get(key) is not None:
        m23 = (r2[key] + r3[key]) / 2.0
        if r1 is not None and r1.get(key) is not None and abs(r1[key] - m23) > outlier_mmhg:
            return m23, "mean_bp2_bp3_bp1_outlier"
    if not vals:
        return None, "none"
    return sum(vals) / len(vals), "mean_bp1_bp2_bp3" if len(vals) == 3 else f"mean_of_{len(vals)}"


def derive(crf: Mapping, cfg: Mapping | None = None) -> dict:
    """Return the CRF plus derived fields. cfg keys (all optional):
    bracket_mmhg (10), bp1_outlier_mmhg (15), bmi_cutoffs ('asia_pacific'), hba1c_dm_threshold (6.5),
    equity_min_band (4), equity_max_band (10).
    """
    cfg = dict(cfg or {})
    out = dict(crf)
    v2 = is_v2(crf)
    if v2:
        conds = [c for c in CONDITIONS if c in (crf.get("conditions") or [])]
        flags = sorted({CONDITION_TO_FLAG[c] for c in conds if c in CONDITION_TO_FLAG}, key=FLAGS.index) or (["none"] if "none" in conds else [])
        for k in CONTEXT_KEYS:
            out[k] = context_value(crf, k)
    else:
        flags = crf.get("flags") or []
        if isinstance(flags, str):
            flags = [flags]
        conds = v1_conditions(flags, crf.get("arr_type"), crf.get("haem_type"))
    out["flags"] = list(flags)
    for f in FLAGS[1:]:
        out["flag_" + f.replace(" ", "_").replace("/", "_")] = f in flags
    out["conditions"] = conds
    for c in CONDITIONS[:-1]:
        out["cond_" + c] = c in conds

    h = _num(crf.get("height_cm"))
    w = _num(crf.get("weight_kg"))
    out["bmi"] = (w / (h / 100.0) ** 2) if (h and w and h > 0) else None
    out["bmi_class"] = bmi_class(out["bmi"], cfg.get("bmi_cutoffs", "asia_pacific"))
    out["age_band"] = age_band(_num(crf.get("age")))

    r1, r2, r3 = (_reading(crf, k) for k in ("bp1", "bp2", "bp3"))
    outl = float(cfg.get("bp1_outlier_mmhg", 15.0))
    out["bp_target_sbp"], out["bp_target_rule_sbp"] = bp_target(r1, r2, r3, outl, "sbp")
    out["bp_target_dbp"], out["bp_target_rule_dbp"] = bp_target(r1, r2, r3, outl, "dbp")
    out["bp_target_rule"] = out["bp_target_rule_sbp"]
    for key in ("sbp", "dbp"):
        v23 = [r[key] for r in (r2, r3) if r is not None and r.get(key) is not None]
        out[f"bp_target_23_{key}"] = sum(v23) / len(v23) if v23 else None
    out["bp_target_23"] = out["bp_target_23_sbp"]
    hrs = [r["hr"] for r in (r1, r2, r3) if r is not None and r.get("hr") is not None]
    out["hr_cuff_mean"] = sum(hrs) / len(hrs) if hrs else None

    bracket = float(cfg.get("bracket_mmhg", 10.0))
    spread = {}
    for key in ("sbp", "dbp"):
        vals = [r[key] for r in (r1, r2, r3) if r is not None and r.get(key) is not None]
        spread[key] = (max(vals) - min(vals)) if len(vals) >= 2 else None
    out["bp_spread_sbp"], out["bp_spread_dbp"] = spread["sbp"], spread["dbp"]
    out["bracket_flag"] = any(s is not None and s > bracket for s in spread.values())

    mst = _num(crf.get("mst_band"))
    lo, hi = int(cfg.get("equity_min_band", 4)), int(cfg.get("equity_max_band", 10))
    out["mst_band"] = int(mst) if mst is not None else None
    out["equity_scope"] = "in" if (mst is not None and lo <= mst <= hi) else "out"
    out["mst_group"] = None if mst is None else ("4-5" if mst <= 5 else ("6-7" if mst <= 7 else ("8-10" if mst <= 10 else None)))
    if mst is not None and mst < 4:
        out["mst_group"] = "1-3"
    out["mst_equity_arm"] = None if mst is None else ("7-10" if 7 <= mst <= 10 else ("4-6" if 4 <= mst <= 6 else None))

    hba1c = _num(crf.get("hba1c_pct")) if crf.get("hba1c_pct") is not None else _num(crf.get("hba1c"))
    out["hba1c"] = out["hba1c_pct"] = hba1c
    thr = float(cfg.get("hba1c_dm_threshold", 6.5))
    # v2 labels for every record (documented_hba1c | documented | hba1c_only | no_known); the app's own label wins.
    out["dm_label"] = crf.get("dm_label") if (v2 and crf.get("dm_label")) else dm_label(conds, hba1c, thr)

    out["bp_category"] = bp_category(out["bp_target_sbp"], out["bp_target_dbp"])
    preg = crf.get("pregnant")
    out["pregnant"] = YES_NO.get(preg) if isinstance(preg, str) else (bool(preg) if preg is not None else None)
    out["spo2"] = _num(crf.get("spo2"))
    out["hb_gdl"] = _num(crf.get("hb_gdl"))
    out["glucose_mgdl"] = _num(crf.get("glucose_mgdl"))
    out["last_meal_h"] = _num(crf.get("last_meal_h"))
    out["irregular_pulse"] = crf.get("irregular_pulse")
    out["imaged_hand"] = crf.get("imaged_hand", "left")
    # Add-on fields captured by the onboarding app (configs/crf_schema.json); absent on older CRFs.
    ga = _num(crf.get("gestational_age_weeks"))
    out["gestational_age_weeks"] = ga
    out["trimester"] = crf.get("trimester") if crf.get("trimester") is not None else ((1 if ga < 14 else 2 if ga < 28 else 3) if ga is not None else None)
    out["anc_hb_gdl"] = _num(crf.get("anc_hb_gdl"))
    out["ita_deg"] = _num(crf.get("ita_deg"))
    tags = crf.get("cohort_tags") or []
    out["cohort_tags"] = list(tags) if isinstance(tags, (list, tuple)) else [tags]
    for tag in ("af_nested", "hard_control_nested", "anaemia_nested", "antenatal_addon"):
        out[f"cohort_{tag}"] = tag in out["cohort_tags"]
    hdp = crf.get("hdp_status")
    out["hdp_present"] = None if hdp in (None, "unknown") else hdp != "none"
    out["requires_reshoot_review"] = bool(out["bracket_flag"])
    _derive_v2_haem(crf, out, cfg)
    for k in ("htn_meds_today", "cardiac_device", "on_dialysis"):
        if isinstance(crf.get(k), str):
            out[k] = YES_NO.get(crf[k])
    if crf.get("dm_treatment") is not None:
        out["on_insulin"] = crf["dm_treatment"] in ("insulin", "tablets_insulin")
    out["dm_years"] = _num(crf.get("dm_years"))
    out["mstgrp"] = mst_group(out["mst_band"]) if out["mst_band"] is not None and 1 <= out["mst_band"] <= 10 else None
    out["kardia_determination"] = _kardia(crf.get("clip1b")) or _kardia(crf.get("clip1"))
    return out


def v1_conditions(flags: list, arr_type: Any = None, haem_type: Any = None) -> list[str]:
    """v2 conditions implied by v1 flags (arrhythmia split by arr_type, anaemia/thalassaemia by haem_type)."""
    out = {FLAG_TO_CONDITION[f] for f in flags if f in FLAG_TO_CONDITION}
    if "arrhythmia" in flags:
        out.add("af" if arr_type == "af" else "arrhythmia_other")
    if "anaemia/thalassaemia" in flags:
        out.add(V1_HAEM_TO_CONDITION.get(haem_type, "anaemia_other"))
    return [c for c in CONDITIONS if c in out]


def _kardia(clip: Any) -> str | None:
    v = clip.get("kardia_determination") if isinstance(clip, Mapping) else None
    return v if isinstance(v, str) and v.strip() else None


def _visit_date(crf: Mapping):
    """Scan date (BP1 time) for the transfusion interval, else the enrol part's submission time."""
    b1 = crf.get("bp1")
    for ts in (b1.get("wall_ts") if isinstance(b1, Mapping) else None, context_value(crf, "submitted_at", ("enrol", "scan"))):
        t = parse_ts(ts)
        if t is not None:
            return t.date()
    return None


def _derive_v2_haem(crf: Mapping, out: dict, cfg: Mapping) -> None:
    """Haematology covariates: the exported engine values when present, else recomputed from the record."""
    for k in ("hb_gdl", "rbc_mill", "mcv_fl", "mch_pg", "rdw_pct", "ferritin_ngml", "hba2_pct", "hbf_pct", "hbe_pct"):
        out[k] = _num(crf.get(k))
    preg = "yes" if out["pregnant"] is True else None
    grade = crf.get("anaemia_grade") or anaemia_grade(out["hb_gdl"], crf.get("sex"), preg, out["trimester"])
    out["anaemia_grade"] = grade
    out["anaemic"] = None if grade is None else grade != "none"
    mcv, rbc = out["mcv_fl"], out["rbc_mill"]
    mi = _num(crf.get("mentzer"))
    out["mentzer_index"] = mi if mi is not None else (round(mcv / rbc, 1) if mcv is not None and rbc else None)
    if out["mentzer_index"] is None or mcv is None:
        out["mentzer_pattern"] = None
    else:
        out["mentzer_pattern"] = "not_microcytic" if mcv >= 80 else ("thal_trait_pattern" if out["mentzer_index"] < 13 else "iron_deficiency_pattern")
    hr = crf.get("hplc_reflex")
    out["hplc_reflex"] = hr if isinstance(hr, bool) else hplc_reflex(mcv, out["mch_pg"])
    record = {**crf, "conditions": out["conditions"], "ferritin_ngml": out["ferritin_ngml"]}
    if not is_v2(crf) and crf.get("haem_type") in V1_HAEM_TO_THAL_TYPE:
        record["thal_type"] = V1_HAEM_TO_THAL_TYPE[crf["haem_type"]]
    out["haem_cell"] = crf.get("haem_cell") or haem_cell(record, out["anaemic"], float(cfg.get("ferritin_id_cutoff", 15.0)))
    if "days_since_transfusion" not in crf or crf.get("days_since_transfusion") is None:
        last, ref = None, _visit_date(crf)
        if isinstance(crf.get("last_transfusion_date"), str):
            try:
                last = dt.date.fromisoformat(crf["last_transfusion_date"])
            except ValueError:
                last = None
        out["days_since_transfusion"] = (ref - last).days if (last and ref) else None
        if out["days_since_transfusion"] is not None:
            out["transfusion_30d"] = out["days_since_transfusion"] <= 30
        elif crf.get("transfusion_3m") == "no":
            out["transfusion_30d"] = False
    out["days_since_transfusion"] = _num(out.get("days_since_transfusion"))


def derive_file(path: str | Path, cfg: Mapping | None = None) -> dict:
    crf = load_crf(path)
    problems = validate_crf(crf)
    d = derive(crf, cfg)
    d["crf_problems"] = problems
    d["crf_valid"] = not problems
    return d


def covariate_columns() -> list[str]:
    """Clinical covariates carried into every feature table (section 6.7)."""
    return ["study_id", "age", "sex", "pregnant", "age_band", "bmi", "bmi_class", "mst_band", "mst_group", "mst_equity_arm",
            "equity_scope", "dept", "flags", "flag_hypertension", "flag_diabetes", "flag_chronic_kidney_disease",
            "flag_arrhythmia", "flag_anaemia_thalassaemia", "arr_type", "haem_type", "antihtn_today", "acute_30m",
            "hb_gdl", "hba1c", "dm_label", "bp_target_sbp", "bp_target_dbp", "bp_target_23_sbp", "bp_target_23_dbp",
            "bp_target_rule", "bracket_flag", "bp_category", "hr_cuff_mean", "spo2", "irregular_pulse", "recovery",
            "imaged_hand", "handedness", "glucose_mgdl", "last_meal_h", "operator", "unit_id", "stream", "app_ver", "cuff_size",
            # onboarding-app add-ons: nested cohorts, antenatal add-on, rhythm and haemoglobinopathy detail, colorimetry
            "cohort_af_nested", "cohort_hard_control_nested", "cohort_anaemia_nested", "cohort_antenatal_addon",
            "gestational_age_weeks", "trimester", "hdp_status", "hdp_present", "urine_protein", "anc_hb_gdl",
            "arr_status", "transfusion_30d", "dm_type", "on_insulin", "on_dialysis", "ita_deg",
            # schema v2 (onboarding design section 2): conditions and their follow-ups, lab values on record and the
            # engine's derivations, the recruitment MST group and the Kardia app's determination for the clip
            "conditions", "cond_htn", "cond_af", "cond_arrhythmia_other", "cond_heart_other", "cond_diabetes", "cond_thal",
            "cond_ida", "cond_anaemia_other", "cond_ckd", "htn_meds", "htn_meds_today", "af_pattern", "anticoagulant",
            "arrhythmia_type", "cardiac_device", "dm_years", "dm_treatment", "thal_type", "thal_transfusions", "iron_therapy",
            "transfusion_3m", "days_since_transfusion", "anaemia_grade", "anaemic", "haem_cell", "rbc_mill", "mcv_fl",
            "mch_pg", "rdw_pct", "mentzer_index", "mentzer_pattern", "hplc_reflex", "ferritin_ngml", "hplc_result",
            "hba2_pct", "hbf_pct", "hbe_pct", "hba1c_pct", "mstgrp", "kardia_determination", "device_code"]
