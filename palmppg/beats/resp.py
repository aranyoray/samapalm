"""Respiratory proxy of the palm pulse (protocol section 6.5, "respiratory proxy (0.1 to 0.5 Hz modulation)").

Two modulation series are formed and resampled to `RESP_SERIES_FS` on the reference clock:
  (a) amplitude modulation: the per-beat amplitude at the beat feet (preferred) or, without beats, the
      Hilbert envelope of the pulse signal smoothed over `ENVELOPE_SMOOTH_S`;
  (b) the IBI series at the interval midpoints (respiratory sinus arrhythmia).
Each series is linearly detrended and its spectral peak inside cfg `beats.resp_band` gives a rate in
breaths per minute; `resp_power_ratio` is the fraction of the series' power (above DC) inside the band.
`resp_rate_bpm` / `resp_power_ratio` are taken from the series with the larger power ratio.
"""
from __future__ import annotations

import numpy as np
from scipy.signal import hilbert

from palmppg.beats._signal import band_power_ratio, bridge_nans, spectral_peak

RESP_SERIES_FS = 4.0      # sampling rate of the modulation series (algorithm constant; Nyquist 2 Hz > 0.5 Hz)
ENVELOPE_SMOOTH_S = 0.5   # box smoothing of the Hilbert envelope
MIN_POINTS = 6            # fewest beats / intervals that give a usable series
S_PER_MIN = 60.0

RESP_KEYS = ("resp_rate_bpm", "resp_power_ratio", "resp_rate_am_bpm", "resp_power_ratio_am", "resp_rate_ibi_bpm",
             "resp_power_ratio_ibi", "resp_rate_agreement_bpm", "resp_source", "resp_n_am", "resp_n_ibi")


def modulation_rate(t_s, values, band: tuple[float, float], series_fs: float = RESP_SERIES_FS) -> dict:
    """{rate_bpm, power_ratio, f_peak_hz, n} of an irregularly sampled modulation series.

    The series is interpolated onto a uniform grid at `series_fs`, linearly detrended, and its periodogram
    peak inside `band` (Hz) is converted to breaths per minute; `power_ratio` = in-band power / power above DC.
    NaN with fewer than `MIN_POINTS` points or a span shorter than two periods of the band's low edge.
    """
    t = np.asarray(t_s, dtype=float)
    v = np.asarray(values, dtype=float)
    ok = np.isfinite(t) & np.isfinite(v)
    t, v = t[ok], v[ok]
    nan = float("nan")
    out = {"rate_bpm": nan, "power_ratio": nan, "f_peak_hz": nan, "n": int(t.size)}
    if t.size < MIN_POINTS:
        return out
    order = np.argsort(t)
    t, v = t[order], v[order]
    span = t[-1] - t[0]
    if span < 2.0 / float(band[0]):
        return out
    grid = t[0] + np.arange(int(np.floor(span * series_fs)) + 1) / series_fs
    y = np.interp(grid, t, v)
    y = y - np.polyval(np.polyfit(grid - grid[0], y, 1), grid - grid[0])
    f0, _ = spectral_peak(y, series_fs, band)
    out["f_peak_hz"] = float(f0)
    out["rate_bpm"] = float(S_PER_MIN * f0) if np.isfinite(f0) else nan
    out["power_ratio"] = band_power_ratio(y, series_fs, band)
    return out


def envelope_series(x, fs: float, t0: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
    """(t, envelope) Hilbert amplitude envelope of a pulse signal, box-smoothed over `ENVELOPE_SMOOTH_S`."""
    z, mask = bridge_nans(x)
    if z.size < 4:
        return np.zeros(0), np.zeros(0)
    env = np.abs(hilbert(z - z.mean()))
    w = max(int(round(ENVELOPE_SMOOTH_S * fs)), 1)
    env = np.convolve(env, np.ones(w) / w, mode="same")
    env[mask] = np.nan
    return t0 + np.arange(z.size) / float(fs), env


def respiratory_proxy(x, fs: float, band: tuple[float, float], foot_t=None, amplitude=None, ibi_s=None,
                      t0: float = 0.0, series_fs: float = RESP_SERIES_FS) -> dict:
    """Respiratory rate and modulation strength from (a) the amplitude modulation and (b) the IBI series.

    `x` is the pulse signal (volume polarity) sampled at `fs` starting at `t0`; `foot_t` (s, reference
    clock), `amplitude` (per beat) and `ibi_s` (interval after each foot, NaN when invalid) come from the
    beat table; without them the amplitude modulation is the Hilbert envelope of `x` and the IBI estimate
    is NaN. `band` is cfg `beats.resp_band` in Hz. Returns a dict with `RESP_KEYS` (rates in breaths per
    minute, ratios in 0..1, `resp_source` "am" | "ibi" | None). Section 6.5.
    """
    nan = float("nan")
    out: dict = dict.fromkeys(RESP_KEYS, nan)
    out["resp_source"] = None
    if foot_t is not None and amplitude is not None and np.isfinite(np.asarray(amplitude, dtype=float)).sum() >= MIN_POINTS:
        am = modulation_rate(foot_t, amplitude, band, series_fs)
    else:
        t_env, env = envelope_series(x, fs, t0)
        am = modulation_rate(t_env, env, band, series_fs)
    out["resp_rate_am_bpm"], out["resp_power_ratio_am"], out["resp_n_am"] = am["rate_bpm"], am["power_ratio"], am["n"]
    ib = {"rate_bpm": nan, "power_ratio": nan, "n": 0}
    if foot_t is not None and ibi_s is not None:
        f = np.asarray(foot_t, dtype=float)
        ibi = np.asarray(ibi_s, dtype=float)
        if f.size == ibi.size and f.size:
            ib = modulation_rate(f + 0.5 * ibi, ibi, band, series_fs)
    out["resp_rate_ibi_bpm"], out["resp_power_ratio_ibi"], out["resp_n_ibi"] = ib["rate_bpm"], ib["power_ratio"], ib["n"]
    cands = [(am["power_ratio"], am["rate_bpm"], "am"), (ib["power_ratio"], ib["rate_bpm"], "ibi")]
    cands = [c for c in cands if np.isfinite(c[0]) and np.isfinite(c[1])]
    if cands:
        ratio, rate, src = max(cands, key=lambda c: c[0])
        out["resp_rate_bpm"], out["resp_power_ratio"], out["resp_source"] = rate, ratio, src
    if np.isfinite(am["rate_bpm"]) and np.isfinite(ib["rate_bpm"]):
        out["resp_rate_agreement_bpm"] = float(abs(am["rate_bpm"] - ib["rate_bpm"]))
    return out
