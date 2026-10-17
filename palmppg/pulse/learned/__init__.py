"""Learned pulse extractors on proxy video and STMaps (protocol section 6.3 "learned on video or STMaps").

Architectures (torch, each with a small `width` argument so tests train on CPU):
  deepphys.DeepPhys          two-branch appearance / motion CNN with attention (Chen & McDuff 2018)
  tscan.TSCAN                DeepPhys with temporal shift modules (Liu et al. 2020)
  efficientphys.EfficientPhys single-branch TSM network with self-attention masks (Liu et al. 2023)
  physnet.PhysNet            3D CNN encoder-decoder on (3, T, 72, 128) clips (Yu, Li & Zhao 2019)
  physformer.PhysFormerLite  temporal-difference convolution + multi-head self-attention (Yu et al. 2022)
Self-supervised objectives in `ssl`: Contrast-Phys+ (spatio-temporal PSD contrast, label-aware), SimPer
(periodicity contrast with frequency augmentation) and masked reconstruction of STMaps.
`dataset.ClipDataset` windows proxy zarr videos (n, 72, 128, 3) and STMaps with participant-level split
lists; `train.train_model` fixes seeds, enforces participant-grouped splits and optionally logs to MLflow;
`infer` turns windows into a pulse signal and a rate.

Not implemented: PhysMamba and RhythmMamba. Their selective state-space blocks depend on the `mamba-ssm`
package whose kernels require CUDA; the pilot stack is CPU-only (DECISIONS Q14.7) and a pure-PyTorch
re-implementation would not be the published models. The protocol lists them "if stable"; they are not.

Only the pure-architecture modules (`common`, `deepphys`, `tscan`, `efficientphys`, `physnet`,
`physformer`, `ssl`) import torch at module level; `dataset`, `train` and `infer` import it lazily, so
`import palmppg.pulse.learned` works without torch and tests `importorskip` it.
"""
from __future__ import annotations

NOT_IMPLEMENTED = {
    "PhysMamba": "mamba-ssm selective-scan kernels need CUDA; CPU-only pilot stack",
    "RhythmMamba": "mamba-ssm selective-scan kernels need CUDA; CPU-only pilot stack",
}

MODEL_NAMES = ("DeepPhys", "TSCAN", "EfficientPhys", "PhysNet", "PhysFormerLite")


def build_model(name: str, width: int = 16, **kw):
    """Instantiate one of `MODEL_NAMES` by name (torch imported here). Names in `NOT_IMPLEMENTED` raise."""
    if name in NOT_IMPLEMENTED:
        raise NotImplementedError(f"{name}: {NOT_IMPLEMENTED[name]}")
    if name == "DeepPhys":
        from palmppg.pulse.learned.deepphys import DeepPhys

        return DeepPhys(width=width, **kw)
    if name == "TSCAN":
        from palmppg.pulse.learned.tscan import TSCAN

        return TSCAN(width=width, **kw)
    if name == "EfficientPhys":
        from palmppg.pulse.learned.efficientphys import EfficientPhys

        return EfficientPhys(width=width, **kw)
    if name == "PhysNet":
        from palmppg.pulse.learned.physnet import PhysNet

        return PhysNet(width=width, **kw)
    if name == "PhysFormerLite":
        from palmppg.pulse.learned.physformer import PhysFormerLite

        return PhysFormerLite(width=width, **kw)
    raise ValueError(f"unknown model {name!r}; known: {MODEL_NAMES}")
