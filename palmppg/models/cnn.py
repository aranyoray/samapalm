"""ResNet-18 on spatio-temporal maps (STMaps) (protocol section 9 "ResNet-18 on STMaps", E4).

``stmap_from_patches`` turns the ``patches.zarr`` array ``(n_frames, rows, cols, n_ch)`` of CONTRACTS
section 4 into an image ``(n_ch, rows*cols, n_frames)`` whose rows are the per-patch temporal traces,
each min-max normalised over time (the usual STMap construction). ``TorchImageRegressor`` wraps the
from-scratch ResNet-18 in ``nets.cnn`` (torchvision is not installed) with configurable width.
"""
from __future__ import annotations

import numpy as np

from palmppg.models._torchbase import TorchEstimator


def stmap_from_patches(patches: np.ndarray, normalise: bool = True, eps: float = 1e-8) -> np.ndarray:
    """STMap image ``(n_ch, rows*cols, n_frames)`` from patch means ``(n_frames, rows, cols, n_ch)``.

    NaN frames (dropped frames) are bridged by linear interpolation along time per trace; traces that
    are entirely NaN become zero. With ``normalise`` each trace is scaled to [0, 1] over time so that
    the map encodes pulse waveform shape, not absolute brightness.
    """
    p = np.asarray(patches, dtype=np.float32)
    if p.ndim != 4:
        raise ValueError(f"patches must be (n_frames, rows, cols, n_ch), got {p.shape}")
    n_frames, rows, cols, n_ch = p.shape
    traces = p.reshape(n_frames, rows * cols, n_ch).transpose(2, 1, 0).copy()  # (n_ch, P, T)
    t = np.arange(n_frames)
    for c in range(n_ch):
        for i in range(rows * cols):
            tr = traces[c, i]
            ok = np.isfinite(tr)
            if ok.all():
                continue
            if ok.sum() == 0:
                traces[c, i] = 0.0
            else:
                traces[c, i] = np.interp(t, t[ok], tr[ok])
    if normalise:
        lo = traces.min(axis=2, keepdims=True)
        hi = traces.max(axis=2, keepdims=True)
        traces = (traces - lo) / np.maximum(hi - lo, eps)
    return traces.astype(np.float32)


class TorchImageRegressor(TorchEstimator):
    """sklearn-like wrapper for image inputs ``(N, C, H, W)`` (or a list of ``(C, H, W)`` arrays).

    Default module: ``nets.cnn.ResNet18(in_ch, out_dim, **model_kw)``; ``model_fn`` may also be a callable
    ``(in_ch, out_dim) -> nn.Module``. Channels are standardised with training statistics.
    """

    def __init__(self, model_fn=None, epochs: int = 30, lr: float = 1e-3, seed: int = 0, device: str = "cpu",
                 batch_size: int = 16, weight_decay: float = 1e-4, task: str = "regression", grad_clip: float = 1.0,
                 verbose: bool = False, model_kw: dict | None = None):
        super().__init__(model_fn=model_fn, epochs=epochs, lr=lr, seed=seed, device=device, batch_size=batch_size,
                         weight_decay=weight_decay, task=task, grad_clip=grad_clip, verbose=verbose)
        self.model_kw = model_kw

    @staticmethod
    def _as_list(X) -> list[np.ndarray]:
        arr = [np.asarray(x, dtype=np.float32) for x in X]
        if not arr or any(a.ndim != 3 for a in arr):
            raise ValueError("image input must be (N, C, H, W) or a list of (C, H, W) arrays")
        return arr

    def _encode_fit(self, X):
        imgs = self._as_list(X)
        stack = np.stack(imgs)
        self.x_mean_ = stack.mean(axis=(0, 2, 3), keepdims=False).astype(np.float32)
        self.x_std_ = np.maximum(stack.std(axis=(0, 2, 3)), 1e-6).astype(np.float32)
        self.in_shape_ = tuple(imgs[0].shape)
        return self._standardise(imgs)

    def _standardise(self, imgs):
        m, s = self.x_mean_[:, None, None], self.x_std_[:, None, None]
        return [np.nan_to_num((im - m) / s).astype(np.float32) for im in imgs]

    def _encode(self, X):
        imgs = self._as_list(X)
        if imgs[0].shape[0] != self.in_shape_[0]:
            raise ValueError(f"expected {self.in_shape_[0]} channels, got {imgs[0].shape[0]}")
        return self._standardise(imgs)

    def _collate(self, samples):
        torch = self._torch()
        return {"x": torch.from_numpy(np.stack(samples))}

    def _build_module(self, sample, out_dim: int):
        in_ch = int(sample.shape[0])
        if callable(self.model_fn):
            return self.model_fn(in_ch, out_dim)
        from palmppg.models.nets.cnn import ResNet18

        return ResNet18(in_ch, out_dim, **(self.model_kw or {}))


def make_stmap_regressor(width: int = 16, **kw) -> TorchImageRegressor:
    """Zoo factory: ResNet-18 of base ``width`` on STMaps; other keywords go to the wrapper."""
    model_kw = dict(kw.pop("model_kw", None) or {})
    model_kw.setdefault("width", width)
    return TorchImageRegressor(model_fn=None, model_kw=model_kw, **kw)


__all__ = ["TorchImageRegressor", "make_stmap_regressor", "stmap_from_patches"]
