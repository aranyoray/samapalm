"""Palm regions of interest built from 21 hand landmarks (protocol section 6.2).

Landmark indexing follows MediaPipe Hands: 0 wrist; 1-4 thumb CMC, MCP, IP, TIP; 5-8 index MCP, PIP,
DIP, TIP; 9-12 middle; 13-16 ring; 17-20 little (pinky). All polygons are in full-resolution image
pixel coordinates (x right, y down). Masks rasterised at full resolution map to Bayer-plane coordinates
by taking every second row and column (`downsample_mask`), because each plane is half the sensor size.

The thumb rests on the ECG card during the clip (protocol section 1), so the `thumb` polygon is
produced only to be subtracted from every pulse ROI (`roi_masks`).
"""
from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path

import cv2
import numpy as np

# --------------------------------------------------------------------------- landmark indices
WRIST = 0
THUMB_CMC, THUMB_MCP, THUMB_IP, THUMB_TIP = 1, 2, 3, 4
INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP = 5, 6, 7, 8
MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP = 9, 10, 11, 12
RING_MCP, RING_PIP, RING_DIP, RING_TIP = 13, 14, 15, 16
LITTLE_MCP, LITTLE_PIP, LITTLE_DIP, LITTLE_TIP = 17, 18, 19, 20
N_LANDMARKS = 21

FINGERS: dict[str, tuple[int, int, int, int]] = {
    "index": (INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP),
    "middle": (MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP),
    "ring": (RING_MCP, RING_PIP, RING_DIP, RING_TIP),
    "little": (LITTLE_MCP, LITTLE_PIP, LITTLE_DIP, LITTLE_TIP),
}
THUMB_LANDMARKS = (THUMB_CMC, THUMB_MCP, THUMB_IP, THUMB_TIP)
NON_THUMB_LANDMARKS = tuple(i for i in range(N_LANDMARKS) if i not in THUMB_LANDMARKS)

# ROI names in the order the config lists them (configs/pipeline.yaml: rois.names); the config is the
# source of truth at run time, this tuple documents the default order for callers without a config.
DEFAULT_ROI_NAMES: tuple[str, ...] = (
    "thenar", "hypothenar", "central_palm",
    "prox_index", "prox_middle", "prox_ring", "prox_little",
    "mid_phalanges",
    "pad_index", "pad_middle", "pad_ring", "pad_little",
    "volar_wrist", "whole_palm",
)
EXCLUDED_ROI = "thumb"

Polygon = np.ndarray                       # (N, 2) float64, full-res px
RoiShape = Polygon | list[Polygon]         # a simple polygon or a union of rings (mid_phalanges)


# --------------------------------------------------------------------------- geometry helpers
def landmarks_to_px(lm: np.ndarray, image_shape: tuple[int, int]) -> np.ndarray:
    """Normalised landmark coordinates (x, y in [0, 1] of the image) to full-resolution pixels (x, y).

    `image_shape` is (height, width). Only the first two columns of `lm` are used; z is relative depth
    and has no pixel meaning. Serves section 6.2 (ROIs from landmarks).
    """
    a = np.asarray(lm, dtype=float)
    h, w = int(image_shape[0]), int(image_shape[1])
    out = np.empty((a.shape[0], 2), dtype=float)
    out[:, 0] = a[:, 0] * w
    out[:, 1] = a[:, 1] * h
    return out


def _unit(v: np.ndarray) -> np.ndarray:
    n = float(np.hypot(v[0], v[1]))
    if n < 1e-9:
        return np.array([0.0, -1.0])
    return v / n


def _perp(v: np.ndarray) -> np.ndarray:
    """Rotate a unit vector by +90 degrees in image coordinates (x right, y down)."""
    return np.array([-v[1], v[0]])


def segment_band(p0: np.ndarray, p1: np.ndarray, width_ratio: float) -> Polygon:
    """Rectangle around the segment p0->p1 whose width is `width_ratio` times the segment length."""
    p0 = np.asarray(p0, dtype=float)
    p1 = np.asarray(p1, dtype=float)
    d = p1 - p0
    length = float(np.hypot(d[0], d[1]))
    n = _perp(_unit(d)) * (0.5 * width_ratio * length)
    return np.array([p0 + n, p1 + n, p1 - n, p0 - n], dtype=float)


def polyline_band(points: np.ndarray, half_width: float) -> Polygon:
    """Single ring around a polyline, offset by `half_width` on both sides (used for the thumb)."""
    pts = np.asarray(points, dtype=float)
    if pts.shape[0] < 2:
        raise ValueError("polyline needs at least two points")
    normals = []
    for i in range(pts.shape[0]):
        if i == 0:
            t = _unit(pts[1] - pts[0])
        elif i == pts.shape[0] - 1:
            t = _unit(pts[-1] - pts[-2])
        else:
            t = _unit(_unit(pts[i] - pts[i - 1]) + _unit(pts[i + 1] - pts[i]))
        normals.append(_perp(t) * half_width)
    normals = np.asarray(normals)
    left = pts + normals
    right = (pts - normals)[::-1]
    return np.vstack([left, right])


def clip_polygon_to_rect(poly: np.ndarray, width: int, height: int) -> Polygon:
    """Sutherland-Hodgman clip of a polygon against the image rectangle [0, width] x [0, height]."""
    pts = [tuple(map(float, p)) for p in np.asarray(poly, dtype=float)]
    if not pts:
        return np.zeros((0, 2), dtype=float)

    def clip(points, inside, intersect):
        out = []
        if not points:
            return out
        prev = points[-1]
        for cur in points:
            if inside(cur):
                if not inside(prev):
                    out.append(intersect(prev, cur))
                out.append(cur)
            elif inside(prev):
                out.append(intersect(prev, cur))
            prev = cur
        return out

    def x_cross(a, b, x):
        t = (x - a[0]) / (b[0] - a[0])
        return (x, a[1] + t * (b[1] - a[1]))

    def y_cross(a, b, y):
        t = (y - a[1]) / (b[1] - a[1])
        return (a[0] + t * (b[0] - a[0]), y)

    pts = clip(pts, lambda p: p[0] >= 0.0, lambda a, b: x_cross(a, b, 0.0))
    pts = clip(pts, lambda p: p[0] <= width, lambda a, b: x_cross(a, b, float(width)))
    pts = clip(pts, lambda p: p[1] >= 0.0, lambda a, b: y_cross(a, b, 0.0))
    pts = clip(pts, lambda p: p[1] <= height, lambda a, b: y_cross(a, b, float(height)))
    return np.asarray(pts, dtype=float).reshape(-1, 2)


def convex_hull(points: np.ndarray) -> Polygon:
    """Convex hull (counter-clockwise in image coordinates) of a point set."""
    pts = np.asarray(points, dtype=np.float32).reshape(-1, 1, 2)
    hull = cv2.convexHull(pts)
    return hull.reshape(-1, 2).astype(float)


# --------------------------------------------------------------------------- ROI polygons
def roi_polygons(
    lm_xy_px: np.ndarray,
    image_shape: tuple[int, int],
    band_width_ratio: float = 0.6,
    pad_width_ratio: float = 0.6,
    thumb_width_ratio: float = 0.8,
    wrist_pull: float = 0.3,
    thenar_pull: float = 0.3,
    hypothenar_width_ratio: float = 0.6,
    volar_wrist_height_ratio: float = 0.5,
) -> dict[str, RoiShape]:
    """Build every palm ROI polygon (full-res px) from 21 landmark pixel positions (section 6.2).

    Constructions (landmark numbers as in the module header):
      thenar          wrist 0 -> thumb CMC 1 -> thumb MCP 2 -> midpoint(2, 5) -> index MCP 5 pulled
                      `thenar_pull` of the way toward the wrist
      hypothenar      quad from wrist 0 to little MCP 17 widened toward the ulnar edge by
                      `hypothenar_width_ratio` x |17 - 13|
      central_palm    pentagon 5, 9, 13, 17 and wrist 0 pulled `wrist_pull` of the way toward middle MCP 9
      prox_<finger>   MCP -> PIP segment widened to a band of width `band_width_ratio` x segment length
      mid_phalanges   union (list of rings) of the four PIP -> DIP bands
      pad_<finger>    DIP -> TIP band of width `pad_width_ratio` x segment length
      volar_wrist     band below the wrist (away from middle MCP 9), height `volar_wrist_height_ratio`
                      x |9 - 0|, width |5 - 17|, clipped to the image rectangle
      whole_palm      convex hull of all non-thumb landmarks, the hypothenar outer edge and the volar
                      wrist band vertices
      thumb           ring around the 1 -> 2 -> 3 -> 4 polyline, half-width 0.5 x `thumb_width_ratio`
                      x mean segment length; subtracted from every other ROI by `roi_masks`

    Returns {name: (N, 2) float array} with `mid_phalanges` as a list of four rings. The thumb and
    every pulse ROI name are always present; `image_shape` is (height, width).
    """
    lm = np.asarray(lm_xy_px, dtype=float)
    if lm.shape != (N_LANDMARKS, 2):
        raise ValueError(f"expected (21, 2) landmark pixel array, got {lm.shape}")
    h, w = int(image_shape[0]), int(image_shape[1])
    out: dict[str, RoiShape] = {}

    wrist = lm[WRIST]
    # thenar
    index_pulled = lm[INDEX_MCP] + thenar_pull * (wrist - lm[INDEX_MCP])
    out["thenar"] = np.array(
        [wrist, lm[THUMB_CMC], lm[THUMB_MCP], 0.5 * (lm[THUMB_MCP] + lm[INDEX_MCP]), index_pulled], dtype=float
    )
    # hypothenar
    ulnar = hypothenar_width_ratio * (lm[LITTLE_MCP] - lm[RING_MCP])
    out["hypothenar"] = np.array(
        [wrist, lm[LITTLE_MCP], lm[LITTLE_MCP] + ulnar, wrist + ulnar], dtype=float
    )
    # central palm
    wrist_up = wrist + wrist_pull * (lm[MIDDLE_MCP] - wrist)
    out["central_palm"] = np.array(
        [lm[INDEX_MCP], lm[MIDDLE_MCP], lm[RING_MCP], lm[LITTLE_MCP], wrist_up], dtype=float
    )
    # finger bands
    mid_rings: list[Polygon] = []
    for finger, (mcp, pip, dip, tip) in FINGERS.items():
        out[f"prox_{finger}"] = segment_band(lm[mcp], lm[pip], band_width_ratio)
        mid_rings.append(segment_band(lm[pip], lm[dip], band_width_ratio))
        out[f"pad_{finger}"] = segment_band(lm[dip], lm[tip], pad_width_ratio)
    out["mid_phalanges"] = mid_rings
    # volar wrist
    axis = _unit(lm[MIDDLE_MCP] - wrist)
    lateral = _perp(axis)
    palm_w = float(np.hypot(*(lm[INDEX_MCP] - lm[LITTLE_MCP])))
    band_h = volar_wrist_height_ratio * float(np.hypot(*(lm[MIDDLE_MCP] - wrist)))
    half = 0.5 * palm_w * lateral
    volar = np.array([wrist - half, wrist + half, wrist + half - axis * band_h, wrist - half - axis * band_h])
    out["volar_wrist"] = clip_polygon_to_rect(volar, w, h)
    # whole palm hull
    hull_pts = np.vstack([lm[list(NON_THUMB_LANDMARKS)], out["hypothenar"][2:4], volar])
    out["whole_palm"] = clip_polygon_to_rect(convex_hull(hull_pts), w, h)
    # thumb exclusion ring
    thumb_pts = lm[list(THUMB_LANDMARKS)]
    seg_len = float(np.mean(np.hypot(*(np.diff(thumb_pts, axis=0).T))))
    out[EXCLUDED_ROI] = polyline_band(thumb_pts, 0.5 * thumb_width_ratio * seg_len)
    return out


# --------------------------------------------------------------------------- rasterisation
def rasterise(polygon: RoiShape, shape: tuple[int, int], shift: int = 4) -> np.ndarray:
    """Boolean mask of `shape` (height, width) filled by a polygon or a union of rings (cv2.fillPoly).

    Vertices are rounded to 1/2**shift px (fixed-point fillPoly), so sub-pixel polygon edges stay
    stable under slow hand motion. Rings are filled one at a time and OR-ed, so overlapping rings never
    cancel each other. Section 6.2.
    """
    h, w = int(shape[0]), int(shape[1])
    mask = np.zeros((h, w), dtype=np.uint8)
    rings = polygon if isinstance(polygon, list) else [polygon]
    scale = float(1 << shift)
    for ring in rings:
        ring = np.asarray(ring, dtype=float)
        if ring.shape[0] < 3:
            continue
        pts = np.round(ring * scale).astype(np.int32).reshape(-1, 1, 2)
        cv2.fillPoly(mask, [pts], 1, lineType=cv2.LINE_8, shift=shift)
    return mask.astype(bool)


def roi_masks(
    polygons: Mapping[str, RoiShape], shape: tuple[int, int], exclude: Sequence[str] = (EXCLUDED_ROI,)
) -> dict[str, np.ndarray]:
    """Rasterise every ROI at `shape` (height, width) and subtract every `exclude` mask from the rest.

    The excluded masks themselves are returned unmodified under their own names so callers can report
    them (rois.json carries the thumb for exclusion, CONTRACTS section 4). Section 6.2.
    """
    masks = {name: rasterise(poly, shape) for name, poly in polygons.items()}
    excl = [masks[e] for e in exclude if e in masks]
    if excl:
        union = np.logical_or.reduce(excl)
        for name, m in list(masks.items()):
            if name not in exclude:
                masks[name] = m & ~union
    return masks


def downsample_mask(mask: np.ndarray, factor: int = 2) -> np.ndarray:
    """Full-res mask to Bayer-plane coordinates: keep every `factor`-th row and column ([::2, ::2]).

    A plane pixel (r, c) comes from sensor rows 2r..2r+1 and columns 2c..2c+1, so the top-left sensor
    pixel of each 2x2 cell decides membership. CONTRACTS section 0.3.
    """
    if factor == 1:
        return np.asarray(mask, dtype=bool)
    return np.asarray(mask, dtype=bool)[::factor, ::factor]


# --------------------------------------------------------------------------- patch grid
def mask_bbox(mask: np.ndarray) -> tuple[int, int, int, int] | None:
    """(x0, y0, x1, y1) with exclusive upper bounds of the True pixels, or None for an empty mask."""
    ys, xs = np.nonzero(mask)
    if ys.size == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def patch_grid(whole_palm_mask: np.ndarray, rows: int = 16, cols: int = 24) -> list[tuple[int, int, tuple[int, int, int, int]]]:
    """rows x cols cells tiling the whole-palm bounding box: [(r, c, (x0, y0, x1, y1)), ...].

    Cells are listed row-major, always rows*cols of them; bounds are exclusive at the top end and a cell
    may be empty when the bounding box is narrower than the grid. The grid follows the hand because it
    is rebuilt from each landmark frame's whole-palm mask. Section 6.2 (16 x 24 patch grid).
    """
    bbox = mask_bbox(whole_palm_mask)
    if bbox is None:
        return [(r, c, (0, 0, 0, 0)) for r in range(rows) for c in range(cols)]
    x0, y0, x1, y1 = bbox
    xe = np.round(np.linspace(x0, x1, cols + 1)).astype(int)
    ye = np.round(np.linspace(y0, y1, rows + 1)).astype(int)
    out = []
    for r in range(rows):
        for c in range(cols):
            out.append((r, c, (int(xe[c]), int(ye[r]), int(xe[c + 1]), int(ye[r + 1]))))
    return out


def patch_labels(whole_palm_mask: np.ndarray, rows: int = 16, cols: int = 24) -> tuple[np.ndarray, np.ndarray]:
    """Label image for fast per-frame patch means: label = r*cols + c inside the palm, -1 elsewhere.

    Returns (labels int32 of the mask shape, counts (rows*cols,) int64 of palm pixels per cell).
    """
    mask = np.asarray(whole_palm_mask, dtype=bool)
    labels = np.full(mask.shape, -1, dtype=np.int32)
    for r, c, (x0, y0, x1, y1) in patch_grid(mask, rows, cols):
        if x1 > x0 and y1 > y0:
            sub = labels[y0:y1, x0:x1]
            sub[mask[y0:y1, x0:x1]] = r * cols + c
    counts = np.bincount(labels[labels >= 0].ravel(), minlength=rows * cols).astype(np.int64)
    return labels, counts


# --------------------------------------------------------------------------- serialisation
def rois_to_json(polygons: Mapping[str, RoiShape], masks: Mapping[str, np.ndarray], frame_idx: int) -> dict:
    """rois.json payload (CONTRACTS section 4): polygon (first ring), rings (all), frame_idx, n_pixels.

    `n_pixels` counts full-resolution pixels after thumb exclusion (the thumb entry counts its own).
    """
    out = {}
    for name, poly in polygons.items():
        rings = poly if isinstance(poly, list) else [poly]
        rings_l = [np.asarray(r, dtype=float).round(2).tolist() for r in rings]
        out[name] = {
            "polygon": rings_l[0] if rings_l else [],
            "rings": rings_l,
            "frame_idx": int(frame_idx),
            "n_pixels": int(np.count_nonzero(masks[name])) if name in masks else 0,
        }
    return out


def write_rois_json(path: str | Path, payload: dict) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    return path


def rois_from_json(payload: Mapping[str, Mapping]) -> dict[str, RoiShape]:
    """Inverse of `rois_to_json`: rebuild polygon arrays (list of rings when more than one)."""
    out: dict[str, RoiShape] = {}
    for name, entry in payload.items():
        rings = entry.get("rings") or [entry.get("polygon", [])]
        arrs = [np.asarray(r, dtype=float).reshape(-1, 2) for r in rings]
        out[name] = arrs if len(arrs) > 1 else arrs[0]
    return out
