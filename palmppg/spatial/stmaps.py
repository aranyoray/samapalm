"""Spatio-temporal maps (STMaps) from the 16 x 24 patch grid (protocol section 6.2 / 6.3 learned input).

A patch array is (n_frames_grid, rows, cols, n_ch) float32 of per-patch channel means on the uniform
reference-clock grid (CONTRACTS section 4, patches.zarr). An STMap flattens the grid to (T, rows*cols,
n_ch) and normalises each patch's time series so a CNN sees pulse modulation rather than skin colour.
"""
from __future__ import annotations

import warnings
from collections.abc import Sequence
from pathlib import Path

import numpy as np

NORMALISATIONS = ("per_patch_zscore", "minmax", "none")


def stmap_from_patches(
    patches: np.ndarray, normalise: str = "per_patch_zscore", fill_nan: float = 0.0, eps: float = 1e-8
) -> np.ndarray:
    """(T, R, C, ch) patch means -> (T, R*C, ch) float32 STMap, normalised per patch over time.

    "per_patch_zscore": (x - mean_t) / std_t per patch and channel (NaN-aware); patches with no
    variation or no data become `fill_nan`. "minmax": (x - min_t) / (max_t - min_t) into [0, 1].
    "none": flatten only. Remaining NaNs (dropped frames, cells outside the palm) are replaced by
    `fill_nan` so the array can feed a network directly; the mask of missing samples is recoverable
    from the raw patches. Row index = r * C + c (row-major over the grid). Section 6.3 (learned on
    STMaps).
    """
    if normalise not in NORMALISATIONS:
        raise ValueError(f"normalise must be one of {NORMALISATIONS}")
    p = np.asarray(patches, dtype=np.float32)
    if p.ndim != 4:
        raise ValueError(f"patches must be (T, R, C, ch), got {p.shape}")
    t, r, c, ch = p.shape
    x = p.reshape(t, r * c, ch).astype(np.float64)       # normalise in float64, cast once at the end
    with warnings.catch_warnings(), np.errstate(invalid="ignore", divide="ignore"):
        warnings.simplefilter("ignore", RuntimeWarning)        # all-NaN patches (outside the palm) are expected
        if normalise == "per_patch_zscore":
            valid = np.isfinite(x)
            n = valid.sum(axis=0)
            mean = np.where(n > 0, np.nansum(x, axis=0) / np.maximum(n, 1), np.nan)
            dev = np.where(valid, x - mean, 0.0)
            std = np.sqrt(np.sum(dev * dev, axis=0) / np.maximum(n, 1))
            std = np.where(std > eps, std, np.nan)
            x = (x - mean) / std
        elif normalise == "minmax":
            lo = np.nanmin(x, axis=0) if np.isfinite(x).any() else np.full(x.shape[1:], np.nan)
            hi = np.nanmax(x, axis=0) if np.isfinite(x).any() else np.full(x.shape[1:], np.nan)
            span = hi - lo
            span = np.where(span > eps, span, np.nan)
            x = (x - lo) / span
    x = np.where(np.isfinite(x), x, np.float32(fill_nan)).astype(np.float32)
    return x


def stmap_images(stmap: np.ndarray) -> np.ndarray:
    """(T, P, ch) STMap -> (ch, P, T) float32: one 2D image per channel (rows = patches, cols = time)."""
    s = np.asarray(stmap, dtype=np.float32)
    if s.ndim != 3:
        raise ValueError(f"stmap must be (T, P, ch), got {s.shape}")
    return np.ascontiguousarray(np.transpose(s, (2, 1, 0)))


def stmap_to_uint8(image: np.ndarray, lo: float | None = None, hi: float | None = None) -> np.ndarray:
    """Scale a float image to uint8 for a CNN that expects pixels; range defaults to the image min/max."""
    img = np.asarray(image, dtype=np.float32)
    finite = img[np.isfinite(img)]
    lo = float(finite.min()) if (lo is None and finite.size) else (lo if lo is not None else 0.0)
    hi = float(finite.max()) if (hi is None and finite.size) else (hi if hi is not None else 1.0)
    span = hi - lo if hi > lo else 1.0
    out = np.clip((img - lo) / span, 0.0, 1.0) * 255.0
    return np.round(np.where(np.isfinite(out), out, 0.0)).astype(np.uint8)


# --------------------------------------------------------------------------- zarr helpers
def write_patches_zarr(
    path: str | Path, patches: np.ndarray, channels: Sequence[str], t_ref_s: np.ndarray,
    attrs: dict | None = None, chunk_frames: int = 256,
) -> Path:
    """Write (n_frames, rows, cols, n_ch) float32 patch means to patches.zarr with the CONTRACTS attrs.

    Attributes: channels, t_ref_s (list of floats on the reference clock), rows, cols, plus `attrs`.
    Chunked along time so a reader can stream windows without loading the clip.
    """
    import zarr

    p = np.asarray(patches, dtype=np.float32)
    if p.ndim != 4:
        raise ValueError(f"patches must be (T, R, C, ch), got {p.shape}")
    if p.shape[3] != len(channels):
        raise ValueError("channels length must match the last patch axis")
    if p.shape[0] != len(t_ref_s):
        raise ValueError("t_ref_s length must match the time axis")
    path = Path(path)
    if path.exists():
        import shutil

        shutil.rmtree(path)
    chunks = (max(1, min(chunk_frames, p.shape[0])), p.shape[1], p.shape[2], p.shape[3])
    z = zarr.create_array(store=str(path), shape=p.shape, chunks=chunks, dtype="float32", fill_value=np.nan)
    if p.shape[0]:
        z[:] = p
    meta = {"channels": [str(c) for c in channels], "t_ref_s": [float(t) for t in t_ref_s],
            "rows": int(p.shape[1]), "cols": int(p.shape[2])}
    meta.update(attrs or {})
    z.attrs.update(meta)
    return path


def open_patches_zarr(path: str | Path):
    """Lazily open patches.zarr (read-only zarr array; index it to stream frames)."""
    import zarr

    return zarr.open_array(str(path), mode="r")


def read_patches_zarr(path: str | Path) -> tuple[np.ndarray, dict]:
    """Load patches.zarr fully: (array (T, R, C, ch) float32, attrs dict)."""
    z = open_patches_zarr(path)
    return np.asarray(z[:], dtype=np.float32), dict(z.attrs.asdict())


def stmap_from_zarr(path: str | Path, normalise: str = "per_patch_zscore", t_window: tuple[float, float] | None = None):
    """STMap straight from patches.zarr, optionally restricted to [t_window[0], t_window[1]) on t_ref_s."""
    z = open_patches_zarr(path)
    t = np.asarray(z.attrs.asdict().get("t_ref_s", []), dtype=float)
    if t_window is None or t.size == 0:
        sel = slice(0, z.shape[0])
    else:
        idx = np.nonzero((t >= t_window[0]) & (t < t_window[1]))[0]
        sel = slice(int(idx[0]), int(idx[-1]) + 1) if idx.size else slice(0, 0)
    return stmap_from_patches(np.asarray(z[sel], dtype=np.float32), normalise=normalise), t[sel]
