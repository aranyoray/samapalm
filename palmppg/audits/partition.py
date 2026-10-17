"""Partition balance (protocol section 11.1 and section 7): are folds or streams balanced on the strata?

For each stratum: numeric columns get the standardised mean difference (SMD) of every split against the rest
(max |SMD| reported) and a Kruskal-Wallis p; categorical columns get a chi-square test of independence between
split and level, Cramer's V, and the max |SMD| of any level's proportion between a split and the rest.
Participants, not clips, are the unit: by default one row per participant (the first) is used.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from palmppg.eval.strata import normalise_level_column

TABLE_COLUMNS = ["stratum", "kind", "n", "n_splits", "max_abs_smd", "statistic", "dof", "p", "cramers_v", "note"]


def smd_numeric(a, b) -> float:
    """Standardised mean difference (mean(a) - mean(b)) / pooled SD."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    a, b = a[np.isfinite(a)], b[np.isfinite(b)]
    if a.size < 2 or b.size < 2:
        return float("nan")
    s = np.sqrt((np.var(a, ddof=1) + np.var(b, ddof=1)) / 2.0)
    return float((a.mean() - b.mean()) / s) if s > 0 else 0.0


def smd_proportion(p1: float, p2: float) -> float:
    """SMD of a binary indicator from its two proportions."""
    s = np.sqrt((p1 * (1 - p1) + p2 * (1 - p2)) / 2.0)
    return float((p1 - p2) / s) if s > 0 else 0.0


def _is_numeric(s: pd.Series) -> bool:
    if s.dtype == bool or s.dtype == object:
        return False
    return pd.api.types.is_numeric_dtype(s) and s.dropna().nunique() > 5


def partition_balance(df: pd.DataFrame, split_col: str, strata: Sequence[str], id_col: str | None = "study_id",
                      per_participant: bool = True, numeric: Sequence[str] | None = None) -> pd.DataFrame:
    """Balance of ``strata`` across the levels of ``split_col`` (folds or streams). ``numeric`` forces columns
    to be treated as continuous; otherwise a numeric column with more than five distinct values is continuous
    and everything else is categorical."""
    if split_col not in df.columns:
        raise KeyError(f"{split_col} not in frame")
    data = df
    note_unit = ""
    if per_participant and id_col and id_col in df.columns:
        data = df.groupby(id_col, sort=False).first().reset_index()
        note_unit = "one row per participant"
    split = normalise_level_column(data[split_col])
    splits = sorted(split.unique().tolist())
    rows = []
    for s in strata:
        row: dict[str, Any] = {c: float("nan") for c in TABLE_COLUMNS}
        row.update({"stratum": s, "n_splits": len(splits), "note": note_unit})
        if s not in data.columns:
            row.update({"kind": "absent", "n": 0, "note": "column absent from table"})
            rows.append(row)
            continue
        col = data[s]
        force_num = numeric is not None and s in numeric
        if force_num or (numeric is None and _is_numeric(col)):
            v = pd.to_numeric(col, errors="coerce")
            ok = v.notna()
            row.update({"kind": "numeric", "n": int(ok.sum())})
            smds = [abs(smd_numeric(v[ok & (split == sp)], v[ok & (split != sp)])) for sp in splits]
            row["max_abs_smd"] = float(np.nanmax(smds)) if smds and np.isfinite(smds).any() else float("nan")
            groups = [v[ok & (split == sp)].to_numpy() for sp in splits]
            groups = [g for g in groups if g.size >= 2]
            if len(groups) >= 2 and np.std(np.concatenate(groups)) > 0:
                h, p = stats.kruskal(*groups)
                row.update({"statistic": float(h), "dof": len(groups) - 1, "p": float(p)})
        else:
            lev = normalise_level_column(col)
            ct = pd.crosstab(split, lev)
            row.update({"kind": "categorical", "n": len(lev)})
            smds = []
            for lv in ct.columns:
                for sp in splits:
                    in_sp = split == sp
                    p1 = float((lev[in_sp] == lv).mean()) if in_sp.sum() else float("nan")
                    p2 = float((lev[~in_sp] == lv).mean()) if (~in_sp).sum() else float("nan")
                    if np.isfinite(p1) and np.isfinite(p2):
                        smds.append(abs(smd_proportion(p1, p2)))
            row["max_abs_smd"] = float(max(smds)) if smds else float("nan")
            if ct.shape[0] >= 2 and ct.shape[1] >= 2:
                chi2, p, dof, _ = stats.chi2_contingency(ct.to_numpy(), correction=False)
                n = ct.to_numpy().sum()
                k = min(ct.shape) - 1
                row.update({"statistic": float(chi2), "dof": int(dof), "p": float(p),
                            "cramers_v": float(np.sqrt(chi2 / (n * k))) if n and k else float("nan")})
            else:
                row["note"] = (row["note"] + "; " if row["note"] else "") + "single level; not testable"
        rows.append(row)
    return pd.DataFrame(rows, columns=TABLE_COLUMNS)


def partition_level_table(df: pd.DataFrame, split_col: str, strata: Sequence[str], id_col: str | None = "study_id",
                          per_participant: bool = True) -> pd.DataFrame:
    """Long table of n and percentage per (stratum, level, split) for the categorical strata."""
    data = df.groupby(id_col, sort=False).first().reset_index() if (per_participant and id_col and id_col in df.columns) else df
    split = normalise_level_column(data[split_col])
    rows = []
    for s in strata:
        if s not in data.columns or _is_numeric(data[s]):
            continue
        lev = normalise_level_column(data[s])
        for sp in sorted(split.unique().tolist()):
            m = split == sp
            vc = lev[m].value_counts()
            for lv, n in vc.items():
                rows.append({"stratum": s, "level": lv, "split": sp, "n": int(n), "pct": 100.0 * n / m.sum()})
    return pd.DataFrame(rows, columns=["stratum", "level", "split", "n", "pct"])
