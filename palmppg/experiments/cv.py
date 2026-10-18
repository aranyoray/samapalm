"""Participant-grouped out-of-fold predictions with the two mandatory baselines (protocol 10, 11.1-11.3).

Training uses only valid clips of the training participants; every attempted clip of a test participant gets a
prediction slot, and clips that failed QC (or that a model abstains on) keep a NaN prediction so they count as
failures in coverage. Models are wrapped in TrackGuard so a forbidden column raises before fitting.
"""
from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, RidgeCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from palmppg.features.splits import grouped_kfold
from palmppg.models.track import TrackGuard

ALPHAS = np.logspace(-2, 4, 25)


def ridge_model() -> Pipeline:
    return Pipeline([("impute", SimpleImputer(strategy="median", keep_empty_features=True)), ("scale", StandardScaler()), ("ridge", RidgeCV(alphas=ALPHAS))])


def logistic_model(seed: int = 0) -> Pipeline:
    return Pipeline([("impute", SimpleImputer(strategy="median", keep_empty_features=True)), ("scale", StandardScaler()),
                     ("lr", LogisticRegression(C=0.5, max_iter=2000, class_weight="balanced", random_state=seed))])


def gbdt_model(seed: int = 0, task: str = "regression"):
    from palmppg.models.tabular import make_gbdt

    return make_gbdt("lightgbm", task=task, seed=seed, n_estimators=150, learning_rate=0.05, max_depth=3,
                     min_child_samples=5, verbose=-1)


def folds_for(df: pd.DataFrame, n_splits: int, seed: int) -> list[tuple[set, set]]:
    ids = df["study_id"].astype(str).tolist()
    n = min(n_splits, len(set(ids)))
    folds = grouped_kfold(ids, n, seed)
    return [(set(tr), set(te)) for tr, te in folds]


def cv_predict(df: pd.DataFrame, X: pd.DataFrame, y: np.ndarray, valid: np.ndarray, model_fn: Callable[[], object],
               track: str, n_splits: int, seed: int, task: str = "regression", folds=None) -> np.ndarray:
    """Out-of-fold predictions for every row; NaN for invalid clips and for folds that could not be fitted."""
    pred = np.full(len(df), np.nan)
    ids = df["study_id"].astype(str).to_numpy()
    folds = folds or folds_for(df, n_splits, seed)
    for tr_ids, te_ids in folds:
        tr = np.isin(ids, list(tr_ids)) & valid & np.isfinite(y)
        te = np.isin(ids, list(te_ids))
        if tr.sum() < 5 or te.sum() == 0 or X.shape[1] == 0:
            continue
        if task == "classification" and len(np.unique(y[tr])) < 2:
            continue
        m = TrackGuard(model_fn(), track)
        m.fit(X[tr], y[tr])
        if task == "classification":
            p = m.predict_proba(X[te])
            pred[te] = p[:, 1] if p.ndim == 2 else p
        else:
            pred[te] = m.predict(X[te])
    pred[~valid] = np.nan
    return pred


def baseline_predictions(df: pd.DataFrame, y: np.ndarray, valid: np.ndarray, demo: pd.DataFrame, n_splits: int, seed: int,
                         folds=None) -> dict[str, np.ndarray]:
    """predict_mean and demographics_only out-of-fold predictions on the same folds (non-negotiable 11.2).

    Baselines need no video, so they cover every attempted participant whose CRF has the inputs; the coverage of the
    model is what changes, and both are reported."""
    ids = df["study_id"].astype(str).to_numpy()
    folds = folds or folds_for(df, n_splits, seed)
    pm = np.full(len(df), np.nan)
    dm = np.full(len(df), np.nan)
    for tr_ids, te_ids in folds:
        tr = np.isin(ids, list(tr_ids)) & np.isfinite(y)
        te = np.isin(ids, list(te_ids))
        if tr.sum() < 2:
            continue
        pm[te] = float(np.mean(y[tr]))
        if demo.shape[1]:
            m = ridge_model().fit(demo[tr], y[tr])
            dm[te] = m.predict(demo[te])
    return {"predict_mean": pm, "demographics_only": dm}


def shuffled_within_folds(X: pd.DataFrame, df: pd.DataFrame, cols: list[str], folds, seed: int) -> pd.DataFrame:
    """Pulse-shuffled leakage control: permute the temporal columns across participants inside each fold."""
    Xs = X.copy()
    ids = df["study_id"].astype(str).to_numpy()
    r = np.random.default_rng(seed)
    for tr_ids, te_ids in folds:
        for part in (tr_ids, te_ids):
            idx = np.where(np.isin(ids, list(part)))[0]
            if idx.size > 1:
                perm = r.permutation(idx)
                Xs.iloc[idx, [Xs.columns.get_loc(c) for c in cols]] = X.iloc[perm][cols].to_numpy()
    return Xs
