"""Synthetic colour traces with a known pulse, shared by the pulse tests (plus checks of the generator).

The trace model (WP5 brief): DC per channel, 0.5 % AC in green with R:G:B AC ratios 0.5 : 1 : 0.6,
72 bpm with respiratory HRV, a 0.3 Hz motion drift common to all channels, and per-sample noise at a
level a ROI mean of a few thousand pixels shows. Intensity falls when blood volume rises, so the
ground-truth `volume` waveform is in the package polarity.
"""
from __future__ import annotations

import numpy as np
from scipy.signal import find_peaks

from palmppg.core.config import rng

FS = 30.0
DUR_S = 60.0
DC = np.array([300.0, 500.0, 200.0])
AC_RATIOS = np.array([0.5, 1.0, 0.6])
HR_BPM = 72.0


def pulse_waveform(phase: np.ndarray) -> np.ndarray:
    """Zero-mean beat shape over phase in [0, 1): systolic peak at 0.3, dicrotic wave at 0.62."""
    ph = np.mod(phase, 1.0)
    v = np.exp(-((ph - 0.3) ** 2) / (2 * 0.08**2)) + 0.35 * np.exp(-((ph - 0.62) ** 2) / (2 * 0.12**2))
    return v - v.mean()


def rate_profile(t: np.ndarray, hr_bpm: float, hrv: float, ramp: tuple[float, float] | None) -> np.ndarray:
    """Instantaneous rate in bpm: constant with respiratory modulation (0.25 Hz), or a linear ramp."""
    if ramp is not None:
        return np.linspace(ramp[0], ramp[1], t.size)
    return hr_bpm * (1 + hrv * np.sin(2 * np.pi * 0.25 * t))


def synth_traces(hr_bpm: float = HR_BPM, hrv: float = 0.03, drift_amp: float = 0.02, noise: float = 0.0005,
                 ac_g: float = 0.005, seed: int = 1, dur_s: float = DUR_S, fs: float = FS,
                 ramp: tuple[float, float] | None = None, dc: np.ndarray = DC) -> dict:
    """{"t", "rgb" (T, 3), "volume" (T,), "hr_t" (T,) bpm} synthetic ROI-mean traces."""
    g = rng(seed, "synth_traces")
    t = np.arange(int(round(dur_s * fs))) / fs
    hr_t = rate_profile(t, hr_bpm, hrv, ramp)
    phase = np.cumsum(hr_t / 60.0) / fs
    v = pulse_waveform(phase)
    drift = drift_amp * np.sin(2 * np.pi * 0.3 * t + 0.4)
    rgb = dc * (1 + drift[:, None] - AC_RATIOS * ac_g * v[:, None]) + g.normal(0, noise, (t.size, 3)) * dc
    return {"t": t, "rgb": rgb, "volume": v, "hr_t": hr_t}


def synth_pixels(n_pix: int = 48, seed: int = 3, noise: float = 0.002, **kw) -> dict:
    """Per-pixel version for 2SR: (T, n_pix, 3) with pixel-wise DC and pulse amplitude variation."""
    base = synth_traces(seed=seed, noise=0.0, **kw)
    g = rng(seed, "synth_pixels")
    t, v = base["t"], base["volume"]
    dcs = DC * (1 + 0.3 * g.uniform(-1, 1, (n_pix, 1)))
    amp = 1 + 0.2 * g.uniform(-1, 1, (n_pix, 1))
    drift = kw.get("drift_amp", 0.02) * np.sin(2 * np.pi * 0.3 * t + 0.4)
    ratios = AC_RATIOS * kw.get("ac_g", 0.005)
    pix = dcs[None] * (1 + drift[:, None, None] - (amp[None] * ratios[None]) * v[:, None, None])
    pix = pix + g.normal(0, noise, (t.size, n_pix, 3)) * dcs[None]
    return {"t": t, "pix": pix, "volume": v, "hr_t": base["hr_t"]}


def pi_planes_from_rgb(rgb: np.ndarray, seed: int = 11, split: float = 0.01) -> dict[str, np.ndarray]:
    """R, G1, G2, B plane means from an RGB trace: the two greens differ by a fixed gain and independent noise."""
    g = rng(seed, "pi_planes")
    n = rgb.shape[0]
    return {"R": rgb[:, 0], "G1": rgb[:, 1] * (1 + split) + g.normal(0, 0.0003, n) * DC[1],
            "G2": rgb[:, 1] * (1 - split) + g.normal(0, 0.0003, n) * DC[1], "B": rgb[:, 2]}


def _fit_amplitude(t, x, hz):
    y = x - x.mean()
    a = np.column_stack([np.sin(2 * np.pi * hz * t), np.cos(2 * np.pi * hz * t)])
    coef, *_ = np.linalg.lstsq(a, y, rcond=None)
    return float(np.hypot(*coef))


def test_generator_rate_and_beat_count():
    s = synth_traces()
    assert abs(s["hr_t"].mean() - HR_BPM) < 1e-9
    peaks, _ = find_peaks(s["volume"], distance=int(0.5 * FS), prominence=0.5)
    assert abs(peaks.size - HR_BPM * DUR_S / 60.0) <= 1
    assert s["rgb"].shape == (1800, 3) and np.isfinite(s["rgb"]).all()


def test_generator_ac_ratios_and_polarity():
    s = synth_traces(hrv=0.0, drift_amp=0.0, noise=0.0)
    rgb, v = s["rgb"], s["volume"]
    # intensity falls when volume rises: negative correlation in every channel, G strongest
    cors = [np.corrcoef(rgb[:, c], v)[0, 1] for c in range(3)]
    assert all(c < -0.99 for c in cors)
    amp = [(rgb[:, c].max() - rgb[:, c].min()) / DC[c] for c in range(3)]
    assert abs(amp[0] / amp[1] - 0.5) < 1e-6 and abs(amp[2] / amp[1] - 0.6) < 1e-6
    assert abs(amp[1] - 0.005 * (v.max() - v.min())) < 1e-9


def test_ramp_profile_is_linear():
    s = synth_traces(ramp=(60, 90), hrv=0.0)
    assert s["hr_t"][0] == 60 and s["hr_t"][-1] == 90
    assert np.allclose(np.diff(s["hr_t"]), np.diff(s["hr_t"])[0])
