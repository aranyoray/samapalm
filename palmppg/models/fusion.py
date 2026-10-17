"""Multimodal fusion (protocol section 9 "late-fusion and cross-attention multimodal models").

* ``LateFusion``: base estimators (one per modality or model family) whose predictions are combined by
  a ridge regression fitted on **out-of-fold** predictions (participant-grouped folds when ``groups``
  are given, protocol 11.1), so the fusion weights never see in-sample predictions. Each base is then
  refitted on all data.
* ``TorchCrossAttentionRegressor``: two modality token sets (e.g. beat-morphology tokens and IBI tokens,
  or Pi and phone pulse windows) fused by cross-attention (``nets.fusion.CrossAttentionFusion``).
"""
from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, clone
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.model_selection import GroupKFold, KFold

from palmppg.models._torchbase import (
    TorchEstimator,
    as_sequence_list,
    channel_stats,
    pad_sequences,
    standardise,
)


def _select(X, name: str):
    if isinstance(X, Mapping):
        if name not in X:
            raise KeyError(f"no input for estimator '{name}' (have {list(X)})")
        return X[name]
    return X


def _subset(X, idx: np.ndarray):
    if isinstance(X, (pd.DataFrame, pd.Series)):
        return X.iloc[idx]
    if isinstance(X, np.ndarray):
        return X[idx]
    return [X[i] for i in idx]


class LateFusion(BaseEstimator):
    """Late fusion of named estimators with ridge-learned weights on out-of-fold predictions.

    ``X`` may be one DataFrame shared by all bases or a dict ``{name: X_name}`` with one input per base.
    ``fit(X, y, groups=None)``: ``groups`` (study_id) selects ``GroupKFold``; without groups a shuffled
    ``KFold`` with ``seed`` is used. ``task='regression'`` combines with ``Ridge(ridge_alpha)``
    (``positive=True`` when ``nonnegative``); ``task='classification'`` (binary) combines positive-class
    probabilities with a logistic regression. After fit: ``weights_`` (dict name -> coefficient),
    ``intercept_``, ``oof_predictions_`` (n, k) for audits.
    """

    def __init__(self, estimators: Mapping[str, BaseEstimator], n_splits: int = 5, seed: int = 0,
                 ridge_alpha: float = 1.0, nonnegative: bool = False, task: str = "regression"):
        self.estimators = estimators
        self.n_splits = n_splits
        self.seed = seed
        self.ridge_alpha = ridge_alpha
        self.nonnegative = nonnegative
        self.task = task

    def _base_pred(self, est, X) -> np.ndarray:
        if self.task == "classification":
            return np.asarray(est.predict_proba(X))[:, 1]
        return np.asarray(est.predict(X), dtype=float).ravel()

    def fit(self, X, y, groups=None):
        names = list(self.estimators)
        y = np.asarray(y)
        n = len(y)
        if groups is not None:
            splitter = GroupKFold(n_splits=min(self.n_splits, len(np.unique(groups))))
            folds = list(splitter.split(np.zeros(n), y, groups))
        else:
            folds = list(KFold(n_splits=min(self.n_splits, n), shuffle=True, random_state=self.seed).split(np.zeros(n)))
        oof = np.full((n, len(names)), np.nan)
        for j, name in enumerate(names):
            Xj = _select(X, name)
            for tr, te in folds:
                est = clone(self.estimators[name]).fit(_subset(Xj, tr), y[tr])
                oof[te, j] = self._base_pred(est, _subset(Xj, te))
        self.oof_predictions_ = oof
        if self.task == "regression":
            comb = Ridge(alpha=self.ridge_alpha, positive=self.nonnegative).fit(oof, y.astype(float))
        elif self.task == "classification":
            comb = LogisticRegression(max_iter=2000).fit(oof, y)
            self.classes_ = comb.classes_
        else:
            raise ValueError("task must be 'regression' or 'classification'")
        self.combiner_ = comb
        coef = np.asarray(comb.coef_).ravel()
        self.weights_ = {name: float(c) for name, c in zip(names, coef)}
        self.intercept_ = float(np.asarray(comb.intercept_).ravel()[0])
        self.estimators_ = {name: clone(self.estimators[name]).fit(_select(X, name), y) for name in names}
        return self

    def _stack(self, X) -> np.ndarray:
        return np.column_stack([self._base_pred(est, _select(X, name)) for name, est in self.estimators_.items()])

    def predict(self, X):
        return self.combiner_.predict(self._stack(X))

    def predict_proba(self, X):
        if self.task != "classification":
            raise AttributeError("predict_proba only for task='classification'")
        return self.combiner_.predict_proba(self._stack(X))


class TorchCrossAttentionRegressor(TorchEstimator):
    """Cross-attention fusion wrapper: ``fit((tokens_a, tokens_b), y)`` where each is a list of
    ``(T_i, C)`` arrays (lengths may differ between modalities). ``model_kw`` goes to
    ``nets.fusion.CrossAttentionFusion`` (d_model, n_heads, dropout)."""

    def __init__(self, epochs: int = 30, lr: float = 1e-3, seed: int = 0, device: str = "cpu", batch_size: int = 32,
                 weight_decay: float = 1e-4, task: str = "regression", grad_clip: float = 1.0, verbose: bool = False,
                 model_kw: dict | None = None):
        super().__init__(model_fn=None, epochs=epochs, lr=lr, seed=seed, device=device, batch_size=batch_size,
                         weight_decay=weight_decay, task=task, grad_clip=grad_clip, verbose=verbose)
        self.model_kw = model_kw

    @staticmethod
    def _pair(X) -> tuple[list[np.ndarray], list[np.ndarray]]:
        if not isinstance(X, (tuple, list)) or len(X) != 2:
            raise ValueError("input must be a pair (tokens_a, tokens_b) of sequence lists")
        a, b = as_sequence_list(X[0]), as_sequence_list(X[1])
        if len(a) != len(b):
            raise ValueError("both modalities need the same number of samples")
        return a, b

    def _encode_fit(self, X):
        a, b = self._pair(X)
        self.a_mean_, self.a_std_ = channel_stats(a)
        self.b_mean_, self.b_std_ = channel_stats(b)
        return list(zip(standardise(a, self.a_mean_, self.a_std_), standardise(b, self.b_mean_, self.b_std_)))

    def _encode(self, X):
        a, b = self._pair(X)
        return list(zip(standardise(a, self.a_mean_, self.a_std_), standardise(b, self.b_mean_, self.b_std_)))

    def _collate(self, samples):
        torch = self._torch()
        xa, ma = pad_sequences([s[0] for s in samples])
        xb, mb = pad_sequences([s[1] for s in samples])
        return {"xa": torch.from_numpy(xa), "xb": torch.from_numpy(xb), "mask_a": torch.from_numpy(ma),
                "mask_b": torch.from_numpy(mb)}

    def _build_module(self, sample, out_dim: int):
        from palmppg.models.nets.fusion import CrossAttentionFusion

        return CrossAttentionFusion(int(sample[0].shape[1]), int(sample[1].shape[1]), out_dim, **(self.model_kw or {}))


def make_cross_attention_regressor(**kw) -> TorchCrossAttentionRegressor:
    return TorchCrossAttentionRegressor(**kw)


__all__ = ["LateFusion", "TorchCrossAttentionRegressor", "make_cross_attention_regressor"]
