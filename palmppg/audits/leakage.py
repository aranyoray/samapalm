"""Leakage checks (protocol section 11.1 participant splits, section 8 augmentation rules, E5 control).

  split_integrity              no participant in two validation folds, train/test disjoint per fold, augmented
                               copies never in validation and never in training when their source is in validation
  pulse_shuffle_control_summary the E5 pulse-shuffled arm compared with demographics-only
  target_in_features           the target (or a cuff reading) hiding among the feature columns

``target_in_features`` is implemented here rather than imported from the feature-store package, which is built
concurrently; the two checks are independent and both may run.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pandas as pd

from palmppg.eval.bootstrap import participant_bootstrap

TARGET_NAME_PATTERNS: tuple[str, ...] = ("bp_target", "bp1", "bp2", "bp3", "sbp", "dbp", "cuff")


def _fold_parts(fold: Any) -> tuple[set[str], set[str]]:
    if isinstance(fold, Mapping):
        tr, te = fold.get("train", ()), fold.get("test", fold.get("validation", ()))
    else:
        tr, te = fold[0], fold[1]
    return {str(x) for x in tr}, {str(x) for x in te}


def split_integrity(folds: Sequence[Any], df: pd.DataFrame | None = None, id_col: str = "study_id",
                    source_col: str = "augmented_from") -> dict[str, Any]:
    """Check a list of (train_ids, test_ids) folds. With ``df`` (rows carrying ``id_col`` and, for augmented
    copies, ``source_col`` = the id of the source participant) the augmentation rules of section 8 are checked
    too. Returns ok, problems (list of strings), and counts."""
    problems: list[str] = []
    seen_test: dict[str, int] = {}
    parts = [_fold_parts(f) for f in folds]
    for k, (tr, te) in enumerate(parts):
        both = tr & te
        if both:
            problems.append(f"fold {k}: {len(both)} id(s) in both train and validation: {sorted(both)[:5]}")
        for x in te:
            if x in seen_test:
                problems.append(f"participant {x} in validation of folds {seen_test[x]} and {k}")
            else:
                seen_test[x] = k
    n_aug = 0
    unassigned = 0
    if df is not None:
        if id_col not in df.columns:
            raise KeyError(f"{id_col} not in frame")
        ids = df[id_col].astype(str).to_numpy()
        all_ids = set().union(*[tr | te for tr, te in parts]) if parts else set()
        unassigned = int(sum(x not in all_ids for x in set(ids)))
        if source_col in df.columns:
            src = df[source_col].to_numpy(dtype=object)
            aug_mask = np.array([s is not None and not (isinstance(s, float) and np.isnan(s)) for s in src])
            n_aug = int(aug_mask.sum())
            for aid, sid in set(zip(ids[aug_mask], (str(s) for s in src[aug_mask]))):
                for k, (tr, te) in enumerate(parts):
                    if aid in te:
                        problems.append(f"fold {k}: augmented copy {aid} (source {sid}) sits in validation")
                    if sid in te and aid in tr:
                        problems.append(f"fold {k}: augmented copy {aid} in training while its source {sid} is in validation")
    return {"ok": not problems, "problems": problems, "n_folds": len(parts), "n_ids_in_validation": len(seen_test),
            "n_augmented_rows": n_aug, "n_ids_unassigned": unassigned}


def _sd_of(df: pd.DataFrame, arm_col: str, arm: str, y_col: str, pred_col: str) -> float:
    m = (df[arm_col].astype(str) == arm).to_numpy()
    e = pd.to_numeric(df.loc[m, pred_col], errors="coerce").to_numpy(dtype=float) - pd.to_numeric(df.loc[m, y_col], errors="coerce").to_numpy(dtype=float)
    e = e[np.isfinite(e)]
    return float(np.std(e, ddof=1)) if e.size > 1 else float("nan")


def pulse_shuffle_control_summary(results_df: pd.DataFrame, y_col: str, pred_col: str, arm_col: str = "arm",
                                  id_col: str = "study_id", shuffled_arm: str = "pulse_shuffled_control",
                                  demographics_arm: str = "demographics_only", temporal_arms: Sequence[str] = ("temporal_only", "static_plus_temporal"),
                                  n_resamples: int = 500, ci: float = 0.95, seed: int | None = 0) -> dict[str, Any]:
    """E5 leakage control summary on a long results frame (one row per clip per arm). Reports the error SD of
    every arm and the improvement ``sd(demographics_only) - sd(pulse_shuffled_control)`` with a paired
    participant-bootstrap CI. ``leak_suspected`` is True when the lower CI bound of that improvement is above
    zero: shuffled pulse features carry no participant signal, so beating demographics-only with them means
    information reached the model some other way."""
    for c in (y_col, pred_col, arm_col, id_col):
        if c not in results_df.columns:
            raise KeyError(f"{c} not in frame")
    arms = results_df[arm_col].astype(str).unique().tolist()
    for a in (shuffled_arm, demographics_arm):
        if a not in arms:
            raise KeyError(f"arm {a} not in results")
    table = pd.DataFrame([{"arm": a, "n": int((results_df[arm_col].astype(str) == a).sum()),
                           "error_sd": _sd_of(results_df, arm_col, a, y_col, pred_col)} for a in arms])
    sub = results_df[results_df[arm_col].astype(str).isin([shuffled_arm, demographics_arm])]
    r = participant_bootstrap(sub, lambda d: _sd_of(d, arm_col, demographics_arm, y_col, pred_col) - _sd_of(d, arm_col, shuffled_arm, y_col, pred_col),
                              id_col=id_col, n=n_resamples, ci=ci, seed=seed, salt="pulse_shuffle_summary")
    out = {"table": table, "improvement_vs_demographics": r.point, "improvement_lo": r.lo, "improvement_hi": r.hi,
           "leak_suspected": bool(np.isfinite(r.lo) and r.lo > 0), "n_participants": r.n_participants}
    for t in temporal_arms:
        if t in arms:
            out[f"temporal_minus_shuffled_sd__{t}"] = _sd_of(results_df, arm_col, t, y_col, pred_col) - _sd_of(results_df, arm_col, shuffled_arm, y_col, pred_col)
    return out


def target_in_features(features_df: pd.DataFrame, feature_cols: Sequence[str], target_col: str, corr_max: float = 0.99,
                       name_patterns: Sequence[str] = TARGET_NAME_PATTERNS) -> dict[str, Any]:
    """Flag feature columns that are the target by name (the target column itself or a cuff-reading name
    pattern) or by value (|Pearson r| with the target above ``corr_max``, or exact equality)."""
    problems: list[str] = []
    by_name = [c for c in feature_cols if c == target_col or any(p in c.lower() for p in name_patterns)]
    for c in by_name:
        problems.append(f"feature {c} names the target or a cuff reading")
    y = pd.to_numeric(features_df[target_col], errors="coerce").to_numpy(dtype=float) if target_col in features_df.columns else None
    max_r = float("nan")
    by_value: list[tuple[str, float]] = []
    if y is not None:
        for c in feature_cols:
            if c not in features_df.columns or c == target_col:
                continue
            x = pd.to_numeric(features_df[c], errors="coerce").to_numpy(dtype=float)
            ok = np.isfinite(x) & np.isfinite(y)
            if ok.sum() < 3 or np.std(x[ok]) == 0 or np.std(y[ok]) == 0:
                continue
            r = float(np.corrcoef(x[ok], y[ok])[0, 1])
            if not np.isfinite(max_r) or abs(r) > max_r:
                max_r = abs(r)
            if np.allclose(x[ok], y[ok]) or abs(r) > corr_max:
                by_value.append((c, r))
                problems.append(f"feature {c} tracks the target (r={r:.4f})")
    return {"ok": not problems, "problems": problems, "by_name": by_name, "by_value": by_value, "max_abs_corr": max_r}
