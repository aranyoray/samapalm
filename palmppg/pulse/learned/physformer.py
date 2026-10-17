"""PhysFormer-lite (Yu, Shen, Shi, Zhao, Torr & Zhao 2022, CVPR): temporal-difference transformer (6.3).

Stem: three 3D convolutions with (1,2,2) max pooling bring (3, T, 72, 128) to (w, T, 9, 16). Tube
tokens: a strided 3D convolution with kernel = stride = (4, 3, 4) gives T/4 x 3 x 4 tokens of `dim`
channels. Each of `depth` blocks is
    x = x + TD-MHSA(LN(x)),   x = x + ST-FF(LN(x)),
where TD-MHSA computes queries and keys with the temporal-difference convolution of the paper (CDC_T:
a 3x3x3 convolution minus theta times the 1x1x1 convolution whose kernel is the sum of the temporal
neighbours' weights, theta = 0.7) and values with a 1x1x1 convolution, and the attention is
softmax(Q K^T / (sqrt(d) gra_sharp)) V; ST-FF is a 1x1x1 expansion, a depthwise 3x3x3 convolution, ELU,
and a 1x1x1 projection. Head: spatial mean, two temporal x2 upsampling convolutions and a 1x1
projection to one value per frame. "Lite" = small `dim`, `depth` 2, no stochastic depth. Input
(N, 3, T, H, W) in [0, 1] with T divisible by 4 (the stem keeps T; tokens use T/4); output (N, T).
"""
from __future__ import annotations

import torch
import torch.nn.functional as F
from torch import nn

from palmppg.pulse.learned.common import standardise


class CDCT(nn.Module):
    """Temporal-difference 3D convolution (CDC_T): out = conv3d(x, W) - theta * conv1x1x1(x, sum_{t in {0,2}} W_t)."""

    def __init__(self, cin: int, cout: int, theta: float = 0.7) -> None:
        super().__init__()
        self.conv = nn.Conv3d(cin, cout, 3, padding=1, bias=False)
        self.theta = float(theta)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.conv(x)
        if self.theta == 0.0:
            return out
        w = self.conv.weight
        kernel_diff = (w[:, :, 0].sum(dim=(2, 3)) + w[:, :, 2].sum(dim=(2, 3)))[:, :, None, None, None]
        return out - self.theta * F.conv3d(x, kernel_diff)


class TDMHSA(nn.Module):
    def __init__(self, dim: int, heads: int, theta: float, gra_sharp: float) -> None:
        super().__init__()
        self.heads = int(heads)
        self.q = CDCT(dim, dim, theta)
        self.k = CDCT(dim, dim, theta)
        self.v = nn.Conv3d(dim, dim, 1, bias=False)
        self.proj = nn.Linear(dim, dim)
        self.gra_sharp = float(gra_sharp)

    def forward(self, x: torch.Tensor, shape: tuple[int, int, int]) -> torch.Tensor:
        n, length, dim = x.shape
        t, h, w = shape
        vol = x.transpose(1, 2).reshape(n, dim, t, h, w)
        q = self.q(vol).flatten(2).transpose(1, 2)
        k = self.k(vol).flatten(2).transpose(1, 2)
        v = self.v(vol).flatten(2).transpose(1, 2)
        hd = dim // self.heads
        q = q.view(n, length, self.heads, hd).transpose(1, 2)
        k = k.view(n, length, self.heads, hd).transpose(1, 2)
        v = v.view(n, length, self.heads, hd).transpose(1, 2)
        att = (q @ k.transpose(-2, -1)) / (hd**0.5 * self.gra_sharp)
        out = (att.softmax(dim=-1) @ v).transpose(1, 2).reshape(n, length, dim)
        return self.proj(out)


class STFeedForward(nn.Module):
    def __init__(self, dim: int, hidden: int) -> None:
        super().__init__()
        self.fc1 = nn.Conv3d(dim, hidden, 1)
        self.dw = nn.Conv3d(hidden, hidden, 3, padding=1, groups=hidden)
        self.bn = nn.BatchNorm3d(hidden)
        self.fc2 = nn.Conv3d(hidden, dim, 1)

    def forward(self, x: torch.Tensor, shape: tuple[int, int, int]) -> torch.Tensor:
        n, length, dim = x.shape
        t, h, w = shape
        vol = x.transpose(1, 2).reshape(n, dim, t, h, w)
        vol = self.fc2(F.elu(self.bn(self.dw(self.fc1(vol)))))
        return vol.flatten(2).transpose(1, 2)


class PhysFormerBlock(nn.Module):
    def __init__(self, dim: int, heads: int, theta: float, gra_sharp: float, ff_mult: int) -> None:
        super().__init__()
        self.norm1 = nn.LayerNorm(dim)
        self.attn = TDMHSA(dim, heads, theta, gra_sharp)
        self.norm2 = nn.LayerNorm(dim)
        self.ff = STFeedForward(dim, ff_mult * dim)

    def forward(self, x: torch.Tensor, shape) -> torch.Tensor:
        x = x + self.attn(self.norm1(x), shape)
        return x + self.ff(self.norm2(x), shape)


class PhysFormerLite(nn.Module):
    input_layout = "NCTHW"

    def __init__(self, width: int = 16, dim: int | None = None, depth: int = 2, heads: int = 4, theta: float = 0.7,
                 gra_sharp: float = 2.0, ff_mult: int = 2, in_channels: int = 3, patch: tuple[int, int, int] = (4, 3, 4)) -> None:
        super().__init__()
        w = int(width)
        dim = int(dim) if dim is not None else 4 * w
        if dim % heads:
            raise ValueError("dim must be divisible by heads")
        self.patch = tuple(int(p) for p in patch)
        self.stem = nn.Sequential(
            nn.Conv3d(in_channels, w // 2 or 1, (1, 5, 5), padding=(0, 2, 2)), nn.BatchNorm3d(w // 2 or 1), nn.ReLU(inplace=True),
            nn.MaxPool3d((1, 2, 2)),
            nn.Conv3d(w // 2 or 1, w, 3, padding=1), nn.BatchNorm3d(w), nn.ReLU(inplace=True),
            nn.MaxPool3d((1, 2, 2)),
            nn.Conv3d(w, w, 3, padding=1), nn.BatchNorm3d(w), nn.ReLU(inplace=True),
            nn.MaxPool3d((1, 2, 2)),
        )
        self.embed = nn.Conv3d(w, dim, self.patch, stride=self.patch)
        self.blocks = nn.ModuleList([PhysFormerBlock(dim, heads, theta, gra_sharp, ff_mult) for _ in range(depth)])
        self.norm = nn.LayerNorm(dim)
        self.up1 = nn.Sequential(nn.Upsample(scale_factor=2), nn.Conv1d(dim, dim, 3, padding=1), nn.BatchNorm1d(dim), nn.ELU())
        self.up2 = nn.Sequential(nn.Upsample(scale_factor=2), nn.Conv1d(dim, dim // 2, 3, padding=1), nn.BatchNorm1d(dim // 2), nn.ELU())
        self.head = nn.Conv1d(dim // 2, 1, 1)

    @staticmethod
    def positional_encoding(length: int, dim: int, device) -> torch.Tensor:
        """Fixed sinusoidal encoding (1, length, dim) over the token index (time-major), so the model
        has no size-dependent parameters and any T divisible by the tube length works."""
        pos = torch.arange(length, device=device, dtype=torch.float32)[:, None]
        i = torch.arange(0, dim, 2, device=device, dtype=torch.float32)
        div = torch.exp(-i * (torch.log(torch.tensor(10000.0)) / dim))
        pe = torch.zeros(length, dim, device=device)
        pe[:, 0::2] = torch.sin(pos * div)
        pe[:, 1::2] = torch.cos(pos * div)[:, : dim // 2]
        return pe[None]

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        n, _, t = x.shape[:3]
        if t % self.patch[0]:
            raise ValueError(f"PhysFormerLite needs T divisible by {self.patch[0]}, got {t}")
        h = self.embed(self.stem(standardise(x)))
        _, dim, tt, hh, ww = h.shape
        tokens = h.flatten(2).transpose(1, 2)
        tokens = tokens + self.positional_encoding(tokens.shape[1], dim, x.device)
        for blk in self.blocks:
            tokens = blk(tokens, (tt, hh, ww))
        tokens = self.norm(tokens)
        vol = tokens.transpose(1, 2).reshape(n, dim, tt, hh, ww).mean(dim=(3, 4))
        out = self.head(self.up2(self.up1(vol)))
        return out.view(n, -1)[:, :t]
