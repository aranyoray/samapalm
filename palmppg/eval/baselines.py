"""The two mandatory baselines and the pulse-shuffled leakage control (protocol sections 9 E0/E5, 11.2).

  * predict-the-mean: every test row gets the training-set mean of the target;
  * demographics-only: a ridge regression on CRF demographics fitted inside each training fold;
  * pulse-shuffled control (E5): pulse features permuted across participants within a fold so a model trained on
    them can only exploit static or demographic signal; a model that still beats demographics-only has leaked.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from palmppg.core.config import CONFIG_DIR, load_yaml, rng

DEFAULT_DEMOGRAPHICS: tuple[str, ...] = ("age", "sex", "bmi")
EXPERIMENTS_YAML = CONFIG_DIR / "experiments" / "experiments.yaml"


def demographics_columns(path: str | Path | None = None) -> list[str]:
    """Demographic columns named in configs/experiments/experiments.yaml (defaults.demographics_columns);
    falls back to age, sex, bmi when the file is absent, unparsable or lacks the key."""
    p = Path(path) if path else EXPERIMENTS_YAML
    try:
        cols = load_yaml(p).get("defaults", {}).get("demographics_columns")
    except (OSError, ValueError, yaml.YAMLError):  # absent or unparsable file: fall back, never fail a baseline
        cols = None
    return list(cols) if cols else list(DEFAULT_DEMOGRAPHICS)


def predict_mean_predictions(train_y, n_test: int) -> np.ndarray:
    """Predict-the-mean baseline (E0): the training-set mean (ignoring NaN) repeated ``n_test`` times."""
    y = np.asarray(train_y, dtype=float).ravel()
    y = y[np.isfinite(y)]
    if y.size == 0:
        raise ValueError("no finite training targets")
    return np.full(int(n_test), float(np.mean(y)), dtype=float)


class DemographicsRidge:
    """Ridge regression on demographic columns only (E0 baseline). Categorical columns are one-hot encoded with
    categories learned on the training fold; numeric columns are median-imputed and standardised on the
    training fold. Everything is fitted in-fold, so no information from a test fold enters the baseline."""

    def __init__(self, columns: Sequence[str] | None = None, alpha: float = 1.0,
                 categorical: Sequence[str] = ("sex", "dept", "mst_group", "bmi_class", "age_band")):
        self.columns = list(columns) if columns is not None else demographics_columns()
        self.alpha = float(alpha)
        self.categorical = [c for c in categorical if c in self.columns]
        self.numeric = [c for c in self.columns if c not in self.categorical]
        self._cats: dict[str, list[str]] = {}
        self._medians: dict[str, float] = {}
        self._mu: np.ndarray | None = None
        self._sd: np.ndarray | None = None
        self._model = None

    def _design(self, df: pd.DataFrame, fit: bool) -> np.ndarray:
        cols = []
        for c in self.numeric:
            v = pd.to_numeric(df[c], errors="coerce").to_numpy(dtype=float) if c in df.columns else np.full(len(df), np.nan)
            if fit:
                med = float(np.nanmedian(v)) if np.isfinite(v).any() else 0.0
                self._medians[c] = med
            v = np.where(np.isfinite(v), v, self._medians[c])
            cols.append(v)
        for c in self.categorical:
            raw = df[c].astype(object).map(lambda x: "missing" if x is None or (isinstance(x, float) and np.isnan(x)) else str(x)) if c in df.columns else pd.Series(["missing"] * len(df))
            if fit:
                self._cats[c] = sorted(raw.unique().tolist())[1:]  # drop one level as the reference
            for lev in self._cats[c]:
                cols.append((raw.to_numpy() == lev).astype(float))
        X = np.column_stack(cols) if cols else np.zeros((len(df), 0))
        if fit:
            self._mu = X.mean(axis=0) if X.shape[1] else np.zeros(0)
            sd = X.std(axis=0) if X.shape[1] else np.zeros(0)
            self._sd = np.where(sd > 0, sd, 1.0)
        return (X - self._mu) / self._sd

    def fit(self, df: pd.DataFrame, y) -> DemographicsRidge:
        from sklearn.linear_model import Ridge

        yv = np.asarray(y, dtype=float).ravel()
        ok = np.isfinite(yv)
        X = self._design(df.iloc[np.flatnonzero(ok)], fit=True)
        self._model = Ridge(alpha=self.alpha).fit(X, yv[ok])
        return self

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        if self._model is None:
            raise RuntimeError("fit first")
        return np.asarray(self._model.predict(self._design(df, fit=False)), dtype=float)


def demographics_only(columns: Sequence[str] | None = None, alpha: float = 1.0) -> Callable[[pd.DataFrame, Any, pd.DataFrame], np.ndarray]:
    """Return ``fit_predict(train_df, train_y, test_df) -> predictions`` for use inside the CV loops: a fresh
    ``DemographicsRidge`` is fitted on each call, so nothing leaks between folds (E0 baseline)."""
    def fit_predict(train_df: pd.DataFrame, train_y, test_df: pd.DataFrame) -> np.ndarray:
        return DemographicsRidge(columns, alpha).fit(train_df, train_y).predict(test_df)

    return fit_predict


def pulse_shuffled_control(df: pd.DataFrame, pulse_cols: Sequence[str], fold_col: str | None = None,
                           id_col: str = "study_id", seed: int | None = 0, salt: str = "pulse_shuffle") -> tuple[pd.DataFrame, pd.DataFrame]:
    """E5 leakage control: permute the pulse feature columns *across participants within each fold* so every
    participant receives another participant's pulse features (a cyclic shift of a random participant order, so
    nobody keeps their own). Rows of a donor are cycled when the receiver has more rows. Returns the shuffled
    frame and a map (fold, study_id, donor_study_id)."""
    missing = [c for c in pulse_cols if c not in df.columns]
    if missing:
        raise KeyError(f"pulse columns not in frame: {missing}")
    if id_col not in df.columns:
        raise KeyError(f"{id_col} not in frame")
    out = df.copy()
    g = rng(seed, salt)
    folds = out[fold_col].to_numpy() if fold_col else np.zeros(len(out), dtype=int)
    rows = []
    for f in pd.unique(folds):
        in_fold = np.flatnonzero(folds == f)
        ids = out[id_col].to_numpy()[in_fold].astype(str)
        uniq = np.array(sorted(set(ids)))
        if len(uniq) < 2:
            for u in uniq:
                rows.append({"fold": f, id_col: u, "donor": u, "note": "single participant in fold; not shuffled"})
            continue
        order = g.permutation(len(uniq))
        donor_of = {uniq[order[i]]: uniq[order[(i + 1) % len(uniq)]] for i in range(len(uniq))}
        blocks = {u: in_fold[ids == u] for u in uniq}
        src = df[list(pulse_cols)].to_numpy()
        for u in uniq:
            recv = blocks[u]
            don = blocks[donor_of[u]]
            take = don[np.arange(len(recv)) % len(don)]
            out.iloc[recv, [out.columns.get_loc(c) for c in pulse_cols]] = src[take]
            rows.append({"fold": f, id_col: u, "donor": donor_of[u], "note": ""})
    return out, pd.DataFrame(rows)
