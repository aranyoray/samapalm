"""Cross-attention fusion of two modality token sets (protocol 9 "late-fusion and cross-attention")."""
from __future__ import annotations

import torch
from torch import nn

from palmppg.models.nets.common import masked_mean


class CrossAttentionFusion(nn.Module):
    """Tokens A (B, Ta, Ca) and B (B, Tb, Cb) are projected to ``d_model``; A attends to B and B to A
    (multi-head cross-attention with residual + LayerNorm + feed-forward); both streams are mean-pooled
    over their valid steps and concatenated for the head. ``embed`` returns the (B, 2 d_model) vector."""

    def __init__(self, in_a: int, in_b: int, out_dim: int, d_model: int = 32, n_heads: int = 4, dropout: float = 0.1,
                 max_len: int = 4096):
        super().__init__()
        self.proj_a, self.proj_b = nn.Linear(in_a, d_model), nn.Linear(in_b, d_model)
        self.pos_a, self.pos_b = nn.Embedding(max_len, d_model), nn.Embedding(max_len, d_model)
        self.attn_ab = nn.MultiheadAttention(d_model, n_heads, dropout=dropout, batch_first=True)
        self.attn_ba = nn.MultiheadAttention(d_model, n_heads, dropout=dropout, batch_first=True)
        self.norm_a1, self.norm_b1 = nn.LayerNorm(d_model), nn.LayerNorm(d_model)
        self.norm_a2, self.norm_b2 = nn.LayerNorm(d_model), nn.LayerNorm(d_model)
        self.ff_a = nn.Sequential(nn.Linear(d_model, 2 * d_model), nn.ReLU(), nn.Dropout(dropout), nn.Linear(2 * d_model, d_model))
        self.ff_b = nn.Sequential(nn.Linear(d_model, 2 * d_model), nn.ReLU(), nn.Dropout(dropout), nn.Linear(2 * d_model, d_model))
        self.drop = nn.Dropout(dropout)
        self.head = nn.Linear(2 * d_model, out_dim)
        self.embed_dim = 2 * d_model

    def _tokens(self, x, proj, pos):
        T = x.shape[1]
        return proj(x) + pos(torch.arange(T, device=x.device))[None]

    def embed(self, xa: torch.Tensor, xb: torch.Tensor, mask_a: torch.Tensor | None = None,
              mask_b: torch.Tensor | None = None) -> torch.Tensor:
        a = self._tokens(xa, self.proj_a, self.pos_a)
        b = self._tokens(xb, self.proj_b, self.pos_b)
        pad_a = None if mask_a is None else ~mask_a
        pad_b = None if mask_b is None else ~mask_b
        a2, _ = self.attn_ab(a, b, b, key_padding_mask=pad_b, need_weights=False)
        b2, _ = self.attn_ba(b, a, a, key_padding_mask=pad_a, need_weights=False)
        a = self.norm_a1(a + self.drop(a2))
        b = self.norm_b1(b + self.drop(b2))
        a = self.norm_a2(a + self.drop(self.ff_a(a)))
        b = self.norm_b2(b + self.drop(self.ff_b(b)))
        return torch.cat([masked_mean(a, mask_a), masked_mean(b, mask_b)], dim=1)

    def forward(self, xa, xb, mask_a=None, mask_b=None) -> torch.Tensor:
        return self.head(self.embed(xa, xb, mask_a, mask_b))
