"""The model zoo: names -> factories with their requirements (protocol section 9).

``MODEL_ZOO`` maps a name to a ``ModelSpec`` whose ``factory(cfg, seed, **kw)`` returns an estimator,
embedder or trainer. ``build(name, cfg, seed)`` checks the torch requirement first so a CPU-only
tabular run never imports torch. ``list_models()`` is what the experiment runner and the model cards
iterate over. Zoo-level defaults that the protocol leaves open are read from ``cfg`` under ``models.*``
with the defaults given here (see ``ZOO_DEFAULTS``) so that a run can override them without code edits.
"""
from __future__ import annotations

import importlib.util
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

ZOO_DEFAULTS: dict[str, Any] = {
    "models.gbdt.n_estimators": 50,
    "models.gbdt.learning_rate": 0.1,
    "models.gbdt.max_depth": 4,
    "models.demographics_columns": ["age", "sex", "bmi"],
    "models.interval_alpha": 0.1,
    "models.ensemble_n": 5,
    "models.mc_dropout_samples": 20,
    "models.torch.epochs": 30,
    "models.torch.lr": 1e-3,
    "models.torch.device": "cpu",
    "models.fm.papagei_s_weights": None,
    "models.fm.siamquality_weights": None,
    "models.dann.lambda_domain": 1.0,
}


def cfg_get(cfg, key: str, default=None):
    """``cfg.get(key, default)`` tolerant of ``cfg is None`` and of a plain dict."""
    if default is None:
        default = ZOO_DEFAULTS.get(key)
    if cfg is None:
        return default
    if hasattr(cfg, "get") and not isinstance(cfg, dict):
        return cfg.get(key, default)
    node: Any = cfg
    for part in key.split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return default
    return node


def torch_available() -> bool:
    return importlib.util.find_spec("torch") is not None


@dataclass(frozen=True)
class ModelSpec:
    name: str
    factory: Callable[..., Any]
    requires_torch: bool
    task: str          # regression | classification | quantile | embedding | denoising | fusion | uncertainty
    family: str        # tabular | linear | baseline | temporal | cnn | graph | adversarial | fm | fusion | gan | uncertainty
    description: str
    requires_weights: bool = False

    def to_dict(self) -> dict:
        return {"name": self.name, "requires_torch": self.requires_torch, "task": self.task, "family": self.family,
                "requires_weights": self.requires_weights, "description": self.description}


MODEL_ZOO: dict[str, ModelSpec] = {}


def register(name: str, requires_torch: bool, task: str, family: str, description: str, requires_weights: bool = False):
    def deco(fn):
        MODEL_ZOO[name] = ModelSpec(name, fn, requires_torch, task, family, description, requires_weights)
        return fn
    return deco


def _gbdt_kw(cfg, seed, kw) -> dict:
    out = {"seed": seed, "n_estimators": cfg_get(cfg, "models.gbdt.n_estimators"),
               "learning_rate": cfg_get(cfg, "models.gbdt.learning_rate"), "max_depth": cfg_get(cfg, "models.gbdt.max_depth")}
    out.update(kw)
    return out


# --------------------------------------------------------------------------- tabular
for _kind in ("lightgbm", "xgboost", "catboost"):
    def _reg(cfg=None, seed=0, _kind=_kind, **kw):
        from palmppg.models.tabular import make_gbdt
        return make_gbdt(_kind, "regression", **_gbdt_kw(cfg, seed, kw))

    def _clf(cfg=None, seed=0, _kind=_kind, **kw):
        from palmppg.models.tabular import make_gbdt
        return make_gbdt(_kind, "classification", **_gbdt_kw(cfg, seed, kw))

    def _qpair(cfg=None, seed=0, _kind=_kind, **kw):
        from palmppg.models.tabular import make_quantile_pair
        alpha = kw.pop("alpha", cfg_get(cfg, "models.interval_alpha"))
        return make_quantile_pair(alpha, kind=_kind, **_gbdt_kw(cfg, seed, kw))

    register(f"{_kind}_regression", False, "regression", "tabular",
             f"{_kind} GBDT regressor with monotone constraints (protocol 9, E3)")(_reg)
    register(f"{_kind}_classification", False, "classification", "tabular",
             f"{_kind} GBDT classifier (E7 rhythm, E12 screening)")(_clf)
    register(f"{_kind}_quantile_pair", False, "quantile", "tabular",
             f"{_kind} lower/median/upper quantile regressors (protocol 10 intervals)")(_qpair)


@register("ridge", False, "regression", "linear", "standard-scaled ridge baseline (protocol 9)")
def _ridge(cfg=None, seed=0, **kw):
    from palmppg.models.tabular import make_ridge
    return make_ridge(**kw)


@register("elastic_net", False, "regression", "linear", "standard-scaled elastic-net baseline (protocol 9)")
def _enet(cfg=None, seed=0, **kw):
    from palmppg.models.tabular import make_elastic_net
    return make_elastic_net(seed=seed, **kw)


@register("logistic_ridge", False, "classification", "linear", "L2 logistic regression baseline (E7)")
def _logit(cfg=None, seed=0, **kw):
    from palmppg.models.tabular import make_linear
    return make_linear("ridge", "classification", **kw)


@register("linear_quantile_pair", False, "quantile", "linear", "pinball-loss linear quantile pair (protocol 10)")
def _lin_q(cfg=None, seed=0, **kw):
    from palmppg.models.tabular import make_quantile_pair
    alpha = kw.pop("alpha", cfg_get(cfg, "models.interval_alpha"))
    return make_quantile_pair(alpha, kind="linear", seed=seed, **kw)


@register("predict_mean", False, "regression", "baseline", "predict-the-mean baseline, mandatory in every table (11.2)")
def _mean(cfg=None, seed=0, task="regression", **kw):
    from palmppg.models.tabular import PredictMeanBaseline
    return PredictMeanBaseline(task=task)


@register("demographics_only", False, "regression", "baseline",
          "demographics-only baseline, mandatory in every table (11.2, E5 go/no-go)")
def _demo(cfg=None, seed=0, task="regression", **kw):
    from palmppg.models.tabular import DemographicsOnlyBaseline
    cols = kw.pop("columns", cfg_get(cfg, "models.demographics_columns"))
    return DemographicsOnlyBaseline(columns=cols, task=task, **kw)


# --------------------------------------------------------------------------- torch sequence / image / graph
def _torch_kw(cfg, seed, kw) -> dict:
    out = {"seed": seed, "epochs": cfg_get(cfg, "models.torch.epochs"), "lr": cfg_get(cfg, "models.torch.lr"),
               "device": cfg_get(cfg, "models.torch.device")}
    out.update(kw)
    return out


for _arch in ("conv1d", "tcn", "gru", "small_transformer"):
    def _seq(cfg=None, seed=0, _arch=_arch, **kw):
        from palmppg.models.temporal import make_sequence_regressor
        return make_sequence_regressor(_arch, **_torch_kw(cfg, seed, kw))

    register(_arch, True, "regression", "temporal",
             f"{_arch} on beat/IBI sequences (B, T, C) (protocol 9)")(_seq)


@register("resnet18_stmap", True, "regression", "cnn", "ResNet-18 (from scratch, configurable width) on STMaps (protocol 9)")
def _resnet(cfg=None, seed=0, **kw):
    from palmppg.models.cnn import make_stmap_regressor
    return make_stmap_regressor(**_torch_kw(cfg, seed, kw))


@register("stgcn", True, "regression", "graph", "ST-GCN on the palm ROI graph from cfg rois.graph (protocol 9)")
def _stgcn(cfg=None, seed=0, **kw):
    from palmppg.models.graph import make_stgcn_regressor
    return make_stgcn_regressor(cfg, **_torch_kw(cfg, seed, kw))


@register("dann", True, "regression", "adversarial",
          "domain-adversarial feature extractor against unit/operator/dept/camera (E11)")
def _dann(cfg=None, seed=0, **kw):
    from palmppg.models.adversarial import DANNEstimator
    kw.setdefault("lambda_domain", cfg_get(cfg, "models.dann.lambda_domain"))
    return DANNEstimator(**_torch_kw(cfg, seed, kw))


# --------------------------------------------------------------------------- foundation-model embedders
@register("papagei_s", True, "embedding", "fm", "PaPaGei-S ResNet-1D embedder, user-supplied weights (E10)",
          requires_weights=True)
def _papagei(cfg=None, seed=0, **kw):
    from palmppg.models.fm import load_embedder
    path = kw.pop("weights_path", cfg_get(cfg, "models.fm.papagei_s_weights"))
    return load_embedder("papagei_s", path, **kw)


@register("siamquality", True, "embedding", "fm", "SiamQuality ResNet-1D embedder, user-supplied weights (E10)",
          requires_weights=True)
def _siam(cfg=None, seed=0, **kw):
    from palmppg.models.fm import load_embedder
    path = kw.pop("weights_path", cfg_get(cfg, "models.fm.siamquality_weights"))
    return load_embedder("siamquality", path, **kw)


@register("randominit_embedder", True, "embedding", "fm",
          "random-weight embedder for pipeline tests only; every output column carries 'randominit'")
def _randinit(cfg=None, seed=0, name="papagei_s", **kw):
    from palmppg.models.fm import RandomInitEmbedder
    return RandomInitEmbedder(name, seed=seed, **kw)


# --------------------------------------------------------------------------- fusion, GAN, uncertainty
@register("late_fusion", False, "fusion", "fusion", "late fusion, weights learned by ridge on out-of-fold predictions")
def _late(cfg=None, seed=0, estimators=None, **kw):
    from palmppg.models.fusion import LateFusion
    if estimators is None:
        estimators = {"ridge": build("ridge", cfg, seed), "lightgbm": build("lightgbm_regression", cfg, seed)}
    return LateFusion(estimators, seed=seed, **kw)


@register("cross_attention_fusion", True, "fusion", "fusion", "cross-attention fusion of two modality token sets")
def _xattn(cfg=None, seed=0, **kw):
    from palmppg.models.fusion import make_cross_attention_regressor
    return make_cross_attention_regressor(**_torch_kw(cfg, seed, kw))


@register("pulsegan", True, "denoising", "gan", "PulseGAN denoiser; judged only by downstream metrics")
def _pulsegan(cfg=None, seed=0, **kw):
    from palmppg.models.gan import PulseGANTrainer
    return PulseGANTrainer(**_torch_kw(cfg, seed, kw))


@register("dualgan", True, "denoising", "gan", "Dual-GAN (BVP-GAN + noise-GAN) denoiser; never a headline result")
def _dualgan(cfg=None, seed=0, **kw):
    from palmppg.models.gan import DualGANTrainer
    return DualGANTrainer(**_torch_kw(cfg, seed, kw))


GBDT_BAGGING: dict[str, dict] = {
    # Seeds change nothing in a deterministic GBDT without row/column subsampling, so an ensemble of GBDT
    # members needs bagging turned on; these are the defaults applied by the deep_ensemble factory.
    "lightgbm": {"subsample": 0.8, "subsample_freq": 1, "colsample_bytree": 0.8},
    "xgboost": {"subsample": 0.8, "colsample_bytree": 0.8},
    "catboost": {"bootstrap_type": "Bernoulli", "subsample": 0.8, "rsm": 0.8},
}


@register("deep_ensemble", False, "uncertainty", "uncertainty",
          "ensemble of independently seeded members; GBDT bases get row/column subsampling (protocol 10)")
def _ens(cfg=None, seed=0, base="lightgbm_regression", n=None, **kw):
    from palmppg.models.uncertainty import DeepEnsemble
    n = cfg_get(cfg, "models.ensemble_n") if n is None else n
    for kind, bagging in GBDT_BAGGING.items():
        if base.startswith(kind):
            for k, v in bagging.items():
                kw.setdefault(k, v)
    return DeepEnsemble(n=n, model_fn=lambda s: build(base, cfg, s, **kw), seed=seed)


@register("mc_dropout", True, "uncertainty", "uncertainty", "MC dropout over a torch wrapper (protocol 10)")
def _mcd(cfg=None, seed=0, base="tcn", n_samples=None, **kw):
    from palmppg.models.uncertainty import MCDropout
    n_samples = cfg_get(cfg, "models.mc_dropout_samples") if n_samples is None else n_samples
    return MCDropout(build(base, cfg, seed, **kw), n_samples=n_samples, seed=seed)


@register("split_conformal", False, "uncertainty", "uncertainty", "split conformal intervals around a point estimator")
def _conf(cfg=None, seed=0, base="lightgbm_regression", alpha=None, **kw):
    from palmppg.models.uncertainty import SplitConformal
    alpha = cfg_get(cfg, "models.interval_alpha") if alpha is None else alpha
    return SplitConformal(build(base, cfg, seed, **kw), alpha=alpha)


# --------------------------------------------------------------------------- API
def list_models(requires_torch: bool | None = None) -> list[dict]:
    """Every zoo entry as a dict (name, requires_torch, task, family, requires_weights, description)."""
    out = [s.to_dict() for s in MODEL_ZOO.values()]
    if requires_torch is not None:
        out = [d for d in out if d["requires_torch"] == requires_torch]
    return out


def names() -> list[str]:
    return list(MODEL_ZOO)


def build(name: str, cfg=None, seed: int = 0, **kw):
    """Instantiate zoo model ``name`` with ``cfg`` defaults and ``seed``; raises ``KeyError`` for unknown
    names and ``ImportError`` (before importing anything heavy) when torch is required but absent."""
    if name not in MODEL_ZOO:
        raise KeyError(f"unknown model '{name}'; known: {sorted(MODEL_ZOO)}")
    spec = MODEL_ZOO[name]
    if spec.requires_torch and not torch_available():
        raise ImportError(f"model '{name}' requires torch, which is not installed (pip install palmppg[deep])")
    return spec.factory(cfg, seed, **kw)


__all__ = [
    "GBDT_BAGGING",
    "MODEL_ZOO",
    "ZOO_DEFAULTS",
    "ModelSpec",
    "build",
    "cfg_get",
    "list_models",
    "names",
    "register",
    "torch_available",
]
