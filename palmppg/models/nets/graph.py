"""Spatial-temporal graph convolutional network (Yan et al. 2018) on the palm ROI graph (protocol 9).

Input ``x`` is (B, C, T, V): C pulse channels, T time steps, V ROI nodes. The adjacency ``A`` is a
(K, V, V) stack of partitions (self and neighbours) multiplied by a learnable edge-importance mask.
Temporal stride is 1 throughout so the validity mask (B, T) stays aligned for masked pooling.
"""
from __future__ import annotations

import numpy as np
import torch
from torch import nn


class GraphConv(nn.Module):
    def __init__(self, in_ch: int, out_ch: int, K: int):
        super().__init__()
        self.K = K
        self.out_ch = out_ch
        self.conv = nn.Conv2d(in_ch, out_ch * K, 1)

    def forward(self, x: torch.Tensor, A: torch.Tensor) -> torch.Tensor:
        B, _, T, V = x.shape
        y = self.conv(x).view(B, self.K, self.out_ch, T, V)
        return torch.einsum("bkctv,kvw->bctw", y, A)


class STGCNBlock(nn.Module):
    def __init__(self, in_ch: int, out_ch: int, K: int, t_kernel: int = 9, dropout: float = 0.1, residual: bool = True):
        super().__init__()
        self.gcn = GraphConv(in_ch, out_ch, K)
        self.tcn = nn.Sequential(nn.BatchNorm2d(out_ch), nn.ReLU(inplace=True),
                                 nn.Conv2d(out_ch, out_ch, (t_kernel, 1), padding=((t_kernel - 1) // 2, 0)),
                                 nn.BatchNorm2d(out_ch), nn.Dropout(dropout))
        if not residual:
            self.res = None
        elif in_ch == out_ch:
            self.res = nn.Identity()
        else:
            self.res = nn.Sequential(nn.Conv2d(in_ch, out_ch, 1), nn.BatchNorm2d(out_ch))
        self.act = nn.ReLU(inplace=True)

    def forward(self, x: torch.Tensor, A: torch.Tensor) -> torch.Tensor:
        r = 0 if self.res is None else self.res(x)
        return self.act(self.tcn(self.gcn(x, A)) + r)


class STGCN(nn.Module):
    """Data batch-norm, ``n_blocks`` ST-GCN blocks with edge importance, masked global pooling, linear head."""

    def __init__(self, A: np.ndarray, in_ch: int, out_dim: int, hidden: int = 16, n_blocks: int = 3,
                 t_kernel: int = 9, dropout: float = 0.1, edge_importance: bool = True):
        super().__init__()
        A = np.asarray(A, dtype=np.float32)
        if A.ndim == 2:
            A = A[None]
        self.register_buffer("A", torch.from_numpy(A))
        K, V, _ = A.shape
        self.data_bn = nn.BatchNorm1d(in_ch * V)
        chans = [in_ch] + [hidden] * n_blocks
        self.blocks = nn.ModuleList([STGCNBlock(chans[i], chans[i + 1], K, t_kernel, dropout, residual=i > 0)
                                     for i in range(n_blocks)])
        if edge_importance:
            self.edge = nn.ParameterList([nn.Parameter(torch.ones(K, V, V)) for _ in range(n_blocks)])
        else:
            self.edge = [1.0] * n_blocks
        self.head = nn.Linear(hidden, out_dim)
        self.embed_dim = hidden
        self.n_nodes = V

    def embed(self, x: torch.Tensor, mask: torch.Tensor | None = None) -> torch.Tensor:
        B, C, T, V = x.shape
        h = x.permute(0, 3, 1, 2).reshape(B, V * C, T)
        h = self.data_bn(h).view(B, V, C, T).permute(0, 2, 3, 1).contiguous()
        for blk, imp in zip(self.blocks, self.edge):
            h = blk(h, self.A * imp)
        h = h.mean(dim=3)                       # (B, hidden, T) mean over nodes
        if mask is None:
            return h.mean(dim=2)
        m = mask.to(h.dtype).unsqueeze(1)
        return (h * m).sum(dim=2) / m.sum(dim=2).clamp_min(1.0)

    def forward(self, x: torch.Tensor, mask: torch.Tensor | None = None) -> torch.Tensor:
        return self.head(self.embed(x, mask))
