"""ECG cleaning: zero-phase Butterworth band-pass plus an IIR mains notch (protocol section 6.4).

The band (`ecg.band`, 0.5 to 40 Hz) and the notch frequency (`ecg.notch_hz`, 50 Hz) come from the Config
object; nothing here hard-codes them. Filtering is zero-phase (forward-backward) so R-peak timing is not
shifted, which the fine anchor and the pulse-arrival analyses depend on. NaN gaps (a digitised strip with
missing columns) are bridged linearly for filtering and restored afterwards.
"""
from __future__ import annotations

import numpy as np
from scipy.signal import butter, filtfilt, iirnotch, sosfiltfilt

from palmppg.core.config import Config

NYQUIST_FRACTION = 0.45     # an upper band edge is capped below Nyquist so the filter stays stable
DEFAULT_ORDER = 4
DEFAULT_NOTCH_Q = 30.0


def _cfg(cfg: Config | None) -> Config:
    if cfg is None:
        from palmppg.core.config import load_pipeline_config

        cfg = load_pipeline_config()
    return cfg


def bridge_nan(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Linearly interpolate NaN runs (edges held at the nearest finite value). Returns (filled, nan_mask)."""
    x = np.asarray(x, dtype=np.float64)
    bad = ~np.isfinite(x)
    if not bad.any():
        return x.copy(), bad
    if bad.all():
        return np.zeros_like(x), bad
    idx = np.arange(x.size)
    filled = x.copy()
    filled[bad] = np.interp(idx[bad], idx[~bad], x[~bad])
    return filled, bad


def _padlen(n: int, default: int) -> int:
    return int(max(0, min(default, n - 1)))


def bandpass(x, fs: float, lo: float, hi: float, order: int = DEFAULT_ORDER) -> np.ndarray:
    """Zero-phase Butterworth band-pass (`sosfiltfilt`), `lo`/`hi` in Hz; `hi` is capped at 0.45 fs."""
    x = np.asarray(x, dtype=np.float64)
    hi_eff = min(float(hi), NYQUIST_FRACTION * float(fs))
    if not (0.0 < lo < hi_eff):
        raise ValueError(f"band must satisfy 0 < lo < hi < Nyquist, got lo={lo}, hi={hi}, fs={fs}")
    sos = butter(int(order), [float(lo), hi_eff], btype="bandpass", fs=float(fs), output="sos")
    default_pad = 3 * (2 * len(sos) + 1)
    pad = _padlen(x.size, default_pad)
    if x.size <= 2 * (order + 1):
        return x - np.mean(x)
    return sosfiltfilt(sos, x, padlen=pad)


def notch(x, fs: float, hz: float, q: float = DEFAULT_NOTCH_Q) -> np.ndarray:
    """Zero-phase IIR notch at `hz` (quality factor `q`); a notch at or above Nyquist is skipped."""
    x = np.asarray(x, dtype=np.float64)
    if hz is None or hz <= 0 or hz >= 0.5 * fs:
        return x.copy()
    b, a = iirnotch(float(hz), float(q), fs=float(fs))
    pad = _padlen(x.size, 3 * max(len(a), len(b)))
    if x.size <= 4:
        return x.copy()
    return filtfilt(b, a, x, padlen=pad)


def clean_ecg(x, fs: float, band: tuple[float, float] | None = None, notch_hz: float | None = None,
              cfg: Config | None = None, order: int = DEFAULT_ORDER, notch_q: float = DEFAULT_NOTCH_Q) -> np.ndarray:
    """Cleaned ECG in millivolts as float32 (protocol 6.4): median removed, zero-phase Butterworth band-pass
    `band` (default `ecg.band`), then an IIR notch at `notch_hz` (default `ecg.notch_hz`; pass 0 to skip).

    Input `x` is in millivolts at `fs` Hz; NaN samples are bridged for filtering and returned as NaN.
    """
    if band is None or notch_hz is None:
        c = _cfg(cfg)
        band = tuple(c.get("ecg.band")) if band is None else band
        notch_hz = float(c.get("ecg.notch_hz")) if notch_hz is None else notch_hz
    filled, bad = bridge_nan(x)
    if bad.all():
        return np.full(filled.shape, np.nan, dtype=np.float32)
    y = filled - np.median(filled[~bad])
    y = bandpass(y, fs, float(band[0]), float(band[1]), order=order)
    y = notch(y, fs, float(notch_hz), q=notch_q)
    y[bad] = np.nan
    return y.astype(np.float32)
