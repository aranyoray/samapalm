"""ST-GCN on the palm ROI graph (protocol section 9: "ST-GCN on the palm ROI graph (radial side:
thenar, index, middle; ulnar side: hypothenar, ring, little; arch: central palm, proximal phalanges)").

The graph comes from ``cfg rois.graph`` (radial, ulnar, arch node lists). Edges (a decision recorded
in the WP9 report): consecutive nodes within each list are chained; ``central_palm`` joins ``thenar``
and ``hypothenar`` (the arch spans both sides); each finger pad joins its proximal phalanx
(``pad_<f>`` - ``prox_<f>``). Node features are per-ROI pulse windows ``(T, V, C)`` in the node order
of ``PalmGraph.nodes``. ``build_palm_graph`` and ``normalised_partitions`` are numpy only; the network
lives in ``nets.graph`` and is imported lazily.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field

import numpy as np

from palmppg.models._torchbase import TorchEstimator, channel_stats, standardise

GRAPH_GROUPS: tuple[str, ...] = ("radial", "ulnar", "arch")


@dataclass
class PalmGraph:
    nodes: list[str]
    edges: list[tuple[str, str]]
    adjacency: np.ndarray                      # (V, V) symmetric binary, no self loops
    groups: dict[str, list[str]] = field(default_factory=dict)

    @property
    def n_nodes(self) -> int:
        return len(self.nodes)

    def index(self, name: str) -> int:
        return self.nodes.index(name)

    def stack_windows(self, windows: dict[str, np.ndarray]) -> np.ndarray:
        """``{roi: (T, C)}`` -> ``(T, V, C)`` in node order; a missing ROI becomes a NaN node."""
        arrays = [np.asarray(windows[n], dtype=np.float32) for n in self.nodes if n in windows]
        if not arrays:
            raise ValueError("no graph node present in windows")
        T = min(a.shape[0] for a in arrays)
        C = arrays[0].shape[1] if arrays[0].ndim == 2 else 1
        out = np.full((T, self.n_nodes, C), np.nan, dtype=np.float32)
        for v, n in enumerate(self.nodes):
            if n in windows:
                a = np.asarray(windows[n], dtype=np.float32)
                a = a[:, None] if a.ndim == 1 else a
                out[:, v, :] = a[:T]
        return out


def build_palm_graph(cfg) -> PalmGraph:
    """Nodes and adjacency from ``cfg.get('rois.graph')`` (keys radial, ulnar, arch).

    ``cfg`` may be a ``Config``, a plain pipeline dict (``{"rois": {"graph": ...}}``) or the graph dict itself.
    """
    if isinstance(cfg, dict):
        spec = cfg["rois"]["graph"] if "rois" in cfg else cfg
    else:
        spec = cfg.get("rois.graph")
    if not isinstance(spec, dict) or not any(g in spec for g in GRAPH_GROUPS):
        raise ValueError("rois.graph must map radial/ulnar/arch to ROI name lists")
    groups = {g: list(spec[g]) for g in GRAPH_GROUPS if g in spec}
    nodes: list[str] = []
    for g in GRAPH_GROUPS:
        for n in groups.get(g, []):
            if n not in nodes:
                nodes.append(n)
    edges: set[tuple[str, str]] = set()

    def add(a: str, b: str) -> None:
        if a in nodes and b in nodes and a != b:
            edges.add(tuple(sorted((a, b))))

    for g, members in groups.items():
        for a, b in itertools.pairwise(members):
            add(a, b)
    for side in ("thenar", "hypothenar"):
        add("central_palm", side)
    for n in nodes:
        if n.startswith("pad_"):
            add(n, "prox_" + n[len("pad_"):])
    V = len(nodes)
    A = np.zeros((V, V), dtype=np.float32)
    for a, b in edges:
        i, j = nodes.index(a), nodes.index(b)
        A[i, j] = A[j, i] = 1.0
    return PalmGraph(nodes, sorted(edges), A, groups)


def normalised_partitions(A: np.ndarray, n_partitions: int = 2) -> np.ndarray:
    """ST-GCN partitions ``(K, V, V)``: ``K=1`` symmetric-normalised ``A + I``; ``K=2`` the identity (root)
    and the row-normalised neighbour matrix (distance partitioning)."""
    A = np.asarray(A, dtype=np.float32)
    V = A.shape[0]
    if n_partitions == 1:
        Ah = A + np.eye(V, dtype=np.float32)
        d = Ah.sum(axis=1)
        Dm = np.diag(1.0 / np.sqrt(np.maximum(d, 1e-8)))
        return (Dm @ Ah @ Dm)[None].astype(np.float32)
    if n_partitions == 2:
        d = np.maximum(A.sum(axis=1, keepdims=True), 1e-8)
        return np.stack([np.eye(V, dtype=np.float32), (A / d).astype(np.float32)])
    raise ValueError("n_partitions must be 1 or 2")


class TorchGraphRegressor(TorchEstimator):
    """ST-GCN wrapper: ``fit(list of (T_i, V, C) arrays, y)``; ``V`` must equal ``graph.n_nodes``.

    ``graph`` is a ``PalmGraph`` (or ``cfg`` to build one); ``n_partitions`` selects the adjacency
    partitioning; ``model_kw`` goes to ``nets.graph.STGCN`` (hidden, n_blocks, t_kernel, dropout).
    """

    def __init__(self, graph: PalmGraph | None = None, cfg=None, n_partitions: int = 2, epochs: int = 30,
                 lr: float = 1e-3, seed: int = 0, device: str = "cpu", batch_size: int = 16, weight_decay: float = 1e-4,
                 task: str = "regression", grad_clip: float = 1.0, verbose: bool = False, model_kw: dict | None = None):
        super().__init__(model_fn=None, epochs=epochs, lr=lr, seed=seed, device=device, batch_size=batch_size,
                         weight_decay=weight_decay, task=task, grad_clip=grad_clip, verbose=verbose)
        self.graph = graph
        self.cfg = cfg
        self.n_partitions = n_partitions
        self.model_kw = model_kw

    def _graph(self) -> PalmGraph:
        if self.graph is not None:
            return self.graph
        if self.cfg is None:
            raise ValueError("TorchGraphRegressor needs graph= or cfg=")
        return build_palm_graph(self.cfg)

    def _as_list(self, X) -> list[np.ndarray]:
        g = self._graph()
        out = []
        for x in X:
            a = np.asarray(x, dtype=np.float32)
            if a.ndim == 2:
                a = a[:, :, None]
            if a.ndim != 3 or a.shape[1] != g.n_nodes:
                raise ValueError(f"each sample must be (T, V={g.n_nodes}, C), got {a.shape}")
            out.append(a)
        if not out:
            raise ValueError("empty input")
        return out

    def _encode_fit(self, X):
        samples = self._as_list(X)
        flat = [s.reshape(-1, s.shape[2]) for s in samples]
        self.x_mean_, self.x_std_ = channel_stats(flat)
        self.n_channels_ = int(samples[0].shape[2])
        self.graph_ = self._graph()
        return standardise(samples, self.x_mean_, self.x_std_)

    def _encode(self, X):
        return standardise(self._as_list(X), self.x_mean_, self.x_std_)

    def _collate(self, samples):
        torch = self._torch()
        B = len(samples)
        T = max(s.shape[0] for s in samples)
        V, C = samples[0].shape[1], samples[0].shape[2]
        x = np.zeros((B, C, T, V), dtype=np.float32)
        mask = np.zeros((B, T), dtype=bool)
        for i, s in enumerate(samples):
            x[i, :, : s.shape[0], :] = s.transpose(2, 0, 1)
            mask[i, : s.shape[0]] = True
        return {"x": torch.from_numpy(x), "mask": torch.from_numpy(mask)}

    def _build_module(self, sample, out_dim: int):
        from palmppg.models.nets.graph import STGCN

        A = normalised_partitions(self.graph_.adjacency, self.n_partitions)
        return STGCN(A, int(sample.shape[2]), out_dim, **(self.model_kw or {}))


def make_stgcn_regressor(cfg, **kw) -> TorchGraphRegressor:
    """Zoo factory: ST-GCN on the graph built from ``cfg``."""
    return TorchGraphRegressor(graph=build_palm_graph(cfg), **kw)


__all__ = [
    "GRAPH_GROUPS",
    "PalmGraph",
    "TorchGraphRegressor",
    "build_palm_graph",
    "make_stgcn_regressor",
    "normalised_partitions",
]
