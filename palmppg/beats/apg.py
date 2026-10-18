"""Acceleration plethysmogram of the ensemble beat (protocol section 6.5, "APG a, b, c, d, e waves and ageing index").

`ensemble_beat` averages the quality-gated beats aligned at their feet (unit height, fine grid); `apg_waves`
takes its second derivative (Savitzky-Golay) and locates the waves: a = largest maximum of the second
derivative on the upstroke, b = deepest minimum after a (around the systolic peak), e = maximum of the
second derivative at the dicrotic notch (the local maximum nearest the ensemble notch time when known,
else the largest local maximum after b), c and d = the largest maximum and the following minimum between
b and e (absent, i.e. NaN, when the b-e limb is monotonic). Outputs: amplitudes (1 / s^2 for a unit-height
beat), times after the foot (s), the ratios b/a, c/a, d/a, e/a and Takazawa's ageing index
(b - c - d - e) / a, in which an absent c or d contributes no deflection (0).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from palmppg.beats._signal import ANALYSIS_FS, bridge_nans, derivative, local_extrema, resample_segment

# Algorithm constants (not protocol quantities): the smoothing span of the second derivative, the part
# of the beat searched for waves, and the tolerance for matching the e wave to the notch time.
APG_SMOOTH_S = 0.06
APG_SEARCH_FRAC = 0.8
E_NOTCH_TOLERANCE_S = 0.08

APG_WAVES = ("a", "b", "c", "d", "e")
APG_KEYS = tuple(APG_WAVES) + tuple(f"t_{w}_s" for w in APG_WAVES) + ("b_a", "c_a", "d_a", "e_a", "ageing_index", "n_waves", "n_beats")


def ensemble_beat(beats_df: pd.DataFrame, x, fs: float, quality=None, quality_min: float = 0.0,
                  t0: float | None = None, fs_fine: float = ANALYSIS_FS, normalise: bool = True) -> dict:
    """Foot-aligned average of the quality-gated beats: {"tau_s", "beat", "n_beats", "fs"}.

    Each beat runs from its foot over the median pulse width (shorter beats are held at their last value
    before the next foot so no upstroke of the following beat leaks in), referenced to its foot level and,
    when `normalise`, scaled to unit height. Empty arrays when fewer than one beat qualifies. Section 6.5.
    """
    z, _ = bridge_nans(x)
    if t0 is None:
        t0 = float((getattr(beats_df, "attrs", {}) or {}).get("t0", 0.0))
    n = len(beats_df)
    empty = {"tau_s": np.zeros(0), "beat": np.zeros(0), "n_beats": 0, "fs": float(fs_fine)}
    if n < 2:
        return empty
    foot = (beats_df["foot_t"].to_numpy(dtype=float) - t0) * fs
    nxt = np.append(foot[1:], np.nan)
    keep = np.isfinite(nxt) & (nxt > foot)
    if quality is not None:
        q = np.asarray(quality, dtype=float)
        keep &= np.isfinite(q) & (q >= float(quality_min))
    if not keep.any():
        return empty
    width = float(np.median((nxt - foot)[keep]))
    n_fine = int(np.floor(width * fs_fine / fs)) + 1
    acc = []
    for k in np.flatnonzero(keep):
        end = min(foot[k] + width, nxt[k] - 1.0)
        if end <= foot[k]:
            continue
        _, b = resample_segment(z, foot[k], end, fs, fs_fine)
        if b.size < 4:
            continue
        b = b - b[0]
        if normalise:
            h = float(b.max())
            if h <= 0:
                continue
            b = b / h
        if b.size < n_fine:
            b = np.concatenate([b, np.full(n_fine - b.size, b[-1])])
        acc.append(b[:n_fine])
    if not acc:
        return empty
    beat = np.mean(np.asarray(acc), axis=0)
    return {"tau_s": np.arange(n_fine) / float(fs_fine), "beat": beat, "n_beats": len(acc), "fs": float(fs_fine)}


def apg_waves(beat, fs_fine: float, notch_tau_s: float | None = None, smooth_s: float = APG_SMOOTH_S) -> dict:
    """a, b, c, d, e waves of the second derivative of one (ensemble) beat; see the module docstring.

    `beat` is the foot-aligned beat (unit height recommended) sampled at `fs_fine`; `notch_tau_s` is the
    ensemble notch time after the foot (median `notch_time_s`), used to place the e wave. Returns a dict
    with `APG_KEYS` (NaN for missing waves, `n_waves` found). Section 6.5.
    """
    nan = float("nan")
    out: dict = dict.fromkeys(APG_KEYS, nan)
    out["n_waves"] = 0
    b_arr = np.asarray(beat, dtype=float)
    if b_arr.size < 8:
        return out
    d2 = derivative(b_arr, fs_fine, 2, smooth_s)
    limit = max(int(APG_SEARCH_FRAC * b_arr.size), 4)
    ipk = int(np.argmax(b_arr[:limit]))
    maxima, minima = local_extrema(d2[:limit])
    found: dict[str, int] = {}
    up = [i for i in maxima if i <= ipk]
    found["a"] = max(up, key=lambda i: d2[i]) if up else int(np.argmax(d2[:ipk + 1]))
    after_a = np.arange(found["a"] + 1, limit)
    if after_a.size:
        found["b"] = int(found["a"] + 1 + np.argmin(d2[found["a"] + 1:limit]))
        later = [i for i in maxima if i > found["b"]]
        if later:
            if notch_tau_s is not None and np.isfinite(notch_tau_s):
                target = notch_tau_s * fs_fine
                near = min(later, key=lambda i: abs(i - target))
                found["e"] = near if abs(near - target) <= E_NOTCH_TOLERANCE_S * fs_fine else max(later, key=lambda i: d2[i])
            else:
                found["e"] = max(later, key=lambda i: d2[i])
            mid = [i for i in maxima if found["b"] < i < found["e"]]
            if mid:
                found["c"] = max(mid, key=lambda i: d2[i])
                dips = [i for i in minima if found["c"] < i < found["e"]]
                if dips:
                    found["d"] = min(dips)
    for w, i in found.items():
        out[w] = float(d2[i])
        out[f"t_{w}_s"] = float(i / fs_fine)
    out["n_waves"] = len(found)
    a = out["a"]
    if np.isfinite(a) and a > 0:
        for w in ("b", "c", "d", "e"):
            out[f"{w}_a"] = out[w] / a if np.isfinite(out[w]) else nan
        if np.isfinite(out["b"]) and np.isfinite(out["e"]):
            c = out["c"] if np.isfinite(out["c"]) else 0.0
            d = out["d"] if np.isfinite(out["d"]) else 0.0
            out["ageing_index"] = (out["b"] - c - d - out["e"]) / a
    return out


def ensemble_apg(beats_df: pd.DataFrame, x, fs: float, quality=None, quality_min: float = 0.0,
                 notch_tau_s: float | None = None, t0: float | None = None) -> dict:
    """`apg_waves` of the `ensemble_beat` of the quality-gated beats, plus `n_beats` used (section 6.5)."""
    eb = ensemble_beat(beats_df, x, fs, quality, quality_min, t0)
    out = apg_waves(eb["beat"], eb["fs"], notch_tau_s)
    out["n_beats"] = int(eb["n_beats"])
    return out
