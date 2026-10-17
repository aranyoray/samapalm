"""Participant-level (cluster) bootstrap confidence intervals (protocol section 7: every metric table carries
participant-level bootstrap 95 percent CIs with the resample count from ``bootstrap.n_resamples``).

Participants are the sampling unit: each resample draws participants with replacement and concatenates all of
their rows (clips, cameras, beats), so repeated measurements within a person never inflate the precision.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from palmppg.core.config import Config, load_pipeline_config, rng


@dataclass(frozen=True)
class BootstrapResult:
    point: float
    lo: float
    hi: float
    n_participants: int
    n_rows: int
    n_resamples: int
    ci: float
    n_failed_resamples: int = 0

    def as_dict(self) -> dict:
        return asdict(self)


def _resolve(n: int | None, seed: int | None, cfg: Config | None) -> tuple[int, int]:
    if n is None or seed is None:
        cfg = cfg or load_pipeline_config()
    if n is None:
        n = int(cfg.get("bootstrap.n_resamples"))
    if seed is None:
        seed = int(cfg.get("study.seed"))
    return int(n), int(seed)


def participant_groups(ids) -> tuple[np.ndarray, list[np.ndarray]]:
    """Unique participant ids and, for each, the row positions it owns."""
    arr = np.asarray(ids).astype(str)
    uniq, inv = np.unique(arr, return_inverse=True)
    order = np.argsort(inv, kind="stable")
    bounds = np.searchsorted(inv[order], np.arange(len(uniq) + 1))
    groups = [order[bounds[k]:bounds[k + 1]] for k in range(len(uniq))]
    return uniq, groups


def participant_bootstrap(df: pd.DataFrame, metric_fn: Callable[[pd.DataFrame], float], id_col: str = "study_id",
                          n: int | None = None, ci: float = 0.95, seed: int | None = None, salt: str = "bootstrap",
                          cfg: Config | None = None) -> BootstrapResult:
    """Percentile bootstrap CI of ``metric_fn(df)`` resampling participants (``id_col``) with replacement.

    ``n`` defaults to cfg ``bootstrap.n_resamples`` and ``seed`` to cfg ``study.seed``; randomness comes from
    ``palmppg.core.config.rng(seed, salt)`` so results are reproducible. Resamples where the metric is not finite
    are dropped and counted in ``n_failed_resamples``. With fewer than two participants the bounds are NaN.
    """
    if id_col not in df.columns:
        raise KeyError(f"{id_col} not in frame")
    n, seed = _resolve(n, seed, cfg)
    point = float(metric_fn(df))
    uniq, groups = participant_groups(df[id_col].to_numpy())
    k = len(uniq)
    if k < 2 or n <= 0:
        return BootstrapResult(point, float("nan"), float("nan"), k, len(df), 0, ci)
    g = rng(seed, salt)
    stats = np.empty(n, dtype=float)
    draws = g.integers(0, k, size=(n, k))
    for b in range(n):
        idx = np.concatenate([groups[j] for j in draws[b]])
        try:
            stats[b] = float(metric_fn(df.iloc[idx]))
        except (ValueError, ZeroDivisionError, FloatingPointError):
            stats[b] = np.nan
    ok = np.isfinite(stats)
    if ok.sum() == 0:
        return BootstrapResult(point, float("nan"), float("nan"), k, len(df), n, ci, int(n - ok.sum()))
    lo, hi = np.percentile(stats[ok], [100.0 * (1.0 - ci) / 2.0, 100.0 * (1.0 + ci) / 2.0])
    return BootstrapResult(point, float(lo), float(hi), k, len(df), n, ci, int(n - ok.sum()))


def participant_bootstrap_difference(df: pd.DataFrame, metric_a: Callable[[pd.DataFrame], float],
                                     metric_b: Callable[[pd.DataFrame], float], id_col: str = "study_id",
                                     n: int | None = None, ci: float = 0.95, seed: int | None = None,
                                     salt: str = "bootstrap_diff", cfg: Config | None = None) -> BootstrapResult:
    """Bootstrap CI of ``metric_a(df) - metric_b(df)`` on the same participant resamples (paired comparison of
    two arms stored in the same frame, e.g. demographics-only versus temporal error SD)."""
    return participant_bootstrap(df, lambda d: float(metric_a(d)) - float(metric_b(d)), id_col, n, ci, seed, salt, cfg)
