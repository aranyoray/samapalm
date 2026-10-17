"""Foundation-model embedders for pulse signals (protocol section 9 "PaPaGei and SiamQuality
embeddings"; E10 foundation-model transfer).

Weights are never shipped, downloaded or fabricated here. ``load_embedder(name, weights_path)`` builds
the architecture and loads a user-supplied checkpoint; when the file is absent it raises
``FileNotFoundError`` whose message carries the download instructions. ``RandomInitEmbedder`` exists for
pipeline tests only and labels every output column with ``randominit`` so that a random embedding can
never be mistaken for a pre-trained one in a feature table.

Architectures (``nets.fm.ResNet1D``, the resnet1d family of Hong et al. 2020):

* ``papagei_s``: PaPaGei-S (Pillai et al. 2024). ResNet-1D encoder, 1 input channel, base_filters 32,
  kernel 3, stride 2, 18 basic blocks, 512-d output, trained on 10 s segments at 125 Hz (1250 samples),
  each segment z-scored. The released checkpoint also holds the morphology mixture-of-experts heads; they
  are not part of the embedding and are ignored at load time (reported in ``unexpected_keys_``).
* ``siamquality``: SiamQuality (Ding et al. 2024). ResNet-1D encoder on 30 s segments at 100 Hz
  (3000 samples), z-scored. The block configuration must match the checkpoint; the defaults in
  ``EMBEDDER_SPECS`` are overridden with ``arch_kwargs`` and a mismatch raises at load time with the
  missing and unexpected key lists.

Inputs of any sampling rate are resampled (polyphase) to the model rate and cut into non-overlapping
segments; the clip embedding is the mean over segments. Column names follow CONTRACTS section 5:
``embedding__<camera>__<roi>__<method>__d<i>``.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.signal import resample_poly

from palmppg.core.tracks import CAMERAS, REGISTRY, FeatureRegistry
from palmppg.models._torchbase import derived_seed

RANDOMINIT = "randominit"


@dataclass(frozen=True)
class EmbedderSpec:
    name: str
    fs_hz: float
    segment_s: float
    dim: int
    arch_kwargs: dict = field(default_factory=dict)
    source_url: str = ""
    weights_hint: str = ""

    @property
    def segment_samples(self) -> int:
        return round(self.fs_hz * self.segment_s)


EMBEDDER_SPECS: dict[str, EmbedderSpec] = {
    "papagei_s": EmbedderSpec(
        "papagei_s", 125.0, 10.0, 512,
        {"in_channels": 1, "base_filters": 32, "kernel_size": 3, "stride": 2, "groups": 1, "n_block": 18, "n_classes": 512},
        "https://github.com/Nokia-Bell-Labs/papagei-foundation-model",
        "papagei_s.pt (PaPaGei-S) from the repository's weights link; place it under models/weights/ and pass "
        "its path as weights_path or set models.fm.papagei_s_weights in the pipeline config"),
    "siamquality": EmbedderSpec(
        "siamquality", 100.0, 30.0, 512,
        {"in_channels": 1, "base_filters": 64, "kernel_size": 16, "stride": 2, "groups": 1, "n_block": 16, "n_classes": 512},
        "https://github.com/chengding0713/SiamQuality",
        "the SiamQuality encoder checkpoint from the repository; pass its path as weights_path (or set "
        "models.fm.siamquality_weights) and match arch_kwargs to the checkpoint's encoder configuration"),
}


def download_instructions(name: str) -> str:
    spec = EMBEDDER_SPECS[name]
    return (f"{name} weights are not shipped with this repository. Obtain {spec.weights_hint}. "
            f"Source: {spec.source_url}. The embedder never falls back to random weights; use "
            f"RandomInitEmbedder('{name}') only for pipeline tests (its columns are labelled '{RANDOMINIT}').")


def build_module(name: str, arch_kwargs: dict | None = None):
    """Instantiate the ``ResNet1D`` backbone of ``name`` (torch imported here)."""
    from palmppg.models.nets.fm import ResNet1D

    if name not in EMBEDDER_SPECS:
        raise KeyError(f"unknown embedder '{name}' (have {sorted(EMBEDDER_SPECS)})")
    kw = dict(EMBEDDER_SPECS[name].arch_kwargs)
    kw.update(arch_kwargs or {})
    return ResNet1D(**kw)


def resample_to(signal: np.ndarray, fs_in: float, fs_out: float) -> np.ndarray:
    """Polyphase resampling of a 1-D signal from ``fs_in`` to ``fs_out`` (NaN bridged first)."""
    x = np.asarray(signal, dtype=float).ravel()
    ok = np.isfinite(x)
    if ok.sum() == 0:
        return np.zeros(round(x.size * fs_out / fs_in))
    if not ok.all():
        t = np.arange(x.size)
        x = np.interp(t, t[ok], x[ok])
    if abs(fs_in - fs_out) < 1e-9:
        return x
    frac = Fraction(fs_out / fs_in).limit_denominator(1000)
    return resample_poly(x, frac.numerator, frac.denominator)


def segment(signal: np.ndarray, n: int, hop: int | None = None) -> np.ndarray:
    """Non-overlapping (or ``hop``-strided) windows of ``n`` samples, each z-scored: (n_segments, n)."""
    x = np.asarray(signal, dtype=np.float32).ravel()
    hop = n if hop is None else int(hop)
    if x.size < n:
        return np.zeros((0, n), dtype=np.float32)
    starts = range(0, x.size - n + 1, hop)
    segs = np.stack([x[s:s + n] for s in starts])
    mu = segs.mean(axis=1, keepdims=True)
    sd = np.maximum(segs.std(axis=1, keepdims=True), 1e-6)
    return ((segs - mu) / sd).astype(np.float32)


class Embedder:
    """A loaded (or random-init) embedding model with a fixed input rate and segment length."""

    def __init__(self, name: str, module, spec: EmbedderSpec, device: str = "cpu", random_init: bool = False,
                 weights_path: str | None = None):
        self.name = name
        self.module = module.to(device).eval()
        self.spec = spec
        self.device = device
        self.random_init = random_init
        self.weights_path = weights_path
        self.unexpected_keys_: list[str] = []
        self._dim = int(getattr(module, "embed_dim", spec.dim))

    @property
    def dim(self) -> int:
        """Embedding width of the built module (the spec's width unless ``arch_kwargs`` changed it)."""
        return self._dim

    @property
    def method(self) -> str:
        return RANDOMINIT if self.random_init else self.name

    def feature_names(self, camera: str, roi: str = "fused") -> list[str]:
        """Column names; random-init embedders carry ``__randominit__`` in every name."""
        if self.random_init:
            return [f"embedding__{camera}__{roi}__{RANDOMINIT}__{self.name}_d{i:03d}" for i in range(self.dim)]
        return [f"embedding__{camera}__{roi}__{self.name}__d{i:03d}" for i in range(self.dim)]

    def segments(self, signal: np.ndarray, fs: float, hop_s: float | None = None) -> np.ndarray:
        x = resample_to(signal, fs, self.spec.fs_hz)
        hop = None if hop_s is None else round(hop_s * self.spec.fs_hz)
        return segment(x, self.spec.segment_samples, hop)

    def embed(self, signal: np.ndarray, fs: float, hop_s: float | None = None, batch_size: int = 16) -> np.ndarray:
        """(n_segments, dim) embeddings of a 1-D pulse signal sampled at ``fs`` Hz."""
        import torch

        segs = self.segments(signal, fs, hop_s)
        if segs.shape[0] == 0:
            return np.zeros((0, self.dim), dtype=np.float32)
        outs = []
        with torch.no_grad():
            for s in range(0, segs.shape[0], batch_size):
                x = torch.from_numpy(segs[s:s + batch_size])[:, None, :].to(self.device)
                outs.append(self.module.embed(x).cpu().numpy())
        return np.concatenate(outs).astype(np.float32)

    def embed_clip(self, signal: np.ndarray, fs: float, hop_s: float | None = None) -> np.ndarray:
        """Mean embedding over segments (dim,); NaN when the clip is shorter than one segment."""
        e = self.embed(signal, fs, hop_s)
        if e.shape[0] == 0:
            return np.full(self.dim, np.nan, dtype=np.float32)
        return e.mean(axis=0)

    def embed_row(self, signal: np.ndarray, fs: float, camera: str, roi: str = "fused") -> pd.Series:
        """Clip embedding as a Series keyed by the registered column names."""
        return pd.Series(self.embed_clip(signal, fs), index=self.feature_names(camera, roi), dtype="float32")


def _unwrap_state_dict(obj) -> dict:
    sd = obj
    for key in ("state_dict", "model_state_dict", "model", "encoder"):
        if isinstance(sd, dict) and key in sd and isinstance(sd[key], dict):
            sd = sd[key]
    if not isinstance(sd, dict):
        raise TypeError("checkpoint does not contain a state dict")
    return {k.removeprefix("module."): v for k, v in sd.items()}


def load_embedder(name: str, weights_path: str | Path | None, device: str = "cpu", arch_kwargs: dict | None = None,
                  allow_missing: bool = False) -> Embedder:
    """Build ``name`` and load user-supplied weights; ``FileNotFoundError`` with instructions when absent.

    Keys the architecture needs but the checkpoint lacks raise ``RuntimeError`` (unless ``allow_missing``);
    extra checkpoint keys (task heads) are ignored and listed in ``Embedder.unexpected_keys_``.
    """
    if name not in EMBEDDER_SPECS:
        raise KeyError(f"unknown embedder '{name}' (have {sorted(EMBEDDER_SPECS)})")
    if weights_path is None or not Path(weights_path).is_file():
        raise FileNotFoundError(f"weights for '{name}' not found at {weights_path!r}. " + download_instructions(name))
    import torch

    module = build_module(name, arch_kwargs)
    raw = torch.load(str(weights_path), map_location="cpu", weights_only=True)
    sd = _unwrap_state_dict(raw)
    result = module.load_state_dict(sd, strict=False)
    if result.missing_keys and not allow_missing:
        raise RuntimeError(f"{name}: checkpoint lacks {len(result.missing_keys)} backbone key(s) "
                           f"(first: {result.missing_keys[:5]}); match arch_kwargs to the checkpoint")
    emb = Embedder(name, module, EMBEDDER_SPECS[name], device, random_init=False, weights_path=str(weights_path))
    emb.unexpected_keys_ = list(result.unexpected_keys)
    emb.missing_keys_ = list(result.missing_keys)
    return emb


class RandomInitEmbedder(Embedder):
    """Randomly initialised backbone for pipeline tests only. Every column name carries ``randominit``;
    outputs must never be reported as foundation-model results."""

    def __init__(self, name: str = "papagei_s", seed: int = 0, device: str = "cpu", arch_kwargs: dict | None = None):
        import torch

        torch.manual_seed(derived_seed(seed, f"randominit:{name}"))
        module = build_module(name, arch_kwargs)
        super().__init__(name, module, EMBEDDER_SPECS[name], device, random_init=True, weights_path=None)
        self.seed = seed


def feature_columns(camera: str, roi: str = "fused", method: str = "papagei_s", dim: int | None = None) -> list[str]:
    """Column names for ``method`` (an embedder name, or ``'randominit'`` which prefixes the PaPaGei-S names)."""
    if method == RANDOMINIT:
        spec = EMBEDDER_SPECS["papagei_s"]
        d = dim or spec.dim
        return [f"embedding__{camera}__{roi}__{RANDOMINIT}__{spec.name}_d{i:03d}" for i in range(d)]
    spec = EMBEDDER_SPECS[method]
    return [f"embedding__{camera}__{roi}__{method}__d{i:03d}" for i in range(dim or spec.dim)]


def register_features(registry: FeatureRegistry = REGISTRY, cameras: Iterable[str] = CAMERAS,
                      rois: Iterable[str] = ("fused",), methods: Iterable[str] = ("papagei_s", "siamquality", RANDOMINIT),
                      **_) -> list[str]:
    """Register embedding columns per camera x roi x method (idempotent); ``requires_raw`` for the Pi camera."""
    names = []
    for cam in cameras:
        for roi in rois:
            for method in methods:
                for col in feature_columns(cam, roi, method):
                    registry.add(col, group="embedding", camera=cam, requires_raw=(cam == "pi"),
                                 description=f"{method} embedding dimension ({'random init, tests only' if method == RANDOMINIT else 'pre-trained'})",
                                 units="a.u.")
                    names.append(col)
    return names


__all__ = [
    "EMBEDDER_SPECS",
    "RANDOMINIT",
    "Embedder",
    "EmbedderSpec",
    "RandomInitEmbedder",
    "build_module",
    "download_instructions",
    "feature_columns",
    "load_embedder",
    "register_features",
    "resample_to",
    "segment",
]
