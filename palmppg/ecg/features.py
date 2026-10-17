"""ECG-derived rate and rhythm features, and the instantaneous rate series for the sync cross-correlation.

Protocol section 6.4: "IBI series; HR; rhythm features (irregularity, RMSSD, sample entropy, Poincare)".
Section 4.3: the ECG instantaneous heart-rate series resampled to `sync.xcorr.rate_fs` (4 Hz) is
cross-correlated with the PPG rate series over +/- `sync.xcorr.lag_s`.

Every column here is registered `requires_ecg=True` in group "ecg" (CONTRACTS section 5; feature-store
column = "ecg__<name>"). Units are in the FEATURES table. Statistics use the valid IBIs only
(`beats.ibi_bounds_s`); successive-difference statistics use pairs of adjacent valid intervals.
"""
from __future__ import annotations

import math

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from palmppg.core.config import Config
from palmppg.core.timeline import resample_to_grid, uniform_grid
from palmppg.core.tracks import REGISTRY, FeatureRegistry

GROUP = "ecg"
MS_PER_S = 1000.0
S_PER_MIN = 60.0
PNN_THRESHOLD_MS = 50.0        # the "50" in pNN50 is part of the feature's definition, not a study threshold
SAMPEN_DIMENSION = 2
SAMPEN_R_FRAC = 0.2            # r = 0.2 * SD, the standard sample-entropy tolerance
SAMPEN_MIN_N = 10
SAMPEN_MAX_N = 5000

# (name, units, description); the feature-store column is "ecg__<name>".
FEATURES: tuple[tuple[str, str, str], ...] = (
    ("hr_mean_bpm", "bpm", "60 / mean valid IBI over the feature window"),
    ("hr_median_bpm", "bpm", "median instantaneous heart rate (60 / IBI)"),
    ("n_beats", "count", "R-peaks inside the feature window"),
    ("n_ibi", "count", "IBIs inside the window (adjacent peaks)"),
    ("n_ibi_rejected", "count", "IBIs outside beats.ibi_bounds_s"),
    ("ibi_mean_ms", "ms", "mean valid IBI"),
    ("ibi_median_ms", "ms", "median valid IBI"),
    ("sdnn_ms", "ms", "SD of valid IBIs (ddof=1)"),
    ("rmssd_ms", "ms", "root mean square of successive IBI differences"),
    ("pnn50", "%", "percentage of successive IBI differences above 50 ms"),
    ("sampen", "nats", "sample entropy of the IBI series (m=2, r=0.2 SD)"),
    ("poincare_sd1_ms", "ms", "Poincare short-axis SD"),
    ("poincare_sd2_ms", "ms", "Poincare long-axis SD"),
    ("poincare_ratio", "ratio", "SD1 / SD2"),
    ("ibi_cv", "ratio", "IBI irregularity: coefficient of variation (SD / mean)"),
    ("ibi_succ_diff_gt50_frac", "fraction", "IBI irregularity: fraction of successive differences above 50 ms"),
    ("turning_point_ratio", "ratio", "turning points / (n - 2) of the IBI sequence (2/3 for a random sequence)"),
    ("detector_agree_frac", "fraction", "primary R-peaks matched by the second detector"),
    ("r_amp_median_mv", "mV", "median cleaned-ECG amplitude at the R-peaks"),
    ("r_amp_cv", "ratio", "coefficient of variation of the R-peak amplitudes"),
    ("window_span_s", "s", "first to last R-peak used"),
    # clip-level fields written by palmppg.ecg.run into ecg_features.json
    ("fs", "Hz", "ECG sampling rate"),
    ("n_samples", "count", "ECG samples"),
    ("ecg_duration_s", "s", "ECG recording length"),
    ("ecg_digitised", "bool", "ECG came from the PDF digitiser rather than an ATC file"),
    ("export_format", "label", "atc | pdf"),
    ("source_file", "label", "ECG file used"),
    ("start_time", "label", "ISO8601 start time from the ATC header (audit only; never used to align)"),
    ("crc_ok_all", "bool", "every ATC block passed its CRC"),
    ("clipped_frac", "fraction", "ATC samples at the int16 rails"),
    ("detectors", "label", "detectors run, ';'-joined, primary first"),
    ("n_peaks_primary", "count", "R-peaks found by the primary detector over the whole recording"),
    ("secondary_matched_frac", "fraction", "second-detector peaks matched to a primary peak"),
    ("artefact_found", "bool", "fine-anchor artefact onset found"),
    ("artefact_onset_t_ecg_s", "s", "artefact onset in ECG native seconds"),
    ("artefact_score", "ratio", "feature value over threshold at the onset"),
    ("feature_window_end_s", "s", "R-peaks after this ECG time are excluded (artefact onset or tail exclusion)"),
    ("app_rhythm_label", "label", "Kardia app rhythm label (covariate only, never the label)"),
    ("clinician_rhythm", "label", "clinician-read rhythm class (the label; from clinician.json)"),
    ("clinician_rhythm_unmapped", "bool", "clinician text was not one of ecg.rhythm_classes (mapped to other)"),
    ("clinician_ecg_hr", "bpm", "clinician-read heart rate (reference quantity)"),
    ("hard_non_af", "bool", "clinician rhythm is in ecg.hard_non_af"),
    ("digitiser_rows_found", "count", "PDF digitiser: strip rows found"),
    ("digitiser_px_per_mm", "px/mm", "PDF digitiser: grid pitch measured on the page"),
    ("digitiser_trace_coverage", "fraction", "PDF digitiser: columns with a trace"),
    ("digitiser_skew_deg", "deg", "PDF digitiser: deskew angle applied"),
)
FEATURE_NAMES: tuple[str, ...] = tuple(f[0] for f in FEATURES)


def column_name(name: str) -> str:
    """Feature-store column for an ECG feature: group__name (camera omitted, the ECG is camera-independent)."""
    return f"{GROUP}__{name}"


def register_features(registry: FeatureRegistry = REGISTRY) -> list[str]:
    """Register every ECG-derived column with the track registry (idempotent; CONTRACTS section 5).

    All are group "ecg", camera "any", `requires_ecg=True`: they can never enter a product_candidate model.
    Returns the column names.
    """
    out = []
    for name, units, desc in FEATURES:
        tags = ("label",) if name == "clinician_rhythm" else (("covariate",) if name == "app_rhythm_label" else ())
        col = column_name(name)
        registry.add(col, GROUP, camera="any", requires_ecg=True, requires_raw=False, units=units,
                     description=desc, tags=tags)
        out.append(col)
    return out


def _cfg(cfg: Config | None) -> Config:
    if cfg is None:
        from palmppg.core.config import load_pipeline_config

        cfg = load_pipeline_config()
    return cfg


# --------------------------------------------------------------------------- building blocks
def sample_entropy(x, m: int = SAMPEN_DIMENSION, r: float | None = None, r_frac: float = SAMPEN_R_FRAC) -> float:
    """Sample entropy SampEn(m, r) = -ln(A / B) of a 1-D series (Richman and Moorman 2000).

    B counts pairs of length-m templates (Chebyshev distance <= r, self-matches excluded) among the first
    N - m templates, A the same for length m + 1; r defaults to `r_frac` * SD (ddof=1). NaN when the series
    is shorter than SAMPEN_MIN_N, r is zero, or no match exists.
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
    if not (r > 1e-9 * float(np.max(np.abs(v)))):      # a (numerically) constant series has no entropy
        return float("nan")
    n_templates = n - m

    def count(dim: int) -> int:
        templ = sliding_window_view(v, dim)[:n_templates]
        total = 0
        step = 512
        for s in range(0, n_templates, step):
            block = templ[s:s + step]
            d = np.abs(block[:, None, :] - templ[None, :, :]).max(axis=2)
            total += int((d <= r).sum())
        return total - n_templates  # remove self-matches

    b = count(m)
    a = count(m + 1)
    if a <= 0 or b <= 0:
        return float("nan")
    return float(-math.log(a / b))


def turning_point_ratio(x, rel_tol: float = 1e-9) -> float:
    """Fraction of interior points that are local extrema; 2/3 is the expectation for an i.i.d. sequence.

    Differences below `rel_tol` times the series' absolute maximum count as ties (not turning points), so
    floating-point noise from accumulated beat times cannot create spurious extrema.
    """
    v = np.asarray(x, dtype=np.float64)
    v = v[np.isfinite(v)]
    if v.size < 3:
        return float("nan")
    tol = float(rel_tol) * float(np.max(np.abs(v))) if v.size else 0.0
    a, b, c = v[:-2], v[1:-1], v[2:]
    tp = ((b > a + tol) & (b > c + tol)) | ((b < a - tol) & (b < c - tol))
    return float(tp.mean())


def poincare_sd(ibi_ms, succ_diff_ms) -> tuple[float, float]:
    """Poincare SD1 (short axis) and SD2 (long axis) in the units of `ibi_ms`."""
    ibi = np.asarray(ibi_ms, dtype=np.float64)
    d = np.asarray(succ_diff_ms, dtype=np.float64)
    if ibi.size < 3 or d.size < 2:
        return float("nan"), float("nan")
    sdsd2 = float(np.var(d, ddof=1))
    sdnn2 = float(np.var(ibi, ddof=1))
    sd1 = math.sqrt(0.5 * sdsd2)
    sd2sq = 2.0 * sdnn2 - 0.5 * sdsd2
    if sd2sq < -1e-9 * max(sdnn2, 1.0):      # only a genuinely negative value is undefined
        return sd1, float("nan")
    return sd1, math.sqrt(max(sd2sq, 0.0))


def _windowed_ibis(t: np.ndarray, keep: np.ndarray, bounds: tuple[float, float]) -> dict:
    """IBIs between kept peaks that were adjacent in the original sequence, with validity per bounds."""
    lo, hi = bounds
    order = np.argsort(t)
    t = t[order]
    keep = keep[order]
    adj = keep[:-1] & keep[1:]
    ibi = np.diff(t)[adj]
    t_end = t[1:][adj]
    valid = (ibi >= lo) & (ibi <= hi)
    # successive pairs: both intervals valid and the intervals themselves adjacent in the kept sequence
    pos = np.where(adj)[0]
    succ_adjacent = np.diff(pos) == 1
    pair_valid = valid[:-1] & valid[1:] & succ_adjacent
    succ = np.diff(ibi)[pair_valid]
    return {"ibi_s": ibi, "t_end_s": t_end, "valid": valid, "succ_diff_s": succ, "n_kept": int(keep.sum())}


# --------------------------------------------------------------------------- public API
def ecg_features(rpeaks_t, x_clean=None, fs: float | None = None, window_mask=None, agree=None,
                 cfg: Config | None = None, bounds_s: tuple[float, float] | None = None) -> dict:
    """Clip-level ECG rate and rhythm features from R-peak times in seconds (protocol 6.4).

    `window_mask` (bool per peak) restricts the peaks (IBIs are formed only between kept peaks that were
    adjacent in the original sequence, so no interval bridges an excluded gap). `agree` (bool per peak,
    from `detect_rpeaks`) gives `detector_agree_frac` over the kept peaks. `x_clean` + `fs` add the R-peak
    amplitude features. Returns {name: float | int} for the names in FEATURES up to `window_span_s`; NaN
    where a quantity cannot be computed.
    """
    if bounds_s is None:
        bounds_s = tuple(_cfg(cfg).get("beats.ibi_bounds_s"))
    bounds = (float(bounds_s[0]), float(bounds_s[1]))
    t = np.asarray(rpeaks_t, dtype=np.float64)
    keep = np.ones(t.size, dtype=bool) if window_mask is None else np.asarray(window_mask, dtype=bool)
    if keep.shape != t.shape:
        raise ValueError("window_mask must have one entry per R-peak")
    nan = float("nan")
    out: dict[str, float | int] = {name: nan for name, _, _ in FEATURES[:21]}
    out["n_beats"] = int(keep.sum())
    if agree is not None:
        a = np.asarray(agree, dtype=bool)
        if a.shape != t.shape:
            raise ValueError("agree must have one entry per R-peak")
        out["detector_agree_frac"] = float(a[keep].mean()) if keep.any() else nan
    if out["n_beats"] < 2:
        out["n_ibi"] = 0
        out["n_ibi_rejected"] = 0
        return out
    w = _windowed_ibis(t, keep, bounds)
    ibi_ms = w["ibi_s"][w["valid"]] * MS_PER_S
    succ_ms = w["succ_diff_s"] * MS_PER_S
    out["n_ibi"] = int(w["ibi_s"].size)
    out["n_ibi_rejected"] = int((~w["valid"]).sum())
    tk = np.sort(t[keep])
    out["window_span_s"] = float(tk[-1] - tk[0])
    if ibi_ms.size == 0:
        return out
    mean_ibi = float(np.mean(ibi_ms))
    out["ibi_mean_ms"] = mean_ibi
    out["ibi_median_ms"] = float(np.median(ibi_ms))
    out["hr_mean_bpm"] = S_PER_MIN * MS_PER_S / mean_ibi
    out["hr_median_bpm"] = float(np.median(S_PER_MIN * MS_PER_S / ibi_ms))
    if ibi_ms.size >= 2:
        sdnn = float(np.std(ibi_ms, ddof=1))
        out["sdnn_ms"] = sdnn
        out["ibi_cv"] = sdnn / mean_ibi
    if succ_ms.size >= 1:
        out["rmssd_ms"] = float(np.sqrt(np.mean(succ_ms**2)))
        frac = float(np.mean(np.abs(succ_ms) > PNN_THRESHOLD_MS))
        out["pnn50"] = 100.0 * frac
        out["ibi_succ_diff_gt50_frac"] = frac
    sd1, sd2 = poincare_sd(ibi_ms, succ_ms)
    out["poincare_sd1_ms"], out["poincare_sd2_ms"] = sd1, sd2
    out["poincare_ratio"] = (sd1 / sd2) if (np.isfinite(sd1) and np.isfinite(sd2) and sd2 > 0) else nan
    out["sampen"] = sample_entropy(ibi_ms)
    out["turning_point_ratio"] = turning_point_ratio(ibi_ms)
    if x_clean is not None and fs is not None:
        x = np.asarray(x_clean, dtype=np.float64)
        idx = np.clip(np.round(tk * float(fs)).astype(np.int64), 0, x.size - 1)
        amp = x[idx]
        amp = amp[np.isfinite(amp)]
        if amp.size:
            med = float(np.median(amp))
            out["r_amp_median_mv"] = med
            out["r_amp_cv"] = float(np.std(amp, ddof=1) / abs(med)) if (amp.size > 1 and med != 0) else nan
    return out


def instantaneous_rate(rpeaks_t, grid=None, fs: float | None = None, cfg: Config | None = None,
                       bounds_s: tuple[float, float] | None = None) -> tuple[np.ndarray, np.ndarray]:
    """ECG instantaneous heart-rate series (t, bpm) for the sync cross-correlation (protocol 4.3).

    Rate 60 / IBI is placed at the time of the second peak of each valid interval (`beats.ibi_bounds_s`)
    and linearly interpolated onto `grid` (seconds; default a uniform grid from the first to the last peak
    at `fs`, default `sync.xcorr.rate_fs`). Gaps wider than the upper IBI bound and times outside the
    peaks are NaN.
    """
    c = None
    if bounds_s is None or (grid is None and fs is None):
        c = _cfg(cfg)
    if bounds_s is None:
        bounds_s = tuple(c.get("beats.ibi_bounds_s"))
    t = np.sort(np.asarray(rpeaks_t, dtype=np.float64))
    if grid is None:
        if fs is None:
            fs = float(c.get("sync.xcorr.rate_fs"))
        if t.size == 0:
            return np.zeros(0), np.zeros(0)
        grid = uniform_grid(float(t[0]), float(t[-1]), float(fs))
    grid = np.asarray(grid, dtype=np.float64)
    if t.size < 2:
        return grid, np.full(grid.shape, np.nan)
    ibi = np.diff(t)
    valid = (ibi >= float(bounds_s[0])) & (ibi <= float(bounds_s[1]))
    if valid.sum() < 2:
        return grid, np.full(grid.shape, np.nan)
    t_rate = t[1:][valid]
    bpm = S_PER_MIN / ibi[valid]
    return grid, resample_to_grid(t_rate, bpm, grid, max_gap_s=float(bounds_s[1]))
