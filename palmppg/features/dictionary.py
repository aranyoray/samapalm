"""Data dictionary (protocol section 12, reports/data_dictionary.md; CONTRACTS section 5).

Every registered feature column with its group, camera, track flags, units and description, as a
markdown table. The integrator writes the result to reports/data_dictionary.md after every builder has
populated `palmppg.core.tracks.REGISTRY`.
"""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pandas as pd

from palmppg.core.tracks import REGISTRY, FeatureRegistry

from ._common import describe_column

DICTIONARY_COLUMNS = ["name", "group", "camera", "requires_ecg", "requires_raw", "units", "description"]


def data_dictionary_frame(registry: FeatureRegistry = REGISTRY, extra: Mapping[str, Mapping] | None = None) -> pd.DataFrame:
    """One row per registered column (plus `extra` entries: {name: {field: value}} to add unregistered
    columns such as fold ids, or to override units/description), sorted by group then name."""
    rows: dict[str, dict] = {}
    table = registry.table()
    if len(table):
        for rec in table.to_dict("records"):
            units, desc = rec.get("units") or "", rec.get("description") or ""
            if not units or not desc:
                u, d = describe_column(rec["name"])
                units, desc = units or u, desc or d
            rows[rec["name"]] = {"name": rec["name"], "group": rec["group"], "camera": rec["camera"],
                                 "requires_ecg": bool(rec["requires_ecg"]), "requires_raw": bool(rec["requires_raw"]),
                                 "units": units, "description": desc}
    for name, fields in (extra or {}).items():
        base = rows.get(name)
        if base is None:
            u, d = describe_column(name)
            base = {"name": name, "group": "extra", "camera": "any", "requires_ecg": False, "requires_raw": False,
                    "units": u, "description": d}
        base.update({k: v for k, v in dict(fields).items() if k in DICTIONARY_COLUMNS and k != "name"})
        rows[name] = base
    df = pd.DataFrame(list(rows.values()), columns=DICTIONARY_COLUMNS)
    return df.sort_values(["group", "name"], kind="stable").reset_index(drop=True)


def _cell(v) -> str:
    if isinstance(v, bool):
        return "yes" if v else "no"
    return str(v).replace("|", "\\|").replace("\n", " ")


def data_dictionary_markdown(registry: FeatureRegistry = REGISTRY, extra: Mapping[str, Mapping] | None = None,
                             title: str = "Data dictionary") -> str:
    """Markdown document: a header with per-group counts and the track rule, then the column table."""
    df = data_dictionary_frame(registry, extra)
    intro = ("Column naming follows `group__camera__roi__method__name` (CONTRACTS section 5). Columns with "
             "`requires_ecg` or `requires_raw` are science-track only and never enter a product_candidate "
             "model (protocol sections 6.6, 9, 11.5).")
    lines = [f"# {title}", "", intro, ""]
    if len(df):
        counts = df.groupby("group").size().sort_index()
        lines.append(f"{len(df)} columns in {len(counts)} groups: " + ", ".join(f"{g} ({n})" for g, n in counts.items()) + ".")
        lines.append(f"{int(df['requires_ecg'].sum())} require ECG; {int(df['requires_raw'].sum())} require raw Bayer.")
        lines.append("")
    lines.append("| " + " | ".join(DICTIONARY_COLUMNS) + " |")
    lines.append("|" + "|".join(["---"] * len(DICTIONARY_COLUMNS)) + "|")
    for rec in df.to_dict("records"):
        lines.append("| " + " | ".join(_cell(rec[c]) for c in DICTIONARY_COLUMNS) + " |")
    return "\n".join(lines) + "\n"


def write_data_dictionary(path: str | Path, registry: FeatureRegistry = REGISTRY,
                          extra: Mapping[str, Mapping] | None = None) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(data_dictionary_markdown(registry, extra), encoding="utf-8")
    return p
