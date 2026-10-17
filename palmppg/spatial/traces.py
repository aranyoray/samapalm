"""Per-ROI and per-patch statistics per frame, streamed onto the uniform grid (protocol section 6.2).

Inputs are either Bayer planes {"R", "G1", "G2", "B"} (Pi path, half-resolution uint16/float arrays,
never demosaiced, CONTRACTS section 0.3) or an (H, W, 3) RGB frame (phone and pi_proxy paths, 8-bit
sRGB; `transfer="srgb_inverse"` turns each pixel into linear-ish [0, 1] before averaging and the
limitation that compressed phone video cannot be truly linearised is stated in `srgb_inverse_lut`).

Masks are in the frame's own coordinates (plane coordinates for the Pi: full-res masks go through
`rois.downsample_mask`). ROIs follow slow hand motion: `MaskSchedule` rasterises the ROI set of each
landmark frame (landmarks run at ~4 fps) and serves the one nearest in reference-clock time, cached.
Output: traces.parquet DataFrame on the uniform grid (NaN where no frame landed in a grid slot) and
the (n_frames_grid, rows, cols, n_ch) patch-mean array written by `stmaps.write_patches_zarr`.
"""
from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterable, Iterator, Mapping, Sequence
from pathlib import Path

import numpy as np
import pandas as pd

from palmppg.spatial import rois as R
from palmppg.spatial.landmarks import landmark_array
from palmppg.spatial.stmaps import write_patches_zarr

PI_CHANNELS: tuple[str, ...] = ("R", "G1", "G2", "B")
RGB_CHANNELS: tuple[str, ...] = ("R", "G", "B")
TRANSFERS = ("none", "srgb_inverse")


# --------------------------------------------------------------------------- transfer
def srgb_inverse_lut() -> np.ndarray:
    """256-entry float32 LUT of the inverse sRGB transfer (IEC 61966-2-1) mapping 8-bit codes to [0, 1].

    This is the nominal inverse of the sRGB curve only: compressed consumer video has an unknown camera
    tone curve, white balance and codec processing on top, so the result is "linear-ish" and is labelled
    `colour_space = "inverted_srgb"` / `linearised_from_srgb = True` (CONTRACTS section 0.4), never
    linear. Protocol section 5.
    """
    c = np.arange(256, dtype=np.float64) / 255.0
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return lin.astype(np.float32)


_SRGB_LUT = srgb_inverse_lut()


def frame_to_planes(frame, channels: Sequence[str] | None = None) -> dict[str, np.ndarray]:
    """Normalise an input frame to {channel: 2D array}: a planes dict is passed through, RGB is split."""
    if isinstance(frame, Mapping):
        planes = {str(k): np.asarray(v) for k, v in frame.items()}
        if channels is not None:
            missing = [c for c in channels if c not in planes]
            if missing:
                raise KeyError(f"frame is missing planes {missing}")
            planes = {c: planes[c] for c in channels}
        return planes
    arr = np.asarray(frame)
    if arr.ndim != 3 or arr.shape[2] != 3:
        raise ValueError(f"frame must be a planes dict or (H, W, 3) RGB, got {arr.shape}")
    names = tuple(channels) if channels is not None else RGB_CHANNELS
    if len(names) != 3:
        raise ValueError("an RGB frame needs exactly three channel names")
    return {n: arr[:, :, i] for i, n in enumerate(names)}


# --------------------------------------------------------------------------- mask sets
class MaskSet:
    """Flat pixel indices per ROI plus patch labels, for one landmark frame, in frame coordinates.

    The patch grid tiles the bounding box of `patch_roi` (whole_palm); when that ROI is absent (a static
    mask dict) the union of the given masks is used and `patch_roi` reads "union".
    """

    def __init__(
        self, masks: Mapping[str, np.ndarray], shape: tuple[int, int], rows: int, cols: int,
        patch_roi: str = "whole_palm", key: int | None = None,
    ) -> None:
        self.shape = (int(shape[0]), int(shape[1]))
        self.key = key
        self.rows, self.cols = int(rows), int(cols)
        self.roi_index: dict[str, np.ndarray] = {}
        self.roi_npix: dict[str, int] = {}
        for name, m in masks.items():
            m = np.asarray(m, dtype=bool)
            if m.shape != self.shape:
                raise ValueError(f"mask {name} has shape {m.shape}, expected {self.shape}")
            idx = np.flatnonzero(m)
            self.roi_index[name] = idx
            self.roi_npix[name] = int(idx.size)
        palm = masks.get(patch_roi)
        if palm is None and masks:                   # static mask dicts without a whole_palm: grid over their union
            palm = np.logical_or.reduce([np.asarray(m, dtype=bool) for m in masks.values()])
        self.patch_roi = patch_roi if patch_roi in masks else "union"
        if palm is not None:
            labels, counts = R.patch_labels(np.asarray(palm, dtype=bool), self.rows, self.cols)
            inside = labels >= 0
            self.patch_pix = np.flatnonzero(inside)
            self.patch_lab = labels[inside]
            self.patch_counts = counts
        else:
            self.patch_pix = np.zeros(0, dtype=np.int64)
            self.patch_lab = np.zeros(0, dtype=np.int32)
            self.patch_counts = np.zeros(self.rows * self.cols, dtype=np.int64)

    @property
    def roi_names(self) -> list[str]:
        return list(self.roi_index)


def mask_set_from_landmarks(
    lm_norm: np.ndarray, full_res_shape: tuple[int, int], plane_scale: int, rows: int, cols: int,
    roi_kwargs: Mapping | None = None, exclude: Sequence[str] = (R.EXCLUDED_ROI,), key: int | None = None,
    roi_names: Sequence[str] | None = None,
) -> MaskSet:
    """Landmarks (normalised) -> full-res polygons -> masks with thumb excluded -> plane-coordinate MaskSet."""
    lm_px = R.landmarks_to_px(np.asarray(lm_norm)[:, :2], full_res_shape)
    polys = R.roi_polygons(lm_px, full_res_shape, **(roi_kwargs or {}))
    masks = R.roi_masks(polys, full_res_shape, exclude=exclude)
    keep = [n for n in (roi_names or list(masks)) if n not in exclude]
    down = {n: R.downsample_mask(masks[n], plane_scale) for n in keep}
    shape = (int(np.ceil(full_res_shape[0] / plane_scale)), int(np.ceil(full_res_shape[1] / plane_scale)))
    return MaskSet(down, shape, rows, cols, key=key)


class MaskSchedule:
    """Serve the ROI mask set of the landmark frame nearest in reference-clock time, with a small cache.

    Built from the landmarks DataFrame (detected rows only), the full-resolution frame shape and the
    plane scale (2 for Bayer planes, 1 for RGB frames). Section 6.2: ROIs follow slow motion because
    every video frame uses the landmarks of the nearest 4 fps landmark frame.
    """

    def __init__(
        self, landmarks_df: pd.DataFrame, full_res_shape: tuple[int, int], plane_scale: int = 2,
        rows: int = 16, cols: int = 24, roi_kwargs: Mapping | None = None, roi_names: Sequence[str] | None = None,
        max_cache: int = 4,
    ) -> None:
        det = landmarks_df[landmarks_df["source"] != "none"].sort_values("t_ref_s", kind="stable")
        if len(det) == 0:
            raise ValueError("no detected landmark frames: cannot build ROI masks")
        self.t = det["t_ref_s"].to_numpy(dtype=float)
        self.frame_idx = det["frame_idx"].to_numpy(dtype=np.int64)
        self.lm = landmark_array(det)
        self.full_res_shape = (int(full_res_shape[0]), int(full_res_shape[1]))
        self.plane_scale = int(plane_scale)
        self.rows, self.cols = int(rows), int(cols)
        self.roi_kwargs = dict(roi_kwargs or {})
        self.roi_names = list(roi_names) if roi_names else None
        self.max_cache = int(max_cache)
        self._cache: OrderedDict[int, MaskSet] = OrderedDict()

    @property
    def plane_shape(self) -> tuple[int, int]:
        return (int(np.ceil(self.full_res_shape[0] / self.plane_scale)),
                int(np.ceil(self.full_res_shape[1] / self.plane_scale)))

    def nearest(self, t_ref_s: float) -> int:
        pos = int(np.searchsorted(self.t, t_ref_s))
        if pos <= 0:
            return 0
        if pos >= self.t.size:
            return self.t.size - 1
        return pos - 1 if (t_ref_s - self.t[pos - 1]) <= (self.t[pos] - t_ref_s) else pos

    def mask_set(self, pos: int) -> MaskSet:
        if pos in self._cache:
            self._cache.move_to_end(pos)
            return self._cache[pos]
        ms = mask_set_from_landmarks(
            self.lm[pos], self.full_res_shape, self.plane_scale, self.rows, self.cols, self.roi_kwargs,
            key=int(self.frame_idx[pos]), roi_names=self.roi_names,
        )
        self._cache[pos] = ms
        while len(self._cache) > self.max_cache:
            self._cache.popitem(last=False)
        return ms

    def masks_at(self, t_ref_s: float) -> MaskSet:
        return self.mask_set(self.nearest(float(t_ref_s)))

    def representative_pos(self) -> int:
        """Index of the detected landmark frame closest to the per-coordinate median landmark set."""
        med = np.median(self.lm[:, :, :2], axis=0)
        d = np.sum((self.lm[:, :, :2] - med) ** 2, axis=(1, 2))
        return int(np.argmin(d))


# --------------------------------------------------------------------------- per-frame stats
def _gather(planes: Mapping[str, np.ndarray], idx: np.ndarray, transfer: str) -> tuple[dict[str, np.ndarray], dict]:
    raw = {ch: np.asarray(p).ravel()[idx] for ch, p in planes.items()}
    if transfer == "srgb_inverse":
        vals = {ch: (_SRGB_LUT[v] if v.dtype == np.uint8 else v.astype(np.float32)) for ch, v in raw.items()}
    else:
        vals = {ch: v.astype(np.float32) for ch, v in raw.items()}
    return vals, raw


def _stats_from_index(
    planes: Mapping[str, np.ndarray], idx: np.ndarray, white_level: float, transfer: str, with_median: bool = True
) -> dict:
    n = int(idx.size)
    if n == 0:
        return {"mean": {ch: np.nan for ch in planes}, "median": {ch: np.nan for ch in planes},
                "npix": 0, "sat_frac": np.nan}
    vals, raw = _gather(planes, idx, transfer)
    sat = np.zeros(n, dtype=bool)
    for v in raw.values():
        sat |= v >= white_level
    out = {"mean": {ch: float(np.mean(v)) for ch, v in vals.items()}, "npix": n, "sat_frac": float(np.mean(sat))}
    out["median"] = {ch: float(np.median(v)) for ch, v in vals.items()} if with_median else {ch: np.nan for ch in vals}
    return out


def roi_stats(
    planes_or_rgb, masks_plane_coords: Mapping[str, np.ndarray] | MaskSet, white_level: float,
    channels: Sequence[str] | None = None, transfer: str = "none",
) -> dict[str, dict]:
    """Per-ROI mean and median per channel, pixel count and saturated fraction for one frame.

    `planes_or_rgb`: {"R","G1","G2","B"} Bayer planes or an (H, W, 3) RGB frame. `masks_plane_coords`:
    {roi: bool mask} in the frame's coordinates (or a MaskSet). `white_level`: the value at which the
    sensor clips in the input units (1023 for 10-bit raw, the calibrated clip level for dark-subtracted
    flat-fielded planes, 255 for 8-bit video); `sat_frac` is the fraction of ROI pixels at or above it
    in any channel, measured before `transfer`. `transfer="srgb_inverse"` applies the inverse sRGB LUT
    to 8-bit codes before averaging. Returns {roi: {"mean": {ch: v}, "median": {ch: v}, "npix": n,
    "sat_frac": f}}. Section 6.2 (per ROI per frame: mean and median per channel, pixel count,
    saturation fraction).
    """
    if transfer not in TRANSFERS:
        raise ValueError(f"transfer must be one of {TRANSFERS}")
    planes = frame_to_planes(planes_or_rgb, channels)
    shape = next(iter(planes.values())).shape
    for ch, p in planes.items():
        if p.shape != shape:
            raise ValueError(f"plane {ch} shape {p.shape} differs from {shape}")
    if isinstance(masks_plane_coords, MaskSet):
        if masks_plane_coords.shape != tuple(shape):
            raise ValueError(f"mask set shape {masks_plane_coords.shape} differs from frame shape {shape}")
        index = masks_plane_coords.roi_index
    else:
        index = {}
        for name, m in masks_plane_coords.items():
            m = np.asarray(m, dtype=bool)
            if m.shape != tuple(shape):
                raise ValueError(f"mask {name} shape {m.shape} differs from frame shape {shape}")
            index[name] = np.flatnonzero(m)
    return {name: _stats_from_index(planes, idx, float(white_level), transfer) for name, idx in index.items()}


def patch_means(planes: Mapping[str, np.ndarray], ms: MaskSet, transfer: str = "none") -> np.ndarray:
    """(rows, cols, n_ch) float32 mean per patch cell over whole-palm pixels; NaN for empty cells."""
    n_ch = len(planes)
    out = np.full((ms.rows * ms.cols, n_ch), np.nan, dtype=np.float32)
    if ms.patch_pix.size == 0:
        return out.reshape(ms.rows, ms.cols, n_ch)
    vals, _ = _gather(planes, ms.patch_pix, transfer)
    counts = ms.patch_counts
    nz = counts > 0
    for k, (ch, v) in enumerate(vals.items()):
        sums = np.bincount(ms.patch_lab, weights=v.astype(np.float64), minlength=ms.rows * ms.cols)
        out[nz, k] = (sums[nz] / counts[nz]).astype(np.float32)
    return out.reshape(ms.rows, ms.cols, n_ch)


# --------------------------------------------------------------------------- streaming run
def trace_columns(roi_names: Sequence[str], channels: Sequence[str]) -> list[str]:
    """Column order of traces.parquet after t_ref_s, frame_idx (CONTRACTS section 4)."""
    cols: list[str] = []
    for roi in roi_names:
        cols += [f"{roi}__{ch}__mean" for ch in channels]
        cols += [f"{roi}__{ch}__median" for ch in channels]
        cols += [f"{roi}__npix", f"{roi}__sat_frac"]
    return cols


def empty_traces(grid_t_s: np.ndarray, roi_names: Sequence[str], channels: Sequence[str]) -> pd.DataFrame:
    """All-NaN traces frame on the grid (used when no hand was found)."""
    grid = np.asarray(grid_t_s, dtype=float)
    cols = {"t_ref_s": grid, "frame_idx": pd.array([pd.NA] * grid.size, dtype="Int64")}
    cols.update({c: np.full(grid.size, np.nan) for c in trace_columns(roi_names, channels)})
    return pd.DataFrame(cols)


def _frame_time_lookup(t_frame_s) -> dict[int, float]:
    if isinstance(t_frame_s, pd.DataFrame):
        return dict(zip(t_frame_s["frame_idx"].astype(int).tolist(), t_frame_s["t_ref_s"].astype(float).tolist()))
    if isinstance(t_frame_s, Mapping):
        return {int(k): float(v) for k, v in t_frame_s.items()}
    arr = np.asarray(t_frame_s, dtype=float)
    return {int(i): float(v) for i, v in enumerate(arr)}


def run_traces(
    frames_iter: Iterator[tuple[int, object]],
    masks: MaskSchedule | MaskSet | Mapping[str, np.ndarray],
    t_frame_s,
    grid_t_s: np.ndarray,
    channels: Sequence[str],
    white_level: float,
    transfer: str = "none",
    patches_path: str | Path | None = None,
    rows: int = 16,
    cols: int = 24,
    roi_names: Sequence[str] | None = None,
    with_median: bool = True,
    patch_attrs: dict | None = None,
) -> tuple[pd.DataFrame, np.ndarray, dict]:
    """Stream (frame_idx, planes-or-rgb) frames into traces.parquet rows and the patch-mean array.

    Each frame is placed in the grid slot nearest its reference-clock time (`t_frame_s`: DataFrame with
    frame_idx and t_ref_s, a dict, or an array indexed by frame_idx) when it lies within half a grid
    period of it; the closer frame wins a contested slot and slots no frame reaches stay NaN, so frame
    drops are visible in the traces (section 6.1). ROI masks come from `masks` (a MaskSchedule follows
    the nearest landmark frame; a MaskSet or a {roi: mask} dict is static). Patch means are taken on
    the whole-palm grid of the same mask set and written to `patches_path` as patches.zarr when given.
    Returns (traces DataFrame, patches (n_grid, rows, cols, n_ch) float32, info dict with counts).
    Frames themselves are never retained. Section 6.2.
    """
    if transfer not in TRANSFERS:
        raise ValueError(f"transfer must be one of {TRANSFERS}")
    grid = np.asarray(grid_t_s, dtype=float)
    if grid.size < 2:
        raise ValueError("grid_t_s needs at least two samples")
    dt = float(np.median(np.diff(grid)))
    half = 0.5 * dt + 1e-9
    times = _frame_time_lookup(t_frame_s)
    channels = list(channels)
    n_ch = len(channels)

    static: MaskSet | None
    if isinstance(masks, MaskSchedule):
        static = None
        names = roi_names or masks.roi_names or [n for n in R.DEFAULT_ROI_NAMES]
        rows, cols = masks.rows, masks.cols
    elif isinstance(masks, MaskSet):
        static = masks
        names = roi_names or masks.roi_names
        rows, cols = masks.rows, masks.cols
    else:
        first = next(iter(masks.values()))
        static = MaskSet(masks, np.asarray(first).shape, rows, cols)
        names = roi_names or list(masks)
    names = [n for n in names if n != R.EXCLUDED_ROI]

    columns = trace_columns(names, channels)
    col_pos = {c: i for i, c in enumerate(columns)}
    data = np.full((grid.size, len(columns)), np.nan, dtype=np.float64)
    frame_of = np.full(grid.size, -1, dtype=np.int64)
    dist_of = np.full(grid.size, np.inf, dtype=np.float64)
    patches = np.full((grid.size, rows, cols, n_ch), np.nan, dtype=np.float32)
    info = {"n_frames_seen": 0, "n_frames_placed": 0, "n_frames_no_time": 0, "n_frames_off_grid": 0,
            "n_frames_replaced": 0, "mask_keys_used": []}
    used_keys: set = set()

    for frame_idx, frame in frames_iter:
        info["n_frames_seen"] += 1
        t = times.get(int(frame_idx))
        if t is None:
            info["n_frames_no_time"] += 1
            continue
        k = int(np.round((t - grid[0]) / dt))
        if k < 0 or k >= grid.size or abs(t - grid[k]) > half:
            info["n_frames_off_grid"] += 1
            continue
        d = abs(t - grid[k])
        if d >= dist_of[k]:
            info["n_frames_replaced"] += 1
            continue
        planes = frame_to_planes(frame, channels)
        ms = static if static is not None else masks.masks_at(t)
        shape = next(iter(planes.values())).shape
        if tuple(shape) != ms.shape:
            raise ValueError(f"frame {frame_idx} shape {shape} does not match mask shape {ms.shape}")
        if ms.key is not None:
            used_keys.add(int(ms.key))
        row = data[k]
        for roi in names:
            idx = ms.roi_index.get(roi)
            if idx is None:
                continue
            st = _stats_from_index(planes, idx, float(white_level), transfer, with_median)
            for ch in channels:
                row[col_pos[f"{roi}__{ch}__mean"]] = st["mean"][ch]
                row[col_pos[f"{roi}__{ch}__median"]] = st["median"][ch]
            row[col_pos[f"{roi}__npix"]] = st["npix"]
            row[col_pos[f"{roi}__sat_frac"]] = st["sat_frac"]
        patches[k] = patch_means(planes, ms, transfer)
        if frame_of[k] >= 0:
            info["n_frames_replaced"] += 1
        else:
            info["n_frames_placed"] += 1
        frame_of[k] = int(frame_idx)
        dist_of[k] = d

    df = pd.DataFrame(data, columns=columns)
    df.insert(0, "frame_idx", pd.array([int(f) if f >= 0 else pd.NA for f in frame_of], dtype="Int64"))
    df.insert(0, "t_ref_s", grid)
    info["n_grid"] = int(grid.size)
    info["n_grid_missing"] = int((frame_of < 0).sum())
    info["mask_keys_used"] = sorted(used_keys)
    info["channels"] = channels
    info["roi_names"] = names
    if patches_path is not None:
        attrs = {"roi": "whole_palm", "grid_fs": 1.0 / dt, "transfer": transfer}
        attrs.update(patch_attrs or {})
        write_patches_zarr(patches_path, patches, channels, grid, attrs=attrs)
    return df, patches, info


def iter_frames_from_arrays(frames: Iterable, frame_indices: Iterable[int]) -> Iterator[tuple[int, object]]:
    """Convenience: zip frame indices with frames (for tests and small synthetic clips)."""
    for i, f in zip(frame_indices, frames):
        yield int(i), f
