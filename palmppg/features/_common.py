"""Internal helpers shared by the feature-store modules (protocol section 6.7, CONTRACTS section 5).

JSON flattening with "__", numeric coercion with booleans kept, nullable dtype harmonisation for
parquet, the registry wrapper that registers every column exactly once, and the column-name parser
that supplies units and descriptions to the data dictionary.
"""
from __future__ import annotations

import json
import math
import numbers
import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from palmppg.core.tracks import CAMERAS, REGISTRY, FeatureMeta, FeatureRegistry, TrackViolation

SEP = "__"
LIST_JOIN = ";"
ID_COLUMNS: tuple[str, ...] = ("study_id", "clip_id", "camera", "stream", "source_study_id")
# Keys inside per-clip JSON files that duplicate the row identifiers or the registry flags and are
# therefore not flattened into feature columns.
JSON_META_KEYS: frozenset[str] = frozenset({"study_id", "clip_id", "camera", "requires_ecg", "requires_raw"})

_NUMERIC_RE = re.compile(r"^[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$")


# --------------------------------------------------------------------------- null / coercion
def is_null(v: Any) -> bool:
    """True for None, pandas NA and float NaN (never for arrays or strings)."""
    if v is None or v is pd.NA:
        return True
    if isinstance(v, (float, np.floating)):
        return bool(math.isnan(float(v)))
    return False


def coerce_scalar(v: Any) -> Any:
    """Numeric coercion with booleans kept (CONTRACTS section 0.11).

    bool stays bool; ints and floats become float; numeric-looking strings become float; the strings
    "true"/"false" become bool; empty strings and NaN become None; every other string is kept verbatim.
    """
    if is_null(v):
        return None
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, numbers.Real):
        return float(v)
    if isinstance(v, str):
        s = v.strip()
        if s == "":
            return None
        if _NUMERIC_RE.match(s):
            return float(s)
        if s.lower() in ("true", "false"):
            return s.lower() == "true"
        return s
    if isinstance(v, (bytes, bytearray)):
        return v.decode("utf-8", errors="replace")
    return str(v)


def flatten(obj: Any, prefix: str = "", skip: Iterable[str] = (), sep: str = SEP) -> dict[str, Any]:
    """Flatten nested mappings into {key__subkey: scalar}.

    Lists of scalars collapse to one ";"-joined string column plus a `<key>__n` count column (an empty
    list gives None and 0); lists of mappings are expanded by index. Keys in `skip` are dropped at any
    depth. Values are returned un-coerced; callers apply `coerce_scalar`.
    """
    skip = set(skip)
    out: dict[str, Any] = {}

    def rec(node: Any, key: str) -> None:
        if isinstance(node, Mapping):
            for k, v in node.items():
                if k in skip:
                    continue
                rec(v, f"{key}{sep}{k}" if key else str(k))
        elif isinstance(node, (list, tuple, np.ndarray)):
            items = list(node)
            if all(not isinstance(x, (Mapping, list, tuple, np.ndarray)) for x in items):
                out[key] = LIST_JOIN.join(str(coerce_scalar(x)) for x in items) if items else None
                out[f"{key}{sep}n"] = len(items)
            else:
                for i, v in enumerate(items):
                    rec(v, f"{key}{sep}{i}")
        else:
            out[key] = node

    rec(obj, prefix)
    return out


def load_json(path: str | Path) -> dict | None:
    """Read a JSON object; None when the file is absent (every input of the feature store is optional)."""
    p = Path(path)
    if not p.exists():
        return None
    with open(p, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return data if isinstance(data, Mapping) else None


# --------------------------------------------------------------------------- dtypes
def harmonise_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """Give every column a nullable dtype that survives parquet: boolean, float64 or object strings.

    A column whose non-null values are all bool becomes pandas "boolean"; all-numeric becomes float64;
    all-null becomes float64 NaN; anything else is kept as object with None for missing values.
    """
    out = df.copy()
    for c in out.columns:
        vals = out[c].tolist()
        present = [v for v in vals if not is_null(v)]
        if not present:
            out[c] = pd.Series([np.nan] * len(out), dtype="float64", index=out.index)
        elif all(isinstance(v, (bool, np.bool_)) for v in present):
            out[c] = pd.array([None if is_null(v) else bool(v) for v in vals], dtype="boolean")
        elif all(isinstance(v, numbers.Real) and not isinstance(v, (bool, np.bool_)) for v in present):
            out[c] = pd.to_numeric(out[c], errors="coerce").astype("float64")
        else:
            out[c] = pd.Series([None if is_null(v) else str(v) for v in vals], dtype=object, index=out.index)
    return out


def record_to_frame(record: Mapping[str, Any]) -> pd.DataFrame:
    """One-row DataFrame from a flat record with harmonised nullable dtypes."""
    return harmonise_dtypes(pd.DataFrame({k: [v] for k, v in record.items()}))


# --------------------------------------------------------------------------- column naming
GROUP_DESCRIPTIONS: dict[str, str] = {
    "id": "row identifier",
    "covariate": "clinical covariate or derived stratum from the CRF (protocol 3.1, 7)",
    "qc": "ingest quality-control flag or measurement (protocol 6.1)",
    "sync": "synchronisation field from the clip timeline (protocol 4.4)",
    "static_colour": "static colour feature from the first seconds of the clip (protocol 6.2)",
    "pulse": "pulse extraction summary per method and ROI (protocol 6.3)",
    "hrv": "heart-rate variability from palm beats (protocol 6.5)",
    "morphology": "beat morphology, per-beat ensemble (protocol 6.5)",
    "apg": "acceleration plethysmogram wave feature (protocol 6.5)",
    "perfusion": "perfusion index per ROI and channel (protocol 6.5)",
    "resp": "respiratory modulation proxy (protocol 6.5)",
    "beats": "beat-level clip aggregate (protocol 6.5)",
    "embedding": "learned embedding component from a video model (protocol 6.3)",
    "ecg": "ECG-derived feature, requires_ecg (protocol 6.4)",
    "pat": "pulse arrival time versus ECG, requires_ecg (protocol 6.6)",
    "clinician": "clinician ECG read, requires_ecg (protocol 3)",
}

# (suffix or exact-name pattern, units, description) checked in order against the last name part.
_NAME_RULES: tuple[tuple[str, str, str], ...] = (
    (r"^hr_bpm$", "bpm", "pulse rate of the dominant spectral peak"),
    (r"^sqi$", "0..1", "signal quality index (snr_band, CONTRACTS section 6)"),
    (r"^snr_db$", "dB", "SNR of the dominant band peak versus the rest of the band"),
    (r"^best$", "label", "method__roi with the highest SQI in the clip"),
    (r"^drop_pct$", "%", "frames dropped, from true frame-time gaps"),
    (r"^saturation_frac$", "fraction", "saturated-pixel fraction inside the skin mask"),
    (r"^lighting_drift_pct$", "%", "linear intensity trend across the clip"),
    (r"^vignetting_residual_pct$", "%", "residual vignetting after flat-field correction"),
    (r"^landmark_jitter_px$", "px", "landmark jitter used as a motion proxy"),
    (r"^eis_warp_px$", "px", "residual electronic stabilisation warp"),
    (r"^fs_median$", "Hz", "median frame rate from true frame times"),
    (r"^duration_s$", "s", "clip duration on the reference clock"),
    (r"^n_frames$", "count", "frames read"),
    (r"^reasons$", "list", "failing QC flag names, ';'-joined"),
    (r"^colour_space$", "label", "linear_raw or inverted_srgb (phone values are linearised from sRGB)"),
    (r"^grade$", "label", "sync grade: fine | coarse | none"),
    (r"^ecg_map_method$", "label", "clock-map method that placed the ECG on the reference clock"),
    (r"^ecg_uncertainty_s$", "s", "stated uncertainty of the ECG clock map"),
    (r"^xcorr_peak$", "r", "normalised cross-correlation peak of ECG versus pulse rate series"),
    (r"_bpm$", "bpm", "rate in beats per minute"),
    (r"_mmhg$", "mmHg", "pressure"),
    (r"_ms$", "ms", "duration in milliseconds"),
    (r"(?<!pct)_s$", "s", "duration in seconds"),
    (r"_pct$", "%", "percentage"),
    (r"_db$", "dB", "decibels"),
    (r"_px$", "px", "pixels"),
    (r"_hz$", "Hz", "frequency"),
    (r"_gdl$", "g/dL", "concentration"),
    (r"_mgdl$", "mg/dL", "concentration"),
    (r"_cm$", "cm", "length"),
    (r"_kg$", "kg", "mass"),
    (r"(_frac|_fraction|_ratio|_index|_idx)$", "ratio", "dimensionless ratio or index"),
    (r"(_flag|_found|_ok|_detected|_agree|_allowed|^is_|_valid|^valid_)", "bool", "boolean flag"),
    (r"(^n_|_n$|_count$)", "count", "count"),
    (r"_entropy$", "nats", "entropy"),
)

COVARIATE_DESCRIPTIONS: dict[str, tuple[str, str]] = {
    "age": ("years", "age at visit"),
    "sex": ("label", "sex as recorded on the CRF"),
    "pregnant": ("bool", "pregnant at visit"),
    "age_band": ("label", "<40 | 40-59 | 60+"),
    "bmi": ("kg/m^2", "body-mass index from height and weight"),
    "bmi_class": ("label", "WHO Asia-Pacific BMI class"),
    "mst_band": ("band", "Monk Skin Tone band, self-selected 1..10"),
    "mst_group": ("label", "MST grouping 4-5 | 6-7 | 8-10 (1-3 out of scope)"),
    "mst_equity_arm": ("label", "equity arm 4-6 versus 7-10 (protocol 7)"),
    "equity_scope": ("label", "in when MST band is within the equity range"),
    "dept": ("label", "department tag"),
    "flags": ("list", "disease flags, ';'-joined"),
    "flag_hypertension": ("bool", "hypertension flag"),
    "flag_diabetes": ("bool", "diabetes flag"),
    "flag_chronic_kidney_disease": ("bool", "chronic kidney disease flag"),
    "flag_arrhythmia": ("bool", "arrhythmia flag"),
    "flag_anaemia_thalassaemia": ("bool", "anaemia or thalassaemia flag"),
    "arr_type": ("label", "arrhythmia type when flagged"),
    "haem_type": ("label", "haematological type when flagged"),
    "antihtn_today": ("label", "antihypertensive taken today: yes <=2 h | yes >2 h | no"),
    "acute_30m": ("list", "acute exposures in the last 30 min, ';'-joined"),
    "hb_gdl": ("g/dL", "chart haemoglobin"),
    "hba1c": ("%", "chart HbA1c"),
    "dm_label": ("label", "diabetes label derived from flag and HbA1c (DECISIONS D-005)"),
    "bp_target_sbp": ("mmHg", "cuff SBP reference: mean of three readings, BP1 dropped when outlying (target)"),
    "bp_target_dbp": ("mmHg", "cuff DBP reference (target)"),
    "bp_target_23_sbp": ("mmHg", "mean of BP2 and BP3 SBP (sensitivity target)"),
    "bp_target_23_dbp": ("mmHg", "mean of BP2 and BP3 DBP (sensitivity target)"),
    "bp_target_rule": ("label", "which averaging rule produced the SBP target"),
    "bracket_flag": ("bool", "cuff readings spread above the bracket threshold"),
    "bp_category": ("label", "ACC/AHA 2017 band on the cuff mean (stratification format)"),
    "hr_cuff_mean": ("bpm", "mean cuff heart rate across readings"),
    "spo2": ("%", "spot SpO2, nullable"),
    "irregular_pulse": ("bool", "operator noted an irregular pulse"),
    "recovery": ("label", "recovery gate result"),
    "imaged_hand": ("label", "hand imaged"),
    "handedness": ("label", "handedness"),
    "glucose_mgdl": ("mg/dL", "point-of-care glucose, nullable"),
    "last_meal_h": ("h", "hours since the last meal"),
    "operator": ("label", "operator id"),
    "unit_id": ("label", "capture unit id"),
    "stream": ("label", "data stream: pilot | development | model_selection | test"),
    "app_ver": ("label", "onboarding app version"),
    "cuff_size": ("label", "cuff size used"),
    "time_of_day": ("label", "morning | afternoon on the local clock (protocol 7)"),
    "lux_band": ("label", "ambient lux band <200 | 200-400 | >400 (protocol 7)"),
    "bp_tertile": ("label", "reference SBP tertile with cut points from the development set (protocol 10)"),
    "capture_mode": ("label", "simultaneous | sequential (protocol 2)"),
    "rhythm_class": ("label", "clinician rhythm class from clinician.json (protocol 6.4)"),
    "ecg_digitised": ("bool", "ECG came from the PDF digitiser rather than an ATC file"),
    "sync_grade": ("label", "sync grade: fine | coarse | none (protocol 4.4)"),
    "study_id": ("id", "participant id (join key)"),
    "clip_id": ("id", "clip id; clip1b marks the single permitted re-shoot"),
    "camera": ("id", "pi | phone | pi_proxy"),
    "source_study_id": ("id", "source participant of an augmented copy (protocol 8); null for originals"),
}


def parse_column(name: str) -> dict[str, str | None]:
    """Split `group__camera__roi__method__name` (CONTRACTS section 5) into its parts, camera None when absent."""
    parts = name.split(SEP)
    group = parts[0]
    camera = parts[1] if len(parts) > 1 and parts[1] in CAMERAS else None
    rest = parts[2:] if camera else parts[1:]
    return {"group": group, "camera": camera, "rest": SEP.join(rest), "last": parts[-1]}


def describe_column(name: str) -> tuple[str, str]:
    """(units, description) for a column from its name alone, so repeated registrations agree exactly."""
    if name in COVARIATE_DESCRIPTIONS:
        return COVARIATE_DESCRIPTIONS[name]
    info = parse_column(name)
    base = GROUP_DESCRIPTIONS.get(info["group"], "feature")
    last = info["last"].lower()
    units, detail = "", ""
    for pattern, u, d in _NAME_RULES:
        if re.search(pattern, last):
            units, detail = u, d
            break
    if info["group"] == "embedding":
        units, detail = "a.u.", "embedding dimension"
    where = f" [{info['rest']}]" if info["rest"] else ""
    desc = f"{base}{where}" + (f": {detail}" if detail else "")
    return units, desc


# --------------------------------------------------------------------------- registry wrapper
def ensure_registered(name: str, group: str, camera: str = "any", requires_ecg: bool = False,
                      requires_raw: bool = False, registry: FeatureRegistry = REGISTRY,
                      units: str | None = None, description: str | None = None) -> FeatureMeta:
    """Register a column once (idempotent). An existing entry is accepted when it is at least as
    restrictive as the one requested; a less restrictive existing entry would let a forbidden column
    through a track guard and raises TrackViolation instead of being silently overwritten.

    Units and description default to empty so the entry equals the minimal form other builders use
    (`REGISTRY.add(name, group=..., camera=..., requires_raw=...)`); the data dictionary derives units and
    description from the name (`describe_column`) when the registry entry leaves them empty."""
    existing = registry.get(name)
    if existing is not None:
        if (requires_ecg and not existing.requires_ecg) or (requires_raw and not existing.requires_raw):
            raise TrackViolation(
                f"column {name} is already registered as requires_ecg={existing.requires_ecg}, "
                f"requires_raw={existing.requires_raw} but the feature store needs requires_ecg={requires_ecg}, "
                f"requires_raw={requires_raw}"
            )
        return existing
    return registry.add(name, group, camera=camera, requires_ecg=bool(requires_ecg), requires_raw=bool(requires_raw),
                        units=units or "", description=description or "")
