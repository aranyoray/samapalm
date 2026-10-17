"""Per-unit dark-frame and flat-field calibration of the Pi Bayer planes, and the vignetting residual check.

Serves protocol section 6.1 ("dark-frame subtract and flat-field divide per unit; verify vignetting removed to
within 3 percent across the aperture") and CONTRACTS section 3.1: calibrated plane =
(plane - dark) / max(flat_norm, eps), flat_norm = (flat - dark) divided by its central-region mean, computed
per Bayer plane. When a unit has no calibration files the black level `pi.black_level` is subtracted instead
and the result is labelled `calibration_applied = False`.
"""
from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path

import numpy as np

from palmppg.ingest.bayer import (
    PLANE_NAMES,
    default_stride,
    frame_bytes,
    plane_stats,
    split_planes,
    unpack_csi2p_10bit,
)

DARKFRAME_NAME = "darkframe.raw"
FLATFIELD_NAME = "flatfield.raw"
LUXMAP_NAME = "luxmap.json"


def central_region_slices(shape: tuple[int, int], fraction: float = 0.5) -> tuple[slice, slice]:
    """Row/col slices of the central `fraction` (per axis) of a plane of `shape`; 0.5 -> central 50 % region. CONTRACTS section 3.1 flat normalisation region."""
    h, w = int(shape[0]), int(shape[1])
    fr = float(fraction)
    r0, r1 = round(h * (1 - fr) / 2), round(h * (1 + fr) / 2)
    c0, c1 = round(w * (1 - fr) / 2), round(w * (1 + fr) / 2)
    return slice(r0, max(r1, r0 + 1)), slice(c0, max(c1, c0 + 1))


def _read_single_frame(path: Path, width: int, height: int, stride_bytes: int, crop_rect: Mapping | None,
                       sensor_size: tuple[int, int] | None) -> np.ndarray:
    """Unpack one packed frame with the clip geometry, or a full-sensor frame cropped by `crop_rect`."""
    size = path.stat().st_size
    fb = frame_bytes(height, stride_bytes)

    def _clip_geometry() -> np.ndarray:
        with open(path, "rb") as fh:
            buf = fh.read(fb)
        return unpack_csi2p_10bit(buf, width, height, stride_bytes)

    if size == fb:  # exactly one frame with the clip geometry
        return _clip_geometry()
    if crop_rect and sensor_size:  # one full-sensor frame, cropped like the clip
        sw, sh = int(sensor_size[0]), int(sensor_size[1])
        sstride = default_stride(sw)
        sfb = frame_bytes(sh, sstride)
        if size == sfb or (size % sfb == 0 and size % fb != 0):
            with open(path, "rb") as fh:
                buf = fh.read(sfb)
            full = unpack_csi2p_10bit(buf, sw, sh, sstride)
            x, y, w, h = (int(crop_rect[k]) for k in ("x", "y", "w", "h"))
            if (w, h) != (width, height):
                raise ValueError(f"crop_rect {w}x{h} does not match clip geometry {width}x{height}")
            return full[y: y + h, x: x + w]
    if size > fb and size % fb == 0:  # several frames with the clip geometry: the first one is used
        return _clip_geometry()
    raise ValueError(f"{path}: {size} bytes matches neither the clip geometry ({fb} bytes per frame) nor a "
                     f"full-sensor frame cropped by crop_rect")


class UnitCalibration:
    """Dark frame, normalised flat field and optional lux map of one capture unit, per Bayer plane. Serves section 6.1 and CONTRACTS section 3.1.

    Construct with `UnitCalibration.load(unit_dir, meta, black_level=cfg['pi.black_level'])`. The object is
    usable even when no files exist (`applied` is False, `apply` subtracts the black level); `summary()`
    is what `pi/ingest.json` records.
    """

    def __init__(self, dark: Mapping[str, np.ndarray] | None, flat_norm: Mapping[str, np.ndarray] | None,
                 black_level: float, eps: float = 1e-3, luxmap: dict | None = None, unit_id: str | None = None,
                 pattern: str = "RGGB", sources: dict | None = None, central_fraction: float = 0.5):
        self.dark = {k: np.asarray(v, dtype=np.float32) for k, v in dark.items()} if dark else None
        self.flat_norm = {k: np.asarray(v, dtype=np.float32) for k, v in flat_norm.items()} if flat_norm else None
        self.black_level = float(black_level)
        self.eps = float(eps)
        self.luxmap = luxmap
        self.unit_id = unit_id
        self.pattern = pattern
        self.sources = dict(sources or {})
        self.central_fraction = float(central_fraction)
        if self.flat_norm is not None:
            self._flat_den = {k: np.maximum(v, self.eps) for k, v in self.flat_norm.items()}
        else:
            self._flat_den = None

    # ------------------------------------------------------------------ construction
    @classmethod
    def none(cls, black_level: float, unit_id: str | None = None, pattern: str = "RGGB") -> UnitCalibration:
        """Fallback when a unit has no darkframe/flatfield: black-level subtraction only, `applied=False`. CONTRACTS section 3.1: black level subtracted only when no dark frame exists."""
        return cls(None, None, black_level, unit_id=unit_id, pattern=pattern, sources={"reason": "no calibration files"})

    @classmethod
    def from_frames(cls, dark_mosaic: np.ndarray | None, flat_mosaic: np.ndarray | None, black_level: float,
                    pattern: str = "RGGB", eps: float = 1e-3, central_fraction: float = 0.5, luxmap: dict | None = None,
                    unit_id: str | None = None, sources: dict | None = None) -> UnitCalibration:
        """Build from unpacked uint16 mosaics (dark may be None: a constant black level is used instead). CONTRACTS section 3.1 formulas; used by the loader and by synthetic tests (section 8)."""
        if flat_mosaic is None:
            return cls.none(black_level, unit_id, pattern)
        flat = {k: v.astype(np.float32) for k, v in split_planes(flat_mosaic, pattern).items()}
        if dark_mosaic is not None:
            dark = {k: v.astype(np.float32) for k, v in split_planes(dark_mosaic, pattern).items()}
        else:
            dark = {k: np.full(v.shape, float(black_level), dtype=np.float32) for k, v in flat.items()}
        flat_norm = {}
        for k in PLANE_NAMES:
            fd = flat[k] - dark[k]
            rs, cs = central_region_slices(fd.shape, central_fraction)
            centre = float(fd[rs, cs].mean())
            if not np.isfinite(centre) or centre <= 0:
                raise ValueError(f"flat field plane {k} has non-positive central mean ({centre}); check the white card")
            flat_norm[k] = fd / centre
        return cls(dark, flat_norm, black_level, eps=eps, luxmap=luxmap, unit_id=unit_id, pattern=pattern,
                   sources=sources, central_fraction=central_fraction)

    @classmethod
    def load(cls, unit_dir: str | os.PathLike | None, meta: Mapping, black_level: float, eps: float = 1e-3,
             sensor_size: tuple[int, int] | None = None, central_fraction: float = 0.5) -> UnitCalibration:
        """Read `darkframe.raw` and `flatfield.raw` from the unit directory with the clip's geometry (section 3).

        Each file is one packed frame with the clip geometry, or one full-sensor frame (`sensor_size`, the
        configured `pi.width` x `pi.height`) cropped by `meta["crop_rect"]`. `luxmap.json` is optional.
        Missing files -> `UnitCalibration.none(black_level)`.
        """
        width, height = int(meta["width"]), int(meta["height"])
        stride = int(meta.get("stride_bytes") or default_stride(width))
        pattern = str(meta.get("bayer_pattern") or "RGGB").upper()
        unit_id = meta.get("unit_id")
        crop = meta.get("crop_rect")
        if unit_dir is None:
            return cls.none(black_level, unit_id, pattern)
        unit_dir = Path(unit_dir)
        flat_p, dark_p, lux_p = unit_dir / FLATFIELD_NAME, unit_dir / DARKFRAME_NAME, unit_dir / LUXMAP_NAME
        if not flat_p.exists():
            cal = cls.none(black_level, unit_id or unit_dir.name, pattern)
            cal.sources["reason"] = f"{flat_p} missing"
            return cal
        flat = _read_single_frame(flat_p, width, height, stride, crop, sensor_size)
        dark = _read_single_frame(dark_p, width, height, stride, crop, sensor_size) if dark_p.exists() else None
        luxmap = None
        if lux_p.exists():
            try:
                luxmap = json.loads(lux_p.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                luxmap = None
        sources = {"flatfield": str(flat_p), "darkframe": str(dark_p) if dark is not None else None,
                   "luxmap": str(lux_p) if luxmap is not None else None}
        return cls.from_frames(dark, flat, black_level, pattern=pattern, eps=eps, central_fraction=central_fraction,
                               luxmap=luxmap, unit_id=unit_id or unit_dir.name, sources=sources)

    # ------------------------------------------------------------------ use
    @property
    def applied(self) -> bool:
        """True when a flat field exists (full dark + flat correction); False means black-level subtraction only. Recorded as `calibration_applied` in ingest.json (section 6.1)."""
        return self.flat_norm is not None

    def apply(self, planes: Mapping[str, np.ndarray]) -> dict[str, np.ndarray]:
        """Calibrated float32 planes: (plane - dark) / max(flat_norm, eps), or plane - black_level without a unit flat.

        Accepts single planes (h, w) or stacks (n, h, w). Output is in the raw digital-number scale with the dark
        level removed, so a perfectly flat scene gives the same value everywhere (section 6.1).
        """
        out: dict[str, np.ndarray] = {}
        for k, p in planes.items():
            p = np.asarray(p, dtype=np.float32)
            if self.dark is not None:
                d = self.dark[k]
                if d.shape != p.shape[-2:]:
                    raise ValueError(f"plane {k} shape {p.shape[-2:]} does not match calibration {d.shape}")
                corrected = p - d
            else:
                corrected = p - np.float32(self.black_level)
            if self._flat_den is not None:
                corrected = corrected / self._flat_den[k]
            out[k] = corrected.astype(np.float32, copy=False)
        return out

    def corrected_flat(self) -> dict[str, np.ndarray] | None:
        """The flat field after its own correction: ideally 1.0 everywhere, what the vignetting residual is measured on. Section 6.1 vignetting residual input."""
        if self.flat_norm is None:
            return None
        return {k: (v / np.maximum(v, self.eps)).astype(np.float32) for k, v in self.flat_norm.items()}

    def summary(self) -> dict:
        """Numbers for `pi/ingest.json`: per-plane dark mean, flat extremes, luxmap presence. Section 6.1 calibration record."""
        s: dict = {"calibration_applied": self.applied, "black_level_fallback": self.black_level, "unit_id": self.unit_id,
                   "eps": self.eps, "sources": self.sources, "luxmap_present": self.luxmap is not None}
        if self.dark is not None:
            s["dark_mean"] = plane_stats(self.dark)
        if self.flat_norm is not None:
            s["flat_norm_min"] = {k: float(v.min()) for k, v in self.flat_norm.items()}
            s["flat_norm_max"] = {k: float(v.max()) for k, v in self.flat_norm.items()}
            s["flat_vignetting_pct_uncorrected"] = vignetting_residual_pct(self.flat_norm)
        return s


def _gaussian_smooth(plane: np.ndarray, sigma: float) -> np.ndarray:
    from scipy.ndimage import gaussian_filter

    return gaussian_filter(np.asarray(plane, dtype=np.float32), sigma=sigma, mode="nearest")


def vignetting_residual_by_plane(planes_corrected: Mapping[str, np.ndarray], aperture_mask: np.ndarray | None = None,
                                 sigma_frac: float = 0.05) -> dict[str, float]:
    """Per-plane residual non-uniformity in percent: 100 * (p95 - p5) / median over the aperture of a Gaussian- Section 6.1 vignetting check, per plane.
    smoothed (sigma = sigma_frac * min(h, w), a large blur that removes texture and noise) version of each plane."""
    out = {}
    for k, p in planes_corrected.items():
        p = np.asarray(p, dtype=np.float32)
        if p.ndim == 3:
            p = p.mean(axis=0)
        sigma = max(1.0, sigma_frac * min(p.shape))
        sm = _gaussian_smooth(p, sigma)
        sel = sm[aperture_mask] if aperture_mask is not None else sm.reshape(-1)
        sel = sel[np.isfinite(sel)]
        if sel.size == 0:
            out[k] = float("nan")
            continue
        med = float(np.median(sel))
        if med == 0:
            out[k] = float("inf")
            continue
        p5, p95 = np.percentile(sel, [5, 95])
        out[k] = float(100.0 * (p95 - p5) / abs(med))
    return out


def vignetting_residual_pct(planes_corrected: Mapping[str, np.ndarray], aperture_mask: np.ndarray | None = None,
                            sigma_frac: float = 0.05) -> float:
    """Worst-plane vignetting residual in percent (section 6.1: flag above cfg `qc.vignetting_residual_pct_max`).

    (p95 - p5) / median over the aperture of a heavily smoothed version of the corrected planes, maximum over
    planes so a residual in any colour plane is reported. `aperture_mask` is a half-resolution boolean mask.
    """
    vals = [v for v in vignetting_residual_by_plane(planes_corrected, aperture_mask, sigma_frac).values() if np.isfinite(v)]
    return float(max(vals)) if vals else float("nan")


def aperture_mask_from_flat(flat_norm_plane: np.ndarray, rel_threshold: float = 0.2) -> np.ndarray:
    """Boolean half-resolution mask of pixels the flat field illuminates (above `rel_threshold` x central mean). Section 6.1: the residual is measured across the aperture only."""
    p = np.asarray(flat_norm_plane, dtype=np.float32)
    rs, cs = central_region_slices(p.shape, 0.5)
    centre = float(p[rs, cs].mean())
    return p > rel_threshold * centre
