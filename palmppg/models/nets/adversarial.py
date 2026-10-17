"""Domain-adversarial neural network (Ganin et al. 2016) pieces: gradient reversal, extractor, heads."""
from __future__ import annotations

import torch
from torch import nn

from palmppg.models.nets.common import mlp


class GradReverse(torch.autograd.Function):
    @staticmethod
    def forward(ctx, x: torch.Tensor, lambd: float) -> torch.Tensor:
        ctx.lambd = lambd
        return x.view_as(x)

    @staticmethod
    def backward(ctx, grad: torch.Tensor):
        return -ctx.lambd * grad, None


def grad_reverse(x: torch.Tensor, lambd: float = 1.0) -> torch.Tensor:
    """Identity in the forward pass, gradient scaled by ``-lambd`` in the backward pass."""
    return GradReverse.apply(x, lambd)


class MLPExtractor(nn.Module):
    def __init__(self, in_dim: int, emb_dim: int = 16, hidden: int = 64, dropout: float = 0.1):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(in_dim, hidden), nn.ReLU(), nn.Dropout(dropout),
                                 nn.Linear(hidden, emb_dim), nn.ReLU())
        self.embed_dim = emb_dim

    def forward(self, x: torch.Tensor, mask: torch.Tensor | None = None) -> torch.Tensor:
        return self.net(x)


class DANN(nn.Module):
    """``extractor`` -> embedding; label head on the embedding; domain head behind gradient reversal.

    ``forward`` returns ``(y_hat, domain_logits, embedding)``; ``embed`` returns the embedding only.
    """

    def __init__(self, extractor: nn.Module, out_dim: int, n_domains: int, hidden: int = 32, dropout: float = 0.1,
                 domain_hidden: int = 0):
        super().__init__()
        self.extractor = extractor
        d = extractor.embed_dim
        self.label_head = mlp(d, hidden, out_dim, dropout)
        # A linear domain head (domain_hidden=0) is the matched adversary for the linear probe used in the
        # E11 audit; domain_hidden > 0 gives the two-layer head of the original DANN.
        self.domain_head = nn.Linear(d, n_domains) if domain_hidden <= 0 else mlp(d, domain_hidden, n_domains, dropout)
        self.embed_dim = d

    def embed(self, x: torch.Tensor, mask: torch.Tensor | None = None) -> torch.Tensor:
        return self.extractor(x, mask) if mask is not None else self.extractor(x)

    def forward(self, x: torch.Tensor, mask: torch.Tensor | None = None, lambd: float = 1.0):
        z = self.embed(x, mask)
        return self.label_head(z), self.domain_head(grad_reverse(z, lambd)), z
