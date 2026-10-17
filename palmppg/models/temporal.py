"""Sequence models on beat and IBI sequences (protocol section 9: "1D CNN, TCN, GRU and a small
transformer on beats and IBI series"; E4 BP deep, E5 static-versus-temporal, E7 rhythm).

Inputs are lists of arrays ``(T_i, C)`` (variable length; one row per beat or per sample) or a 3-D
array ``(N, T, C)``. Channels are standardised with the training statistics. ``torch`` is imported
lazily; ``pytest.importorskip('torch')`` in tests.
"""
from __future__ import annotations

from palmppg.models._torchbase import (
    TorchEstimator,
    as_sequence_list,
    channel_stats,
    pad_sequences,
    standardise,
)

ARCHITECTURES: tuple[str, ...] = ("conv1d", "tcn", "gru", "small_transformer")


class TorchSequenceRegressor(TorchEstimator):
    """sklearn-like wrapper: ``fit(list_of_(T,C)_arrays, y)``, ``predict``, ``predict_proba`` (classification),
    ``predict_samples`` (MC dropout), ``transform`` (pooled embeddings).

    ``model_fn`` is an architecture name from ``ARCHITECTURES`` (hyper-parameters in ``model_kw``) or a
    callable ``(in_ch, out_dim) -> nn.Module`` whose forward takes ``(x, mask)``. Deterministic for a
    fixed ``seed`` on CPU. Regression outputs are in the units of ``y``.
    """

    def __init__(self, model_fn="tcn", epochs: int = 30, lr: float = 1e-3, seed: int = 0, device: str = "cpu",
                 batch_size: int = 32, weight_decay: float = 1e-4, task: str = "regression", grad_clip: float = 1.0,
                 verbose: bool = False, model_kw: dict | None = None):
        super().__init__(model_fn=model_fn, epochs=epochs, lr=lr, seed=seed, device=device, batch_size=batch_size,
                         weight_decay=weight_decay, task=task, grad_clip=grad_clip, verbose=verbose)
        self.model_kw = model_kw

    def _encode_fit(self, X):
        seqs = as_sequence_list(X)
        self.x_mean_, self.x_std_ = channel_stats(seqs)
        self.n_channels_ = int(seqs[0].shape[1])
        return standardise(seqs, self.x_mean_, self.x_std_)

    def _encode(self, X):
        seqs = as_sequence_list(X)
        if seqs[0].shape[1] != self.n_channels_:
            raise ValueError(f"expected {self.n_channels_} channels, got {seqs[0].shape[1]}")
        return standardise(seqs, self.x_mean_, self.x_std_)

    def _collate(self, samples):
        torch = self._torch()
        x, mask = pad_sequences(samples)
        return {"x": torch.from_numpy(x), "mask": torch.from_numpy(mask)}

    def _build_module(self, sample, out_dim: int):
        in_ch = int(sample.shape[1])
        if callable(self.model_fn):
            return self.model_fn(in_ch, out_dim)
        from palmppg.models.nets.temporal import make_model

        return make_model(str(self.model_fn), in_ch, out_dim, **(self.model_kw or {}))


def make_sequence_regressor(arch: str = "tcn", **kw) -> TorchSequenceRegressor:
    """Factory used by the zoo: ``arch`` in ``ARCHITECTURES``; keyword arguments go to the wrapper."""
    if arch not in ARCHITECTURES:
        raise KeyError(f"unknown architecture '{arch}' (have {ARCHITECTURES})")
    return TorchSequenceRegressor(model_fn=arch, **kw)


__all__ = ["ARCHITECTURES", "TorchSequenceRegressor", "make_sequence_regressor"]
