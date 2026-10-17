"""TS-CAN (Liu, Han, Patel & McDuff 2020): DeepPhys with temporal shift modules (section 6.3).

Same two branches and attention as DeepPhys, but every convolution of the motion branch is preceded by a
temporal shift (`TemporalShift`) across the `frame_depth` frames of a window, so the per-frame network
sees its neighbours at no extra cost. Input (N, T, 3, H, W) in [0, 1]; T must equal `frame_depth`
(the window length the shifts are built for). Output (N, T).
"""
from __future__ import annotations

import torch
from torch import nn

from palmppg.pulse.learned.common import AttentionMask, TemporalShift, diff_normalise, standardise


class TSCAN(nn.Module):
    input_layout = "NTCHW"

    def __init__(self, frame_depth: int = 32, width: int = 32, in_channels: int = 3, dropout: float = 0.25,
                 hidden: int = 128, pool_hw: tuple[int, int] = (4, 8), fold_div: int = 3) -> None:
        super().__init__()
        w = int(width)
        self.frame_depth = int(frame_depth)
        self.tsm1 = TemporalShift(frame_depth, fold_div)
        self.tsm2 = TemporalShift(frame_depth, fold_div)
        self.tsm3 = TemporalShift(frame_depth, fold_div)
        self.tsm4 = TemporalShift(frame_depth, fold_div)
        self.m_conv1 = nn.Conv2d(in_channels, w, 3, padding=1)
        self.m_conv2 = nn.Conv2d(w, w, 3)
        self.m_conv3 = nn.Conv2d(w, 2 * w, 3, padding=1)
        self.m_conv4 = nn.Conv2d(2 * w, 2 * w, 3)
        self.a_conv1 = nn.Conv2d(in_channels, w, 3, padding=1)
        self.a_conv2 = nn.Conv2d(w, w, 3)
        self.a_conv3 = nn.Conv2d(w, 2 * w, 3, padding=1)
        self.a_conv4 = nn.Conv2d(2 * w, 2 * w, 3)
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
            raise ValueError(f"TS-CAN was built for {self.frame_depth} frames per window, got {t}")
        motion = diff_normalise(x).flatten(0, 1)
        app = standardise(x).flatten(0, 1)
        a = torch.tanh(self.a_conv1(app))
        a = torch.tanh(self.a_conv2(a))
        g1 = self.attn1(a)
        m = torch.tanh(self.m_conv1(self.tsm1(motion)))
        m = torch.tanh(self.m_conv2(self.tsm2(m))) * g1
        m = self.drop(self.pool(m))
        a = self.drop(self.pool(a))
        a = torch.tanh(self.a_conv3(a))
        a = torch.tanh(self.a_conv4(a))
        g2 = self.attn2(a)
        m = torch.tanh(self.m_conv3(self.tsm3(m)))
        m = torch.tanh(self.m_conv4(self.tsm4(m))) * g2
        m = self.drop(self.pool(m))
        m = self.final_pool(m).flatten(1)
        m = self.drop(torch.tanh(self.fc1(m)))
        return self.fc2(m).view(n, t)
