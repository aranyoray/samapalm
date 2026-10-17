"""Pulse rate from a pulse signal: instantaneous series and clip-level values (protocol 6.3, 4.3, E1).

`instantaneous_rate` gives the (t, bpm) series that the sync cross-correlation of section 4.3 compares
with the ECG rate series (resampled to `sync.xcorr.rate_fs`) and that E1 (pulse rate versus ECG HR)
summarises. `clip_hr` gives the clip-level rate from the spectral peak and from the median beat
interval. Times are seconds on the reference clock: `t0` is the reference time of sample 0.
"""
from __future__ import annotations

import numpy as np

from palmppg.core.timeline import resample_to_grid, uniform_grid
from palmppg.pulse.preprocess import bridge_nans, window_iter
from palmppg.pulse.sqi import detect_beats, spectral_peak

RATE_METHODS = ("peaks", "stft")


def refine_peaks(x: np.ndarray, peaks: np.ndarray) -> np.ndarray:
    """Sub-sample peak positions by a parabola through the three samples around each peak.

    At 30 fps one sample of IBI is about 3 bpm at 75 bpm, so the refinement is what makes a beat-based
    rate series usable (section 4.3 cross-correlation, E1)."""
    z, _ = bridge_nans(x)
    out = np.asarray(peaks, dtype=float).copy()
    for i, k in enumerate(peaks):
        if 0 < k < z.size - 1:
            y0, y1, y2 = z[k - 1], z[k], z[k + 1]
            den = y0 - 2.0 * y1 + y2
            if den < 0:
                out[i] = k + float(np.clip(0.5 * (y0 - y2) / den, -0.5, 0.5))
    return out


def beat_times(x: np.ndarray, fs: float, band: tuple[float, float], ibi_bounds_s: tuple[float, float] = (0.33, 2.0),
               t0: float = 0.0) -> np.ndarray:
    """Systolic peak times (s, sub-sample refined) of a volume-polarity pulse signal; see `sqi.detect_beats`."""
    peaks = detect_beats(x, fs, band, ibi_bounds_s)
    return t0 + refine_peaks(x, peaks) / float(fs)


def rate_from_beats(times_s: np.ndarray, grid_s: np.ndarray, ibi_bounds_s: tuple[float, float] = (0.33, 2.0),
                    max_gap_s: float = 2.0) -> np.ndarray:
    """Instantaneous rate (bpm) from beat times on `grid_s`: 60 / IBI at interval midpoints, linearly
    interpolated; NaN outside the beats, inside gaps longer than `max_gap_s` and across intervals outside
    `ibi_bounds_s` (missed or spurious beats)."""
    t = np.sort(np.asarray(times_s, dtype=float))
    grid = np.asarray(grid_s, dtype=float)
    if t.size < 2:
        return np.full(grid.size, np.nan)
    ibi = np.diff(t)
    ok = (ibi >= ibi_bounds_s[0]) & (ibi <= ibi_bounds_s[1])
    mid = 0.5 * (t[:-1] + t[1:])
    if ok.sum() < 2:
        return np.full(grid.size, np.nan)
    rate = resample_to_grid(mid[ok], 60.0 / ibi[ok], grid, max_gap_s=max_gap_s)
    return rate


def instantaneous_rate(
    x: np.ndarray, fs: float, method: str = "peaks", grid_fs: float = 4.0, t0: float = 0.0,
    band: tuple[float, float] = (0.5, 4.0), ibi_bounds_s: tuple[float, float] = (0.33, 2.0),
    stft_window_s: float = 8.0, max_gap_s: float = 2.0,
) -> tuple[np.ndarray, np.ndarray]:
    """(t, bpm) instantaneous pulse rate on a uniform grid at `grid_fs` Hz (section 4.3 / E1).

    "peaks": beat intervals from the systolic peaks (`sqi.detect_beats`), 60 / IBI at the interval
    midpoints interpolated onto the grid (NaN in gaps, see `rate_from_beats`). "stft": the spectral
    peak in `band` of a sliding `stft_window_s` Hann window stepped at 1 / `grid_fs`, placed at the
    window centre and interpolated onto the grid (NaN beyond the first and last window centre). `grid_fs`
    is `sync.xcorr.rate_fs` for the sync use; `ibi_bounds_s` is `beats.ibi_bounds_s`. Times are
    `t0` + sample / fs.
    """
    if method not in RATE_METHODS:
        raise ValueError(f"method must be one of {RATE_METHODS}")
    x = np.asarray(x, dtype=float)
    n = x.size
    if n == 0:
        return np.zeros(0), np.zeros(0)
    grid = uniform_grid(t0, t0 + (n - 1) / float(fs), float(grid_fs))
    if method == "peaks":
        return grid, rate_from_beats(beat_times(x, fs, band, ibi_bounds_s, t0), grid, ibi_bounds_s, max_gap_s)
    z, mask = bridge_nans(x)
    centres, bpm = [], []
    step_s = 1.0 / float(grid_fs)
    for i0, i1, seg in window_iter(z, fs, stft_window_s, step_s):
        if mask[i0:i1].mean() > 0.5:
            continue
        f0, _ = spectral_peak(seg, fs, band)
        if np.isfinite(f0):
            centres.append(t0 + 0.5 * (i0 + i1 - 1) / float(fs))
            bpm.append(60.0 * f0)
    if len(centres) < 2:
        return grid, np.full(grid.size, np.nan)
    return grid, resample_to_grid(np.asarray(centres), np.asarray(bpm), grid, max_gap_s=max(2.0 * step_s, max_gap_s))


def clip_hr(x: np.ndarray, fs: float, band: tuple[float, float], ibi_bounds_s: tuple[float, float] = (0.33, 2.0)) -> dict:
    """Clip-level pulse rate: {"hr_spectral_bpm", "f_peak_hz", "hr_ibi_median_bpm", "n_beats", "ibi_median_s"}.

    `hr_spectral_bpm` = 60 x the periodogram peak in `band` over the whole signal; `hr_ibi_median_bpm` =
    60 / median of the beat intervals inside `ibi_bounds_s`. Section 6.3 / E1.
    """
    x = np.asarray(x, dtype=float)
    f0, _ = spectral_peak(x, fs, band) if np.isfinite(x).sum() >= 8 else (float("nan"), 0.0)
    t = beat_times(x, fs, band, ibi_bounds_s)
    ibi = np.diff(t)
    ibi = ibi[(ibi >= ibi_bounds_s[0]) & (ibi <= ibi_bounds_s[1])]
    med = float(np.median(ibi)) if ibi.size else float("nan")
    return {
        "hr_spectral_bpm": float(60.0 * f0) if np.isfinite(f0) else float("nan"), "f_peak_hz": float(f0),
        "hr_ibi_median_bpm": float(60.0 / med) if np.isfinite(med) and med > 0 else float("nan"),
        "n_beats": int(t.size), "ibi_median_s": med,
    }
