"""The model zoo lists every model and builds the non-torch ones (protocol 9)."""
import numpy as np
import pandas as pd
import pytest

from palmppg.core.config import load_pipeline_config, rng
from palmppg.models import zoo

REQUIRED = {
    "lightgbm_regression", "xgboost_regression", "catboost_regression", "lightgbm_classification",
    "xgboost_classification", "catboost_classification", "lightgbm_quantile_pair", "xgboost_quantile_pair",
    "catboost_quantile_pair", "ridge", "elastic_net", "logistic_ridge", "linear_quantile_pair", "predict_mean",
    "demographics_only", "conv1d", "tcn", "gru", "small_transformer", "resnet18_stmap", "stgcn", "dann",
    "papagei_s", "siamquality", "randominit_embedder", "late_fusion", "cross_attention_fusion", "pulsegan",
    "dualgan", "deep_ensemble", "mc_dropout", "split_conformal",
}


def test_zoo_lists_every_model():
    listed = {d["name"] for d in zoo.list_models()}
    assert REQUIRED <= listed and listed == set(zoo.names())
    torch_free = {d["name"] for d in zoo.list_models(requires_torch=False)}
    assert {"ridge", "lightgbm_regression", "predict_mean", "late_fusion", "split_conformal", "deep_ensemble"} <= torch_free
    assert {"tcn", "resnet18_stmap", "stgcn", "dann", "pulsegan"} <= {d["name"] for d in zoo.list_models(requires_torch=True)}
    assert all(d["requires_weights"] for d in zoo.list_models() if d["name"] in ("papagei_s", "siamquality"))
    with pytest.raises(KeyError):
        zoo.build("nope")


def test_cfg_get_defaults():
    cfg = load_pipeline_config()
    assert zoo.cfg_get(None, "models.gbdt.n_estimators") == 50
    assert zoo.cfg_get(cfg, "models.gbdt.n_estimators") == 50
    assert zoo.cfg_get({"models": {"gbdt": {"n_estimators": 7}}}, "models.gbdt.n_estimators") == 7
    assert zoo.cfg_get(cfg.with_overrides({"models": {"interval_alpha": 0.2}}), "models.interval_alpha") == 0.2
    assert zoo.cfg_get(cfg, "sync.p1.pulses") == 3


def test_builds_and_fits_every_non_torch_model():
    cfg = load_pipeline_config()
    g = rng(1, "zoo")
    n = 120
    X = pd.DataFrame({"age": g.uniform(20, 80, n), "sex": g.choice(["F", "M"], n), "bmi": g.uniform(18, 35, n),
                      "f1": g.normal(size=n), "f2": g.normal(size=n)})
    y = 2.0 * X["f1"] + 0.1 * X["age"] + g.normal(size=n)
    yc = (y > y.median()).astype(int)
    Xnum = X.drop(columns=["sex"])
    for spec in zoo.list_models(requires_torch=False):
        name = spec["name"]
        model = zoo.build(name, cfg, seed=1)
        if spec["task"] == "classification":
            model.fit(Xnum, yc)
            assert model.predict_proba(Xnum).shape == (n, 2)
        elif name == "demographics_only":
            model.fit(X, y)
            assert model.predict(X).shape == (n,)
        elif spec["task"] == "quantile":
            model.fit(Xnum, y)
            lo, hi = model.predict_interval(Xnum)
            assert np.all(lo <= hi)
        elif name == "split_conformal":
            model.fit(Xnum[:80], y[:80]).calibrate(Xnum[80:], y[80:])
            lo, hi = model.predict_interval(Xnum[:5])
            assert np.all(lo < hi)
        else:
            model.fit(Xnum, y)
            assert model.predict(Xnum).shape == (n,)


def test_deep_ensemble_of_gbdts_has_spread():
    g = rng(2, "ens")
    X = pd.DataFrame(g.normal(size=(200, 3)), columns=["a", "b", "c"])
    y = X["a"] + np.sin(X["b"]) + 0.3 * g.normal(size=200)
    for base in ("lightgbm_regression", "xgboost_regression", "catboost_regression"):
        ens = zoo.build("deep_ensemble", None, seed=0, base=base, n=3, n_estimators=20).fit(X, y)
        mean, std = ens.predict_with_uncertainty(X)
        assert std.max() > 0, base
        assert np.sqrt(np.mean((mean - y) ** 2)) < np.std(y)


def test_torch_models_build():
    pytest.importorskip("torch")
    cfg = load_pipeline_config()
    for name in ("conv1d", "tcn", "gru", "small_transformer", "resnet18_stmap", "stgcn", "dann",
                 "cross_attention_fusion", "pulsegan", "dualgan", "mc_dropout"):
        assert zoo.build(name, cfg, seed=0) is not None
    for name in ("papagei_s", "siamquality"):
        with pytest.raises(FileNotFoundError):
            zoo.build(name, cfg, seed=0)
    emb = zoo.build("randominit_embedder", cfg, seed=0, arch_kwargs={"n_block": 2, "base_filters": 4, "n_classes": 8})
    assert emb.random_init and all("__randominit__" in c for c in emb.feature_names("phone"))
    assert zoo.build("stgcn", cfg).graph.n_nodes == 11
