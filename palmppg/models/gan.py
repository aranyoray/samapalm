"""PulseGAN and Dual-GAN pulse denoisers (protocol section 9 "Dual-GAN and PulseGAN denoising judged
only by downstream metrics"; section 6.3 learned extraction; section 11.10).

Outputs of these trainers are judged **only** by downstream metrics (pulse-rate agreement with ECG,
SQI, coverage, morphology stability in the augmentation study) and **never appear in a headline
result**; GAN or diffusion outputs are not evidence of a pulse on their own.

* ``PulseGANTrainer`` (Song et al. 2021): a conditional GAN whose 1-D U-Net generator maps a noisy
  pulse window to a clean one; the discriminator sees (noisy, candidate) pairs; the generator loss is
  adversarial + lambda_time * L1 (time) + lambda_spec * L1 (magnitude spectrum).
* ``DualGANTrainer`` (Lu et al. 2021): a BVP-GAN (noisy -> clean) and a Noise-GAN (clean + z -> noise)
  trained jointly; the noise generator produces realistic noisy copies of clean windows that the
  BVP generator must also invert (cycle term), which regularises the denoiser with few paired windows.

Both expose ``fit(noisy_windows, clean_windows)`` on equal-length 1-D windows and ``denoise(x)``.
"""
from __future__ import annotations

import numpy as np
from sklearn.base import BaseEstimator

from palmppg.core.config import rng
from palmppg.models._torchbase import derived_seed


def _windows(X) -> np.ndarray:
    arr = np.asarray([np.asarray(x, dtype=np.float32).ravel() for x in X], dtype=np.float32)
    if arr.ndim != 2 or arr.shape[0] == 0:
        raise ValueError("windows must be a list of equal-length 1-D arrays")
    mu = arr.mean(axis=1, keepdims=True)
    sd = np.maximum(arr.std(axis=1, keepdims=True), 1e-6)
    return np.nan_to_num((arr - mu) / sd).astype(np.float32)


class _GANBase(BaseEstimator):
    def __init__(self, epochs: int = 20, lr: float = 2e-4, seed: int = 0, device: str = "cpu", batch_size: int = 16,
                 hidden: int = 16, verbose: bool = False):
        self.epochs = epochs
        self.lr = lr
        self.seed = seed
        self.device = device
        self.batch_size = batch_size
        self.hidden = hidden
        self.verbose = verbose

    @staticmethod
    def _torch():
        import torch

        return torch

    def _batches(self, n: int, epoch: int):
        perm = rng(self.seed, f"gan-epoch:{epoch}").permutation(n)
        bs = max(2, min(int(self.batch_size), n))
        for s in range(0, n, bs):
            idx = perm[s:s + bs]
            if idx.size >= 2:
                yield idx

    def denoise(self, x) -> np.ndarray:
        """Denoised window(s) in z-score units, same shape as the input (1-D array or list of windows)."""
        torch = self._torch()
        single = np.ndim(x) == 1
        W = _windows([x] if single else x)
        self.G_.eval()
        with torch.no_grad():
            out = self.G_(torch.from_numpy(W)[:, None, :].to(self.device))[:, 0, :].cpu().numpy()
        return out[0] if single else out


class PulseGANTrainer(_GANBase):
    """Conditional PulseGAN trainer; after ``fit``: ``G_`` (generator), ``D_``, ``history_`` (per-epoch losses)."""

    def __init__(self, epochs: int = 20, lr: float = 2e-4, seed: int = 0, device: str = "cpu", batch_size: int = 16,
                 hidden: int = 16, verbose: bool = False, lambda_time: float = 10.0, lambda_spec: float = 1.0):
        super().__init__(epochs, lr, seed, device, batch_size, hidden, verbose)
        self.lambda_time = lambda_time
        self.lambda_spec = lambda_spec

    def fit(self, noisy, clean):
        torch = self._torch()
        from palmppg.models.nets.gan import Discriminator1D, Generator1D, spectral_l1

        torch.manual_seed(derived_seed(self.seed, "pulsegan"))
        Xn, Xc = _windows(noisy), _windows(clean)
        if Xn.shape != Xc.shape:
            raise ValueError("noisy and clean windows must have the same shape")
        n = Xn.shape[0]
        G, D = Generator1D(1, self.hidden).to(self.device), Discriminator1D(2, self.hidden).to(self.device)
        oG = torch.optim.Adam(G.parameters(), lr=self.lr, betas=(0.5, 0.999))
        oD = torch.optim.Adam(D.parameters(), lr=self.lr, betas=(0.5, 0.999))
        bce, l1 = torch.nn.BCEWithLogitsLoss(), torch.nn.L1Loss()
        self.history_ = {"d": [], "g_adv": [], "g_time": [], "g_spec": []}
        for epoch in range(int(self.epochs)):
            G.train()
            D.train()
            acc = {k: 0.0 for k in self.history_}
            seen = 0
            for idx in self._batches(n, epoch):
                xn = torch.from_numpy(Xn[idx])[:, None, :].to(self.device)
                xc = torch.from_numpy(Xc[idx])[:, None, :].to(self.device)
                ones, zeros = torch.ones(idx.size, 1, device=self.device), torch.zeros(idx.size, 1, device=self.device)
                fake = G(xn)
                d_loss = bce(D(torch.cat([xn, xc], 1)), ones) + bce(D(torch.cat([xn, fake.detach()], 1)), zeros)
                oD.zero_grad()
                d_loss.backward()
                oD.step()
                g_adv = bce(D(torch.cat([xn, fake], 1)), ones)
                g_time = l1(fake, xc)
                g_spec = spectral_l1(fake, xc)
                g_loss = g_adv + self.lambda_time * g_time + self.lambda_spec * g_spec
                oG.zero_grad()
                g_loss.backward()
                oG.step()
                for k, v in zip(acc, (d_loss, g_adv, g_time, g_spec)):
                    acc[k] += float(v.item()) * idx.size
                seen += idx.size
            for k, v in acc.items():
                self.history_[k].append(v / max(seen, 1))
        self.G_, self.D_ = G.eval(), D.eval()
        return self


class DualGANTrainer(_GANBase):
    """Dual-GAN trainer: BVP generator ``G_`` (noisy -> clean), noise generator ``Gn_`` (clean, z -> noise),
    discriminators ``D_`` (clean) and ``Dn_`` (noisy); ``history_`` per epoch."""

    def __init__(self, epochs: int = 20, lr: float = 2e-4, seed: int = 0, device: str = "cpu", batch_size: int = 16,
                 hidden: int = 16, verbose: bool = False, lambda_rec: float = 10.0, lambda_cycle: float = 5.0):
        super().__init__(epochs, lr, seed, device, batch_size, hidden, verbose)
        self.lambda_rec = lambda_rec
        self.lambda_cycle = lambda_cycle

    def fit(self, noisy, clean):
        torch = self._torch()
        from palmppg.models.nets.gan import Discriminator1D, Generator1D

        torch.manual_seed(derived_seed(self.seed, "dualgan"))
        Xn, Xc = _windows(noisy), _windows(clean)
        if Xn.shape != Xc.shape:
            raise ValueError("noisy and clean windows must have the same shape")
        n = Xn.shape[0]
        Gb, Gn = Generator1D(1, self.hidden).to(self.device), Generator1D(2, self.hidden).to(self.device)
        Db, Dn = Discriminator1D(1, self.hidden).to(self.device), Discriminator1D(1, self.hidden).to(self.device)
        oG = torch.optim.Adam(list(Gb.parameters()) + list(Gn.parameters()), lr=self.lr, betas=(0.5, 0.999))
        oD = torch.optim.Adam(list(Db.parameters()) + list(Dn.parameters()), lr=self.lr, betas=(0.5, 0.999))
        bce, l1 = torch.nn.BCEWithLogitsLoss(), torch.nn.L1Loss()
        self.history_ = {"d": [], "g_adv": [], "g_rec": [], "g_cycle": []}
        gen = torch.Generator(device="cpu").manual_seed(derived_seed(self.seed, "dualgan-z"))
        for epoch in range(int(self.epochs)):
            for m in (Gb, Gn, Db, Dn):
                m.train()
            acc = {k: 0.0 for k in self.history_}
            seen = 0
            for idx in self._batches(n, epoch):
                xn = torch.from_numpy(Xn[idx])[:, None, :].to(self.device)
                xc = torch.from_numpy(Xc[idx])[:, None, :].to(self.device)
                z = torch.randn(xc.shape, generator=gen).to(self.device)
                ones, zeros = torch.ones(idx.size, 1, device=self.device), torch.zeros(idx.size, 1, device=self.device)
                bvp = Gb(xn)                                  # denoised
                synth_noisy = xc + Gn(torch.cat([xc, z], 1))   # clean + modelled noise
                d_loss = (bce(Db(xc), ones) + bce(Db(bvp.detach()), zeros)
                          + bce(Dn(xn), ones) + bce(Dn(synth_noisy.detach()), zeros))
                oD.zero_grad()
                d_loss.backward()
                oD.step()
                g_adv = bce(Db(bvp), ones) + bce(Dn(synth_noisy), ones)
                g_rec = l1(bvp, xc)
                g_cycle = l1(Gb(synth_noisy), xc)
                g_loss = g_adv + self.lambda_rec * g_rec + self.lambda_cycle * g_cycle
                oG.zero_grad()
                g_loss.backward()
                oG.step()
                for k, v in zip(acc, (d_loss, g_adv, g_rec, g_cycle)):
                    acc[k] += float(v.item()) * idx.size
                seen += idx.size
            for k, v in acc.items():
                self.history_[k].append(v / max(seen, 1))
        self.G_, self.Gn_, self.D_, self.Dn_ = Gb.eval(), Gn.eval(), Db.eval(), Dn.eval()
        return self


__all__ = ["DualGANTrainer", "PulseGANTrainer"]
