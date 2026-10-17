"""LED marker detection in video: block trace, pattern detection with sub-frame edges, offset fit.

Serves protocol section 4.2: "mean intensity of the LED pixel block per frame, threshold on the Bayer plane
with the best contrast, match the pattern, report the onset frame and sub-frame estimate by fitting the
rising edge ... accept if the edges agree within one frame period after a single offset and drift term"
(DECISIONS D-003).

Frames are streamed: ``led_trace`` keeps one scalar per plane per frame and never a frame buffer.
Pi frames are Bayer planes (never demosaiced here); block coordinates are full-resolution Bayer
coordinates and are halved for plane coordinates.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence

import numpy as np
from scipy.ndimage import median_filter

from palmppg.core.timeline import ClockMap
from palmppg.ingest.sync_events import match_pulse_pattern

# Defaults for knobs the protocol leaves open; ``build_timeline`` reads them from the config with these
# fallbacks (listed as config additions in the WP2 report).
DEFAULTS = {
    "sync.led.min_contrast": 0.10,        # (hi - lo) / |off level| must exceed this
    "sync.led.min_snr": 5.0,              # (hi - lo) / robust noise sigma must exceed this
    "sync.led.baseline_window_s": 3.0,    # rolling-median baseline removal window (0 disables)
    "sync.led.duration_tol_frames": 1.5,  # on/off duration tolerance, in frame periods ...
    "sync.led.duration_tol_frac": 0.30,   # ... or this fraction of the nominal duration, whichever is larger
}

RGB_CHANNELS = ("R", "G", "B")


# --------------------------------------------------------------------------- block traces
def block_to_plane_coords(block: Mapping) -> dict:
    """Full-resolution Bayer block ``{x,y,w,h}`` -> half-resolution plane block (CONTRACTS 3.3)."""
    x, y, w, h = int(block["x"]), int(block["y"]), int(block["w"]), int(block["h"])
    return {"x": x // 2, "y": y // 2, "w": max(1, w // 2), "h": max(1, h // 2)}


def _block_mean(arr: np.ndarray, b: Mapping) -> float:
    sub = arr[b["y"]:b["y"] + b["h"], b["x"]:b["x"] + b["w"]]
    if sub.size == 0:
        raise ValueError(f"LED block {dict(b)} lies outside the array of shape {arr.shape}")
    return float(np.mean(sub, dtype=np.float64))


def led_trace_planes(frames_iter: Iterable, block: Mapping) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """Per-frame mean of the LED block on every plane/channel, streaming (section 4.2).

    ``frames_iter`` yields ``(frame_idx, planes)`` where ``planes`` is a dict of Bayer planes (Pi, half
    resolution, block halved) or an ``(H, W, 3)`` RGB array (phone, full-resolution block). Returns
    ``(frame_idx, {plane_name: intensity})`` in the frames' own intensity units.
    """
    idx: list[int] = []
    traces: dict[str, list[float]] = {}
    plane_block = block_to_plane_coords(block)
    full_block = {"x": int(block["x"]), "y": int(block["y"]), "w": int(block["w"]), "h": int(block["h"])}
    for frame_idx, frame in frames_iter:
        if isinstance(frame, Mapping):
            items = [(str(k), np.asarray(v), plane_block) for k, v in frame.items()]
        else:
            arr = np.asarray(frame)
            if arr.ndim == 3 and arr.shape[-1] in (3, 4):
                items = [(RGB_CHANNELS[c], arr[..., c], full_block) for c in range(3)]
            elif arr.ndim == 2:
                items = [("Y", arr, full_block)]
            else:
                raise ValueError(f"unsupported frame shape {arr.shape}")
        idx.append(int(frame_idx))
        for name, arr, b in items:
            traces.setdefault(name, []).append(_block_mean(arr, b))
    return np.asarray(idx, dtype=np.int64), {k: np.asarray(v, dtype=float) for k, v in traces.items()}


def plane_contrast(x: np.ndarray) -> float:
    """Contrast score ``(p99 - p1) / p50`` of a block trace (plane selection rule of section 4.2)."""
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if x.size < 2:
        return 0.0
    p1, p50, p99 = np.percentile(x, [1, 50, 99])
    return float((p99 - p1) / max(abs(p50), 1e-9))


def select_best_plane(traces: Mapping[str, np.ndarray]) -> str:
    """Name of the plane/channel with the highest ``plane_contrast``."""
    if not traces:
        raise ValueError("no planes")
    scores = {k: plane_contrast(v) for k, v in traces.items()}
    return max(scores, key=lambda k: (scores[k], k))


def led_trace_with_plane(frames_iter: Iterable, block: Mapping,
                         plane_selector: str | Callable | None = None) -> tuple[np.ndarray, np.ndarray, str]:
    """``(frame_idx, intensity, plane_name)``: LED block trace on the best-contrast plane (section 4.2).

    ``plane_selector``: None = automatic (max (p99-p1)/p50), a plane/channel name, or a callable taking the
    dict of traces and returning a name.
    """
    idx, traces = led_trace_planes(frames_iter, block)
    if plane_selector is None:
        name = select_best_plane(traces)
    elif callable(plane_selector):
        name = str(plane_selector(traces))
    else:
        name = str(plane_selector)
    if name not in traces:
        raise KeyError(f"plane {name!r} not among {sorted(traces)}")
    return idx, traces[name], name


def led_trace(frames_iter: Iterable, block: Mapping,
              plane_selector: str | Callable | None = None) -> tuple[np.ndarray, np.ndarray]:
    """``(frame_idx, intensity)`` of the LED block on the best-contrast plane (section 4.2)."""
    idx, y, _ = led_trace_with_plane(frames_iter, block, plane_selector)
    return idx, y


# --------------------------------------------------------------------------- thresholding
def robust_levels(y: np.ndarray, n_on: int) -> tuple[float, float, float]:
    """``(lo, hi, sigma)``: robust off level (median), on level (median of the top ``n_on`` samples)
    and noise sigma (1.4826 * MAD about the median). The on level uses the pattern's expected number
    of lit frames so it is insensitive to a few outliers."""
    y = np.asarray(y, dtype=float)
    lo = float(np.median(y))
    n_on = int(max(1, min(n_on, y.size)))
    top = np.sort(y)[-n_on:]
    hi = float(np.median(top))
    sigma = float(1.4826 * np.median(np.abs(y - lo)))
    return lo, hi, max(sigma, 1e-12)


def remove_baseline(y: np.ndarray, fps: float, window_s: float) -> np.ndarray:
    """Subtract a rolling-median baseline (slow box-light drift); the LED is lit for a small fraction of
    any window of ``window_s`` so the median tracks the off level. Returns ``y`` unchanged when the trace
    is shorter than twice the window."""
    y = np.asarray(y, dtype=float)
    if window_s <= 0 or y.size < 2 * round(window_s * fps):
        return y
    size = round(window_s * fps) | 1
    return y - median_filter(y, size=size, mode="nearest")


def _crossings(t: np.ndarray, y: np.ndarray, thr: float) -> tuple[list[dict], list[dict]]:
    """Rising/falling threshold crossings with linear sub-frame interpolation between bracketing frames."""
    above = y > thr
    d = np.diff(above.astype(np.int8))
    rises, falls = [], []
    for i in np.where(d != 0)[0]:
        y0, y1 = y[i], y[i + 1]
        frac = (thr - y0) / (y1 - y0) if y1 != y0 else 0.5
        frac = float(np.clip(frac, 0.0, 1.0))
        rec = {"i": int(i), "frac": frac, "t": float(t[i] + frac * (t[i + 1] - t[i])),
               "step": float(y1 - y0), "gap_s": float(t[i + 1] - t[i])}
        (rises if d[i] > 0 else falls).append(rec)
    return rises, falls


def detect_pattern(t_s, intensity, pattern_spec: Mapping, fps: float, min_contrast: float | None = None,
                   min_snr: float | None = None, exposure_s: float = 0.0, baseline_window_s: float | None = None,
                   duration_tol_frames: float | None = None, duration_tol_frac: float | None = None,
                   frame_idx=None, search_window: tuple[float, float] | None = None) -> dict | None:
    """Find one LED pattern in a block trace; sub-frame edges by fitting the rising/falling edge (section 4.2).

    * Adaptive threshold at the midpoint of the robust off/on levels (after rolling-median baseline removal).
    * Each edge time is the linear interpolation of the threshold crossing between the two bracketing
      frames, shifted by ``exposure_s / 2`` so that frame timestamps taken at exposure start (Pi
      ``SensorTimestamp``) give the time the LED actually changed state.
    * The run of pulses whose on/off durations match the spec within
      ``max(duration_tol_frames / fps, duration_tol_frac * nominal)`` is the pattern.

    Returns ``None`` when the pattern is absent (contrast or SNR too low, or no matching run), else
    ``{"onset_s", "edges": [{t_s, kind, frame_idx, frame_before, subframe_frac, confidence, pattern}],
    "pattern", "threshold", "lo", "hi", "contrast", "snr", "score", "n_pulses_seen"}`` with ``t_s`` in the
    trace's own time base (seconds). ``frame_idx`` is the first frame on the new side of the edge.
    """
    min_contrast = DEFAULTS["sync.led.min_contrast"] if min_contrast is None else float(min_contrast)
    min_snr = DEFAULTS["sync.led.min_snr"] if min_snr is None else float(min_snr)
    baseline_window_s = DEFAULTS["sync.led.baseline_window_s"] if baseline_window_s is None else baseline_window_s
    duration_tol_frames = DEFAULTS["sync.led.duration_tol_frames"] if duration_tol_frames is None else duration_tol_frames
    duration_tol_frac = DEFAULTS["sync.led.duration_tol_frac"] if duration_tol_frac is None else duration_tol_frac

    t = np.asarray(t_s, dtype=float)
    y_raw = np.asarray(intensity, dtype=float)
    fidx = np.arange(t.size, dtype=np.int64) if frame_idx is None else np.asarray(frame_idx, dtype=np.int64)
    keep = np.isfinite(t) & np.isfinite(y_raw)
    if search_window is not None:
        keep &= (t >= search_window[0]) & (t <= search_window[1])
    t, y_raw, fidx = t[keep], y_raw[keep], fidx[keep]
    if t.size < 4:
        return None
    order = np.argsort(t, kind="stable")
    t, y_raw, fidx = t[order], y_raw[order], fidx[order]

    y = remove_baseline(y_raw, fps, float(baseline_window_s))
    n_on = max(2, round(0.5 * pattern_spec["pulses"] * pattern_spec["on_s"] * fps))
    lo, hi, sigma = robust_levels(y, n_on)
    off_level = float(np.median(y_raw))
    contrast = (hi - lo) / max(abs(off_level), 1e-9)
    snr = (hi - lo) / sigma
    if hi <= lo or contrast < min_contrast or snr < min_snr:
        return None
    thr = 0.5 * (lo + hi)
    rises, falls = _crossings(t, y, thr)
    if not rises or not falls:
        return None
    half_exp = 0.5 * float(exposure_s)

    # pair each rise with the next fall
    pulses: list[tuple[float, float]] = []
    pairs: list[tuple[dict, dict]] = []
    fi = 0
    for r in rises:
        while fi < len(falls) and falls[fi]["i"] <= r["i"]:
            fi += 1
        if fi >= len(falls):
            break
        f = falls[fi]
        pulses.append((r["t"] + half_exp, f["t"] + half_exp))
        pairs.append((r, f))
        fi += 1
    if not pulses:
        return None
    tol_on = max(duration_tol_frames / fps, duration_tol_frac * pattern_spec["on_s"])
    tol_off = max(duration_tol_frames / fps, duration_tol_frac * pattern_spec["off_s"])
    match = match_pulse_pattern(pulses, pattern_spec, tol_on, tol_off)
    if match is None:
        return None

    period = 1.0 / fps
    edges: list[dict] = []
    for k in match["indices"]:
        for rec, kind in ((pairs[k][0], "start"), (pairs[k][1], "end")):
            step_frac = abs(rec["step"]) / (hi - lo)
            conf = float(np.clip(step_frac, 0.0, 1.0) * min(1.0, period / max(rec["gap_s"], 1e-9)))
            edges.append({
                "t_s": float(rec["t"] + half_exp), "kind": kind, "frame_idx": int(fidx[rec["i"] + 1]),
                "frame_before": int(fidx[rec["i"]]), "subframe_frac": float(rec["frac"]),
                "confidence": conf, "pattern": str(pattern_spec.get("name", "")),
            })
    edges.sort(key=lambda e: e["t_s"])
    return {
        "onset_s": edges[0]["t_s"], "edges": edges, "pattern": str(pattern_spec.get("name", "")),
        "threshold": float(thr), "lo": float(lo), "hi": float(hi), "contrast": float(contrast),
        "snr": float(snr), "score": float(match["score"]), "n_pulses_seen": len(pulses),
        "exposure_s": float(exposure_s),
    }


# --------------------------------------------------------------------------- offset + drift fit
def _as_pattern_dict(edges) -> dict[str, list]:
    """Accept ``{pattern: [edge...]}``, ``{pattern: detect_pattern result}`` or a flat edge list."""
    if edges is None:
        return {}
    if isinstance(edges, Mapping):
        out: dict[str, list] = {}
        for pat, v in edges.items():
            if v is None:
                continue
            if isinstance(v, Mapping) and "edges" in v:
                v = v["edges"]
            out[str(pat)] = list(v)
        return out
    out = {}
    for e in edges:
        out.setdefault(str(e.get("pattern", "")), []).append(e)
    return out


def _edge_time_kind(e) -> tuple[float, str]:
    if isinstance(e, Mapping):
        return float(e["t_s"]), str(e["kind"])
    return float(e[0]), str(e[1])


def match_edges(detected: Mapping[str, Sequence], expected: Mapping[str, Sequence]) -> list[dict]:
    """Pair detected with expected edges per pattern and per kind, in time order (section 4.2)."""
    pairs: list[dict] = []
    for pat in sorted(set(detected) & set(expected)):
        det = sorted((_edge_time_kind(e) for e in detected[pat]), key=lambda x: x[0])
        exp = sorted((_edge_time_kind(e) for e in expected[pat]), key=lambda x: x[0])
        for kind in ("start", "end"):
            d_k = [t for t, k in det if k == kind]
            e_k = [t for t, k in exp if k == kind]
            for j, (td, te) in enumerate(zip(d_k, e_k)):
                pairs.append({"pattern": pat, "kind": kind, "ordinal": j, "t_native_s": td, "t_ref_s": te})
    pairs.sort(key=lambda p: p["t_ref_s"])
    return pairs


def fit_led_offset(detected_edges, expected_edges, stream: str, fps: float, tolerance_frames: float,
                   min_edges: int, method: str | None = None, drift_min_edges: int = 4) -> tuple[ClockMap | None, dict]:
    """One offset (+ drift when >= ``drift_min_edges`` edges) from detected vs logged edges (D-003).

    ``detected_edges``: ``{pattern: [edge dict with t_s (stream-native seconds), kind]}`` (or the
    ``detect_pattern`` results); ``expected_edges``: ``{pattern: [(t_ref_s, kind)]}`` from the log.
    Returns ``(ClockMap(stream, method) | None, report)`` where the report lists the residual of every
    matched edge (seconds and frame periods), ``residual_max_frames``, and ``accepted`` = at least
    ``min_edges`` matched and every residual within ``tolerance_frames`` frame periods. The map's
    uncertainty is ``max(residual_rms, (1/fps) / sqrt(12 n))`` (frame-quantisation floor). Section 4.2.
    """
    method = method or ("audio_beep" if "audio" in stream else "led_pattern")
    pairs = match_edges(_as_pattern_dict(detected_edges), _as_pattern_dict(expected_edges))
    n_expected = sum(len(v) for v in _as_pattern_dict(expected_edges).values())
    report: dict = {
        "stream": stream, "method": method, "n_matched": len(pairs), "n_expected": int(n_expected),
        "tolerance_frames": float(tolerance_frames), "min_edges": int(min_edges), "fps": float(fps),
        "offset_s": None, "drift": None, "drift_fitted": False, "residuals": [], "residual_max_s": None,
        "residual_max_frames": None, "residual_rms_s": None, "accepted": False, "reason": "",
    }
    if not pairs:
        report["reason"] = "no edges matched"
        return None, report
    native = np.array([p["t_native_s"] for p in pairs])
    ref = np.array([p["t_ref_s"] for p in pairs])
    fit_drift = len(pairs) >= drift_min_edges and np.ptp(native) > 0
    cm = ClockMap.fit(native, ref, stream, method=method, fit_drift=fit_drift)
    resid = ref - cm.to_ref(native)
    period = 1.0 / fps
    cm.uncertainty_s = float(max(cm.residual_rms_s or 0.0, period / np.sqrt(12.0 * len(pairs))))
    for p, r in zip(pairs, resid):
        p["residual_s"] = float(r)
        p["residual_frames"] = float(r / period)
    rmax = float(np.max(np.abs(resid)))
    accepted = len(pairs) >= int(min_edges) and rmax / period <= float(tolerance_frames)
    reasons = []
    if len(pairs) < int(min_edges):
        reasons.append(f"{len(pairs)} edges matched, need {int(min_edges)}")
    if rmax / period > float(tolerance_frames):
        reasons.append(f"max residual {rmax / period:.2f} frames exceeds {float(tolerance_frames):.2f}")
    cm.notes = f"{len(pairs)} edges; max residual {rmax / period:.2f} frames; " + ("accepted" if accepted else "rejected")
    report.update({
        "offset_s": float(cm.offset_s), "drift": float(cm.drift), "drift_fitted": bool(fit_drift),
        "residuals": pairs, "residual_max_s": rmax, "residual_max_frames": float(rmax / period),
        "residual_rms_s": float(cm.residual_rms_s or 0.0), "accepted": bool(accepted),
        "reason": "; ".join(reasons) if reasons else "all matched edges within tolerance",
        "uncertainty_s": float(cm.uncertainty_s),
    })
    return cm, report
