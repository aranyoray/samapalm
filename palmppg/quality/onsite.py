"""On-site quality grades for a palm clip and its ECG (design contract section 4; Kotlin twin: android/quality-core).

Rule-based, transparent, offline: every grade is "good" | "borderline" | "retake" with short plain reasons for the
operator and the metrics behind them. The irregular-rhythm flag is a screening heuristic for clinician review, never a
rhythm label, and never lowers a grade. All thresholds are PROVISIONAL defaults, to be calibrated on pilot clips the
way DECISIONS D-008 handles the pipeline SQI threshold.

Video (from `<clip>_roi.csv`, `<clip>_frames.csv` optional): duration, fps, dropped frames from frame-time gaps,
exposure (median Y, median clipped fraction, share of near-black rows: the D-033 black-frame failure), motion (median
relative change of the 3x3 grid between rows), and the pulse: POS (Wang et al. 2017, 1.6 s windows) on R/G/B
resampled to 30 Hz, Hann periodogram, peak in 0.7-3.5 Hz, and de Haan & Jeanne (2013) SNR: power within +/-0.1 Hz of
f0 and +/-0.2 Hz of 2 f0 over the rest of 0.5-4 Hz (f0 = the reference heart rate when one is given).

ECG (mV at fs): 0.5-40 Hz Butterworth biquads (RBJ bilinear form) run forward and backward over an odd-extended
copy; Pan-Tompkins style QRS detection (5-point derivative, square, 150 ms moving integration, adaptive thresholds
with search-back, 250 ms refractory, R refined to max |x| within +/-75 ms); template correlation with the median
beat (Orphanidou et al. 2015), kurtosis kSQI (Clifford et al. 2012, Pearson kurtosis, Gaussian = 3), flat-line share,
RR checks after Orphanidou (HR 40-180, longest RR < 3 s, longest/shortest RR < 2.2), and RR irregularity after Dash
et al. 2009 (RMSSD/mean RR, turning points, Shannon entropy).

Readers: roi/frames/ECG CSVs as written by PalmRecorderActivity, ATC through `palmppg.ecg.atc`, and Kardia PDFs
through a small vector-path reader (the Kardia app draws one polyline point per 300 Hz sample, 0.2362 pt apart at
25 mm/s), a line-by-line port of the Kotlin `KardiaPdf` so both read the same samples.

Numbers are computed the same way in both languages (same biquads, same periodogram, same order of operations
where a decision depends on it); the fixtures in configs/quality_fixtures pin grades, reasons and metrics.
"""
from __future__ import annotations

import math
import os
import re
import tempfile
import zlib
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import numpy as np

from palmppg.ecg.atc import parse_atc

MM = 72.0 / 25.4                     # PDF points per millimetre
CLOSING_SENTENCE = "This is not a medical opinion. A study doctor reviews every recording."
GRID_COLS = tuple(f"g{r}{c}" for r in range(3) for c in range(3))


# --------------------------------------------------------------------------- data types and configs
@dataclass
class Grade:
    level: str                       # "good" | "borderline" | "retake"
    reasons: list[str]
    metrics: dict[str, float | None]


@dataclass
class RoiSeries:
    t_s: np.ndarray
    r: np.ndarray
    g: np.ndarray
    b: np.ndarray
    y: np.ndarray
    clip_frac: np.ndarray
    grid: np.ndarray | None = None   # 9 x n luma means (g00..g22), or None


@dataclass
class EcgTrace:
    fs: float
    mv: np.ndarray
    warnings: list[str] = field(default_factory=list)
    determination: str | None = None  # Kardia PDF page text, as printed
    hr_bpm: int | None = None
    enhanced_filter: bool | None = None
    mains_hz: int | None = None


@dataclass
class RhythmSummary:
    hr_bpm: float | None
    rhythm: str                      # "regular" | "irregular" | "insufficient"
    inverted: bool
    n_beats: int
    rr_min_s: float | None
    rr_max_s: float | None
    irregular_flag: bool
    sentences: list[str]

    @property
    def text(self) -> str:
        return " ".join(self.sentences)


@dataclass(frozen=True)
class VideoQualityConfig:
    """PROVISIONAL video thresholds (calibrate on pilot clips, as D-008)."""
    min_duration_frac: float = 0.9          # retake: duration < 0.9 x the clip length asked for
    min_mean_level: float = 25.0            # retake: median Y below this (torch off, palm off the lens)
    dark_level: float = 20.0                # a row with Y below this counts as dark
    max_dark_frac: float = 0.2              # retake: more dark rows than this
    retake_clipped_frac: float = 0.25
    retake_dropped_frac: float = 0.05
    retake_snr_db: float = -3.0             # de Haan SNR, retake below
    borderline_snr_db: float = 1.5
    borderline_clipped_frac: float = 0.05
    borderline_motion: float = 0.02
    borderline_dropped_frac: float = 0.01
    max_ref_hr_diff_bpm: float = 8.0
    resample_hz: float = 30.0
    pos_window_s: float = 1.6               # Wang et al. 2017
    pulse_lo_hz: float = 0.7
    pulse_hi_hz: float = 3.5
    snr_lo_hz: float = 0.5
    snr_hi_hz: float = 4.0
    snr_f0_halfwidth_hz: float = 0.1        # de Haan & Jeanne 2013
    snr_h2_halfwidth_hz: float = 0.2


@dataclass(frozen=True)
class EcgQualityConfig:
    """PROVISIONAL ECG thresholds (calibrate on pilot clips, as D-008)."""
    min_duration_s: float = 20.0
    retake_flat_frac: float = 0.3
    min_beats: int = 8
    retake_template_corr: float = 0.5
    retake_hr_lo: float = 30.0
    retake_hr_hi: float = 220.0
    borderline_template_corr: float = 0.66  # Orphanidou et al. 2015
    min_ksqi: float = 5.0                   # Clifford et al. 2012
    max_rr_s: float = 3.0                   # Orphanidou: longest RR
    borderline_hr_lo: float = 40.0
    borderline_hr_hi: float = 180.0
    borderline_flat_frac: float = 0.1
    max_rr_ratio: float = 2.2               # Orphanidou: longest / shortest RR (skipped when irregular)
    flat_ptp_mv: float = 0.05               # 1 s window with a smaller peak-to-peak counts as flat
    band_lo_hz: float = 0.5
    band_hi_hz: float = 40.0
    irregular_rmssd_ratio: float = 0.1      # Dash et al. 2009
    irregular_shannon: float = 0.7
    min_rr_for_rhythm: int = 8


# --------------------------------------------------------------------------- small shared numerics
def _rhu(x: float) -> int:
    """Round half up for non-negative values (sample counts)."""
    return int(math.floor(x + 0.5))


def fmt(x: float, nd: int) -> str:
    """Decimal text of x rounded half away from zero to nd places (same digits as Kotlin's BigDecimal HALF_UP)."""
    q = Decimal(float(x) + 0.0).quantize(Decimal(1).scaleb(-nd), rounding=ROUND_HALF_UP)
    return str(abs(q) if q == 0 else q)


def _median(v) -> float:
    a = np.sort(np.asarray(v, dtype=float))
    n = a.size
    if n == 0:
        return float("nan")
    m = n // 2
    return float(a[m]) if n % 2 else float((a[m - 1] + a[m]) / 2.0)


def _quantile(v, q: float) -> float:
    """Linear-interpolation quantile (numpy's default definition), written out so Kotlin matches it."""
    a = np.sort(np.asarray(v, dtype=float))
    n = a.size
    pos = q * (n - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, n - 1)
    return float(a[lo] + (a[hi] - a[lo]) * (pos - lo))


def _nfft(n: int) -> int:
    p, target = 1, max(8 * n, 4096)
    while p < target:
        p *= 2
    return p


def periodogram(x, fs: float) -> tuple[np.ndarray, np.ndarray]:
    """Mean-removed, symmetric-Hann-windowed, zero-padded one-sided power spectrum (f in Hz, x^2 units)."""
    x = np.asarray(x, dtype=float)
    n = x.size
    z = x - x.mean()
    w = 0.5 - 0.5 * np.cos(2.0 * math.pi * np.arange(n) / (n - 1)) if n > 1 else np.ones(n)
    nfft = _nfft(n)
    spec = np.fft.rfft(z * w, n=nfft)
    f = np.arange(nfft // 2 + 1) * (fs / nfft)
    pxx = (spec.real ** 2 + spec.imag ** 2) / max(float(np.sum(w * w)), 1e-12)
    return f, pxx


def _spectral_peak(f: np.ndarray, pxx: np.ndarray, lo: float, hi: float, df: float) -> float | None:
    sel = np.where((f >= lo) & (f <= hi))[0]
    if sel.size == 0 or not np.any(pxx[sel] > 0):
        return None
    k = int(sel[int(np.argmax(pxx[sel]))])
    fpk = float(f[k])
    if 0 < k < f.size - 1:
        y0, y1, y2 = float(pxx[k - 1]), float(pxx[k]), float(pxx[k + 1])
        den = y0 - 2.0 * y1 + y2
        if den < 0:
            fpk = fpk + 0.5 * (y0 - y2) / den * df
    return fpk


def _biquad_coeffs(kind: str, f0: float, fs: float) -> tuple[float, float, float, float, float]:
    """Second-order Butterworth (Q = 1/sqrt 2) low- or high-pass, bilinear transform (RBJ cookbook), a0 = 1."""
    w0 = 2.0 * math.pi * f0 / fs
    c, s = math.cos(w0), math.sin(w0)
    alpha = s / (2.0 * (1.0 / math.sqrt(2.0)))
    if kind == "lp":
        b0, b1 = (1.0 - c) / 2.0, 1.0 - c
    else:
        b0, b1 = (1.0 + c) / 2.0, -(1.0 + c)
    a0 = 1.0 + alpha
    return b0 / a0, b1 / a0, b0 / a0, (-2.0 * c) / a0, (1.0 - alpha) / a0


def _biquad(x: list[float], co) -> list[float]:
    b0, b1, b2, a1, a2 = co
    z1 = z2 = 0.0
    out = [0.0] * len(x)
    for i, xi in enumerate(x):
        yi = b0 * xi + z1
        z1 = b1 * xi - a1 * yi + z2
        z2 = b2 * xi - a2 * yi
        out[i] = yi
    return out


def ecg_bandpass(mv, fs: float, lo: float = 0.5, hi: float = 40.0) -> np.ndarray:
    """Zero-phase 0.5-40 Hz band-pass: median removed, odd extension of 2 s, HP then LP biquad, forward and back."""
    x = np.asarray(mv, dtype=float)
    n = x.size
    if n == 0:
        return x.copy()
    x = x - _median(x)
    sections = [_biquad_coeffs("hp", lo, fs), _biquad_coeffs("lp", min(hi, 0.45 * fs), fs)]
    pad = min(n - 1, _rhu(2.0 * fs))
    if pad > 0:
        left = 2.0 * x[0] - x[pad:0:-1]
        right = 2.0 * x[-1] - x[n - 2:n - 2 - pad:-1] if n - 2 - pad >= 0 else 2.0 * x[-1] - x[n - 2::-1]
        xp = np.concatenate([left, x, right])
    else:
        xp = x
    y = xp.tolist()
    for co in sections:
        y = _biquad(y, co)
    y.reverse()
    for co in sections:
        y = _biquad(y, co)
    y.reverse()
    return np.asarray(y[pad:pad + n], dtype=float)


# --------------------------------------------------------------------------- recorder file readers
def _header_index(line: str) -> dict[str, int]:
    return {h.strip(): i for i, h in enumerate(line.strip().split(","))}


def parse_roi_csv(text: str) -> RoiSeries:
    """`<clip>_roi.csv` (CONTRACTS 3.5) -> RoiSeries sorted by t_ref_ns, t in seconds from the first row.

    Rows that do not parse or carry non-finite values are skipped. The 3x3 grid is kept when all nine columns exist.
    """
    lines = text.splitlines()
    if not lines:
        raise ValueError("roi.csv is empty")
    idx = _header_index(lines[0])
    need = ["t_ref_ns", "y_mean", "r_mean", "g_mean", "b_mean", "clip_frac"]
    missing = [c for c in need if c not in idx]
    if missing:
        raise ValueError(f"roi.csv: missing columns {missing}")
    has_grid = all(c in idx for c in GRID_COLS)
    cols = need[1:] + (list(GRID_COLS) if has_grid else [])
    rows: list[tuple[int, list[float]]] = []
    for line in lines[1:]:
        if not line.strip():
            continue
        parts = line.split(",")
        try:
            t = int(parts[idx["t_ref_ns"]].strip())
            vals = [float(parts[idx[c]]) for c in cols]
        except (ValueError, IndexError):
            continue
        if all(math.isfinite(v) for v in vals):
            rows.append((t, vals))
    rows.sort(key=lambda r: r[0])
    if not rows:
        z = np.zeros(0)
        return RoiSeries(z, z, z, z, z, z, np.zeros((9, 0)) if has_grid else None)
    t0 = rows[0][0]
    t_s = np.array([(t - t0) / 1e9 for t, _ in rows])
    v = np.array([vals for _, vals in rows], dtype=float)
    grid = v[:, 5:14].T.copy() if has_grid else None
    return RoiSeries(t_s, v[:, 1].copy(), v[:, 2].copy(), v[:, 3].copy(), v[:, 0].copy(), v[:, 4].copy(), grid)


def parse_frames_csv(text: str) -> np.ndarray:
    """`<clip>_frames.csv` sensor_ts_ns -> seconds from the first frame, sorted."""
    lines = text.splitlines()
    if not lines:
        return np.zeros(0)
    idx = _header_index(lines[0])
    if "sensor_ts_ns" not in idx:
        raise ValueError("frames.csv: missing column sensor_ts_ns")
    ts = []
    for line in lines[1:]:
        parts = line.split(",")
        try:
            ts.append(int(parts[idx["sensor_ts_ns"]].strip()))
        except (ValueError, IndexError):
            continue
    ts.sort()
    if not ts:
        return np.zeros(0)
    return np.array([(t - ts[0]) / 1e9 for t in ts])


def parse_ecg_csv(text: str) -> tuple[np.ndarray, float]:
    """`<clip>_ecg_samples.csv` -> (lead1_mv, fs), fs from the t_ref_ns span ((n-1) / span); 300 Hz if unknown."""
    lines = text.splitlines()
    if not lines:
        raise ValueError("ecg_samples.csv is empty")
    idx = _header_index(lines[0])
    if "lead1_mv" not in idx:
        raise ValueError("ecg_samples.csv: missing column lead1_mv")
    has_t = "t_ref_ns" in idx
    mv, ts = [], []
    for line in lines[1:]:
        if not line.strip():
            continue
        parts = line.split(",")
        try:
            v = float(parts[idx["lead1_mv"]])
            t = int(parts[idx["t_ref_ns"]].strip()) if has_t else None
        except (ValueError, IndexError):
            continue
        if not math.isfinite(v):
            continue
        mv.append(v)
        if t is not None:
            ts.append(t)
    fs = 300.0
    if len(ts) >= 2 and ts[-1] > ts[0]:
        fs = (len(ts) - 1) * 1e9 / (ts[-1] - ts[0])
    return np.array(mv, dtype=float), fs


def read_atc(source: bytes | str | os.PathLike) -> EcgTrace:
    """ATC file (bytes or path) through `palmppg.ecg.atc.parse_atc`; its problems become warnings."""
    if isinstance(source, (bytes, bytearray)):
        fd, tmp = tempfile.mkstemp(suffix=".atc")
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(bytes(source))
            rec = parse_atc(tmp)
        finally:
            os.unlink(tmp)
    else:
        rec = parse_atc(source)
    return EcgTrace(fs=float(rec["fs"]), mv=np.asarray(rec["samples_mv"], dtype=np.float64),
                    warnings=[str(p) for p in rec["problems"]])


# --------------------------------------------------------------------------- video
def _increasing(t: np.ndarray) -> np.ndarray:
    keep = np.zeros(t.size, dtype=bool)
    last = -math.inf
    for i, v in enumerate(t):
        if v > last:
            keep[i] = True
            last = v
    return keep


def _resample(t: np.ndarray, v: np.ndarray, hz: float) -> np.ndarray:
    """Linear interpolation of v(t) onto t0 + k / hz, k = 0 .. floor(span * hz)."""
    n = t.size
    if n < 2:
        return np.zeros(0)
    m = int(math.floor((t[-1] - t[0]) * hz + 1e-9)) + 1
    tg = t[0] + np.arange(m) / hz
    j = np.clip(np.searchsorted(t, tg, side="right") - 1, 0, n - 2)
    slope = (v[j + 1] - v[j]) / (t[j + 1] - t[j])
    return v[j] + slope * (tg - t[j])


def pos_pulse(r: np.ndarray, g: np.ndarray, b: np.ndarray, fs: float, window_s: float = 1.6) -> np.ndarray:
    """Plane-orthogonal-to-skin pulse (Wang et al. 2017) with overlap-add of `window_s` windows.

    Windows where a channel mean is below 1 code (black frames) are skipped and contribute nothing.
    """
    n = r.size
    win = _rhu(window_s * fs)
    h = np.zeros(n)
    for s0 in range(0, n - win + 1):
        cr, cg, cb = r[s0:s0 + win], g[s0:s0 + win], b[s0:s0 + win]
        mr, mg, mb = cr.mean(), cg.mean(), cb.mean()
        if min(mr, mg, mb) < 1.0:
            continue
        nr, ng, nb = cr / mr, cg / mg, cb / mb
        s1 = ng - nb
        s2 = -2.0 * nr + ng + nb
        sd2 = float(np.sqrt(np.mean((s2 - s2.mean()) ** 2)))
        sd1 = float(np.sqrt(np.mean((s1 - s1.mean()) ** 2)))
        alpha = sd1 / sd2 if sd2 > 0 else 0.0
        p = s1 + alpha * s2
        h[s0:s0 + win] += p - p.mean()
    return h


def _video_metrics(roi: RoiSeries, frame_times_s, ref_hr_bpm: float | None, cfg: VideoQualityConfig) -> dict:
    t = np.asarray(roi.t_s, dtype=float)
    out: dict[str, float | None] = {k: None for k in (
        "duration_s", "fps", "dropped_frac", "mean_level", "clipped_frac", "dark_frac", "motion", "snr_db",
        "pulse_bpm", "perfusion_pct", "skewness")}
    timing = np.asarray(frame_times_s, dtype=float) if frame_times_s is not None and len(frame_times_s) >= 2 else t
    if timing.size >= 2 and timing[-1] > timing[0]:
        dts = np.diff(timing)
        pos = dts[dts > 0]
        d = _median(pos)
        span = float(timing[-1] - timing[0])
        out["duration_s"] = span + d
        out["fps"] = (timing.size - 1) / span
        missing = 0
        for dt in dts:
            missing += max(0, int(math.floor(dt / d + 0.5)) - 1)
        out["dropped_frac"] = missing / (timing.size - 1 + missing)
    else:
        out["duration_s"] = 0.0
    if t.size == 0:
        return out
    out["mean_level"] = _median(roi.y)
    out["clipped_frac"] = _median(roi.clip_frac)
    out["dark_frac"] = float(np.count_nonzero(roi.y < cfg.dark_level)) / t.size
    if roi.grid is not None and roi.grid.shape[1] >= 2:
        num = np.abs(np.diff(roi.grid, axis=1)).sum(axis=0) / 9.0
        den = roi.grid[:, :-1].sum(axis=0) / 9.0
    else:
        num = np.abs(np.diff(roi.y))
        den = roi.y[:-1]
    ok = den >= cfg.dark_level                     # motion is judged on lit rows only
    if np.any(ok):
        out["motion"] = _median(num[ok] / den[ok])

    keep = _increasing(t)
    tt = t[keep]
    hz = cfg.resample_hz
    r30, g30, b30 = (_resample(tt, np.asarray(c, dtype=float)[keep], hz) for c in (roi.r, roi.g, roi.b))
    if r30.size >= _rhu(cfg.pos_window_s * hz):
        h = pos_pulse(r30, g30, b30, hz, cfg.pos_window_s)
        f, pxx = periodogram(h, hz)
        df = hz / _nfft(h.size)
        fpk = _spectral_peak(f, pxx, cfg.pulse_lo_hz, cfg.pulse_hi_hz, df)
        band = (f >= cfg.snr_lo_hz) & (f <= cfg.snr_hi_hz)
        if fpk is not None and np.any(pxx[band] > 0):
            out["pulse_bpm"] = 60.0 * fpk
            f0 = ref_hr_bpm / 60.0 if ref_hr_bpm is not None else fpk
            sig = band & ((np.abs(f - f0) <= cfg.snr_f0_halfwidth_hz) | (np.abs(f - 2.0 * f0) <= cfg.snr_h2_halfwidth_hz))
            s_pow = float(np.sum(pxx[sig]))
            n_pow = float(np.sum(pxx[band & ~sig]))
            out["snr_db"] = 99.0 if n_pow <= 0 else 10.0 * math.log10(max(s_pow, 1e-300) / n_pow)
        mu = float(h.mean())
        m2 = float(np.mean((h - mu) ** 2))
        if m2 > 0:
            out["skewness"] = float(np.mean((h - mu) ** 3)) / m2 ** 1.5
        gm = float(g30.mean())
        if gm >= 1.0:
            half = _rhu(hz) // 2
            cs = np.concatenate([[0.0], np.cumsum(g30)])
            i = np.arange(g30.size)
            lo = np.maximum(0, i - half)
            hi = np.minimum(g30.size, i + half + 1)
            ac = g30 - (cs[hi] - cs[lo]) / (hi - lo)
            out["perfusion_pct"] = 100.0 * (_quantile(ac, 0.95) - _quantile(ac, 0.05)) / gm
    return out


def score_video(roi: RoiSeries, frame_times_s, expected_seconds: float, ref_hr_bpm: float | None = None,
                cfg: VideoQualityConfig = VideoQualityConfig()) -> Grade:
    """Grade a palm clip from its ROI trace (and frame times when available). Rules in the module docstring."""
    m = _video_metrics(roi, frame_times_s, ref_hr_bpm, cfg)
    retake: list[str] = []
    border: list[str] = []
    dur = m["duration_s"]
    if roi.t_s.size == 0:
        retake.append("No video analysis rows were written")
    if expected_seconds > 0 and dur < cfg.min_duration_frac * expected_seconds:
        retake.append(f"Clip too short ({fmt(dur, 1)} s of {fmt(expected_seconds, 1)} s)")
    lvl, dark = m["mean_level"], m["dark_frac"]
    if lvl is not None and lvl < cfg.min_mean_level:
        retake.append(f"Too dark (level {fmt(lvl, 1)}): check the torch and that the palm covers the camera")
    elif dark is not None and dark > cfg.max_dark_frac:
        retake.append(f"Dark or black frames in {fmt(100.0 * dark, 0)}% of the clip")
    clip = m["clipped_frac"]
    if clip is not None and clip > cfg.retake_clipped_frac:
        retake.append(f"Overexposed: {fmt(100.0 * clip, 0)}% of the palm area clipped")
    elif clip is not None and clip > cfg.borderline_clipped_frac:
        border.append(f"Some overexposure: {fmt(100.0 * clip, 0)}% of the palm area clipped")
    drop = m["dropped_frac"]
    if drop is not None and drop > cfg.retake_dropped_frac:
        retake.append(f"Many dropped frames ({fmt(100.0 * drop, 1)}%)")
    elif drop is not None and drop > cfg.borderline_dropped_frac:
        border.append(f"Some dropped frames ({fmt(100.0 * drop, 1)}%)")
    snr = m["snr_db"]
    if snr is None:
        if roi.t_s.size > 0:
            retake.append("No pulse signal could be measured")
    elif snr < cfg.retake_snr_db:
        retake.append(f"No clear pulse in the video (SNR {fmt(snr, 1)} dB)")
    elif snr < cfg.borderline_snr_db:
        border.append(f"Weak pulse signal (SNR {fmt(snr, 1)} dB)")
    mot = m["motion"]
    if mot is not None and mot > cfg.borderline_motion:
        border.append(f"Hand or phone moved (frame-to-frame change {fmt(100.0 * mot, 1)}%)")
    pulse = m["pulse_bpm"]
    if ref_hr_bpm is not None and pulse is not None and abs(pulse - ref_hr_bpm) > cfg.max_ref_hr_diff_bpm:
        border.append(f"Video pulse {fmt(pulse, 0)} bpm differs from the reference {fmt(ref_hr_bpm, 0)} bpm")
    level = "retake" if retake else "borderline" if border else "good"
    return Grade(level, retake + border, m)


# --------------------------------------------------------------------------- ECG
def _integrated_energy(y: np.ndarray, fs: float) -> np.ndarray:
    n = y.size
    d = np.zeros(n)
    if n >= 5:
        d[2:n - 2] = (2.0 * y[3:n - 1] + y[4:n] - y[0:n - 4] - 2.0 * y[1:n - 3]) / 8.0
    s = d * d
    half = _rhu(0.150 * fs) // 2
    cs = np.concatenate([[0.0], np.cumsum(s)])
    i = np.arange(n)
    lo = np.maximum(0, i - half)
    hi = np.minimum(n, i + half + 1)
    return (cs[hi] - cs[lo]) / (hi - lo)


def _detect_on_filtered(y: np.ndarray, fs: float, with_polarity: bool = False):
    n = y.size
    if n < 5:
        return (np.zeros(0, dtype=np.int64), False) if with_polarity else np.zeros(0, dtype=np.int64)
    m = _integrated_energy(y, fs)
    peaks = [i for i in range(1, n - 1) if m[i] > m[i - 1] and m[i] >= m[i + 1]]
    w2 = _rhu(2.0 * fs)
    maxima = [float(np.max(m[s:s + w2])) for s in range(0, n, w2) if min(n, s + w2) - s >= w2 // 2]
    spki = _median(maxima) if maxima else float(np.max(m))
    npki = _median(m)
    thr = npki + 0.25 * (spki - npki)
    refr = _rhu(0.25 * fs)
    qrs: list[int] = []
    rr: list[int] = []
    pending: list[int] = []
    for p in peaks:
        if qrs and rr:
            recent = rr[-8:]
            rr_avg = sum(recent) / len(recent)
            if p - qrs[-1] > 1.66 * rr_avg:
                best = -1
                for c in pending:
                    if c - qrs[-1] > refr and m[c] > 0.5 * thr and (best < 0 or m[c] > m[best]):
                        best = c
                if best >= 0:
                    rr.append(best - qrs[-1])
                    qrs.append(best)
                    spki = 0.25 * m[best] + 0.75 * spki
                    pending = [c for c in pending if c > best]
                    thr = npki + 0.25 * (spki - npki)
        if qrs and p - qrs[-1] <= refr:
            continue
        if m[p] > thr:
            if qrs:
                rr.append(p - qrs[-1])
            qrs.append(p)
            spki = 0.125 * m[p] + 0.875 * spki
            pending = []
        else:
            npki = 0.125 * m[p] + 0.875 * npki
            pending.append(p)
        thr = npki + 0.25 * (spki - npki)
    r, inverted = _refine(y, fs, qrs)
    return (r, inverted) if with_polarity else r


def _refine(y: np.ndarray, fs: float, qrs: list[int]) -> tuple[np.ndarray, bool]:
    """One polarity for the whole record, then each R moved to the extreme of that sign within +/-75 ms.

    Beats closer than 75 ms to either end are dropped. Inverted when the median negative swing around the beats
    exceeds 1.5 x the median positive swing; a single sign keeps biphasic (RS) complexes aligned on the same wave
    instead of alternating between R and S.
    """
    n = y.size
    rw = _rhu(0.075 * fs)
    refr = _rhu(0.25 * fs)
    if not qrs:
        return np.zeros(0, dtype=np.int64), False
    pos, neg = [], []
    for p in qrs:
        lo, hi = max(0, p - rw), min(n, p + rw + 1)
        pos.append(float(np.max(y[lo:hi])))
        neg.append(-float(np.min(y[lo:hi])))
    inverted = _median(neg) > 1.5 * _median(pos)
    sy = -y if inverted else y
    refined = []
    for p in qrs:
        lo, hi = max(0, p - rw), min(n, p + rw + 1)
        refined.append(lo + int(np.argmax(sy[lo:hi])))
    refined.sort()
    out: list[int] = []
    for r in refined:
        if out and r - out[-1] < refr:
            if sy[r] > sy[out[-1]]:
                out[-1] = r
        else:
            out.append(r)
    out = [r for r in out if rw <= r <= n - 1 - rw]          # edge transients are not beats
    return np.asarray(out, dtype=np.int64), inverted


def detect_qrs(mv, fs: float) -> np.ndarray:
    """R-peak sample indices of a lead-I ECG in mV (band-passed 0.5-40 Hz first)."""
    return _detect_on_filtered(ecg_bandpass(mv, fs), fs)


def _irregularity(rr: np.ndarray) -> tuple[float, float, float, bool]:
    """Dash et al. 2009 on RR intervals (s): (rmssd_ratio, tpr, shannon, irregular)."""
    n = rr.size
    k = n // 16                                   # Dash trims 8 of 128 at each end
    order = np.argsort(rr, kind="stable")
    keep = np.sort(order[k:n - k])
    tr = rr[keep]
    diffs = np.diff(tr)
    rmssd = math.sqrt(float(np.mean(diffs * diffs))) if diffs.size else 0.0
    rmssd_ratio = rmssd / float(tr.mean())
    n_tp = sum(1 for i in range(1, n - 1) if (rr[i] - rr[i - 1]) * (rr[i + 1] - rr[i]) < 0)
    tpr = n_tp / (n - 2)
    mu = (2.0 * n - 4.0) / 3.0
    sigma = math.sqrt((16.0 * n - 29.0) / 90.0)
    tp_random = abs(n_tp - mu) <= 1.96 * sigma
    lo, hi = float(tr.min()), float(tr.max())
    if hi - lo <= 0:
        shannon = 0.0
    else:
        counts = [0] * 16
        for v in tr:
            counts[min(15, int(math.floor((v - lo) / (hi - lo) * 16.0)))] += 1
        shannon = 0.0
        for c in counts:
            if c:
                p = c / tr.size
                shannon -= p * math.log(p)
        shannon /= math.log(16.0)
    return rmssd_ratio, tpr, shannon, tp_random


def _ecg_analyse(mv, fs: float, cfg: EcgQualityConfig) -> tuple[dict, bool, float | None]:
    x = np.nan_to_num(np.asarray(mv, dtype=float), nan=0.0, posinf=0.0, neginf=0.0)
    n = x.size
    keys = ("duration_s", "hr_bpm", "n_beats", "rr_max_s", "rr_ratio", "template_corr", "ksqi", "flat_frac",
            "irregular_flag", "rmssd_ratio", "tpr", "shannon", "inverted")
    m: dict[str, float | None] = {k: None for k in keys}
    m["duration_s"] = n / fs if fs > 0 else 0.0
    m["n_beats"] = 0.0
    m["irregular_flag"] = 0.0
    m["inverted"] = 0.0
    if n == 0:
        m["flat_frac"] = 1.0
        return m, False, None
    y = ecg_bandpass(x, fs, cfg.band_lo_hz, cfg.band_hi_hz)
    r, inverted = _detect_on_filtered(y, fs, with_polarity=True)
    m["n_beats"] = float(r.size)
    m["inverted"] = 1.0 if inverted else 0.0
    w = _rhu(fs)
    nw = n // w if w > 0 else 0
    if nw == 0:
        m["flat_frac"] = 1.0 if float(x.max() - x.min()) < cfg.flat_ptp_mv else 0.0
    else:
        seg = x[:nw * w].reshape(nw, w)
        m["flat_frac"] = float(np.count_nonzero(seg.max(axis=1) - seg.min(axis=1) < cfg.flat_ptp_mv)) / nw
    mu = float(y.mean())
    m2 = float(np.mean((y - mu) ** 2))
    if m2 > 0:
        m["ksqi"] = float(np.mean((y - mu) ** 4)) / (m2 * m2)
    irregular = False
    rr_min = None
    if r.size >= 2:
        rr = np.diff(r) / fs
        rr_min = float(rr.min())
        m["hr_bpm"] = 60.0 / _median(rr)
        m["rr_max_s"] = float(rr.max())
        m["rr_ratio"] = float(rr.max()) / rr_min
        if rr.size >= cfg.min_rr_for_rhythm:
            rmssd_ratio, tpr, shannon, tp_random = _irregularity(rr)
            m["rmssd_ratio"], m["tpr"], m["shannon"] = rmssd_ratio, tpr, shannon
            irregular = (rmssd_ratio >= cfg.irregular_rmssd_ratio and tp_random
                         and shannon >= cfg.irregular_shannon)
            m["irregular_flag"] = 1.0 if irregular else 0.0
    pre, post = _rhu(0.25 * fs), _rhu(0.45 * fs)
    beats = [y[i - pre:i + post] for i in r if i - pre >= 0 and i + post <= n]
    if len(beats) >= 3:
        b = np.asarray(beats)
        tmpl = np.array([_median(b[:, j]) for j in range(b.shape[1])])
        tc = tmpl - tmpl.mean()
        tss = float(np.sum(tc * tc))
        if tss > 0:
            cors = []
            for beat in b:
                bc = beat - beat.mean()
                den = math.sqrt(float(np.sum(bc * bc)) * tss)
                cors.append(float(np.sum(bc * tc)) / den if den > 0 else 0.0)
            m["template_corr"] = float(np.mean(cors))
    return m, irregular, rr_min


def _ecg_grade(m: dict, irregular: bool, cfg: EcgQualityConfig) -> tuple[str, list[str]]:
    retake: list[str] = []
    border: list[str] = []
    if m["duration_s"] < cfg.min_duration_s:
        retake.append(f"ECG too short ({fmt(m['duration_s'], 1)} s, need {fmt(cfg.min_duration_s, 0)} s)")
    flat = m["flat_frac"]
    if flat > cfg.retake_flat_frac:
        retake.append(f"Flat line in {fmt(100.0 * flat, 0)}% of the recording: fingers off the electrodes?")
    elif flat > cfg.borderline_flat_frac:
        border.append(f"Flat line in {fmt(100.0 * flat, 0)}% of the recording")
    nb = int(m["n_beats"])
    if nb < cfg.min_beats:
        retake.append(f"Too few beats detected ({nb})")
    tcor = m["template_corr"]
    if tcor is not None and tcor < cfg.retake_template_corr:
        retake.append(f"Beats do not look alike (template match {fmt(tcor, 2)}): noise or movement")
    elif tcor is not None and tcor < cfg.borderline_template_corr:
        border.append(f"Noisy beats (template match {fmt(tcor, 2)})")
    hr = m["hr_bpm"]
    if hr is not None and (hr < cfg.retake_hr_lo or hr > cfg.retake_hr_hi):
        retake.append(f"Heart rate out of range ({fmt(hr, 0)} bpm): beats probably mis-detected")
    elif hr is not None and (hr < cfg.borderline_hr_lo or hr > cfg.borderline_hr_hi):
        border.append(f"Heart rate {fmt(hr, 0)} bpm is outside {fmt(cfg.borderline_hr_lo, 0)}-"
                      f"{fmt(cfg.borderline_hr_hi, 0)} bpm")
    ks = m["ksqi"]
    if ks is not None and ks < cfg.min_ksqi:
        border.append(f"Noisy baseline (kurtosis {fmt(ks, 1)})")
    rrmax = m["rr_max_s"]
    if rrmax is not None and rrmax > cfg.max_rr_s:
        border.append(f"Long gap between beats ({fmt(rrmax, 1)} s)")
    ratio = m["rr_ratio"]
    if ratio is not None and not irregular and ratio > cfg.max_rr_ratio:
        border.append(f"Uneven beat detection (longest/shortest interval {fmt(ratio, 1)})")
    return ("retake" if retake else "borderline" if border else "good"), retake + border


def score_ecg(mv, fs: float, cfg: EcgQualityConfig = EcgQualityConfig()) -> Grade:
    """Grade a lead-I ECG (mV at fs Hz). Rules in the module docstring; the irregular flag never lowers the grade."""
    m, irregular, _ = _ecg_analyse(mv, fs, cfg)
    level, reasons = _ecg_grade(m, irregular, cfg)
    return Grade(level, reasons, m)


def summarise_ecg(mv, fs: float, cfg: EcgQualityConfig = EcgQualityConfig()) -> RhythmSummary:
    """Participant-friendly rhythm summary: heart rate, regular / irregular / insufficient, plain sentences.

    Never names a rhythm; "irregular" means the beat spacing varied (Dash et al. 2009 screening heuristic).
    """
    m, irregular, rr_min = _ecg_analyse(mv, fs, cfg)
    level, _ = _ecg_grade(m, irregular, cfg)
    hr = m["hr_bpm"]
    if level == "retake" or hr is None or m["rmssd_ratio"] is None:
        rhythm = "insufficient"
        sentences = ["The recording was not clear enough to measure the heart rate and rhythm.",
                     "This often happens when the fingers move or do not rest fully on the sensor."]
    else:
        rhythm = "irregular" if irregular else "regular"
        first = f"Your heart rate during the recording was about {fmt(hr, 0)} beats per minute."
        if irregular:
            second = ("The time between beats varied more than usual, so a study doctor will look at this "
                      "recording closely.")
        else:
            second = "The beats came at a steady pace."
        sentences = [first, second]
    return RhythmSummary(hr_bpm=None if rhythm == "insufficient" else hr, rhythm=rhythm,
                         inverted=m["inverted"] == 1.0, n_beats=int(m["n_beats"]), rr_min_s=rr_min, rr_max_s=m["rr_max_s"],
                         irregular_flag=irregular, sentences=sentences + [CLOSING_SENTENCE])


# --------------------------------------------------------------------------- Kardia PDF (vector trace reader)
class _Name(str):
    pass


class _Kw(str):
    pass


@dataclass(frozen=True)
class _Ref:
    num: int
    gen: int


_WS = b"\x00\t\n\x0c\r "
_DELIM = b"()<>[]{}/%"
_NUM_RE = re.compile(rb"[+-]?(?:\d+\.?\d*|\.\d+)")
_INT_RE = re.compile(rb"\d+")
_ESC = {ord("n"): 10, ord("r"): 13, ord("t"): 9, ord("b"): 8, ord("f"): 12}


class _Lexer:
    """PDF tokens: ("d", "<<" | ">>" | "[" | "]" | "{" | "}"), ("n", name), ("s", bytes), ("r", regular bytes)."""

    def __init__(self, data: bytes, pos: int = 0, end: int | None = None):
        self.data = data
        self.pos = pos
        self.end = len(data) if end is None else end

    def next(self):
        d, n = self.data, self.end
        while True:
            while self.pos < n and d[self.pos] in _WS:
                self.pos += 1
            if self.pos >= n:
                return None
            c = d[self.pos]
            if c == 0x25:                                  # % comment
                while self.pos < n and d[self.pos] not in (10, 13):
                    self.pos += 1
                continue
            break
        if c == 0x2F:                                      # /name
            p = self.pos + 1
            while p < n and d[p] not in _WS and d[p] not in _DELIM:
                p += 1
            raw = d[self.pos + 1:p]
            self.pos = p
            return ("n", _Name(re.sub(rb"#([0-9A-Fa-f]{2})", lambda mm: bytes([int(mm.group(1), 16)]),
                                      raw).decode("latin-1")))
        if c == 0x28:                                      # (literal string)
            return ("s", self._literal())
        if c == 0x3C:                                      # < or <<
            if self.pos + 1 < n and d[self.pos + 1] == 0x3C:
                self.pos += 2
                return ("d", "<<")
            p = d.find(b">", self.pos + 1, n)
            p = n if p < 0 else p
            hexs = bytes(ch for ch in d[self.pos + 1:p] if ch not in _WS)
            self.pos = min(n, p + 1)
            if len(hexs) % 2:
                hexs += b"0"
            try:
                return ("s", bytes.fromhex(hexs.decode("latin-1")))
            except ValueError:
                return ("s", b"")
        if c == 0x3E:                                      # >> (a lone > is skipped)
            if self.pos + 1 < n and d[self.pos + 1] == 0x3E:
                self.pos += 2
                return ("d", ">>")
            self.pos += 1
            return self.next()
        if c in b"[]{}":
            self.pos += 1
            return ("d", chr(c))
        if c == 0x29:                                      # stray )
            self.pos += 1
            return self.next()
        p = self.pos
        while p < n and d[p] not in _WS and d[p] not in _DELIM:
            p += 1
        raw = d[self.pos:p]
        self.pos = p
        return ("r", raw)

    def _literal(self) -> bytes:
        d, n = self.data, self.end
        p = self.pos + 1
        depth = 1
        out = bytearray()
        while p < n:
            c = d[p]
            if c == 0x5C:                                  # backslash
                p += 1
                if p >= n:
                    break
                e = d[p]
                if e in _ESC:
                    out.append(_ESC[e])
                    p += 1
                elif 0x30 <= e <= 0x37:
                    q = p
                    while q < n and q < p + 3 and 0x30 <= d[q] <= 0x37:
                        q += 1
                    out.append(int(d[p:q], 8) & 0xFF)
                    p = q
                elif e == 13:
                    p += 2 if p + 1 < n and d[p + 1] == 10 else 1
                elif e == 10:
                    p += 1
                else:
                    out.append(e)
                    p += 1
                continue
            if c == 0x28:
                depth += 1
            elif c == 0x29:
                depth -= 1
                if depth == 0:
                    p += 1
                    break
            out.append(c)
            p += 1
        self.pos = p
        return bytes(out)


def _value(tok, lx: _Lexer, refs: bool):
    if tok is None:
        return None
    kind, v = tok
    if kind == "d":
        if v == "<<":
            out = {}
            while True:
                t = lx.next()
                if t is None or t == ("d", ">>"):
                    return out
                if t[0] == "n":
                    out[str(t[1])] = _value(lx.next(), lx, refs)
        if v == "[":
            arr = []
            while True:
                t = lx.next()
                if t is None or t == ("d", "]"):
                    return arr
                arr.append(_value(t, lx, refs))
        return _Kw(v)
    if kind in ("n", "s"):
        return v
    if _NUM_RE.fullmatch(v):
        if refs and _INT_RE.fullmatch(v):
            save = lx.pos
            t2 = lx.next()
            if t2 is not None and t2[0] == "r" and _INT_RE.fullmatch(t2[1]):
                t3 = lx.next()
                if t3 == ("r", b"R"):
                    return _Ref(int(v), int(t2[1]))
            lx.pos = save
        return float(v)
    if v == b"true":
        return True
    if v == b"false":
        return False
    if v == b"null":
        return None
    return _Kw(v.decode("latin-1"))


class _PdfDoc:
    _OBJ_RE = re.compile(rb"(\d+)\s+(\d+)\s+obj\b")

    def __init__(self, data: bytes):
        self.data = data
        self.objs: dict[int, tuple[object, bytes | None]] = {}
        self.warnings: list[str] = []
        skip_until = 0
        for mt in self._OBJ_RE.finditer(data):
            if mt.start() < skip_until:
                continue
            lx = _Lexer(data, mt.end())
            val = _value(lx.next(), lx, True)
            raw = None
            p = lx.pos
            while p < len(data) and data[p] in _WS:
                p += 1
            if data.startswith(b"stream", p) and isinstance(val, dict):
                p += 6
                if data.startswith(b"\r\n", p):
                    p += 2
                elif p < len(data) and data[p] in (10, 13):
                    p += 1
                length = val.get("Length")
                end = -1
                if isinstance(length, float) and 0 <= length <= len(data) - p:
                    e = p + int(length)
                    q = e
                    while q < len(data) and data[q] in _WS:
                        q += 1
                    if data.startswith(b"endstream", q):
                        end = e
                if end < 0:
                    e = data.find(b"endstream", p)
                    e = len(data) if e < 0 else e
                    if data[e - 2:e] == b"\r\n":
                        e -= 2
                    elif e > p and data[e - 1] in (10, 13):
                        e -= 1
                    end = e
                raw = data[p:end]
                skip_until = end
            self.objs[int(mt.group(1))] = (val, raw)
        for num, (val, raw) in list(self.objs.items()):
            if isinstance(val, dict) and val.get("Type") == "ObjStm" and raw is not None:
                body = self.decode(val, raw)
                if body is None:
                    continue
                first = int(val.get("First", 0) or 0)
                count = int(val.get("N", 0) or 0)
                lx = _Lexer(body, 0, min(first, len(body)))
                pairs = []
                for _ in range(count):
                    a, b = lx.next(), lx.next()
                    if a is None or b is None:
                        break
                    try:
                        pairs.append((int(a[1]), int(b[1])))
                    except (ValueError, TypeError):
                        break
                for onum, off in pairs:
                    if onum not in self.objs:
                        lx2 = _Lexer(body, first + off)
                        self.objs[onum] = (_value(lx2.next(), lx2, True), None)

    def resolve(self, v):
        depth = 0
        while isinstance(v, _Ref) and depth < 32:
            v = self.objs.get(v.num, (None, None))[0]
            depth += 1
        return v

    def decode(self, d: dict, raw: bytes) -> bytes | None:
        filt = self.resolve(d.get("Filter"))
        names = [str(self.resolve(f)) for f in filt] if isinstance(filt, list) else ([str(filt)] if filt else [])
        if not names:
            return raw
        if names != ["FlateDecode"]:
            self.warnings.append(f"stream filter {'/'.join(names)} not supported: stream skipped")
            return None
        parms = self.resolve(d.get("DecodeParms"))
        if isinstance(parms, list):
            parms = self.resolve(parms[0]) if parms else None
        if isinstance(parms, dict) and float(self.resolve(parms.get("Predictor", 1)) or 1) > 1:
            self.warnings.append("stream predictor not supported: stream skipped")
            return None
        z = zlib.decompressobj()
        try:
            return z.decompress(raw) + z.flush()
        except zlib.error:
            self.warnings.append("damaged compressed stream skipped")
            return None

    def stream_of(self, ref) -> tuple[dict, bytes] | None:
        if not isinstance(ref, _Ref):
            return None
        val, raw = self.objs.get(ref.num, (None, None))
        if not isinstance(val, dict) or raw is None:
            return None
        body = self.decode(val, raw)
        return None if body is None else (val, body)

    def pages(self) -> list[tuple[dict, dict | None]]:
        out: list[tuple[dict, dict | None]] = []
        cat = None
        for num in sorted(self.objs):
            val = self.objs[num][0]
            if isinstance(val, dict) and val.get("Type") == "Catalog":
                cat = val
        seen: set[int] = set()

        def walk(node_ref, inherited):
            node = self.resolve(node_ref)
            if isinstance(node_ref, _Ref):
                if node_ref.num in seen:
                    return
                seen.add(node_ref.num)
            if not isinstance(node, dict):
                return
            res = self.resolve(node.get("Resources")) if "Resources" in node else inherited
            kids = self.resolve(node.get("Kids"))
            if isinstance(kids, list):
                for k in kids:
                    walk(k, res)
            elif node.get("Type") == "Page" or "Contents" in node:
                out.append((node, res))

        if cat is not None:
            walk(cat.get("Pages"), None)
        if not out:
            for num in sorted(self.objs):
                val = self.objs[num][0]
                if isinstance(val, dict) and val.get("Type") == "Page":
                    out.append((val, self.resolve(val.get("Resources"))))
        return out


def _mul(m, n):
    a, b, c, d, e, f = m
    A, B, C, D, E, F = n
    return (a * A + b * C, a * B + b * D, c * A + d * C, c * B + d * D, e * A + f * C + E, e * B + f * D + F)


def _lum(vals) -> bool | None:
    """True when a stroke colour is dark (luminance <= 0.5), None when unknown."""
    if len(vals) == 1:
        return vals[0] <= 0.5
    if len(vals) == 3:
        return 0.299 * vals[0] + 0.587 * vals[1] + 0.114 * vals[2] <= 0.5
    if len(vals) == 4:
        c, m, y, k = vals
        return 0.299 * (1 - c) * (1 - k) + 0.587 * (1 - m) * (1 - k) + 0.114 * (1 - y) * (1 - k) <= 0.5
    return None


class _Painter:
    """Runs content streams: keeps stroked subpaths in device space and the text of each BT..ET block."""

    STROKE = {"S", "s", "B", "B*", "b", "b*"}
    PAINT = STROKE | {"f", "F", "f*", "n"}

    def __init__(self, doc: _PdfDoc):
        self.doc = doc
        self.paths: list[tuple[int, list[tuple[float, float]], float]] = []
        self.text: list[list[str]] = []

    def run(self, content: bytes, resources, ctm, page: int, depth: int = 0) -> None:
        if depth > 8:
            return
        while len(self.text) <= page:
            self.text.append([])
        lx = _Lexer(content)
        ops: list = []
        lw, dark = 1.0, True
        stack: list = []
        subs: list[list[tuple[float, float]]] = []
        cur: list[tuple[float, float]] | None = None
        bt: list[str] | None = None

        def pt(x, y):
            return (ctm[0] * x + ctm[2] * y + ctm[4], ctm[1] * x + ctm[3] * y + ctm[5])

        def nums(k):
            vals = ops[-k:] if len(ops) >= k else []
            return [float(v) for v in vals] if len(vals) == k and all(isinstance(v, float) for v in vals) else None

        while True:
            tok = lx.next()
            if tok is None:
                break
            if tok[0] == "r" and not _NUM_RE.fullmatch(tok[1]) and tok[1] not in (b"true", b"false", b"null"):
                op = tok[1].decode("latin-1")
            else:
                ops.append(_value(tok, lx, False))
                continue
            if op == "BI":                                 # inline image: skip its binary data
                mt = re.compile(rb"\sID[\s]").search(content, lx.pos)
                if mt:
                    me = re.compile(rb"\sEI(?=[\s/<\[]|$)").search(content, mt.end())
                    lx.pos = me.end() if me else len(content)
            elif op == "q":
                stack.append((ctm, lw, dark))
            elif op == "Q":
                if stack:
                    ctm, lw, dark = stack.pop()
            elif op == "cm":
                v = nums(6)
                if v:
                    ctm = _mul(tuple(v), ctm)
            elif op == "w":
                v = nums(1)
                if v:
                    lw = v[0]
            elif op in ("G", "RG", "K"):
                v = nums({"G": 1, "RG": 3, "K": 4}[op])
                if v:
                    dark = bool(_lum(v))
            elif op == "CS":
                dark = True
            elif op in ("SC", "SCN"):
                if ops and all(isinstance(v, float) for v in ops):
                    lu = _lum([float(v) for v in ops])
                    dark = True if lu is None else lu
            elif op == "m":
                v = nums(2)
                if v:
                    cur = [pt(v[0], v[1])]
                    subs.append(cur)
            elif op in ("l", "c", "v", "y"):
                v = nums({"l": 2, "c": 6, "v": 4, "y": 4}[op])
                if v:
                    x, y = (v[0], v[1]) if op == "l" else (v[2], v[3]) if op in ("v", "y") else (v[4], v[5])
                    if cur is None:
                        cur = []
                        subs.append(cur)
                    cur.append(pt(x, y))
            elif op == "re":
                v = nums(4)
                if v:
                    x, y, w, h = v
                    subs.append([pt(x, y), pt(x + w, y), pt(x + w, y + h), pt(x, y + h), pt(x, y)])
                    cur = None
            elif op == "h":
                if cur and len(cur) > 1 and cur[-1] != cur[0]:
                    cur.append(cur[0])
                cur = None
            elif op in self.PAINT:
                if op in ("s", "b", "b*") and cur and len(cur) > 1 and cur[-1] != cur[0]:
                    cur.append(cur[0])
                if op in self.STROKE and dark:
                    scale = math.sqrt(abs(ctm[0] * ctm[3] - ctm[1] * ctm[2]))
                    for sp in subs:
                        if len(sp) >= 2:
                            self.paths.append((page, sp, lw * scale))
                subs, cur = [], None
            elif op == "BT":
                bt = []
            elif op == "ET":
                if bt is not None:
                    line = "".join(bt).strip()
                    if line:
                        self.text[page].append(line)
                bt = None
            elif op in ("Tj", "'", '"'):
                if bt is not None and ops and isinstance(ops[-1], bytes):
                    bt.append(ops[-1].decode("latin-1"))
            elif op == "TJ":
                if bt is not None and ops and isinstance(ops[-1], list):
                    for el in ops[-1]:
                        if isinstance(el, bytes):
                            bt.append(el.decode("latin-1"))
                        elif isinstance(el, float) and el < -200:
                            bt.append(" ")
            elif op == "Do":
                if ops and isinstance(ops[-1], _Name):
                    self._form(str(ops[-1]), resources, ctm, page, depth)
            ops = []

    def _form(self, name: str, resources, ctm, page: int, depth: int) -> None:
        res = self.doc.resolve(resources)
        xo = self.doc.resolve(res.get("XObject")) if isinstance(res, dict) else None
        ref = xo.get(name) if isinstance(xo, dict) else None
        st = self.doc.stream_of(ref)
        if st is None or st[0].get("Subtype") != "Form":
            return
        mat = self.doc.resolve(st[0].get("Matrix"))
        m = tuple(float(v) for v in mat) if isinstance(mat, list) and len(mat) == 6 else (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
        fres = self.doc.resolve(st[0].get("Resources")) if "Resources" in st[0] else res
        self.run(st[1], fres, _mul(m, ctm), page, depth + 1)


def _trace_step(pts) -> float | None:
    """Median x step of a polyline that looks like a sampled trace (>= 20 points, x strictly rising in
    near-equal steps of 0.05-1 pt; exact repeats allowed), else None."""
    if len(pts) < 20:
        return None
    steps = [pts[i + 1][0] - pts[i][0] for i in range(len(pts) - 1)]
    nz = [s for s in steps if abs(s) > 1e-6]
    if len(nz) < 0.9 * len(steps) or any(s <= 0 for s in nz):
        return None
    med = _median(nz)
    if not 0.05 <= med <= 1.0 or any(abs(s - med) > 0.2 * med for s in nz):
        return None
    return med


def _cal_height(pts) -> float | None:
    """Height (pt) of a calibration pulse: 4-8 axis-aligned points, base -> up -> plateau -> base."""
    if not 4 <= len(pts) <= 8:
        return None
    for i in range(len(pts) - 1):
        dx, dy = pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]
        if dx < -0.01 or (abs(dx) > 0.01 and abs(dy) > 0.01):
            return None
    base = pts[0][1]
    if abs(pts[-1][1] - base) > 0.5:
        return None
    top = max(p[1] for p in pts)
    height = top - base
    width = pts[-1][0] - pts[0][0]
    plateau = [p[0] for p in pts if abs(p[1] - top) < 0.01]
    if not 2 * MM <= height <= 40 * MM or width > 25 * MM or max(plateau) - min(plateau) < 1 * MM:
        return None
    return height


def _page_text_fields(text: str, tr: EcgTrace) -> tuple[float | None, float | None, float | None]:
    m = re.search(r"Kardia Determination:\s*([^\n]*)", text)
    if m:
        det = m.group(1).strip()
        if not det:
            rest = text[m.end():].lstrip()
            det = rest.split("\n", 1)[0].strip() if rest else ""
        tr.determination = det or None
    m = re.search(r"Heart Rate:\s*(\d{2,3})\s*BPM", text, re.I)
    if m:
        tr.hr_bpm = int(m.group(1))
    m = re.search(r"Mains Frequency:\s*(50|60)\s*Hz", text)
    if m:
        tr.mains_hz = int(m.group(1))
    if "Enhanced Filter" in text:
        tr.enhanced_filter = True
    elif "Original Filter" in text:
        tr.enhanced_filter = False
    speed = gain = dur = None
    m = re.search(r"(\d+(?:\.\d+)?)\s*mm/s", text)
    if m:
        speed = float(m.group(1))
    m = re.search(r"(\d+(?:\.\d+)?)\s*mm/mV", text)
    if m:
        gain = float(m.group(1))
    m = re.search(r"Duration:\s*(\d+)\s*s\b", text)
    if m:
        dur = float(m.group(1))
    return speed, gain, dur


def read_kardia_pdf(source: bytes | str | os.PathLike) -> EcgTrace:
    """Kardia PDF export -> lead-I ECG in mV at 300 Hz from the vector trace (no rasterising).

    Keeps stroked dark polylines that look like a sampled trace, drops the calibration pulse, beat ticks, grid and
    baselines, groups the trace into strips per page (8 mm y gap), orders them top to bottom and page by page, maps
    each point to a sample index from its x position, converts to mV against the strip's baseline with the measured
    calibration pulse (else the printed scale, else 10 mm/mV) and concatenates. A 6-lead export keeps the top strip
    (lead I) of each page. Everything assumed is listed in `warnings`. Raises ValueError when no trace is found.
    """
    data = bytes(source) if isinstance(source, (bytes, bytearray)) else Path(source).read_bytes()
    if not data.startswith(b"%PDF"):
        raise ValueError("not a PDF file")
    doc = _PdfDoc(data)
    painter = _Painter(doc)
    pages = doc.pages()
    for i, (page, res) in enumerate(pages):
        c = page.get("Contents")
        rv = doc.resolve(c)
        refs = rv if isinstance(rv, list) else [c] if isinstance(c, _Ref) else []
        body = b""
        for ref in refs:
            st = doc.stream_of(ref)
            if st is not None:
                body += st[1] + b"\n"
        painter.run(body, res, (1.0, 0.0, 0.0, 1.0, 0.0, 0.0), i)
    tr = EcgTrace(fs=300.0, mv=np.zeros(0), warnings=list(doc.warnings))
    text = "\n".join("\n".join(lines) for lines in painter.text)
    speed, gain, dur = _page_text_fields(text, tr)
    return _assemble_trace(painter.paths, text, speed, gain, dur, tr)


def _assemble_trace(paths, text: str, speed, gain, dur, tr: EcgTrace) -> EcgTrace:
    cands: list[tuple[int, list, float]] = []
    cals: list[float] = []
    hlines: list[tuple[int, float, float, float]] = []
    for page, pts, _lw in paths:
        step = _trace_step(pts)
        if step is not None:
            cands.append((page, pts, step))
            continue
        h = _cal_height(pts)
        if h is not None:
            cals.append(h)
            continue
        if len(pts) == 2 and abs(pts[0][1] - pts[1][1]) < 0.01 and abs(pts[1][0] - pts[0][0]) > 100:
            hlines.append((page, pts[0][1], min(pts[0][0], pts[1][0]), max(pts[0][0], pts[1][0])))
    if not cands:
        raise ValueError("no ECG trace found in the PDF")
    all_steps = []
    for _page, pts, _s in cands:
        all_steps.extend(s for s in (pts[i + 1][0] - pts[i][0] for i in range(len(pts) - 1)) if abs(s) > 1e-6)
    dx = _median(all_steps)

    strips: list[tuple[int, list]] = []
    multi_lead = re.search(r"\baV[RLF]\b", text) is not None
    warn_multi = False
    for page in sorted({c[0] for c in cands}):
        here = sorted(((_median([p[1] for p in pts]), pts) for pg, pts, _s in cands if pg == page),
                      key=lambda e: -e[0])
        groups: list[list] = []
        last = None
        for yc, pts in here:
            if last is None or last - yc > 8 * MM:
                groups.append([])
            groups[-1].append(pts)
            last = yc
        if multi_lead or len(groups) == 6:
            groups = groups[:1]
            warn_multi = True
        strips.extend((page, g) for g in groups)
    if warn_multi:
        tr.warnings.append("multi-lead layout: lead I taken from the top strip of each page")

    if cals:
        pt_per_mv = _median(cals)
        if gain is not None and abs(pt_per_mv - gain * MM) > 0.1 * gain * MM:
            tr.warnings.append(f"calibration pulse ({fmt(pt_per_mv / MM, 1)} mm) differs from the printed "
                               f"scale ({fmt(gain, 1)} mm/mV): pulse used")
    elif gain is not None:
        pt_per_mv = gain * MM
        tr.warnings.append(f"no calibration pulse: printed scale {fmt(gain, 1)} mm/mV used")
    else:
        pt_per_mv = 10.0 * MM
        tr.warnings.append("no calibration pulse or printed scale: 10 mm/mV assumed")
    if speed is None:
        speed = 25.0
        tr.warnings.append("paper speed not printed: 25 mm/s assumed")
    fs_meas = speed * MM / dx
    if abs(fs_meas - 300.0) <= 0.02 * 300.0:
        fs = 300.0
    else:
        fs = fs_meas
        tr.warnings.append(f"sample spacing gives {fmt(fs_meas, 1)} Hz, not the Kardia 300 Hz: measured rate used")

    out: list[float] = []
    gaps = 0
    no_base = 0
    for page, group in strips:
        pts = sorted((p for g in group for p in g), key=lambda p: p[0])
        x0 = pts[0][0]
        vals: dict[int, float] = {}
        for x, y in pts:
            k = int(math.floor((x - x0) / dx + 0.5))
            if k not in vals:
                vals[k] = y
        kmax = max(vals)
        ys = [0.0] * (kmax + 1)
        known = sorted(vals)
        for a, b in zip(known[:-1], known[1:]):
            ys[a] = vals[a]
            for k in range(a + 1, b):
                gaps += 1
                ys[k] = vals[a] + (vals[b] - vals[a]) * (k - a) / (b - a)
        ys[kmax] = vals[kmax]
        ymed = _median(ys)
        xs_lo, xs_hi = x0, pts[-1][0]
        near = [(abs(hy - ymed), hy) for pg, hy, hx0, hx1 in hlines
                if pg == page and hx0 <= xs_hi and hx1 >= xs_lo and abs(hy - ymed) <= 10 * MM]
        if near:
            zero = min(near)[1]
        else:
            zero = ymed
            no_base += 1
        out.extend((v - zero) / pt_per_mv for v in ys)
    if gaps:
        tr.warnings.append(f"{gaps} missing sample(s) interpolated")
    if no_base:
        tr.warnings.append(f"no baseline found for {no_base} strip(s): strip median used as 0 mV")
    if dur is not None and abs(len(out) / fs - dur) > 1.0:
        tr.warnings.append(f"recovered {fmt(len(out) / fs, 1)} s but the page says {fmt(dur, 0)} s")
    tr.fs = fs
    tr.mv = np.asarray(out, dtype=float)
    return tr
