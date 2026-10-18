"""Perfusion index per ROI and channel from the raw ROI traces (protocol section 6.5, "perfusion index per ROI and channel").

PI (percent) = 100 x AC / DC on one `<roi>__<channel>__mean` column of traces.parquet (CONTRACTS section 4):
AC = 2 sqrt(2) x RMS of the band-passed trace (the peak-to-peak amplitude of a sinusoid with that RMS; the
band is cfg `pulse.band_rate`), DC = mean of the raw trace. The raw traces are required: the z-scored pulse
signals of pulse.parquet carry no DC level. Pi traces are Bayer-plane means (R, G1, G2, B, never
demosaiced), so Pi perfusion columns are `requires_raw`; phone and pi_proxy traces are R, G, B.
"""
from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from palmppg.beats._signal import bandpass

SEP = "__"
TRACE_STAT = "mean"
PI_CHANNELS: tuple[str, ...] = ("R", "G1", "G2", "B")
RGB_CHANNELS: tuple[str, ...] = ("R", "G", "B")
PERFUSION_STATS = ("pi_pct", "ac", "dc")
AC_FROM_RMS = 2.0 * np.sqrt(2.0)
MIN_SECONDS = 2.0   # the band-pass needs a few periods of the slowest band component (algorithm constant)


def trace_channels(columns: Sequence[str]) -> tuple[str, ...]:
    """Channel set of a traces.parquet column list: Pi Bayer planes when a G1 mean column exists, else RGB."""
    if any(c.endswith(f"{SEP}G1{SEP}{TRACE_STAT}") for c in columns):
        return PI_CHANNELS
    return RGB_CHANNELS


def trace_rois(columns: Sequence[str], channels: Sequence[str], order: Sequence[str] | None = None,
               exclude: Sequence[str] = ()) -> list[str]:
    """ROI names with a `<roi>__<ch>__mean` column for every channel, in `order` first, then the rest."""
    suffix = f"{SEP}{channels[0]}{SEP}{TRACE_STAT}"
    found = []
    for c in columns:
        if c.endswith(suffix):
            roi = c[: -len(suffix)]
            if roi not in exclude and all(f"{roi}{SEP}{ch}{SEP}{TRACE_STAT}" in columns for ch in channels):
                found.append(roi)
    first = [r for r in (order or []) if r in found]
    return first + [r for r in found if r not in first]


def perfusion_from_trace(x, fs: float, band: tuple[float, float]) -> dict:
    """{pi_pct, ac, dc, n} of one raw intensity trace (NaN = dropped or masked-out samples).

    DC = mean of the finite samples (trace units), AC = `AC_FROM_RMS` x RMS of the band-passed trace
    (NaNs bridged for the filter and ignored in the RMS), pi_pct = 100 AC / DC. NaN when fewer than
    `MIN_SECONDS` of finite samples exist or DC is not positive.
    """
    x = np.asarray(x, dtype=float)
    finite = np.isfinite(x)
    n = int(finite.sum())
    nan = float("nan")
    if n < int(MIN_SECONDS * fs) or n < 8:
        return {"pi_pct": nan, "ac": nan, "dc": nan, "n": n}
    dc = float(np.mean(x[finite]))
    y = bandpass(x, fs, band[0], band[1])
    y = y[np.isfinite(y)]
    ac = float(AC_FROM_RMS * np.sqrt(np.mean(y**2))) if y.size else nan
    pi = 100.0 * ac / dc if (np.isfinite(ac) and dc > 0) else nan
    return {"pi_pct": pi, "ac": ac, "dc": dc, "n": n}


def perfusion_index(traces_df: pd.DataFrame, roi: str, channel: str, band: tuple[float, float], fs: float,
                    valid_mask=None) -> dict:
    """Perfusion index of `<roi>__<channel>__mean` in traces.parquet over the samples of `valid_mask`
    (the timeline's analysis window; all samples when None). See `perfusion_from_trace`. Section 6.5."""
    col = f"{roi}{SEP}{channel}{SEP}{TRACE_STAT}"
    if col not in traces_df.columns:
        raise KeyError(f"traces have no column {col}")
    x = traces_df[col].to_numpy(dtype=float).copy()
    if valid_mask is not None:
        x[~np.asarray(valid_mask, dtype=bool)] = np.nan
    return perfusion_from_trace(x, fs, band)


def perfusion_table(traces_df: pd.DataFrame, band: tuple[float, float], fs: float, valid_mask=None,
                    rois: Sequence[str] | None = None, channels: Sequence[str] | None = None,
                    exclude: Sequence[str] = ()) -> dict:
    """{roi: {channel: {pi_pct, ac, dc, n}}} for every ROI (cfg `rois.names` order, `rois.excluded` left
    out) and every channel present in the traces (section 6.5)."""
    cols = list(traces_df.columns)
    chans = tuple(channels) if channels is not None else trace_channels(cols)
    roi_list = trace_rois(cols, chans, order=rois, exclude=exclude)
    return {roi: {ch: perfusion_index(traces_df, roi, ch, band, fs, valid_mask) for ch in chans} for roi in roi_list}
