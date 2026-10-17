"""ResNet-1D backbone in the ``resnet1d`` family (Hong et al. 2020) used by PaPaGei and SiamQuality.

Layer names follow the reference implementation (``first_block_conv``, ``basicblock_list.<i>.conv1`` ...,
``final_bn``, ``dense``) so that a user-supplied checkpoint can be loaded by key; any head beyond the
backbone (PaPaGei-S mixture-of-experts heads) is reported as an unexpected key and ignored.
"""
from __future__ import annotations

import torch
import torch.nn.functional as F
from torch import nn


class Conv1dPadSame(nn.Module):
    """Conv1d with TensorFlow-style 'same' padding for any stride."""

    def __init__(self, in_channels: int, out_channels: int, kernel_size: int, stride: int, groups: int = 1):
        super().__init__()
        self.kernel_size, self.stride = kernel_size, stride
        self.conv = nn.Conv1d(in_channels, out_channels, kernel_size, stride=stride, groups=groups)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        L = x.shape[-1]
        out_len = (L + self.stride - 1) // self.stride
        p = max(0, (out_len - 1) * self.stride + self.kernel_size - L)
        return self.conv(F.pad(x, (p // 2, p - p // 2)))


class MaxPool1dPadSame(nn.Module):
    def __init__(self, kernel_size: int):
        super().__init__()
        self.kernel_size = kernel_size
        self.pool = nn.MaxPool1d(kernel_size)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        L = x.shape[-1]
        out_len = (L + self.kernel_size - 1) // self.kernel_size
        p = max(0, (out_len - 1) * self.kernel_size + self.kernel_size - L)
        return self.pool(F.pad(x, (p // 2, p - p // 2)))


class BasicBlock1D(nn.Module):
    def __init__(self, in_channels: int, out_channels: int, kernel_size: int, stride: int, groups: int,
                 downsample: bool, use_bn: bool, use_do: bool, is_first_block: bool = False):
        super().__init__()
        self.in_channels, self.out_channels = in_channels, out_channels
        self.downsample, self.use_bn, self.use_do, self.is_first_block = downsample, use_bn, use_do, is_first_block
        s = stride if downsample else 1
        self.bn1 = nn.BatchNorm1d(in_channels)
        self.relu1 = nn.ReLU()
        self.do1 = nn.Dropout(p=0.5)
        self.conv1 = Conv1dPadSame(in_channels, out_channels, kernel_size, s, groups)
        self.bn2 = nn.BatchNorm1d(out_channels)
        self.relu2 = nn.ReLU()
        self.do2 = nn.Dropout(p=0.5)
        self.conv2 = Conv1dPadSame(out_channels, out_channels, kernel_size, 1, groups)
        self.max_pool = MaxPool1dPadSame(stride)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        identity = x
        out = x
        if not self.is_first_block:
            if self.use_bn:
                out = self.bn1(out)
            out = self.relu1(out)
            if self.use_do:
                out = self.do1(out)
        out = self.conv1(out)
        if self.use_bn:
            out = self.bn2(out)
        out = self.relu2(out)
        if self.use_do:
            out = self.do2(out)
        out = self.conv2(out)
        if self.downsample:
            identity = self.max_pool(identity)
        if self.out_channels != self.in_channels:
            identity = identity.transpose(-1, -2)
            ch1 = (self.out_channels - self.in_channels) // 2
            ch2 = self.out_channels - self.in_channels - ch1
            identity = F.pad(identity, (ch1, ch2), "constant", 0).transpose(-1, -2)
        return out + identity


class ResNet1D(nn.Module):
    """``n_block`` basic blocks; filters double every ``increasefilter_gap`` blocks and the length is
    divided by ``stride`` every ``downsample_gap`` blocks; global mean over time; ``dense`` to ``n_classes``."""

    def __init__(self, in_channels: int = 1, base_filters: int = 32, kernel_size: int = 3, stride: int = 2,
                 groups: int = 1, n_block: int = 18, n_classes: int = 512, downsample_gap: int = 2,
                 increasefilter_gap: int = 4, use_bn: bool = True, use_do: bool = True):
        super().__init__()
        self.first_block_conv = Conv1dPadSame(in_channels, base_filters, kernel_size, 1)
        self.first_block_bn = nn.BatchNorm1d(base_filters)
        self.first_block_relu = nn.ReLU()
        blocks = []
        out_channels = base_filters
        for i in range(n_block):
            is_first = i == 0
            downsample = (i % downsample_gap == 1)
            if is_first:
                in_channels_i, out_channels = base_filters, base_filters
            else:
                in_channels_i = int(base_filters * 2 ** ((i - 1) // increasefilter_gap))
                out_channels = in_channels_i * 2 if (i % increasefilter_gap == 0 and i != 0) else in_channels_i
            blocks.append(BasicBlock1D(in_channels_i, out_channels, kernel_size, stride, groups, downsample,
                                       use_bn, use_do, is_first))
        self.basicblock_list = nn.ModuleList(blocks)
        self.final_bn = nn.BatchNorm1d(out_channels)
        self.final_relu = nn.ReLU()
        self.dense = nn.Linear(out_channels, n_classes)
        self.embed_dim = n_classes
        self.use_bn = use_bn

    def embed(self, x: torch.Tensor) -> torch.Tensor:
        out = self.first_block_conv(x)
        if self.use_bn:
            out = self.first_block_bn(out)
        out = self.first_block_relu(out)
        for blk in self.basicblock_list:
            out = blk(out)
        if self.use_bn:
            out = self.final_bn(out)
        out = self.final_relu(out).mean(-1)
        return self.dense(out)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.embed(x)
