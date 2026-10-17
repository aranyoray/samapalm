"""Visibility-graph IBI features (protocol 9, E7): exact values on known series, networkx agreement."""
import networkx as nx
import numpy as np
import pytest

from palmppg.core.config import rng
from palmppg.core.tracks import FeatureRegistry, TrackViolation
from palmppg.models.visibility import (
    degree_entropy_bits,
    feature_columns,
    graph_features,
    horizontal_visibility_graph,
    natural_visibility_graph,
    register_features,
    visibility_feature_names,
    visibility_features,
)


def _mean_degree(G):
    return np.mean([d for _, d in G.degree()])


def test_nvg_matches_networkx_reference():
    y = rng(3, "vis").uniform(size=150)
    G = natural_visibility_graph(y)
    ref = nx.visibility_graph(y)
    assert set(map(frozenset, G.edges())) == set(map(frozenset, ref.edges()))
    assert G.number_of_nodes() == 150


def test_exact_degrees_on_known_series():
    n = 50
    const = np.full(n, 0.8)
    assert _mean_degree(natural_visibility_graph(const)) == pytest.approx(2 * (n - 1) / n)
    assert _mean_degree(horizontal_visibility_graph(const)) == pytest.approx(2 * (n - 1) / n)
    linear = np.arange(n, dtype=float)
    assert _mean_degree(natural_visibility_graph(linear)) == pytest.approx(2 * (n - 1) / n)   # on-chord points block
    assert _mean_degree(horizontal_visibility_graph(linear)) == pytest.approx(2 * (n - 1) / n)
    convex = np.arange(n, dtype=float) ** 2
    Gc = natural_visibility_graph(convex)
    assert Gc.number_of_edges() == n * (n - 1) // 2                                          # complete graph
    f = graph_features(Gc, "nvg")
    assert f["nvg_mean_degree"] == pytest.approx(n - 1) and f["nvg_max_degree_ratio"] == pytest.approx(1.0)
    assert f["nvg_degree_entropy"] == pytest.approx(0.0) and f["nvg_clustering"] == pytest.approx(1.0)
    n = 40
    alternating = np.tile([1.0, 0.0], n // 2)                                                 # bigeminy-like
    H = horizontal_visibility_graph(alternating)
    assert H.number_of_edges() == 3 * n // 2 - 2
    assert _mean_degree(H) == pytest.approx((3 * n - 4) / n)
    p = np.array([2 / 50, 48 / 50])
    assert degree_entropy_bits(horizontal_visibility_graph(const)) == pytest.approx(float(-(p * np.log2(p)).sum()))


def test_iid_series_hvg_mean_degree_tends_to_four():
    y = rng(4, "iid").uniform(size=600)
    assert abs(_mean_degree(horizontal_visibility_graph(y)) - 4.0) < 0.25


def test_regular_versus_irregular_ibis():
    g = rng(5, "ibi")
    n = 90
    regular = 0.85 + 0.02 * np.sin(2 * np.pi * np.arange(n) / 5) + 0.003 * g.normal(size=n)   # sinus with RSA
    irregular = g.uniform(0.5, 1.3, n)                                                        # AF-like
    fr, fi = visibility_features(regular), visibility_features(irregular)
    assert list(fr) == visibility_feature_names() and len(fr) == 10
    assert fi["nvg_degree_entropy"] > fr["nvg_degree_entropy"]
    assert fr["nvg_assortativity"] > fi["nvg_assortativity"]
    assert fr["hvg_assortativity"] > fi["hvg_assortativity"]
    assert all(np.isfinite(v) for v in fr.values()) and all(np.isfinite(v) for v in fi.values())


def test_short_or_nan_series():
    out = visibility_features([0.8] * 5)
    assert all(np.isnan(v) for v in out.values())
    with_nan = np.array([0.8, np.nan, 0.9, 0.7] * 5)
    out = visibility_features(with_nan, min_beats=10)
    assert np.isfinite(out["nvg_mean_degree"])
    assert np.isfinite(visibility_features(np.full(12, 0.8), t_s=np.arange(12) * 0.8)["hvg_mean_degree"])


def test_feature_columns_and_registration():
    reg = FeatureRegistry()
    names = register_features(reg, cameras=("pi", "phone"), rois=("fused", "thenar"))
    assert len(names) == 2 * 2 * 10 + 10 and len(set(names)) == len(names)
    assert register_features(reg, cameras=("pi", "phone"), rois=("fused", "thenar")) == names  # idempotent
    assert feature_columns("phone")[0] == "hrv__phone__fused__visibility__nvg_mean_degree"
    assert feature_columns("", source="ecg")[0] == "ecg__visibility__nvg_mean_degree"
    reg.check_columns(feature_columns("phone"), "product_candidate")
    with pytest.raises(TrackViolation):
        reg.check_columns(feature_columns("pi"), "product_candidate")
    with pytest.raises(TrackViolation):
        reg.check_columns(feature_columns("", source="ecg"), "product_candidate")
    reg.check_columns(feature_columns("", source="ecg"), "science")
