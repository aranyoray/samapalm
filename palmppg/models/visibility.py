"""Visibility-graph features of an inter-beat-interval (IBI) series for rhythm work (protocol 9, E7).

A time series maps to a graph: one node per beat, an edge between two beats when the IBI bars "see"
each other. The natural visibility graph (NVG, Lacasa et al. 2008) joins i < j when every intermediate
bar lies strictly below the straight line between the two bar tops; the horizontal visibility graph
(HVG, Luque et al. 2009) joins i < j when every intermediate bar is strictly lower than both.
Regular (sinus) IBI series give sparse, low-entropy graphs; irregularly irregular series (AF) give
denser, higher-entropy graphs. Two known reference values used by the tests: a constant series has
mean degree exactly 2(n-1)/n in both graphs, and an i.i.d. series has an HVG mean degree that tends
to 4 as n grows. No torch dependency; graph metrics come from networkx.

Features (per graph, prefixed ``nvg_`` and ``hvg_``): ``mean_degree`` (edges per node), ``degree_entropy``
(Shannon entropy of the degree distribution, bits), ``clustering`` (average clustering coefficient),
``assortativity`` (degree assortativity coefficient, NaN when undefined), ``max_degree_ratio``
(maximum degree divided by n-1). Column naming follows CONTRACTS section 5.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Sequence

import networkx as nx
import numpy as np

from palmppg.core.tracks import CAMERAS, REGISTRY, FeatureRegistry, feature_prefix

GRAPH_METRICS: tuple[str, ...] = ("mean_degree", "degree_entropy", "clustering", "assortativity", "max_degree_ratio")
GRAPH_KINDS: tuple[str, ...] = ("nvg", "hvg")
METHOD = "visibility"


def _as_series(y) -> np.ndarray:
    y = np.asarray(y, dtype=float).ravel()
    if y.size and not np.isfinite(y).all():
        y = y[np.isfinite(y)]
    return y


def natural_visibility_graph(y: Sequence[float], t: Sequence[float] | None = None) -> nx.Graph:
    """NVG of ``y`` sampled at times ``t`` (default: the beat index). O(n^2) running-slope scan.

    Node ``i`` sees ``j > i`` when for all ``i < k < j``:
    ``y_k < y_i + (y_j - y_i) * (t_k - t_i) / (t_j - t_i)``, i.e. the slope from ``i`` to ``j`` exceeds the
    largest slope from ``i`` to any intermediate bar.
    """
    y = _as_series(y)
    n = y.size
    t = np.arange(n, dtype=float) if t is None else np.asarray(t, dtype=float).ravel()
    if t.size != n:
        raise ValueError("t and y must have the same length")
    G = nx.Graph()
    G.add_nodes_from(range(n))
    for i in range(n - 1):
        max_slope = -math.inf
        for j in range(i + 1, n):
            slope = (y[j] - y[i]) / (t[j] - t[i])
            if slope > max_slope:
                G.add_edge(i, j)
            max_slope = max(max_slope, slope)
    return G


def horizontal_visibility_graph(y: Sequence[float]) -> nx.Graph:
    """HVG of ``y``: ``i`` sees ``j > i`` when every intermediate bar is strictly below ``min(y_i, y_j)``.

    The scan from ``i`` stops at the first ``j`` with ``y_j >= y_i`` because no later bar can see ``i``.
    """
    y = _as_series(y)
    n = y.size
    G = nx.Graph()
    G.add_nodes_from(range(n))
    for i in range(n - 1):
        running_max = -math.inf
        for j in range(i + 1, n):
            if min(y[i], y[j]) > running_max:
                G.add_edge(i, j)
            if y[j] >= y[i]:
                break
            running_max = max(running_max, y[j])
    return G


def degree_entropy_bits(G: nx.Graph) -> float:
    """Shannon entropy (bits) of the empirical degree distribution of ``G``."""
    degs = np.array([d for _, d in G.degree()], dtype=int)
    if degs.size == 0:
        return float("nan")
    _, counts = np.unique(degs, return_counts=True)
    p = counts / counts.sum()
    return float(-np.sum(p * np.log2(p)))


def graph_features(G: nx.Graph, prefix: str) -> dict[str, float]:
    """The five graph metrics of ``G`` keyed ``<prefix>_<metric>``; NaN where undefined."""
    n = G.number_of_nodes()
    out = {f"{prefix}_{m}": float("nan") for m in GRAPH_METRICS}
    if n < 2:
        return out
    degs = np.array([d for _, d in G.degree()], dtype=float)
    out[f"{prefix}_mean_degree"] = float(degs.mean())
    out[f"{prefix}_degree_entropy"] = degree_entropy_bits(G)
    out[f"{prefix}_clustering"] = float(nx.average_clustering(G)) if G.number_of_edges() else 0.0
    if G.number_of_edges() >= 2 and np.unique(degs).size > 1:
        try:
            r = nx.degree_assortativity_coefficient(G)
            out[f"{prefix}_assortativity"] = float(r) if np.isfinite(r) else float("nan")
        except (ZeroDivisionError, ValueError, nx.NetworkXError):
            out[f"{prefix}_assortativity"] = float("nan")
    out[f"{prefix}_max_degree_ratio"] = float(degs.max() / (n - 1))
    return out


def visibility_feature_names() -> list[str]:
    """Short names of the ten features, in output order (``nvg_*`` then ``hvg_*``)."""
    return [f"{k}_{m}" for k in GRAPH_KINDS for m in GRAPH_METRICS]


def visibility_features(ibi_s: Sequence[float], min_beats: int = 10, t_s: Sequence[float] | None = None) -> dict[str, float]:
    """Ten visibility-graph features of an IBI series in seconds (protocol 9, E7 rhythm).

    Returns NaN for every feature when fewer than ``min_beats`` finite intervals exist, so a short or
    heavily gapped clip is counted as missing (and therefore as a failure downstream, protocol 11.3).
    ``t_s`` (beat times) is optional and only affects the NVG slopes; the index is used otherwise.
    """
    y = _as_series(ibi_s)
    names = visibility_feature_names()
    if y.size < min_beats:
        return {k: float("nan") for k in names}
    t = None if t_s is None else np.asarray(t_s, dtype=float).ravel()
    if t is not None and t.size != y.size:
        t = None
    out = graph_features(natural_visibility_graph(y, t), "nvg")
    out.update(graph_features(horizontal_visibility_graph(y), "hvg"))
    return {k: out[k] for k in names}


def feature_columns(camera: str, roi: str = "fused", source: str = "pulse") -> list[str]:
    """Full column names: ``hrv__<camera>__<roi>__visibility__<name>`` (pulse IBIs) or
    ``ecg__visibility__<name>`` (ECG IBIs, ``requires_ecg``)."""
    if source == "ecg":
        return [f"ecg__{METHOD}__{n}" for n in visibility_feature_names()]
    return [feature_prefix("hrv", camera, roi, METHOD, n) for n in visibility_feature_names()]


def register_features(registry: FeatureRegistry = REGISTRY, cameras: Iterable[str] = CAMERAS,
                      rois: Iterable[str] = ("fused",), **_) -> list[str]:
    """Register the visibility columns for every camera x roi plus the ECG variant (idempotent)."""
    names: list[str] = []
    for cam in cameras:
        for roi in rois:
            for col, short in zip(feature_columns(cam, roi), visibility_feature_names()):
                registry.add(col, group="hrv", camera=cam, requires_raw=(cam == "pi"),
                             description=f"visibility-graph {short} of the {roi} pulse IBI series", units="graph")
                names.append(col)
    for col, short in zip(feature_columns("", source="ecg"), visibility_feature_names()):
        registry.add(col, group="ecg", camera="any", requires_ecg=True,
                     description=f"visibility-graph {short} of the ECG IBI series", units="graph")
        names.append(col)
    return names


__all__ = [
    "GRAPH_KINDS",
    "GRAPH_METRICS",
    "degree_entropy_bits",
    "feature_columns",
    "graph_features",
    "horizontal_visibility_graph",
    "natural_visibility_graph",
    "register_features",
    "visibility_feature_names",
    "visibility_features",
]
