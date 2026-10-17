"""Self-contained fixtures for the ECG tests: a template-based synthetic single-lead ECG with exactly known
R-peak times, and a temporary participant folder writer (CONTRACTS section 3.6 layout)."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import numpy as np

from palmppg.core.config import rng
from palmppg.core.paths import ParticipantPaths

# (amplitude scale, centre s relative to the R apex, sigma s) of Gaussian waves: P, Q, R, S, T
TEMPLATE = ((0.15, -0.18, 0.025), (-0.08, -0.025, 0.006), (1.0, 0.0, 0.009), (-0.20, 0.022, 0.006), (0.30, 0.26, 0.045))
FS = 300.0


def synthetic_ecg(fs: float = FS, duration_s: float = 60.0, hr_bpm: float = 65.0, rsa_bpm: float = 3.0,
                  rsa_hz: float = 0.25, r_amp_mv: float = 1.0, noise_mv: float = 0.0, mains_mv: float = 0.0,
                  mains_hz: float = 50.0, wander_mv: float = 0.0, wander_hz: float = 0.2, seed: int = 0,
                  first_beat_s: float = 0.6) -> dict:
    """Gaussian-wave ECG in millivolts with beats whose instantaneous rate is hr + rsa * sin(2 pi f t).

    Returns {x, t, r_times_s (exact R apex times), ibi_s, hr_true_bpm (60 / mean IBI), fs}.
    """
    n = round(duration_s * fs)
    t = np.arange(n) / fs
    beats = [first_beat_s]
    while True:
        hr = hr_bpm + rsa_bpm * np.sin(2 * np.pi * rsa_hz * beats[-1])
        nxt = beats[-1] + 60.0 / hr
        if nxt > duration_s - 0.35:
            break
        beats.append(nxt)
    r_times = np.asarray(beats)
    x = np.zeros(n)
    half = int(0.5 * fs)
    for tb in r_times:
        c = round(tb * fs)
        lo, hi = max(0, c - half), min(n, c + half)
        tt = t[lo:hi] - tb
        for amp, centre, sigma in TEMPLATE:
            x[lo:hi] += r_amp_mv * amp * np.exp(-0.5 * ((tt - centre) / sigma) ** 2)
    g = rng(seed, "synthetic_ecg")
    if noise_mv:
        x = x + noise_mv * g.normal(size=n)
    if mains_mv:
        x = x + mains_mv * np.sin(2 * np.pi * mains_hz * t + 0.3)
    if wander_mv:
        x = x + wander_mv * np.sin(2 * np.pi * wander_hz * t)
    ibi = np.diff(r_times)
    return {"x": x, "t": t, "r_times_s": r_times, "ibi_s": ibi, "hr_true_bpm": 60.0 / float(ibi.mean()), "fs": fs}


def add_lift_artefact(x: np.ndarray, fs: float, t_step_s: float, step_mv: float = 2.0, ring_mv: float = 1.0,
                      ring_hz: float = 8.0, tau_s: float = 0.3) -> tuple[np.ndarray, float]:
    """Baseline step plus damped ringing from `t_step_s` on. Returns (signal, time of the first sample at
    the new level)."""
    y = x.copy()
    i0 = round(t_step_s * fs)
    tt = np.arange(y.size - i0) / fs
    y[i0:] += step_mv + ring_mv * np.exp(-tt / tau_s) * np.sin(2 * np.pi * ring_hz * tt)
    return y, i0 / fs


def write_participant(root: Path, study_id: str, ecg_mv: np.ndarray | None = None, fs: float = FS,
                      pdf_mv: np.ndarray | None = None, clinician: dict | None = None,
                      app_label: str = "Normal", start: dt.datetime | None = None) -> ParticipantPaths:
    """Temporary participant folder with ecg/kardia_0001.atc (when `ecg_mv`), ecg/kardia_0001.pdf (when
    `pdf_mv`), ecg/kardia_meta.json and clinician.json (when given)."""
    from palmppg.ecg.atc import write_atc
    from palmppg.ecg.pdf_digitiser import render_synthetic_strip_pdf

    pp = ParticipantPaths(study_id, Path(root) / "participants" / study_id)
    pp.ecg.mkdir(parents=True, exist_ok=True)
    start = start or dt.datetime(2026, 10, 17, 10, 30, 5, tzinfo=dt.timezone(dt.timedelta(hours=5, minutes=30)))
    fmt = "atc" if ecg_mv is not None else "pdf"
    if ecg_mv is not None:
        write_atc(pp.ecg / "kardia_0001.atc", ecg_mv, fs=fs, start_time=start, info={"phone_model": "tablet"})
    if pdf_mv is not None:
        render_synthetic_strip_pdf(pp.ecg / "kardia_0001.pdf", pdf_mv, fs)
    dur = (ecg_mv if ecg_mv is not None else pdf_mv)
    meta = {"start_wall_ts": start.isoformat(), "duration_s": (len(dur) / fs) if dur is not None else None, "fs": fs,
            "app_rhythm_label": app_label, "device_id": "KARDIA-01", "export_format": fmt}
    pp.ecg_meta.write_text(json.dumps(meta), encoding="utf-8")
    if clinician is not None:
        pp.clinician.write_text(json.dumps(clinician), encoding="utf-8")
    return pp


def nearest_offsets(reference: np.ndarray, found: np.ndarray) -> np.ndarray:
    """found - reference for the nearest found element of each reference element (NaN when `found` empty)."""
    ref = np.asarray(reference, dtype=float)
    f = np.sort(np.asarray(found, dtype=float))
    if f.size == 0:
        return np.full(ref.shape, np.nan)
    pos = np.searchsorted(f, ref)
    out = np.empty(ref.size)
    for i, k in enumerate(pos):
        cands = [f[j] for j in (k - 1, k) if 0 <= j < f.size]
        out[i] = min(cands, key=lambda v: abs(v - ref[i])) - ref[i]
    return out
