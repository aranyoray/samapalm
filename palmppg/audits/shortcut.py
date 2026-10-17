"""Shortcut audit (protocol section 9 E11): can the features predict a nuisance variable (operator, unit,
department, stream, time of day, antihypertensive timing, camera) better than chance in participant-grouped CV,
and are the model residuals associated with it?

A feature set that identifies the operator or unit is carrying acquisition signal rather than physiology; a
residual that differs by nuisance level shows the model's errors are not exchangeable across it. Both are
reported as measured numbers against their chance level; nothing here states what the numbers should be.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from palmppg.audits._cv import design_matrix, grouped_cv_classification
from palmppg.core.config import rng

DEFAULT_NUISANCE: tuple[str, ...] = ("operator", "unit_id", "dept", "stream", "time_of_day", "antihtn_today", "camera")
TABLE_COLUMNS = ["nuisance", "n", "n_levels", "balanced_accuracy", "chance", "excess", "macro_f1", "chance_macro_f1",
                 "perm_p", "residual_anova_f", "residual_anova_p", "residual_kruskal_h", "residual_kruskal_p",
                 "residual_eta_sq", "note"]


@dataclass(frozen=True)
class ShortcutAuditResult:
    table: pd.DataFrame
    markdown: str


def residual_association(residuals, levels, min_level_n: int = 2) -> dict[str, float]:
    """One-way ANOVA F and Kruskal-Wallis H of residuals across nuisance levels, plus eta-squared
    (between-level share of the residual sum of squares). Levels with fewer than ``min_level_n`` rows are dropped."""
    r = np.asarray(residuals, dtype=float).ravel()
    lv = np.asarray(levels).astype(object)
    ok = np.isfinite(r) & pd.notna(lv)
    r, lv = r[ok], lv[ok].astype(str)
    groups = [r[lv == v] for v in np.unique(lv)]
    groups = [g for g in groups if g.size >= min_level_n]
    nan = {"anova_f": float("nan"), "anova_p": float("nan"), "kruskal_h": float("nan"), "kruskal_p": float("nan"),
           "eta_sq": float("nan")}
    if len(groups) < 2:
        return nan
    allv = np.concatenate(groups)
    if np.std(allv) == 0:
        return nan
    f, pf = stats.f_oneway(*groups)
    try:
        h, ph = stats.kruskal(*groups)
    except ValueError:
        h, ph = float("nan"), float("nan")
    gm = allv.mean()
    ss_b = sum(g.size * (g.mean() - gm) ** 2 for g in groups)
    ss_t = float(np.sum((allv - gm) ** 2))
    return {"anova_f": float(f), "anova_p": float(pf), "kruskal_h": float(h), "kruskal_p": float(ph),
            "eta_sq": float(ss_b / ss_t) if ss_t > 0 else float("nan")}


def _permutation_p(X, y, groups, observed: float, n_perm: int, cv: int, seed: int | None, salt: str) -> float:
    """Participant-level label permutation null for the balanced accuracy (labels stay constant within a
    participant; the participant-to-label assignment is shuffled)."""
    if n_perm <= 0:
        return float("nan")
    g = np.asarray(groups).astype(str)
    uniq = np.array(sorted(set(g)))
    first = {u: y[np.flatnonzero(g == u)[0]] for u in uniq}
    gen = rng(seed, salt + ":perm")
    hits = 0
    for i in range(int(n_perm)):
        perm = gen.permutation(len(uniq))
        lab = {uniq[j]: first[uniq[perm[j]]] for j in range(len(uniq))}
        yp = np.array([lab[x] for x in g])
        res = grouped_cv_classification(X, yp, g, cv, seed, f"{salt}:perm{i}")
        if res["balanced_accuracy"] >= observed:
            hits += 1
    return float((hits + 1) / (n_perm + 1))


def shortcut_audit(features_df: pd.DataFrame, feature_cols: Sequence[str], nuisance_cols: Sequence[str] | None = None,
                   cv: int = 5, seed: int | None = 0, residual_col: str | None = None, id_col: str = "study_id",
                   min_level_n: int = 5, n_permutations: int = 0) -> ShortcutAuditResult:
    """E11 shortcut audit. For each nuisance column: balanced accuracy and macro-F1 of predicting it from
    ``feature_cols`` in participant-grouped ``cv``-fold CV against chance (1/k), an optional participant-level
    permutation p-value, and (when ``residual_col`` is given) ANOVA / Kruskal-Wallis association of model
    residuals with the nuisance. Levels with fewer than ``min_level_n`` rows are left out of the classifier and
    named in the note. Returns the table and a markdown rendering."""
    nuisance_cols = list(DEFAULT_NUISANCE if nuisance_cols is None else nuisance_cols)
    missing = [c for c in feature_cols if c not in features_df.columns]
    if missing:
        raise KeyError(f"feature columns not in frame: {missing}")
    if id_col not in features_df.columns:
        raise KeyError(f"{id_col} not in frame")
    X_all = design_matrix(features_df, feature_cols)
    rows = []
    for nz in nuisance_cols:
        row: dict[str, Any] = {c: float("nan") for c in TABLE_COLUMNS}
        row.update({"nuisance": nz, "note": ""})
        if nz not in features_df.columns:
            row.update({"n": 0, "n_levels": 0, "note": "column absent from table"})
            rows.append(row)
            continue
        lab = features_df[nz].astype(object).map(lambda v: None if v is None or (isinstance(v, float) and np.isnan(v)) else str(v))
        counts = lab.value_counts()
        keep_levels = counts[counts >= min_level_n].index.tolist()
        dropped = counts[counts < min_level_n]
        mask = lab.isin(keep_levels).to_numpy()
        n_lev = len(keep_levels)
        row.update({"n": int(mask.sum()), "n_levels": n_lev})
        notes = []
        if len(dropped):
            left_out = ", ".join(f"{k} (n={v})" for k, v in dropped.items())
            notes.append(f"levels left out (n<{min_level_n}): {left_out}")
        if n_lev >= 2 and mask.sum() >= 2 * cv:
            X = X_all[mask]
            y = lab[mask].to_numpy().astype(str)
            grp = features_df[id_col].to_numpy()[mask]
            try:
                res = grouped_cv_classification(X, y, grp, cv, seed, f"shortcut:{nz}")
                row.update({"balanced_accuracy": res["balanced_accuracy"], "chance": res["chance"],
                            "excess": res["balanced_accuracy"] - res["chance"], "macro_f1": res["macro_f1"],
                            "chance_macro_f1": res["chance_macro_f1"]})
                row["perm_p"] = _permutation_p(X, y, grp, res["balanced_accuracy"], n_permutations, cv, seed, f"shortcut:{nz}")
            except ValueError as e:
                notes.append(str(e))
        else:
            notes.append("single level or too few rows after filtering; shortcut not testable")
        if residual_col is not None and residual_col in features_df.columns:
            a = residual_association(features_df[residual_col].to_numpy(dtype=float), lab.to_numpy())
            row.update({"residual_anova_f": a["anova_f"], "residual_anova_p": a["anova_p"],
                        "residual_kruskal_h": a["kruskal_h"], "residual_kruskal_p": a["kruskal_p"],
                        "residual_eta_sq": a["eta_sq"]})
        row["note"] = "; ".join(notes)
        rows.append(row)
    table = pd.DataFrame(rows, columns=TABLE_COLUMNS)
    return ShortcutAuditResult(table, shortcut_markdown(table, residual_col is not None, n_permutations))


def shortcut_markdown(table: pd.DataFrame, with_residuals: bool, n_permutations: int = 0) -> str:
    cols = ["nuisance", "n", "n_levels", "balanced_accuracy", "chance", "excess", "macro_f1", "chance_macro_f1"]
    if n_permutations > 0:
        cols.append("perm_p")
    if with_residuals:
        cols += ["residual_anova_p", "residual_kruskal_p", "residual_eta_sq"]
    cols.append("note")

    def f(v):
        if isinstance(v, (float, np.floating)):
            return "" if not np.isfinite(v) else f"{v:.3f}"
        return str(v)

    lines = ["## Shortcut audit (E11): nuisance predictability from features, participant-grouped CV", "",
             "| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, r in table.iterrows():
        lines.append("| " + " | ".join(f(r[c]) for c in cols) + " |")
    lines += ["", ("`chance` is 1/k for balanced accuracy; `excess` = balanced accuracy - chance (measured, no "
                   "threshold applied).")]
    if with_residuals:
        lines.append("Residual columns: one-way ANOVA and Kruskal-Wallis of model residuals across nuisance levels.")
    return "\n".join(lines) + "\n"
