"""ResNet-18 written from scratch (torchvision is not installed) for spatio-temporal maps (protocol 9)."""
from __future__ import annotations

import torch
from torch import nn


class BasicBlock(nn.Module):
    """He et al. 2016 basic block: two 3x3 convolutions with batch norm and an identity/projection shortcut."""

    def __init__(self, in_ch: int, out_ch: int, stride: int = 1):
        super().__init__()
        self.conv1 = nn.Conv2d(in_ch, out_ch, 3, stride=stride, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(out_ch)
        self.conv2 = nn.Conv2d(out_ch, out_ch, 3, stride=1, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(out_ch)
        self.act = nn.ReLU(inplace=True)
        if stride != 1 or in_ch != out_ch:
            self.shortcut = nn.Sequential(nn.Conv2d(in_ch, out_ch, 1, stride=stride, bias=False), nn.BatchNorm2d(out_ch))
        else:
            self.shortcut = nn.Identity()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = self.act(self.bn1(self.conv1(x)))
        h = self.bn2(self.conv2(h))
        return self.act(h + self.shortcut(x))


class ResNet18(nn.Module):
    """ResNet-18 ([2, 2, 2, 2] basic blocks) with configurable base ``width`` (64 is the original).

    ``small_input=True`` uses a 3x3 stride-1 stem without max-pooling (STMaps are small: a few hundred
    patches by a few hundred frames); ``False`` uses the ImageNet 7x7/2 stem plus max-pool.
    ``embed`` returns the globally pooled 8*width features.
    """

    def __init__(self, in_ch: int = 3, out_dim: int = 1, width: int = 64, dropout: float = 0.1,
                 small_input: bool = True, layers: tuple[int, int, int, int] = (2, 2, 2, 2)):
        super().__init__()
        if small_input:
            self.stem = nn.Sequential(nn.Conv2d(in_ch, width, 3, stride=1, padding=1, bias=False), nn.BatchNorm2d(width),
                                      nn.ReLU(inplace=True))
        else:
            self.stem = nn.Sequential(nn.Conv2d(in_ch, width, 7, stride=2, padding=3, bias=False), nn.BatchNorm2d(width),
                                      nn.ReLU(inplace=True), nn.MaxPool2d(3, stride=2, padding=1))
        stages = []
        c = width
        for i, (n_blocks, mult) in enumerate(zip(layers, (1, 2, 4, 8))):
            out = width * mult
            blocks = [BasicBlock(c, out, stride=1 if i == 0 else 2)]
            blocks += [BasicBlock(out, out) for _ in range(n_blocks - 1)]
            stages.append(nn.Sequential(*blocks))
            c = out
        self.stages = nn.Sequential(*stages)
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.drop = nn.Dropout(dropout)
        self.fc = nn.Linear(c, out_dim)
        self.embed_dim = c

    def embed(self, x: torch.Tensor) -> torch.Tensor:
        h = self.stages(self.stem(x))
        return self.drop(self.pool(h).flatten(1))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.fc(self.embed(x))
