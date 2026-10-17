"""Synthetic single-lead ECG built from the same beat schedule as the palm pulse (CONTRACTS 3.6).

Protocol sections served: 3 (ecg/ layout: ATC file, kardia_meta.json, optional PDF strip), 4.3 (coarse
anchor: the Kardia recording starts an app latency after thumb contact; fine anchor: the thumb lift leaves an
unmistakable baseline artefact), 6.4 (300 Hz, millivolts, 50 Hz mains, baseline wander), 6.6 (R-peaks precede
the PPG feet by a per-participant pulse arrival time; ectopic beats are shared with the pulse).

Waveform: one P-QRS-T template per beat (sum of Gaussians around the R time, T placed with a square-root
rate dependence), baseline wander as slow sinusoids, 50 Hz mains at low amplitude, white noise, and the
thumb-lift artefact as a 2-3 mV step with exponential recovery. Rhythm profiles change the beat statistics
(AF: irregular, no P wave; flutter: regular fast with flutter waves; paced: spike before each QRS; frequent
ectopy: many premature beats).

ATC layout written here: header b"ALIVE" + 3 version bytes, then blocks of `u32 length (LE) | 4-byte id |
data | u32 crc32` where the CRC-32 is computed over id + data; blocks `info`, `fmt `, `ecg ` (int16 LE, 500 nV
per LSB). The parse side is WP3 (palmppg.ecg.atc); DECISIONS D-007 requires re-checking on the first real file.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import struct
import uuid as _uuid
import zlib
from pathlib import Path

import numpy as np

ECG_TEMPLATE = {                      # name: (centre s from R, sigma s, amplitude mV); T centre scales with sqrt(IBI/0.85)
    "P": (-0.16, 0.025, 0.12), "Q": (-0.028, 0.009, -0.10), "R": (0.0, 0.010, 1.00),
    "S": (0.030, 0.010, -0.22), "T": (0.27, 0.045, 0.30),
}
ATC_RESOLUTION_NV = 500               # nV per LSB (CONTRACTS 3.6)
ATC_VERSION = (1, 0, 0)
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))

RHYTHM_PROFILES = {                   # beat statistics per clinician rhythm class (cfg ecg.rhythm_classes)
    "sinus": {"hr": (52, 105), "hrv_sd_s": (0.015, 0.05), "resp_amp": (0.03, 0.08), "ectopic_frac": 0.0, "p_wave": True,
              "pacing_spike": False, "flutter": False, "noise_mv": 0.012},
    "af": {"hr": (70, 135), "hrv_sd_s": (0.11, 0.18), "resp_amp": (0.0, 0.0), "ectopic_frac": 0.0, "p_wave": False,
           "pacing_spike": False, "flutter": False, "noise_mv": 0.02},
    "aflutter": {"hr": (140, 152), "hrv_sd_s": (0.003, 0.008), "resp_amp": (0.0, 0.01), "ectopic_frac": 0.0, "p_wave": False,
                 "pacing_spike": False, "flutter": True, "noise_mv": 0.012},
    "svt": {"hr": (150, 185), "hrv_sd_s": (0.003, 0.008), "resp_amp": (0.0, 0.01), "ectopic_frac": 0.0, "p_wave": False,
            "pacing_spike": False, "flutter": False, "noise_mv": 0.012},
    "frequent_ectopy": {"hr": (60, 95), "hrv_sd_s": (0.015, 0.04), "resp_amp": (0.02, 0.06), "ectopic_frac": 0.15, "p_wave": True,
                        "pacing_spike": False, "flutter": False, "noise_mv": 0.012},
    "paced": {"hr": (60, 75), "hrv_sd_s": (0.002, 0.005), "resp_amp": (0.0, 0.0), "ectopic_frac": 0.0, "p_wave": False,
              "pacing_spike": True, "flutter": False, "noise_mv": 0.012},
    "other": {"hr": (55, 110), "hrv_sd_s": (0.03, 0.08), "resp_amp": (0.02, 0.05), "ectopic_frac": 0.04, "p_wave": True,
              "pacing_spike": False, "flutter": False, "noise_mv": 0.02},
    "unreadable": {"hr": (55, 105), "hrv_sd_s": (0.02, 0.05), "resp_amp": (0.03, 0.08), "ectopic_frac": 0.0, "p_wave": True,
                   "pacing_spike": False, "flutter": False, "noise_mv": 0.45},
}


def rhythm_profile(rhythm: str) -> dict:
    """Beat-generation profile for a clinician rhythm class (section 6.4 / 9 E7)."""
    if rhythm not in RHYTHM_PROFILES:
        raise KeyError(f"unknown rhythm class {rhythm}")
    return dict(RHYTHM_PROFILES[rhythm])


# ----------------------------------------------------------------------------- waveform
def ecg_waveform(t_s: np.ndarray, r_times_s: np.ndarray, rng: np.random.Generator, p_wave: bool = True,
                 pacing_spike: bool = False, flutter: bool = False, baseline_mv: float = 0.05, mains_mv: float = 0.02,
                 noise_mv: float = 0.012, mains_hz: float = 50.0, artefacts: list[tuple[float, float, float]] | None = None,
                 amplitude_scale: np.ndarray | None = None) -> np.ndarray:
    """ECG in millivolts at times `t_s` (ECG clock, s) given R-peak times on the same clock.

    `artefacts`: list of (t_s, step_mv, tau_s) baseline steps with exponential recovery (the thumb lift).
    `amplitude_scale`: per-beat QRS scaling (ectopic beats look different).
    """
    t = np.asarray(t_s, dtype=float)
    r = np.asarray(r_times_s, dtype=float)
    mv = np.zeros_like(t)
    if r.size:
        ibi = np.diff(r)
        ibi = np.append(ibi, ibi[-1] if ibi.size else 0.85)
        amp = np.ones(r.size) if amplitude_scale is None else np.asarray(amplitude_scale, float)
        for k, rt in enumerate(r):
            lo = int(np.searchsorted(t, rt - 0.35))
            hi = int(np.searchsorted(t, rt + 0.55))
            if hi <= lo:
                continue
            tau = t[lo:hi] - rt
            seg = np.zeros(hi - lo)
            for name, (c, s, a) in ECG_TEMPLATE.items():
                if name == "P" and not p_wave:
                    continue
                if name == "T":
                    c = c * math.sqrt(max(ibi[k], 0.3) / 0.85)
                scale = amp[k] if name in ("Q", "R", "S") else 1.0
                seg += scale * a * np.exp(-((tau - c) ** 2) / (2 * s * s))
            if pacing_spike:
                seg += 1.5 * np.exp(-((tau + 0.040) ** 2) / (2 * 0.0012**2))
            mv[lo:hi] += seg
    if flutter:
        mv += 0.15 * (2.0 * ((t * 5.0) % 1.0) - 1.0)          # sawtooth flutter waves at 300/min
    if baseline_mv > 0:
        for f, a in ((0.18, 1.0), (0.31, 0.6), (0.07, 0.4)):
            mv += baseline_mv * a * np.sin(2 * math.pi * f * t + float(rng.uniform(0, 2 * math.pi)))
    if mains_mv > 0:
        mv += mains_mv * np.sin(2 * math.pi * mains_hz * t + float(rng.uniform(0, 2 * math.pi)))
    if noise_mv > 0:
        mv += rng.normal(0.0, noise_mv, size=t.shape)
    for (ta, step, tau_s) in artefacts or ():
        m = t >= ta
        mv[m] += step * np.exp(-(t[m] - ta) / max(tau_s, 1e-3))
    return mv


def synth_ecg_record(foot_t_ref_s: np.ndarray, pat_s: float, fs: float, duration_s: float, ecg_t0_ref_s: float,
                     rng: np.random.Generator, rhythm: str = "sinus", artefacts_ref: list[tuple[float, float, float]] | None = None,
                     pat_jitter_s: float = 0.004, is_ectopic: np.ndarray | None = None, **wave_kw) -> dict:
    """ECG samples whose R-peaks precede each PPG foot by `pat_s` (+ per-beat jitter), on the ECG clock
    (t_ecg = t_ref - ecg_t0_ref_s). Section 6.6 (PAT) and 4.3 (artefact). Returns mv, t_ecg_s, r times on both clocks."""
    prof = rhythm_profile(rhythm)
    feet = np.asarray(foot_t_ref_s, dtype=float)
    pat = pat_s + (rng.normal(0.0, pat_jitter_s, feet.size) if pat_jitter_s > 0 else 0.0)
    r_ref = feet - pat
    n = int(round(duration_s * fs))
    t_ecg = np.arange(n) / fs
    r_ecg = r_ref - ecg_t0_ref_s
    inside = (r_ecg > -0.4) & (r_ecg < duration_s + 0.4)
    ect = np.zeros(feet.size, bool) if is_ectopic is None else np.asarray(is_ectopic, bool)
    amp = np.where(ect, 1.35, 1.0)
    art = [(ta - ecg_t0_ref_s, step, tau) for (ta, step, tau) in (artefacts_ref or [])]
    kw = {"p_wave": prof["p_wave"], "pacing_spike": prof["pacing_spike"], "flutter": prof["flutter"], "noise_mv": prof["noise_mv"]}
    kw.update(wave_kw)
    mv = ecg_waveform(t_ecg, r_ecg[inside], rng, artefacts=art, amplitude_scale=amp[inside], **kw)
    keep = (r_ecg >= 0) & (r_ecg < duration_s)
    return {"mv": mv, "t_ecg_s": t_ecg, "fs": float(fs), "r_times_ecg_s": r_ecg[keep], "r_times_ref_s": r_ref[keep],
            "foot_t_ref_s": feet[keep], "pat_per_beat_s": pat[keep], "is_ectopic": ect[keep], "pat_s": float(pat_s),
            "ecg_t0_ref_s": float(ecg_t0_ref_s), "artefacts_ecg_s": art, "rhythm": rhythm}


# ----------------------------------------------------------------------------- ATC writer (CONTRACTS 3.6)
def _fixed(s: str, n: int) -> bytes:
    b = s.encode("ascii", "replace")[: n - 1]
    return b + b"\x00" * (n - len(b))


def _block(block_id: bytes, data: bytes) -> bytes:
    if len(block_id) != 4:
        raise ValueError("block id must be 4 bytes")
    crc = zlib.crc32(block_id + data) & 0xFFFFFFFF
    return struct.pack("<I", len(data)) + block_id + data + struct.pack("<I", crc)


def write_atc(path: str | Path, mv: np.ndarray, fs: float, start_iso: str, device_id: str = "KARDIA-SYNTH-0001",
              phone_model: str = "Kardia tablet (synthetic)", recorder_sw: str = "KardiaApp synth", recorder_hw: str = "KardiaMobile Card",
              location: str = "MCH Kolkata", record_uuid: str | None = None, resolution_nv: int = ATC_RESOLUTION_NV) -> Path:
    """Write an ATC v1 chunk file: info (date 32, uuid 40, udid 44, model 32, sw 32, hw 32, location 52 bytes),
    fmt (u8 format, u16 Hz, u16 nV/LSB, u8 flags, u16 reserved) and ecg (int16 LE)."""
    path = Path(path)
    info = (_fixed(start_iso, 32) + _fixed(record_uuid or str(_uuid.uuid4()), 40) + _fixed(device_id, 44)
            + _fixed(phone_model, 32) + _fixed(recorder_sw, 32) + _fixed(recorder_hw, 32) + _fixed(location, 52))
    fmt = struct.pack("<BHHBH", 1, int(round(fs)), int(resolution_nv), 0, 0)
    lsb_mv = resolution_nv * 1e-6
    samples = np.clip(np.rint(np.asarray(mv, dtype=float) / lsb_mv), -32768, 32767).astype("<i2")
    with open(path, "wb") as fh:
        fh.write(b"ALIVE" + bytes(ATC_VERSION))
        fh.write(_block(b"info", info))
        fh.write(_block(b"fmt ", fmt))
        fh.write(_block(b"ecg ", samples.tobytes()))
    return path


def write_kardia_meta(path: str | Path, start_wall_ts: str, duration_s: float, fs: float, app_rhythm_label: str,
                      device_id: str, export_format: str) -> Path:
    path = Path(path)
    path.write_text(json.dumps({"start_wall_ts": start_wall_ts, "duration_s": float(duration_s), "fs": float(fs),
                                "app_rhythm_label": app_rhythm_label, "device_id": device_id, "export_format": export_format},
                               indent=1), encoding="utf-8")
    return path


def write_pdf_strip(path: str | Path, mv: np.ndarray, fs: float, title: str = "KardiaMobile (synthetic)",
                    row_seconds: float = 10.0, mm_per_s: float = 25.0, mm_per_mv: float = 10.0) -> Path:
    """Kardia-style PDF strip at 25 mm/s and 10 mm/mV on a red/pink grid with a dark trace (section 6.4 fallback).
    Rendered with matplotlib (imported lazily)."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages

    path = Path(path)
    mv = np.asarray(mv, dtype=float)
    n_rows = int(math.ceil(mv.size / fs / row_seconds))
    rows_per_page = 6
    width_mm = row_seconds * mm_per_s
    row_h_mm = 40.0
    with PdfPages(path) as pdf:
        for page in range(int(math.ceil(n_rows / rows_per_page))):
            fig = plt.figure(figsize=((width_mm + 20) / 25.4, (rows_per_page * row_h_mm + 30) / 25.4))
            fig.text(0.05, 0.97, f"{title}  {mm_per_s:.0f} mm/s  {mm_per_mv:.0f} mm/mV  {fs:.0f} Hz", fontsize=8)
            for r in range(rows_per_page):
                row = page * rows_per_page + r
                if row >= n_rows:
                    break
                ax = fig.add_axes([10 / (width_mm + 20), 1 - (20 + (r + 1) * row_h_mm) / (rows_per_page * row_h_mm + 30),
                                   width_mm / (width_mm + 20), row_h_mm / (rows_per_page * row_h_mm + 30)])
                ax.set_xlim(0, width_mm)
                ax.set_ylim(-row_h_mm / 2, row_h_mm / 2)
                for x in np.arange(0, width_mm + 0.1, 1.0):
                    ax.axvline(x, color="#f4b6b6" if x % 5 else "#e06666", lw=0.3 if x % 5 else 0.6, zorder=0)
                for y in np.arange(-row_h_mm / 2, row_h_mm / 2 + 0.1, 1.0):
                    ax.axhline(y, color="#f4b6b6" if y % 5 else "#e06666", lw=0.3 if y % 5 else 0.6, zorder=0)
                i0, i1 = int(row * row_seconds * fs), int(min((row + 1) * row_seconds * fs, mv.size))
                seg = mv[i0:i1]
                ax.plot(np.arange(seg.size) / fs * mm_per_s, np.clip(seg, -1.9, 1.9) * mm_per_mv, color="#111111", lw=0.7, zorder=2)
                ax.set_xticks([])
                ax.set_yticks([])
                for sp in ax.spines.values():
                    sp.set_visible(False)
            pdf.savefig(fig)
            plt.close(fig)
    return path


def app_rhythm_label(rhythm: str, rng: np.random.Generator) -> str:
    """The Kardia app's own label (a covariate only, section 6.4): mostly right, sometimes Unclassified."""
    u = float(rng.random())
    if rhythm == "sinus":
        return "Normal" if u < 0.92 else "Unclassified"
    if rhythm == "af":
        return "Possible Atrial Fibrillation" if u < 0.85 else "Unclassified"
    if rhythm in ("svt", "aflutter"):
        return "Tachycardia" if u < 0.7 else "Unclassified"
    if rhythm == "unreadable":
        return "Unreadable"
    return "Unclassified"


def write_ecg_record(ecg_dir: str | Path, study_id: str, number: int, foot_t_ref_s: np.ndarray, pat_s: float, rhythm: str,
                     cfg, rng: np.random.Generator, pi_truth: dict, seconds: float, wall0_ns: int, pi_wall_offset_s: float = 0.0,
                     kardia_clock_offset_s: float = -0.8, app_latency_s: float | None = None, export_format: str = "atc",
                     kardia_duration_s: float | None = None, is_ectopic: np.ndarray | None = None, device_id: str = "KARDIA-SYNTH-0001") -> dict:
    """Write kardia_####.atc (or .pdf) and kardia_meta.json for one participant; return the ECG truth.

    Section 4.3: the recording starts `app_latency_s` (0.5-1.5 s) after thumb contact when the Kardia
    duration covers the clip, or after P1 onset when the app only allows a shorter recording
    (cfg study.kardia_duration_s < video_seconds). `start_time` is the Kardia device wall clock = Pi wall
    clock (true wall + Pi offset) corrected to the true wall, plus the Kardia clock offset.
    """
    ecg_dir = Path(ecg_dir)
    ecg_dir.mkdir(parents=True, exist_ok=True)
    fs = float(cfg.get("ecg.fs"))
    kd = float(kardia_duration_s if kardia_duration_s is not None else cfg.get("study.kardia_duration_s"))
    latency = float(rng.uniform(0.5, 1.5)) if app_latency_s is None else float(app_latency_s)
    if kd + 0.5 < seconds:
        p1 = min(p["on_s"] for p in pi_truth["led_schedule"] if p["pattern"] == "P1")
        anchor, anchor_kind = p1, "p1_onset"
    else:
        anchor, anchor_kind = float(pi_truth["thumb_contact_t_ref_s"]), "thumb_contact"
    ecg_t0_ref = anchor + latency
    artefacts = []
    lift = pi_truth.get("thumb_lift_t_ref_s")
    if lift is not None:
        artefacts.append((float(lift), float(rng.uniform(2.0, 3.0)), 1.0))
        artefacts.append((float(pi_truth["thumb_down_t_ref_s"]), -float(rng.uniform(1.0, 1.5)), 0.6))
    rec = synth_ecg_record(foot_t_ref_s, pat_s, fs, kd, ecg_t0_ref, rng, rhythm, artefacts, is_ectopic=is_ectopic)
    true_wall_start_ns = int(wall0_ns + round(ecg_t0_ref * 1e9))
    kardia_wall = dt.datetime.fromtimestamp((true_wall_start_ns / 1e9) + kardia_clock_offset_s, tz=IST)
    start_iso = kardia_wall.isoformat(timespec="milliseconds")
    label = app_rhythm_label(rhythm, rng)
    if export_format == "pdf":
        file = write_pdf_strip(ecg_dir / f"kardia_{number:04d}.pdf", rec["mv"], fs, title=f"KardiaMobile {study_id} (synthetic)")
    else:
        file = write_atc(ecg_dir / f"kardia_{number:04d}.atc", rec["mv"], fs, start_iso, device_id=device_id)
    write_kardia_meta(ecg_dir / "kardia_meta.json", start_iso, kd, fs, label, device_id, export_format)
    truth = {
        "study_id": study_id, "file": file.name, "export_format": export_format, "fs": fs, "duration_s": kd,
        "ecg_t0_ref_s": float(ecg_t0_ref), "anchor_kind": anchor_kind, "anchor_t_ref_s": float(anchor), "app_latency_s": latency,
        "kardia_clock_offset_s": float(kardia_clock_offset_s), "start_wall_ts": start_iso, "true_start_wall_ns": true_wall_start_ns,
        "pat_s": float(pat_s), "r_times_ecg_s": rec["r_times_ecg_s"].tolist(), "r_times_ref_s": rec["r_times_ref_s"].tolist(),
        "foot_t_ref_s": rec["foot_t_ref_s"].tolist(), "pat_per_beat_s": rec["pat_per_beat_s"].tolist(),
        "is_ectopic": rec["is_ectopic"].astype(bool).tolist(), "artefacts_ecg_s": rec["artefacts_ecg_s"],
        "artefact_onset_ecg_s": rec["artefacts_ecg_s"][0][0] if rec["artefacts_ecg_s"] else None,
        "artefact_onset_ref_s": float(lift) if lift is not None else None, "rhythm": rhythm, "app_rhythm_label": label,
        "ecg_hr_bpm": float(60.0 / np.mean(np.diff(rec["r_times_ecg_s"]))) if rec["r_times_ecg_s"].size > 2 else None,
        "clock_map": {"stream": "ecg", "offset_s": float(ecg_t0_ref), "drift": 0.0, "method": "synthetic_truth"},
    }
    (ecg_dir / "ecg_truth.json").write_text(json.dumps(truth, indent=1), encoding="utf-8")
    return truth
