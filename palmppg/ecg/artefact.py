"""Fine-anchor artefact onset in the ECG (protocol section 4.3).

At pattern P2 the operator lifts the right thumb off the Kardia card; the lead-off transient is an
unmistakable baseline artefact. The detector looks for the first sample after `search_from_s` whose
absolute first difference (slew: the largest absolute change over any span up to SLEW_SPAN_S, so a
band-limited edge spread over a few samples still counts in full) or absolute excursion from the
baseline exceeds an adaptive threshold estimated on the preceding clean window of
`sync.artefact.clean_window_s` seconds:

    threshold = max(median + k_mad * MAD,  margin * max over the clean window)

The second term is what makes QRS complexes invisible to the detector: the clean window holds at least
one beat, so its maximum slew and maximum excursion are those of ordinary QRS complexes, and only an
event larger than that by `margin` can trigger. The onset is the earliest crossing over both features;
a slew crossing is refined to the steepest single-sample step inside its span. The result is in ECG
native seconds; the sync layer pairs it with the thumb-lift frame.
"""
from __future__ import annotations

import math

import numpy as np

from palmppg.core.config import Config
from palmppg.ecg.clean import bridge_nan

MAD_TO_SIGMA = 1.4826
DEFAULT_MARGIN = 1.5          # used when the config has no sync.artefact.margin entry
MIN_CLEAN_FRACTION = 0.25     # the clean window must hold at least this fraction of its nominal samples
SLEW_SPAN_S = 0.010           # the slew feature is the largest |x[i+k] - x[i]| over 1 <= k <= span
FEATURES = ("slew", "excursion")


def slew_feature(x: np.ndarray, fs: float, span_s: float = SLEW_SPAN_S) -> tuple[np.ndarray, int]:
    """max over 1 <= k <= K of |x[i+k] - x[i]| with K = round(span_s * fs); element i refers to a rise that
    starts at sample i. Returns (feature of length n - 1, K)."""
    n = x.size
    k_max = max(1, round(float(span_s) * float(fs)))
    k_max = min(k_max, n - 1)
    f = np.abs(np.diff(x))
    for k in range(2, k_max + 1):
        d = np.abs(x[k:] - x[:-k])
        f[:d.size] = np.maximum(f[:d.size], d)
    return f, k_max


def _cfg(cfg: Config | None) -> Config:
    if cfg is None:
        from palmppg.core.config import load_pipeline_config

        cfg = load_pipeline_config()
    return cfg


def _not_found(reason: str, **extra) -> dict:
    out = {"found": False, "onset_t_s": None, "onset_idx": None, "score": None, "threshold": None,
           "feature": None, "reason": reason}
    out.update(extra)
    return out


def adaptive_threshold(f_clean: np.ndarray, k_mad: float, margin: float) -> dict:
    """median + k * MAD (MAD scaled to sigma) versus margin * max over the clean window; the larger wins."""
    med = float(np.median(f_clean))
    mad = float(np.median(np.abs(f_clean - med))) * MAD_TO_SIGMA
    thr_mad = med + float(k_mad) * mad
    thr_max = float(margin) * float(np.max(f_clean))
    return {"median": med, "mad": mad, "thr_mad": thr_mad, "thr_max": thr_max, "threshold": max(thr_mad, thr_max)}


def artefact_onset(x, fs: float, search_from_s: float, clean_window_s: float | None = None,
                   k_mad: float | None = None, cfg: Config | None = None, margin: float | None = None,
                   search_to_s: float | None = None) -> dict:
    """First artefact onset after `search_from_s` in an ECG (raw or cleaned, mV at `fs` Hz); section 4.3.

    Returns {found, onset_t_s, onset_idx, score (feature / threshold at the onset, >= 1 when found),
    threshold, feature ("slew" | "excursion"), reason (why nothing qualified when found=False),
    search_from_s, search_to_s, clean_window_s [start, end], k_mad, margin, thresholds {feature: ...},
    candidates {feature: {found, t_s, idx, score, max_ratio}}}. Defaults: `sync.artefact.clean_window_s`,
    `sync.artefact.k_mad`, `sync.artefact.margin` (DEFAULT_MARGIN when absent).
    """
    if clean_window_s is None or k_mad is None or margin is None:
        c = _cfg(cfg)
        clean_window_s = float(c.get("sync.artefact.clean_window_s")) if clean_window_s is None else clean_window_s
        k_mad = float(c.get("sync.artefact.k_mad")) if k_mad is None else k_mad
        margin = float(c.get("sync.artefact.margin", DEFAULT_MARGIN)) if margin is None else margin
    fs = float(fs)
    filled, bad = bridge_nan(x)
    n = filled.size
    base = {"search_from_s": float(search_from_s), "search_to_s": None if search_to_s is None else float(search_to_s),
            "k_mad": float(k_mad), "margin": float(margin), "fs": fs, "n_samples": int(n)}
    if n < 3 or bad.all():
        return _not_found("signal empty or all NaN", **base)
    i_from = math.ceil(float(search_from_s) * fs)
    i_to = n if search_to_s is None else min(n, math.floor(float(search_to_s) * fs) + 1)
    if i_from >= n - 1:
        return _not_found(f"search start {search_from_s:.3f} s is at or beyond the signal end "
                          f"({(n - 1) / fs:.3f} s)", **base)
    if i_to <= i_from + 1:
        return _not_found("search window is empty", **base)
    n_clean = round(float(clean_window_s) * fs)
    c0 = max(0, i_from - n_clean)
    c1 = i_from
    base["clean_window_s"] = [c0 / fs, c1 / fs]
    if c1 - c0 < max(3, int(MIN_CLEAN_FRACTION * n_clean)):
        return _not_found(f"clean window before {search_from_s:.3f} s holds only {c1 - c0} samples", **base)

    clean_seg = filled[c0:c1]
    baseline = float(np.median(clean_seg))
    slew, k_span = slew_feature(filled, fs)
    feats = {
        "slew": slew,                                  # element i = largest rise starting at sample i
        "excursion": np.abs(filled - baseline),
    }
    clean_slices = {"slew": slice(c0, max(c0 + 1, c1 - k_span)), "excursion": slice(c0, c1)}
    base["slew_span_samples"] = int(k_span)
    thresholds: dict[str, dict] = {}
    candidates: dict[str, dict] = {}
    best: tuple[float, str, int, float] | None = None
    for name in FEATURES:
        f = feats[name]
        thr = adaptive_threshold(f[clean_slices[name]], k_mad, margin)
        thresholds[name] = thr
        hi = min(i_to, f.size)
        seg = f[i_from:hi]
        above = np.where(seg > thr["threshold"])[0]
        max_ratio = float(seg.max() / thr["threshold"]) if (seg.size and thr["threshold"] > 0) else float("nan")
        if above.size:
            i = int(i_from + above[0])
            score = float(f[i] / thr["threshold"]) if thr["threshold"] > 0 else float("inf")
            if name == "slew":
                # refine to the steepest single-sample step inside the span that triggered
                seg_d = np.abs(np.diff(filled[i:min(n, i + k_span + 1)]))
                i = i + int(np.argmax(seg_d)) if seg_d.size else i
                t = (i + 0.5) / fs
            else:
                t = i / fs
            candidates[name] = {"found": True, "t_s": t, "idx": i, "score": score, "max_ratio": max_ratio}
            if best is None or t < best[0]:
                best = (t, name, i, score)
        else:
            candidates[name] = {"found": False, "t_s": None, "idx": None, "score": None, "max_ratio": max_ratio}
    base["thresholds"] = {k: v["threshold"] for k, v in thresholds.items()}
    base["threshold_detail"] = thresholds
    base["candidates"] = candidates
    if best is None:
        ratios = ", ".join(f"{k} max {v['max_ratio']:.2f} x threshold" for k, v in candidates.items())
        return _not_found(f"no excursion above the adaptive threshold after {search_from_s:.3f} s ({ratios})", **base)
    t, name, i, score = best
    return {"found": True, "onset_t_s": float(t), "onset_idx": int(i), "score": float(score),
            "threshold": float(thresholds[name]["threshold"]), "feature": name, "reason": None, **base}


def exclusion_window_ecg(onset_t_s: float, end_t_s: float, reason: str = "fine-anchor lift artefact") -> dict:
    """ECG-native exclusion window from the artefact onset to the end of the recording (protocol 6.4:
    'window exclusions written back to the timeline'); the sync layer maps it onto the reference clock."""
    return {"start_s": float(onset_t_s), "end_s": float(end_t_s), "reason": reason}
