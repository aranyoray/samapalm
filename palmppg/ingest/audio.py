"""Buzzer beep detection on the phone audio track (protocol section 4.2, phone side).

"Onset detection on the audio track (band-pass at the buzzer tone, Hilbert envelope, pattern match)."
Pipeline: zero-phase Butterworth band-pass (scipy SOS, ``sosfiltfilt`` so the tone-burst edges stay
symmetric about the true onset), analytic-signal envelope, adaptive midpoint threshold, sub-sample edge
times by linear interpolation of the threshold crossing, then the P1/P2 pulse-sequence match.

Audio time -> phone video time: the container's audio stream has its own start time (PyAV
``audio_stream.start_time * time_base``); the caller passes it as ``audio_start_offset_s`` so that
``t_video = t_audio + audio_start_offset_s``. One clip of audio (60 s at 48 kHz, ~3 M samples, ~25 MB as
float64) is processed in memory; this module never touches video frames.
"""
from __future__ import annotations

from collections.abc import Mapping

import numpy as np
from scipy.fft import next_fast_len
from scipy.signal import butter, hilbert, sosfiltfilt

from palmppg.ingest.sync_events import match_pulse_pattern

DEFAULTS = {
    "sync.audio.min_snr_db": 10.0,          # envelope step over in-band noise, dB
    "sync.audio.envelope_smooth_s": 0.0005,  # symmetric moving average on the envelope
    "sync.audio.duration_tol_s": 0.020,      # pulse on/off duration tolerance ...
    "sync.audio.duration_tol_frac": 0.20,    # ... or this fraction of nominal, whichever is larger
}


def bandpass_sos(fs: float, tone_hz: float, bandwidth_hz: float, order: int = 4):
    """Second-order sections of a Butterworth band-pass centred on the buzzer tone."""
    lo = max(1.0, tone_hz - bandwidth_hz / 2.0)
    hi = min(fs / 2.0 - 1.0, tone_hz + bandwidth_hz / 2.0)
    if hi <= lo:
        raise ValueError(f"band [{lo}, {hi}] Hz is empty for fs={fs}")
    return butter(order, [lo, hi], btype="bandpass", fs=fs, output="sos")


def tone_envelope(x, fs: float, tone_hz: float, bandwidth_hz: float, order: int = 4,
                  smooth_s: float | None = None) -> np.ndarray:
    """Band-passed (zero-phase) analytic-signal envelope of the buzzer tone, same length as ``x``.

    Units: those of ``x`` (amplitude). A short symmetric moving average (``smooth_s``) removes residual
    carrier ripple without shifting edges. Section 4.2.
    """
    smooth_s = DEFAULTS["sync.audio.envelope_smooth_s"] if smooth_s is None else smooth_s
    x = np.asarray(x, dtype=float)
    if x.ndim == 2:  # (n, channels) -> mono
        x = x.mean(axis=1)
    if x.size < 16:
        raise ValueError("audio too short")
    sos = bandpass_sos(fs, tone_hz, bandwidth_hz, order)
    y = sosfiltfilt(sos, x - float(np.mean(x)))
    n = y.size
    env = np.abs(hilbert(y, N=next_fast_len(n)))[:n]
    w = round(float(smooth_s) * fs)
    if w >= 3:
        w |= 1
        kernel = np.ones(w) / w
        env = np.convolve(env, kernel, mode="same")
    return env


def _crossings(t: np.ndarray, env: np.ndarray, thr: float) -> tuple[list[dict], list[dict]]:
    above = env > thr
    d = np.diff(above.astype(np.int8))
    rises, falls = [], []
    for i in np.where(d != 0)[0]:
        y0, y1 = env[i], env[i + 1]
        frac = float(np.clip((thr - y0) / (y1 - y0), 0.0, 1.0)) if y1 != y0 else 0.5
        rec = {"i": int(i), "t": float(t[i] + frac * (t[i + 1] - t[i]))}
        (rises if d[i] > 0 else falls).append(rec)
    return rises, falls


def detect_beeps(audio, fs: float, tone_hz: float, bandwidth_hz: float, pattern_specs: Mapping[str, Mapping],
                 min_snr_db: float | None = None, duration_tol_s: float | None = None,
                 duration_tol_frac: float | None = None, audio_start_offset_s: float = 0.0,
                 smooth_s: float | None = None) -> dict[str, dict | None]:
    """Detect the P1/P2 beep patterns in an audio track (section 4.2, phone side).

    Returns ``{pattern: {"onset_s", "edges": [{t_s, kind, confidence, pattern}], "snr_db", "score"} | None}``
    with ``None`` for absent patterns. All ``t_s`` are **phone video seconds**
    (``t_audio + audio_start_offset_s``); ``onset_audio_s`` carries the raw audio-time onset for audit.
    Onset precision is limited by the band-pass rise time (about ``1 / bandwidth_hz``) and the noise, not by
    the sample period: the crossing is interpolated between samples.
    """
    min_snr_db = DEFAULTS["sync.audio.min_snr_db"] if min_snr_db is None else float(min_snr_db)
    duration_tol_s = DEFAULTS["sync.audio.duration_tol_s"] if duration_tol_s is None else float(duration_tol_s)
    duration_tol_frac = DEFAULTS["sync.audio.duration_tol_frac"] if duration_tol_frac is None else float(duration_tol_frac)
    specs = {str(k): dict(v) for k, v in pattern_specs.items()}
    out: dict[str, dict | None] = {k: None for k in specs}
    env = tone_envelope(audio, fs, tone_hz, bandwidth_hz, smooth_s=smooth_s)
    t = np.arange(env.size, dtype=float) / float(fs)

    min_on = min(s["on_s"] for s in specs.values()) if specs else 0.1
    n_on = max(8, round(0.5 * min_on * fs))
    lo = float(np.median(env))
    hi = float(np.median(np.sort(env)[-n_on:]))
    sigma = max(float(1.4826 * np.median(np.abs(env - lo))), 1e-12)
    snr_db = float(20.0 * np.log10(max(hi - lo, 1e-12) / sigma))
    if hi <= lo or snr_db < min_snr_db:
        return out
    thr = 0.5 * (lo + hi)
    rises, falls = _crossings(t, env, thr)
    pulses: list[tuple[float, float]] = []
    fi = 0
    for r in rises:
        while fi < len(falls) and falls[fi]["i"] <= r["i"]:
            fi += 1
        if fi >= len(falls):
            break
        pulses.append((r["t"], falls[fi]["t"]))
        fi += 1
    if not pulses:
        return out
    # discard sub-millisecond glitches (noise spikes crossing the threshold)
    pulses = [(a, b) for a, b in pulses if (b - a) >= 0.001]
    conf = float(np.clip((hi - lo) / (sigma * 10.0), 0.0, 1.0))
    for name, spec in specs.items():
        tol_on = max(duration_tol_s, duration_tol_frac * spec["on_s"])
        tol_off = max(duration_tol_s, duration_tol_frac * spec["off_s"])
        m = match_pulse_pattern(pulses, spec, tol_on, tol_off)
        if m is None:
            continue
        edges = []
        for k in m["indices"]:
            a, b = pulses[k]
            edges.append({"t_s": a + audio_start_offset_s, "kind": "start", "confidence": conf, "pattern": name})
            edges.append({"t_s": b + audio_start_offset_s, "kind": "end", "confidence": conf, "pattern": name})
        edges.sort(key=lambda e: e["t_s"])
        out[name] = {
            "onset_s": edges[0]["t_s"], "onset_audio_s": edges[0]["t_s"] - audio_start_offset_s, "edges": edges,
            "snr_db": snr_db, "score": float(m["score"]), "threshold": float(thr), "pattern": name,
            "audio_start_offset_s": float(audio_start_offset_s), "n_pulses_seen": len(pulses),
        }
    return out


def audio_to_video_time(t_audio_s, audio_start_offset_s: float) -> np.ndarray:
    """Audio-stream seconds -> phone video (container) seconds: ``t + audio_start_offset_s``."""
    return np.asarray(t_audio_s, dtype=float) + float(audio_start_offset_s)


def beep_edges(result: Mapping[str, dict | None]) -> dict[str, list[dict]]:
    """``{pattern: edges}`` of the detected patterns, ready for ``led.fit_led_offset``."""
    return {k: v["edges"] for k, v in result.items() if v is not None}


def beep_precision_s(cfg_onset_tolerance_ms: float, bandwidth_hz: float) -> float:
    """Stated uncertainty of a beep-anchored offset: the larger of the configured onset tolerance and the
    band-pass rise time (about ``1 / bandwidth``). Section 4.2 / 4.5."""
    return float(max(cfg_onset_tolerance_ms / 1e3, 1.0 / max(bandwidth_hz, 1.0)))
