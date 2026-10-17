"""Sequence architectures on (B, T, C) beat or IBI sequences (protocol section 9).

Every model takes ``x`` (B, T, C) and an optional validity ``mask`` (B, T) and returns (B, out_dim);
``embed`` returns the pooled representation before the output head so that MC dropout, DANN and the
fusion models can reuse the backbone.
"""
from __future__ import annotations

import torch
from torch import nn
from torch.nn.utils.rnn import pack_padded_sequence

from palmppg.models.nets.common import masked_mean


class Conv1DNet(nn.Module):
    """Stack of same-padded Conv1d + BatchNorm + ReLU + Dropout, masked mean pooling, linear head."""

    def __init__(self, in_ch: int, out_dim: int, hidden: int = 32, n_layers: int = 3, kernel: int = 5,
                 dropout: float = 0.1):
        super().__init__()
        layers = []
        c = in_ch
        for _ in range(n_layers):
            layers += [nn.Conv1d(c, hidden, kernel, padding=kernel // 2), nn.BatchNorm1d(hidden), nn.ReLU(),
                       nn.Dropout(dropout)]
            c = hidden
        self.body = nn.Sequential(*layers)
        self.head = nn.Linear(hidden, out_dim)
        self.embed_dim = hidden

    def embed(self, x: torch.Tensor, mask: torch.Tensor | None = None) -> torch.Tensor:
        h = self.body(x.transpose(1, 2)).transpose(1, 2)
        return masked_mean(h, mask)

    def forward(self, x: torch.Tensor, mask: torch.Tensor | None = None) -> torch.Tensor:
        return self.head(self.embed(x, mask))


class _Chomp(nn.Module):
    def __init__(self, n: int):
        super().__init__()
        self.n = n

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x[:, :, : x.shape[2] - self.n] if self.n > 0 else x


class TemporalBlock(nn.Module):
    """Two dilated *causal* convolutions with a residual connection (Bai et al. 2018)."""

    def __init__(self, in_ch: int, out_ch: int, kernel: int, dilation: int, dropout: float):
        super().__init__()
        pad = (kernel - 1) * dilation
        self.net = nn.Sequential(
            nn.Conv1d(in_ch, out_ch, kernel, padding=pad, dilation=dilation), _Chomp(pad), nn.ReLU(), nn.Dropout(dropout),
            nn.Conv1d(out_ch, out_ch, kernel, padding=pad, dilation=dilation), _Chomp(pad), nn.ReLU(), nn.Dropout(dropout),
        )
        self.down = nn.Conv1d(in_ch, out_ch, 1) if in_ch != out_ch else nn.Identity()
        self.act = nn.ReLU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.act(self.net(x) + self.down(x))


class TCN(nn.Module):
    """Dilated causal temporal convolutional network; receptive field 1 + 2(k-1)(2^L - 1)."""

    def __init__(self, in_ch: int, out_dim: int, hidden: int = 32, n_levels: int = 3, kernel: int = 3,
                 dropout: float = 0.1):
        super().__init__()
        blocks = []
        c = in_ch
        for i in range(n_levels):
            blocks.append(TemporalBlock(c, hidden, kernel, 2 ** i, dropout))
            c = hidden
        self.body = nn.Sequential(*blocks)
        self.head = nn.Linear(hidden, out_dim)
        self.embed_dim = hidden
        self.receptive_field = 1 + 2 * (kernel - 1) * (2 ** n_levels - 1)

    def embed(self, x: torch.Tensor, mask: torch.Tensor | None = None) -> torch.Tensor:
        h = self.body(x.transpose(1, 2)).transpose(1, 2)
        return masked_mean(h, mask)

    def forward(self, x: torch.Tensor, mask: torch.Tensor | None = None) -> torch.Tensor:
        return self.head(self.embed(x, mask))


class GRUNet(nn.Module):
    """GRU over packed variable-length sequences; the final hidden state is the embedding."""

    def __init__(self, in_ch: int, out_dim: int, hidden: int = 32, n_layers: int = 1, dropout: float = 0.1,
                 bidirectional: bool = False):
        super().__init__()
        self.gru = nn.GRU(in_ch, hidden, num_layers=n_layers, batch_first=True,
                          dropout=dropout if n_layers > 1 else 0.0, bidirectional=bidirectional)
        d = hidden * (2 if bidirectional else 1)
        self.drop = nn.Dropout(dropout)
        self.head = nn.Linear(d, out_dim)
        self.embed_dim = d
        self.bidirectional = bidirectional

    def embed(self, x: torch.Tensor, mask: torch.Tensor | None = None) -> torch.Tensor:
        if mask is None:
            _, h = self.gru(x)
        else:
            lengths = mask.sum(dim=1).clamp_min(1).cpu()
            packed = pack_padded_sequence(x, lengths, batch_first=True, enforce_sorted=False)
            _, h = self.gru(packed)
        if self.bidirectional:
            out = torch.cat([h[-2], h[-1]], dim=1)
        else:
            out = h[-1]
        return self.drop(out)

    def forward(self, x: torch.Tensor, mask: torch.Tensor | None = None) -> torch.Tensor:
        return self.head(self.embed(x, mask))


class SmallTransformer(nn.Module):
    """Pre-norm transformer encoder with learned positions and masked mean pooling."""

    def __init__(self, in_ch: int, out_dim: int, d_model: int = 32, n_heads: int = 4, n_layers: int = 2,
                 dim_ff: int = 64, dropout: float = 0.1, max_len: int = 4096):
        super().__init__()
        self.inp = nn.Linear(in_ch, d_model)
        self.pos = nn.Embedding(max_len, d_model)
        layer = nn.TransformerEncoderLayer(d_model, n_heads, dim_ff, dropout, batch_first=True, norm_first=True)
        self.enc = nn.TransformerEncoder(layer, n_layers, enable_nested_tensor=False)
        self.norm = nn.LayerNorm(d_model)
        self.head = nn.Linear(d_model, out_dim)
        self.embed_dim = d_model
        self.max_len = max_len

    def embed(self, x: torch.Tensor, mask: torch.Tensor | None = None) -> torch.Tensor:
        T = x.shape[1]
        if T > self.max_len:
            raise ValueError(f"sequence length {T} exceeds max_len {self.max_len}")
        pos = torch.arange(T, device=x.device)
        h = self.inp(x) + self.pos(pos)[None]
        pad = None if mask is None else ~mask
        h = self.enc(h, src_key_padding_mask=pad)
        return masked_mean(self.norm(h), mask)

    def forward(self, x: torch.Tensor, mask: torch.Tensor | None = None) -> torch.Tensor:
        return self.head(self.embed(x, mask))


ARCHITECTURES = {"conv1d": Conv1DNet, "tcn": TCN, "gru": GRUNet, "small_transformer": SmallTransformer}


def make_model(arch: str, in_ch: int, out_dim: int, **kw) -> nn.Module:
    if arch not in ARCHITECTURES:
        raise KeyError(f"unknown sequence architecture '{arch}' (have {sorted(ARCHITECTURES)})")
    return ARCHITECTURES[arch](in_ch, out_dim, **kw)
