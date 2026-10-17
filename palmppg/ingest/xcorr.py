"""Heart-rate cross-correlation check of the ECG anchor (protocol section 4.3, refinement step).

"Cross-correlate the ECG instantaneous heart-rate series (R-peaks, resampled to 4 Hz) with the PPG
instantaneous rate series over a lag window of +/- 3 s around the coarse anchor. Accept when the
normalised correlation peak is at least 0.6 and exceeds the second-best peak by 0.15. The lag includes
mean pulse arrival time, so it checks the fine anchor to within about 0.3 s but does not replace it."

Sign convention: ``lag_s > 0`` means the PPG rate series lags the ECG series (pulse after R-peak), i.e.
``ppg(t) ~ ecg(t - lag)``.
"""
from __future__ import annotations

import numpy as np

from palmppg.core.timeline import resample_to_grid, uniform_grid

DEFAULTS = {
    "sync.xcorr.second_peak_exclusion_s": 0.5,   # second-best peak searched outside +/- this of the best
    "sync.xcorr.min_overlap_s": 10.0,            # shortest overlap for a meaningful correlation
    "sync.xcorr.max_gap_s": 2.0,                 # beat gaps longer than this leave NaN in the rate series
}


def rate_series_from_events(event_times_s, fs: float, t_grid=None, max_gap_s: float | None = None):
    """Instantaneous rate (bpm) from beat times, on a uniform grid at ``fs`` (``sync.xcorr.rate_fs``).

    Each interval gives ``60 / ibi`` placed at the interval midpoint, linearly interpolated to the grid;
    NaN outside the beats and inside gaps longer than ``max_gap_s``. Returns ``(t_grid, rate_bpm)``;
    ``t_grid`` spans the beats when not given. Times are in whatever clock the beats are in. Section 4.3.
    """
    max_gap_s = DEFAULTS["sync.xcorr.max_gap_s"] if max_gap_s is None else float(max_gap_s)
    t = np.sort(np.asarray(event_times_s, dtype=float))
    t = t[np.isfinite(t)]
    if t.size < 2:
        grid = np.asarray(t_grid, dtype=float) if t_grid is not None else np.zeros(0)
        return grid, np.full(grid.size, np.nan)
    ibi = np.diff(t)
    ok = ibi > 0
    mid = 0.5 * (t[:-1] + t[1:])[ok]
    rate = 60.0 / ibi[ok]
    grid = np.asarray(t_grid, dtype=float) if t_grid is not None else uniform_grid(float(mid[0]), float(mid[-1]), fs)
    if mid.size < 2:
        return grid, np.full(grid.size, np.nan)
    return grid, resample_to_grid(mid, rate, grid, max_gap_s=max_gap_s)


def _pearson(a: np.ndarray, b: np.ndarray) -> float:
    m = np.isfinite(a) & np.isfinite(b)
    if m.sum() < 3:
        return np.nan
    a, b = a[m] - a[m].mean(), b[m] - b[m].mean()
    den = np.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / den) if den > 0 else np.nan


def xcorr_lag(ecg_rate, ppg_rate, fs: float, max_lag_s: float, min_peak: float, min_margin: float,
              second_peak_exclusion_s: float | None = None, min_overlap_s: float | None = None) -> dict:
    """Normalised cross-correlation of two rate series on the same grid; best lag and acceptance (section 4.3).

    For each integer lag within +/- ``max_lag_s`` the Pearson correlation of the overlapping finite samples
    is computed (``corr(ecg(t), ppg(t + lag))``); the best lag is refined by a parabola through the three
    samples around the peak. The second-best peak is the highest correlation outside +/-
    ``second_peak_exclusion_s`` of the best. ``accepted`` = peak >= min_peak and peak - second >= min_margin
    (``sync.xcorr.min_peak``/``min_margin``). Returns ``{lag_s, peak, second_peak, margin, accepted, lags_s,
    corr, n_overlap, reason}``.
    """
    excl = DEFAULTS["sync.xcorr.second_peak_exclusion_s"] if second_peak_exclusion_s is None else float(second_peak_exclusion_s)
    min_overlap_s = DEFAULTS["sync.xcorr.min_overlap_s"] if min_overlap_s is None else float(min_overlap_s)
    a = np.asarray(ecg_rate, dtype=float)
    b = np.asarray(ppg_rate, dtype=float)
    if a.shape != b.shape:
        raise ValueError(f"rate series must share a grid: {a.shape} vs {b.shape}")
    n = a.size
    K = round(max_lag_s * fs)
    lags = np.arange(-K, K + 1)
    corr = np.full(lags.size, np.nan)
    n_ov = np.zeros(lags.size, dtype=int)
    for j, k in enumerate(lags):
        if k >= 0:
            x, y = a[: n - k], b[k:]
        else:
            x, y = a[-k:], b[: n + k]
        n_ov[j] = int((np.isfinite(x) & np.isfinite(y)).sum())
        corr[j] = _pearson(x, y)
    base = {"lags_s": (lags / fs).tolist(), "corr": corr.tolist(), "fs": float(fs), "max_lag_s": float(max_lag_s),
            "min_peak": float(min_peak), "min_margin": float(min_margin), "second_peak_exclusion_s": excl}
    valid = np.isfinite(corr) & (n_ov >= round(min_overlap_s * fs))
    if not valid.any():
        return {**base, "lag_s": None, "peak": None, "second_peak": None, "margin": None, "accepted": False,
                "n_overlap": int(n_ov.max()) if n_ov.size else 0, "reason": "insufficient overlap"}
    cw = np.where(valid, corr, -np.inf)
    j = int(np.argmax(cw))
    peak = float(corr[j])
    lag = float(lags[j] / fs)
    if 0 < j < lags.size - 1 and valid[j - 1] and valid[j + 1]:
        y0, y1, y2 = corr[j - 1], corr[j], corr[j + 1]
        den = y0 - 2 * y1 + y2
        if den < 0:
            delta = 0.5 * (y0 - y2) / den
            lag = float((lags[j] + np.clip(delta, -1, 1)) / fs)
    outside = valid & (np.abs(lags - lags[j]) > round(excl * fs))
    second = float(corr[outside].max()) if outside.any() else float("-inf")
    margin = peak - second if np.isfinite(second) else float("inf")
    accepted = bool(peak >= min_peak and margin >= min_margin)
    reasons = []
    if peak < min_peak:
        reasons.append(f"peak {peak:.2f} < {min_peak:.2f}")
    if margin < min_margin:
        reasons.append(f"margin {margin:.2f} < {min_margin:.2f}")
    return {**base, "lag_s": lag, "peak": peak, "second_peak": None if not np.isfinite(second) else second,
            "margin": None if not np.isfinite(margin) else float(margin), "accepted": accepted,
            "n_overlap": int(n_ov[j]), "reason": "; ".join(reasons) if reasons else "accepted"}


def agree_with_fine(lag_s: float | None, agree_s: float) -> bool:
    """True when the residual lag after the fine map is within ``sync.xcorr.agree_s`` (section 4.4: fine
    grade needs the cross-correlation to agree within 0.3 s). The lag includes mean pulse arrival time,
    so this is a plausibility check of the anchor, not a refinement of it."""
    if lag_s is None or not np.isfinite(lag_s):
        return False
    return bool(abs(float(lag_s)) <= float(agree_s))
