"""Beat segmentation of the best-SQI morphology signal (protocol section 6.5).

`detect_beats(x_morph, fs, ibi_bounds)` finds systolic peaks by adaptive prominence and distance, feet by
the intersecting-tangents method (cfg `beats.foot_method`; "min" = preceding trough) and dicrotic notches
in the decay, then runs the per-clip matched-filter second pass of section 6.5: the ensemble-average beat
of the first pass is correlated with the signal (normalised cross-correlation), peaks are re-detected on
the correlation output, snapped to the nearest signal maximum, feet and notches re-derived, and the number
of beats that changed between the passes is reported in the result's `attrs`.

IBIs are foot to foot. The foot (start of the upstroke) is the sharpest, least shape-dependent fiducial of
a pulse wave: the systolic peak drifts with the reflected wave and with amplitude changes, and the foot is
also the fiducial that PAT pairs with the ECG R-peak (section 6.6), so one definition serves both. IBIs
outside `beats.ibi_bounds_s` are set to NaN (`ibi_valid` False). Positions inside the clip are sample
units of the input; times are `t0 + position / fs` in seconds on the reference clock.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.signal import correlate, find_peaks, savgol_filter

from palmppg.beats._signal import bridge_nans, interp_at, parabolic_refine, spectral_peak

FOOT_METHODS = ("intersecting_tangents", "min")

# Algorithm constants (not protocol quantities): the seed prominence of the first peak pass as a fraction
# of the signal SD, the adaptive prominence as a fraction of the median seed prominence, the minimum
# inter-peak distance as a fraction of the spectral period, the notch smoothing span and minimum depth
# (fraction of the beat amplitude), the fraction of the diastole searched for a notch, the minimum
# number of beats for a matched-filter template, the snap window from a correlation peak to the signal
# maximum, and the tolerance below which a peak counts as unchanged between the two passes.
SEED_PROMINENCE_SD = 0.3
ADAPTIVE_PROMINENCE_FRAC = 0.4
MIN_DISTANCE_PERIOD_FRAC = 0.6
NOTCH_SMOOTH_S = 0.10
NOTCH_MIN_DEPTH_FRAC = 0.02
NOTCH_SEARCH_FRAC = 0.8
MIN_TEMPLATE_BEATS = 5
SNAP_S = 0.08
CHANGE_TOL_SAMPLES = 1

BEAT_COLUMNS = ("peak_idx", "peak_t", "foot_idx", "foot_t", "notch_idx", "notch_t", "dicrotic_idx", "dicrotic_t",
                "notch_kind", "ibi_s", "ibi_valid", "amplitude", "gap")


# --------------------------------------------------------------------------- peaks
def adaptive_peaks(y, distance: int) -> np.ndarray:
    """Local maxima of y at least `distance` samples apart with an adaptive prominence threshold.

    A seed pass uses `SEED_PROMINENCE_SD` x SD(y); when it finds at least three peaks the threshold is
    re-set to `ADAPTIVE_PROMINENCE_FRAC` x the median seed prominence, so the threshold follows the
    clip's own pulse amplitude rather than its noise level. Section 6.5 (peaks on the best-SQI signal).
    """
    y = np.asarray(y, dtype=float)
    sd = float(np.std(y)) if y.size else 0.0
    if y.size < 3 or sd <= 0:
        return np.zeros(0, dtype=int)
    seed, props = find_peaks(y, distance=max(int(distance), 1), prominence=SEED_PROMINENCE_SD * sd)
    if seed.size < 3:
        return seed.astype(int)
    thr = ADAPTIVE_PROMINENCE_FRAC * float(np.median(props["prominences"]))
    peaks, _ = find_peaks(y, distance=max(int(distance), 1), prominence=thr)
    return peaks.astype(int)


def peak_distance(z, fs: float, ibi_bounds: tuple[float, float]) -> int:
    """Minimum inter-peak distance in samples: the shortest IBI allowed, raised to `MIN_DISTANCE_PERIOD_FRAC`
    of the dominant period inside the rate range implied by `ibi_bounds` so dicrotic waves are skipped."""
    lo_s, hi_s = float(ibi_bounds[0]), float(ibi_bounds[1])
    dist = int(round(lo_s * fs))
    f0, _ = spectral_peak(z, fs, (1.0 / hi_s, 1.0 / lo_s))
    if np.isfinite(f0) and f0 > 0:
        dist = max(dist, int(MIN_DISTANCE_PERIOD_FRAC * fs / f0))
    return max(dist, 1)


# --------------------------------------------------------------------------- feet and notches
def tangent_foot(z, start: int, peak: int, method: str = "intersecting_tangents") -> float:
    """Foot position (fractional sample) of the beat whose systolic peak is at `peak`.

    The search runs over z[start : peak + 1]. "min" returns the preceding trough (the minimum of the
    window). "intersecting_tangents" draws the tangent at the steepest point of the upstroke from that
    trough to the peak (the largest forward difference, placed at the mid-sample) and returns where it
    meets the horizontal line through the trough, clipped to [trough, peak]. Section 6.5 (feet).
    """
    if method not in FOOT_METHODS:
        raise ValueError(f"foot_method must be one of {FOOT_METHODS}, got {method!r}")
    z = np.asarray(z, dtype=float)
    start = int(max(start, 0))
    seg = z[start:peak + 1]
    if seg.size < 2:
        return float(peak)
    imin = int(np.argmin(seg))
    trough = start + imin
    if method == "min":
        return float(trough)
    up = seg[imin:]
    if up.size < 2:
        return float(trough)
    d = np.diff(up)
    k = int(np.argmax(d))
    slope = float(d[k])
    if slope <= 0:
        return float(trough)
    t_s, x_s = k + 0.5, 0.5 * (up[k] + up[k + 1])
    foot = t_s + (up[0] - x_s) / slope
    return float(trough + np.clip(foot, 0.0, up.size - 1))


def find_notch(z, fs: float, peak: int, end: int, amplitude: float) -> tuple[float, float, str | None]:
    """Dicrotic notch and dicrotic peak positions (fractional samples) in the decay z[peak : end + 1].

    First choice: a local minimum of the Savitzky-Golay-smoothed decay followed by a local maximum at
    least `NOTCH_MIN_DEPTH_FRAC` x `amplitude` higher (kind "min"). Otherwise the most pronounced shoulder:
    the local maximum of the first derivative in the decay where the slope is still negative, i.e. a
    zero crossing of the second derivative (kind "inflection"); there the dicrotic peak is the shoulder
    itself. Only the first `NOTCH_SEARCH_FRAC` of the diastole is searched. (nan, nan, None) when absent.
    Section 6.5 (dicrotic notch presence and timing).
    """
    z = np.asarray(z, dtype=float)
    peak, end = int(peak), int(min(end, z.size - 1))
    n = end - peak
    if n < 4:
        return float("nan"), float("nan"), None
    seg = z[peak:end + 1]
    win = max(int(round(NOTCH_SMOOTH_S * fs)), 5)
    win += 1 - (win % 2)
    if seg.size > win:
        s = savgol_filter(seg, win, 3)
        d1 = savgol_filter(seg, win, 3, deriv=1)
    else:
        s = seg
        d1 = np.gradient(seg)
    limit = max(int(NOTCH_SEARCH_FRAC * n), 2)
    for i in range(1, limit):
        if not (s[i - 1] > s[i] <= s[i + 1]):
            continue
        j = i + 1
        while j < s.size - 1 and not (s[j - 1] < s[j] >= s[j + 1]):
            j += 1
        if j < s.size - 1 and s[j] - s[i] >= NOTCH_MIN_DEPTH_FRAC * amplitude:
            return peak + parabolic_refine(s, i)[0], peak + parabolic_refine(s, j)[0], "min"
    best, best_val = None, -np.inf
    for i in range(1, limit):
        if d1[i - 1] < d1[i] >= d1[i + 1] and d1[i] < 0 and d1[i] > best_val:
            best, best_val = i, float(d1[i])
    if best is None:
        return float("nan"), float("nan"), None
    pos = peak + parabolic_refine(d1, best)[0]
    return pos, pos, "inflection"


# --------------------------------------------------------------------------- template and matched filter
def ensemble_template(z, mask, peaks, feet, ibi_samples: float) -> tuple[np.ndarray, int] | None:
    """Ensemble-average beat around the systolic peaks: (zero-mean template, samples before the peak).

    The window holds the median foot-to-peak rise (plus one sample) before the peak and the rest of the
    median IBI after it; beats touching a NaN gap or the array ends are left out. None with fewer than
    `MIN_TEMPLATE_BEATS` usable beats. Section 6.5 (per-clip matched filter).
    """
    z = np.asarray(z, dtype=float)
    peaks = np.asarray(peaks, dtype=int)
    feet = np.asarray(feet, dtype=float)
    if peaks.size < MIN_TEMPLATE_BEATS or not np.isfinite(ibi_samples) or ibi_samples < 3:
        return None
    pre = int(np.ceil(np.median(peaks - feet))) + 1
    post = int(round(ibi_samples)) - pre
    if post < 2:
        post = max(2, int(round(0.5 * ibi_samples)))
    segs = [z[p - pre:p + post] for p in peaks
            if p - pre >= 0 and p + post <= z.size and not mask[p - pre:p + post].any()]
    if len(segs) < MIN_TEMPLATE_BEATS:
        return None
    template = np.mean(np.asarray(segs), axis=0)
    template = template - template.mean()
    if not np.any(template != 0):
        return None
    return template, pre


def matched_filter_output(z, template, pre: int) -> np.ndarray:
    """Normalised cross-correlation of z with the template, aligned so that index i scores a beat whose
    systolic peak sits at z[i]; values in [-1, 1] (local energy normalisation makes the prominence
    threshold amplitude-independent)."""
    z = np.asarray(z, dtype=float)
    t = np.asarray(template, dtype=float)
    n, m = z.size, t.size
    if n == 0 or m == 0:
        return np.zeros(n)
    full = correlate(z, t, mode="full")
    start = m - 1 - int(pre)
    c = np.zeros(n)
    lo, hi = max(start, 0), min(start + n, full.size)
    c[lo - start:lo - start + (hi - lo)] = full[lo:hi]
    energy = np.convolve(z**2, np.ones(m), mode="full")
    e = np.zeros(n)
    e[lo - start:lo - start + (hi - lo)] = energy[lo:hi]
    norm = np.sqrt(np.maximum(e, 0.0)) * float(np.sqrt(np.sum(t**2)))
    with np.errstate(invalid="ignore", divide="ignore"):
        out = np.where(norm > 0, c / norm, 0.0)
    return out


def snap_to_maximum(z, peaks, snap: int) -> np.ndarray:
    """Move each index to the largest sample of z within +/- `snap` samples (duplicates removed, sorted)."""
    z = np.asarray(z, dtype=float)
    out = []
    for p in np.asarray(peaks, dtype=int):
        lo, hi = max(p - snap, 0), min(p + snap + 1, z.size)
        if hi > lo:
            out.append(lo + int(np.argmax(z[lo:hi])))
    return np.unique(np.asarray(out, dtype=int))


def count_changes(first, second, tol: int = CHANGE_TOL_SAMPLES) -> dict:
    """{n_first, n_second, n_added, n_removed, n_moved, n_changed}: second-pass peaks without a first-pass
    peak within `tol` samples are added, first-pass peaks without a second-pass match removed, matched
    pairs that are not identical moved; n_changed = added + removed + moved."""
    a = np.sort(np.asarray(first, dtype=int))
    b = np.sort(np.asarray(second, dtype=int))
    used = np.zeros(a.size, dtype=bool)
    added = moved = 0
    for p in b:
        if a.size:
            j = int(np.argmin(np.abs(a - p)))
            if abs(int(a[j]) - int(p)) <= tol and not used[j]:
                used[j] = True
                moved += int(a[j] != p)
                continue
        added += 1
    removed = int((~used).sum())
    return {"n_first": int(a.size), "n_second": int(b.size), "n_added": int(added), "n_removed": removed,
            "n_moved": int(moved), "n_changed": int(added + removed + moved)}


# --------------------------------------------------------------------------- assembly
def _median_ibi_samples(peaks: np.ndarray, fs: float, ibi_bounds: tuple[float, float]) -> float:
    if peaks.size < 2:
        return float("nan")
    d = np.diff(peaks)
    ok = (d >= ibi_bounds[0] * fs) & (d <= ibi_bounds[1] * fs)
    return float(np.median(d[ok])) if ok.any() else float(np.median(d))


def assemble_beats(z, mask, fs: float, peaks, ibi_bounds: tuple[float, float], foot_method: str, t0: float = 0.0) -> pd.DataFrame:
    """Feet, notches, amplitudes and foot-to-foot IBIs for the given systolic peak indices.

    Columns: peak_idx, peak_t (parabolic sub-sample), foot_idx (floor), foot_t, notch_idx / notch_t and
    dicrotic_idx / dicrotic_t (nullable), notch_kind ("min" | "inflection" | None), ibi_s (foot to foot,
    NaN outside `ibi_bounds` and for the last beat), ibi_valid, amplitude (peak minus foot level, signal
    units) and gap (True when a NaN gap lies between this foot and the next). Section 6.5.
    """
    z = np.asarray(z, dtype=float)
    mask = np.asarray(mask, dtype=bool)
    peaks = np.unique(np.asarray(peaks, dtype=int))
    n = peaks.size
    max_ibi = int(round(ibi_bounds[1] * fs))
    med_ibi = _median_ibi_samples(peaks, fs, ibi_bounds)
    feet = np.zeros(n)
    for k, p in enumerate(peaks):
        start = int(peaks[k - 1]) if k > 0 else int(p - max_ibi)
        feet[k] = tangent_foot(z, max(start, p - max_ibi, 0), int(p), foot_method)
    rows = []
    for k, p in enumerate(peaks):
        peak_pos, _ = parabolic_refine(z, int(p))
        amp = float(z[p] - interp_at(z, feet[k]))
        if k + 1 < n:
            end = int(np.floor(feet[k + 1]))
        else:
            end = int(min(z.size - 1, p + (med_ibi if np.isfinite(med_ibi) else max_ibi)))
        notch, dic, kind = find_notch(z, fs, int(p), end, amp)
        gap = bool(mask[int(np.floor(feet[k])):end + 1].any())
        ibi_raw = (feet[k + 1] - feet[k]) / fs if k + 1 < n else float("nan")
        valid = bool(np.isfinite(ibi_raw) and ibi_bounds[0] <= ibi_raw <= ibi_bounds[1])
        rows.append({
            "peak_idx": int(p), "peak_t": t0 + peak_pos / fs,
            "foot_idx": int(np.floor(feet[k])), "foot_t": t0 + feet[k] / fs,
            "notch_idx": int(round(notch)) if np.isfinite(notch) else None, "notch_t": t0 + notch / fs,
            "dicrotic_idx": int(round(dic)) if np.isfinite(dic) else None, "dicrotic_t": t0 + dic / fs,
            "notch_kind": kind, "ibi_s": ibi_raw if valid else float("nan"), "ibi_valid": valid,
            "amplitude": amp, "gap": gap,
        })
    df = pd.DataFrame(rows, columns=list(BEAT_COLUMNS))
    df["notch_idx"] = df["notch_idx"].astype("Int64")
    df["dicrotic_idx"] = df["dicrotic_idx"].astype("Int64")
    df["notch_kind"] = df["notch_kind"].astype(object).where(df["notch_kind"].notna(), None)
    return df


def detect_beats(x_morph, fs: float, ibi_bounds: tuple[float, float], foot_method: str = "intersecting_tangents",
                 matched_filter: bool = True, t0: float = 0.0) -> pd.DataFrame:
    """Beat table of a morphology-band pulse signal in volume polarity (protocol section 6.5).

    `ibi_bounds` is cfg `beats.ibi_bounds_s` (s), `foot_method` cfg `beats.foot_method`, `matched_filter`
    cfg `beats.matched_filter`. First pass: adaptive peaks (`adaptive_peaks`, `peak_distance`), feet
    (`tangent_foot`), notches (`find_notch`). Second pass (when enabled and at least `MIN_TEMPLATE_BEATS`
    beats exist): ensemble template -> normalised cross-correlation -> peaks re-detected on it, snapped to
    the signal maximum within `SNAP_S`, feet and notches re-derived. Returns the table of `assemble_beats`
    whose `.attrs` hold fs, t0, foot_method, the template (list) and `pre`, `matched_filter` (bool, applied)
    and `changes` (`count_changes`). Times are `t0` + position / fs on the reference clock. NaN samples are
    bridged for detection and reported through `gap`.
    """
    if foot_method not in FOOT_METHODS:
        raise ValueError(f"foot_method must be one of {FOOT_METHODS}, got {foot_method!r}")
    lo, hi = float(ibi_bounds[0]), float(ibi_bounds[1])
    if not (0 < lo < hi):
        raise ValueError(f"ibi_bounds must satisfy 0 < lo < hi, got {ibi_bounds}")
    z, mask = bridge_nans(x_morph)
    attrs = {"fs": float(fs), "t0": float(t0), "foot_method": foot_method, "ibi_bounds_s": [lo, hi],
             "template": None, "pre": None, "matched_filter": False, "changes": None}
    if z.size < 3 or mask.all():
        df = assemble_beats(z, mask, fs, np.zeros(0, dtype=int), (lo, hi), foot_method, t0)
        df.attrs.update(attrs)
        return df
    dist = peak_distance(z, fs, (lo, hi))
    first = adaptive_peaks(z, dist)
    first = first[~mask[first]] if first.size else first
    beats = assemble_beats(z, mask, fs, first, (lo, hi), foot_method, t0)
    peaks = first
    if matched_filter:
        feet = (beats["foot_t"].to_numpy(dtype=float) - t0) * fs
        tmpl = ensemble_template(z, mask, first, feet, _median_ibi_samples(first, fs, (lo, hi)))
        if tmpl is not None:
            template, pre = tmpl
            ncc = matched_filter_output(z, template, pre)
            second = adaptive_peaks(ncc, dist)
            second = snap_to_maximum(z, second, max(int(round(SNAP_S * fs)), 1))
            second = second[~mask[second]] if second.size else second
            attrs["changes"] = count_changes(first, second)
            attrs.update({"template": template.tolist(), "pre": int(pre), "matched_filter": True})
            if second.size:
                peaks = second
                beats = assemble_beats(z, mask, fs, second, (lo, hi), foot_method, t0)
    attrs["n_peaks"] = int(peaks.size)
    beats.attrs.update(attrs)
    return beats
