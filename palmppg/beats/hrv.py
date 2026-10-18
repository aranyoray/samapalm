"""Heart-rate variability of the palm pulse from foot-to-foot IBIs (protocol section 6.5, "HRV set").

`hrv_features(ibi_s)` computes, on the valid intervals (finite and inside cfg `beats.ibi_bounds_s`):
sdnn_ms, rmssd_ms, pnn50 (percent), sampen (m = 2, r = 0.2 SD, nats), ibi_hist_entropy (Shannon entropy
in bits of the IBI histogram with `IBI_HIST_BIN_MS` = 8 ms bins), sd1_ms, sd2_ms, sd1_sd2_ratio (Poincare),
tpr (turning-point ratio), n_ibi, n_beats, mean_ibi_ms, mean_hr_bpm and hr_cv (SD / mean of 60 / IBI).
Successive-difference statistics (RMSSD, pNN50, SD1, TPR) use only pairs of intervals that are adjacent in
the input, so a NaN (invalid or gated-out) interval breaks the chain instead of bridging it.
"""
from __future__ import annotations

import math

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

MS_PER_S = 1000.0
S_PER_MIN = 60.0
# Feature-definition constants (part of the feature names, not study thresholds): the 50 ms of pNN50, the
# 8 ms histogram bin of the IBI-histogram entropy, the sample-entropy dimension, tolerance fraction and
# minimum series length.
PNN_THRESHOLD_MS = 50.0
IBI_HIST_BIN_MS = 8.0
SAMPEN_DIMENSION = 2
SAMPEN_R_FRAC = 0.2
SAMPEN_MIN_N = 10
SAMPEN_MAX_N = 5000

HRV_KEYS = ("sdnn_ms", "rmssd_ms", "pnn50", "sampen", "ibi_hist_entropy", "sd1_ms", "sd2_ms", "sd1_sd2_ratio", "tpr",
            "n_ibi", "n_beats", "mean_ibi_ms", "median_ibi_ms", "mean_hr_bpm", "hr_cv")
HRV_UNITS = {"sdnn_ms": "ms", "rmssd_ms": "ms", "pnn50": "%", "sampen": "nats", "ibi_hist_entropy": "bit",
             "sd1_ms": "ms", "sd2_ms": "ms", "sd1_sd2_ratio": "ratio", "tpr": "ratio", "n_ibi": "count",
             "n_beats": "count", "mean_ibi_ms": "ms", "median_ibi_ms": "ms", "mean_hr_bpm": "bpm", "hr_cv": "ratio"}


def sample_entropy(x, m: int = SAMPEN_DIMENSION, r: float | None = None, r_frac: float = SAMPEN_R_FRAC) -> float:
    """SampEn(m, r) = -ln(A / B) (Richman and Moorman 2000); r defaults to `r_frac` x SD (ddof = 1).

    B counts template pairs of length m within Chebyshev distance r (self-matches excluded) among the
    first N - m templates, A the same for length m + 1. NaN for fewer than `SAMPEN_MIN_N` values, a
    (numerically) constant series, or no matches. Units: nats.
    """
    v = np.asarray(x, dtype=np.float64)
    v = v[np.isfinite(v)]
    n = v.size
    if n < max(SAMPEN_MIN_N, m + 2):
        return float("nan")
    if n > SAMPEN_MAX_N:
        v = v[:SAMPEN_MAX_N]
        n = v.size
    if r is None:
        r = float(r_frac) * float(np.std(v, ddof=1))
    if not (r > 1e-9 * float(np.max(np.abs(v)))):
        return float("nan")
    n_templates = n - m

    def count(dim: int) -> int:
        templ = sliding_window_view(v, dim)[:n_templates]
        total = 0
        for s in range(0, n_templates, 512):
            block = templ[s:s + 512]
            d = np.abs(block[:, None, :] - templ[None, :, :]).max(axis=2)
            total += int((d <= r).sum())
        return total - n_templates

    b = count(m)
    a = count(m + 1)
    if a <= 0 or b <= 0:
        return float("nan")
    return float(-math.log(a / b))


def ibi_histogram_entropy(ibi_ms, bin_ms: float = IBI_HIST_BIN_MS) -> float:
    """Shannon entropy (bits) of the IBI histogram with `bin_ms` bins aligned at multiples of `bin_ms`."""
    v = np.asarray(ibi_ms, dtype=float)
    v = v[np.isfinite(v)]
    if v.size < 2:
        return float("nan")
    lo = math.floor(v.min() / bin_ms) * bin_ms
    hi = math.ceil(v.max() / bin_ms) * bin_ms
    edges = np.arange(lo, hi + bin_ms, bin_ms) if hi > lo else np.array([lo, lo + bin_ms])
    counts, _ = np.histogram(v, bins=edges)
    p = counts[counts > 0] / v.size
    return float(-np.sum(p * np.log2(p)))


def turning_point_ratio(x, adjacent=None, rel_tol: float = 1e-9) -> float:
    """Fraction of interior points that are local extrema (2/3 expected for an i.i.d. sequence).

    `adjacent` (bool, len n - 1) marks which consecutive pairs are truly adjacent; a triplet is only counted
    when both of its pairs are. Differences below `rel_tol` x max |x| are ties, not turning points.
    """
    v = np.asarray(x, dtype=np.float64)
    n = v.size
    if n < 3:
        return float("nan")
    adj = np.ones(n - 1, dtype=bool) if adjacent is None else np.asarray(adjacent, dtype=bool)
    ok = adj[:-1] & adj[1:] & np.isfinite(v[:-2]) & np.isfinite(v[1:-1]) & np.isfinite(v[2:])
    if not ok.any():
        return float("nan")
    tol = float(rel_tol) * float(np.nanmax(np.abs(v)))
    a, b, c = v[:-2], v[1:-1], v[2:]
    tp = ((b > a + tol) & (b > c + tol)) | ((b < a - tol) & (b < c - tol))
    return float(np.mean(tp[ok]))


def poincare_sd(ibi_ms, succ_diff_ms) -> tuple[float, float]:
    """Poincare SD1 (short axis) and SD2 (long axis) in ms; NaN with fewer than three intervals."""
    ibi = np.asarray(ibi_ms, dtype=float)
    d = np.asarray(succ_diff_ms, dtype=float)
    if ibi.size < 3 or d.size < 2:
        return float("nan"), float("nan")
    sdsd2 = float(np.var(d, ddof=1))
    sdnn2 = float(np.var(ibi, ddof=1))
    sd1 = math.sqrt(0.5 * sdsd2)
    sd2sq = 2.0 * sdnn2 - 0.5 * sdsd2
    if sd2sq < -1e-9 * max(sdnn2, 1.0):
        return sd1, float("nan")
    return sd1, math.sqrt(max(sd2sq, 0.0))


def hrv_features(ibi_s, ibi_bounds: tuple[float, float] | None = None) -> dict:
    """HRV set of protocol section 6.5 from a sequence of foot-to-foot intervals in seconds.

    Intervals that are NaN or outside `ibi_bounds` (cfg `beats.ibi_bounds_s`) are invalid: they are left out
    of every statistic and break the successive-difference chain. Returns a dict with `HRV_KEYS`
    (units in `HRV_UNITS`); NaN where a statistic is undefined, counts as ints.
    """
    v = np.asarray(ibi_s, dtype=float)
    valid = np.isfinite(v)
    if ibi_bounds is not None:
        valid &= (v >= float(ibi_bounds[0])) & (v <= float(ibi_bounds[1]))
    ibi_ms = np.where(valid, v, np.nan) * MS_PER_S
    good = ibi_ms[valid]
    nan = float("nan")
    out: dict = dict.fromkeys(HRV_KEYS, nan)
    out["n_ibi"] = int(good.size)
    out["n_beats"] = int(good.size + 1) if good.size else 0
    if good.size == 0:
        return out
    adjacent = valid[:-1] & valid[1:]
    succ = np.diff(ibi_ms)[adjacent]
    out["mean_ibi_ms"] = float(np.mean(good))
    out["median_ibi_ms"] = float(np.median(good))
    hr = S_PER_MIN * MS_PER_S / good
    out["mean_hr_bpm"] = float(S_PER_MIN / (np.mean(good) / MS_PER_S))
    if good.size >= 2:
        out["sdnn_ms"] = float(np.std(good, ddof=1))
        out["hr_cv"] = float(np.std(hr, ddof=1) / np.mean(hr))
        out["ibi_hist_entropy"] = ibi_histogram_entropy(good)
    if succ.size >= 1:
        out["rmssd_ms"] = float(np.sqrt(np.mean(succ**2)))
        out["pnn50"] = float(100.0 * np.mean(np.abs(succ) > PNN_THRESHOLD_MS))
    sd1, sd2 = poincare_sd(good, succ)
    out["sd1_ms"], out["sd2_ms"] = sd1, sd2
    out["sd1_sd2_ratio"] = (sd1 / sd2) if (np.isfinite(sd1) and np.isfinite(sd2) and sd2 > 0) else nan
    out["sampen"] = sample_entropy(good)
    out["tpr"] = turning_point_ratio(ibi_ms, adjacent)
    return out
