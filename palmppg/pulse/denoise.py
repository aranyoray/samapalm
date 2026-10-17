"""Adversarial pulse denoising: PulseGAN-style and Dual-GAN-lite (protocol section 9 model zoo).

PulseGAN (Song et al. 2021): a 1D U-Net generator maps a noisy rPPG window to a clean pulse window and a
conditional discriminator judges (noisy, candidate) pairs; the generator loss adds an L1 waveform term
and an L1 spectral-magnitude term to the adversarial term. Dual-GAN-lite (after Lu, Han & Zhou 2021):
two generators, one predicting the pulse and one the noise, with a consistency term
G_pulse(x) + G_noise(x) = x, plus the adversarial term on the pulse.

Protocol 11.10: GAN outputs never appear in a headline result. Everything here is judged only by the
downstream metrics of the experiment that consumes it (E4 / E15) and is reported as such. torch is
imported at module level (the module is entirely torch); tests `importorskip` it.
"""
from __future__ import annotations

import time

import numpy as np
import torch
import torch.nn.functional as F
from torch import nn

from palmppg.core.config import rng


def _seed(seed: int, salt: str) -> torch.Generator:
    s = int(rng(seed, salt).integers(0, 2**31 - 1))
    torch.manual_seed(s)
    g = torch.Generator()
    g.manual_seed(s)
    return g


def _conv(cin: int, cout: int, k: int, stride: int = 1) -> nn.Sequential:
    return nn.Sequential(nn.Conv1d(cin, cout, k, stride=stride, padding=k // 2), nn.BatchNorm1d(cout), nn.LeakyReLU(0.2))


class PulseGenerator1D(nn.Module):
    """1D U-Net: three encoder levels (stride-2 down-sampling), bottleneck, three decoder levels with skip
    connections, linear output. (N, in_channels, T) -> (N, 1, T); T is padded to a multiple of 8."""

    def __init__(self, width: int = 16, in_channels: int = 1, depth: int = 3) -> None:
        super().__init__()
        w = int(width)
        self.depth = int(depth)
        self.inp = _conv(in_channels, w, 7)
        self.down = nn.ModuleList()
        self.up = nn.ModuleList()
        self.dec = nn.ModuleList()
        chans = [w * (2**i) for i in range(self.depth + 1)]
        for i in range(self.depth):
            self.down.append(_conv(chans[i], chans[i + 1], 5, stride=2))
        self.bottleneck = _conv(chans[-1], chans[-1], 3)
        for i in reversed(range(self.depth)):
            self.up.append(nn.ConvTranspose1d(chans[i + 1], chans[i], 4, stride=2, padding=1))
            self.dec.append(_conv(2 * chans[i], chans[i], 3))
        self.out = nn.Conv1d(w, 1, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        t = x.shape[-1]
        mult = 2**self.depth
        pad = (-t) % mult
        if pad:
            x = F.pad(x, (0, pad), mode="reflect")
        h = self.inp(x)
        skips = [h]
        for d in self.down:
            h = d(h)
            skips.append(h)
        h = self.bottleneck(h)
        for u, dcv in zip(self.up, self.dec):
            h = u(h)
            skip = skips[-2]
            skips.pop()
            h = dcv(torch.cat([h, skip], dim=1))
        return self.out(h)[..., :t]


class PulseDiscriminator1D(nn.Module):
    """Strided 1D convolutions + global average pooling + linear logit. `in_channels` = 2 for the
    conditional PulseGAN discriminator ((noisy, candidate) stacked), 1 for an unconditional one."""

    def __init__(self, width: int = 16, in_channels: int = 2) -> None:
        super().__init__()
        w = int(width)
        self.net = nn.Sequential(
            nn.Conv1d(in_channels, w, 7, stride=2, padding=3), nn.LeakyReLU(0.2),
            nn.Conv1d(w, 2 * w, 5, stride=2, padding=2), nn.BatchNorm1d(2 * w), nn.LeakyReLU(0.2),
            nn.Conv1d(2 * w, 4 * w, 5, stride=2, padding=2), nn.BatchNorm1d(4 * w), nn.LeakyReLU(0.2),
            nn.AdaptiveAvgPool1d(1), nn.Flatten(), nn.Linear(4 * w, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class DualGANLite(nn.Module):
    """Two U-Net generators: `g_pulse` predicts the clean pulse and `g_noise` the noise of a window, tied by
    the consistency x = g_pulse(x) + g_noise(x). forward -> (pulse, noise)."""

    def __init__(self, width: int = 16) -> None:
        super().__init__()
        self.g_pulse = PulseGenerator1D(width)
        self.g_noise = PulseGenerator1D(width)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        return self.g_pulse(x), self.g_noise(x)


def _standardise_rows(a: np.ndarray) -> np.ndarray:
    a = np.asarray(a, dtype=np.float32)
    mu = a.mean(axis=1, keepdims=True)
    sd = a.std(axis=1, keepdims=True)
    return (a - mu) / np.where(sd > 1e-8, sd, 1.0)


def _spectral_l1(a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
    return (torch.fft.rfft(a, dim=-1).abs() - torch.fft.rfft(b, dim=-1).abs()).abs().mean()


def train_pulsegan(noisy: np.ndarray, clean: np.ndarray, width: int = 16, epochs: int = 2, seed: int = 0, lr: float = 2e-4,
                   batch_size: int = 8, lambda_l1: float = 10.0, lambda_spec: float = 1.0,
                   device: str = "cpu") -> tuple[PulseGenerator1D, PulseDiscriminator1D, dict]:
    """Train a PulseGAN pair on paired windows `noisy`, `clean` (M, T), fixed seeds.

    Generator loss: BCE(D(x, G(x)), 1) + lambda_l1 |G(x) - y|_1 + lambda_spec | |FFT G(x)| - |FFT y| |_1;
    discriminator loss: BCE(D(x, y), 1) + BCE(D(x, G(x)), 0). Returns (generator, discriminator, history)
    with history {"g_loss": [...], "d_loss": [...], "l1": [...], "elapsed_s"}. Outputs feed downstream
    metrics only (protocol 11.10).
    """
    g = _seed(seed, "pulsegan")
    x = torch.from_numpy(_standardise_rows(noisy))[:, None, :]
    y = torch.from_numpy(_standardise_rows(clean))[:, None, :]
    gen = PulseGenerator1D(width).to(device)
    disc = PulseDiscriminator1D(width, in_channels=2).to(device)
    opt_g = torch.optim.Adam(gen.parameters(), lr=lr, betas=(0.5, 0.999))
    opt_d = torch.optim.Adam(disc.parameters(), lr=lr, betas=(0.5, 0.999))
    bce = nn.BCEWithLogitsLoss()
    hist = {"g_loss": [], "d_loss": [], "l1": []}
    t0 = time.time()
    m = x.shape[0]
    for _ in range(int(epochs)):
        perm = torch.randperm(m, generator=g)
        gl, dl, l1s, nb = 0.0, 0.0, 0.0, 0
        for i in range(0, m, batch_size):
            idx = perm[i:i + batch_size]
            xb, yb = x[idx].to(device), y[idx].to(device)
            fake = gen(xb)
            # discriminator step
            opt_d.zero_grad()
            d_real = disc(torch.cat([xb, yb], dim=1))
            d_fake = disc(torch.cat([xb, fake.detach()], dim=1))
            loss_d = bce(d_real, torch.ones_like(d_real)) + bce(d_fake, torch.zeros_like(d_fake))
            loss_d.backward()
            opt_d.step()
            # generator step
            opt_g.zero_grad()
            d_fake = disc(torch.cat([xb, fake], dim=1))
            l1 = (fake - yb).abs().mean()
            loss_g = bce(d_fake, torch.ones_like(d_fake)) + lambda_l1 * l1 + lambda_spec * _spectral_l1(fake, yb)
            loss_g.backward()
            opt_g.step()
            gl += float(loss_g)
            dl += float(loss_d)
            l1s += float(l1)
            nb += 1
        hist["g_loss"].append(gl / max(nb, 1))
        hist["d_loss"].append(dl / max(nb, 1))
        hist["l1"].append(l1s / max(nb, 1))
    hist["elapsed_s"] = time.time() - t0
    return gen, disc, hist


def train_dual_gan_lite(noisy: np.ndarray, clean: np.ndarray, width: int = 16, epochs: int = 2, seed: int = 0, lr: float = 2e-4,
                        batch_size: int = 8, lambda_rec: float = 10.0, lambda_cons: float = 5.0,
                        device: str = "cpu") -> tuple[DualGANLite, PulseDiscriminator1D, dict]:
    """Train Dual-GAN-lite on paired windows: L_G = BCE(D(G_p(x)), 1) + lambda_rec (|G_p(x) - y|_1 +
    |G_n(x) - (x - y)|_1) + lambda_cons |G_p(x) + G_n(x) - x|_1; L_D = BCE(D(y), 1) + BCE(D(G_p(x)), 0)
    (unconditional discriminator on the pulse). Returns (model, discriminator, history)."""
    g = _seed(seed, "dualgan")
    x = torch.from_numpy(_standardise_rows(noisy))[:, None, :]
    y = torch.from_numpy(_standardise_rows(clean))[:, None, :]
    model = DualGANLite(width).to(device)
    disc = PulseDiscriminator1D(width, in_channels=1).to(device)
    opt_g = torch.optim.Adam(model.parameters(), lr=lr, betas=(0.5, 0.999))
    opt_d = torch.optim.Adam(disc.parameters(), lr=lr, betas=(0.5, 0.999))
    bce = nn.BCEWithLogitsLoss()
    hist = {"g_loss": [], "d_loss": [], "rec": [], "cons": []}
    t0 = time.time()
    m = x.shape[0]
    for _ in range(int(epochs)):
        perm = torch.randperm(m, generator=g)
        gl, dl, rec_s, cons_s, nb = 0.0, 0.0, 0.0, 0.0, 0
        for i in range(0, m, batch_size):
            idx = perm[i:i + batch_size]
            xb, yb = x[idx].to(device), y[idx].to(device)
            pulse, noise = model(xb)
            opt_d.zero_grad()
            d_real = disc(yb)
            d_fake = disc(pulse.detach())
            loss_d = bce(d_real, torch.ones_like(d_real)) + bce(d_fake, torch.zeros_like(d_fake))
            loss_d.backward()
            opt_d.step()
            opt_g.zero_grad()
            rec = (pulse - yb).abs().mean() + (noise - (xb - yb)).abs().mean()
            cons = (pulse + noise - xb).abs().mean()
            d_fake = disc(pulse)
            loss_g = bce(d_fake, torch.ones_like(d_fake)) + lambda_rec * rec + lambda_cons * cons
            loss_g.backward()
            opt_g.step()
            gl += float(loss_g)
            dl += float(loss_d)
            rec_s += float(rec)
            cons_s += float(cons)
            nb += 1
        hist["g_loss"].append(gl / max(nb, 1))
        hist["d_loss"].append(dl / max(nb, 1))
        hist["rec"].append(rec_s / max(nb, 1))
        hist["cons"].append(cons_s / max(nb, 1))
    hist["elapsed_s"] = time.time() - t0
    return model, disc, hist


def denoise(generator: nn.Module, x: np.ndarray, device: str = "cpu") -> np.ndarray:
    """Apply a trained generator to one (T,) or (M, T) signal; input and output are standardised."""
    a = np.asarray(x, dtype=np.float32)
    single = a.ndim == 1
    rows = _standardise_rows(a[None] if single else a)
    generator.eval()
    with torch.no_grad():
        out = generator(torch.from_numpy(rows)[:, None, :].to(device))
        if isinstance(out, tuple):
            out = out[0]
        out = out[:, 0, :].cpu().numpy()
    out = _standardise_rows(out)
    return out[0] if single else out
