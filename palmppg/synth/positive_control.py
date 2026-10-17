"""Positive control: inject a known pulse into static frames and score what a pipeline recovers.

Protocol section 8: "inject a known pulse (0.3 to 1.0 percent AC/DC in G, realistic morphology, HR 50 to 120,
with HRV) into static palm frames; the pipeline must recover HR within 1 bpm and the injected morphology
parameters within tolerance, on Pi raw and after CRF-28 compression." Run-order step 1 (section 12).

`inject_known_pulse` modulates frames multiplicatively in linear light: G planes at `ac_dc_g` (peak-to-peak
AC/DC), R and B at `ac_ratios` times that, optionally weighted by a perfusion map. `score_recovery` compares a
recovered {hr_bpm, foot_times, morphology} against the truth with tolerances from cfg `synth.positive_control`
(defaults: 1 bpm, one frame period on the median foot error, 20 % on each morphology parameter).
`reference_recovery` is a small, honest extractor (dense-DFT rate at the true sample times, foot detection,
foot-aligned ensemble morphology) so the control can be exercised without the pulse and beats packages; the
integrator wires the real pipeline in its place.
"""
from __future__ import annotations

import math
from typing import Iterable, Iterator

import numpy as np

from palmppg.synth.augment import Frame
from palmppg.synth.palm_scene import _ratio_tuple
from palmppg.synth.pulse_wave import MEASURED_KEYS, _measure_curve, waveform_from_truth

DEFAULT_TOLERANCES = {"hr_bpm": 1.0, "foot_median_frames": 1.0, "morphology_rel": 0.20}
MORPHOLOGY_SCORED = ("upstroke_s", "systolic_width_s", "notch_time_s", "reflection_index", "decay_tau_s")


def tolerances(cfg=None) -> dict:
    """Positive-control tolerances: cfg synth.positive_control when present, else DEFAULT_TOLERANCES."""
    if cfg is None:
        return dict(DEFAULT_TOLERANCES)
    out = dict(DEFAULT_TOLERANCES)
    out.update(cfg.get("synth.positive_control", {}) or {})
    return out


# ----------------------------------------------------------------------------- injection
def inject_known_pulse(frames: Iterable[Frame], pulse_truth: dict, ac_dc_g: float, ac_ratios: dict | tuple = (0.5, 1.0, 0.6),
                       ac_map: np.ndarray | None = None, rng: np.random.Generator | None = None) -> Iterator[Frame]:
    """Yield frames with `DC * (1 - ac_dc_g * ratio_c * ac_map * W(t))` applied in linear light.

    `pulse_truth` is a dict from pulse_wave.generate_pulse (foot_t, morphology, schedule). `ac_map` is a
    full-resolution (h, w) weight map (1 = full amplitude); for Bayer frames it is sampled per plane. Integer
    frames are re-quantised with a seeded +/- 0.5 DN dither (`rng`, default rng(0, "inject")) so the
    sub-DN modulation is not rounded coherently across pixels.
    """
    if rng is None:
        from palmppg.core.config import rng as _rng

        rng = _rng(0, "inject")
    rt = _ratio_tuple(ac_ratios)
    amap_planes = None
    for f in frames:
        w = float(waveform_from_truth(pulse_truth, np.array([f.t_s]))[0])
        lin = f.linear()
        if f.kind == "bayer":
            gains = np.array([rt[0], rt[1], rt[1], rt[2]], np.float32)[:, None, None] * ac_dc_g
            if ac_map is not None:
                if amap_planes is None:
                    m = np.asarray(ac_map, np.float32)
                    amap_planes = np.stack([m[0::2, 0::2], m[0::2, 1::2], m[1::2, 0::2], m[1::2, 1::2]])
                gains = gains * amap_planes
        else:
            gains = np.asarray(rt, np.float32)[None, None, :] * ac_dc_g
            if ac_map is not None:
                gains = gains * np.asarray(ac_map, np.float32)[..., None]
        out = f.with_linear(lin * (1.0 - gains * w), dither=rng)
        out.meta["injected_w"] = w
        yield out


def _fit_mask(m: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    """Nearest-neighbour resize of a bool mask to a frame shape (half-resolution proxies, downscaled frames)."""
    if m.shape == tuple(shape):
        return m
    import cv2

    return cv2.resize(m.astype(np.uint8), (int(shape[1]), int(shape[0])), interpolation=cv2.INTER_NEAREST).astype(bool)


def extract_region_trace(frames: Iterable[Frame], mask: np.ndarray, channel: str = "G1") -> tuple[np.ndarray, np.ndarray, list[int]]:
    """Mean of `channel` within `mask` per frame, in linear light -> (t_s, values, frame_idx).

    `mask` is a full-resolution (h, w) bool; it is sampled per plane for Bayer frames and resized (nearest) when
    the frame is a half-resolution proxy or was downscaled. `channel` in R, G1, G2, B or G (mean of both green
    planes) for Bayer frames; R, G, B for rgb frames.
    """
    m = np.asarray(mask, bool)
    t, v, idx = [], [], []
    for f in frames:
        lin = f.linear()
        if f.kind == "bayer":
            if channel == "G":                                   # mean of both green planes
                sel = _fit_mask(m[0::2, 1::2], lin.shape[1:])
                val = float(0.5 * (lin[1][sel].mean() + lin[2][_fit_mask(m[1::2, 0::2], lin.shape[1:])].mean()))
            else:
                plane = {"R": (0, 0), "G1": (0, 1), "G2": (1, 0), "B": (1, 1)}[channel]
                sel = _fit_mask(m[plane[0]::2, plane[1]::2], lin.shape[1:])
                val = float(lin[("R", "G1", "G2", "B").index(channel)][sel].mean())
        else:
            c = {"R": 0, "G": 1, "G1": 1, "G2": 1, "B": 2}[channel]
            val = float(lin[..., c][_fit_mask(m, lin.shape[:2])].mean())
        t.append(f.t_s)
        v.append(val)
        idx.append(f.idx)
    return np.asarray(t), np.asarray(v), idx


# ----------------------------------------------------------------------------- reference recovery
def _highpass_trace(t: np.ndarray, x: np.ndarray, degree: int = 3) -> np.ndarray:
    """Remove the slow baseline of a 1-D trace with a low-order polynomial fit at the true sample times (a
    trace-level operation of the reference extractor, never applied to frames; no temporal smoothing)."""
    tt = t - t[0]
    return x - np.polyval(np.polyfit(tt, x, degree), tt)


def dense_dft_rate(t_s: np.ndarray, x: np.ndarray, band_hz: tuple[float, float], step_bpm: float = 0.1) -> float:
    """Rate (bpm) of the strongest line in `band_hz`, from a DFT evaluated at the true sample times (no
    resampling), on a `step_bpm` grid. Works with dropped or jittered frames."""
    t = np.asarray(t_s, float)
    x = _highpass_trace(t, np.asarray(x, float))
    bpm = np.arange(band_hz[0] * 60.0, band_hz[1] * 60.0 + step_bpm, step_bpm)
    f = bpm / 60.0
    ph = np.exp(-2j * math.pi * np.outer(f, t))
    power = np.abs(ph @ x) ** 2
    k = int(np.argmax(power))
    if 0 < k < power.size - 1:   # parabolic refinement
        a, b, c = power[k - 1], power[k], power[k + 1]
        denom = a - 2 * b + c
        k_ref = k + (0.5 * (a - c) / denom if denom != 0 else 0.0)
    else:
        k_ref = float(k)
    return float(band_hz[0] * 60.0 + k_ref * step_bpm)


def detect_feet(t_s: np.ndarray, x: np.ndarray, hr_bpm: float) -> np.ndarray:
    """Feet of the blood-volume signal x (positive = more blood) by intersecting tangents (cfg beats.foot_method):
    for each systolic peak, the tangent at the steepest upstroke point meets the level of the preceding minimum;
    sub-frame precision without resampling the trace."""
    from scipy.signal import find_peaks

    t = np.asarray(t_s, float)
    x = np.asarray(x, float)
    fs = 1.0 / float(np.median(np.diff(t)))
    ibi = 60.0 / hr_bpm
    rng_amp = np.percentile(x, 95) - np.percentile(x, 5)
    peaks, _ = find_peaks(x, distance=max(1, int(0.6 * ibi * fs)), prominence=0.3 * rng_amp)
    feet = []
    for p in peaks:
        lo = int(np.searchsorted(t, t[p] - 0.45 * ibi))
        if p - lo < 3:
            continue
        seg_t, seg_x = t[lo:p + 1], x[lo:p + 1]
        slopes = np.diff(seg_x) / np.diff(seg_t)
        k = int(np.argmax(slopes))                      # steepest upstroke interval
        t_s_, x_s_ = 0.5 * (seg_t[k] + seg_t[k + 1]), 0.5 * (seg_x[k] + seg_x[k + 1])
        slope = slopes[k]
        if slope <= 0:
            continue
        y_min = float(seg_x[: k + 1].min())
        t_foot = t_s_ + (y_min - x_s_) / slope
        feet.append(float(np.clip(t_foot, seg_t[0], t[p])))
    return np.asarray(feet)


def ensemble_morphology(t_s: np.ndarray, x: np.ndarray, feet: np.ndarray, grid_s: float = 0.005, span_s: float = 1.2,
                        bandwidth_s: float | None = None) -> dict:
    """Foot-aligned ensemble beat by Gaussian kernel regression of every sample on its time after the beat's
    foot (no resampling of the trace; robust to feet phase-locked to the frame grid), one alignment refinement
    (each beat shifted within one frame period to best match the ensemble), then measured with the same rules
    as the generator's per-beat truth (`pulse_wave._measure_curve`)."""
    t = np.asarray(t_s, float)
    x = np.asarray(x, float)
    nan = {k: float("nan") for k in MEASURED_KEYS}
    if feet.size < 3:
        return nan
    period = float(np.median(np.diff(t)))
    h = bandwidth_s if bandwidth_s is not None else max(0.008, period / 2.0)
    ibi_med = float(np.median(np.diff(feet)))
    beats = []
    for k in range(feet.size - 1):
        f0, f1 = feet[k], feet[k + 1]
        if not (0.6 * ibi_med < f1 - f0 < 1.6 * ibi_med):
            continue
        lo, hi = int(np.searchsorted(t, f0 - 0.5 * period)), int(np.searchsorted(t, min(f1, f0 + span_s)))
        if hi - lo < 4:
            continue
        beats.append((f0, t[lo:hi], x[lo:hi]))
    if len(beats) < 3:
        return nan
    end = min(span_s, float(np.median([b[1][-1] - b[0] for b in beats])))
    grid = np.arange(0.0, end, grid_s)
    shifts = np.zeros(len(beats))

    def kernel_ensemble():
        num = np.zeros(grid.size)
        den = np.zeros(grid.size)
        for (f0, tt, xx), sh in zip(beats, shifts):
            rel = tt - (f0 + sh)
            base = float(np.interp(0.0, rel, xx))        # level at the foot of this beat
            w = np.exp(-0.5 * ((grid[:, None] - rel[None, :]) / h) ** 2)
            num += w @ (xx - base)
            den += w.sum(axis=1)
        return num / np.maximum(den, 1e-9)

    ens = kernel_ensemble()
    cands = np.arange(-period, period + 1e-9, grid_s)
    for i, (f0, tt, xx) in enumerate(beats):
        best, best_c = 0.0, -np.inf
        for sh in cands:
            rel = tt - (f0 + sh)
            ok = (rel >= 0) & (rel < grid[-1])
            if ok.sum() < 4:
                continue
            e = np.interp(rel[ok], grid, ens)
            if np.std(e) <= 0 or np.std(xx[ok]) <= 0:
                continue
            c = float(np.corrcoef(e, xx[ok])[0, 1])
            if c > best_c:
                best_c, best = c, sh
        shifts[i] = best
    ens = kernel_ensemble()
    ens = ens - ens[0]
    peak = float(ens.max())
    if peak <= 1e-12:
        return nan
    m = _measure_curve(grid, ens / peak)
    return {k_: m.get(k_, float("nan")) for k_ in MEASURED_KEYS} | {"notch_present": bool(m.get("notch_present", False)),
                                                                   "n_beats": len(beats), "foot_shift_rms_s": float(np.sqrt(np.mean(shifts**2)))}


def reference_recovery(t_s: np.ndarray, intensity: np.ndarray, cfg=None, band_hz: tuple[float, float] | None = None) -> dict:
    """Recover {hr_bpm, foot_times, morphology} from a mean-intensity trace (e.g. thenar G) at true times.
    Polarity: the blood-volume signal is the negated intensity (CONTRACTS section 6)."""
    if band_hz is None:
        if cfg is None:
            from palmppg.core.config import load_pipeline_config

            cfg = load_pipeline_config()
        band_hz = tuple(cfg.get("pulse.band_rate"))
    t = np.asarray(t_s, float)
    x = _highpass_trace(t, -np.asarray(intensity, float))
    hr = dense_dft_rate(t, x, band_hz)
    feet = detect_feet(t, x, hr)
    morph = ensemble_morphology(t, x, feet)
    return {"hr_bpm": hr, "foot_times": feet, "morphology": morph}


# ----------------------------------------------------------------------------- scoring
def match_feet(truth_feet: np.ndarray, recovered_feet: np.ndarray, max_abs_s: float) -> tuple[np.ndarray, int]:
    """Nearest-neighbour matching of recovered feet to truth feet within max_abs_s; returns signed errors (s)."""
    tf = np.sort(np.asarray(truth_feet, float))
    rf = np.sort(np.asarray(recovered_feet, float))
    if tf.size == 0 or rf.size == 0:
        return np.zeros(0), 0
    j = np.searchsorted(tf, rf)
    j0 = np.clip(j - 1, 0, tf.size - 1)
    j1 = np.clip(j, 0, tf.size - 1)
    nearest = np.where(np.abs(tf[j1] - rf) < np.abs(tf[j0] - rf), tf[j1], tf[j0])
    err = rf - nearest
    ok = np.abs(err) <= max_abs_s
    return err[ok], int(ok.sum())


def score_recovery(truth: dict, recovered: dict, tolerances_: dict | None = None, fps: float = 30.0, cfg=None,
                   window_s: tuple[float, float] | None = None) -> dict:
    """Score a recovery against the truth. Section 8 positive control.

    truth: pulse_truth (generate_pulse) or a Pi clip truth (hr_bpm, foot_t_tangent / foot_tangent_t_ref_s with
    foot_t / foot_t_ref_s as fallback, morphology_measured).
    recovered: {"hr_bpm": float, "foot_times": array (s), "morphology": {param: value}}.
    window_s: restrict the foot comparison to [start, end) on the truth clock. Returns per-item errors and
    pass flags plus an overall "pass".
    """
    tol = tolerances(cfg)
    tol.update(tolerances_ or {})
    hr_t = float(truth["hr_bpm"])
    hr_r = float(recovered.get("hr_bpm", float("nan")))
    hr_err = abs(hr_r - hr_t)
    out = {"hr": {"truth_bpm": hr_t, "recovered_bpm": hr_r, "abs_err_bpm": hr_err, "tolerance_bpm": tol["hr_bpm"],
                  "pass": bool(np.isfinite(hr_err) and hr_err <= tol["hr_bpm"])}}
    feet_t = np.asarray(truth.get("foot_t_tangent", truth.get("foot_tangent_t_ref_s", truth.get("foot_t", truth.get("foot_t_ref_s", [])))), float)
    feet_r = np.asarray(recovered.get("foot_times", []), float)
    if window_s is not None:
        feet_t = feet_t[(feet_t >= window_s[0]) & (feet_t < window_s[1])]
        feet_r = feet_r[(feet_r >= window_s[0]) & (feet_r < window_s[1])]
    period = 1.0 / fps
    ibi = 60.0 / max(hr_t, 1e-6)
    err, n_match = match_feet(feet_t, feet_r, 0.4 * ibi)
    med = float(np.median(np.abs(err))) if err.size else float("nan")
    out["feet"] = {"n_truth": int(feet_t.size), "n_recovered": int(feet_r.size), "n_matched": n_match,
                   "match_rate": (n_match / feet_t.size) if feet_t.size else float("nan"),
                   "median_abs_err_s": med, "median_abs_err_frames": med / period if np.isfinite(med) else float("nan"),
                   "bias_s": float(np.mean(err)) if err.size else float("nan"), "tolerance_frames": tol["foot_median_frames"],
                   "pass": bool(np.isfinite(med) and med <= tol["foot_median_frames"] * period and n_match >= 0.8 * max(feet_t.size, 1))}
    mt = truth.get("morphology_measured", {})
    mr = recovered.get("morphology", {}) or {}
    morph = {}
    for k in MORPHOLOGY_SCORED:
        tv, rv = mt.get(k), mr.get(k)
        if tv is None or rv is None or not (np.isfinite(tv) and np.isfinite(rv)):
            morph[k] = {"truth": tv, "recovered": rv, "rel_err": float("nan"), "pass": None}
            continue
        rel = abs(rv - tv) / max(abs(tv), 1e-9)
        morph[k] = {"truth": float(tv), "recovered": float(rv), "rel_err": float(rel), "pass": bool(rel <= tol["morphology_rel"])}
    scored = [v["pass"] for v in morph.values() if v["pass"] is not None]
    out["morphology"] = morph
    out["morphology_pass"] = bool(scored) and all(scored)
    out["tolerances"] = tol
    out["pass"] = bool(out["hr"]["pass"] and out["feet"]["pass"] and out["morphology_pass"])
    return out
