"""SNR-weighted multi-ROI fusion of pulse signals (protocol section 6.3 "SNR-weighted multi-ROI fusion").

Per-ROI signals are always kept alongside the fused one (`run.run_pulse` writes both). The weights are
proportional to the linear signal-to-noise power of each input, w_i = 10^(snr_db_i / 10) / sum_j (...),
so a ROI 10 dB cleaner than another gets ten times its weight. Inputs whose quality entry carries only an
SQI in [0, 1] use the odds sqi / (1 - sqi) instead, which is monotone in the SNR behind the logistic map.
"""
from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from palmppg.pulse.classical import align_polarity
from palmppg.pulse.preprocess import zscore


def weight_from_quality(entry) -> float:
    """Unnormalised fusion weight of one input: linear SNR power from `snr_db`, else SQI odds, else 0."""
    if isinstance(entry, Mapping):
        snr = entry.get("snr_db")
        if snr is not None and np.isfinite(snr):
            return float(10.0 ** (float(snr) / 10.0))
        entry = entry.get("sqi")
    if entry is None:
        return 0.0
    s = float(entry)
    if not np.isfinite(s) or s <= 0:
        return 0.0
    s = min(s, 1 - 1e-9)
    return float(s / (1.0 - s))


def snr_weighted_fusion(signals: Mapping[str, np.ndarray], sqis: Mapping[str, float | Mapping],
                        min_weight_frac: float = 0.0) -> tuple[np.ndarray, dict[str, float]]:
    """Fuse named pulse signals (each (T,), same grid) into one (T,) signal with SNR weights.

    `sqis[name]` is the `snr_band_sqi` dict (or a bare SQI). Each input is z-scored and its polarity is
    aligned to the highest-weight input before the weighted sum; inputs with a weight below
    `min_weight_frac` x the largest weight are dropped (weight 0). Samples where an input is NaN use the
    remaining inputs with re-normalised weights; a sample with no finite input is NaN. The fused signal
    is z-scored. Returns (fused, {name: normalised weight}) with the weights summing to one (all zero when
    nothing could be fused). Section 6.3.
    """
    names = [n for n in signals if n in sqis]
    if not names:
        raise ValueError("no signal has a quality entry")
    raw_w = {n: weight_from_quality(sqis[n]) for n in names}
    wmax = max(raw_w.values())
    if wmax <= 0:
        t = len(next(iter(signals.values())))
        return np.full(t, np.nan), {n: 0.0 for n in names}
    w = {n: (v if v >= min_weight_frac * wmax else 0.0) for n, v in raw_w.items()}
    tot = sum(w.values())
    w = {n: v / tot for n, v in w.items()}
    ref_name = max(w, key=w.get)
    ref = zscore(np.asarray(signals[ref_name], dtype=float))
    t = ref.size
    num = np.zeros(t)
    den = np.zeros(t)
    for n in names:
        if w[n] <= 0:
            continue
        s = zscore(np.asarray(signals[n], dtype=float))
        if s.size != t:
            raise ValueError(f"signal {n} has {s.size} samples, expected {t}")
        s, _ = align_polarity(s, ref)
        ok = np.isfinite(s)
        num[ok] += w[n] * s[ok]
        den[ok] += w[n]
    fused = np.where(den > 0, num / np.maximum(den, 1e-12), np.nan)
    return zscore(fused), w
