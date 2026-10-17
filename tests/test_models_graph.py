"""Palm ROI graph from cfg rois.graph and the ST-GCN on it (protocol 9)."""
import numpy as np
import pytest

from palmppg.core.config import load_pipeline_config, rng
from palmppg.models.graph import (
    TorchGraphRegressor,
    build_palm_graph,
    make_stgcn_regressor,
    normalised_partitions,
)
from palmppg.models.tabular import PredictMeanBaseline


@pytest.fixture(scope="module")
def cfg():
    return load_pipeline_config()


def test_graph_from_config(cfg):
    G = build_palm_graph(cfg)
    spec = cfg.get("rois.graph")
    assert G.nodes == spec["radial"] + spec["ulnar"] + spec["arch"]
    assert G.n_nodes == 11 and G.groups["arch"][0] == "central_palm"
    A = G.adjacency
    assert A.shape == (11, 11) and np.array_equal(A, A.T) and np.all(np.diag(A) == 0)
    expected = {("central_palm", "thenar"), ("central_palm", "hypothenar"), ("pad_index", "prox_index"),
                ("pad_ring", "prox_ring"), ("thenar", "pad_index"), ("hypothenar", "pad_ring"),
                ("central_palm", "prox_index"), ("prox_ring", "prox_little")}
    have = {tuple(sorted(e)) for e in G.edges}
    assert {tuple(sorted(e)) for e in expected} <= have
    assert len(G.edges) == 14 and int(A.sum()) == 28
    assert ("thenar", "hypothenar") not in have
    assert A[G.index("central_palm")].sum() == 3     # thenar, hypothenar, prox_index
    built = build_palm_graph({"rois": {"graph": {"radial": ["a", "b"], "arch": ["central_palm", "prox_x"]}}})
    assert built.n_nodes == 4 and len(built.edges) == 2


def test_partitions(cfg):
    A = build_palm_graph(cfg).adjacency
    P2 = normalised_partitions(A, 2)
    assert P2.shape == (2, 11, 11) and np.array_equal(P2[0], np.eye(11))
    assert np.allclose(P2[1].sum(axis=1), 1.0)
    P1 = normalised_partitions(A, 1)
    assert P1.shape == (1, 11, 11) and np.allclose(P1[0], P1[0].T)
    with pytest.raises(ValueError):
        normalised_partitions(A, 3)


def test_stack_windows(cfg):
    G = build_palm_graph(cfg)
    stacked = G.stack_windows({"thenar": np.ones((10, 2)), "central_palm": np.zeros((12, 2))})
    assert stacked.shape == (10, 11, 2)
    assert np.all(stacked[:, G.index("thenar")] == 1.0) and np.isnan(stacked[:, G.index("pad_ring")]).all()
    with pytest.raises(ValueError):
        G.stack_windows({"nothing": np.ones((3, 1))})


def _samples(G, g, fs, T=48):
    out = []
    t = np.arange(T) / 30.0
    for f in fs:
        x = np.zeros((T, G.n_nodes, 2), np.float32)
        for v in range(G.n_nodes):
            x[:, v, 0] = np.sin(2 * np.pi * f * t + 0.1 * v) + 0.2 * g.normal(size=T)
            x[:, v, 1] = np.cos(2 * np.pi * f * t + 0.1 * v)
        out.append(x)
    return out


def test_stgcn_forward_and_fit(cfg):
    torch = pytest.importorskip("torch")
    from palmppg.models.nets.graph import STGCN

    G = build_palm_graph(cfg)
    net = STGCN(normalised_partitions(G.adjacency, 2), in_ch=2, out_dim=1, hidden=8, n_blocks=2)
    x = torch.zeros(3, 2, 20, 11)
    mask = torch.ones(3, 20, dtype=torch.bool)
    mask[0, 10:] = False
    assert net(x, mask).shape == (3, 1) and net.embed(x).shape == (3, 8) and net.n_nodes == 11
    g = rng(9, "graph")
    fs = g.uniform(0.7, 2.0, 60)
    X = _samples(G, g, fs)
    model = make_stgcn_regressor(cfg, epochs=12, lr=3e-3, seed=0, batch_size=12, model_kw={"hidden": 8, "n_blocks": 2})
    model.fit(X[:48], fs[:48])
    mse = np.mean((model.predict(X[48:]) - fs[48:]) ** 2)
    base = np.mean((PredictMeanBaseline().fit(X[:48], fs[:48]).predict(X[48:]) - fs[48:]) ** 2)
    assert mse < 0.3 * base, f"mse {mse:.4f} vs baseline {base:.4f}"
    assert model.graph_.n_nodes == 11 and model.transform(X[:2]).shape == (2, 8)
    with pytest.raises(ValueError):
        model.predict([np.zeros((10, 5, 2))])
    with pytest.raises(ValueError):
        TorchGraphRegressor().fit(X[:4], fs[:4])
