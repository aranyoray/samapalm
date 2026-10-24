"""Recruitment targets and the live priority of a candidate (onboarding v2 design section 3).

`configs/recruitment_targets.json` holds groups of cells; each cell key is a strata key produced by the CRF engine
(`strata` for the enrol part, `scan_strata` for the scan part, palmppg/core/crf_schema.py). The Kotlin port
`org.samahealth.crf.Strata` must give identical results; configs/crf_fixtures/strata_golden.json pins both.

Priority for a candidate with strata keys K and counts n (missing counts are 0):
    deficit = max(0, 1 - n[key] / target), contribution = group weight * deficit for every cell whose key is in K;
    score = the largest contribution (0 when none); level none (no cell matched), met (every deficit 0), high,
    medium (score >= levels.high / levels.medium) or low; reasons = matched cells by contribution desc then key asc,
    the first 3, contribution rounded to 3 decimals.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

TARGETS_PATH = Path(__file__).resolve().parents[2] / "configs" / "recruitment_targets.json"
MAX_REASONS = 3


class TargetsError(ValueError):
    pass


def _is_num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def validate_targets(t: Mapping) -> list[str]:
    """Problems in a targets document (empty when usable)."""
    problems: list[str] = []
    levels = t.get("levels")
    if not isinstance(levels, Mapping) or not all(_is_num(levels.get(k)) for k in ("high", "medium")):
        problems.append("levels must give numbers for high and medium")
    elif not 0 <= levels["medium"] <= levels["high"] <= 1:
        problems.append("levels must satisfy 0 <= medium <= high <= 1")
    groups = t.get("groups")
    if not isinstance(groups, list) or not groups:
        return problems + ["groups must be a non-empty list"]
    keys: set[str] = set()
    ids: set[str] = set()
    for i, g in enumerate(groups):
        gid = g.get("id") if isinstance(g, Mapping) else None
        where = f"group {gid or i}"
        if not isinstance(gid, str) or not gid:
            problems.append(f"{where}: id missing")
        elif gid in ids:
            problems.append(f"{where}: duplicate group id")
        ids.add(gid)
        if not isinstance(g, Mapping):
            continue
        w = g.get("weight")
        if not _is_num(w) or not 0 <= w <= 1:
            problems.append(f"{where}: weight must be a number in [0, 1], got {w!r}")
        cells = g.get("cells")
        if not isinstance(cells, list) or not cells:
            problems.append(f"{where}: cells must be a non-empty list")
            continue
        for c in cells:
            key = c.get("key") if isinstance(c, Mapping) else None
            if not isinstance(key, str) or not key:
                problems.append(f"{where}: cell without a key")
                continue
            if key in keys:
                problems.append(f"{where}: duplicate cell key {key}")
            keys.add(key)
            tg = c.get("target")
            if not isinstance(tg, int) or isinstance(tg, bool) or tg <= 0:
                problems.append(f"{where}: cell {key}: target must be a whole number > 0, got {tg!r}")
    return problems


def load_targets(path: str | Path | None = None) -> dict:
    """Read and validate the targets file; raises TargetsError listing every problem."""
    p = Path(path or TARGETS_PATH)
    t = json.loads(p.read_text(encoding="utf-8"))
    problems = validate_targets(t)
    if problems:
        raise TargetsError(f"{p}: " + "; ".join(problems))
    return t


def _cells(targets: Mapping) -> Iterable[tuple[Mapping, Mapping]]:
    for g in targets["groups"]:
        for c in g["cells"]:
            yield g, c


def _row(g: Mapping, c: Mapping, counts: Mapping[str, int]) -> dict:
    n = int(counts.get(c["key"], 0) or 0)
    deficit = max(0.0, 1.0 - n / c["target"])
    return {"key": c["key"], "label": c.get("label", c["key"]), "group": g["id"], "n": n, "target": c["target"],
            "deficit": deficit, "contribution": float(g["weight"]) * deficit}


def _reason(r: Mapping) -> dict:
    return {"key": r["key"], "label": r["label"], "group": r["group"], "n": r["n"], "target": r["target"],
            "contribution": round(r["contribution"], 3)}


def _ranked(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda r: (-r["contribution"], r["key"]))


def priority(keys: Iterable[str], counts: Mapping[str, int], targets: Mapping) -> dict:
    """{score, level, reasons[{key, label, group, n, target, contribution}]} for a candidate's strata keys."""
    ks = set(keys or [])
    rows = [_row(g, c, counts) for g, c in _cells(targets) if c["key"] in ks]
    if not rows:
        return {"score": 0.0, "level": "none", "reasons": []}
    score = max(r["contribution"] for r in rows)
    lv = targets["levels"]
    if all(r["deficit"] == 0 for r in rows):
        level = "met"
    elif score >= lv["high"]:
        level = "high"
    elif score >= lv["medium"]:
        level = "medium"
    else:
        level = "low"
    return {"score": score, "level": level, "reasons": [_reason(r) for r in _ranked(rows)[:MAX_REASONS]]}


def cell_table(counts: Mapping[str, int], targets: Mapping) -> list[dict]:
    """Dashboard rows in file order: group, key, label, n, target, fill = min(1, n / target)."""
    out = []
    for g, c in _cells(targets):
        n = int(counts.get(c["key"], 0) or 0)
        out.append({"group": g["id"], "key": c["key"], "label": c.get("label", c["key"]), "n": n, "target": c["target"],
                    "fill": min(1.0, n / c["target"])})
    return out


def most_needed(counts: Mapping[str, int], targets: Mapping, k: int = 5) -> list[dict]:
    """The k cells a new participant would help most (weighted deficit desc, then key); full and weight-0 cells
    are left out. Same row shape as `priority` reasons."""
    rows = [r for r in (_row(g, c, counts) for g, c in _cells(targets)) if r["contribution"] > 0]
    return [_reason(r) for r in _ranked(rows)[:k]]
