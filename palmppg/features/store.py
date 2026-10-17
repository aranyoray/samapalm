"""Per-clip feature rows (protocol section 6.7): one row per clip per camera joining every derived
artefact under work/<study_id>/<clip_id>/ (CONTRACTS section 4) with the clinical covariates.

Every column is registered with `palmppg.core.tracks.REGISTRY` before it is emitted (CONTRACTS section 5):
ECG-derived and PAT columns carry `requires_ecg=True`; every column of the `pi` camera carries
`requires_raw=True` because the Pi path is raw Bayer by construction (DECISIONS D-006 gives `pi_proxy`
as the product-side view of Pi data). `feature_columns(df, track)` is the only way a model should
select inputs from a table.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
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
    coerce_scalar,
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
SYNC_FIELDS: tuple[str, ...] = ("grade", "p1_found", "p2_found")
SYNC_ECG_FIELDS: tuple[str, ...] = ("ecg_map_method", "ecg_uncertainty_s", "xcorr_peak")
CLINICIAN_FIELDS: tuple[str, ...] = ("rhythm", "ecg_hr", "lead12_obtained", "adverse_event")
# Derived strata that are not CRF fields (protocol section 7).
DERIVED_STRATA: tuple[str, ...] = ("time_of_day", "lux_band", "bp_tertile", "capture_mode", "sync_grade",
                                   "rhythm_class", "ecg_digitised")
STRATA_REQUIRING_ECG: frozenset[str] = frozenset({"rhythm_class", "ecg_digitised"})
BEAT_GROUPS: tuple[str, ...] = ("hrv", "morphology", "apg", "perfusion", "resp")
ECG_GROUPS: frozenset[str] = frozenset({"ecg", "pat", "clinician"})

_REGISTERED_CFG_HASHES: set[str] = set()


# --------------------------------------------------------------------------- registration
def column_meta(name: str, camera: str | None = None) -> dict[str, Any]:
    """Registry metadata implied by a column name (and the camera the row belongs to)."""
    info = parse_column(name)
    group = info["group"]
    cam = info["camera"] or camera
    if name in ID_COLUMNS:
        return {"group": "id", "camera": "any", "requires_ecg": False, "requires_raw": False}
    if group in ECG_GROUPS:
        req_ecg = True
    elif group == "sync":
        req_ecg = info["rest"] in SYNC_ECG_FIELDS
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
    """Register every fixed feature-store column (idempotent): ids, CRF covariates, derived strata, sync
    fields, clinician fields and the QC keys per camera. Columns discovered in JSON files at build time
    (pulse per ROI and method, beat groups, static colour, PAT, ECG, embeddings) are registered as they are
    emitted, so the registry only ever lists columns that exist in a table. Returns the registry size."""
    cfg = cfg if cfg is not None else load_pipeline_config()
    for c in ID_COLUMNS:
        register_column(c, registry)
    for c in covariate_columns():
        if c not in ID_COLUMNS:
            ensure_registered(c, "covariate", registry=registry)
    for c in DERIVED_STRATA:
        ensure_registered(c, "covariate", requires_ecg=c in STRATA_REQUIRING_ECG, registry=registry)
    for f in SYNC_FIELDS + SYNC_ECG_FIELDS:
        register_column(f"sync{SEP}{f}", registry)
    for f in CLINICIAN_FIELDS:
        register_column(f"clinician{SEP}{f}", registry)
    for cam in CAMERAS:
        for k in QC_KEYS:
            register_column(f"qc{SEP}{cam}{SEP}{k}", registry, cam)
            if k in QC_LIST_KEYS:
                register_column(f"qc{SEP}{cam}{SEP}{k}{SEP}n", registry, cam)
    _REGISTERED_CFG_HASHES.add(f"{id(registry)}:{cfg.sha256()}")
    return len(registry.table())


# --------------------------------------------------------------------------- per-file readers
def _put(rec: dict, name: str, value: Any, registry: FeatureRegistry, camera: str | None) -> None:
    register_column(name, registry, camera)
    rec[name] = coerce_scalar(value)


def _flat_json(path: Path) -> dict[str, Any] | None:
    data = load_json(path)
    return None if data is None else flatten(data, skip=JSON_META_KEYS)


def _add_prefixed(rec: dict, prefix: str, flat: Mapping[str, Any] | None, registry: FeatureRegistry, camera: str | None) -> None:
    if not flat:
        return
    for k, v in flat.items():
        _put(rec, f"{prefix}{SEP}{k}" if k else prefix, v, registry, camera)


def _add_pulse_sqi(rec: dict, camera: str, data: Mapping | None, registry: FeatureRegistry) -> None:
    """pulse_sqi.json: {"<method>__<roi>": {sqi, snr_db, hr_bpm}, "best": "<method>__<roi>", "fused": {...}}
    -> pulse__<camera>__<roi>__<method>__<stat>, pulse__<camera>__fused__<stat>, pulse__<camera>__best and
    the best entry's stats copied to pulse__<camera>__best__<stat>."""
    if not data:
        return
    best = data.get("best")
    for key, val in data.items():
        if key in JSON_META_KEYS:
            continue
        if SEP in key and key != "fused" and isinstance(val, Mapping):
            method, roi = key.split(SEP, 1)
            prefix = f"pulse{SEP}{camera}{SEP}{roi}{SEP}{method}"
        else:
            prefix = f"pulse{SEP}{camera}{SEP}{key}"
        _add_prefixed(rec, prefix, _strip_top(key, flatten({key: val}, skip=JSON_META_KEYS)), registry, camera)
    if isinstance(best, str) and isinstance(data.get(best), Mapping):
        for stat, v in flatten(data[best], skip=JSON_META_KEYS).items():
            _put(rec, f"pulse{SEP}{camera}{SEP}best{SEP}{stat}", v, registry, camera)


def _strip_top(key: str, flat: Mapping[str, Any]) -> dict[str, Any]:
    """Drop the leading `key__` of flattened keys; the key itself (a scalar or list value) becomes
    the bare prefix, which `_add_prefixed` would turn into `<prefix>__` so it is mapped to no suffix."""
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


def _add_embeddings(rec: dict, camera: str, cam_dir: Path, registry: FeatureRegistry) -> None:
    """<camera>/embedding*.parquet -> embedding__<camera>__<model>__<k>. Numeric columns only; several
    rows (per window) are averaged to one clip-level vector; a `model` column overrides the file name."""
    for path in sorted(cam_dir.glob("embedding*.parquet")):
        df = pd.read_parquet(path)
        model = _embedding_name(path)
        if "model" in df.columns and len(df):
            first = df["model"].iloc[0]
            if not is_null(first):
                model = str(first)
        num = df.select_dtypes("number")
        if num.empty:
            continue
        means = num.mean(axis=0, skipna=True)
        for k, (col, val) in enumerate(means.items()):
            name = str(col)
            if name.startswith(f"embedding{SEP}{camera}{SEP}"):
                full = name
            else:
                m = re.fullmatch(r"[A-Za-z_]*?(\d+)", name)
                idx = int(m.group(1)) if m else k
                full = f"embedding{SEP}{camera}{SEP}{model}{SEP}{idx}"
            _put(rec, full, float(val), registry, camera)


def _sync_fields(timeline: Mapping | None) -> dict[str, Any]:
    """sync__grade, sync__p1_found, sync__p2_found, sync__ecg_map_method, sync__ecg_uncertainty_s,
    sync__xcorr_peak from timeline.json (Timeline.to_dict()); all None without a timeline."""
    out: dict[str, Any] = {f"sync{SEP}{f}": None for f in SYNC_FIELDS + SYNC_ECG_FIELDS}
    if not timeline:
        return out
    detail = timeline.get("sync_detail") or {}
    out[f"sync{SEP}grade"] = timeline.get("sync_grade")
    out[f"sync{SEP}p1_found"] = detail.get("p1_found")
    out[f"sync{SEP}p2_found"] = detail.get("p2_found")
    out[f"sync{SEP}xcorr_peak"] = detail.get("xcorr_peak")
    ecg_map = None
    for stream, m in (timeline.get("maps") or {}).items():
        if "ecg" in str(stream).lower() or "kardia" in str(stream).lower():
            ecg_map = m
            break
    method = detail.get("ecg_map_method")
    if ecg_map:
        method = method or ecg_map.get("method")
        out[f"sync{SEP}ecg_uncertainty_s"] = ecg_map.get("uncertainty_s")
    out[f"sync{SEP}ecg_map_method"] = method
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
def build_clip_features(study_id: str, clip_id: str, camera: str, work_clip_dir: str | Path, crf_derived: Mapping,
                        clinician: Mapping | None, cfg: Config, clip_meta: Mapping | None = None,
                        registry: FeatureRegistry = REGISTRY) -> pd.DataFrame:
    """One feature row for (study_id, clip_id, camera) from the derived artefacts under `work_clip_dir`
    (protocol 6.7; CONTRACTS section 4). Every input file is optional and every column nullable:
    <camera>/qc.json -> qc__<camera>__*; timeline.json -> sync__*; <camera>/static_colour.json ->
    static_colour__<camera>__*; <camera>/pulse_sqi.json -> pulse__<camera>__<roi>__<method>__*;
    <camera>/beat_features.json -> hrv|morphology|apg|perfusion|resp__<camera>__*; <camera>/pat.json ->
    pat__<camera>__* (requires_ecg); ecg/ecg_features.json -> ecg__* (requires_ecg);
    <camera>/embedding*.parquet -> embedding__<camera>__<model>__<k>; clinician.json -> clinician__*
    (requires_ecg); CRF covariates from `palmppg.core.crf.covariate_columns()`; plus study_id, clip_id,
    camera, stream and the derived strata time_of_day, lux_band, capture_mode, sync_grade, rhythm_class,
    ecg_digitised (bp_tertile is filled table-wide by the integrator from development cut points).
    Nested JSON keys are flattened with "__"; numbers are coerced to float, booleans kept, lists joined
    with ";" plus a `__n` count. `clip_meta` may give start_wall_ns, lux and capture_mode (Pi clip meta).
    """
    if camera not in CAMERAS:
        raise ValueError(f"camera must be one of {CAMERAS}, got {camera!r}")
    if f"{id(registry)}:{cfg.sha256()}" not in _REGISTERED_CFG_HASHES:
        register_features(cfg, registry)
    clip_dir = Path(work_clip_dir)
    cam_dir = clip_dir / camera
    rec: dict[str, Any] = {"study_id": str(study_id), "clip_id": str(clip_id), "camera": camera,
                           "stream": coerce_scalar(crf_derived.get("stream"))}
    for c in covariate_columns():
        if c in ID_COLUMNS:
            continue
        v = crf_derived.get(c)
        if isinstance(v, (list, tuple)):
            v = ";".join(str(coerce_scalar(x)) for x in v) if len(v) else None
        rec[c] = coerce_scalar(v)
    rec["source_study_id"] = coerce_scalar(crf_derived.get("source_study_id"))

    qc = load_json(cam_dir / "qc.json")
    _add_prefixed(rec, f"qc{SEP}{camera}", flatten(qc, skip=JSON_META_KEYS) if qc else None, registry, camera)
    timeline = load_json(clip_dir / "timeline.json")
    for name, v in _sync_fields(timeline).items():
        _put(rec, name, v, registry, None)
    _add_prefixed(rec, f"static_colour{SEP}{camera}", _flat_json(cam_dir / "static_colour.json"), registry, camera)
    _add_pulse_sqi(rec, camera, load_json(cam_dir / "pulse_sqi.json"), registry)
    _add_beat_features(rec, camera, load_json(cam_dir / "beat_features.json"), registry)
    _add_prefixed(rec, f"pat{SEP}{camera}", _flat_json(cam_dir / "pat.json"), registry, camera)
    ecg = _flat_json(clip_dir / "ecg" / "ecg_features.json")
    _add_prefixed(rec, "ecg", ecg, registry, None)
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
    cap = (timeline or {}).get("capture_mode") or meta.get("capture_mode")
    rec["capture_mode"] = coerce_scalar(cap)
    grade = rec.get(f"sync{SEP}grade")
    if is_null(grade) and qc:
        grade = qc.get("sync_grade")
    rec["sync_grade"] = coerce_scalar(grade)
    rec["rhythm_class"] = coerce_scalar(clin.get("rhythm"))
    dig = ecg.get("ecg_digitised") if ecg else None
    rec["ecg_digitised"] = coerce_scalar(dig)
    for c in DERIVED_STRATA:
        register_column(c, registry)
    return record_to_frame(rec)


# --------------------------------------------------------------------------- selection
def feature_columns(df: pd.DataFrame, track: str, registry: FeatureRegistry = REGISTRY,
                    groups: Iterable[str] | None = None, cameras: Iterable[str] | None = None,
                    exclude_targets: bool = True, explicit_targets: Iterable[str] = (), strict: bool = True) -> list[str]:
    """Columns of `df` a model in `track` may use (protocol 9, 11.5), in table order.

    Identifier columns are never returned; unregistered columns raise TrackViolation when `strict`
    (the registry is the single source of truth, CONTRACTS section 5) and are skipped otherwise;
    columns the registry forbids in the track (requires_ecg / requires_raw for product_candidate) are
    dropped; `cameras` (e.g. `cfg.get("tracks.product_candidate.cameras")`) drops camera-specific
    columns of other cameras; `groups` keeps only those registry groups; `exclude_targets` drops
    reference quantities (cuff BP, rhythm, cuff/ECG HR) unless listed in `explicit_targets`.
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
