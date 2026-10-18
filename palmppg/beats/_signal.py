"""Signal helpers shared by the beat modules (protocol section 6.5).

Kept inside palmppg.beats so the package depends on palmppg.core only (COMMON rules): NaN bridging, a
zero-phase Butterworth band-pass, a Hann periodogram with sub-bin peak refinement, Savitzky-Golay
derivatives, cubic resampling of one beat onto a fine grid and parabolic sub-sample refinement. All
functions are unit-preserving: a signal in arbitrary units comes out in the same units (derivatives per
second).
"""
from __future__ import annotations

import numpy as np
from scipy.interpolate import CubicSpline
from scipy.signal import butter, savgol_filter, sosfiltfilt

# Fine internal grid for per-beat morphology and the acceleration plethysmogram: beats sampled at 30 Hz
# hold about 25 samples, too few for widths and derivatives, so each beat is cubic-resampled to this rate
# (an algorithm constant, not a protocol quantity).
ANALYSIS_FS = 240.0


# --------------------------------------------------------------------------- NaN handling
def bridge_nans(x) -> tuple[np.ndarray, np.ndarray]:
    """Linearly bridge interior NaN gaps and hold the nearest finite value at the ends.

    Returns (bridged float64 copy, mask of the samples that were NaN); an all-NaN input becomes zeros with
    an all-True mask. Dropped frames stay visible to callers through the mask (section 6.1 / 6.3).
    """
    x = np.asarray(x, dtype=float)
    mask = ~np.isfinite(x)
    out = x.copy()
    if not mask.any():
        return out, mask
    if mask.all():
        out[:] = 0.0
        return out, mask
    idx = np.arange(x.size)
    out[mask] = np.interp(idx[mask], idx[~mask], x[~mask])
    return out, mask


# --------------------------------------------------------------------------- filtering
def bandpass(x, fs: float, lo: float, hi: float, order: int = 4) -> np.ndarray:
    """Zero-phase Butterworth band-pass [lo, hi] Hz (`hi` capped below Nyquist), NaNs bridged then restored.

    The band is a protocol quantity (`pulse.band_rate` for the perfusion index, `beats.resp_band` for the
    respiratory proxy) supplied by the caller. Units: those of `x`.
    """
    z, mask = bridge_nans(x)
    if z.size == 0:
        return z
    nyq = 0.5 * float(fs)
    hi = min(float(hi), 0.98 * nyq)
    if not (0.0 < float(lo) < hi < nyq):
        raise ValueError(f"band [{lo}, {hi}] Hz is not inside (0, {nyq}) Hz")
    sos = butter(int(order), [float(lo) / nyq, hi / nyq], btype="bandpass", output="sos")
    z = z - z.mean()
    padlen = 3 * (2 * sos.shape[0] + 1)
    if z.size <= padlen:
        pad = padlen - z.size + 1
        zz = np.concatenate([np.full(pad, z[0]), z, np.full(pad, z[-1])])
        y = sosfiltfilt(sos, zz)[pad:pad + z.size]
    else:
        y = sosfiltfilt(sos, z)
    y[mask] = np.nan
    return y


# --------------------------------------------------------------------------- spectra
def periodogram(x, fs: float, nfft: int | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Hann-windowed, mean-removed, zero-padded one-sided power spectrum: (f in Hz, power in x^2 units).

    `nfft` defaults to the power of two at or above 8 x len(x) (at least 4096) so peak positions are finely
    interpolated; NaNs are bridged first.
    """
    z, _ = bridge_nans(x)
    n = z.size
    if n == 0:
        return np.zeros(0), np.zeros(0)
    z = z - z.mean()
    if nfft is None:
        nfft = int(2 ** np.ceil(np.log2(max(8 * n, 4096))))
    w = 0.5 - 0.5 * np.cos(2.0 * np.pi * np.arange(n) / n)
    spec = np.fft.rfft(z * w, n=nfft)
    f = np.fft.rfftfreq(nfft, d=1.0 / float(fs))
    pxx = (np.abs(spec) ** 2) / max(float(np.sum(w**2)), 1e-12)
    return f, pxx


def spectral_peak(x, fs: float, band: tuple[float, float]) -> tuple[float, float]:
    """(f_peak_hz, peak_power) of the strongest periodogram bin inside `band` with parabolic refinement.

    Returns (nan, 0) when the band holds no bins or the signal has no power.
    """
    f, pxx = periodogram(x, fs)
    sel = np.where((f >= band[0]) & (f <= band[1]))[0]
    if sel.size == 0 or not np.any(pxx[sel] > 0):
        return float("nan"), 0.0
    k = int(sel[int(np.argmax(pxx[sel]))])
    fpk = float(f[k])
    if 0 < k < f.size - 1:
        y0, y1, y2 = pxx[k - 1], pxx[k], pxx[k + 1]
        den = y0 - 2.0 * y1 + y2
        if den < 0:
            fpk = float(f[k] + 0.5 * (y0 - y2) / den * (f[1] - f[0]))
    return fpk, float(pxx[k])


def band_power_ratio(x, fs: float, band: tuple[float, float]) -> float:
    """Power inside `band` divided by the total power above DC of the mean-removed periodogram (0..1)."""
    f, pxx = periodogram(x, fs)
    if f.size == 0:
        return float("nan")
    total = float(np.sum(pxx[f > 0]))
    if total <= 0:
        return float("nan")
    inband = (f >= band[0]) & (f <= band[1])
    return float(np.sum(pxx[inband]) / total)


# --------------------------------------------------------------------------- refinement and derivatives
def parabolic_refine(y, k: int) -> tuple[float, float]:
    """Sub-sample extremum position and value from the parabola through y[k-1], y[k], y[k+1].

    Returns (k, y[k]) unchanged at the array ends or when the three points are not curved.
    """
    y = np.asarray(y, dtype=float)
    k = int(k)
    if not (0 < k < y.size - 1):
        return float(k), float(y[k]) if y.size else float("nan")
    y0, y1, y2 = y[k - 1], y[k], y[k + 1]
    den = y0 - 2.0 * y1 + y2
    if den == 0:
        return float(k), float(y1)
    delta = float(np.clip(0.5 * (y0 - y2) / den, -0.5, 0.5))
    return float(k + delta), float(y1 - 0.25 * (y0 - y2) * delta)


def odd_window(fs: float, span_s: float, n: int, minimum: int = 5) -> int:
    """Odd Savitzky-Golay window of about `span_s` seconds at `fs`, at least `minimum`, at most n (odd)."""
    w = max(int(round(float(span_s) * float(fs))), int(minimum))
    w += 1 - (w % 2)
    cap = int(n) if int(n) % 2 == 1 else int(n) - 1
    return max(min(w, cap), 1)


def derivative(y, fs: float, deriv: int, span_s: float, polyorder: int = 3) -> np.ndarray:
    """Savitzky-Golay derivative of order `deriv` (per second^deriv) with a window of about `span_s`.

    The polynomial order is raised to `deriv + 1` when `polyorder` is too low for the requested derivative.
    Short inputs (fewer than four samples) fall back to repeated `np.gradient`.
    """
    y = np.asarray(y, dtype=float)
    if y.size < 4:
        out = y.copy()
        for _ in range(int(deriv)):
            out = np.gradient(out, 1.0 / float(fs)) if out.size > 1 else np.zeros_like(out)
        return out
    order = max(int(polyorder), int(deriv) + 1)
    win = odd_window(fs, span_s, y.size, minimum=order + 2)
    if win <= order:
        win = order + 1 + ((order + 1) % 2 == 0)
        win = min(win, y.size - ((y.size + 1) % 2))
    return savgol_filter(y, win, order, deriv=int(deriv), delta=1.0 / float(fs), mode="interp")


def resample_segment(z, start_pos: float, end_pos: float, fs: float, fine_fs: float = ANALYSIS_FS) -> tuple[np.ndarray, np.ndarray]:
    """Cubic-spline resampling of z between fractional sample positions onto a grid at `fine_fs`.

    Returns (tau_s, values) with tau_s measured from `start_pos` (tau[0] = 0). The spline is fitted on the
    samples from two before the start to two after the end so the edges are well conditioned.
    """
    z = np.asarray(z, dtype=float)
    n = z.size
    i0 = int(max(np.floor(start_pos) - 2, 0))
    i1 = int(min(np.ceil(end_pos) + 3, n))
    if i1 - i0 < 4 or end_pos <= start_pos:
        return np.zeros(0), np.zeros(0)
    idx = np.arange(i0, i1)
    spline = CubicSpline(idx, z[i0:i1])
    n_fine = int(np.floor((end_pos - start_pos) * fine_fs / fs)) + 1
    tau = np.arange(n_fine) / float(fine_fs)
    pos = start_pos + tau * fs
    pos = np.clip(pos, i0, i1 - 1)
    return tau, spline(pos)


def local_extrema(y) -> tuple[np.ndarray, np.ndarray]:
    """Indices of strict local maxima and of local minima (ties on the right allowed) of a 1-D array."""
    y = np.asarray(y, dtype=float)
    if y.size < 3:
        return np.zeros(0, dtype=int), np.zeros(0, dtype=int)
    a, b, c = y[:-2], y[1:-1], y[2:]
    maxima = np.where((b > a) & (b >= c))[0] + 1
    minima = np.where((b < a) & (b <= c))[0] + 1
    return maxima, minima


def interp_at(z, pos: float) -> float:
    """Linear interpolation of z at a fractional sample position (clipped to the array)."""
    z = np.asarray(z, dtype=float)
    if z.size == 0:
        return float("nan")
    p = float(np.clip(pos, 0, z.size - 1))
    return float(np.interp(p, np.arange(z.size), z))
