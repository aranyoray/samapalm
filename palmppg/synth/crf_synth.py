"""CRF, clinician read and latent truth for a synthetic participant (protocol 3.1, CONTRACTS 3.7).

Protocol sections served: 3.1 (every CRF field by name, three bracketing cuff readings with an occasional
BP1 outlier, optional chart values), 7 (population priors that populate every stratum: MST bands mostly
4-10 with a few 1-3, department tags, flags with realistic co-occurrence, antihypertensive timing, acute
exposures), 9 E7 (rhythm classes: sinus mostly, AF about 8 %, hard non-AF about 5 %).

Latent BP model (documented so the relationship is known and recoverable, not a performance claim):
    sbp_true = 95 + 0.45 (age - 45) + 1.0 (bmi - 23) + 12 htn + 4 ckd + 3 dm + 5 (htn and no dose today)
               - 250 (pat_s - 0.24) + 25 (reflection_index - 0.45) + N(0, 6)
    dbp_true = 65 + 0.15 (age - 45) + 0.6 (bmi - 23) + 8 htn - 120 (pat_s - 0.24) + 10 (reflection_index - 0.45) + N(0, 5)
with pat_s ~ N(0.24, 0.03) clipped to [0.17, 0.31] and reflection_index rising with age. Cuff readings are
the latent pressure plus bracketing noise (BP1 higher on seating, BP2/BP3 noisier), and 8 % of BP1 readings
are an outlier (+20..35 mmHg) so the CRF outlier rule (DECISIONS D-005) has something to fire on.
The coefficients live in BP_MODEL and are written into each participant's truth.json.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import numpy as np

from palmppg.core.crf import ACUTE, ANTIHTN, DEPT_TAGS, STREAMS
from palmppg.synth.ecg_synth import IST, rhythm_profile
from palmppg.synth.pulse_wave import default_morphology

BP_MODEL = {
    "sbp": {"intercept": 95.0, "age": 0.45, "bmi": 1.0, "htn": 12.0, "ckd": 4.0, "dm": 3.0, "htn_no_dose": 5.0,
            "pat_s": -250.0, "reflection_index": 25.0, "noise_sd": 6.0, "pat_ref": 0.24, "ri_ref": 0.45, "age_ref": 45.0, "bmi_ref": 23.0},
    "dbp": {"intercept": 65.0, "age": 0.15, "bmi": 0.6, "htn": 8.0, "ckd": 0.0, "dm": 0.0, "htn_no_dose": 0.0,
            "pat_s": -120.0, "reflection_index": 10.0, "noise_sd": 5.0, "pat_ref": 0.24, "ri_ref": 0.45, "age_ref": 45.0, "bmi_ref": 23.0},
}
MST_WEIGHTS = {1: 0.01, 2: 0.01, 3: 0.01, 4: 0.08, 5: 0.14, 6: 0.20, 7: 0.22, 8: 0.17, 9: 0.11, 10: 0.05}
DEPT_WEIGHTS = {"Cardio OPD": 0.16, "Medicine OPD": 0.26, "Nephro OPD": 0.08, "Endo OPD": 0.10, "Haem OPD": 0.06,
                "Thal Day Care": 0.05, "Dialysis": 0.05, "ANC (OBG)": 0.07, "Medicine Ward": 0.08, "Cardio Ward/CCU": 0.05, "Other": 0.04}
RHYTHM_WEIGHTS = {"sinus": 0.885, "af": 0.06, "aflutter": 0.012, "svt": 0.012, "frequent_ectopy": 0.012, "paced": 0.005,
                  "other": 0.007, "unreadable": 0.007}
ARR_TYPES = ["af", "svt", "ectopy", "other"]
HAEM_TYPES = ["iron deficiency", "thalassaemia major", "thalassaemia trait", "other"]
OPERATORS = ["op1", "op2", "op3"]
APP_VER = "onboarding-1.2.0"


def _choice(rng: np.random.Generator, weights: dict):
    keys = list(weights)
    p = np.asarray([weights[k] for k in keys], float)
    return keys[int(rng.choice(len(keys), p=p / p.sum()))]


def sample_latent(study_id: str, rng: np.random.Generator, cfg, overrides: dict | None = None) -> dict:
    """Draw the latent participant: demographics, flags, rhythm, beat statistics, PAT, morphology, melanin, BP."""
    o = dict(overrides or {})
    dept = o.get("dept", _choice(rng, DEPT_WEIGHTS))
    sex = "F" if dept == "ANC (OBG)" else o.get("sex", "F" if rng.random() < 0.45 else "M")
    if dept == "ANC (OBG)":
        age = float(np.clip(rng.normal(27, 5), 18, 42))
    else:
        age = float(np.clip(rng.normal(48, 15), 18, 85))
    age = float(o.get("age", age))
    pregnant = bool(o.get("pregnant", dept == "ANC (OBG)" or (sex == "F" and 18 <= age <= 42 and rng.random() < 0.03)))
    height = float(np.clip(rng.normal(167 if sex == "M" else 154, 7), 140, 195))
    bmi = float(np.clip(rng.normal(23.5, 4.0), 15.5, 40.0))
    weight = round(bmi * (height / 100.0) ** 2, 1)
    mst = int(o.get("mst_band", _choice(rng, MST_WEIGHTS)))
    melanin = float(np.clip((mst - 1) / 9.0 * 0.6 + rng.normal(0, 0.03), 0.0, 0.75))

    p_htn = 0.10 + 0.012 * max(age - 30, 0) + (0.25 if dept in ("Cardio OPD", "Cardio Ward/CCU", "Nephro OPD", "Dialysis") else 0)
    p_dm = 0.06 + 0.008 * max(age - 30, 0) + (0.35 if dept == "Endo OPD" else 0)
    p_ckd = 0.04 + (0.6 if dept in ("Nephro OPD", "Dialysis") else 0)
    p_arr = 0.05 + 0.004 * max(age - 40, 0) + (0.15 if dept in ("Cardio OPD", "Cardio Ward/CCU") else 0)
    p_anaem = 0.08 + (0.6 if dept in ("Haem OPD", "Thal Day Care") else 0) + (0.15 if pregnant else 0)
    flags = []
    htn = rng.random() < min(p_htn, 0.9)
    dm = rng.random() < min(p_dm, 0.9)
    ckd = rng.random() < min(p_ckd, 0.95)
    if ckd and rng.random() < 0.7:
        htn = True
    arr = rng.random() < min(p_arr, 0.9)
    anaem = rng.random() < min(p_anaem, 0.95)
    rhythm = o.get("rhythm")
    if rhythm is None:
        rhythm = _choice(rng, RHYTHM_WEIGHTS)
        if arr and rng.random() < 0.35:
            rhythm = _choice(rng, {"af": 0.55, "frequent_ectopy": 0.25, "svt": 0.1, "aflutter": 0.1})
    if rhythm in ("af", "aflutter", "svt", "frequent_ectopy", "paced") and rng.random() < 0.8:
        arr = True
    for name, on in (("hypertension", htn), ("diabetes", dm), ("chronic kidney disease", ckd), ("arrhythmia", arr),
                     ("anaemia/thalassaemia", anaem)):
        if on:
            flags.append(name)
    if not flags:
        flags = ["none"]
    arr_type = None
    if arr:
        arr_type = {"af": "af", "aflutter": "other", "svt": "svt", "frequent_ectopy": "ectopy"}.get(rhythm, _choice(rng, {k: 1 for k in ARR_TYPES}))
    haem_type = None
    if anaem:
        haem_type = _choice(rng, {"thalassaemia major": 0.6, "thalassaemia trait": 0.3, "other": 0.1}) if dept == "Thal Day Care" \
            else _choice(rng, {"iron deficiency": 0.6, "thalassaemia trait": 0.2, "thalassaemia major": 0.1, "other": 0.1})
    antihtn = (_choice(rng, {"yes <=2 h": 0.3, "yes >2 h": 0.5, "no": 0.2}) if htn else "no")

    prof = rhythm_profile(rhythm)
    lo, hi = cfg.get("synth.hr_bpm")
    hr = float(np.clip(rng.uniform(*prof["hr"]), lo if rhythm == "sinus" else 40, hi if rhythm == "sinus" else 190))
    hrv_sd = float(rng.uniform(*prof["hrv_sd_s"]))
    resp_amp = float(rng.uniform(*prof["resp_amp"]))
    resp_rate = float(rng.uniform(0.18, 0.33))
    pat = float(np.clip(rng.normal(0.24, 0.03), 0.17, 0.31))
    ri = float(np.clip(0.35 + 0.004 * (age - 40) + rng.normal(0, 0.05), 0.15, 0.75))
    morph = default_morphology(
        upstroke_s=float(np.clip(0.19 - 0.0008 * (age - 40) + rng.normal(0, 0.015), 0.10, 0.26)),
        systolic_width_s=float(np.clip(rng.normal(0.21, 0.02), 0.14, 0.30)),
        notch_time_s=float(np.clip(rng.normal(0.36, 0.03), 0.28, 0.46)),
        notch_depth=float(np.clip(rng.normal(0.10, 0.04) - 0.001 * (age - 40), 0.0, 0.25)),
        reflection_index=ri, decay_tau_s=float(np.clip(rng.normal(0.40, 0.06), 0.25, 0.60)))
    ac_lo, ac_hi = cfg.get("synth.ac_dc_g")
    ac_dc_g = float(rng.uniform(ac_lo, ac_hi)) * (0.8 if anaem else 1.0)

    def bp(which):
        m = BP_MODEL[which]
        v = (m["intercept"] + m["age"] * (age - m["age_ref"]) + m["bmi"] * (bmi - m["bmi_ref"]) + m["htn"] * htn + m["ckd"] * ckd
             + m["dm"] * dm + m["htn_no_dose"] * (htn and antihtn == "no") + m["pat_s"] * (pat - m["pat_ref"])
             + m["reflection_index"] * (ri - m["ri_ref"]) + rng.normal(0, m["noise_sd"]))
        return float(v)

    sbp = float(np.clip(bp("sbp"), 85, 200))
    dbp = float(np.clip(bp("dbp"), 50, min(120, sbp - 25)))
    return {
        "study_id": study_id, "age": round(age, 1), "sex": sex, "pregnant": pregnant, "height_cm": round(height, 1),
        "weight_kg": weight, "bmi": round(bmi, 2), "mst_band": mst, "melanin": round(melanin, 4), "dept": dept, "flags": flags,
        "htn": htn, "dm": dm, "ckd": ckd, "arr": arr, "anaem": anaem, "arr_type": arr_type, "haem_type": haem_type,
        "antihtn_today": antihtn, "rhythm": rhythm, "hr_bpm": round(hr, 2), "hrv_sd_s": round(hrv_sd, 4), "resp_amp": round(resp_amp, 4),
        "resp_rate_hz": round(resp_rate, 4), "ectopic_frac": prof["ectopic_frac"], "pat_s": round(pat, 4), "morphology": morph,
        "ac_dc_g": round(ac_dc_g, 5), "ac_ratios": {"R": round(float(rng.uniform(0.4, 0.6)), 3), "G": 1.0, "B": round(float(rng.uniform(0.5, 0.7)), 3)},
        "sbp_true": round(sbp, 2), "dbp_true": round(dbp, 2), "bp_model": BP_MODEL,
    }


def crf_from_latent(latent: dict, rng: np.random.Generator, cfg, visit_start: dt.datetime | None = None, stream: str = "pilot",
                    operator: str | None = None, unit_id: str = "unit_01") -> dict:
    """The CRF the onboarding app would produce for this latent participant (section 3.1 field names)."""
    if stream not in STREAMS:
        raise ValueError(f"stream must be one of {STREAMS}")
    t0 = visit_start or dt.datetime(2026, 10, 20, 9, 30, tzinfo=IST)
    sbp, dbp, hr = latent["sbp_true"], latent["dbp_true"], latent["hr_bpm"]
    cuff_hr_bias = float(rng.normal(0, 2))
    r1 = {"sbp": sbp + 4 + rng.normal(0, 5), "dbp": dbp + 2 + rng.normal(0, 4), "hr": hr + 3 + cuff_hr_bias}
    if rng.random() < 0.08:
        r1["sbp"] += float(rng.uniform(20, 35))
        r1["dbp"] += float(rng.uniform(5, 12))
    r2 = {"sbp": sbp + rng.normal(0, 4), "dbp": dbp + rng.normal(0, 3.5), "hr": hr + cuff_hr_bias + rng.normal(0, 2)}
    r3 = {"sbp": sbp + rng.normal(0, 4), "dbp": dbp + rng.normal(0, 3.5), "hr": hr + cuff_hr_bias + rng.normal(0, 2)}
    readings = {}
    for key, r, minutes in (("bp1", r1, 0), ("bp2", r2, 6), ("bp3", r3, 9)):
        readings[key] = {"sbp": int(round(r["sbp"])), "dbp": int(round(r["dbp"])), "hr": int(round(r["hr"])),
                         "wall_ts": (t0 + dt.timedelta(minutes=minutes)).isoformat(timespec="seconds")}
    has_hb = rng.random() < 0.40 or (latent["anaem"] and rng.random() < 0.5)
    has_hba1c = rng.random() < 0.40 or (latent["dm"] and rng.random() < 0.5)
    hb = float(np.clip(rng.normal(9.5 if latent["anaem"] else 13.2, 1.3), 5.0, 17.5)) if has_hb else None
    hba1c = float(np.clip(rng.normal(8.0 if latent["dm"] else 5.5, 1.0 if latent["dm"] else 0.4), 4.0, 14.0)) if has_hba1c else None
    acute = ["none"]
    if rng.random() < 0.30:
        acute = [a for a in ACUTE[1:] if rng.random() < 0.4] or ["none"]
    irregular = latent["rhythm"] in ("af", "frequent_ectopy", "other")
    if rng.random() < 0.10:
        irregular = not irregular
    initials = "".join(chr(int(c)) for c in rng.integers(65, 91, size=2))
    crf = {
        "study_id": latent["study_id"], "initials": initials, "age": int(round(latent["age"])), "sex": latent["sex"],
        "pregnant": bool(latent["pregnant"]), "height_cm": latent["height_cm"], "weight_kg": latent["weight_kg"],
        "handedness": "right" if rng.random() < 0.9 else "left",
        "cuff_size": "large" if latent["bmi"] >= 30 else ("small" if latent["bmi"] < 18.5 else "adult"),
        "mst_band": int(latent["mst_band"]), "dept": latent["dept"], "flags": list(latent["flags"]), "arr_type": latent["arr_type"],
        "haem_type": latent["haem_type"], "antihtn_today": latent["antihtn_today"], "acute_30m": acute,
        "hb_gdl": round(hb, 1) if hb is not None else None,
        "hb_date": (t0 - dt.timedelta(days=int(rng.integers(1, 120)))).date().isoformat() if hb is not None else None,
        "hba1c": round(hba1c, 1) if hba1c is not None else None,
        "hba1c_date": (t0 - dt.timedelta(days=int(rng.integers(1, 180)))).date().isoformat() if hba1c is not None else None,
        "bp1": readings["bp1"], "bp2": readings["bp2"], "bp3": readings["bp3"],
        "spo2": int(rng.integers(94, 100)) if rng.random() < 0.9 else None, "irregular_pulse": bool(irregular),
        "recovery": "pass" if rng.random() < 0.92 else "fail", "imaged_hand": "left" if rng.random() < 0.98 else "right",
        "bracket_flag": None, "glucose_mgdl": int(rng.integers(80, 260)) if rng.random() < 0.30 else None,
        "last_meal_h": round(float(rng.uniform(0.5, 12)), 1) if rng.random() < 0.8 else None,
        "operator": operator or OPERATORS[int(rng.integers(0, len(OPERATORS)))], "unit_id": unit_id, "stream": stream,
        "app_ver": APP_VER, "screen_log": ["consent", "demographics", "history", "bp1", "rest", "bp2", "clip", "bp3", "review"],
    }
    assert crf["dept"] in DEPT_TAGS and crf["antihtn_today"] in ANTIHTN
    return crf


def clinician_from_latent(latent: dict, rng: np.random.Generator, cfg, ecg_hr_bpm: float | None = None, read_date: str | None = None) -> dict:
    """clinician.json (CONTRACTS 3.6): rhythm in cfg ecg.rhythm_classes, ecg_hr consistent with the generated beats."""
    classes = list(cfg.get("ecg.rhythm_classes"))
    rhythm = latent["rhythm"]
    if rhythm not in classes:
        raise ValueError(f"rhythm {rhythm} not in cfg ecg.rhythm_classes")
    hr = float(ecg_hr_bpm if ecg_hr_bpm is not None else latent["hr_bpm"])
    return {"rhythm": rhythm, "ecg_hr": int(round(hr + rng.normal(0, 0.8))), "lead12_obtained": bool(rng.random() < 0.10),
            "adverse_event": None if rng.random() < 0.99 else "transient dizziness",
            "reader_id": f"reader{int(rng.integers(1, 4))}", "read_date": read_date or "2026-10-21"}


def sample_crf(study_id: str, rng: np.random.Generator, cfg, stream: str = "pilot", overrides: dict | None = None) -> tuple[dict, dict, dict]:
    """Sample (crf, clinician, latent) for one synthetic participant. Section 3.1 / 7 / 9 E7."""
    latent = sample_latent(study_id, rng, cfg, overrides)
    crf = crf_from_latent(latent, rng, cfg, stream=stream)
    clin = clinician_from_latent(latent, rng, cfg)
    return crf, clin, latent


def write_participant_forms(part_dir: str | Path, crf: dict, clinician: dict) -> tuple[Path, Path]:
    part_dir = Path(part_dir)
    part_dir.mkdir(parents=True, exist_ok=True)
    p1 = part_dir / "crf.json"
    p2 = part_dir / "clinician.json"
    p1.write_text(json.dumps(crf, indent=1), encoding="utf-8")
    p2.write_text(json.dumps(clinician, indent=1), encoding="utf-8")
    return p1, p2
