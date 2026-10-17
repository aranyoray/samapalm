"""Multiplicity handling (protocol section 10): a fixed-sequence hierarchy for the primary and key secondary
endpoints, read from the signed frozen config (``multiplicity.hierarchy``); everything else is reported with
``n_tests_run`` annotated and no adjustment.

Fixed-sequence testing: endpoints are tested in the frozen order at the full alpha; testing stops at the first
endpoint that is not rejected and every later endpoint is reported as "not tested (sequence stopped)".
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from palmppg.core.config import ConfigError, verify_frozen

EXPLORATORY_FAMILY = "exploratory (n_tests_run annotated, no adjustment)"


def load_hierarchy(frozen_path: str | Path | None = None) -> tuple[list[str], float]:
    """Hierarchy and alpha from the verified frozen config: ``multiplicity.hierarchy`` and
    ``multiplicity.alpha`` (falls back to ``equity.one_sided_alpha`` when no multiplicity alpha is frozen)."""
    data = verify_frozen(frozen_path)
    mult = data.get("multiplicity") or {}
    hier = mult.get("hierarchy")
    if not hier:
        raise ConfigError("frozen config has no multiplicity.hierarchy")
    alpha = mult.get("alpha", (data.get("equity") or {}).get("one_sided_alpha"))
    if alpha is None:
        raise ConfigError("frozen config has no multiplicity.alpha or equity.one_sided_alpha")
    return [str(h) for h in hier], float(alpha)


def fixed_sequence(p_values: Mapping[str, float], hierarchy: Sequence[str], alpha: float) -> pd.DataFrame:
    """Fixed-sequence test of ``hierarchy`` at level ``alpha``. Returns endpoint, order, p, alpha, tested,
    rejected, note. A missing or non-finite p stops the sequence (it cannot be rejected)."""
    if not (0 < alpha < 1):
        raise ValueError("alpha must be in (0, 1)")
    rows = []
    stopped = False
    for i, name in enumerate(hierarchy):
        p = p_values.get(name)
        p = float("nan") if p is None else float(p)
        if stopped:
            rows.append({"endpoint": name, "order": i + 1, "p": p, "alpha": alpha, "tested": False, "rejected": False,
                         "note": "not tested (sequence stopped)"})
            continue
        if not np.isfinite(p):
            stopped = True
            rows.append({"endpoint": name, "order": i + 1, "p": p, "alpha": alpha, "tested": True, "rejected": False,
                         "note": "p-value missing; sequence stops"})
            continue
        rej = p < alpha
        rows.append({"endpoint": name, "order": i + 1, "p": p, "alpha": alpha, "tested": True, "rejected": bool(rej),
                     "note": "rejected" if rej else "not rejected; sequence stops"})
        if not rej:
            stopped = True
    extra = [k for k in p_values if k not in hierarchy]
    for k in extra:
        rows.append({"endpoint": k, "order": None, "p": float(p_values[k]), "alpha": alpha, "tested": False,
                     "rejected": False, "note": "not in the frozen hierarchy; report under exploratory"})
    return pd.DataFrame(rows)


def annotate_exploratory(results: pd.DataFrame | Mapping[str, Any], n_tests_run: int | None = None) -> pd.DataFrame:
    """Add ``n_tests_run`` and ``family`` columns to a table of exploratory results (one row per test). When
    ``n_tests_run`` is None it is the number of rows."""
    table = results.copy() if isinstance(results, pd.DataFrame) else pd.DataFrame(
        [{"endpoint": k, "p": v} for k, v in dict(results).items()])
    n = int(len(table) if n_tests_run is None else n_tests_run)
    table["n_tests_run"] = n
    table["family"] = EXPLORATORY_FAMILY
    return table


def multiplicity_report(hierarchy_p: Mapping[str, float], exploratory_p: Mapping[str, float] | pd.DataFrame | None = None,
                        frozen_path: str | Path | None = None) -> dict[str, pd.DataFrame]:
    """Both tables from the frozen hierarchy: ``hierarchy`` (fixed sequence) and ``exploratory`` (annotated)."""
    hier, alpha = load_hierarchy(frozen_path)
    out = {"hierarchy": fixed_sequence(hierarchy_p, hier, alpha)}
    if exploratory_p is not None:
        out["exploratory"] = annotate_exploratory(exploratory_p)
    return out
