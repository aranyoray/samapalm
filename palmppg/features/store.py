"""Per-clip feature rows (protocol section 6.7): one row per clip per camera joining every derived
artefact under work/<study_id>/<clip_id>/ (CONTRACTS section 4) with the clinical covariates.

Every column is registered with `palmppg.core.tracks.REGISTRY` before it is emitted (CONTRACTS section 5).
The producer of a column owns its track flags (DECISIONS D-013): the store registers a producer's column
only when it emits it and the producer has not registered it yet, with the producer's flags (ECG-derived,
PAT and clinician columns `requires_ecg=True`; every camera-specific `pi` column `requires_raw=True`,
since the Pi path is raw Bayer by construction and `pi_proxy` is the product-side view of Pi data, D-006).
`feature_columns(df, track)` is the only way a model should select inputs from a table.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

import pandas as pd

from palmppg.core.config import Config, load_pipeline_config
from palmppg.core.crf import covariate_columns
from palmppg.core.tracks import CAMERAS, REGISTRY, FeatureRegistry, TrackViolation

from ._common import (
    ID_COLUMNS,
    JSON_META_KEYS,
    SEP,
    coerce_covariate,
    coerce_label,
    coerce_value,
    ensure_registered,
    flatten,
    is_null,
    load_json,
    parse_column,
    record_to_frame,
)
from .covariates import covariate_settings, derived_strata
from .isolation import check_no_target_leakage

# qc.json keys (CONTRACTS section 4.1); list-valued keys also get a `__n` count column.
QC_KEYS: tuple[str, ...] = (
    "n_frames", "duration_s", "fs_median", "drop_pct", "drop_flag", "saturation_frac", "saturation_flag",
    "flicker_peaks_hz", "flicker_flag", "lighting_drift_pct", "lighting_drift_flag", "vignetting_residual_pct",
    "vignetting_flag", "hand_detected", "hand_is_left", "hand_palmar", "landmark_source", "landmark_jitter_px",
    "motion_flag", "eis_warp_px", "eis_flag", "sync_grade", "sqi_best", "sqi_flag", "valid_clip", "reasons",
)
QC_LIST_KEYS: tuple[str, ...] = ("flicker_peaks_hz", "reasons")
# The sync columns the store emits and their `requires_ecg` flag, equal to the producer's registration
# (palmppg.ingest.sync; DECISIONS D-013): a `fine` grade needs the ECG artefact anchor, so the grade itself
# is ECG-derived. All are group "sync", camera "any", requires_raw False.
SYNC_FIELD_META: dict[str, bool] = {
    "grade": True, "p1_found": False, "p2_found": False,
    "ecg_map_method": True, "ecg_uncertainty_s": True, "xcorr_peak": True,
}
SYNC_FIELDS: tuple[str, ...] = tuple(SYNC_FIELD_META)
CLINICIAN_FIELDS: tuple[str, ...] = ("rhythm", "ecg_hr", "lead12_obtained", "adverse_event")
# Derived strata that are not CRF fields (protocol section 7).
DERIVED_STRATA: tuple[str, ...] = ("time_of_day", "lux_band", "bp_tertile", "capture_mode", "sync_grade",
                                   "rhythm_class", "ecg_digitised")
STRATA_REQUIRING_ECG: frozenset[str] = frozenset({"rhythm_class", "ecg_digitised"})
BEAT_GROUPS: tuple[str, ...] = ("hrv", "morphology", "apg", "perfusion", "resp")
ECG_GROUPS: frozenset[str] = frozenset({"ecg", "pat", "clinician"})
PULSE_STATS: tuple[str, ...] = ("hr_bpm", "sqi", "snr_db")
# Producer metadata that is not a feature: nested copies, window bounds, free-text definitions, run notes.
STATIC_COLOUR_META_KEYS: frozenset[str] = frozenset({"rois", "features", "t_window", "melanin_proxy_definition", "definitions"})
PULSE_META_KEYS: frozenset[str] = frozenset({"ssr_input", "definitions"})
ECG_META_KEYS: frozenset[str] = frozenset({"problems", "export_format_meta"})
# Embedding parquet columns: a full CONTRACTS section 5 name (palmppg.models writes
# embedding__<camera>__<roi>__<method>__d<i>) or a short dimension name e<k>, emb<k>, dim<k>, z<k>, d<k>.
EMBEDDING_FULL_RE = re.compile(rf"^embedding{SEP}(?P<camera>[a-z_]+){SEP}.+$")
EMBEDDING_SHORT_RE = re.compile(r"^(?:e|emb|dim|z|d)_?(\d+)$", re.IGNORECASE)

_REGISTERED_CFG_HASHES: set[str] = set()


# --------------------------------------------------------------------------- registration
def column_meta(name: str, camera: str | None = None) -> dict[str, Any]:
    """Registry metadata implied by a column name (and the camera the row belongs to), matching the
    producers' conventions: ecg/pat/clinician groups and the ECG-dependent sync fields are
    `requires_ecg`; every camera-specific `pi` column is `requires_raw`; camera-free names are covariates."""
    info = parse_column(name)
    group = info["group"]
    cam = info["camera"] or camera
    if name in ID_COLUMNS:
        return {"group": "id", "camera": "any", "requires_ecg": False, "requires_raw": False}
    if group in ECG_GROUPS:
        req_ecg = True
    elif group == "sync":
        req_ecg = SYNC_FIELD_META.get(info["rest"], False)
    else:
        req_ecg = name in STRATA_REQUIRING_ECG
    camera_specific = info["camera"] is not None
    req_raw = camera_specific and info["camera"] == "pi"
    reg_group = group if camera_specific or group in ("sync", "ecg", "clinician") else "covariate"
    return {"group": reg_group, "camera": cam if camera_specific else "any",
            "requires_ecg": bool(req_ecg), "requires_raw": bool(req_raw)}


def register_column(name: str, registry: FeatureRegistry = REGISTRY, camera: str | None = None) -> None:
    m = column_meta(name, camera)
    ensure_registered(name, m["group"], camera=m["camera"], requires_ecg=m["requires_ecg"],
                      requires_raw=m["requires_raw"], registry=registry)


def register_features(cfg: Config | None = None, registry: FeatureRegistry = REGISTRY) -> int:
    """Register the columns the feature store itself owns (idempotent): the identifiers, the CRF covariates,
    the derived strata and the clinician__* fields. Producer-owned columns (qc__, sync__, static_colour__,
    pulse__, the beat groups, pat__, ecg__, embedding__) belong to the modules that compute them; the store
    registers such a column only when it emits it and the producer has not registered it yet, with the
    producer's track flags (CONTRACTS section 5, DECISIONS D-013), so the registry lists only columns that
    exist in a table. Returns the registry size."""
    cfg = cfg if cfg is not None else load_pipeline_config()
    for c in ID_COLUMNS:
        register_column(c, registry)
    for c in covariate_columns():
        if c not in ID_COLUMNS:
            ensure_registered(c, "covariate", registry=registry)
    for c in DERIVED_STRATA:
        ensure_registered(c, "covariate", requires_ecg=c in STRATA_REQUIRING_ECG, registry=registry)
    for f in CLINICIAN_FIELDS:
        register_column(f"clinician{SEP}{f}", registry)
    _REGISTERED_CFG_HASHES.add(f"{id(registry)}:{cfg.sha256()}")
    return len(registry.table())


# --------------------------------------------------------------------------- per-file readers
def _put(rec: dict, name: str, value: Any, registry: FeatureRegistry, camera: str | None) -> None:
    register_column(name, registry, camera)
    rec[name] = coerce_value(name, value)


def _add_prefixed(rec: dict, prefix: str, flat: Mapping[str, Any] | None, registry: FeatureRegistry, camera: str | None) -> None:
    if not flat:
        return
    for k, v in flat.items():
        _put(rec, f"{prefix}{SEP}{k}" if k else prefix, v, registry, camera)


def _check_camera(data: Mapping, camera: str, what: str) -> None:
    cam = data.get("camera")
    if cam is not None and str(cam) != camera:
        raise ValueError(f"{what} says camera {cam!r} but sits in the {camera!r} directory")


def _add_static_colour(rec: dict, camera: str, data: Mapping | None, registry: FeatureRegistry) -> None:
    """static_colour.json in the producer's shape (palmppg.spatial.static_colour): `features` already holds
    the registered `static_colour__<camera>__<roi>__<name>` and `static_colour__<camera>__<name>` columns
    and is taken verbatim; without it, `rois.<roi>.<name>` and the top-level scalars are mapped to those
    names. `colour_space` and `linearised_from_srgb` are kept; `t_window`, the free-text definition and the
    nested copies are not features."""
    if not data:
        return
    _check_camera(data, camera, "static_colour.json")
    prefix = f"static_colour{SEP}{camera}"
    feats = data.get("features")
    if isinstance(feats, Mapping):
        for name, v in feats.items():
            if not str(name).startswith(prefix + SEP):
                raise ValueError(f"static_colour.json feature {name!r} does not belong to camera {camera!r}")
            _put(rec, str(name), v, registry, camera)
    elif isinstance(data.get("rois"), Mapping):
        for roi, vals in data["rois"].items():
            if isinstance(vals, Mapping):
                for name, v in vals.items():
                    if not isinstance(v, (Mapping, list, tuple)):
                        _put(rec, f"{prefix}{SEP}{roi}{SEP}{name}", v, registry, camera)
    for k, v in data.items():
        if k in JSON_META_KEYS or k in STATIC_COLOUR_META_KEYS:
            continue
        if isinstance(v, (Mapping, list, tuple)):
            for kk, vv in flatten({k: v}, skip=JSON_META_KEYS).items():
                if f"{prefix}{SEP}{kk}" not in rec:
                    _put(rec, f"{prefix}{SEP}{kk}", vv, registry, camera)
        elif f"{prefix}{SEP}{k}" not in rec:
            _put(rec, f"{prefix}{SEP}{k}", v, registry, camera)


def _add_pulse_sqi(rec: dict, camera: str, data: Mapping | None, registry: FeatureRegistry) -> None:
    """pulse_sqi.json in the producer's shape (palmppg.pulse.run): {"<method>__<roi>": {sqi, snr_db, hr_bpm}
    | null, "best": "<method>__<roi>", "fused": {sqi, snr_db, hr_bpm, method}, plus camera/requires_raw/
    ssr_input/study_id/clip_id metadata} -> pulse__<camera>__<roi>__<method>__<stat> (a null entry gives
    null stats under the same names), pulse__<camera>__best, pulse__<camera>__fused__<stat> and the best
    entry's stats copied to pulse__<camera>__best__<stat>. `<method>__fused` entries are the per-method
    multi-ROI fusion (roi "fused")."""
    if not data:
        return
    _check_camera(data, camera, "pulse_sqi.json")
    base = f"pulse{SEP}{camera}"
    best = data.get("best")
    for key, val in data.items():
        if key in JSON_META_KEYS or key in PULSE_META_KEYS:
            continue
        if key == "best":
            _put(rec, f"{base}{SEP}best", val, registry, camera)
        elif key == "fused":
            if isinstance(val, Mapping):
                _add_prefixed(rec, f"{base}{SEP}fused", flatten(val, skip=JSON_META_KEYS), registry, camera)
        elif SEP in key:
            method, roi = key.split(SEP, 1)
            prefix = f"{base}{SEP}{roi}{SEP}{method}"
            if isinstance(val, Mapping):
                _add_prefixed(rec, prefix, flatten(val, skip=JSON_META_KEYS), registry, camera)
            else:
                for stat in PULSE_STATS:
                    _put(rec, f"{prefix}{SEP}{stat}", None, registry, camera)
        elif isinstance(val, (Mapping, list, tuple)):
            _add_prefixed(rec, base, flatten({key: val}, skip=JSON_META_KEYS), registry, camera)
        else:
            _put(rec, f"{base}{SEP}{key}", val, registry, camera)
    if isinstance(best, str) and isinstance(data.get(best), Mapping):
        _add_prefixed(rec, f"{base}{SEP}best", flatten(data[best], skip=JSON_META_KEYS), registry, camera)


def _strip_top(key: str, flat: Mapping[str, Any]) -> dict[str, Any]:
    """Drop the leading `key__` of flattened keys; a bare scalar under `key` maps to no suffix."""
    out: dict[str, Any] = {}
    for k, v in flat.items():
        if k.startswith(key + SEP):
            out[k[len(key) + len(SEP):]] = v
        else:
            out[""] = v
    return out


def _add_beat_features(rec: dict, camera: str, data: Mapping | None, registry: FeatureRegistry) -> None:
    """beat_features.json top-level keys hrv/morphology/apg/perfusion/resp become the column group;
    any other top-level key goes under the `beats` group."""
    if not data:
        return
    _check_camera(data, camera, "beat_features.json")
    for key, val in data.items():
        if key in JSON_META_KEYS:
            continue
        prefix = f"{key}{SEP}{camera}" if key in BEAT_GROUPS else f"beats{SEP}{camera}{SEP}{key}"
        _add_prefixed(rec, prefix, _strip_top(key, flatten({key: val}, skip=JSON_META_KEYS)), registry, camera)


def _embedding_name(path: Path) -> str:
    stem = path.stem
    for pre in ("embeddings__", "embedding__", "embeddings_", "embedding_", "embeddings", "embedding"):
        if stem.startswith(pre):
            stem = stem[len(pre):]
            break
    return stem.strip("_") or "model"


def embedding_columns(columns: Iterable[Any], camera: str, model: str) -> dict[str, Any]:
    """{feature column: parquet column} for the embedding columns of a parquet: full
    `embedding__<camera>__...` names are taken verbatim (another camera's name raises), short dimension
    names e<k>/emb<k>/dim<k>/z<k>/d<k> become `embedding__<camera>__<model>__<k>` with k parsed from the
    name, never from the column position. Bookkeeping columns (t_ref_s, frame_idx, window_idx, model, ...)
    are not embeddings and are left out."""
    found: dict[str, Any] = {}
    for col in columns:
        name = str(col)
        m_full = EMBEDDING_FULL_RE.match(name)
        if m_full:
            if m_full.group("camera") != camera:
                raise ValueError(f"embedding column {name!r} belongs to camera {m_full.group('camera')!r}, not {camera!r}")
            found[name] = col
            continue
        m = EMBEDDING_SHORT_RE.match(name)
        if m:
            found[f"embedding{SEP}{camera}{SEP}{model}{SEP}{int(m.group(1))}"] = col
    return found


def _add_embeddings(rec: dict, camera: str, cam_dir: Path, registry: FeatureRegistry) -> None:
    """<camera>/embedding*.parquet -> clip-level embedding columns (`embedding_columns`), averaging the
    rows (one per window or segment). `<model>` comes from a `model` column or the file stem. A parquet
    with no embedding column raises ValueError: that is a producer-shape error, not missing data."""
    for path in sorted(cam_dir.glob("embedding*.parquet")):
        df = pd.read_parquet(path)
        model = _embedding_name(path)
        if "model" in df.columns and len(df) and not is_null(df["model"].iloc[0]):
            model = str(df["model"].iloc[0])
        found = embedding_columns(df.columns, camera, model)
        if not found:
            raise ValueError(f"{path}: no embedding column (embedding__{camera}__... or e<k>/emb<k>/dim<k>/z<k>/d<k>) "
                             f"among {list(map(str, df.columns))[:10]}")
        for full in sorted(found, key=_embedding_sort_key):
            vals = pd.to_numeric(df[found[full]], errors="coerce")
            _put(rec, full, float(vals.mean()) if vals.notna().any() else None, registry, camera)


def _embedding_sort_key(name: str) -> tuple:
    head, _, last = name.rpartition(SEP)
    m = re.search(r"(\d+)$", last)
    return (head, int(m.group(1)) if m else -1, last)


def _dig(d: Any, keys: Sequence[str]) -> Any:
    for k in keys:
        if not isinstance(d, Mapping) or d.get(k) is None:
            return None
        d = d[k]
    return d


def _sync_fields(sync_report: Mapping | None, timeline: Mapping | None) -> dict[str, Any]:
    """The six sync columns from sync.json (the palmppg.ingest.sync report: `grade`, `grade_detail.p1_found`
    / `p2_found`, `offsets.ecg.method` / `uncertainty_s`, `ecg.xcorr.peak`), falling back to timeline.json
    (`Timeline.to_dict()`: `sync_grade`, `sync_detail`, `maps.ecg`) for a clip without a sync report; the
    cross-correlation peak exists only in the sync report. All None without either file."""
    out: dict[str, Any] = {f"sync{SEP}{f}": None for f in SYNC_FIELDS}
    rep = sync_report if isinstance(sync_report, Mapping) else {}
    tl = timeline if isinstance(timeline, Mapping) else {}
    if not rep and not tl:
        return out
    detail = rep.get("grade_detail") if isinstance(rep.get("grade_detail"), Mapping) else (tl.get("sync_detail") or {})
    out[f"sync{SEP}grade"] = rep.get("grade") if rep.get("grade") is not None else tl.get("sync_grade")
    out[f"sync{SEP}p1_found"] = detail.get("p1_found")
    out[f"sync{SEP}p2_found"] = detail.get("p2_found")
    ecg_map = _dig(rep, ("offsets", "ecg"))
    if ecg_map is None:
        for stream, m in (tl.get("maps") or {}).items():
            if "ecg" in str(stream).lower() or "kardia" in str(stream).lower():
                ecg_map = m
                break
    method = (ecg_map or {}).get("method") or detail.get("ecg_map_method")
    out[f"sync{SEP}ecg_map_method"] = method
    out[f"sync{SEP}ecg_uncertainty_s"] = (ecg_map or {}).get("uncertainty_s")
    out[f"sync{SEP}xcorr_peak"] = _dig(rep, ("ecg", "xcorr", "peak"))
    return out


def _clip_meta(work_clip_dir: Path, camera: str, clip_meta: Mapping | None) -> dict:
    """start_wall_ns / lux / capture_mode for the derived strata: explicit `clip_meta` first, then
    <camera>/meta.json, then clip_meta.json beside the timeline."""
    merged: dict = {}
    for p in (work_clip_dir / "clip_meta.json", work_clip_dir / camera / "meta.json"):
        d = load_json(p)
        if d:
            merged.update(d)
    if clip_meta:
        merged.update(dict(clip_meta))
    return merged


# --------------------------------------------------------------------------- the row
def clip_feature_record(study_id: str, clip_id: str, camera: str, work_clip_dir: str | Path, crf_derived: Mapping,
                        clinician: Mapping | None, cfg: Config, clip_meta: Mapping | None = None,
                        registry: FeatureRegistry = REGISTRY) -> dict[str, Any]:
    """The feature row of `build_clip_features` as a flat dict (every column registered), for callers that
    assemble many rows into one table without a DataFrame per row."""
    if camera not in CAMERAS:
        raise ValueError(f"camera must be one of {CAMERAS}, got {camera!r}")
    if f"{id(registry)}:{cfg.sha256()}" not in _REGISTERED_CFG_HASHES:
        register_features(cfg, registry)
    clip_dir = Path(work_clip_dir)
    cam_dir = clip_dir / camera
    rec: dict[str, Any] = {"study_id": str(study_id), "clip_id": str(clip_id), "camera": camera,
                           "stream": coerce_label(crf_derived.get("stream"))}
    for c in covariate_columns():
        if c not in ID_COLUMNS:
            rec[c] = coerce_covariate(c, crf_derived.get(c))
    rec["source_study_id"] = coerce_label(crf_derived.get("source_study_id"))

    qc = load_json(cam_dir / "qc.json")
    if qc:
        _check_camera(qc, camera, "qc.json")
        _add_prefixed(rec, f"qc{SEP}{camera}", flatten(qc, skip=JSON_META_KEYS), registry, camera)
    sync_report = load_json(clip_dir / "sync.json")
    timeline = load_json(clip_dir / "timeline.json")
    for name, v in _sync_fields(sync_report, timeline).items():
        _put(rec, name, v, registry, None)
    _add_static_colour(rec, camera, load_json(cam_dir / "static_colour.json"), registry)
    _add_pulse_sqi(rec, camera, load_json(cam_dir / "pulse_sqi.json"), registry)
    _add_beat_features(rec, camera, load_json(cam_dir / "beat_features.json"), registry)
    pat = load_json(cam_dir / "pat.json")
    if pat:
        _add_prefixed(rec, f"pat{SEP}{camera}", flatten(pat, skip=JSON_META_KEYS), registry, camera)
    ecg = load_json(clip_dir / "ecg" / "ecg_features.json")
    if ecg:
        _add_prefixed(rec, "ecg", flatten(ecg, skip=JSON_META_KEYS | ECG_META_KEYS), registry, None)
    _add_embeddings(rec, camera, cam_dir, registry)
    clin = dict(clinician or {})
    for f in CLINICIAN_FIELDS:
        _put(rec, f"clinician{SEP}{f}", clin.get(f), registry, None)

    meta = _clip_meta(clip_dir, camera, clip_meta)
    settings = covariate_settings(cfg)
    start = meta.get("start_wall_ns")
    if is_null(start):
        bp2 = crf_derived.get("bp2")
        start = bp2.get("wall_ts") if isinstance(bp2, Mapping) else None
    lux = meta.get("lux")
    if is_null(lux) and qc:
        for k in ("lux", "lux_median", "lux_mean"):
            if not is_null(qc.get(k)):
                lux = qc.get(k)
                break
    strata = derived_strata(start, lux, settings)
    rec["time_of_day"] = strata["time_of_day"]
    rec["lux_band"] = strata["lux_band"]
    rec["bp_tertile"] = None
    cap = (sync_report or {}).get("capture_mode") or (timeline or {}).get("capture_mode") or meta.get("capture_mode")
    rec["capture_mode"] = coerce_label(cap)
    grade = rec.get(f"sync{SEP}grade")
    if is_null(grade) and qc:
        grade = qc.get("sync_grade")
    rec["sync_grade"] = coerce_label(grade)
    rec["rhythm_class"] = coerce_label(clin.get("rhythm"))
    rec["ecg_digitised"] = coerce_value("ecg_digitised", ecg.get("ecg_digitised")) if ecg else None
    for c in DERIVED_STRATA:
        register_column(c, registry)
    return rec


def build_clip_features(study_id: str, clip_id: str, camera: str, work_clip_dir: str | Path, crf_derived: Mapping,
                        clinician: Mapping | None, cfg: Config, clip_meta: Mapping | None = None,
                        registry: FeatureRegistry = REGISTRY) -> pd.DataFrame:
    """One feature row for (study_id, clip_id, camera) from the derived artefacts under `work_clip_dir`
    (protocol 6.7; CONTRACTS section 4). Every input file is optional and every column nullable:
    <camera>/qc.json -> qc__<camera>__*; sync.json (timeline.json as fallback) -> sync__*;
    <camera>/static_colour.json -> static_colour__<camera>__*; <camera>/pulse_sqi.json ->
    pulse__<camera>__<roi>__<method>__*; <camera>/beat_features.json -> hrv|morphology|apg|perfusion|resp__
    <camera>__*; <camera>/pat.json -> pat__<camera>__* (requires_ecg); ecg/ecg_features.json -> ecg__*
    (requires_ecg); <camera>/embedding*.parquet -> embedding__<camera>__*; clinician.json -> clinician__*
    (requires_ecg); CRF covariates from `palmppg.core.crf.covariate_columns()` (labels kept verbatim,
    numbers as float, booleans as bool); plus study_id, clip_id, camera, stream and the derived strata
    time_of_day, lux_band, capture_mode, sync_grade, rhythm_class, ecg_digitised (bp_tertile is filled
    table-wide by the integrator from development or training-fold cut points, D-015).
    Nested JSON keys are flattened with "__"; numbers are coerced to float, booleans kept, short lists
    joined with ";" plus a `__n` count. `clip_meta` may give start_wall_ns, lux and capture_mode.
    """
    return record_to_frame(clip_feature_record(study_id, clip_id, camera, work_clip_dir, crf_derived, clinician, cfg,
                                               clip_meta=clip_meta, registry=registry))


def write_clip_features(df: pd.DataFrame, work_clip_dir: str | Path, camera: str) -> Path:
    """Write the per-clip, per-camera table work/<study_id>/<clip_id>/features_<camera>.parquet
    (CONTRACTS section 4, protocol 6.7: one parquet per clip per camera)."""
    clip_dir = Path(work_clip_dir)
    clip_dir.mkdir(parents=True, exist_ok=True)
    path = clip_dir / f"features_{camera}.parquet"
    df.to_parquet(path, index=False)
    return path


# --------------------------------------------------------------------------- selection
def feature_columns(df: pd.DataFrame, track: str, registry: FeatureRegistry = REGISTRY,
                    groups: Iterable[str] | None = None, cameras: Iterable[str] | None = None,
                    exclude_targets: bool = True, explicit_targets: Iterable[str] = (), strict: bool = True,
                    numeric_only: bool = False) -> list[str]:
    """Columns of `df` a model in `track` may use (protocol 9, 11.5), in table order.

    Identifier columns are never returned; unregistered columns raise TrackViolation when `strict`
    (the registry is the single source of truth, CONTRACTS section 5) and are skipped otherwise;
    columns the registry forbids in the track (requires_ecg / requires_raw for product_candidate) are
    dropped; `cameras` (e.g. `cfg.get("tracks.product_candidate.cameras")`) drops camera-specific
    columns of other cameras; `groups` keeps only those registry groups; `exclude_targets` drops
    reference quantities (cuff BP, rhythm, cuff/ECG HR) unless listed in `explicit_targets`;
    `numeric_only` drops label (object-dtype) columns such as `pulse__<camera>__best` or `dept`, keeping
    numbers and booleans, for estimators that do not encode categoricals themselves.
    """
    gs = set(groups) if groups is not None else None
    cams = set(cameras) if cameras is not None else None
    unknown, out = [], []
    for c in df.columns:
        name = str(c)
        if name in ID_COLUMNS:
            continue
        m = registry.get(name)
        if m is None:
            unknown.append(name)
            continue
        if not m.allowed_in(track):
            continue
        if cams is not None and m.camera != "any" and m.camera not in cams:
            continue
        if gs is not None and m.group not in gs:
            continue
        if numeric_only and not (pd.api.types.is_numeric_dtype(df[c].dtype) or pd.api.types.is_bool_dtype(df[c].dtype)
                                 or str(df[c].dtype) == "boolean"):
            continue
        out.append(name)
    if unknown and strict:
        raise TrackViolation(f"{len(unknown)} unregistered column(s) in the table: {unknown[:10]}")
    if exclude_targets:
        flagged = set(check_no_target_leakage(out, explicit_targets))
        out = [c for c in out if c not in flagged]
    return out


def id_columns(df: pd.DataFrame) -> list[str]:
    """The identifier columns present in `df`, in canonical order."""
    return [c for c in ID_COLUMNS if c in df.columns]
