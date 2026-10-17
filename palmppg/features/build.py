"""Feature-store tables (protocol section 6.7; DECISIONS D-011): one parquet per stream under
work/tables/, never mixing streams, plus qc_table.parquet across clips and cameras.

The locked prospective test stream is never built by `build_feature_store`; it is built only by
`build_test_stream_features`, which goes through `TestStreamGuard.open()` (separate mount, access log,
read once) and writes to its own directory so no glob over work/tables can pick it up.
"""
from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pandas as pd

from palmppg.core.config import Config
from palmppg.core.crf import derive_file
from palmppg.core.paths import StudyLayout, TestStreamGuard, WorkLayout
from palmppg.core.tracks import CAMERAS, REGISTRY, FeatureRegistry

from ._common import JSON_META_KEYS, coerce_scalar, flatten, harmonise_dtypes, load_json
from .isolation import TEST_STREAM, StreamIsolationError, assert_stream_isolated
from .store import build_clip_features, register_features

DEFAULT_STREAMS: tuple[str, ...] = ("pilot", "development", "model_selection")
TEST_TABLES_SUBDIR = "tables_test_stream"
_NON_CLIP_DIRS = {"tables", "reports", "synthetic", TEST_TABLES_SUBDIR}


# --------------------------------------------------------------------------- discovery
def clip_dirs(work_root: str | Path, study_id: str, fallback_clip_ids: Iterable[str] = ()) -> list[tuple[str, Path]]:
    """(clip_id, work/<study_id>/<clip_id>) for every clip directory in the work tree, plus any clip id
    known from the study layout (so a clip with no derived artefacts still yields an all-null row)."""
    base = Path(work_root) / study_id
    found: dict[str, Path] = {}
    if base.exists():
        for p in sorted(base.iterdir()):
            if p.is_dir() and p.name.startswith("clip"):
                found[p.name] = p
    for cid in fallback_clip_ids:
        found.setdefault(cid, base / cid)
    return sorted(found.items())


def _pi_meta(part, clip_id: str) -> dict:
    p = part.pi_meta(clip_id)
    d = load_json(p) if p.exists() else None
    return {k: d.get(k) for k in ("start_wall_ns", "lux", "capture_mode") if d and k in d} if d else {}


def _camera_expected(part, clip_id: str, clip_dir: Path, camera: str) -> bool:
    """A (clip, camera) row exists when derived artefacts exist for that camera, or when the raw source
    exists in the study tree (so a clip whose processing failed still yields an all-null row and counts
    as a failure in coverage, protocol 11.3). pi_proxy rows exist only once the proxy chain ran."""
    if (clip_dir / camera).exists():
        return True
    if camera == "pi":
        return part.pi_meta(clip_id).exists()
    if camera == "phone":
        return part.phone_meta(clip_id).exists()
    return False


def _qc_row(study_id: str, clip_id: str, camera: str, stream: str, clip_dir: Path) -> dict | None:
    qc = load_json(clip_dir / camera / "qc.json")
    if qc is None:
        return None
    row: dict[str, Any] = {"study_id": study_id, "clip_id": clip_id, "camera": camera, "stream": stream}
    for k, v in flatten(qc, skip=JSON_META_KEYS).items():
        row[k] = coerce_scalar(v)
    tl = load_json(clip_dir / "timeline.json")
    if tl and tl.get("sync_grade"):
        row["sync_grade"] = tl["sync_grade"]
    return row


def collect_rows(layout: StudyLayout, work_root: str | Path, cfg: Config, cameras: Iterable[str] = CAMERAS,
                 streams: Iterable[str] = DEFAULT_STREAMS, registry: FeatureRegistry = REGISTRY) -> dict:
    """Walk every participant of `layout`, derive the CRF, and build one feature row per clip per camera
    whose stream is in `streams`. Returns {"rows": {stream: [DataFrame]}, "qc_rows": [dict],
    "skipped": {stream_or_reason: n}}. Participants without a crf.json are skipped and counted."""
    register_features(cfg, registry)
    wanted = set(streams)
    cams = [c for c in cameras if c in CAMERAS]
    rows: dict[str, list[pd.DataFrame]] = {s: [] for s in streams}
    qc_rows: list[dict] = []
    skipped: dict[str, int] = {}
    crf_cfg = cfg.section("crf")
    for part in layout.participants():
        if not part.crf.exists():
            skipped["no_crf"] = skipped.get("no_crf", 0) + 1
            continue
        crf = derive_file(part.crf, crf_cfg)
        stream = crf.get("stream")
        if stream not in wanted:
            key = str(stream) if stream is not None else "no_stream"
            skipped[key] = skipped.get(key, 0) + 1
            continue
        clinician = load_json(part.clinician) if part.clinician.exists() else None
        for clip_id, clip_dir in clip_dirs(work_root, part.study_id, part.clip_ids()):
            meta = _pi_meta(part, clip_id)
            for camera in cams:
                if not _camera_expected(part, clip_id, clip_dir, camera):
                    continue
                df = build_clip_features(part.study_id, clip_id, camera, clip_dir, crf, clinician, cfg,
                                         clip_meta=meta, registry=registry)
                rows[stream].append(df)
                qc = _qc_row(part.study_id, clip_id, camera, stream, clip_dir)
                if qc is not None:
                    qc_rows.append(qc)
    return {"rows": rows, "qc_rows": qc_rows, "skipped": skipped}


def concat_rows(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Row-bind one-row frames, keeping identifiers first and nullable dtypes consistent."""
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True, sort=False)
    df = harmonise_dtypes(df)
    first = [c for c in ("study_id", "clip_id", "camera", "stream") if c in df.columns]
    rest = [c for c in df.columns if c not in first]
    return df[first + rest].sort_values(first, kind="stable").reset_index(drop=True)


# --------------------------------------------------------------------------- builders
def write_qc_table(qc_rows: list[dict], tables_dir: Path, name: str = "qc_table.parquet") -> Path | None:
    """qc_table.parquet: one row per clip per camera with every QC flag, the sync grade and the stream."""
    if not qc_rows:
        return None
    df = harmonise_dtypes(pd.DataFrame(qc_rows))
    first = [c for c in ("study_id", "clip_id", "camera", "stream", "sync_grade", "valid_clip") if c in df.columns]
    df = df[first + [c for c in df.columns if c not in first]].sort_values(first[:3], kind="stable").reset_index(drop=True)
    path = tables_dir / name
    df.to_parquet(path, index=False)
    return path


def build_feature_store(work_root: str | Path, study_layout: StudyLayout, cfg: Config,
                        cameras: Iterable[str] = CAMERAS, streams: Iterable[str] = DEFAULT_STREAMS,
                        registry: FeatureRegistry = REGISTRY) -> dict:
    """Write work/tables/features_<stream>.parquet for each stream in `streams` (one table per stream,
    streams never mixed, protocol 6.7) and work/tables/qc_table.parquet. The test stream is refused here:
    use `build_test_stream_features`. Returns {"tables": {stream: Path}, "qc_table": Path | None,
    "n_rows": {stream: n}, "skipped": {label: n}, "manifest": Path}."""
    streams = tuple(streams)
    if TEST_STREAM in streams:
        raise StreamIsolationError("the test stream is built only through build_test_stream_features (D-011)")
    work = WorkLayout(work_root)
    collected = collect_rows(study_layout, work.root, cfg, cameras, streams, registry)
    tables: dict[str, Path] = {}
    n_rows: dict[str, int] = {}
    for stream in streams:
        frames = collected["rows"].get(stream, [])
        if not frames:
            n_rows[stream] = 0
            continue
        df = concat_rows(frames)
        assert_stream_isolated(df, expected_stream=stream)
        path = work.tables / f"features_{stream}.parquet"
        df.to_parquet(path, index=False)
        tables[stream] = path
        n_rows[stream] = len(df)
    qc_path = write_qc_table(collected["qc_rows"], work.tables)
    manifest = {"streams": list(streams), "tables": {k: str(v) for k, v in tables.items()},
                "qc_table": str(qc_path) if qc_path else None, "n_rows": n_rows, "skipped": collected["skipped"],
                "cameras": list(cameras), "config_sha256": cfg.sha256()}
    mpath = work.tables / "feature_store_manifest.json"
    mpath.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return {"tables": tables, "qc_table": qc_path, "n_rows": n_rows, "skipped": collected["skipped"], "manifest": mpath}


def build_test_stream_features(guard: TestStreamGuard, work_root: str | Path, cfg: Config, reason: str, operator: str,
                               frozen_config_sha: str, cameras: Iterable[str] = CAMERAS,
                               out_dir: str | Path | None = None, registry: FeatureRegistry = REGISTRY) -> dict:
    """Build features_test.parquet for the locked prospective test stream (protocol 11.1, D-011).

    Goes through `guard.open()` (access log, read-once), accepts only participants whose CRF stream is
    "test" (anything else on the test mount is a data-entry error and raises), and writes to
    `out_dir` or work/<TEST_TABLES_SUBDIR>/, never to work/tables/. Returns {"table": Path, "qc_table":
    Path | None, "n_rows": int, "skipped": {...}}.
    """
    layout = guard.open(reason=reason, operator=operator, frozen_config_sha=frozen_config_sha)
    work_root = Path(work_root)
    collected = collect_rows(layout, work_root, cfg, cameras, (TEST_STREAM,), registry)
    foreign = {k: v for k, v in collected["skipped"].items() if k not in ("no_crf",)}
    if foreign:
        raise StreamIsolationError(f"non-test participants on the test mount: {foreign}")
    frames = collected["rows"].get(TEST_STREAM, [])
    tables_dir = Path(out_dir) if out_dir else work_root / TEST_TABLES_SUBDIR
    tables_dir.mkdir(parents=True, exist_ok=True)
    if not frames:
        return {"table": None, "qc_table": None, "n_rows": 0, "skipped": collected["skipped"]}
    df = concat_rows(frames)
    assert_stream_isolated(df, expected_stream=TEST_STREAM, allow_test=True)
    path = tables_dir / f"features_{TEST_STREAM}.parquet"
    df.to_parquet(path, index=False)
    qc_path = write_qc_table(collected["qc_rows"], tables_dir, name=f"qc_table_{TEST_STREAM}.parquet")
    return {"table": path, "qc_table": qc_path, "n_rows": len(df), "skipped": collected["skipped"]}


def read_feature_table(path: str | Path, expected_stream: str | None = None, allow_test: bool = False) -> pd.DataFrame:
    """Read a feature table and check stream isolation before returning it."""
    df = pd.read_parquet(path)
    assert_stream_isolated(df, expected_stream=expected_stream, allow_test=allow_test)
    return df


def tables_for_streams(work_root: str | Path, streams: Iterable[str]) -> dict[str, Path]:
    """Paths of the per-stream tables that exist under work/tables (never the test stream)."""
    work = WorkLayout(work_root)
    out = {}
    for s in streams:
        if s == TEST_STREAM:
            raise StreamIsolationError("test-stream table is not listed with development tables")
        p = work.tables / f"features_{s}.parquet"
        if p.exists():
            out[s] = p
    return out
