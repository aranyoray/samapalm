"""Shared sklearn-like wrapper for the torch models in this package (protocol section 9).

``TorchEstimator`` owns seeding, target standardisation, the training loop, batched prediction,
stochastic (MC-dropout) passes and embedding extraction. Subclasses only say how their inputs are
encoded and collated and how the ``nn.Module`` is built. ``torch`` is imported inside methods so
the public modules import cleanly without it (CONTRACTS section 0.5).

Determinism: ``torch.manual_seed`` is set from ``core.config.rng(seed, salt)`` at fit and at every
stochastic prediction; mini-batch order comes from ``rng(seed, 'epoch:<i>')``. On CPU with a fixed
thread count the same seed gives the same weights.
"""
from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.base import BaseEstimator
from sklearn.preprocessing import LabelEncoder

from palmppg.core.config import rng


def derived_seed(seed: int, salt: str) -> int:
    return int(rng(seed, salt).integers(0, 2**31 - 1))


class TorchEstimator(BaseEstimator):
    """Base class: ``fit(X, y)``, ``predict``, ``predict_proba``, ``predict_samples``, ``transform``.

    Parameters: ``model_fn`` (subclass-specific builder or architecture name), ``epochs``, ``lr``,
    ``seed``, ``device``, ``batch_size``, ``weight_decay``, ``task`` (regression | classification),
    ``grad_clip`` (max gradient norm, 0 disables), ``verbose``.
    Regression targets are standardised with the training mean and SD and de-standardised on output,
    so predictions are in the units of ``y``.
    """

    def __init__(self, model_fn=None, epochs: int = 30, lr: float = 1e-3, seed: int = 0, device: str = "cpu",
                 batch_size: int = 32, weight_decay: float = 1e-4, task: str = "regression", grad_clip: float = 1.0,
                 verbose: bool = False):
        self.model_fn = model_fn
        self.epochs = epochs
        self.lr = lr
        self.seed = seed
        self.device = device
        self.batch_size = batch_size
        self.weight_decay = weight_decay
        self.task = task
        self.grad_clip = grad_clip
        self.verbose = verbose

    # ------------------------------------------------------------------ hooks for subclasses
    def _encode_fit(self, X) -> list[Any]:
        raise NotImplementedError

    def _encode(self, X) -> list[Any]:
        raise NotImplementedError

    def _collate(self, samples: list[Any]) -> dict:
        raise NotImplementedError

    def _build_module(self, sample: Any, out_dim: int):
        raise NotImplementedError

    def _forward(self, module, batch: dict):
        return module(**batch)

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _torch():
        import torch

        return torch

    def _seed_torch(self, salt: str = "fit") -> None:
        self._torch().manual_seed(derived_seed(self.seed, salt))

    def _dev(self):
        return self._torch().device(self.device)

    def _prepare_targets(self, y):
        torch = self._torch()
        if self.task == "regression":
            yv = np.asarray(y, dtype=float)
            if yv.ndim == 1:
                yv = yv[:, None]
            self.y_mean_ = yv.mean(axis=0)
            self.y_std_ = np.maximum(yv.std(axis=0), 1e-8)
            self.out_dim_ = int(yv.shape[1])
            t = torch.from_numpy(((yv - self.y_mean_) / self.y_std_).astype(np.float32))
        elif self.task == "classification":
            self.label_encoder_ = LabelEncoder().fit(np.asarray(y))
            self.classes_ = self.label_encoder_.classes_
            self.out_dim_ = len(self.classes_)
            t = torch.from_numpy(self.label_encoder_.transform(np.asarray(y)).astype(np.int64))
        else:
            raise ValueError("task must be 'regression' or 'classification'")
        return t

    def _loss_fn(self):
        torch = self._torch()
        return torch.nn.MSELoss() if self.task == "regression" else torch.nn.CrossEntropyLoss()

    def _to_device(self, batch: dict) -> dict:
        dev = self._dev()
        return {k: (v.to(dev) if hasattr(v, "to") else v) for k, v in batch.items()}

    # ------------------------------------------------------------------ training
    def fit(self, X, y, **fit_params):
        torch = self._torch()
        self._seed_torch("fit")
        samples = self._encode_fit(X)
        targets = self._prepare_targets(y)
        n = len(samples)
        if n != int(targets.shape[0]):
            raise ValueError(f"X has {n} samples but y has {targets.shape[0]}")
        self.module_ = self._build_module(samples[0], self.out_dim_).to(self._dev())
        self.n_parameters_ = int(sum(p.numel() for p in self.module_.parameters()))
        opt = torch.optim.AdamW(self.module_.parameters(), lr=self.lr, weight_decay=self.weight_decay)
        loss_fn = self._loss_fn()
        bs = max(1, min(int(self.batch_size), n))
        self.history_: list[float] = []
        self.module_.train()
        for epoch in range(int(self.epochs)):
            perm = rng(self.seed, f"epoch:{epoch}").permutation(n)
            total, seen = 0.0, 0
            for start in range(0, n, bs):
                idx = perm[start:start + bs]
                if idx.size == 1 and n > 1:
                    continue  # BatchNorm cannot normalise a single sample; the sample returns in a later epoch
                batch = self._to_device(self._collate([samples[i] for i in idx]))
                tgt = targets[idx].to(self._dev())
                out = self._forward(self.module_, batch)
                loss = loss_fn(out, tgt)
                opt.zero_grad()
                loss.backward()
                if self.grad_clip and self.grad_clip > 0:
                    torch.nn.utils.clip_grad_norm_(self.module_.parameters(), self.grad_clip)
                opt.step()
                total += float(loss.item()) * idx.size
                seen += idx.size
            self.history_.append(total / max(seen, 1))
            if self.verbose:
                print(f"epoch {epoch + 1}/{self.epochs} loss {self.history_[-1]:.4f}")
        self.module_.eval()
        self.is_fitted_ = True
        return self

    # ------------------------------------------------------------------ inference
    def _predict_raw(self, X, stochastic: bool = False, embed: bool = False) -> np.ndarray:
        torch = self._torch()
        samples = self._encode(X)
        self.module_.eval()
        if stochastic:
            for m in self.module_.modules():
                if isinstance(m, torch.nn.Dropout):
                    m.train()
        outs = []
        bs = max(1, int(self.batch_size))
        with torch.no_grad():
            for start in range(0, len(samples), bs):
                batch = self._to_device(self._collate(samples[start:start + bs]))
                if embed:
                    out = self.module_.embed(**batch)
                else:
                    out = self._forward(self.module_, batch)
                    if isinstance(out, (tuple, list)):
                        out = out[0]
                outs.append(out.detach().cpu().numpy())
        self.module_.eval()
        return np.concatenate(outs, axis=0) if outs else np.zeros((0, self.out_dim_), dtype=np.float32)

    def _decode(self, raw: np.ndarray) -> np.ndarray:
        if self.task == "regression":
            y = raw.astype(float) * self.y_std_ + self.y_mean_
            return y[:, 0] if self.out_dim_ == 1 else y
        return self.classes_[np.argmax(raw, axis=1)]

    def predict(self, X):
        return self._decode(self._predict_raw(X))

    def predict_proba(self, X):
        if self.task != "classification":
            raise AttributeError("predict_proba is only defined for task='classification'")
        logits = self._predict_raw(X).astype(float)
        logits -= logits.max(axis=1, keepdims=True)
        p = np.exp(logits)
        return p / p.sum(axis=1, keepdims=True)

    def predict_samples(self, X, n_samples: int = 20, seed: int | None = None) -> np.ndarray:
        """``n_samples`` MC-dropout passes: (n_samples, N) predictions in target units for regression,
        (n_samples, N, K) class probabilities for classification. Protocol 10."""
        torch = self._torch()
        base = self.seed if seed is None else seed
        out = []
        for i in range(int(n_samples)):
            torch.manual_seed(derived_seed(base, f"mc:{i}"))
            raw = self._predict_raw(X, stochastic=True)
            if self.task == "regression":
                out.append(self._decode(raw))
            else:
                z = raw.astype(float) - raw.max(axis=1, keepdims=True)
                p = np.exp(z)
                out.append(p / p.sum(axis=1, keepdims=True))
        return np.stack(out)

    def transform(self, X) -> np.ndarray:
        """Pooled embeddings from the module's ``embed`` method (N, D)."""
        if not hasattr(self.module_, "embed"):
            raise AttributeError(f"{type(self.module_).__name__} has no embed()")
        return self._predict_raw(X, embed=True)


# ---------------------------------------------------------------------- sequence helpers (numpy only)
def as_sequence_list(X) -> list[np.ndarray]:
    """Normalise sequence input to a list of float32 arrays (T_i, C)."""
    if isinstance(X, np.ndarray) and X.ndim == 3:
        return [np.asarray(x, dtype=np.float32) for x in X]
    out = []
    for x in X:
        a = np.asarray(x, dtype=np.float32)
        if a.ndim == 1:
            a = a[:, None]
        if a.ndim != 2 or a.shape[0] == 0:
            raise ValueError(f"each sequence must be (T, C) with T >= 1, got shape {a.shape}")
        out.append(a)
    if not out:
        raise ValueError("empty input")
    return out


def pad_sequences(seqs: list[np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    """Zero-pad to (B, T_max, C) and return the validity mask (B, T_max), True on real steps."""
    B = len(seqs)
    T = max(s.shape[0] for s in seqs)
    C = seqs[0].shape[1]
    x = np.zeros((B, T, C), dtype=np.float32)
    mask = np.zeros((B, T), dtype=bool)
    for i, s in enumerate(seqs):
        x[i, : s.shape[0]] = s
        mask[i, : s.shape[0]] = True
    return x, mask


def channel_stats(seqs: list[np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    """Per-channel mean and SD over every step of every training sequence (NaN-aware)."""
    cat = np.concatenate(seqs, axis=0)
    mean = np.nanmean(cat, axis=0)
    std = np.nanstd(cat, axis=0)
    return mean.astype(np.float32), np.maximum(std, 1e-6).astype(np.float32)


def standardise(seqs: list[np.ndarray], mean: np.ndarray, std: np.ndarray) -> list[np.ndarray]:
    out = []
    for s in seqs:
        z = (s - mean) / std
        out.append(np.nan_to_num(z, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32))
    return out


__all__ = ["TorchEstimator", "as_sequence_list", "channel_stats", "derived_seed", "pad_sequences", "standardise"]
