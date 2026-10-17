"""Signal quality indices for pulse signals (protocol section 6.3, feeding 6.1 `valid_clip` and E2).

Primary: `snr_band_sqi`, de Haan's spectral SNR (de Haan & Jeanne 2013, section III.E): per window the
power inside +/- `peak_halfwidth_hz` of the dominant peak in the rate band and of its first harmonic,
versus the remaining power in the band, in dB; the clip value is the median over windows. The dB value
is mapped to [0, 1] with a logistic centred at 0 dB with a 4 dB scale (`sqi_from_db`), so the frozen
`sqi.threshold` in `frozen_config.yaml` lives on that scale (CONTRACTS section 6).
Secondary (Elgendi 2016, "Optimal signal quality index for photoplethysmogram signals"): the template
correlation of beats with their ensemble average, and the skewness and kurtosis of the signal.

Spectral helpers (`periodogram`, `spectral_peak`, `band_snr_db`) are shared with `classical` and `rate`.
"""
from __future__ import annotations

import numpy as np
from scipy.signal import find_peaks
from scipy.stats import kurtosis, skew

from palmppg.pulse.preprocess import bridge_nans, hann_window, window_iter

SQI_CENTRE_DB = 0.0   # logistic centre of the dB -> [0, 1] map (CONTRACTS section 6)
SQI_SCALE_DB = 4.0    # logistic scale
PEAK_HALFWIDTH_HZ = 0.1  # de Haan's +/- 0.1 Hz around the peak and its harmonic


# --------------------------------------------------------------------------- spectra
def periodogram(x: np.ndarray, fs: float, nfft: int | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Hann-windowed, mean-removed, zero-padded one-sided power spectrum (f in Hz, power in x^2 units).

    `nfft` defaults to the first power of two at or above 8 x len(x) (and at least 4096) so peak
    positions are interpolated finely; NaNs are bridged first.
    """
    z, _ = bridge_nans(x)
    n = z.size
    if n == 0:
        return np.zeros(0), np.zeros(0)
    z = z - z.mean()
    if nfft is None:
        nfft = int(2 ** np.ceil(np.log2(max(8 * n, 4096))))
    w = hann_window(n)
    spec = np.fft.rfft(z * w, n=nfft)
    f = np.fft.rfftfreq(nfft, d=1.0 / float(fs))
    pxx = (np.abs(spec) ** 2) / max(float(np.sum(w**2)), 1e-12)
    return f, pxx


def spectral_peak(x: np.ndarray, fs: float, band: tuple[float, float], nfft: int | None = None) -> tuple[float, float]:
    """(f_peak_hz, peak_power) of the strongest periodogram bin inside `band`, parabolic sub-bin refinement.

    Returns (nan, 0) when the band holds no bins or the signal has no power. Section 6.3 / E1 (pulse
    rate from the spectral peak).
    """
    f, pxx = periodogram(x, fs, nfft)
    sel = np.where((f >= band[0]) & (f <= band[1]))[0]
    if sel.size == 0 or not np.any(pxx[sel] > 0):
        return float("nan"), 0.0
    k = sel[int(np.argmax(pxx[sel]))]
    fpk = float(f[k])
    if 0 < k < f.size - 1:
        y0, y1, y2 = pxx[k - 1], pxx[k], pxx[k + 1]
        den = y0 - 2.0 * y1 + y2
        if den < 0:
            delta = 0.5 * (y0 - y2) / den
            fpk = float(f[k] + delta * (f[1] - f[0]))
    return fpk, float(pxx[k])


def band_snr_db(
    x: np.ndarray, fs: float, band: tuple[float, float], peak_halfwidth_hz: float = PEAK_HALFWIDTH_HZ,
    nfft: int | None = None,
) -> tuple[float, float]:
    """de Haan's SNR in dB of one window: (snr_db, f_peak_hz).

    SNR = 10 log10( sum of power within +/- `peak_halfwidth_hz` of the dominant peak f0 and of 2 f0,
    both clipped to `band` / power of the rest of the band ). A window without a peak returns (nan, nan).
    """
    f, pxx = periodogram(x, fs, nfft)
    inband = (f >= band[0]) & (f <= band[1])
    if not inband.any() or not np.any(pxx[inband] > 0):
        return float("nan"), float("nan")
    f0, _ = spectral_peak(x, fs, band, nfft)
    sig = inband & ((np.abs(f - f0) <= peak_halfwidth_hz) | (np.abs(f - 2.0 * f0) <= peak_halfwidth_hz))
    s_pow = float(np.sum(pxx[sig]))
    n_pow = float(np.sum(pxx[inband & ~sig]))
    if n_pow <= 0:
        return float("inf"), f0
    return float(10.0 * np.log10(max(s_pow, 1e-300) / n_pow)), f0


# --------------------------------------------------------------------------- logistic map
def sqi_from_db(snr_db, centre_db: float = SQI_CENTRE_DB, scale_db: float = SQI_SCALE_DB):
    """Logistic map dB -> [0, 1]: sqi = 1 / (1 + exp(-(snr_db - centre) / scale)); 0 dB -> 0.5, +4 dB -> 0.73.

    NaN stays NaN. The frozen `sqi.threshold` is expressed on this scale.
    """
    v = np.asarray(snr_db, dtype=float)
    with np.errstate(over="ignore", invalid="ignore"):
        out = 1.0 / (1.0 + np.exp(-(v - centre_db) / scale_db))
    return float(out) if out.ndim == 0 else out


def db_from_sqi(sqi, centre_db: float = SQI_CENTRE_DB, scale_db: float = SQI_SCALE_DB):
    """Inverse of `sqi_from_db` (clipped away from 0 and 1)."""
    p = np.clip(np.asarray(sqi, dtype=float), 1e-9, 1 - 1e-9)
    out = centre_db + scale_db * np.log(p / (1.0 - p))
    return float(out) if out.ndim == 0 else out


# --------------------------------------------------------------------------- secondary SQIs
def detect_beats(x: np.ndarray, fs: float, band: tuple[float, float], ibi_bounds_s: tuple[float, float] = (0.33, 2.0),
                 prominence_frac: float = 0.3) -> np.ndarray:
    """Systolic peak indices of a pulse signal in volume polarity.

    The minimum peak distance is 60 % of the period of the spectral peak in `band` (so dicrotic waves are
    skipped) and never below the shortest IBI in `ibi_bounds_s`; the prominence threshold is
    `prominence_frac` x the signal SD. Section 6.3 (rate from beat intervals) and 6.5.
    """
    z, mask = bridge_nans(x)
    if z.size < 3 or mask.all():
        return np.zeros(0, dtype=int)
    f0, _ = spectral_peak(z, fs, band)
    dist = int(ibi_bounds_s[0] * fs)
    if np.isfinite(f0) and f0 > 0:
        dist = max(dist, int(0.6 * fs / f0))
    sd = float(np.std(z))
    peaks, _ = find_peaks(z, distance=max(dist, 1), prominence=prominence_frac * sd if sd > 0 else None)
    return peaks[~mask[peaks]] if peaks.size else peaks


def template_correlation_sqi(x: np.ndarray, fs: float, band: tuple[float, float],
                             ibi_bounds_s: tuple[float, float] = (0.33, 2.0)) -> float:
    """Mean Pearson correlation of each beat with the ensemble-average beat (Orphanidou 2015, Elgendi 2016).

    Beats are cut at the detected systolic peaks with a fixed length of the median inter-peak interval,
    centred so the peak sits at 1/3 of the segment. Fewer than three beats returns NaN. Unitless in [-1, 1].
    """
    z, mask = bridge_nans(x)
    peaks = detect_beats(z, fs, band, ibi_bounds_s)
    if peaks.size < 3:
        return float("nan")
    seg = int(np.median(np.diff(peaks)))
    pre = seg // 3
    post = seg - pre
    beats = []
    for p in peaks:
        if p - pre < 0 or p + post > z.size or mask[max(p - pre, 0):p + post].any():
            continue
        beats.append(z[p - pre:p + post])
    if len(beats) < 3:
        return float("nan")
    b = np.asarray(beats)
    template = b.mean(axis=0)
    tc = template - template.mean()
    if np.sqrt(np.sum(tc**2)) == 0:
        return float("nan")
    cors = []
    for beat in b:
        bc = beat - beat.mean()
        den = np.sqrt(np.sum(bc**2) * np.sum(tc**2))
        cors.append(float(np.sum(bc * tc) / den) if den > 0 else 0.0)
    return float(np.mean(cors))


def skewness_kurtosis_sqi(x: np.ndarray) -> tuple[float, float]:
    """(skewness, excess kurtosis) of the finite samples (Elgendi 2016 S_SQI and K_SQI); NaN when too short."""
    v = np.asarray(x, dtype=float)
    v = v[np.isfinite(v)]
    if v.size < 4 or np.std(v) == 0:
        return float("nan"), float("nan")
    return float(skew(v)), float(kurtosis(v))


# --------------------------------------------------------------------------- primary SQI
def snr_band_sqi(
    x: np.ndarray, fs: float, band: tuple[float, float], window_s: float, step_s: float,
    peak_halfwidth_hz: float = PEAK_HALFWIDTH_HZ, centre_db: float = SQI_CENTRE_DB, scale_db: float = SQI_SCALE_DB,
    min_finite_frac: float = 0.8, ibi_bounds_s: tuple[float, float] = (0.33, 2.0),
) -> dict:
    """Clip-level SQI of one pulse signal (protocol section 6.3; `sqi_best` of the QC table, section 6.1).

    Per sliding window (`window_s`, `step_s` from `pulse.window_s` / `pulse.step_s`) with at least
    `min_finite_frac` finite samples: de Haan's SNR in dB (`band_snr_db`) and the peak rate in bpm. Clip
    values are medians over windows. Returns
    {"sqi": logistic(snr_db) in [0, 1], "snr_db", "hr_bpm", "n_windows", "template_corr", "skewness",
    "kurtosis", "snr_db_windows": [...], "hr_bpm_windows": [...], "window_start_s": [...]}.
    A signal without a usable window gives sqi 0, snr_db -inf and hr NaN.
    """
    x = np.asarray(x, dtype=float)
    snrs, hrs, starts = [], [], []
    for i0, i1, seg in window_iter(x, fs, window_s, step_s):
        finite = np.isfinite(seg)
        if finite.mean() < min_finite_frac or finite.sum() < 8:
            continue
        snr_db, f0 = band_snr_db(seg, fs, band, peak_halfwidth_hz)
        if not np.isfinite(f0):
            continue
        snrs.append(snr_db)
        hrs.append(60.0 * f0)
        starts.append(i0 / float(fs))
    if snrs:
        snr_med = float(np.median(snrs))
        hr_med = float(np.median(hrs))
        sqi = float(sqi_from_db(snr_med, centre_db, scale_db))
    else:
        snr_med, hr_med, sqi = float("-inf"), float("nan"), 0.0
    sk, ku = skewness_kurtosis_sqi(x)
    return {
        "sqi": sqi, "snr_db": snr_med, "hr_bpm": hr_med, "n_windows": len(snrs),
        "template_corr": template_correlation_sqi(x, fs, band, ibi_bounds_s), "skewness": sk, "kurtosis": ku,
        "snr_db_windows": [float(v) for v in snrs], "hr_bpm_windows": [float(v) for v in hrs],
        "window_start_s": [float(v) for v in starts],
    }
