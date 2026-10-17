"""Domain-adversarial features (DANN, Ganin et al. 2016) against unit, operator, department and camera
labels (protocol section 9 "domain-adversarial features against unit, operator, department and camera";
E11 shortcut audit).

The feature extractor is trained so that the label head predicts the endpoint while a domain head
behind a gradient-reversal layer *fails* to predict the nuisance label. A low domain accuracy of a
fresh probe on the embeddings is the point: it says the embedding carries little unit/operator/dept/
camera information. ``probe_domain_accuracy`` is the honest measurement (a logistic-regression probe
scored under stratified K-fold on the embeddings), reported next to the chance level.
"""
from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import LabelEncoder, StandardScaler

from palmppg.core.config import rng
from palmppg.core.tracks import CAMERAS, REGISTRY, FeatureRegistry
from palmppg.models._torchbase import (
    TorchEstimator,
    as_sequence_list,
    channel_stats,
    pad_sequences,
    standardise,
)

METHOD = "dann"


def _as_tabular(X) -> np.ndarray:
    if isinstance(X, pd.DataFrame):
        return X.to_numpy(dtype=np.float32)
    return np.asarray(X, dtype=np.float32)


class DANNEstimator(TorchEstimator):
    """DANN wrapper: ``fit(X, y, domains)``, ``predict``, ``transform`` (domain-invariant embeddings),
    ``domain_accuracy`` (internal head) and ``probe_domain_accuracy`` (external probe).

    ``extractor``: ``'mlp'`` for tabular ``X`` (N, D) or ``'conv1d'``/``'tcn'``/``'gru'`` for lists of
    ``(T, C)`` sequences. ``lambda_domain`` scales the reversed gradient; ``lambda_schedule='ramp'`` follows
    Ganin's ``2 / (1 + exp(-10 p)) - 1`` warm-up over training progress ``p``; ``'constant'`` applies
    ``lambda_domain`` from the first step; ``lambda_domain=0`` is the no-adversary baseline.
    ``domain_hidden=0`` uses a linear domain head (the matched adversary for the linear probe of E11);
    ``> 0`` uses a two-layer head of that width. The domain head is kept close to its optimum against the
    current embedding (``domain_steps`` head-only updates per batch at ``lr * domain_lr_mult``) so that the
    reversed gradient removes domain information instead of merely mis-leading a stale head.
    After ``fit``: ``domain_classes_``, ``domain_chance_`` (largest domain prior), ``domain_accuracy_``
    (internal head on the training data).
    """

    def __init__(self, extractor: str = "mlp", emb_dim: int = 16, hidden: int = 64, lambda_domain: float = 1.0,
                 lambda_schedule: str = "constant", domain_hidden: int = 0, domain_lr_mult: float = 10.0,
                 domain_steps: int = 2, epochs: int = 30, lr: float = 1e-3, seed: int = 0, device: str = "cpu",
                 batch_size: int = 32, weight_decay: float = 1e-4, task: str = "regression", grad_clip: float = 1.0,
                 verbose: bool = False, model_kw: dict | None = None):
        super().__init__(model_fn=None, epochs=epochs, lr=lr, seed=seed, device=device, batch_size=batch_size,
                         weight_decay=weight_decay, task=task, grad_clip=grad_clip, verbose=verbose)
        self.extractor = extractor
        self.emb_dim = emb_dim
        self.hidden = hidden
        self.lambda_domain = lambda_domain
        self.lambda_schedule = lambda_schedule
        self.domain_hidden = domain_hidden
        self.domain_lr_mult = domain_lr_mult
        self.domain_steps = domain_steps
        self.model_kw = model_kw

    # ------------------------------------------------------------------ encoding
    @property
    def _sequential(self) -> bool:
        return self.extractor != "mlp"

    def _encode_fit(self, X):
        if self._sequential:
            seqs = as_sequence_list(X)
            self.x_mean_, self.x_std_ = channel_stats(seqs)
            self.n_features_in_ = int(seqs[0].shape[1])
            return standardise(seqs, self.x_mean_, self.x_std_)
        A = _as_tabular(X)
        self.x_mean_ = np.nanmean(A, axis=0).astype(np.float32)
        self.x_std_ = np.maximum(np.nanstd(A, axis=0), 1e-6).astype(np.float32)
        self.n_features_in_ = int(A.shape[1])
        return list(np.nan_to_num((A - self.x_mean_) / self.x_std_).astype(np.float32))

    def _encode(self, X):
        if self._sequential:
            return standardise(as_sequence_list(X), self.x_mean_, self.x_std_)
        A = _as_tabular(X)
        return list(np.nan_to_num((A - self.x_mean_) / self.x_std_).astype(np.float32))

    def _collate(self, samples):
        torch = self._torch()
        if self._sequential:
            x, mask = pad_sequences(samples)
            return {"x": torch.from_numpy(x), "mask": torch.from_numpy(mask)}
        return {"x": torch.from_numpy(np.stack(samples))}

    def _build_module(self, sample, out_dim: int):
        from palmppg.models.nets.adversarial import DANN, MLPExtractor

        kw = dict(self.model_kw or {})
        if self._sequential:
            from palmppg.models.nets.temporal import make_model

            backbone = make_model(self.extractor, int(sample.shape[1]), self.emb_dim, **kw)
            extractor = _SequenceExtractor(backbone, self.emb_dim)
        else:
            extractor = MLPExtractor(int(sample.shape[0]), self.emb_dim, self.hidden, kw.get("dropout", 0.1))
        return DANN(extractor, out_dim, self.n_domains_, hidden=self.hidden, dropout=kw.get("dropout", 0.1),
                    domain_hidden=self.domain_hidden)

    def _forward(self, module, batch):
        return module(**batch)[0]

    def _lambda(self, progress: float) -> float:
        if self.lambda_schedule == "constant":
            return float(self.lambda_domain)
        return float(self.lambda_domain) * (2.0 / (1.0 + np.exp(-10.0 * progress)) - 1.0)

    # ------------------------------------------------------------------ training
    def fit(self, X, y, domains=None, **fit_params):
        if domains is None:
            raise ValueError("DANNEstimator.fit needs domains (unit, operator, dept or camera labels)")
        torch = self._torch()
        self._seed_torch("fit")
        samples = self._encode_fit(X)
        targets = self._prepare_targets(y)
        self.domain_encoder_ = LabelEncoder().fit(np.asarray(domains))
        self.domain_classes_ = self.domain_encoder_.classes_
        d_idx = self.domain_encoder_.transform(np.asarray(domains)).astype(np.int64)
        self.n_domains_ = len(self.domain_classes_)
        counts = np.bincount(d_idx, minlength=self.n_domains_)
        self.domain_chance_ = float(counts.max() / counts.sum())
        d_t = torch.from_numpy(d_idx)
        n = len(samples)
        self.module_ = self._build_module(samples[0], self.out_dim_).to(self._dev())
        head_params = list(self.module_.domain_head.parameters())
        head_ids = {id(p) for p in head_params}
        other_params = [p for p in self.module_.parameters() if id(p) not in head_ids]
        opt = torch.optim.AdamW([{"params": other_params, "lr": self.lr},
                                 {"params": head_params, "lr": self.lr * self.domain_lr_mult}],
                                weight_decay=self.weight_decay)
        opt_head = torch.optim.AdamW(head_params, lr=self.lr * self.domain_lr_mult, weight_decay=self.weight_decay)
        task_loss, dom_loss = self._loss_fn(), torch.nn.CrossEntropyLoss()
        bs = max(1, min(int(self.batch_size), n))
        self.history_, self.history_domain_ = [], []
        self.module_.train()
        n_steps = int(self.epochs) * max(1, (n + bs - 1) // bs)
        step = 0
        for epoch in range(int(self.epochs)):
            perm = rng(self.seed, f"epoch:{epoch}").permutation(n)
            tot, tot_d, seen = 0.0, 0.0, 0
            for start in range(0, n, bs):
                idx = perm[start:start + bs]
                if idx.size == 1 and n > 1:
                    continue
                lambd = self._lambda(step / max(n_steps - 1, 1))
                batch = self._to_device(self._collate([samples[i] for i in idx]))
                d_batch = d_t[idx].to(self._dev())
                for _ in range(int(self.domain_steps)):      # head-only updates on detached embeddings
                    with torch.no_grad():
                        z = self.module_.embed(**batch)
                    l_head = dom_loss(self.module_.domain_head(z), d_batch)
                    opt_head.zero_grad()
                    l_head.backward()
                    opt_head.step()
                y_hat, d_logits, _ = self.module_(**batch, lambd=lambd)
                lt = task_loss(y_hat, targets[idx].to(self._dev()))
                ld = dom_loss(d_logits, d_batch)
                loss = lt + ld
                opt.zero_grad()
                loss.backward()
                if self.grad_clip and self.grad_clip > 0:
                    torch.nn.utils.clip_grad_norm_(self.module_.parameters(), self.grad_clip)
                opt.step()
                tot += float(lt.item()) * idx.size
                tot_d += float(ld.item()) * idx.size
                seen += idx.size
                step += 1
            self.history_.append(tot / max(seen, 1))
            self.history_domain_.append(tot_d / max(seen, 1))
        self.module_.eval()
        self.is_fitted_ = True
        self.domain_accuracy_ = self.domain_accuracy(X, domains)
        return self

    # ------------------------------------------------------------------ audits
    def _domain_logits(self, X) -> np.ndarray:
        torch = self._torch()
        samples = self._encode(X)
        outs = []
        self.module_.eval()
        with torch.no_grad():
            for s in range(0, len(samples), max(1, int(self.batch_size))):
                batch = self._to_device(self._collate(samples[s:s + self.batch_size]))
                outs.append(self.module_(**batch)[1].cpu().numpy())
        return np.concatenate(outs)

    def domain_accuracy(self, X, domains) -> float:
        """Accuracy of the internal (adversarially trained) domain head on ``X``."""
        pred = self.domain_classes_[np.argmax(self._domain_logits(X), axis=1)]
        return float(np.mean(pred == np.asarray(domains)))

    def probe_domain_accuracy(self, X, domains, seed: int = 0, n_splits: int = 5) -> float:
        """Stratified K-fold accuracy of a fresh logistic-regression probe predicting ``domains`` from the
        embeddings ``transform(X)``: the number to report in E11 (low is good, compare with chance)."""
        Z = self.transform(X)
        d = np.asarray(domains)
        n_splits = max(2, min(n_splits, int(np.min(np.unique(d, return_counts=True)[1]))))
        cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
        probe = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=1.0))
        return float(np.mean(cross_val_score(probe, Z, d, cv=cv, scoring="accuracy")))


class _SequenceExtractor:
    """Adapter giving a sequence backbone the ``extractor(x, mask) -> embedding`` interface, with a linear
    projection from the backbone's pooled width to ``emb_dim``."""

    def __new__(cls, backbone, emb_dim: int):
        import torch

        class Wrapped(torch.nn.Module):
            def __init__(self, net, d):
                super().__init__()
                self.net = net
                self.proj = torch.nn.Sequential(torch.nn.Linear(net.embed_dim, d), torch.nn.ReLU())
                self.embed_dim = d

            def forward(self, x, mask=None):
                return self.proj(self.net.embed(x, mask))

        return Wrapped(backbone, emb_dim)


def feature_columns(camera: str, roi: str = "fused", dim: int = 16) -> list[str]:
    """``embedding__<camera>__<roi>__dann__d<i>`` column names for a ``dim``-d DANN embedding."""
    return [f"embedding__{camera}__{roi}__{METHOD}__d{i:03d}" for i in range(dim)]


def register_features(registry: FeatureRegistry = REGISTRY, cameras: Iterable[str] = CAMERAS,
                      rois: Iterable[str] = ("fused",), dann_dim: int = 16, **_) -> list[str]:
    """Register DANN embedding columns per camera x roi (idempotent); ``requires_raw`` for the Pi camera."""
    names = []
    for cam in cameras:
        for roi in rois:
            for col in feature_columns(cam, roi, dann_dim):
                registry.add(col, group="embedding", camera=cam, requires_raw=(cam == "pi"),
                             description="domain-adversarial embedding dimension", units="a.u.")
                names.append(col)
    return names


__all__ = ["METHOD", "DANNEstimator", "feature_columns", "register_features"]
