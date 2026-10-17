"""DeepPhys (Chen & McDuff 2018): two-branch appearance / motion CNN with soft attention (section 6.3).

Motion branch input: normalised frame differences (`diff_normalise`); appearance branch input:
standardised raw frames. The appearance branch produces two attention masks (after the second and the
fourth convolution) that gate the motion branch, which ends in two dense layers predicting one pulse
value per frame. Widths: w, w, 2w, 2w channels (the paper uses 32 and 64); the spatial map is
adaptively pooled to `pool_hw` before the dense layers so any proxy frame size works.
Input (N, T, 3, H, W) float in [0, 1]; output (N, T).
"""
from __future__ import annotations

import torch
from torch import nn

from palmppg.pulse.learned.common import AttentionMask, diff_normalise, standardise


class DeepPhys(nn.Module):
    input_layout = "NTCHW"

    def __init__(self, width: int = 32, in_channels: int = 3, dropout: float = 0.25, hidden: int = 128,
                 pool_hw: tuple[int, int] = (4, 8)) -> None:
        super().__init__()
        w = int(width)
        self.width = w
        # motion branch
        self.m_conv1 = nn.Conv2d(in_channels, w, 3, padding=1)
        self.m_conv2 = nn.Conv2d(w, w, 3)
        self.m_conv3 = nn.Conv2d(w, 2 * w, 3, padding=1)
        self.m_conv4 = nn.Conv2d(2 * w, 2 * w, 3)
        # appearance branch
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
        motion = diff_normalise(x).flatten(0, 1)
        app = standardise(x).flatten(0, 1)
        a = torch.tanh(self.a_conv1(app))
        a = torch.tanh(self.a_conv2(a))
        g1 = self.attn1(a)
        m = torch.tanh(self.m_conv1(motion))
        m = torch.tanh(self.m_conv2(m)) * g1
        m = self.drop(self.pool(m))
        a = self.drop(self.pool(a))
        a = torch.tanh(self.a_conv3(a))
        a = torch.tanh(self.a_conv4(a))
        g2 = self.attn2(a)
        m = torch.tanh(self.m_conv3(m))
        m = torch.tanh(self.m_conv4(m)) * g2
        m = self.drop(self.pool(m))
        m = self.final_pool(m).flatten(1)
        m = self.drop(torch.tanh(self.fc1(m)))
        out = self.fc2(m)
        return out.view(n, t)
