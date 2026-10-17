"""Shared torch building blocks for the learned extractors (protocol section 6.3).

Input layout of every model is declared by its `input_layout` attribute: "NTCHW" (frame-wise networks,
DeepPhys family) or "NCTHW" (3D networks, PhysNet / PhysFormer). Frames are float in [0, 1]; the
models apply their own normalisation (`diff_normalise`, `standardise`). Outputs are (N, T) pulse
predictions in the package polarity whenever the target is (the loss is polarity-aware).
"""
from __future__ import annotations

import torch
from torch import nn


def count_parameters(module: nn.Module) -> int:
    return int(sum(p.numel() for p in module.parameters() if p.requires_grad))


def diff_normalise(x: torch.Tensor, eps: float = 1e-6) -> torch.Tensor:
    """Normalised frame differences d_t = (x_{t+1} - x_t) / (x_{t+1} + x_t + eps), divided by their SD
    over the clip (Chen & McDuff 2018, "motion representation"); a zero frame is prepended so the output
    has the input's T frames. x: (N, T, C, H, W)."""
    d = (x[:, 1:] - x[:, :-1]) / (x[:, 1:] + x[:, :-1] + eps)
    sd = d.flatten(1).std(dim=1).clamp_min(eps).view(-1, 1, 1, 1, 1)
    d = d / sd
    zero = torch.zeros_like(d[:, :1])
    return torch.cat([zero, d], dim=1)


def standardise(x: torch.Tensor, eps: float = 1e-6) -> torch.Tensor:
    """(x - mean) / sd over everything but the batch axis (appearance representation)."""
    mu = x.flatten(1).mean(dim=1).view(-1, *([1] * (x.ndim - 1)))
    sd = x.flatten(1).std(dim=1).clamp_min(eps).view(-1, *([1] * (x.ndim - 1)))
    return (x - mu) / sd


class AttentionMask(nn.Module):
    """DeepPhys soft attention: mask = (H W) sigmoid(conv1x1(x)) / (2 ||sigmoid(conv1x1(x))||_1)."""

    def __init__(self, channels: int) -> None:
        super().__init__()
        self.conv = nn.Conv2d(channels, 1, kernel_size=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        m = torch.sigmoid(self.conv(x))
        h, w = m.shape[-2:]
        norm = 2.0 * m.sum(dim=(1, 2, 3), keepdim=True).clamp_min(1e-6)
        return h * w * m / norm


class TemporalShift(nn.Module):
    """Temporal shift module (Lin et al. 2019) as used by TS-CAN: on (N*T, C, H, W) with `n_frames` = T,
    the first 1/`fold_div` of the channels are shifted one frame forward, the next 1/`fold_div` one frame
    backward, the rest stay (zero-cost temporal modelling)."""

    def __init__(self, n_frames: int, fold_div: int = 3) -> None:
        super().__init__()
        self.n_frames = int(n_frames)
        self.fold_div = int(fold_div)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        nt, c, h, w = x.shape
        t = self.n_frames
        n = nt // t
        x = x.view(n, t, c, h, w)
        fold = c // self.fold_div
        out = torch.zeros_like(x)
        out[:, 1:, :fold] = x[:, :-1, :fold]
        out[:, :-1, fold:2 * fold] = x[:, 1:, fold:2 * fold]
        out[:, :, 2 * fold:] = x[:, :, 2 * fold:]
        return out.view(nt, c, h, w)


def pearson_per_row(pred: torch.Tensor, target: torch.Tensor, eps: float = 1e-8) -> torch.Tensor:
    """Pearson correlation of each row of (N, T) `pred` with `target`."""
    p = pred - pred.mean(dim=1, keepdim=True)
    t = target - target.mean(dim=1, keepdim=True)
    num = (p * t).sum(dim=1)
    den = torch.sqrt((p * p).sum(dim=1) * (t * t).sum(dim=1)).clamp_min(eps)
    return num / den


class NegPearsonLoss(nn.Module):
    """1 - Pearson(pred, target), averaged over the batch (Yu et al. 2019); scale- and offset-free, so the
    model learns the waveform and the polarity of the target."""

    def forward(self, pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        return (1.0 - pearson_per_row(pred, target)).mean()


class StandardisedMSELoss(nn.Module):
    """MSE between per-row standardised prediction and target (amplitude-free)."""

    def forward(self, pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        p = (pred - pred.mean(dim=1, keepdim=True)) / pred.std(dim=1, keepdim=True).clamp_min(1e-6)
        t = (target - target.mean(dim=1, keepdim=True)) / target.std(dim=1, keepdim=True).clamp_min(1e-6)
        return ((p - t) ** 2).mean()


def make_loss(name: str) -> nn.Module:
    if name == "neg_pearson":
        return NegPearsonLoss()
    if name == "mse":
        return StandardisedMSELoss()
    raise ValueError("loss must be 'neg_pearson' or 'mse'")


def seed_torch(seed: int) -> torch.Generator:
    """Seed torch's global RNG and return a CPU generator seeded identically (DataLoader shuffling)."""
    torch.manual_seed(int(seed))
    g = torch.Generator()
    g.manual_seed(int(seed))
    return g
