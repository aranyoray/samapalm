"""1-D generator and discriminator used by the PulseGAN and Dual-GAN trainers."""
from __future__ import annotations

import torch
import torch.nn.functional as F
from torch import nn


class Generator1D(nn.Module):
    """Small 1-D U-Net: three stride-2 encoder convolutions, three transposed-convolution decoders with
    skip connections, output cropped to the input length. ``in_ch`` lets the noise generator take
    (signal, z) pairs."""

    def __init__(self, in_ch: int = 1, hidden: int = 16, kernel: int = 7):
        super().__init__()
        p = kernel // 2
        self.e1 = nn.Sequential(nn.Conv1d(in_ch, hidden, kernel, 2, p), nn.LeakyReLU(0.2))
        self.e2 = nn.Sequential(nn.Conv1d(hidden, 2 * hidden, kernel, 2, p), nn.BatchNorm1d(2 * hidden), nn.LeakyReLU(0.2))
        self.e3 = nn.Sequential(nn.Conv1d(2 * hidden, 4 * hidden, kernel, 2, p), nn.BatchNorm1d(4 * hidden), nn.LeakyReLU(0.2))
        self.d3 = nn.Sequential(nn.ConvTranspose1d(4 * hidden, 2 * hidden, kernel, 2, p, output_padding=1),
                                nn.BatchNorm1d(2 * hidden), nn.ReLU())
        self.d2 = nn.Sequential(nn.ConvTranspose1d(4 * hidden, hidden, kernel, 2, p, output_padding=1),
                                nn.BatchNorm1d(hidden), nn.ReLU())
        self.d1 = nn.ConvTranspose1d(2 * hidden, 1, kernel, 2, p, output_padding=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        L = x.shape[-1]
        h1 = self.e1(x)
        h2 = self.e2(h1)
        h3 = self.e3(h2)
        u3 = self.d3(h3)[..., : h2.shape[-1]]
        u2 = self.d2(torch.cat([u3, h2], 1))[..., : h1.shape[-1]]
        out = self.d1(torch.cat([u2, h1], 1))[..., :L]
        if out.shape[-1] < L:
            out = F.pad(out, (0, L - out.shape[-1]))
        return out


class Discriminator1D(nn.Module):
    """Strided convolutions with LeakyReLU, global average pooling and a linear logit."""

    def __init__(self, in_ch: int = 1, hidden: int = 16, kernel: int = 7):
        super().__init__()
        p = kernel // 2
        self.net = nn.Sequential(
            nn.Conv1d(in_ch, hidden, kernel, 2, p), nn.LeakyReLU(0.2),
            nn.Conv1d(hidden, 2 * hidden, kernel, 2, p), nn.LeakyReLU(0.2),
            nn.Conv1d(2 * hidden, 4 * hidden, kernel, 2, p), nn.LeakyReLU(0.2),
        )
        self.fc = nn.Linear(4 * hidden, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.fc(self.net(x).mean(-1))


def spectral_l1(a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
    """L1 distance between magnitude spectra (the PulseGAN frequency-domain term)."""
    return (torch.fft.rfft(a, dim=-1).abs() - torch.fft.rfft(b, dim=-1).abs()).abs().mean()
