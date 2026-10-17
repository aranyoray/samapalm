"""SHA-256 manifests for data integrity (offload, ingest and experiment provenance)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def sha256_file(path: str | Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def build_manifest(root: str | Path, patterns: tuple[str, ...] = ("**/*",)) -> dict[str, dict]:
    root = Path(root)
    out: dict[str, dict] = {}
    for pat in patterns:
        for p in sorted(root.glob(pat)):
            if p.is_file() and p.name != "MANIFEST.sha256.json":
                out[p.relative_to(root).as_posix()] = {"sha256": sha256_file(p), "bytes": p.stat().st_size}
    return out


def write_manifest(root: str | Path, name: str = "MANIFEST.sha256.json") -> Path:
    root = Path(root)
    m = build_manifest(root)
    path = root / name
    path.write_text(json.dumps(m, indent=1, sort_keys=True), encoding="utf-8")
    return path


def verify_manifest(root: str | Path, name: str = "MANIFEST.sha256.json") -> dict[str, str]:
    """Return {relpath: 'ok'|'missing'|'changed'} for each manifest entry."""
    root = Path(root)
    m = json.loads((root / name).read_text(encoding="utf-8"))
    status = {}
    for rel, info in m.items():
        p = root / rel
        if not p.exists():
            status[rel] = "missing"
        elif sha256_file(p) != info["sha256"]:
            status[rel] = "changed"
        else:
            status[rel] = "ok"
    return status
