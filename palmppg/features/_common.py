"""Internal helpers shared by the feature-store modules (protocol section 6.7, CONTRACTS section 5).

JSON flattening with "__", numeric coercion with booleans kept (label keys and CRF strata stay verbatim),
nullable dtype harmonisation for parquet, the registry wrapper that registers every column once with the
units and description the data dictionary needs, and the column-name parser behind both.
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
# A list of scalars longer than this is a per-beat or per-window series, not a clip-level feature: only
# the `<key>__n` count is kept for it.
LIST_MAX_ITEMS = 16
ID_COLUMNS: tuple[str, ...] = ("study_id", "clip_id", "camera", "stream", "source_study_id")
# Keys inside per-clip JSON files that duplicate the row identifiers or the registry flags and are
# therefore not flattened into feature columns.
JSON_META_KEYS: frozenset[str] = frozenset({"study_id", "clip_id", "camera", "requires_ecg", "requires_raw"})
# Last name parts whose string values are labels: a numeric-looking label ("007", "1.10") is never a number.
LABEL_KEYS: frozenset[str] = frozenset({
    "landmark_source", "sync_grade", "grade", "colour_space", "best", "method", "export_format", "source_file",
    "start_time", "app_rhythm_label", "clinician_rhythm", "rhythm", "detectors", "reasons", "ecg_map_method",
    "capture_mode", "model", "adverse_event", "reader_id", "read_date",
})
# CRF covariates (palmppg.core.crf.covariate_columns) by kind. Everything not listed is a label kept
# verbatim: operator "007", unit_id "02", app_ver "1.10" and cuff_size "12" are section 7 strata and E11
# nuisance variables, so they are never turned into numbers.
NUMERIC_COVARIATES: frozenset[str] = frozenset({
    "age", "bmi", "mst_band", "hb_gdl", "hba1c", "bp_target_sbp", "bp_target_dbp", "bp_target_23_sbp",
    "bp_target_23_dbp", "hr_cuff_mean", "spo2", "glucose_mgdl", "last_meal_h",
})
BOOL_COVARIATES: frozenset[str] = frozenset({
    "pregnant", "flag_hypertension", "flag_diabetes", "flag_chronic_kidney_disease", "flag_arrhythmia",
    "flag_anaemia_thalassaemia", "bracket_flag", "irregular_pulse",
})
LIST_COVARIATES: frozenset[str] = frozenset({"flags", "acute_30m"})
_TRUE_STRINGS = frozenset({"true", "yes", "y", "t", "1"})
_FALSE_STRINGS = frozenset({"false", "no", "n", "f", "0"})

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
    """Numeric coercion with booleans kept (CONTRACTS section 0.11), for producer-JSON values.

    bool stays bool; ints and floats become float; numeric-looking strings become float; the strings
    "true"/"false" become bool; empty strings and NaN become None; every other string is kept verbatim.
    Label keys (`LABEL_KEYS`) and CRF covariates go through `coerce_value` / `coerce_covariate` instead.
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


def coerce_label(v: Any) -> str | None:
    """A label value kept verbatim: None for null or empty, otherwise the stripped text. A number written
    in the JSON becomes its shortest text ("7" for 7 or 7.0) so an id typed as a number and one typed as
    text agree; nothing is ever parsed as a number."""
    if is_null(v):
        return None
    if isinstance(v, (bool, np.bool_)):
        return str(bool(v))
    if isinstance(v, numbers.Integral):
        return str(int(v))
    if isinstance(v, numbers.Real):
        f = float(v)
        return str(int(f)) if f.is_integer() else repr(f)
    if isinstance(v, (bytes, bytearray)):
        v = v.decode("utf-8", errors="replace")
    s = str(v).strip()
    return s or None


def coerce_bool(v: Any) -> bool | None:
    """A boolean covariate: bool kept; 0/1 numbers and the strings yes/no, true/false, y/n, t/f, 1/0
    (any case) mapped; anything else is missing (CONTRACTS 0.11: booleans are real booleans, never
    sentinel strings)."""
    if is_null(v):
        return None
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, numbers.Real):
        f = float(v)
        return True if f == 1.0 else (False if f == 0.0 else None)
    if isinstance(v, str):
        s = v.strip().lower()
        if s in _TRUE_STRINGS:
            return True
        if s in _FALSE_STRINGS:
            return False
    return None


def coerce_number(v: Any) -> float | None:
    """A numeric covariate: numbers and numeric-looking strings become float; anything else is missing."""
    if is_null(v) or isinstance(v, (bool, np.bool_)):
        return None
    if isinstance(v, numbers.Real):
        return float(v)
    if isinstance(v, str) and _NUMERIC_RE.match(v.strip()):
        return float(v.strip())
    return None


def coerce_value(name: str, v: Any) -> Any:
    """Producer-JSON coercion chosen by the column name: a label key keeps its text, everything else goes
    through `coerce_scalar`."""
    if name.rsplit(SEP, 1)[-1] in LABEL_KEYS:
        return coerce_label(v)
    return coerce_scalar(v)


def coerce_covariate(name: str, v: Any) -> Any:
    """CRF covariate coercion by kind: `BOOL_COVARIATES` -> bool, `NUMERIC_COVARIATES` -> float,
    `LIST_COVARIATES` -> ";"-joined labels, everything else a label kept verbatim."""
    if name in BOOL_COVARIATES:
        return coerce_bool(v)
    if name in NUMERIC_COVARIATES:
        return coerce_number(v)
    if isinstance(v, (list, tuple, np.ndarray)):
        items = [x for x in (coerce_label(i) for i in v) if x is not None]
        return LIST_JOIN.join(items) if items else None
    return coerce_label(v)


def flatten(obj: Any, prefix: str = "", skip: Iterable[str] = (), sep: str = SEP) -> dict[str, Any]:
    """Flatten nested mappings into {key__subkey: scalar}.

    Lists of scalars collapse to one ";"-joined string column plus a `<key>__n` count column (an empty
    list gives None and 0; a list longer than `LIST_MAX_ITEMS` gives the count only); lists of mappings
    are expanded by index. Keys in `skip` are dropped at any depth. Values are returned un-coerced;
    callers apply `coerce_value`.
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
                if not items:
                    out[key] = None
                elif len(items) <= LIST_MAX_ITEMS:
                    out[key] = LIST_JOIN.join(str(coerce_scalar(x)) for x in items)
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
def _kind(v: Any) -> str:
    if isinstance(v, (bool, np.bool_)):
        return "b"
    if isinstance(v, numbers.Real):
        return "n"
    if isinstance(v, str) and v.strip().lower() in _TRUE_STRINGS | _FALSE_STRINGS:
        return "bs"
    return "s"


def _harmonise_series(s: pd.Series) -> pd.Series:
    if str(s.dtype) == "boolean":
        return s
    if pd.api.types.is_bool_dtype(s.dtype):
        return s.astype("boolean")
    if pd.api.types.is_numeric_dtype(s.dtype):
        return pd.to_numeric(s, errors="coerce").astype("float64")
    present = s[~s.isna()]
    if present.empty:
        return pd.Series(np.nan, index=s.index, dtype="float64")
    kinds = set(present.map(_kind).unique())
    if kinds == {"n"}:
        return pd.to_numeric(s, errors="coerce").astype("float64")
    if "b" in kinds and kinds <= {"b", "bs"}:
        # real booleans mixed with yes/no text from another CRF: one boolean column, never sentinel strings
        return pd.array([coerce_bool(v) for v in s.tolist()], dtype="boolean")
    return pd.Series([None if is_null(v) else str(v) for v in s.tolist()], dtype=object, index=s.index)


def harmonise_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """Give every column a nullable dtype that survives parquet: boolean, float64 or object strings.

    A column whose non-null values are all bool (or bool mixed with yes/no text) becomes pandas
    "boolean"; all-numeric becomes float64; all-null becomes float64 NaN; anything else is kept as object
    with None for missing values.
    """
    out = df.copy()
    for c in out.columns:
        out[c] = _harmonise_series(out[c])
    return out


def record_to_frame(record: Mapping[str, Any]) -> pd.DataFrame:
    """One-row DataFrame from a flat record with harmonised nullable dtypes."""
    return harmonise_dtypes(pd.DataFrame({k: [v] for k, v in record.items()}))


def records_to_frame(records: Iterable[Mapping[str, Any]]) -> pd.DataFrame:
    """One DataFrame from many flat records (columns in first-seen order), harmonised once per column."""
    recs = list(records)
    if not recs:
        return pd.DataFrame()
    return harmonise_dtypes(pd.DataFrame.from_records(recs))


# --------------------------------------------------------------------------- column naming
GROUP_DESCRIPTIONS: dict[str, str] = {
    "id": "row identifier",
    "covariate": "clinical covariate or derived stratum from the CRF (protocol 3.1, 7)",
    "qc": "ingest quality-control flag or measurement (protocol 6.1)",
    "sync": "synchronisation field from the clip sync report (protocol 4.4)",
    "static_colour": "static colour feature from the first seconds of the clip (protocol 6.2)",
    "pulse": "pulse extraction summary per method and ROI (protocol 6.3)",
    "hrv": "heart-rate variability from palm beats (protocol 6.5)",
    "morphology": "beat morphology, per-beat ensemble (protocol 6.5)",
    "apg": "acceleration plethysmogram wave feature (protocol 6.5)",
    "perfusion": "perfusion index per ROI and channel (protocol 6.5)",
    "resp": "respiratory modulation proxy (protocol 6.5)",
    "beats": "beat-level clip aggregate (protocol 6.5)",
    "embedding": "learned embedding component from a video or pulse model (protocol 6.3, 9)",
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
    (r"^method$", "label", "method name"),
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
    (r"^linearised_from_srgb$", "bool", "values were inverted from sRGB (CONTRACTS 0.4), not truly linear"),
    (r"^grade$", "label", "sync grade: fine | coarse | none"),
    (r"^ecg_map_method$", "label", "clock-map method that placed the ECG on the reference clock"),
    (r"^ecg_uncertainty_s$", "s", "stated uncertainty of the ECG clock map"),
    (r"^xcorr_peak$", "r", "normalised cross-correlation peak of ECG versus pulse rate series"),
    (r"^(R|G|B)_mean$", "a.u.", "window-mean channel value in the stated colour space"),
    (r"^(rg|bg)$", "ratio", "chromaticity ratio"),
    (r"^melanin_proxy$", "a.u.", "log(R) - log(B); a camera-space proxy, not a melanin measurement"),
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
    (r"(_frac|_fraction|_ratio|_index|_idx|_variance)$", "ratio", "dimensionless ratio or index"),
    (r"(_flag|_found|_ok|_detected|_agree|_allowed|^is_|_valid|^valid_|_used$|_present)", "bool", "boolean flag"),
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
    "operator": ("label", "operator id, kept verbatim"),
    "unit_id": ("label", "capture unit id, kept verbatim"),
    "stream": ("label", "data stream: pilot | development | model_selection | test"),
    "app_ver": ("label", "onboarding app version, kept verbatim"),
    "cuff_size": ("label", "cuff size used, kept verbatim"),
    "time_of_day": ("label", "morning | afternoon on the local clock (protocol 7)"),
    "lux_band": ("label", "ambient lux band <200 | 200-400 | >400 (protocol 7)"),
    "bp_tertile": ("label", "reference SBP tertile with cut points from the development set or the training fold (D-015)"),
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
    """Register a column once (idempotent). An existing entry is accepted as it stands when it is at least
    as restrictive as the one requested (the producer of a column owns its track flags, DECISIONS D-013);
    a less restrictive existing entry would let a forbidden column through a track guard and raises
    TrackViolation instead of being silently overwritten.

    Units and description default to `describe_column(name)` so the data dictionary is complete whichever
    module registers first; the registry keeps the richer text when the producer registers later."""
    existing = registry.get(name)
    if existing is not None:
        if (requires_ecg and not existing.requires_ecg) or (requires_raw and not existing.requires_raw):
            raise TrackViolation(
                f"column {name} is already registered as requires_ecg={existing.requires_ecg}, "
                f"requires_raw={existing.requires_raw} but the feature store needs requires_ecg={requires_ecg}, "
                f"requires_raw={requires_raw}"
            )
        return existing
    if units is None or description is None:
        u, d = describe_column(name)
        units = u if units is None else units
        description = d if description is None else description
    return registry.add(name, group, camera=camera, requires_ecg=bool(requires_ecg), requires_raw=bool(requires_raw),
                        units=units, description=description)
