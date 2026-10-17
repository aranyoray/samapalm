"""Self-supervised objectives for pulse extraction (protocol section 6.3 "self-supervised Contrast-Phys+,
SimPer, MAE on STMaps from development data only").

* `contrast_phys_plus_loss`: Contrast-Phys (Sun & Li 2022) samples rPPG signals from different spatial
  positions and temporal crops of a spatio-temporal rPPG block (N, S, T); their normalised power spectra
  in the rate band must agree within a video (positive pairs, mean squared PSD distance pulled down) and
  differ across videos (negative pairs, pushed up): L = L_pos - L_neg. Contrast-Phys+ (Sun & Li 2024)
  adds label awareness: when a ground-truth pulse is available for a video, its PSD joins that video's
  positive set and the negative set of every other video.
* `simper_loss` with `frequency_augment`: SimPer (Yang et al. 2023) builds views of each clip at
  different speeds (frequency augmentation by temporal resampling); the feature similarity between two
  views is pulled towards a soft target that decays with the speed difference (soft-label InfoNCE over
  periodicity similarity, here the cosine similarity of band-limited normalised PSDs).
* `STMapMAE`: masked-autoencoder reconstruction of STMap images (C, P, T): random patch masking, a small
  transformer encoder on the visible patches, a light decoder, MSE on the masked patches; `encode` gives
  an embedding for downstream models.
torch is imported at module level (this module is entirely torch).
"""
from __future__ import annotations

import torch
import torch.nn.functional as F
from torch import nn


# --------------------------------------------------------------------------- spectra
def band_psd(x: torch.Tensor, fs: float, band: tuple[float, float], nfft: int | None = None) -> tuple[torch.Tensor, torch.Tensor]:
    """Normalised power spectrum of each row of (N, T) inside `band`: (freqs (F,), psd (N, F) summing to 1)."""
    x = x - x.mean(dim=1, keepdim=True)
    n = x.shape[1]
    nfft = nfft or max(4 * n, 512)
    spec = torch.fft.rfft(x, n=nfft, dim=1).abs() ** 2
    freqs = torch.fft.rfftfreq(nfft, d=1.0 / fs).to(x.device)
    sel = (freqs >= band[0]) & (freqs <= band[1])
    p = spec[:, sel]
    return freqs[sel], p / p.sum(dim=1, keepdim=True).clamp_min(1e-12)


# --------------------------------------------------------------------------- Contrast-Phys+
def sample_st_signals(st_block: torch.Tensor, n_space: int, n_time: int, crop_len: int, generator: torch.Generator | None = None):
    """Sample `n_space` spatial positions x `n_time` temporal crops of length `crop_len` from (N, S, T).
    Returns (signals (N, n_space*n_time, crop_len), spatial index, start index)."""
    n, s, t = st_block.shape
    if crop_len > t:
        raise ValueError("crop_len longer than the block")
    sp = torch.randint(0, s, (n, n_space), generator=generator)
    st = torch.randint(0, t - crop_len + 1, (n, n_time), generator=generator)
    out = torch.empty(n, n_space * n_time, crop_len, dtype=st_block.dtype, device=st_block.device)
    for i in range(n):
        k = 0
        for a in range(n_space):
            for b in range(n_time):
                out[i, k] = st_block[i, sp[i, a], st[i, b]:st[i, b] + crop_len]
                k += 1
    return out, sp, st


def contrast_phys_plus_loss(
    st_block: torch.Tensor, fs: float, band: tuple[float, float], n_space: int = 2, n_time: int = 2,
    crop_len: int | None = None, labels: torch.Tensor | None = None, label_mask: torch.Tensor | None = None,
    generator: torch.Generator | None = None,
) -> dict:
    """Contrast-Phys+ loss on a batch of ST-rPPG blocks (N, S, T) predicted by a network.

    `labels` (N, T) optional ground-truth pulses with `label_mask` (N,) bool saying which are real.
    Returns {"loss", "pos", "neg"}: loss = pos - neg where pos is the mean squared distance between
    normalised PSDs of samples of the same video (and its label), neg the same between different videos.
    """
    n, s, t = st_block.shape
    crop_len = crop_len or t
    sig, _, starts = sample_st_signals(st_block, n_space, n_time, crop_len, generator)
    k = sig.shape[1]
    _, psd = band_psd(sig.reshape(n * k, crop_len), fs, band)
    psd = psd.reshape(n, k, -1)
    groups = [psd[i] for i in range(n)]
    if labels is not None:
        if label_mask is None:
            label_mask = torch.ones(n, dtype=torch.bool)
        for i in range(n):
            if bool(label_mask[i]):
                crops = torch.stack([labels[i, int(starts[i, b]):int(starts[i, b]) + crop_len] for b in range(n_time)])
                _, lp = band_psd(crops, fs, band)
                groups[i] = torch.cat([groups[i], lp], dim=0)
    pos_terms, neg_terms = [], []
    for i in range(n):
        gi = groups[i]
        if gi.shape[0] > 1:
            d = ((gi[:, None, :] - gi[None, :, :]) ** 2).mean(dim=2)
            iu = torch.triu_indices(gi.shape[0], gi.shape[0], offset=1)
            pos_terms.append(d[iu[0], iu[1]].mean())
        for j in range(i + 1, n):
            gj = groups[j]
            neg_terms.append(((gi[:, None, :] - gj[None, :, :]) ** 2).mean())
    pos = torch.stack(pos_terms).mean() if pos_terms else torch.zeros((), device=st_block.device)
    neg = torch.stack(neg_terms).mean() if neg_terms else torch.zeros((), device=st_block.device)
    return {"loss": pos - neg, "pos": pos, "neg": neg}


# --------------------------------------------------------------------------- SimPer
def frequency_augment(x: torch.Tensor, speeds: torch.Tensor, out_len: int) -> torch.Tensor:
    """Resample each (T,) row of `x` (N, T) at `speeds` (N,) so the output of `out_len` samples plays the
    signal `speed` times faster (periodicity scaled by `speed`); linear interpolation, requires
    out_len * max(speed) <= T."""
    n, t = x.shape
    pos = torch.arange(out_len, dtype=x.dtype, device=x.device)[None, :] * speeds.to(x.dtype)[:, None]
    if float(pos.max()) > t - 1:
        raise ValueError("speed x out_len exceeds the source length")
    lo = pos.floor().long().clamp(0, t - 2)
    frac = (pos - lo.to(x.dtype))
    left = torch.gather(x, 1, lo)
    right = torch.gather(x, 1, lo + 1)
    return left * (1 - frac) + right * frac


def periodicity_similarity(a: torch.Tensor, b: torch.Tensor, fs: float, band: tuple[float, float]) -> torch.Tensor:
    """Cosine similarity of the band-limited normalised PSDs of (M, T) `a` and (M, T) `b` (phase-free)."""
    _, pa = band_psd(a, fs, band)
    _, pb = band_psd(b, fs, band)
    return F.cosine_similarity(pa, pb, dim=1)


def simper_loss(features: torch.Tensor, speeds: torch.Tensor, fs: float, band: tuple[float, float],
                tau: float = 0.1, label_tau: float = 0.5) -> torch.Tensor:
    """SimPer soft-label InfoNCE over the views of each anchor.

    `features` (N, V, T): V views (speeds) of N anchors, as feature sequences; `speeds` (N, V). For a view
    a of anchor i, similarities s_ab (b != a) are periodicity similarities; the target distribution is
    softmax_b(-|speed_a - speed_b| / label_tau); loss = -sum_b w_ab log softmax_b(s_ab / tau), averaged.
    """
    n, v, t = features.shape
    if v < 2:
        raise ValueError("SimPer needs at least two views per anchor")
    total = torch.zeros((), device=features.device)
    for i in range(n):
        for a in range(v):
            others = [b for b in range(v) if b != a]
            sims = periodicity_similarity(features[i, a].expand(len(others), t), features[i, others], fs, band)
            dspeed = (speeds[i, a] - speeds[i, others]).abs()
            w = torch.softmax(-dspeed / label_tau, dim=0)
            logp = torch.log_softmax(sims / tau, dim=0)
            total = total - (w * logp).sum()
    return total / (n * v)


# --------------------------------------------------------------------------- MAE on STMaps
class STMapMAE(nn.Module):
    """Masked autoencoder on STMap images (N, C, P, T): patches of (patch_p x patch_t), `mask_ratio`
    masked, encoder (depth `depth`, width `dim`), decoder (one layer, width `dec_dim`), MSE on masked
    patches. `forward(x)` -> {"loss", "pred", "mask", "embedding"}; `encode(x)` -> (N, dim) mean token."""

    def __init__(self, in_channels: int = 3, patch: tuple[int, int] = (8, 8), dim: int = 64, depth: int = 2,
                 heads: int = 4, dec_dim: int = 32, mask_ratio: float = 0.75, max_tokens: int = 4096) -> None:
        super().__init__()
        self.patch = (int(patch[0]), int(patch[1]))
        self.mask_ratio = float(mask_ratio)
        self.embed = nn.Conv2d(in_channels, dim, self.patch, stride=self.patch)
        self.pos = nn.Parameter(torch.zeros(1, max_tokens, dim))
        nn.init.normal_(self.pos, std=0.02)
        layer = nn.TransformerEncoderLayer(dim, heads, 2 * dim, dropout=0.0, batch_first=True, norm_first=True)
        self.encoder = nn.TransformerEncoder(layer, depth, enable_nested_tensor=False)
        self.norm = nn.LayerNorm(dim)
        self.dec_embed = nn.Linear(dim, dec_dim)
        self.mask_token = nn.Parameter(torch.zeros(1, 1, dec_dim))
        self.dec_pos = nn.Parameter(torch.zeros(1, max_tokens, dec_dim))
        nn.init.normal_(self.dec_pos, std=0.02)
        dec_layer = nn.TransformerEncoderLayer(dec_dim, heads, 2 * dec_dim, dropout=0.0, batch_first=True, norm_first=True)
        self.decoder = nn.TransformerEncoder(dec_layer, 1, enable_nested_tensor=False)
        self.dec_norm = nn.LayerNorm(dec_dim)
        self.head = nn.Linear(dec_dim, in_channels * self.patch[0] * self.patch[1])

    def patchify(self, x: torch.Tensor) -> torch.Tensor:
        n, c, p, t = x.shape
        ph, pw = self.patch
        x = x[:, :, : p - p % ph, : t - t % pw]
        x = x.reshape(n, c, p // ph, ph, t // pw, pw).permute(0, 2, 4, 1, 3, 5)
        return x.reshape(n, (p // ph) * (t // pw), c * ph * pw)

    def random_mask(self, n: int, length: int, generator: torch.Generator | None = None):
        n_keep = max(int(round(length * (1 - self.mask_ratio))), 1)
        noise = torch.rand(n, length, generator=generator)
        order = noise.argsort(dim=1)
        restore = order.argsort(dim=1)
        keep = order[:, :n_keep]
        mask = torch.ones(n, length)
        mask[:, :n_keep] = 0
        mask = torch.gather(mask, 1, restore)
        return keep, mask, restore

    def encode(self, x: torch.Tensor, keep: torch.Tensor | None = None) -> torch.Tensor:
        tok = self.embed(x).flatten(2).transpose(1, 2)
        tok = tok + self.pos[:, : tok.shape[1]]
        if keep is not None:
            tok = torch.gather(tok, 1, keep[:, :, None].expand(-1, -1, tok.shape[2]).to(tok.device))
        return self.norm(self.encoder(tok))

    def embedding(self, x: torch.Tensor) -> torch.Tensor:
        return self.encode(x).mean(dim=1)

    def forward(self, x: torch.Tensor, generator: torch.Generator | None = None) -> dict:
        target = self.patchify(x)
        n, length, _ = target.shape
        keep, mask, restore = self.random_mask(n, length, generator)
        mask = mask.to(x.device)
        enc = self.encode(x, keep)
        dec = self.dec_embed(enc)
        n_mask = length - keep.shape[1]
        tokens = torch.cat([dec, self.mask_token.expand(n, n_mask, -1)], dim=1)
        tokens = torch.gather(tokens, 1, restore[:, :, None].expand(-1, -1, tokens.shape[2]).to(x.device))
        tokens = tokens + self.dec_pos[:, :length]
        pred = self.head(self.dec_norm(self.decoder(tokens)))
        per_patch = ((pred - target) ** 2).mean(dim=2)
        loss = (per_patch * mask).sum() / mask.sum().clamp_min(1.0)
        return {"loss": loss, "pred": pred, "mask": mask, "embedding": enc.mean(dim=1)}
