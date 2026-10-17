"""Kardia PDF strip fallback: a synthetic strip renderer and the digitiser (protocol section 6.4).

"Fallback PDF digitiser: deskew, isolate the trace at 25 mm/s and 10 mm/mV, extract and resample to
300 Hz, set ecg_digitised = true; unit-test it on a synthetic PDF you render yourself."

Renderer (`render_synthetic_strip_pdf`, reportlab): a Kardia-like page with a red/pink 1 mm / 5 mm paper
grid, a dark trace drawn at true scale (speed_mm_s, gain_mm_mv), several rows per page, header text, row
labels, and an optional page skew for the deskew test.

Digitiser (`digitise_pdf`): pymupdf rasterises each page at `dpi`; pixels are split into grid (red hue,
light) and trace (dark); the skew is estimated with a Hough transform of the grid lines (coarse) and
refined by maximising the sharpness of the grid's row and column projections; the page is rotated back;
the grid pitch is measured from the line positions (least-squares over all lines, both axes) which gives
px/mm; the trace rows are found as the peaks of the trace-pixel row projection (the isoelectric
baselines); each row's centreline is the per-column centre of mass of the trace pixels; columns map to
seconds through speed_mm_s and px/mm, rows to millivolts through gain_mm_mv and px/mm referenced to the
row's median level; rows are concatenated in reading order (across pages) and resampled to `fs_out`.
Output units: millivolts at `fs_out` Hz, `ecg_digitised = True`.
"""
from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np
from scipy.signal import correlate, find_peaks

from palmppg.core.timeline import resample_to_grid

MM_PER_INCH = 25.4
PT_PER_MM = 72.0 / MM_PER_INCH
A4_LANDSCAPE_MM = (297.0, 210.0)
FINE_GRID_MM = 1.0
BOLD_GRID_MM = 5.0
DEFAULT_SPEED_MM_S = 25.0      # ECG paper convention; the protocol fixes the Kardia export to this
DEFAULT_GAIN_MM_MV = 10.0
DEFAULT_DPI = 300
DEFAULT_FS_OUT = 300.0

# pixel classification (8-bit RGB)
DARK_MAX = 110                 # trace: every channel below this
GRID_MIN_REDNESS = 20          # grid: R exceeds max(G, B) by at least this
GRID_MIN_RED = 150
# geometry
MAX_SKEW_DEG = 3.0
MIN_ROW_GAP_MM = 8.0           # two strip rows are never closer than this
ROW_PROFILE_SMOOTH_MM = 0.5
ROW_PROMINENCE_FRAC = 0.15
BBOX_FRAC = 0.2                # grid bounding box: profile above this fraction of its maximum
MAX_GAP_MM = 2.0               # trace gaps wider than this become NaN in the output
PITCH_TOLERANCE = 0.3          # measured pitch must be within this fraction of 1 mm or 5 mm (dpi prior)


class DigitiserError(RuntimeError):
    pass


# =========================================================================== renderer
def render_synthetic_strip_pdf(path: str | Path, ecg_mv, fs: float, speed_mm_s: float = DEFAULT_SPEED_MM_S,
                               gain_mm_mv: float = DEFAULT_GAIN_MM_MV, rows: int | None = None,
                               row_seconds: float = 10.0, row_pitch_mm: float = 30.0,
                               margins_mm: tuple[float, float, float, float] = (20.0, 12.0, 22.0, 12.0),
                               page_mm: tuple[float, float] = A4_LANDSCAPE_MM, skew_deg: float = 0.0,
                               trace_width_mm: float = 0.25, trace_rgb=(0.10, 0.10, 0.10),
                               fine_rgb=(1.0, 0.76, 0.76), bold_rgb=(1.0, 0.50, 0.50),
                               fine_width_mm: float = 0.15, bold_width_mm: float = 0.30,
                               title: str = "Single-lead strip (synthetic, lead I)") -> dict:
    """Render `ecg_mv` (millivolts at `fs` Hz) as a Kardia-like PDF strip at true scale (protocol 6.4 test).

    Rows of `row_seconds` (or `rows` equal rows) stacked `row_pitch_mm` apart on a red/pink 1 mm / 5 mm
    grid, dark trace at `speed_mm_s` x `gain_mm_mv`, header and row labels outside the grid, continuing on
    further pages when the rows do not fit. `skew_deg` rotates the whole page content about its centre.
    `margins_mm` = (left, right, top, bottom). Returns {path, rows, pages, rows_per_page, row_seconds,
    duration_s, layout}.
    """
    from reportlab.pdfgen import canvas

    x = np.asarray(ecg_mv, dtype=np.float64)
    if x.ndim != 1 or x.size < 2:
        raise ValueError("ecg_mv must be a 1-D array with at least two samples")
    duration = x.size / float(fs)
    if rows is None:
        rows = math.ceil(duration / float(row_seconds) - 1e-9)
    else:
        rows = int(rows)
        row_seconds = duration / rows
    left, right, top, bottom = (float(v) for v in margins_mm)
    page_w, page_h = (float(v) for v in page_mm)
    row_width = float(row_seconds) * float(speed_mm_s)
    if row_width > page_w - left - right:
        raise ValueError(f"row of {row_seconds:.2f} s needs {row_width:.0f} mm, page offers "
                         f"{page_w - left - right:.0f} mm; shorten row_seconds")
    rows_per_page = max(1, int((page_h - top - bottom) // float(row_pitch_mm)))
    pages = math.ceil(rows / rows_per_page)
    half_mm = float(row_pitch_mm) / 2.0 - 1.0
    clip_mv = half_mm / float(gain_mm_mv)
    n_row = round(float(row_seconds) * float(fs))

    c = canvas.Canvas(str(path), pagesize=(page_w * PT_PER_MM, page_h * PT_PER_MM))
    c.setLineCap(0)   # butt caps: the stroke does not extend past the first and last samples
    c.setLineJoin(1)  # round joins: no mitre spikes at sharp R-waves
    for page in range(pages):
        r0 = page * rows_per_page
        r1 = min(rows, r0 + rows_per_page)
        n_here = r1 - r0
        grid_top = page_h - top
        grid_bottom = grid_top - n_here * float(row_pitch_mm)
        c.saveState()
        if skew_deg:
            cx, cy = page_w * PT_PER_MM / 2.0, page_h * PT_PER_MM / 2.0
            c.translate(cx, cy)
            c.rotate(float(skew_deg))
            c.translate(-cx, -cy)
        # header text (dark, outside the grid)
        c.setFillColorRGB(*trace_rgb)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(left * PT_PER_MM, (page_h - top / 2.0 + 2.0) * PT_PER_MM, title)
        c.setFont("Helvetica", 8)
        c.drawString(left * PT_PER_MM, (page_h - top / 2.0 - 3.0) * PT_PER_MM,
                     f"{speed_mm_s:g} mm/s   {gain_mm_mv:g} mm/mV   source {fs:g} Hz   page {page + 1}/{pages}")
        c.drawString(left * PT_PER_MM, (grid_bottom - 5.0) * PT_PER_MM,
                     f"{rows} rows of {row_seconds:.2f} s; {duration:.2f} s in total")
        # grid: fine then bold, as (x1, y1, x2, y2) point lists
        for pitch, rgb, width in ((FINE_GRID_MM, fine_rgb, fine_width_mm), (BOLD_GRID_MM, bold_rgb, bold_width_mm)):
            c.setStrokeColorRGB(*rgb)
            c.setLineWidth(width * PT_PER_MM)
            segs = []
            n_v = round(row_width / pitch)
            for k in range(n_v + 1):
                gx = (left + k * pitch) * PT_PER_MM
                segs.append((gx, grid_bottom * PT_PER_MM, gx, grid_top * PT_PER_MM))
            n_h = round((grid_top - grid_bottom) / pitch)
            for k in range(n_h + 1):
                gy = (grid_bottom + k * pitch) * PT_PER_MM
                segs.append((left * PT_PER_MM, gy, (left + row_width) * PT_PER_MM, gy))
            c.lines(segs)
        # rows
        c.setStrokeColorRGB(*trace_rgb)
        c.setLineWidth(float(trace_width_mm) * PT_PER_MM)
        c.setFont("Helvetica", 7)
        for r in range(r0, r1):
            base_y = grid_top - (r - r0 + 0.5) * float(row_pitch_mm)
            seg = np.clip(x[r * n_row:(r + 1) * n_row], -clip_mv, clip_mv)
            if seg.size < 2:
                continue
            xs = (left + np.arange(seg.size) / float(fs) * float(speed_mm_s)) * PT_PER_MM
            ys = (base_y + seg * float(gain_mm_mv)) * PT_PER_MM
            p = c.beginPath()
            p.moveTo(float(xs[0]), float(ys[0]))
            for xi, yi in zip(xs[1:], ys[1:]):
                p.lineTo(float(xi), float(yi))
            c.drawPath(p, stroke=1, fill=0)
            c.setFillColorRGB(*trace_rgb)
            c.drawString((left - 13.0) * PT_PER_MM, (base_y - 1.0) * PT_PER_MM, f"I {r * row_seconds:5.1f}s")
        c.restoreState()
        c.showPage()
    c.save()
    return {"path": str(path), "rows": rows, "pages": pages, "rows_per_page": rows_per_page,
            "row_seconds": float(row_seconds), "duration_s": duration,
            "layout": {"margins_mm": [left, right, top, bottom], "row_pitch_mm": float(row_pitch_mm),
                       "page_mm": [page_w, page_h], "speed_mm_s": float(speed_mm_s),
                       "gain_mm_mv": float(gain_mm_mv), "skew_deg": float(skew_deg),
                       "trace_width_mm": float(trace_width_mm), "clip_mv": clip_mv}}


# =========================================================================== digitiser building blocks
def rasterise_pdf(path: str | Path, dpi: int = DEFAULT_DPI) -> list[np.ndarray]:
    """Every page as an RGB uint8 array (H, W, 3) rendered at `dpi` with pymupdf."""
    import pymupdf

    out = []
    with pymupdf.open(str(path)) as doc:
        for page in doc:
            pix = page.get_pixmap(dpi=int(dpi), colorspace=pymupdf.csRGB, alpha=False)
            arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            out.append(np.ascontiguousarray(arr[:, :, :3]))
    return out


def classify_pixels(rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(grid_mask, trace_mask): grid = light pixels with a red hue (R above G and B); trace = dark pixels."""
    r = rgb[:, :, 0].astype(np.int16)
    g = rgb[:, :, 1].astype(np.int16)
    b = rgb[:, :, 2].astype(np.int16)
    trace = np.maximum(np.maximum(r, g), b) < DARK_MAX
    redness = r - np.maximum(g, b)
    grid = (~trace) & (redness > GRID_MIN_REDNESS) & (r > GRID_MIN_RED)
    return grid, trace


def rotate_image(img: np.ndarray, angle_deg: float, border):
    """Rotate about the image centre by `angle_deg` (OpenCV convention: positive = counter-clockwise)."""
    h, w = img.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), float(angle_deg), 1.0)
    return cv2.warpAffine(img, m, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=border)


def _shrink(mask: np.ndarray, scale: float) -> np.ndarray:
    return cv2.resize(mask.astype(np.float32), None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)


def projection_sharpness(mask_f: np.ndarray, angle_deg: float) -> float:
    """Squared coefficient of variation of the row and column projections after rotating by `angle_deg`;
    maximal when the grid lines are axis-aligned."""
    rot = rotate_image(mask_f, angle_deg, 0.0)
    col = rot.sum(axis=0)
    row = rot.sum(axis=1)
    out = 0.0
    for p in (col, row):
        m = float(p.mean())
        if m > 0:
            out += float(p.var()) / (m * m)
    return out


def hough_skew_deg(grid_mask: np.ndarray, scale: float = 0.25, max_deg: float = MAX_SKEW_DEG) -> float | None:
    """Median tilt (degrees) of the near-horizontal grid lines from a Hough transform of the grid mask at
    reduced scale; None when no line reaches the vote threshold."""
    small = (_shrink(grid_mask, scale) > 0.25).astype(np.uint8) * 255
    theta_step = math.radians(0.05)
    lim = math.radians(max_deg)
    lines = cv2.HoughLines(small, 1, theta_step, int(0.25 * min(small.shape)), None, 0, 0,
                           math.pi / 2 - lim, math.pi / 2 + lim)
    if lines is None or len(lines) == 0:
        return None
    thetas = lines[:min(len(lines), 400), 0, 1]
    dev = thetas - math.pi / 2
    return float(np.degrees(np.median(dev)))


def estimate_skew_deg(grid_mask: np.ndarray, max_deg: float = MAX_SKEW_DEG) -> dict:
    """Skew of the page: Hough coarse estimate, then a projection-sharpness scan at 1/4 scale over
    +/- max_deg in 0.1 deg steps seeded with the Hough candidates (both signs), refined at 1/2 scale in
    0.01 deg steps. Returns {skew_deg (angle to pass to rotate_image), hough_deg, coarse_deg}."""
    hough = hough_skew_deg(grid_mask)
    small = _shrink(grid_mask, 0.25)
    angles = list(np.round(np.arange(-max_deg, max_deg + 1e-9, 0.1), 3))
    if hough is not None and abs(hough) <= max_deg:
        angles += [hough, -hough]
    scores = {a: projection_sharpness(small, a) for a in angles}
    coarse = max(scores, key=scores.get)
    half = _shrink(grid_mask, 0.5)
    fine_angles = np.arange(coarse - 0.15, coarse + 0.15 + 1e-9, 0.01)
    fine_scores = [projection_sharpness(half, float(a)) for a in fine_angles]
    best = float(fine_angles[int(np.argmax(fine_scores))])
    return {"skew_deg": best, "hough_deg": hough, "coarse_deg": float(coarse)}


def _profile_bbox(profile: np.ndarray, frac: float = BBOX_FRAC) -> tuple[int, int] | None:
    if profile.size == 0 or profile.max() <= 0:
        return None
    idx = np.where(profile > frac * profile.max())[0]
    if idx.size == 0:
        return None
    return int(idx[0]), int(idx[-1]) + 1


def grid_bbox(grid_mask: np.ndarray) -> tuple[int, int, int, int] | None:
    """(x0, x1, y0, y1) half-open pixel bounds of the paper grid, or None when no grid is visible."""
    cols = _profile_bbox(grid_mask.sum(axis=0).astype(np.float64))
    rows = _profile_bbox(grid_mask.sum(axis=1).astype(np.float64))
    if cols is None or rows is None:
        return None
    return cols[0], cols[1], rows[0], rows[1]


def line_pitch_px(profile: np.ndarray, min_lag_px: int = 3) -> dict:
    """Pitch of a periodic line profile (grid-line centres along one axis).

    Autocorrelation gives the first lag with a local maximum (coarse pitch); the line centres are then
    found as profile peaks, refined by centroid, indexed by rounding their spacing to the coarse pitch,
    and the pitch is the least-squares slope of position versus index. Returns {pitch_px, n_lines,
    coarse_px, residual_px}.
    """
    p = np.asarray(profile, dtype=np.float64)
    p = p - p.mean()
    empty = {"pitch_px": float("nan"), "n_lines": 0, "coarse_px": float("nan"), "residual_px": float("nan"),
             "first_px": float("nan"), "last_px": float("nan")}
    if p.size < 2 * min_lag_px + 2 or not np.any(p):
        return empty
    ac = correlate(p, p, mode="full")[p.size - 1:]
    ac = ac / ac[0]
    lag_max = max(min_lag_px + 2, p.size // 4)
    seg = ac[:lag_max]
    peaks, _ = find_peaks(seg, prominence=0.05)
    peaks = peaks[peaks >= min_lag_px]
    if peaks.size == 0:
        return empty
    coarse = float(peaks[0])
    raw = np.asarray(profile, dtype=np.float64)
    prom = ROW_PROMINENCE_FRAC * float(raw.max() - np.median(raw))
    # zero padding so the outermost lines, which sit on the profile edges, are found as peaks too
    pad = max(1, int(coarse))
    padded = np.concatenate([np.zeros(pad), raw, np.zeros(pad)])
    centres, _ = find_peaks(padded, distance=max(1, int(0.6 * coarse)), prominence=max(prom, 1e-9))
    centres = centres - pad
    if centres.size < 3:
        return {"pitch_px": coarse, "n_lines": int(centres.size), "coarse_px": coarse, "residual_px": float("nan"),
                "first_px": float("nan"), "last_px": float("nan")}
    half = max(1, round(coarse / 3.0))
    refined = np.empty(centres.size)
    for i, c in enumerate(centres):
        lo, hi = max(0, c - half), min(raw.size, c + half + 1)
        w = raw[lo:hi] - min(raw[lo:hi].min(), 0.0)
        refined[i] = (np.arange(lo, hi) * w).sum() / w.sum() if w.sum() > 0 else c
    # line index from the spacing to the previous line (robust to a coarse pitch off by a few per cent,
    # which rounding the distance from the first line would accumulate over hundreds of lines)
    k = np.concatenate([[0.0], np.cumsum(np.maximum(1.0, np.round(np.diff(refined) / coarse)))])
    slope, intercept = np.polyfit(k, refined, 1)
    resid = refined - (intercept + slope * k)
    return {"pitch_px": float(slope), "n_lines": int(centres.size), "coarse_px": coarse,
            "residual_px": float(np.sqrt(np.mean(resid**2))),
            "first_px": float(intercept), "last_px": float(intercept + slope * k[-1])}


def px_per_mm_from_pitch(pitch_px: float, dpi: float) -> tuple[float, str]:
    """Interpret a measured pitch as the 1 mm or the 5 mm grid using the rasterisation dpi as the prior
    (a Kardia export is at true scale); returns (px_per_mm, basis) with basis in {fine, bold, unverified}."""
    expected = float(dpi) / MM_PER_INCH
    if not np.isfinite(pitch_px) or pitch_px <= 0:
        return expected, "unverified"
    if abs(pitch_px / expected - 1.0) <= PITCH_TOLERANCE:
        return float(pitch_px), "fine"
    if abs(pitch_px / (BOLD_GRID_MM * expected) - 1.0) <= PITCH_TOLERANCE:
        return float(pitch_px) / BOLD_GRID_MM, "bold"
    return float(pitch_px), "unverified"


def find_row_baselines(trace_mask: np.ndarray, bbox: tuple[int, int, int, int], px_per_mm: float) -> np.ndarray:
    """Image rows of the strip baselines inside the grid bbox: peaks of the smoothed trace-pixel row
    projection at least MIN_ROW_GAP_MM apart with prominence >= ROW_PROMINENCE_FRAC of the maximum."""
    x0, x1, y0, y1 = bbox
    prof = trace_mask[y0:y1, x0:x1].sum(axis=1).astype(np.float64)
    if prof.max() <= 0:
        return np.zeros(0, dtype=np.int64)
    k = max(1, round(ROW_PROFILE_SMOOTH_MM * px_per_mm))
    sm = np.convolve(prof, np.ones(k) / k, mode="same")
    dist = max(1, round(MIN_ROW_GAP_MM * px_per_mm))
    peaks, _ = find_peaks(sm, distance=dist, prominence=ROW_PROMINENCE_FRAC * float(sm.max()))
    return (peaks + y0).astype(np.int64)


def _longest_run(flags: np.ndarray, max_gap: int) -> tuple[int, int] | None:
    """(start, end) half-open of the longest run of True values allowing gaps of up to `max_gap` False."""
    idx = np.where(flags)[0]
    if idx.size == 0:
        return None
    breaks = np.where(np.diff(idx) > max_gap + 1)[0]
    starts = np.concatenate([[0], breaks + 1])
    ends = np.concatenate([breaks + 1, [idx.size]])
    lengths = idx[ends - 1] - idx[starts]
    j = int(np.argmax(lengths))
    return int(idx[starts[j]]), int(idx[ends[j] - 1]) + 1


STEEP_COLUMN_FACTOR = 1.5     # a column holding more than this times the stroke width carries a steep segment


def trace_row(trace_mask: np.ndarray, y_top: int, y_bot: int, x0: int, x1: int, px_per_mm: float) -> dict:
    """Centreline of one strip row from the trace pixels inside the band.

    Each column's sample is the centre of mass of its trace pixels, except at the apex of a sharp wave:
    a column that is a local extremum of the centre-of-mass sequence and holds a tall pixel run (steep
    flanks entering it) takes the run's extreme edge moved inward by half the stroke width, which is
    where the drawn path's tip is (the centre of mass of such a column sits well below an R apex).
    Returns {x_cols (absolute column index), y_centre (NaN where no trace), count, stroke_px (median
    pixels per column), x_start, x_end (longest trace run), multi_run_frac, baseline_px}.
    """
    sub = trace_mask[y_top:y_bot, x0:x1]
    ys = np.arange(y_top, y_bot, dtype=np.float64)[:, None]
    cnt = sub.sum(axis=0).astype(np.float64)
    with np.errstate(invalid="ignore", divide="ignore"):
        yc = (sub * ys).sum(axis=0) / cnt
    yc[cnt == 0] = np.nan
    run = _longest_run(cnt > 0, max_gap=round(MAX_GAP_MM * px_per_mm))
    if run is None:
        return {"x_cols": np.zeros(0), "y_centre": np.zeros(0), "count": np.zeros(0), "stroke_px": float("nan"),
                "x_start": None, "x_end": None, "multi_run_frac": float("nan"), "baseline_px": float("nan")}
    s, e = run
    cols = np.arange(x0 + s, x0 + e, dtype=np.float64)
    sub = sub[:, s:e]
    yc, cnt = yc[s:e], cnt[s:e]
    stroke = float(np.median(cnt[cnt > 0]))
    half = 0.5 * stroke
    has = cnt > 0
    y_min = np.where(has, np.argmax(sub, axis=0) + y_top, np.nan)
    y_max = np.where(has, y_bot - 1 - np.argmax(sub[::-1], axis=0), np.nan)
    if yc.size >= 3:
        filled = yc.copy()
        if (~has).any() and has.any():
            filled[~has] = np.interp(np.where(~has)[0], np.where(has)[0], yc[has])
        mid, prev, nxt = filled[1:-1], filled[:-2], filled[2:]
        steep = cnt[1:-1] > STEEP_COLUMN_FACTOR * stroke
        top = (mid < prev) & (mid <= nxt) & steep & has[1:-1]      # image y minimum = signal maximum
        bottom = (mid > prev) & (mid >= nxt) & steep & has[1:-1]
        yc = yc.copy()
        yc[1:-1] = np.where(top, y_min[1:-1] + half, np.where(bottom, y_max[1:-1] - half, yc[1:-1]))
    transitions = (np.diff(sub.astype(np.int8), axis=0) == 1).sum(axis=0)
    multi = float(np.mean(transitions > 1)) if transitions.size else float("nan")
    return {"x_cols": cols, "y_centre": yc, "count": cnt, "stroke_px": stroke, "x_start": float(x0 + s),
            "x_end": float(x0 + e - 1), "multi_run_frac": multi, "baseline_px": float(np.nanmedian(yc))}


def digitise_page(rgb: np.ndarray, dpi: int, speed_mm_s: float, gain_mm_mv: float) -> dict:
    """Deskew, calibrate and trace every strip row on one rasterised page. Returns {rows: [row dicts with
    t_rel_s, mv, duration_s, ...], calibration: {...}, problems: [...]} (rows empty when no grid)."""
    grid, _ = classify_pixels(rgb)
    problems: list[str] = []
    if grid.sum() < 0.001 * grid.size:
        return {"rows": [], "calibration": {}, "problems": ["no paper grid found on the page"]}
    skew = estimate_skew_deg(grid)
    if abs(skew["skew_deg"]) > 0.005:
        rgb = rotate_image(rgb, skew["skew_deg"], (255, 255, 255))
        grid, trace = classify_pixels(rgb)
    else:
        grid, trace = classify_pixels(rgb)
    bbox = grid_bbox(grid)
    if bbox is None:
        return {"rows": [], "calibration": {"skew": skew}, "problems": ["grid bounding box empty"]}
    x0, x1, y0, y1 = bbox
    col_prof = grid[y0:y1, x0:x1].sum(axis=0).astype(np.float64)
    row_prof = grid[y0:y1, x0:x1].sum(axis=1).astype(np.float64)
    px_x = line_pitch_px(col_prof)
    px_y = line_pitch_px(row_prof)
    ppm_x, basis_x = px_per_mm_from_pitch(px_x["pitch_px"], dpi)
    ppm_y, basis_y = px_per_mm_from_pitch(px_y["pitch_px"], dpi)
    if basis_x == "unverified" or basis_y == "unverified":
        problems.append(f"grid pitch could not be matched to 1 mm or 5 mm (x {px_x['pitch_px']:.2f} px, "
                        f"y {px_y['pitch_px']:.2f} px at {dpi} dpi)")
    ppm = 0.5 * (ppm_x + ppm_y)
    x_left = x0 + px_x["first_px"]      # outermost vertical grid lines (sub-pixel, from the line fit)
    x_right = x0 + px_x["last_px"]
    baselines = find_row_baselines(trace, bbox, ppm)
    rows: list[dict] = []
    if baselines.size == 0:
        problems.append("no trace rows found inside the grid")
    else:
        if baselines.size >= 2:
            half = float(np.median(np.diff(baselines))) / 2.0
        else:
            half = min(baselines[0] - y0, y1 - baselines[0])
        for i, yb in enumerate(baselines):
            top = int(max(y0, (baselines[i - 1] + yb) // 2 if i > 0 else yb - half))
            bot = int(min(y1, (yb + baselines[i + 1]) // 2 if i + 1 < baselines.size else yb + half))
            tr = trace_row(trace, top, bot, x0, x1, ppm)
            if tr["x_start"] is None or tr["x_cols"].size < 2:
                problems.append(f"row {i} at y={int(yb)} has no trace")
                continue
            # Row timing. A stroke's butt cap sticks out sideways by up to half the stroke width where the
            # path starts or ends on a steep segment, so the trace run over-reads the row extent by a
            # pixel or two per end. The strip layout gives cap-free references: rows start on the grid's
            # left edge and full rows span the whole grid, both located sub-pixel by the grid-line fit.
            # The trace is snapped to an edge when it lies within one stroke width of it; otherwise the
            # measured run is used with the expected cap excess (a quarter stroke width) removed.
            w = tr["stroke_px"] if np.isfinite(tr["stroke_px"]) else 0.0
            snap_start = np.isfinite(x_left) and abs(tr["x_start"] - x_left) <= max(w, 1.0)
            snap_end = np.isfinite(x_right) and abs(tr["x_end"] - x_right) <= max(w, 1.0)
            origin = x_left if snap_start else tr["x_start"] + 0.25 * w
            px_per_s = float(speed_mm_s) * ppm_x
            if snap_end and snap_start:
                duration = (x_right - x_left) / px_per_s           # first sample to the next row's first
                full = True
            else:
                duration = (tr["x_end"] - 0.25 * w - origin) / px_per_s   # first to last sample
                full = False
            t_rel = (tr["x_cols"] - origin) / px_per_s
            mv = (tr["baseline_px"] - tr["y_centre"]) / (float(gain_mm_mv) * ppm_y)
            touches = bool(np.nanmin(tr["y_centre"]) <= top + 1 or np.nanmax(tr["y_centre"]) >= bot - 2)
            rows.append({"index_on_page": i, "baseline_px": tr["baseline_px"], "y_top": top, "y_bot": bot,
                         "x_start": tr["x_start"], "x_end": tr["x_end"], "stroke_px": tr["stroke_px"],
                         "origin_px": float(origin), "snapped": [bool(snap_start), bool(snap_end)], "full": full,
                         "duration_s": float(duration),
                         "coverage": float(np.mean(tr["count"] > 0)), "multi_run_frac": tr["multi_run_frac"],
                         "touches_band_edge": touches, "t_rel_s": t_rel, "mv": mv})
    cal = {"skew_deg": skew["skew_deg"], "hough_skew_deg": skew["hough_deg"], "px_per_mm_x": ppm_x,
           "px_per_mm_y": ppm_y, "px_per_mm": ppm, "pitch_basis_x": basis_x, "pitch_basis_y": basis_y,
           "pitch_px_x": px_x["pitch_px"], "pitch_px_y": px_y["pitch_px"], "n_lines_x": px_x["n_lines"],
           "n_lines_y": px_y["n_lines"], "pitch_residual_px": [px_x["residual_px"], px_y["residual_px"]],
           "grid_bbox_px": [x0, x1, y0, y1], "grid_edges_px": [float(x_left), float(x_right)], "dpi": int(dpi)}
    return {"rows": rows, "calibration": cal, "problems": problems}


def resample_trace(t: np.ndarray, v: np.ndarray, grid: np.ndarray, max_gap_s: float) -> np.ndarray:
    """Native column samples (t strictly increasing) -> uniform grid by a cubic spline through the samples
    (linear interpolation clips narrow R apices that fall between grid points); NaN outside the samples
    and inside gaps wider than `max_gap_s`."""
    from scipy.interpolate import CubicSpline

    if t.size < 4:
        return resample_to_grid(t, v, grid, max_gap_s=max_gap_s)
    out = CubicSpline(t, v, extrapolate=False)(grid)
    gaps = np.where(np.diff(t) > max_gap_s)[0]
    for i in gaps:
        out[(grid > t[i]) & (grid < t[i + 1])] = np.nan
    return out


# =========================================================================== public entry point
def digitise_pdf(path: str | Path, fs_out: float = DEFAULT_FS_OUT, dpi: int = DEFAULT_DPI,
                 speed_mm_s: float = DEFAULT_SPEED_MM_S, gain_mm_mv: float = DEFAULT_GAIN_MM_MV) -> dict:
    """Digitise a Kardia-style PDF strip into millivolts at `fs_out` Hz (protocol 6.4 fallback path).

    Returns {samples_mv (float32, NaN inside trace gaps wider than MAX_GAP_MM), fs, ecg_digitised: True,
    rows_found, n_pages, duration_s, calibration {px_per_mm, px_per_mm_x, px_per_mm_y, dpi, speed_mm_s,
    gain_mm_mv, skew_deg (per page), hough_skew_deg, pitch_basis, stroke_width_px, fs_native_hz, grid_bbox_px},
    quality {trace_coverage, gap_frac, multi_run_frac, anisotropy, row_durations_s, rows_touching_edge,
    ok, problems}, rows (per-row geometry)}. Full rows are given a common duration (the mean of the rows
    within 1 % of the longest) so stroke-end errors do not accumulate across rows; the last, shorter row
    keeps its own. Raises DigitiserError when no row can be traced on any page.
    """
    pages = rasterise_pdf(path, dpi)
    all_rows: list[dict] = []
    cals: list[dict] = []
    problems: list[str] = []
    for p, rgb in enumerate(pages):
        res = digitise_page(rgb, dpi, speed_mm_s, gain_mm_mv)
        problems.extend(f"page {p + 1}: {m}" for m in res["problems"])
        if res["calibration"]:
            cals.append(res["calibration"])
        for r in res["rows"]:
            r["page"] = p + 1
            all_rows.append(r)
    if not all_rows:
        raise DigitiserError(f"{path}: no strip rows found ({'; '.join(problems) or 'no pages'})")

    durations = np.array([r["duration_s"] for r in all_rows], dtype=np.float64)
    is_full = np.array([r["full"] for r in all_rows], dtype=bool)
    if not is_full.any():
        is_full = durations >= 0.99 * durations.max()
    common = float(durations[is_full].mean()) if is_full.any() else float("nan")
    row_dur = np.where(is_full, common, durations)
    step = 1.0 / float(fs_out)
    t_parts, v_parts = [], []
    offset = 0.0
    for r, d, f in zip(all_rows, row_dur, is_full):
        r["t_offset_s"] = offset
        r["duration_used_s"] = float(d)
        ok = np.isfinite(r["mv"])
        t_parts.append(offset + r["t_rel_s"][ok])
        v_parts.append(r["mv"][ok])
        # a full row's duration already reaches the next row's first sample; a partial row's does not
        offset += float(d) if f else float(d) + step
    t_all = np.concatenate(t_parts)
    v_all = np.concatenate(v_parts)
    order = np.argsort(t_all, kind="stable")
    t_all, v_all = t_all[order], v_all[order]
    keep = np.concatenate([[True], np.diff(t_all) > 0])
    t_all, v_all = t_all[keep], v_all[keep]
    total = offset - step
    n_out = math.floor(total * float(fs_out) + 1e-6) + 1
    grid = np.arange(n_out) * step
    ppm_x = float(np.mean([c["px_per_mm_x"] for c in cals]))
    max_gap_s = MAX_GAP_MM / float(speed_mm_s)
    mv_out = resample_trace(t_all, v_all, grid, max_gap_s=max_gap_s)
    # the first and last output samples sit on the row ends: hold the nearest value instead of NaN
    first_ok = np.where(np.isfinite(mv_out))[0]
    if first_ok.size:
        mv_out[:first_ok[0]] = mv_out[first_ok[0]]
        mv_out[first_ok[-1] + 1:] = mv_out[first_ok[-1]]

    ppm = float(np.mean([c["px_per_mm"] for c in cals]))
    ppm_y = float(np.mean([c["px_per_mm_y"] for c in cals]))
    coverage = float(np.mean([r["coverage"] for r in all_rows]))
    gap_frac = float(np.mean(~np.isfinite(mv_out))) if mv_out.size else 1.0
    anis = ppm_x / ppm_y if ppm_y > 0 else float("nan")
    touching = [i for i, r in enumerate(all_rows) if r["touches_band_edge"]]
    bases = {c["pitch_basis_x"] for c in cals} | {c["pitch_basis_y"] for c in cals}
    ok = (coverage > 0.9 and gap_frac < 0.05 and abs(anis - 1.0) < 0.05 and "unverified" not in bases)
    calibration = {
        "px_per_mm": ppm, "px_per_mm_x": ppm_x, "px_per_mm_y": ppm_y, "dpi": int(dpi),
        "speed_mm_s": float(speed_mm_s), "gain_mm_mv": float(gain_mm_mv),
        "skew_deg": [c["skew_deg"] for c in cals], "hough_skew_deg": [c["hough_skew_deg"] for c in cals],
        "pitch_basis": sorted(bases), "stroke_width_px": float(np.nanmedian([r["stroke_px"] for r in all_rows])),
        "fs_native_hz": float(speed_mm_s) * ppm_x, "grid_bbox_px": [c["grid_bbox_px"] for c in cals],
        "n_grid_lines": [[c["n_lines_x"], c["n_lines_y"]] for c in cals],
    }
    quality = {"trace_coverage": coverage, "gap_frac": gap_frac,
               "multi_run_frac": float(np.nanmean([r["multi_run_frac"] for r in all_rows])),
               "anisotropy": float(anis), "row_durations_s": [float(d) for d in durations],
               "rows_touching_edge": touching, "n_rows": len(all_rows), "ok": bool(ok), "problems": problems}
    rows_out = [{k: v for k, v in r.items() if k not in ("t_rel_s", "mv")} for r in all_rows]
    return {"samples_mv": mv_out.astype(np.float32), "fs": float(fs_out), "ecg_digitised": True,
            "rows_found": len(all_rows), "n_pages": len(pages), "duration_s": float(total),
            "calibration": calibration, "quality": quality, "rows": rows_out}
