"""Data manifests: one sha256 row per raw study file (protocol sections 11.6 "data hashed" and 12 data/).

`data_manifest` walks a `StudyLayout` (participants, units, clock log), hashing with
`palmppg.core.hashing.sha256_file`; `write_manifest` stores it as data/manifests/<date>.parquet and
`verify_manifest` reports ok / changed / missing / new per path.
"""
from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from pathlib import Path

import pandas as pd

from palmppg.core.config import REPO_ROOT
from palmppg.core.hashing import sha256_file
from palmppg.core.paths import StudyLayout

MANIFESTS_DIR = REPO_ROOT / "data" / "manifests"
MANIFEST_COLUMNS = ["study_id", "part", "path", "sha256", "bytes", "mtime"]
PARTICIPANT_PARTS = ("pi", "phone", "ecg")
SKIP_NAMES = {"MANIFEST.sha256.json", "ACCESS_LOG.jsonl", ".DS_Store"}


def _part_of(rel_in_participant: Path) -> str:
    top = rel_in_participant.parts[0]
    if len(rel_in_participant.parts) > 1:
        return top if top in PARTICIPANT_PARTS else f"other/{top}"
    return rel_in_participant.stem  # crf.json -> crf, clinician.json -> clinician


def _row(root: Path, p: Path, study_id: str | None, part: str) -> dict:
    st = p.stat()
    return {"study_id": study_id, "part": part, "path": p.relative_to(root).as_posix(),
            "sha256": sha256_file(p), "bytes": int(st.st_size), "mtime": float(st.st_mtime)}


def data_manifest(study_layout: StudyLayout, include_units: bool = True, include_clock_log: bool = True,
                  parts: Iterable[str] | None = None) -> pd.DataFrame:
    """Hash every file of a study tree. Columns: study_id (None for unit and root files), part
    (crf | clinician | pi | phone | ecg | units | clock_sync_log | other/<dir>), path (posix, relative to the
    study root), sha256, bytes, mtime (epoch seconds, audit only). Sorted by (study_id, part, path)."""
    root = Path(study_layout.root)
    want = set(parts) if parts is not None else None
    rows: list[dict] = []
    for part_paths in study_layout.participants():
        for p in sorted(part_paths.root.rglob("*")):
            if not p.is_file() or p.name in SKIP_NAMES:
                continue
            part = _part_of(p.relative_to(part_paths.root))
            if want is not None and part not in want:
                continue
            rows.append(_row(root, p, part_paths.study_id, part))
    if include_units and study_layout.units_dir.exists() and (want is None or "units" in want):
        for unit_dir in sorted(x for x in study_layout.units_dir.iterdir() if x.is_dir()):
            for p in sorted(unit_dir.rglob("*")):
                if p.is_file() and p.name not in SKIP_NAMES:
                    rows.append(_row(root, p, None, "units"))
    if include_clock_log and study_layout.clock_sync_log.exists() and (want is None or "clock_sync_log" in want):
        rows.append(_row(root, study_layout.clock_sync_log, None, "clock_sync_log"))
    df = pd.DataFrame(rows, columns=MANIFEST_COLUMNS)
    df["study_id"] = df["study_id"].astype(object).where(df["study_id"].notna(), None)
    return df.sort_values(["part", "path"], kind="stable").sort_values("study_id", kind="stable", na_position="last").reset_index(drop=True)


def manifest_path(date: str | dt.date | None = None, manifests_dir: str | Path | None = None) -> Path:
    d = date if isinstance(date, str) else (date or dt.date.today()).isoformat()
    return Path(manifests_dir or MANIFESTS_DIR) / f"{d}.parquet"


def write_manifest(df: pd.DataFrame, date: str | dt.date | None = None, manifests_dir: str | Path | None = None) -> Path:
    """Write the manifest to data/manifests/<date>.parquet (date defaults to today, ISO format)."""
    path = manifest_path(date, manifests_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    df[MANIFEST_COLUMNS].to_parquet(path, index=False)
    return path


def read_manifest(path: str | Path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    missing = [c for c in MANIFEST_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"{path}: manifest lacks columns {missing}")
    return df


def verify_manifest(study_layout: StudyLayout, manifest: pd.DataFrame | str | Path, check_new: bool = True) -> pd.DataFrame:
    """Re-hash the tree and compare: one row per path with status ok | changed | missing | new
    (new = on disk but absent from the manifest, only when `check_new`)."""
    m = read_manifest(manifest) if not isinstance(manifest, pd.DataFrame) else manifest
    root = Path(study_layout.root)
    rows = []
    for rec in m[MANIFEST_COLUMNS].to_dict("records"):
        p = root / rec["path"]
        if not p.exists():
            status = "missing"
        elif sha256_file(p) != rec["sha256"]:
            status = "changed"
        else:
            status = "ok"
        rows.append({"study_id": rec["study_id"], "part": rec["part"], "path": rec["path"], "status": status})
    if check_new:
        known = set(m["path"].astype(str))
        current = data_manifest(study_layout)
        for rec in current.to_dict("records"):
            if rec["path"] not in known:
                rows.append({"study_id": rec["study_id"], "part": rec["part"], "path": rec["path"], "status": "new"})
    return pd.DataFrame(rows, columns=["study_id", "part", "path", "status"])


def manifest_summary(status: pd.DataFrame) -> dict[str, int]:
    """Counts per status, always listing all four statuses."""
    counts = status["status"].value_counts().to_dict() if len(status) else {}
    return {k: int(counts.get(k, 0)) for k in ("ok", "changed", "missing", "new")}


def assert_manifest_ok(study_layout: StudyLayout, manifest: pd.DataFrame | str | Path, allow_new: bool = False) -> dict[str, int]:
    """Raise RuntimeError when any manifest entry changed or went missing (or is new, unless allowed)."""
    status = verify_manifest(study_layout, manifest, check_new=not allow_new)
    summary = manifest_summary(status)
    bad = summary["changed"] + summary["missing"] + (0 if allow_new else summary["new"])
    if bad:
        examples = status[status["status"] != "ok"]["path"].head(10).tolist()
        raise RuntimeError(f"manifest check failed: {summary}; e.g. {examples}")
    return summary
