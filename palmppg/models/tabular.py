"""Tabular models for the BP and rhythm endpoints (protocol section 9, E0, E3, E7, E12).

* ``make_gbdt``: LightGBM, XGBoost or CatBoost regressors/classifiers/quantile regressors with per-column
  monotone constraints resolved by column *name* at fit time, so the constraint survives column
  re-ordering. Small ``n_estimators`` by default (the pilot is 500 participants).
* ``make_linear``: ridge and elastic-net baselines (regression) and their logistic counterparts
  (classification) behind standard scaling.
* ``make_quantile_pair``: a lower/upper quantile pair (plus median) giving a (1 - alpha) interval
  (protocol 10: intervals with an abstain option; see ``uncertainty.AbstainPolicy``).
* ``PredictMeanBaseline`` and ``DemographicsOnlyBaseline``: the two baselines every results table
  must carry (protocol 9 "E0 baselines", 11.2).

All estimators are sklearn-compatible and meant to be wrapped by ``track.TrackGuard``.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin, RegressorMixin, clone
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import ElasticNet, LogisticRegression, QuantileRegressor, Ridge
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import LabelEncoder, OneHotEncoder, StandardScaler

GBDT_KINDS = ("lightgbm", "xgboost", "catboost")
TASKS = ("regression", "classification", "quantile")
DEFAULT_DEMOGRAPHIC_COLUMNS: tuple[str, ...] = ("age", "sex", "bmi")


# --------------------------------------------------------------------------- helpers
def _columns_of(X) -> list[str]:
    if isinstance(X, pd.DataFrame):
        return [str(c) for c in X.columns]
    return [f"f{i}" for i in range(np.asarray(X).shape[1])]


def resolve_monotone_constraints(constraints: Mapping[str, int] | None, columns: Sequence[str]) -> list[int]:
    """Map ``{column: +1|-1|0}`` onto the column order; unknown names raise ``KeyError``."""
    out = [0] * len(columns)
    if not constraints:
        return out
    index = {c: i for i, c in enumerate(columns)}
    for name, sign in constraints.items():
        if name not in index:
            raise KeyError(f"monotone constraint on unknown column '{name}' (have {list(columns)[:10]} ...)")
        s = int(sign)
        if s not in (-1, 0, 1):
            raise ValueError(f"monotone constraint for '{name}' must be -1, 0 or +1, got {sign}")
        out[index[name]] = s
    return out


class _GBDTBase(BaseEstimator):
    """Shared construction of the backend estimator at fit time (so constraints use column names)."""

    def __init__(self, kind: str = "lightgbm", task: str = "regression", quantile_alpha: float | None = None,
                 monotone_constraints: Mapping[str, int] | None = None, seed: int = 0, n_estimators: int = 50,
                 learning_rate: float = 0.1, max_depth: int = 4, n_jobs: int = 2, extra: Mapping | None = None):
        self.kind = kind
        self.task = task
        self.quantile_alpha = quantile_alpha
        self.monotone_constraints = monotone_constraints
        self.seed = seed
        self.n_estimators = n_estimators
        self.learning_rate = learning_rate
        self.max_depth = max_depth
        self.n_jobs = n_jobs
        self.extra = extra

    def _validate(self) -> None:
        if self.kind not in GBDT_KINDS:
            raise ValueError(f"kind must be one of {GBDT_KINDS}, got {self.kind}")
        if self.task not in TASKS:
            raise ValueError(f"task must be one of {TASKS}, got {self.task}")
        if self.task == "quantile" and not (self.quantile_alpha is not None and 0.0 < float(self.quantile_alpha) < 1.0):
            raise ValueError("task='quantile' needs quantile_alpha in (0, 1)")

    def _build(self, columns: Sequence[str], n_classes: int | None):
        self._validate()
        mono = resolve_monotone_constraints(self.monotone_constraints, columns)
        has_mono = any(m != 0 for m in mono)
        extra = dict(self.extra or {})
        q = None if self.quantile_alpha is None else float(self.quantile_alpha)
        if self.kind == "lightgbm":
            import lightgbm as lgb

            if has_mono and self.task == "quantile":
                raise ValueError("LightGBM cannot combine monotone_constraints with the quantile objective; "
                                 "use kind='xgboost' or 'catboost' for constrained quantile models")
            params = {"n_estimators": self.n_estimators, "learning_rate": self.learning_rate, "max_depth": self.max_depth,
                          "num_leaves": min(2 ** self.max_depth - 1, 31), "random_state": self.seed, "n_jobs": self.n_jobs,
                          "deterministic": True, "force_col_wise": True, "verbose": -1, "min_child_samples": 5}
            if has_mono:
                params.update(monotone_constraints=mono, monotone_constraints_method="intermediate")
            params.update(extra)
            if self.task == "classification":
                return lgb.LGBMClassifier(**params)
            if self.task == "quantile":
                return lgb.LGBMRegressor(objective="quantile", alpha=q, **params)
            return lgb.LGBMRegressor(objective="regression", **params)
        if self.kind == "xgboost":
            import xgboost as xgb

            params = {"n_estimators": self.n_estimators, "learning_rate": self.learning_rate, "max_depth": self.max_depth,
                          "random_state": self.seed, "n_jobs": self.n_jobs, "tree_method": "hist", "verbosity": 0,
                          "monotone_constraints": tuple(mono)}
            params.update(extra)
            if self.task == "classification":
                return xgb.XGBClassifier(**params)
            if self.task == "quantile":
                return xgb.XGBRegressor(objective="reg:quantileerror", quantile_alpha=q, **params)
            return xgb.XGBRegressor(objective="reg:squarederror", **params)
        import catboost as cb

        params = {"iterations": self.n_estimators, "learning_rate": self.learning_rate, "depth": self.max_depth,
                      "random_seed": self.seed, "thread_count": self.n_jobs, "verbose": False, "allow_writing_files": False,
                      "monotone_constraints": mono}
        params.update(extra)
        if self.task == "classification":
            loss = "MultiClass" if (n_classes or 2) > 2 else "Logloss"
            return cb.CatBoostClassifier(loss_function=loss, **params)
        if self.task == "quantile":
            return cb.CatBoostRegressor(loss_function=f"Quantile:alpha={q}", **params)
        return cb.CatBoostRegressor(loss_function="RMSE", **params)

    @staticmethod
    def _as_matrix(X) -> np.ndarray:
        if isinstance(X, pd.DataFrame):
            return X.to_numpy(dtype=float)
        return np.asarray(X, dtype=float)


class GBDTRegressor(_GBDTBase, RegressorMixin):
    """Gradient-boosted regression (or quantile regression) with name-resolved monotone constraints.

    Attributes after fit: ``model_`` (backend estimator), ``feature_names_in_``, ``monotone_resolved_``.
    Serves protocol 9 (BP workhorse, E3) and 10 (quantile intervals when ``task='quantile'``).
    """

    def fit(self, X, y):
        cols = _columns_of(X)
        self.feature_names_in_ = np.asarray(cols, dtype=object)
        self.n_features_in_ = len(cols)
        self.monotone_resolved_ = resolve_monotone_constraints(self.monotone_constraints, cols)
        self.model_ = self._build(cols, None)
        self.model_.fit(self._as_matrix(X), np.asarray(y, dtype=float))
        return self

    def predict(self, X):
        return np.asarray(self.model_.predict(self._as_matrix(X)), dtype=float).ravel()


class GBDTClassifier(_GBDTBase, ClassifierMixin):
    """Gradient-boosted classification (AF versus sinus, E7; screening, E12) with monotone constraints.

    Labels are encoded internally so every backend sees 0..K-1; ``classes_`` restores the originals.
    """

    def fit(self, X, y):
        cols = _columns_of(X)
        self.feature_names_in_ = np.asarray(cols, dtype=object)
        self.n_features_in_ = len(cols)
        self.monotone_resolved_ = resolve_monotone_constraints(self.monotone_constraints, cols)
        self.label_encoder_ = LabelEncoder().fit(np.asarray(y))
        self.classes_ = self.label_encoder_.classes_
        y_enc = self.label_encoder_.transform(np.asarray(y))
        self.model_ = self._build(cols, len(self.classes_))
        self.model_.fit(self._as_matrix(X), y_enc)
        return self

    def predict_proba(self, X):
        p = np.asarray(self.model_.predict_proba(self._as_matrix(X)), dtype=float)
        if p.ndim == 1:
            p = np.column_stack([1.0 - p, p])
        return p

    def predict(self, X):
        return self.classes_[np.argmax(self.predict_proba(X), axis=1)]


def make_gbdt(kind: str = "lightgbm", task: str = "regression", quantile_alpha: float | None = None,
              monotone_constraints: Mapping[str, int] | None = None, seed: int = 0, n_estimators: int = 50,
              learning_rate: float = 0.1, max_depth: int = 4, n_jobs: int = 2, **extra):
    """Build a GBDT estimator.

    kind: ``lightgbm`` | ``xgboost`` | ``catboost``; task: ``regression`` | ``classification`` |
    ``quantile`` (needs ``quantile_alpha``); ``monotone_constraints``: ``{column_name: +1 | -1 | 0}``.
    Extra keyword arguments are forwarded to the backend. Serves protocol 9.
    """
    cls = GBDTClassifier if task == "classification" else GBDTRegressor
    return cls(kind=kind, task=task, quantile_alpha=quantile_alpha, monotone_constraints=monotone_constraints,
               seed=seed, n_estimators=n_estimators, learning_rate=learning_rate, max_depth=max_depth,
               n_jobs=n_jobs, extra=extra or None)


# --------------------------------------------------------------------------- linear baselines
def make_linear(kind: str = "ridge", task: str = "regression", alpha: float = 1.0, l1_ratio: float = 0.5,
                seed: int = 0, max_iter: int = 5000) -> Pipeline:
    """Standard-scaled ridge or elastic-net baseline (protocol 9).

    Regression: ``Ridge(alpha)`` or ``ElasticNet(alpha, l1_ratio)``. Classification: logistic regression
    with an L2 penalty (ridge) or elastic-net penalty via saga (``C = 1/alpha``).
    """
    if kind not in ("ridge", "elastic_net"):
        raise ValueError("kind must be 'ridge' or 'elastic_net'")
    if task == "regression":
        model = Ridge(alpha=alpha) if kind == "ridge" else ElasticNet(alpha=alpha, l1_ratio=l1_ratio,
                                                                       max_iter=max_iter, random_state=seed)
    elif task == "classification":
        C = 1.0 / max(alpha, 1e-12)
        if kind == "ridge":
            model = LogisticRegression(C=C, max_iter=max_iter)
        else:
            model = LogisticRegression(solver="saga", l1_ratio=l1_ratio, C=C, max_iter=max_iter, random_state=seed)
    else:
        raise ValueError("task must be 'regression' or 'classification'")
    return make_pipeline(StandardScaler(), model)


def make_ridge(alpha: float = 1.0, task: str = "regression") -> Pipeline:
    """Ridge baseline behind a StandardScaler (protocol 9)."""
    return make_linear("ridge", task, alpha=alpha)


def make_elastic_net(alpha: float = 0.1, l1_ratio: float = 0.5, task: str = "regression", seed: int = 0) -> Pipeline:
    """Elastic-net baseline behind a StandardScaler (protocol 9)."""
    return make_linear("elastic_net", task, alpha=alpha, l1_ratio=l1_ratio, seed=seed)


# --------------------------------------------------------------------------- quantile pairs
class QuantileIntervalRegressor(BaseEstimator, RegressorMixin):
    """A lower/upper quantile pair (optionally a median) giving a (1 - alpha) prediction interval.

    ``predict`` returns the median when available, else the interval mid-point. ``predict_interval``
    returns ``(lo, hi)`` with crossings repaired by sorting; the crossing rate seen at the last call is
    stored in ``crossing_rate_``. Serves protocol 10 (intervals; abstain by width via
    ``uncertainty.AbstainPolicy``).
    """

    def __init__(self, lower, upper, median=None, alpha: float = 0.1):
        self.lower = lower
        self.upper = upper
        self.median = median
        self.alpha = alpha

    def fit(self, X, y):
        y = np.asarray(y, dtype=float)
        self.lower_ = clone(self.lower).fit(X, y)
        self.upper_ = clone(self.upper).fit(X, y)
        self.median_ = clone(self.median).fit(X, y) if self.median is not None else None
        return self

    def predict_interval(self, X) -> tuple[np.ndarray, np.ndarray]:
        lo = np.asarray(self.lower_.predict(X), dtype=float).ravel()
        hi = np.asarray(self.upper_.predict(X), dtype=float).ravel()
        crossed = lo > hi
        self.crossing_rate_ = float(np.mean(crossed)) if lo.size else 0.0
        return np.minimum(lo, hi), np.maximum(lo, hi)

    def predict(self, X) -> np.ndarray:
        if self.median_ is not None:
            return np.asarray(self.median_.predict(X), dtype=float).ravel()
        lo, hi = self.predict_interval(X)
        return 0.5 * (lo + hi)


def _linear_quantile(q: float, l1_penalty: float) -> Pipeline:
    return make_pipeline(StandardScaler(), QuantileRegressor(quantile=q, alpha=l1_penalty, solver="highs"))


def make_quantile_pair(alpha: float = 0.1, kind: str = "linear", seed: int = 0, l1_penalty: float = 0.0,
                       with_median: bool = True, **gbdt_kw) -> QuantileIntervalRegressor:
    """Quantile pair at ``alpha/2`` and ``1 - alpha/2`` (plus the median) for a (1 - alpha) interval.

    ``kind='linear'`` uses sklearn ``QuantileRegressor`` (pinball loss, L1 penalty ``l1_penalty``) behind
    standard scaling; any GBDT kind uses ``make_gbdt(task='quantile')``. Serves protocol 10.
    """
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be in (0, 1)")
    lo_q, hi_q = alpha / 2.0, 1.0 - alpha / 2.0
    if kind == "linear":
        lower, upper = _linear_quantile(lo_q, l1_penalty), _linear_quantile(hi_q, l1_penalty)
        median = _linear_quantile(0.5, l1_penalty) if with_median else None
    else:
        lower = make_gbdt(kind, "quantile", quantile_alpha=lo_q, seed=seed, **gbdt_kw)
        upper = make_gbdt(kind, "quantile", quantile_alpha=hi_q, seed=seed, **gbdt_kw)
        median = make_gbdt(kind, "quantile", quantile_alpha=0.5, seed=seed, **gbdt_kw) if with_median else None
    return QuantileIntervalRegressor(lower, upper, median, alpha=alpha)


# --------------------------------------------------------------------------- mandatory baselines
class PredictMeanBaseline(BaseEstimator):
    """Predict-the-mean baseline required in every results table (protocol 9 E0, 11.2).

    regression: predicts the training mean of ``y`` (units of ``y``); classification: predicts the
    majority class and the class priors as probabilities. Ignores ``X`` entirely.
    """

    def __init__(self, task: str = "regression"):
        self.task = task

    def fit(self, X, y):
        y = np.asarray(y)
        if self.task == "regression":
            self.mean_ = float(np.nanmean(y.astype(float)))
        elif self.task == "classification":
            self.classes_, counts = np.unique(y, return_counts=True)
            self.prior_ = counts / counts.sum()
            self.majority_ = self.classes_[int(np.argmax(counts))]
        else:
            raise ValueError("task must be 'regression' or 'classification'")
        self.n_features_in_ = int(X.shape[1]) if hasattr(X, "shape") and len(getattr(X, "shape", ())) == 2 else 0
        return self

    def predict(self, X):
        n = len(X)
        if self.task == "regression":
            return np.full(n, self.mean_, dtype=float)
        return np.full(n, self.majority_, dtype=self.classes_.dtype)

    def predict_proba(self, X):
        if self.task != "classification":
            raise AttributeError("predict_proba only for task='classification'")
        return np.tile(self.prior_, (len(X), 1))

    def _more_tags(self):
        return {"requires_y": True}


class DemographicsOnlyBaseline(BaseEstimator):
    """Demographics-only baseline required in every results table (protocol 9 E0, 11.2, go/no-go E5).

    Uses only ``columns`` (default age, sex, bmi; configurable through ``models.demographics_columns``).
    Numeric columns: median imputation + standard scaling; categorical/boolean columns: most-frequent
    imputation + one-hot. Default estimator: ridge (regression) or L2 logistic regression
    (classification); pass ``estimator`` to override. Missing columns raise ``KeyError``.
    """

    def __init__(self, columns: Sequence[str] = DEFAULT_DEMOGRAPHIC_COLUMNS, task: str = "regression",
                 estimator=None, alpha: float = 1.0):
        self.columns = tuple(columns)
        self.task = task
        self.estimator = estimator
        self.alpha = alpha

    def _frame(self, X) -> pd.DataFrame:
        if not isinstance(X, pd.DataFrame):
            raise TypeError("DemographicsOnlyBaseline needs a DataFrame with the demographic columns")
        missing = [c for c in self.columns if c not in X.columns]
        if missing:
            raise KeyError(f"demographic column(s) missing: {missing}")
        return X[list(self.columns)]

    def fit(self, X, y):
        F = self._frame(X)
        num = [c for c in F.columns if pd.api.types.is_numeric_dtype(F[c]) and not pd.api.types.is_bool_dtype(F[c])]
        cat = [c for c in F.columns if c not in num]
        transformers = []
        if num:
            transformers.append(("num", make_pipeline(SimpleImputer(strategy="median"), StandardScaler()), num))
        if cat:
            transformers.append(("cat", make_pipeline(SimpleImputer(strategy="most_frequent"),
                                                      OneHotEncoder(handle_unknown="ignore")), cat))
        pre = ColumnTransformer(transformers, remainder="drop")
        if self.estimator is not None:
            est = clone(self.estimator)
        elif self.task == "regression":
            est = Ridge(alpha=self.alpha)
        elif self.task == "classification":
            est = LogisticRegression(C=1.0 / max(self.alpha, 1e-12), max_iter=5000)
        else:
            raise ValueError("task must be 'regression' or 'classification'")
        Fc = F.copy()
        for c in cat:
            Fc[c] = Fc[c].astype(object)
        self.pipeline_ = Pipeline([("pre", pre), ("est", est)]).fit(Fc, np.asarray(y))
        self.numeric_columns_, self.categorical_columns_ = num, cat
        if hasattr(est, "classes_"):
            self.classes_ = est.classes_
        return self

    def _prep(self, X) -> pd.DataFrame:
        F = self._frame(X).copy()
        for c in self.categorical_columns_:
            F[c] = F[c].astype(object)
        return F

    def predict(self, X):
        return self.pipeline_.predict(self._prep(X))

    def predict_proba(self, X):
        return self.pipeline_.predict_proba(self._prep(X))


__all__ = [
    "DEFAULT_DEMOGRAPHIC_COLUMNS",
    "GBDT_KINDS",
    "TASKS",
    "DemographicsOnlyBaseline",
    "GBDTClassifier",
    "GBDTRegressor",
    "PredictMeanBaseline",
    "QuantileIntervalRegressor",
    "make_elastic_net",
    "make_gbdt",
    "make_linear",
    "make_quantile_pair",
    "make_ridge",
    "resolve_monotone_constraints",
]
