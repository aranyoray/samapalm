"""CRF (case report form) parsing, validation and derived fields.

Field names follow section 3.1 of the protocol exactly. Derived fields:
  bmi, bp_target_sbp/dbp (mean of the three cuff readings, BP1 dropped when it is the clear outlier),
  bp_target_23 (mean of BP2 and BP3, sensitivity analysis), bracket_flag, equity_scope, dm_label,
  bp_category, age_band, bmi_class, hr_cuff_mean, bp_target_rule (which rule fired).
Cuff BP is intermittent and bracketing; nothing here pretends otherwise.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Mapping

DEPT_TAGS = ["Cardio OPD", "Medicine OPD", "Nephro OPD", "Endo OPD", "Haem OPD", "Thal Day Care", "Dialysis",
             "ANC (OBG)", "Medicine Ward", "Cardio Ward/CCU", "Other"]
FLAGS = ["none", "hypertension", "diabetes", "chronic kidney disease", "arrhythmia", "anaemia/thalassaemia"]
ANTIHTN = ["yes <=2 h", "yes >2 h", "no"]
ACUTE = ["none", "caffeine", "tobacco", "exercise", "meal"]
STREAMS = ["pilot", "development", "model_selection", "test"]
REQUIRED = ["study_id", "age", "sex", "mst_band", "dept", "flags", "bp1", "bp2", "bp3", "operator", "unit_id", "stream"]
BP_KEYS = ("sbp", "dbp", "hr")


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


def validate_crf(crf: Mapping) -> list[str]:
    """Return a list of problems (empty when the CRF is usable)."""
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
    flags = crf.get("flags") or []
    if isinstance(flags, str):
        flags = [flags]
    out["flags"] = list(flags)
    for f in FLAGS[1:]:
        out["flag_" + f.replace(" ", "_").replace("/", "_")] = f in flags

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

    hba1c = _num(crf.get("hba1c"))
    thr = float(cfg.get("hba1c_dm_threshold", 6.5))
    if "diabetes" in flags:
        out["dm_label"] = "known_dm"
    elif hba1c is not None and hba1c >= thr:
        out["dm_label"] = "hba1c_above_threshold_no_flag"
    elif hba1c is not None:
        out["dm_label"] = "hba1c_below_threshold"
    else:
        out["dm_label"] = "no_flag_no_hba1c"

    out["bp_category"] = bp_category(out["bp_target_sbp"], out["bp_target_dbp"])
    out["pregnant"] = bool(crf.get("pregnant")) if crf.get("pregnant") is not None else None
    out["spo2"] = _num(crf.get("spo2"))
    out["hb_gdl"] = _num(crf.get("hb_gdl"))
    out["glucose_mgdl"] = _num(crf.get("glucose_mgdl"))
    out["last_meal_h"] = _num(crf.get("last_meal_h"))
    out["irregular_pulse"] = crf.get("irregular_pulse")
    out["imaged_hand"] = crf.get("imaged_hand", "left")
    out["requires_reshoot_review"] = bool(out["bracket_flag"])
    return out


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
            "imaged_hand", "handedness", "glucose_mgdl", "last_meal_h", "operator", "unit_id", "stream", "app_ver", "cuff_size"]
