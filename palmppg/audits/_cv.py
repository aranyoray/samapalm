"""Shared participant-grouped CV classification used by the shortcut audit (E11) and the MST
leakage probe (E6). Private to palmppg.audits."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from palmppg.core.config import rng


def grouped_folds(groups, n_splits: int, seed: int | None, salt: str = "grouped_cv") -> list[tuple[np.ndarray, np.ndarray]]:
    """Participant-grouped folds: participants are shuffled with ``rng(seed, salt)`` and dealt round-robin into
    ``n_splits`` folds, so every participant's rows sit in exactly one test fold."""
    g = np.asarray(groups).astype(str)
    uniq = np.array(sorted(set(g)))
    k = min(int(n_splits), len(uniq))
    if k < 2:
        raise ValueError("need at least two participants for grouped CV")
    order = rng(seed, salt).permutation(len(uniq))
    fold_of = {uniq[order[i]]: i % k for i in range(len(uniq))}
    f = np.array([fold_of[x] for x in g])
    return [(np.flatnonzero(f != j), np.flatnonzero(f == j)) for j in range(k)]


def chance_macro_f1(y) -> float:
    """Expected macro-F1 of uniform random guessing over the k observed classes: for class j with prevalence
    p_j the F1 against a guess rate 1/k is 2 p_j (1/k) / (p_j + 1/k)."""
    y = np.asarray(y)
    classes, counts = np.unique(y, return_counts=True)
    k = len(classes)
    if k == 0:
        return float("nan")
    q = 1.0 / k
    p = counts / counts.sum()
    return float(np.mean(2 * p * q / (p + q)))


def grouped_cv_classification(X: np.ndarray, y, groups, n_splits: int = 5, seed: int | None = 0,
                              salt: str = "grouped_cv", n_estimators: int = 100) -> dict[str, Any]:
    """Random-forest classification of ``y`` from ``X`` in participant-grouped CV. Returns balanced accuracy,
    macro-F1, their chance levels (1/k for balanced accuracy; uniform-guess macro-F1), n, n_classes and the
    out-of-fold predictions. NaN features are median-imputed on the training fold."""
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import balanced_accuracy_score, f1_score

    X = np.asarray(X, dtype=float)
    y = np.asarray(y).astype(str)
    classes = np.unique(y)
    if len(classes) < 2:
        return {"balanced_accuracy": float("nan"), "macro_f1": float("nan"), "chance": float("nan"),
                "chance_macro_f1": float("nan"), "n": len(y), "n_classes": len(classes),
                "note": "fewer than two classes", "y_pred": None}
    pred = np.empty(len(y), dtype=object)
    rs = int(rng(seed, salt + ":rf").integers(0, 2**31 - 1))
    for tr, te in grouped_folds(groups, n_splits, seed, salt):
        Xtr, Xte = X[tr].copy(), X[te].copy()
        med = np.nanmedian(Xtr, axis=0) if len(Xtr) else np.zeros(X.shape[1])
        med = np.where(np.isfinite(med), med, 0.0)
        Xtr = np.where(np.isfinite(Xtr), Xtr, med)
        Xte = np.where(np.isfinite(Xte), Xte, med)
        if len(np.unique(y[tr])) < 2:
            pred[te] = y[tr][0] if len(tr) else classes[0]
            continue
        clf = RandomForestClassifier(n_estimators=n_estimators, min_samples_leaf=2, random_state=rs, n_jobs=1)
        clf.fit(Xtr, y[tr])
        pred[te] = clf.predict(Xte)
    pred = pred.astype(str)
    return {"balanced_accuracy": float(balanced_accuracy_score(y, pred)),
            "macro_f1": float(f1_score(y, pred, average="macro")),
            "chance": float(1.0 / len(classes)), "chance_macro_f1": chance_macro_f1(y),
            "n": len(y), "n_classes": len(classes), "note": "", "y_pred": pred}


def design_matrix(df: pd.DataFrame, feature_cols) -> np.ndarray:
    """Float design matrix from feature columns (non-numeric values become NaN)."""
    return np.column_stack([pd.to_numeric(df[c], errors="coerce").to_numpy(dtype=float) for c in feature_cols])
