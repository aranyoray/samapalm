"""EfficientPhys (Liu, Hill, Jiang, Patel & McDuff 2023): single-branch TSM network (section 6.3).

The hand-crafted difference and appearance inputs of DeepPhys are replaced by a learnable
normalisation-difference layer (frame difference followed by batch normalisation) and the appearance
attention by self-attention masks on the same branch: TSM + conv (x2), self-attention mask, average
pool, TSM + conv (x2), self-attention mask, average pool, dense layers. Input (N, T, 3, H, W) in [0, 1]
with T = `frame_depth`; output (N, T) (a zero difference frame is prepended).
"""
from __future__ import annotations

import torch
from torch import nn

from palmppg.pulse.learned.common import AttentionMask, TemporalShift


class EfficientPhys(nn.Module):
    input_layout = "NTCHW"

    def __init__(self, frame_depth: int = 32, width: int = 32, in_channels: int = 3, dropout: float = 0.25,
                 hidden: int = 128, pool_hw: tuple[int, int] = (4, 8), fold_div: int = 3) -> None:
        super().__init__()
        w = int(width)
        self.frame_depth = int(frame_depth)
        self.norm_diff = nn.BatchNorm2d(in_channels)
        self.tsm1 = TemporalShift(frame_depth, fold_div)
        self.tsm2 = TemporalShift(frame_depth, fold_div)
        self.tsm3 = TemporalShift(frame_depth, fold_div)
        self.tsm4 = TemporalShift(frame_depth, fold_div)
        self.conv1 = nn.Conv2d(in_channels, w, 3, padding=1)
        self.conv2 = nn.Conv2d(w, w, 3)
        self.conv3 = nn.Conv2d(w, 2 * w, 3, padding=1)
        self.conv4 = nn.Conv2d(2 * w, 2 * w, 3)
        self.attn1 = AttentionMask(w)
        self.attn2 = AttentionMask(2 * w)
        self.pool = nn.AvgPool2d(2)
        self.drop = nn.Dropout(dropout)
        self.final_pool = nn.AdaptiveAvgPool2d(pool_hw)
        self.fc1 = nn.Linear(2 * w * pool_hw[0] * pool_hw[1], hidden)
        self.fc2 = nn.Linear(hidden, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        n, t = x.shape[:2]
        if t != self.frame_depth:
            raise ValueError(f"EfficientPhys was built for {self.frame_depth} frames per window, got {t}")
        d = x[:, 1:] - x[:, :-1]
        d = torch.cat([torch.zeros_like(d[:, :1]), d], dim=1).flatten(0, 1)
        d = self.norm_diff(d)
        h = torch.tanh(self.conv1(self.tsm1(d)))
        h = torch.tanh(self.conv2(self.tsm2(h)))
        h = h * self.attn1(h)
        h = self.drop(self.pool(h))
        h = torch.tanh(self.conv3(self.tsm3(h)))
        h = torch.tanh(self.conv4(self.tsm4(h)))
        h = h * self.attn2(h)
        h = self.drop(self.pool(h))
        h = self.final_pool(h).flatten(1)
        h = self.drop(torch.tanh(self.fc1(h)))
        return self.fc2(h).view(n, t)
