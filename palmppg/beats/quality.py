"""Per-beat quality index in [0, 1] (protocol section 6.5, "per-beat quality index").

`beat_quality(beats_df, x, fs, template)` scores every beat from three components:
  q_template   Pearson correlation of the beat with the clip's ensemble template (negative -> 0);
  q_ibi        plausibility of the beat's own intervals against the local median of its neighbours'
               intervals (free below `IBI_DEV_FREE`, zero at `IBI_DEV_FULL` relative deviation);
  q_amplitude  consistency of the beat amplitude with the clip median amplitude (same shape of map).
`quality` is the geometric mean of the available components, zero for a beat that straddles a NaN gap.
cfg `beats.quality_min` gates the beats that enter the ensemble morphology, the APG and the HRV set
(`quality_summary` reports how many passed).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from palmppg.beats._signal import bridge_nans

# Algorithm constants (not protocol quantities): the relative IBI deviation that is free of penalty and
# the one that zeroes the IBI component; the same pair for the amplitude component; the number of
# neighbouring intervals on each side used for the local median.
IBI_DEV_FREE = 0.10
IBI_DEV_FULL = 0.50
AMP_DEV_FREE = 0.20
AMP_DEV_FULL = 1.00
IBI_NEIGHBOURS = 4

QUALITY_COLUMNS = ("q_template", "q_ibi", "q_amplitude", "quality")


def _ramp_down(dev: np.ndarray, free: float, full: float) -> np.ndarray:
    """1 below `free`, 0 above `full`, linear in between; NaN deviations give NaN."""
    out = 1.0 - np.clip((dev - free) / (full - free), 0.0, 1.0)
    return np.where(np.isfinite(dev), out, np.nan)


def template_correlation(z, peaks, template, pre: int) -> np.ndarray:
    """Pearson correlation of z around each peak (window of the template, `pre` samples before the peak)
    with the zero-mean template; NaN where the window leaves the array."""
    z = np.asarray(z, dtype=float)
    t = np.asarray(template, dtype=float)
    t = t - t.mean()
    tn = float(np.sqrt(np.sum(t**2)))
    out = np.full(len(peaks), np.nan)
    if tn == 0 or t.size == 0:
        return out
    for k, p in enumerate(np.asarray(peaks, dtype=int)):
        lo, hi = p - int(pre), p - int(pre) + t.size
        if lo < 0 or hi > z.size:
            continue
        seg = z[lo:hi] - z[lo:hi].mean()
        sn = float(np.sqrt(np.sum(seg**2)))
        out[k] = float(np.sum(seg * t) / (sn * tn)) if sn > 0 else 0.0
    return out


def ibi_plausibility(foot_t) -> np.ndarray:
    """Relative deviation of each beat's adjacent intervals from the local median of up to
    `IBI_NEIGHBOURS` intervals on each side (own intervals excluded); the larger of the two deviations.
    NaN when a beat has no neighbours to compare with."""
    f = np.asarray(foot_t, dtype=float)
    n = f.size
    ibi = np.diff(f)
    dev = np.full(n, np.nan)
    for k in range(n):
        own = [i for i in (k - 1, k) if 0 <= i < ibi.size]
        lo, hi = max(k - 1 - IBI_NEIGHBOURS, 0), min(k + IBI_NEIGHBOURS, ibi.size)
        ref = [ibi[i] for i in range(lo, hi) if i not in own and np.isfinite(ibi[i])]
        if not ref or not own:
            continue
        med = float(np.median(ref))
        if med <= 0:
            continue
        dev[k] = max(abs(ibi[i] / med - 1.0) for i in own)
    return dev


def beat_quality(beats_df: pd.DataFrame, x, fs: float, template=None, pre: int | None = None, t0: float | None = None) -> pd.DataFrame:
    """Quality components and the combined `quality` in [0, 1] per beat (index aligned with `beats_df`).

    `template` and `pre` default to `beats_df.attrs` (set by `segmentation.detect_beats`); without a
    template the correlation component is left out. `t0` (reference time of sample 0) also defaults to the
    attrs. Beats flagged `gap` score 0. Section 6.5 (per-beat quality index).
    """
    z, _ = bridge_nans(x)
    attrs = getattr(beats_df, "attrs", {}) or {}
    if template is None:
        template = attrs.get("template")
    if pre is None:
        pre = attrs.get("pre")
    if t0 is None:
        t0 = float(attrs.get("t0", 0.0))
    n = len(beats_df)
    peaks = beats_df["peak_idx"].to_numpy(dtype=int) if n else np.zeros(0, dtype=int)
    q_t = template_correlation(z, peaks, template, int(pre)) if (template is not None and pre is not None and n) else np.full(n, np.nan)
    q_t = np.where(np.isfinite(q_t), np.clip(q_t, 0.0, 1.0), np.nan)
    dev_ibi = ibi_plausibility(beats_df["foot_t"].to_numpy(dtype=float)) if n else np.zeros(0)
    q_i = _ramp_down(dev_ibi, IBI_DEV_FREE, IBI_DEV_FULL)
    amp = beats_df["amplitude"].to_numpy(dtype=float) if n else np.zeros(0)
    pos = amp[np.isfinite(amp) & (amp > 0)]
    med = float(np.median(pos)) if pos.size else float("nan")
    dev_amp = np.abs(amp / med - 1.0) if np.isfinite(med) and med > 0 else np.full(n, np.nan)
    q_a = _ramp_down(dev_amp, AMP_DEV_FREE, AMP_DEV_FULL)
    comps = np.column_stack([q_t, q_i, q_a]) if n else np.zeros((0, 3))
    quality = np.full(n, np.nan)
    for k in range(n):
        c = comps[k][np.isfinite(comps[k])]
        quality[k] = float(np.exp(np.mean(np.log(np.maximum(c, 1e-12))))) if c.size else 1.0
        if c.size and np.any(c <= 0):
            quality[k] = 0.0
    if n and "gap" in beats_df:
        quality[beats_df["gap"].to_numpy(dtype=bool)] = 0.0
    out = pd.DataFrame({"q_template": q_t, "q_ibi": q_i, "q_amplitude": q_a, "quality": np.clip(quality, 0.0, 1.0)},
                       index=beats_df.index)
    return out


def quality_summary(quality, quality_min: float) -> dict:
    """{n_beats, n_good, good_fraction, quality_median, quality_mean, quality_min_cfg} for cfg `beats.quality_min`."""
    q = np.asarray(quality, dtype=float)
    q = q[np.isfinite(q)]
    n = int(q.size)
    good = int(np.sum(q >= float(quality_min))) if n else 0
    return {"n_beats": n, "n_good": good, "good_fraction": (good / n) if n else float("nan"),
            "quality_median": float(np.median(q)) if n else float("nan"),
            "quality_mean": float(np.mean(q)) if n else float("nan"), "quality_min_cfg": float(quality_min)}
