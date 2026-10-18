"""Per-beat and ensemble pulse-wave morphology (protocol section 6.5, "morphology per beat and as ensemble").

Every beat is cubic-resampled from its foot to the next foot onto a fine grid (`ANALYSIS_FS`), referenced
to its foot level (b0) and measured:
  upstroke_time_s        foot -> systolic peak (s)
  systolic_width_50_s    width of the systolic wave at 50 % of its amplitude (s)
  diastolic_time_s       systolic peak -> next foot (s)
  dicrotic_notch_present / notch_time_s   from `segmentation.find_notch` (local minimum in the decay, else
                         the second-derivative zero crossing of the shoulder); notch time from the foot (s)
  reflection_index       (diastolic peak - b0) / (systolic peak - b0)
  augmentation_index_proxy  (P2 - P1) / pulse height, where P1 and P2 are the first two fourth-derivative
                         shoulders of the systolic phase (local maxima of the 4th derivative in concave
                         regions; the systolic peak is one of them). A proxy: the palm PPG is a volume
                         wave, not a pressure wave, and the shoulder search is derivative-based.
  systolic_area / diastolic_area / area_ratio   integrals of (b - b0) split at the notch, or at 1/3 of the
                         pulse width when no notch was found (signal units x s)
  pulse_width_s          foot -> next foot (s)
  rise_slope             largest first derivative of the upstroke (signal units / s)
  decay_tau_s            time constant of the exponential fit (log-linear) to the diastolic runoff from
                         `DECAY_FIT_OFFSET_S` after the dicrotic peak (the systolic peak without a notch)
                         to `DECAY_FIT_TAIL_GUARD_S` before the next foot, at most `DECAY_FIT_LEN_S` (s)
  amplitude              systolic peak - b0 (signal units)
`ensemble_morphology` gives the median across the quality-gated beats (cfg `beats.quality_min`) plus the
SD across those beats (`<name>_sd`) as a stability measure, the notch fraction and the beat counts.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from palmppg.beats._signal import ANALYSIS_FS, bridge_nans, derivative, local_extrema, resample_segment

# Algorithm constants (not protocol quantities): the decay-fit window (shared with the synthetic truth
# definition), the smoothing spans of the slope and fourth-derivative estimates, the minimum relative
# size of a fourth-derivative shoulder, the split fraction without a notch and the gate on the ensemble
# notch flag.
DECAY_FIT_OFFSET_S = 0.05
DECAY_FIT_LEN_S = 0.60
DECAY_FIT_TAIL_GUARD_S = 0.02
DECAY_FIT_MIN_S = 0.12
SLOPE_SMOOTH_S = 0.04
AIX_SMOOTH_S = 0.06
AIX_MIN_REL = 0.02
SPLIT_FRACTION = 1.0 / 3.0
NOTCH_PRESENT_FRACTION = 0.5

MORPH_KEYS = ("upstroke_time_s", "systolic_width_50_s", "diastolic_time_s", "dicrotic_notch_present", "notch_time_s",
              "reflection_index", "augmentation_index_proxy", "systolic_area", "diastolic_area", "area_ratio",
              "pulse_width_s", "rise_slope", "decay_tau_s", "amplitude")
MORPH_UNITS = {"upstroke_time_s": "s", "systolic_width_50_s": "s", "diastolic_time_s": "s", "dicrotic_notch_present": "bool",
               "notch_time_s": "s", "reflection_index": "ratio", "augmentation_index_proxy": "ratio",
               "systolic_area": "signal x s", "diastolic_area": "signal x s", "area_ratio": "ratio", "pulse_width_s": "s",
               "rise_slope": "signal / s", "decay_tau_s": "s", "amplitude": "signal"}
ENSEMBLE_EXTRA = ("notch_fraction", "n_beats_used", "n_beats_total")


def _crossing(tau, b, i, level) -> float:
    """Linear interpolation of the time at which b crosses `level` between samples i and i + 1."""
    y0, y1 = b[i], b[i + 1]
    if y1 == y0:
        return float(tau[i])
    return float(tau[i] + (level - y0) / (y1 - y0) * (tau[i + 1] - tau[i]))


def width_at_half(tau, b, ipk: int, b0: float) -> float:
    """Width (s) of the systolic wave at half of its amplitude around the peak sample `ipk`; NaN if the
    decay never comes back to the half level inside the beat."""
    level = b0 + 0.5 * (b[ipk] - b0)
    left = np.where(b[:ipk] < level)[0]
    t_left = _crossing(tau, b, int(left[-1]), level) if left.size else float(tau[0])
    right = np.where(b[ipk:] < level)[0]
    if not right.size:
        return float("nan")
    j = ipk + int(right[0])
    return _crossing(tau, b, j - 1, level) - t_left


def decay_time_constant(tau, y, start_tau: float, fs_fine: float) -> float:
    """Exponential time constant (s) from a log-linear fit of y (> 0) over the runoff window; NaN when the
    window is shorter than `DECAY_FIT_MIN_S`, holds non-positive values or does not decay."""
    i0 = int(np.searchsorted(tau, start_tau + DECAY_FIT_OFFSET_S))
    i1 = y.size - int(round(DECAY_FIT_TAIL_GUARD_S * fs_fine))
    i1 = min(i1, i0 + int(round(DECAY_FIT_LEN_S * fs_fine)))
    seg = y[i0:i1]
    if seg.size < max(5, int(round(DECAY_FIT_MIN_S * fs_fine))) or not np.all(seg > 0):
        return float("nan")
    slope = float(np.polyfit(tau[i0:i1], np.log(seg), 1)[0])
    return float(-1.0 / slope) if slope < 0 else float("nan")


def augmentation_index_proxy(tau, b, b0: float, height: float, split_tau: float, fs_fine: float) -> float:
    """(P2 - P1) / height from the first two fourth-derivative shoulders of the systolic phase [0, split].

    Shoulders are local maxima of the fourth derivative lying in a concave region (second derivative < 0)
    and at least `AIX_MIN_REL` of the largest such maximum; the systolic peak itself is one of them. NaN
    with fewer than two shoulders (no late-systolic wave separable from the main peak).
    """
    sel = tau <= split_tau
    n = int(sel.sum())
    if n < 8 or height <= 0:
        return float("nan")
    seg = b[:n]
    d2 = derivative(seg, fs_fine, 2, AIX_SMOOTH_S, polyorder=5)
    d4 = derivative(seg, fs_fine, 4, AIX_SMOOTH_S, polyorder=5)
    maxima, _ = local_extrema(d4)
    cand = [int(i) for i in maxima if d2[i] < 0 and d4[i] > 0]
    if len(cand) < 2:
        return float("nan")
    ref = max(float(d4[i]) for i in cand)
    cand = [i for i in cand if d4[i] >= AIX_MIN_REL * ref]
    if len(cand) < 2:
        return float("nan")
    p1, p2 = float(seg[cand[0]] - b0), float(seg[cand[1]] - b0)
    return (p2 - p1) / height


def _one_beat(z, fs, foot, peak, nxt, notch, dic, kind, med_width, fs_fine) -> dict:
    nan = float("nan")
    out: dict = dict.fromkeys(MORPH_KEYS, nan)
    out["dicrotic_notch_present"] = kind is not None
    has_next = bool(np.isfinite(nxt) and nxt > peak)
    end = nxt if has_next else (peak + med_width if np.isfinite(med_width) else nan)
    end = min(end, z.size - 1) if np.isfinite(end) else nan
    if not (np.isfinite(end) and foot < peak < end):
        return out
    tau, b = resample_segment(z, foot, end, fs, fs_fine)
    if b.size < 8:
        return out
    b0 = float(b[0])
    nominal = int(round((peak - foot) * fs_fine / fs))
    w = int(round(fs_fine / fs)) + 1
    lo, hi = max(nominal - w, 1), max(min(nominal + w + 1, b.size), 2)
    ipk = lo + int(np.argmax(b[lo:hi]))
    height = float(b[ipk] - b0)
    if height <= 0:
        return out
    out["amplitude"] = height
    out["upstroke_time_s"] = float(tau[ipk])
    d1 = derivative(b, fs_fine, 1, SLOPE_SMOOTH_S)
    out["rise_slope"] = float(np.max(d1[:ipk + 1]))
    out["systolic_width_50_s"] = width_at_half(tau, b, ipk, b0)
    split = None
    if kind is not None and np.isfinite(notch):
        tau_n = (notch - foot) / fs
        tau_d = (dic - foot) / fs if np.isfinite(dic) else tau_n
        out["notch_time_s"] = float(tau_n)
        out["reflection_index"] = float((np.interp(tau_d, tau, b) - b0) / height)
        split = float(tau_n)
    y = b - b0
    if has_next:
        width = (nxt - foot) / fs
        out["pulse_width_s"] = float(width)
        out["diastolic_time_s"] = float((nxt - peak) / fs)
        if split is None:
            split = float(width * SPLIT_FRACTION)
        i_split = int(np.clip(np.searchsorted(tau, split), 1, y.size - 1))
        total = float(np.trapezoid(y, tau))
        sys_area = float(np.trapezoid(y[:i_split + 1], tau[:i_split + 1]))
        out["systolic_area"], out["diastolic_area"] = sys_area, total - sys_area
        out["area_ratio"] = sys_area / (total - sys_area) if (total - sys_area) > 0 else nan
        start_tau = (dic - foot) / fs if (kind == "min" and np.isfinite(dic)) else float(tau[ipk])
        out["decay_tau_s"] = decay_time_constant(tau, y, start_tau, fs_fine)
    if split is None:
        split = float(tau[-1] * SPLIT_FRACTION)
    out["augmentation_index_proxy"] = augmentation_index_proxy(tau, b, b0, height, split, fs_fine)
    return out


def beat_morphology(beats_df: pd.DataFrame, x, fs: float, t0: float | None = None, fs_fine: float = ANALYSIS_FS) -> pd.DataFrame:
    """Per-beat morphology table (columns `MORPH_KEYS`, index aligned with `beats_df`) of the beats of
    `segmentation.detect_beats` on the signal `x` they were detected on (section 6.5).

    `t0` (reference time of x[0]) defaults to `beats_df.attrs["t0"]`. The last beat has no next foot, so its
    diastolic time, pulse width, areas and decay constant are NaN. Units are listed in `MORPH_UNITS`.
    """
    z, _ = bridge_nans(x)
    if t0 is None:
        t0 = float((getattr(beats_df, "attrs", {}) or {}).get("t0", 0.0))
    n = len(beats_df)
    if n == 0:
        return pd.DataFrame(columns=list(MORPH_KEYS), index=beats_df.index)
    pos = lambda col: (beats_df[col].to_numpy(dtype=float) - t0) * fs  # noqa: E731
    foot, peak, notch, dic = pos("foot_t"), pos("peak_t"), pos("notch_t"), pos("dicrotic_t")
    kinds = beats_df["notch_kind"].tolist() if "notch_kind" in beats_df else [None] * n
    nxt = np.append(foot[1:], np.nan)
    widths = nxt - foot
    med_width = float(np.nanmedian(widths)) if np.isfinite(widths).any() else float("nan")
    rows = [_one_beat(z, fs, foot[k], peak[k], nxt[k], notch[k], dic[k], kinds[k], med_width, fs_fine) for k in range(n)]
    out = pd.DataFrame(rows, columns=list(MORPH_KEYS), index=beats_df.index)
    out["dicrotic_notch_present"] = out["dicrotic_notch_present"].astype(bool)
    return out


def ensemble_morphology(per_beat: pd.DataFrame, quality=None, quality_min: float = 0.0) -> dict:
    """Median across the quality-gated beats (quality >= cfg `beats.quality_min`) of every morphology
    feature, its SD across those beats as `<name>_sd` (stability), `notch_fraction`, `dicrotic_notch_present`
    (notch fraction >= `NOTCH_PRESENT_FRACTION`), `n_beats_used` and `n_beats_total`. Section 6.5."""
    n = len(per_beat)
    keep = np.ones(n, dtype=bool)
    if quality is not None and n:
        q = np.asarray(quality, dtype=float)
        keep &= np.isfinite(q) & (q >= float(quality_min))
    sub = per_beat[keep]
    out: dict = {}
    for k in MORPH_KEYS:
        if k == "dicrotic_notch_present":
            frac = float(sub[k].astype(bool).mean()) if len(sub) else float("nan")
            out["notch_fraction"] = frac
            out[k] = bool(np.isfinite(frac) and frac >= NOTCH_PRESENT_FRACTION)
            continue
        v = sub[k].to_numpy(dtype=float) if len(sub) else np.zeros(0)
        v = v[np.isfinite(v)]
        out[k] = float(np.median(v)) if v.size else float("nan")
        out[f"{k}_sd"] = float(np.std(v, ddof=1)) if v.size >= 2 else float("nan")
    out["n_beats_used"] = int(len(sub))
    out["n_beats_total"] = int(n)
    return out
