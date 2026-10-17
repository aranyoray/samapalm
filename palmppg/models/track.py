"""Track enforcement for every estimator (protocol section 9 "two model tracks", section 11.5).

``TrackGuard`` wraps any sklearn-compatible estimator and refuses to fit or predict on a feature
frame that contains a column forbidden in its track (``requires_ecg`` or ``requires_raw`` columns in
``product_candidate``) or a column that was never registered with ``palmppg.core.tracks.REGISTRY``.
It records the exact column list it was fitted on so that prediction-time frames are checked against
the same set and order.

``forbid_target_leak`` is the companion check that a target (or a trivially target-equivalent column)
never sits in the feature matrix.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, clone

from palmppg.core.tracks import REGISTRY, TRACKS, FeatureRegistry, TrackViolation

# Columns that are never features: identifiers and the cuff/clinician targets derived in core.crf.
DEFAULT_TARGET_PATTERNS: tuple[str, ...] = (
    "bp_target", "bp_target_23", "bp_category", "bp_tertile", "rhythm", "ecg_hr", "clinician_",
)


def _column_list(X) -> list[str]:
    if isinstance(X, pd.DataFrame):
        return [str(c) for c in X.columns]
    raise TypeError("TrackGuard needs a pandas DataFrame with registered column names, got "
                    f"{type(X).__name__}")


class TrackGuard(BaseEstimator):
    """Fit/predict gate that calls ``registry.check_columns(X.columns, track)`` before every use.

    Parameters
    ----------
    estimator : sklearn-compatible estimator
        Cloned at ``fit`` time; the fitted clone lives in ``estimator_``.
    track : "product_candidate" | "science"
    registry : FeatureRegistry, default ``palmppg.core.tracks.REGISTRY``
    keep : iterable of str
        Identifier columns (``study_id``, ``clip_id`` ...) that may be present in ``X``. They are
        exempt from the registry check and are dropped before the estimator sees the data; they are
        never features.

    Attributes
    ----------
    fitted_columns_ : list[str]   the feature columns, in order, the estimator was fitted on
    track : str                   the track this guard enforces
    n_features_in_ : int

    Serves protocol section 9 (track separation) and 11.5 (no ECG or PAT feature in a product model).
    """

    def __init__(self, estimator, track: str, registry: FeatureRegistry = REGISTRY, keep: Iterable[str] = ()):
        self.estimator = estimator
        self.track = track
        self.registry = registry
        self.keep = tuple(keep)

    # ------------------------------------------------------------------ checks
    def _check(self, X: pd.DataFrame, stage: str) -> list[str]:
        if self.track not in TRACKS:
            raise TrackViolation(f"unknown track '{self.track}' (allowed {TRACKS})")
        cols = [c for c in _column_list(X) if c not in set(self.keep)]
        self.registry.check_columns(cols, self.track, strict_unknown=True)
        if stage == "predict":
            fitted = getattr(self, "fitted_columns_", None)
            if fitted is None:
                raise TrackViolation("TrackGuard.predict called before fit")
            missing = [c for c in fitted if c not in cols]
            if missing:
                raise TrackViolation(f"{len(missing)} fitted column(s) missing at predict time: {missing[:10]}")
            return list(fitted)
        return cols

    def check(self, X: pd.DataFrame) -> list[str]:
        """Run the track check on ``X`` without fitting; returns the allowed feature columns."""
        return self._check(X, "check")

    # ------------------------------------------------------------------ sklearn API
    def fit(self, X: pd.DataFrame, y=None, **fit_params):
        cols = self._check(X, "fit")
        self.fitted_columns_ = list(cols)
        self.n_features_in_ = len(cols)
        self.estimator_ = clone(self.estimator)
        self.estimator_.fit(X[cols], y, **fit_params)
        if hasattr(self.estimator_, "classes_"):
            self.classes_ = self.estimator_.classes_
        return self

    def predict(self, X: pd.DataFrame):
        cols = self._check(X, "predict")
        return self.estimator_.predict(X[cols])

    def predict_proba(self, X: pd.DataFrame):
        cols = self._check(X, "predict")
        if not hasattr(self.estimator_, "predict_proba"):
            raise AttributeError(f"{type(self.estimator_).__name__} has no predict_proba")
        return self.estimator_.predict_proba(X[cols])

    def predict_interval(self, X: pd.DataFrame):
        cols = self._check(X, "predict")
        if not hasattr(self.estimator_, "predict_interval"):
            raise AttributeError(f"{type(self.estimator_).__name__} has no predict_interval")
        return self.estimator_.predict_interval(X[cols])

    def transform(self, X: pd.DataFrame):
        cols = self._check(X, "predict")
        return self.estimator_.transform(X[cols])

    def score(self, X: pd.DataFrame, y):
        cols = self._check(X, "predict")
        return self.estimator_.score(X[cols], y)


def forbid_target_leak(X: pd.DataFrame, targets: Sequence[str], y=None, patterns: Sequence[str] = DEFAULT_TARGET_PATTERNS,
                       max_abs_corr: float = 0.999) -> list[str]:
    """Raise ``TrackViolation`` when a target leaks into the feature frame.

    Three checks: (1) an exact target name in ``X.columns``; (2) a column whose name starts with one
    of ``patterns`` (cuff BP targets and clinician labels derived in ``core.crf``); (3) when ``y`` is
    numeric, a numeric column whose absolute Pearson correlation with ``y`` is at least
    ``max_abs_corr`` (a renamed copy of the target). Returns the list of checked columns.
    Serves protocol 11.5 and the pulse-shuffled leakage control of E5.
    """
    cols = _column_list(X)
    tset = set(targets)
    bad = [c for c in cols if c in tset]
    if bad:
        raise TrackViolation(f"target column(s) present in features: {bad}")
    bad = [c for c in cols if any(c.startswith(p) for p in patterns)]
    if bad:
        raise TrackViolation(f"target-derived column(s) present in features: {bad}")
    if y is not None:
        yv = np.asarray(y, dtype=float).ravel()
        if np.isfinite(yv).all() and np.std(yv) > 0 and len(yv) == len(X):
            for c in cols:
                col = X[c]
                if not pd.api.types.is_numeric_dtype(col):
                    continue
                v = col.to_numpy(dtype=float)
                ok = np.isfinite(v)
                if ok.sum() < 3 or np.std(v[ok]) == 0:
                    continue
                r = np.corrcoef(v[ok], yv[ok])[0, 1]
                if abs(r) >= max_abs_corr:
                    raise TrackViolation(f"column '{c}' is a copy of the target (|r| = {abs(r):.4f})")
    return cols


__all__ = ["DEFAULT_TARGET_PATTERNS", "TrackGuard", "TrackViolation", "forbid_target_leak"]
