"""STARD 2015 participant flow for the pilot (protocol section 0, item 5).

The flow is built from counts the pipeline measured; nothing is assumed. Each node carries n and the reasons for
exclusion so the diagram can be regenerated from `qc_table.parquet` and the feature store with one command.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd


@dataclass
class FlowCounts:
    enrolled: int
    crf_valid: int
    clips_captured: int
    reshoots: int
    clips_valid_pi: int
    clips_valid_phone: int
    sync_fine: int
    sync_coarse: int
    sync_none: int
    ecg_readable: int
    ecg_digitised: int
    analysed_bp: int
    analysed_rhythm: int
    abstained_bp: int
    exclusion_reasons: dict = field(default_factory=dict)


def counts_from_tables(qc: pd.DataFrame, features: pd.DataFrame, crf: pd.DataFrame, clinician: pd.DataFrame) -> FlowCounts:
    """Derive the STARD counts from the pipeline tables (one row per clip per camera in qc)."""
    pi = qc[qc["camera"] == "pi"]
    ph = qc[qc["camera"] == "phone"]
    reasons: dict[str, int] = {}
    for rs in pi.get("reasons", pd.Series([], dtype=object)).dropna():
        for r in (rs if isinstance(rs, (list, tuple)) else [rs]):
            reasons[r] = reasons.get(r, 0) + 1
    first_pi = pi[pi["clip_id"] == "clip1"] if "clip_id" in pi else pi
    return FlowCounts(
        enrolled=int(crf["study_id"].nunique()),
        crf_valid=int(crf.get("crf_valid", pd.Series([True] * len(crf))).sum()),
        clips_captured=int(pi["study_id"].nunique()),
        reshoots=int((pi["clip_id"] == "clip1b").sum()) if "clip_id" in pi else 0,
        clips_valid_pi=int(first_pi["valid_clip"].fillna(False).sum()),
        clips_valid_phone=int(ph["valid_clip"].fillna(False).sum()) if len(ph) else 0,
        sync_fine=int((first_pi["sync_grade"] == "fine").sum()),
        sync_coarse=int((first_pi["sync_grade"] == "coarse").sum()),
        sync_none=int((first_pi["sync_grade"] == "none").sum()),
        ecg_readable=int((clinician["rhythm"] != "unreadable").sum()) if "rhythm" in clinician else 0,
        ecg_digitised=int(features.get("ecg__ecg_digitised", pd.Series([False] * len(features))).fillna(False).sum()),
        analysed_bp=int(features.get("bp_pred_available", pd.Series([False] * len(features))).fillna(False).sum()),
        analysed_rhythm=int(features.get("rhythm_pred_available", pd.Series([False] * len(features))).fillna(False).sum()),
        abstained_bp=int(features.get("bp_abstained", pd.Series([False] * len(features))).fillna(False).sum()),
        exclusion_reasons=reasons,
    )


def stard_markdown(c: FlowCounts, title: str = "STARD flow (pilot)") -> str:
    lines = [f"# {title}", "", "```mermaid", "flowchart TD",
             f'  A["Enrolled, CRF complete: n={c.enrolled} (valid CRF {c.crf_valid})"]',
             f'  B["Palm clip captured: n={c.clips_captured} (re-shoots {c.reshoots})"]',
             f'  C["Valid Pi clip: n={c.clips_valid_pi}<br/>Valid phone clip: n={c.clips_valid_phone}"]',
             f'  D["Sync grade fine {c.sync_fine} / coarse {c.sync_coarse} / none {c.sync_none}"]',
             f'  E["ECG readable: n={c.ecg_readable} (digitised from PDF {c.ecg_digitised})"]',
             f'  F["BP analysed: n={c.analysed_bp}; abstained {c.abstained_bp} (counted as failures)"]',
             f'  G["Rhythm analysed: n={c.analysed_rhythm}"]',
             "  A --> B --> C --> D --> E", "  E --> F", "  E --> G", "```", "",
             "## Exclusion reasons (Pi, first clip)", "", "| reason | n |", "|---|---|"]
    for k, v in sorted(c.exclusion_reasons.items(), key=lambda kv: -kv[1]):
        lines.append(f"| {k} | {v} |")
    if not c.exclusion_reasons:
        lines.append("| none recorded | 0 |")
    lines += ["", "Failed and abstained readings are failures in every coverage figure."]
    return "\n".join(lines) + "\n"


def write_stard(c: FlowCounts, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stard_markdown(c), encoding="utf-8")
    return path
