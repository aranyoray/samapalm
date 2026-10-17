"""Common pulse preprocessing (protocol section 6.3 "common preprocessing").

Detrend with the smoothness-prior method of Tarvainen, Ranta-aho and Karjalainen (2002), zero-phase
Butterworth band-pass (0.5-4 Hz for rate and rhythm, 0.4-8 Hz for morphology; both from the config),
z-score per clip. NaN samples (dropped frames, masked-out time) are bridged by linear interpolation for
the filters and restored to NaN afterwards (CONTRACTS section 6).

Polarity convention: every pulse signal produced by this package is positive for an increase in blood
volume, which is the *negated* skin intensity (`VOLUME_SIGN`). `intensity_to_volume` applies it.
"""
from __future__ import annotations

from collections.abc import Iterator

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
from scipy.signal import butter, sosfiltfilt

VOLUME_SIGN = -1.0  # pulse = VOLUME_SIGN * intensity: more blood absorbs more light


# --------------------------------------------------------------------------- NaN handling
def bridge_nans(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Linearly bridge interior NaN gaps and hold the nearest finite value at the ends.

    Returns (bridged copy as float64, mask of the samples that were NaN). An all-NaN input becomes
    zeros with an all-True mask so every downstream filter stays finite. Section 6.3 preprocessing
    (drops stay visible: `restore_nans` puts the NaNs back after filtering).
    """
    x = np.asarray(x, dtype=float)
    mask = ~np.isfinite(x)
    if not mask.any():
        return x.copy(), mask
    out = x.copy()
    if mask.all():
        out[:] = 0.0
        return out, mask
    idx = np.arange(x.size)
    out[mask] = np.interp(idx[mask], idx[~mask], x[~mask])
    return out, mask


def restore_nans(x: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Put NaN back at the positions of `mask` (the second output of `bridge_nans`)."""
    out = np.array(x, dtype=float, copy=True)
    out[np.asarray(mask, dtype=bool)] = np.nan
    return out


def intensity_to_volume(x: np.ndarray) -> np.ndarray:
    """Apply the polarity convention: blood-volume pulse = `VOLUME_SIGN` * intensity (CONTRACTS section 6)."""
    return VOLUME_SIGN * np.asarray(x, dtype=float)


# --------------------------------------------------------------------------- detrending
def detrend_smoothness_prior(x: np.ndarray, lam: float) -> np.ndarray:
    """Smoothness-prior detrending (Tarvainen et al. 2002), sparse solve, NaN-safe by bridging.

    With z the signal (T samples), D2 the (T-2) x T second-difference operator and lambda the
    regularisation parameter, the trend is the solution of the regularised least-squares problem
    min ||z - z_trend||^2 + lambda^2 ||D2 z_trend||^2, i.e.

        z_trend = (I + lambda^2 D2^T D2)^-1 z,   z_stat = z - z_trend.

    The operator acts as a high-pass with amplitude response
    H(w) = 16 lambda^2 sin^4(w/2) / (1 + 16 lambda^2 sin^4(w/2)) (w in rad/sample): the gain is 1/2 at
    f = fs / (2 pi sqrt(lambda)) and 1/sqrt(2) (half power) at about 1.25 x that frequency, so `lam`
    scales with the sampling rate; the pilot value is `pulse.detrend_lambda` in the config. The sparse
    system is pentadiagonal and solved with a sparse LU. Returns the stationary part with the input's
    NaNs restored. Protocol section 6.3 (detrend with a smoothness prior).
    """
    z, mask = bridge_nans(x)
    n = z.size
    if n < 3:
        return restore_nans(z - np.nanmean(z) if n else z, mask)
    lam = float(lam)
    d2 = sp.diags([np.ones(n - 2), -2.0 * np.ones(n - 2), np.ones(n - 2)], [0, 1, 2], shape=(n - 2, n), format="csc")
    a = sp.identity(n, format="csc") + (lam**2) * (d2.T @ d2)
    trend = spla.splu(a.tocsc()).solve(z)
    return restore_nans(z - trend, mask)


# --------------------------------------------------------------------------- filtering
def bandpass_sos(fs: float, lo: float, hi: float, order: int = 4) -> np.ndarray:
    """Second-order sections of a Butterworth band-pass [lo, hi] Hz at `fs`; `hi` is capped below Nyquist."""
    nyq = 0.5 * float(fs)
    lo = float(lo)
    hi = min(float(hi), 0.98 * nyq)
    if not (0.0 < lo < hi < nyq):
        raise ValueError(f"band [{lo}, {hi}] Hz is not inside (0, {nyq}) Hz")
    return butter(int(order), [lo / nyq, hi / nyq], btype="bandpass", output="sos")


def bandpass(x: np.ndarray, fs: float, lo: float, hi: float, order: int = 4, zero_phase: bool = True) -> np.ndarray:
    """Zero-phase Butterworth band-pass (order `order`, forward-backward on second-order sections).

    The band [lo, hi] in Hz comes from the config (`pulse.band_rate` 0.5-4 Hz for rate and rhythm,
    `pulse.band_morph` 0.4-8 Hz for morphology). NaNs are bridged for the filter and restored; the
    mean is removed first so edge transients stay small. Short inputs are padded to the filter's
    minimum length. Protocol section 6.3. Units: those of `x`.
    """
    z, mask = bridge_nans(x)
    if z.size == 0:
        return z
    sos = bandpass_sos(fs, lo, hi, order)
    z = z - z.mean()
    if zero_phase:
        padlen = 3 * (2 * sos.shape[0] + 1)
        if z.size <= padlen:
            pad = padlen - z.size + 1
            zz = np.concatenate([np.full(pad, z[0]), z, np.full(pad, z[-1])])
            y = sosfiltfilt(sos, zz)[pad:pad + z.size]
        else:
            y = sosfiltfilt(sos, z)
    else:
        from scipy.signal import sosfilt

        y = sosfilt(sos, z)
    return restore_nans(y, mask)


def zscore(x: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    """(x - mean) / std over the finite samples; NaNs are kept; a constant signal maps to zeros."""
    x = np.asarray(x, dtype=float)
    ok = np.isfinite(x)
    if ok.sum() == 0:
        return x.copy()
    mu = float(np.mean(x[ok]))
    sd = float(np.std(x[ok]))
    out = np.full_like(x, np.nan)
    out[ok] = (x[ok] - mu) / sd if sd > eps else 0.0
    return out


def preprocess(x: np.ndarray, fs: float, band: tuple[float, float], lam: float | None, order: int = 4) -> np.ndarray:
    """Detrend (smoothness prior, skipped when `lam` is None) -> band-pass -> z-score, NaNs restored.

    This is the "common preprocessing" of protocol section 6.3 applied to one trace or pulse signal.
    """
    y = detrend_smoothness_prior(x, lam) if lam is not None else np.asarray(x, dtype=float)
    y = bandpass(y, fs, band[0], band[1], order=order)
    return zscore(y)


# --------------------------------------------------------------------------- windows
def window_iter(x: np.ndarray, fs: float, win_s: float, step_s: float) -> Iterator[tuple[int, int, np.ndarray]]:
    """Yield (start_idx, stop_idx, segment) sliding windows of `win_s` seconds every `step_s` seconds.

    Windows are taken along the first axis. A signal shorter than one window yields itself once. The
    window and step lengths are protocol quantities (`pulse.window_s`, `pulse.step_s`) and are passed in
    by the caller. Section 6.3 (per-window SQI).
    """
    x = np.asarray(x)
    n = x.shape[0]
    win = max(int(round(float(win_s) * float(fs))), 1)
    step = max(int(round(float(step_s) * float(fs))), 1)
    if n <= win:
        yield 0, n, x
        return
    for start in range(0, n - win + 1, step):
        yield start, start + win, x[start:start + win]


def hann_window(n: int) -> np.ndarray:
    """Periodic Hann window of length n used by the overlap-add methods (CHROM); sums to one at 50 % overlap."""
    return 0.5 - 0.5 * np.cos(2.0 * np.pi * np.arange(n) / n)
