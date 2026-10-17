"""PhysNet (Yu, Li & Zhao 2019), 3D CNN encoder-decoder on (3, T, 72, 128) proxy clips (section 6.3, E4).

Spatio-temporal convolutions (1x5x5 stem, then 3x3x3 blocks) with max pooling (1,2,2), (2,2,2), (2,2,2),
(1,2,2), two temporal transposed convolutions that restore T, global spatial average pooling and a 1x1x1
convolution producing one value per frame. Channel widths w, 2w, 2w (the paper: 16, 32, 64). Input
(N, 3, T, H, W) float in [0, 1] (standardised inside), T divisible by 4; output (N, T).
"""
from __future__ import annotations

import torch
from torch import nn

from palmppg.pulse.learned.common import standardise


def _block(cin: int, cout: int, k, p) -> nn.Sequential:
    return nn.Sequential(nn.Conv3d(cin, cout, k, stride=1, padding=p), nn.BatchNorm3d(cout), nn.ReLU(inplace=True))


class PhysNet(nn.Module):
    input_layout = "NCTHW"

    def __init__(self, width: int = 16, in_channels: int = 3) -> None:
        super().__init__()
        w = int(width)
        self.block1 = _block(in_channels, w, (1, 5, 5), (0, 2, 2))
        self.pool1 = nn.MaxPool3d((1, 2, 2))
        self.block2 = _block(w, 2 * w, 3, 1)
        self.block3 = _block(2 * w, 2 * w, 3, 1)
        self.pool2 = nn.MaxPool3d((2, 2, 2))
        self.block4 = _block(2 * w, 2 * w, 3, 1)
        self.block5 = _block(2 * w, 2 * w, 3, 1)
        self.pool3 = nn.MaxPool3d((2, 2, 2))
        self.block6 = _block(2 * w, 2 * w, 3, 1)
        self.block7 = _block(2 * w, 2 * w, 3, 1)
        self.pool4 = nn.MaxPool3d((1, 2, 2))
        self.block8 = _block(2 * w, 2 * w, 3, 1)
        self.block9 = _block(2 * w, 2 * w, 3, 1)
        self.up1 = nn.Sequential(nn.ConvTranspose3d(2 * w, 2 * w, (4, 1, 1), stride=(2, 1, 1), padding=(1, 0, 0)),
                                 nn.BatchNorm3d(2 * w), nn.ELU())
        self.up2 = nn.Sequential(nn.ConvTranspose3d(2 * w, 2 * w, (4, 1, 1), stride=(2, 1, 1), padding=(1, 0, 0)),
                                 nn.BatchNorm3d(2 * w), nn.ELU())
        self.head = nn.Conv3d(2 * w, 1, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        n, _, t = x.shape[:3]
        if t % 4:
            raise ValueError(f"PhysNet needs T divisible by 4, got {t}")
        h = standardise(x)
        h = self.pool1(self.block1(h))
        h = self.pool2(self.block3(self.block2(h)))
        h = self.pool3(self.block5(self.block4(h)))
        h = self.pool4(self.block7(self.block6(h)))
        h = self.block9(self.block8(h))
        h = self.up2(self.up1(h))
        h = h.mean(dim=(3, 4), keepdim=True)
        return self.head(h).view(n, -1)[:, :t]
