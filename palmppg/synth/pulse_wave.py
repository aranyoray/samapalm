"""Beat schedules and PPG beat templates with known, measured morphology.

Protocol sections served: 8 (positive control: "inject a known pulse ... realistic morphology, HR 50 to
120, with HRV"), 6.5 (the per-beat truth table that beat segmentation and morphology are scored against)
and 6.6 (ectopic beats whose capture fraction the ECG-to-pulse comparison reports).

Conventions
  * Times are float seconds on the reference clock. A beat's `foot_t` is the instant its upstroke starts.
  * The beat template `W(tau)` (tau = seconds after the foot) is normalised to unit peak with the foot at
    zero, so a modulation `DC * (1 - ac_dc * W(t))` has peak-to-peak AC/DC equal to `ac_dc`.
  * The pulse-signal polarity convention of CONTRACTS section 6 (positive = more blood volume) means the
    waveform returned here is the *blood-volume* signal; intensity falls when it rises.
  * Morphology inputs are design targets; the truth that scoring uses is *measured* on the generated
    template (`measure_template`) and per beat on the composite signal (`measure_beats`, summarised by
    `summarise_morphology`), so the numbers a perfect algorithm would recover are what is written as ground
    truth. `decay_tau_s` is the log-linear fit of the unit-peak beat from DECAY_FIT_OFFSET_S after the dicrotic
    peak (the systolic peak when there is no notch) to just before the next foot (at most DECAY_FIT_LEN_S).

Template model (sum of three parts, then unit-peak normalised)
  S(tau)  systolic lobe: raised-cosine upstroke reaching 1 at `upstroke_s`, Gaussian fall whose sigma is set
          so the lobe's full width at half maximum equals `systolic_width_s`;
  T(tau)  diastolic runoff: rises with the upstroke, then decays as exp(-(tau - upstroke_s)/decay_tau_s);
  D(tau)  dicrotic (reflected) wave: Gaussian rise of width `dicrotic_width_s` peaking two sigmas after
          `notch_time_s`, then an exponential fall with `decay_tau_s` (so the diastolic runoff after the
          dicrotic peak decays with one time constant).
  The levels of T and D are solved from a 2x2 linear system so that the dicrotic peak sits at
  `reflection_index` and the notch at `reflection_index - notch_depth` (both in unit-peak units); when the
  solution would need a negative level it is clipped to zero and the measured values report what resulted.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

MORPHOLOGY_KEYS = ("upstroke_s", "systolic_width_s", "notch_time_s", "notch_depth", "reflection_index",
                   "decay_tau_s", "dicrotic_width_s")
MEASURED_KEYS = ("upstroke_s", "systolic_width_s", "notch_time_s", "notch_depth", "reflection_index", "decay_tau_s")

DEFAULT_MORPHOLOGY = {
    "upstroke_s": 0.17, "systolic_width_s": 0.20, "notch_time_s": 0.36, "notch_depth": 0.10,
    "reflection_index": 0.45, "decay_tau_s": 0.40, "dicrotic_width_s": 0.08,
}
IBI_BOUNDS_S = (0.30, 2.5)        # physiological guard for generated intervals (not a protocol threshold)
TEMPLATE_DT_S = 0.0005            # fine grid for template measurement
DECAY_FIT_OFFSET_S = 0.05         # decay fit starts this long after the dicrotic (or systolic) peak
DECAY_FIT_LEN_S = 0.60            # and runs at most this long
DECAY_FIT_TAIL_GUARD_S = 0.02     # stop this long before the end of the available beat
DECAY_FIT_MIN_S = 0.12            # NaN when fewer than this remain
NOTCH_MIN_DEPTH = 0.01            # a dip shallower than this (unit-peak units) is not a notch


def default_morphology(**over) -> dict:
    """Return a copy of the default morphology targets, updated with `over`."""
    m = dict(DEFAULT_MORPHOLOGY)
    m.update({k: float(v) for k, v in over.items()})
    return m


# ----------------------------------------------------------------------------- beat schedule
@dataclass
class BeatSchedule:
    """Foot times of every beat plus per-beat flags (reference-clock seconds)."""

    foot_t: np.ndarray
    is_ectopic: np.ndarray
    amplitude: np.ndarray
    hr_bpm_nominal: float
    params: dict = field(default_factory=dict)

    @property
    def n_beats(self) -> int:
        return int(self.foot_t.size)

    @property
    def ibi_s(self) -> np.ndarray:
        """Interval following each foot (NaN for the last beat)."""
        out = np.full(self.foot_t.size, np.nan)
        if self.foot_t.size > 1:
            out[:-1] = np.diff(self.foot_t)
        return out

    def mean_hr_bpm(self) -> float:
        """Mean rate in bpm over the generated intervals."""
        ibi = self.ibi_s[np.isfinite(self.ibi_s)]
        return float(60.0 / np.mean(ibi)) if ibi.size else float("nan")

    def hr_series(self, t_s: np.ndarray) -> np.ndarray:
        """Instantaneous rate (bpm) at times `t_s`: 60/IBI placed at interval midpoints, linearly interpolated."""
        return instantaneous_hr(self.foot_t, np.asarray(t_s, dtype=float))

    def to_dict(self) -> dict:
        return {"foot_t": self.foot_t.tolist(), "is_ectopic": self.is_ectopic.astype(bool).tolist(),
                "amplitude": self.amplitude.tolist(), "hr_bpm_nominal": float(self.hr_bpm_nominal),
                "params": dict(self.params)}

    @classmethod
    def from_dict(cls, d: dict) -> "BeatSchedule":
        return cls(np.asarray(d["foot_t"], float), np.asarray(d["is_ectopic"], bool),
                   np.asarray(d.get("amplitude", np.ones(len(d["foot_t"]))), float),
                   float(d.get("hr_bpm_nominal", float("nan"))), dict(d.get("params", {})))


def instantaneous_hr(foot_t: np.ndarray, t_s: np.ndarray) -> np.ndarray:
    """Instantaneous rate in bpm from foot times, evaluated at `t_s` (section 4.3 rate series)."""
    foot_t = np.asarray(foot_t, dtype=float)
    if foot_t.size < 2:
        return np.full(np.asarray(t_s).shape, np.nan)
    ibi = np.diff(foot_t)
    mid = foot_t[:-1] + 0.5 * ibi
    return np.interp(np.asarray(t_s, dtype=float), mid, 60.0 / ibi)


def beat_times(duration_s: float, hr_bpm: float, hrv_sd_s: float, resp_rate_hz: float, resp_amp: float,
               rng: np.random.Generator, n_ectopic: int = 0, t_start: float = 0.0,
               first_foot_s: float | None = None, ectopic_coupling: float = 0.60,
               ectopic_amplitude: float = 0.70) -> BeatSchedule:
    """Generate foot times with respiratory sinus arrhythmia-like modulation and optional ectopic beats.

    Section 8 positive control ("HR 50 to 120, with HRV") and section 6.6 (ectopic beats).
      duration_s     clip length; feet are kept in [t_start, t_start + duration_s)
      hr_bpm         mean rate (bpm); hrv_sd_s random interval jitter (s, Gaussian, beat to beat)
      resp_rate_hz   breathing rate (Hz); resp_amp relative IBI modulation amplitude (0.05 = +/-5 %)
                     with intervals shortening during inspiration
      n_ectopic      premature beats: foot pulled earlier to `ectopic_coupling` x the local IBI, followed by
                     a full compensatory pause (the next sinus foot is unchanged), amplitude scaled by
                     `ectopic_amplitude` with a mild post-ectopic potentiation on the following beat
    Returns a BeatSchedule (feet in seconds on the reference clock).
    """
    if hr_bpm <= 0:
        raise ValueError("hr_bpm must be positive")
    ibi0 = 60.0 / float(hr_bpm)
    resp_phase = float(rng.uniform(0, 2 * math.pi))
    t = t_start + (float(first_foot_s) if first_foot_s is not None else float(rng.uniform(0.0, ibi0)))
    feet = []
    end = t_start + duration_s
    while t < end:
        feet.append(t)
        ibi = ibi0 * (1.0 - resp_amp * math.sin(2 * math.pi * resp_rate_hz * t + resp_phase))
        ibi += float(rng.normal(0.0, hrv_sd_s)) if hrv_sd_s > 0 else 0.0
        t += float(np.clip(ibi, IBI_BOUNDS_S[0], IBI_BOUNDS_S[1]))
    foot_t = np.asarray(feet, dtype=float)
    n = foot_t.size
    is_ect = np.zeros(n, dtype=bool)
    amp = np.ones(n, dtype=float)
    n_ect = int(min(max(n_ectopic, 0), max((n - 6) // 4, 0)))
    if n_ect > 0:
        candidates = np.arange(3, n - 3)
        chosen: list[int] = []
        order = rng.permutation(candidates)
        for k in order:
            if all(abs(int(k) - c) >= 4 for c in chosen):
                chosen.append(int(k))
            if len(chosen) == n_ect:
                break
        for k in sorted(chosen):
            local_ibi = foot_t[k] - foot_t[k - 1]
            foot_t[k] = foot_t[k - 1] + ectopic_coupling * local_ibi
            is_ect[k] = True
            amp[k] = ectopic_amplitude
            amp[k + 1] = 1.0 + 0.5 * (1.0 - ectopic_amplitude)
    return BeatSchedule(foot_t, is_ect, amp, float(hr_bpm), {
        "duration_s": float(duration_s), "hr_bpm": float(hr_bpm), "hrv_sd_s": float(hrv_sd_s),
        "resp_rate_hz": float(resp_rate_hz), "resp_amp": float(resp_amp), "n_ectopic": int(n_ect),
        "t_start": float(t_start), "ectopic_coupling": float(ectopic_coupling),
        "ectopic_amplitude": float(ectopic_amplitude)})


# ----------------------------------------------------------------------------- beat template
def _systolic_lobe(tau: np.ndarray, t_p: float, sigma_s: float) -> np.ndarray:
    out = np.zeros_like(tau)
    up = (tau >= 0) & (tau < t_p)
    out[up] = 0.5 * (1.0 - np.cos(math.pi * tau[up] / t_p))
    dn = tau >= t_p
    out[dn] = np.exp(-((tau[dn] - t_p) ** 2) / (2.0 * sigma_s**2))
    return out


def _ramp(tau: np.ndarray, t_p: float) -> np.ndarray:
    out = np.zeros_like(tau)
    up = (tau >= 0) & (tau < t_p)
    out[up] = 0.5 * (1.0 - np.cos(math.pi * tau[up] / t_p))
    out[tau >= t_p] = 1.0
    return out


def _resolve(morph: dict) -> dict:
    """Validate the targets and solve the diastolic and dicrotic levels (see module docstring)."""
    m = dict(DEFAULT_MORPHOLOGY)
    m.update({k: float(v) for k, v in morph.items() if k in MORPHOLOGY_KEYS})
    t_p = max(m["upstroke_s"], 0.04)
    w_r = max(m["systolic_width_s"] - 0.5 * t_p, 0.03)
    sigma_s = w_r / math.sqrt(2.0 * math.log(2.0))
    sigma_d = max(m["dicrotic_width_s"], 0.02)
    t_n = max(m["notch_time_s"], t_p + 0.05)
    t_dp = t_n + 2.0 * sigma_d
    tau = max(m["decay_tau_s"], 0.05)
    ri = float(np.clip(m["reflection_index"], 0.0, 0.95))
    nd = float(np.clip(m["notch_depth"], 0.0, ri))
    s_n = float(_systolic_lobe(np.array([t_n]), t_p, sigma_s)[0])
    s_d = float(_systolic_lobe(np.array([t_dp]), t_p, sigma_s)[0])
    a_n = math.exp(-(t_n - t_p) / tau)
    a_d = math.exp(-(t_dp - t_p) / tau)
    c_p = math.exp(-((t_p - t_dp) ** 2) / (2.0 * sigma_d**2))
    e2 = math.exp(-2.0)
    A = np.array([[a_d - ri, 1.0 - ri * c_p], [a_n - (ri - nd), e2 - (ri - nd) * c_p]])
    b = np.array([ri - s_d, (ri - nd) - s_n])
    try:
        sol = np.linalg.solve(A, b)
    except np.linalg.LinAlgError:
        sol = np.array([0.4, ri])
    t_level = float(np.clip(sol[0], 0.0, 3.0))
    d_amp = float(np.clip(sol[1], 0.0, 3.0))
    return {"t_p": t_p, "sigma_s": sigma_s, "sigma_d": sigma_d, "t_dp": t_dp, "tau": tau,
            "t_level": t_level, "d_amp": d_amp, "targets": m}


def _dicrotic(tau: np.ndarray, t_dp: float, sigma_d: float, decay_tau: float) -> np.ndarray:
    """Dicrotic wave: Gaussian rise to its peak at t_dp, exponential fall with the diastolic time constant."""
    rise = np.exp(-((tau - t_dp) ** 2) / (2.0 * sigma_d**2))
    fall = np.exp(-(tau - t_dp) / decay_tau)
    return np.where(tau < t_dp, rise, fall)


def _raw_template(tau: np.ndarray, r: dict) -> np.ndarray:
    tau = np.asarray(tau, dtype=float)
    s = _systolic_lobe(tau, r["t_p"], r["sigma_s"])
    t = r["t_level"] * _ramp(tau, r["t_p"]) * np.exp(-np.maximum(tau - r["t_p"], 0.0) / r["tau"])
    d = r["d_amp"] * _dicrotic(tau, r["t_dp"], r["sigma_d"], r["tau"])
    out = s + t + d
    out[tau < 0] = 0.0
    return out


def beat_template(morphology: dict | None = None, dt_s: float = TEMPLATE_DT_S, max_s: float = 3.0) -> tuple[np.ndarray, np.ndarray]:
    """Unit-peak beat template on a fine grid: returns (tau_s, W). Section 8 positive control morphology."""
    r = _resolve(morphology or {})
    tau = np.arange(0.0, max_s, dt_s)
    w = _raw_template(tau, r)
    peak = float(w.max())
    return tau, w / peak if peak > 0 else w


def measure_template(morphology: dict | None = None, dt_s: float = TEMPLATE_DT_S) -> dict:
    """Measure the morphology a perfect algorithm would recover from the clean template.

    Returns upstroke_s (foot to peak), systolic_width_s (full width at half maximum), notch_time_s
    (foot to the first local minimum after the peak), notch_depth (dicrotic peak minus notch, unit-peak
    units), reflection_index (dicrotic peak height), decay_tau_s (log-linear fit of the runoff after the
    dicrotic wave) and notch_present. NaN when a feature does not exist.
    """
    tau, w = beat_template(morphology, dt_s)
    return _measure_curve(tau, w)


def _measure_curve(tau: np.ndarray, w: np.ndarray, fit_len_s: float = DECAY_FIT_LEN_S) -> dict:
    ip = int(np.argmax(w))
    out: dict = {"upstroke_s": float(tau[ip]), "peak_value": float(w[ip])}
    half = 0.5 * w[ip]
    left = np.where(w[:ip] < half)[0]
    right = np.where(w[ip:] < half)[0]
    t_left = float(np.interp(half, [w[left[-1]], w[left[-1] + 1]], [tau[left[-1]], tau[left[-1] + 1]])) if left.size else float(tau[0])
    if right.size:
        j = ip + right[0]
        t_right = float(np.interp(half, [w[j], w[j - 1]], [tau[j], tau[j - 1]]))
    else:
        t_right = float(tau[-1])
    out["systolic_width_s"] = t_right - t_left
    notch = None
    dic = None
    for i in range(ip + 1, w.size - 1):
        if w[i - 1] > w[i] <= w[i + 1]:
            notch = i
            break
    if notch is not None:
        for i in range(notch + 1, w.size - 1):
            if w[i - 1] < w[i] >= w[i + 1]:
                dic = i
                break
    if notch is not None and dic is not None and w[dic] - w[notch] > NOTCH_MIN_DEPTH:
        out.update({"notch_time_s": float(tau[notch] - tau[0]), "notch_depth": float(w[dic] - w[notch]),
                    "reflection_index": float(w[dic] / w[ip]), "dicrotic_time_s": float(tau[dic] - tau[0]),
                    "notch_present": True})
        start = dic
    else:
        out.update({"notch_time_s": float("nan"), "notch_depth": 0.0, "reflection_index": float("nan"),
                    "dicrotic_time_s": float("nan"), "notch_present": False})
        start = ip
    # decay constant: log-linear fit of the diastolic runoff from DECAY_FIT_OFFSET_S after the dicrotic peak (the
    # systolic peak when there is no notch) to DECAY_FIT_TAIL_GUARD_S before the end of the available curve (a beat
    # ends at the next foot); NaN when fewer than DECAY_FIT_MIN_S of curve remain
    dt = float(tau[1] - tau[0]) if tau.size > 1 else 1.0
    i0 = start + int(round(DECAY_FIT_OFFSET_S / dt))
    i1 = w.size - int(round(DECAY_FIT_TAIL_GUARD_S / dt))
    i1 = min(i1, i0 + int(round(fit_len_s / dt)))
    seg = w[i0:i1]
    if seg.size >= max(5, int(round(DECAY_FIT_MIN_S / dt))) and np.all(seg > 1e-6):
        slope = np.polyfit(tau[i0:i1], np.log(seg), 1)[0]
        out["decay_tau_s"] = float(-1.0 / slope) if slope < 0 else float("nan")
        out["decay_fit_window_s"] = [float(tau[i0] - tau[0]), float(tau[i1 - 1] - tau[0])]
    else:
        out["decay_tau_s"] = float("nan")
        out["decay_fit_window_s"] = None
    out["upstroke_s"] = float(tau[ip] - tau[0])
    return out


# ----------------------------------------------------------------------------- composite waveform
def ppg_waveform(t: np.ndarray, foot_times: np.ndarray, morphology: dict | None = None,
                 amplitudes: np.ndarray | None = None) -> np.ndarray:
    """Blood-volume waveform at times `t` (s) as the superposition of one unit-peak template per beat.

    Each beat contributes `amplitude_k * W(t - foot_k)` for t >= foot_k; tails run under the following
    beat, so a premature beat is naturally cut short. The sum is scaled so that the median foot-to-peak rise of
    the amplitude-1 beats is exactly 1 (`composite_scale`), which keeps "ac_dc" a peak-to-peak quantity
    (section 8: "AC/DC in G ... realistic morphology").
    """
    t = np.asarray(t, dtype=float)
    foot_times = np.asarray(foot_times, dtype=float)
    tau, w = beat_template(morphology)
    amp = np.ones(foot_times.size) if amplitudes is None else np.asarray(amplitudes, dtype=float)
    scale = composite_scale(foot_times, morphology, amp)
    return _superpose(t, foot_times, tau, w, amp) * scale


def _superpose(t: np.ndarray, foot_times: np.ndarray, tau: np.ndarray, w: np.ndarray, amp: np.ndarray) -> np.ndarray:
    cut = np.where(w > 1e-4)[0]
    span = float(tau[cut[-1]]) if cut.size else float(tau[-1])
    out = np.zeros(t.shape, dtype=float)
    order = np.argsort(t)
    ts = t[order]
    acc = np.zeros(ts.size)
    for k, f in enumerate(foot_times):
        i0 = int(np.searchsorted(ts, f, side="left"))
        i1 = int(np.searchsorted(ts, f + span, side="right"))
        if i1 > i0:
            acc[i0:i1] += amp[k] * np.interp(ts[i0:i1] - f, tau, w)
    out[order] = acc
    return out


def composite_scale(foot_times: np.ndarray, morphology: dict | None = None, amplitudes: np.ndarray | None = None,
                    dt_s: float = 0.002) -> float:
    """Factor that makes the median foot-to-peak rise of the superposed beats equal to 1, so `ac_dc` keeps its
    peak-to-peak meaning whatever the rate (tails of earlier beats run under later ones)."""
    foot_times = np.asarray(foot_times, dtype=float)
    if foot_times.size == 0:
        return 1.0
    tau, w = beat_template(morphology)
    amp = np.ones(foot_times.size) if amplitudes is None else np.asarray(amplitudes, dtype=float)
    grid = np.arange(foot_times[0], foot_times[-1] + 1.5, dt_s)
    sig = _superpose(grid, foot_times, tau, w, amp)
    rises = []
    for k, f in enumerate(foot_times):
        nxt = foot_times[k + 1] if k + 1 < foot_times.size else f + 1.5
        i0, i1 = int(np.searchsorted(grid, f)), int(np.searchsorted(grid, nxt))
        if i1 - i0 > 2 and amp[k] == 1.0:
            rises.append(float(sig[i0:i1].max() - sig[i0]))
    if not rises:
        rises = [float(sig.max() - sig.min())]
    med = float(np.median(rises))
    return 1.0 / med if med > 1e-9 else 1.0


def measure_beats(foot_times: np.ndarray, morphology: dict | None = None, amplitudes: np.ndarray | None = None,
                  is_ectopic: np.ndarray | None = None, dt_s: float = 0.001) -> pd.DataFrame:
    """Per-beat ground-truth table measured on the composite waveform (section 6.5 scoring).

    Columns: beat, foot_t (intersecting-tangents foot on the composite, the study's foot definition, cfg
    beats.foot_method), onset_t (where the upstroke was generated; the tangent foot lies about a fifth of the
    upstroke time later), peak_t, notch_t, dicrotic_t, ibi_s, amplitude, is_ectopic, notch_present, peak_value,
    and the per-beat morphology measured on the beat's own window [foot, next foot) referenced to its foot
    level and unit-peak normalised: upstroke_s, systolic_width_s, notch_time_s, notch_depth, reflection_index,
    decay_tau_s (NaN when the feature does not exist or the beat is too short for the decay fit window).
    """
    foot_times = np.asarray(foot_times, dtype=float)
    n = foot_times.size
    amp = np.ones(n) if amplitudes is None else np.asarray(amplitudes, dtype=float)
    ect = np.zeros(n, bool) if is_ectopic is None else np.asarray(is_ectopic, bool)
    cols = ["beat", "foot_t", "onset_t", "peak_t", "notch_t", "dicrotic_t", "ibi_s", "amplitude", "is_ectopic", "notch_present",
            "peak_value", *MEASURED_KEYS]
    if n == 0:
        return pd.DataFrame(columns=cols)
    tau_t, w_t = beat_template(morphology)
    span = float(tau_t[np.where(w_t > 1e-4)[0][-1]])
    grid = np.arange(foot_times[0], foot_times[-1] + span + dt_s, dt_s)
    sig = ppg_waveform(grid, foot_times, morphology, amp)
    rows = []
    for k in range(n):
        f = foot_times[k]
        nxt = foot_times[k + 1] if k + 1 < n else f + span
        i_on = int(np.searchsorted(grid, f))
        i1 = max(int(np.searchsorted(grid, nxt)), i_on + 10)
        i_pk = i_on + int(np.argmax(sig[i_on:i1]))
        ft = tangent_foot(grid[max(i_on - 60, 0):i_pk + 1], sig[max(i_on - 60, 0):i_pk + 1])
        i0 = int(np.clip(np.searchsorted(grid, ft), i_on, i_pk))
        seg = sig[i0:i1] - sig[i0]
        peak = float(seg.max())
        m = _measure_curve(grid[i0:i1] - grid[i0], seg / peak) if peak > 1e-6 else {}
        present = bool(m.get("notch_present", False))
        rows.append({"beat": k, "foot_t": float(ft), "onset_t": float(f), "peak_t": float(grid[i_pk]),
                     "notch_t": float(ft + m["notch_time_s"]) if present else float("nan"),
                     "dicrotic_t": float(ft + m["dicrotic_time_s"]) if present else float("nan"),
                     "ibi_s": float(foot_times[k + 1] - f) if k + 1 < n else float("nan"),
                     "amplitude": float(amp[k]), "is_ectopic": bool(ect[k]), "notch_present": present,
                     "peak_value": float(sig[i_pk]),
                     **{key: float(m.get(key, float("nan"))) for key in MEASURED_KEYS}})
    return pd.DataFrame(rows, columns=cols)


def tangent_foot(t: np.ndarray, x: np.ndarray) -> float:
    """Intersecting-tangents foot (cfg beats.foot_method): the tangent at the steepest point of the upstroke
    ending at the last sample meets the level of the preceding minimum. `t`, `x` cover [before the onset, peak]."""
    t = np.asarray(t, float)
    x = np.asarray(x, float)
    if t.size < 3:
        return float(t[0])
    slopes = np.diff(x) / np.diff(t)
    k = int(np.argmax(slopes))
    slope = slopes[k]
    if slope <= 0:
        return float(t[int(np.argmin(x))])
    t_s, x_s = 0.5 * (t[k] + t[k + 1]), 0.5 * (x[k] + x[k + 1])
    y_min = float(x[: k + 1].min())
    return float(np.clip(t_s + (y_min - x_s) / slope, t[0], t[-1]))


def summarise_morphology(table: pd.DataFrame, exclude_ectopic: bool = True) -> dict:
    """Clip-level truth: median over beats of each per-beat morphology value (ectopic beats and the beat after
    each one excluded by default), plus the notch presence fraction and the number of beats used."""
    if table.empty:
        return {k: float("nan") for k in MEASURED_KEYS} | {"notch_fraction": float("nan"), "n_beats": 0}
    keep = np.ones(len(table), bool)
    if exclude_ectopic and "is_ectopic" in table:
        e = table["is_ectopic"].to_numpy(bool)
        keep &= ~e
        keep[1:] &= ~e[:-1]
    sub = table[keep]
    out = {k: float(np.nanmedian(sub[k].to_numpy(float))) if np.isfinite(sub[k].to_numpy(float)).any() else float("nan") for k in MEASURED_KEYS}
    out["notch_fraction"] = float(sub["notch_present"].mean()) if len(sub) else float("nan")
    out["n_beats"] = int(len(sub))
    return out


def generate_pulse(duration_s: float, hr_bpm: float, rng: np.random.Generator, hrv_sd_s: float = 0.03,
                   resp_rate_hz: float = 0.25, resp_amp: float = 0.05, n_ectopic: int = 0,
                   morphology: dict | None = None, t_start: float = 0.0) -> dict:
    """One call that returns everything a clip needs: schedule, morphology targets, measured morphology
    and the per-beat table, as a JSON-ready dict (`pulse_truth`). Section 8 positive control.

    `foot_t` are the generated upstroke onsets (what the waveform is built from); `foot_t_tangent` are the
    intersecting-tangents feet measured on the composite (what foot detection is scored against)."""
    sched = beat_times(duration_s, hr_bpm, hrv_sd_s, resp_rate_hz, resp_amp, rng, n_ectopic, t_start)
    morph = default_morphology(**(morphology or {}))
    table = measure_beats(sched.foot_t, morph, sched.amplitude, sched.is_ectopic)
    return {
        "schedule": sched.to_dict(), "foot_t": sched.foot_t.tolist(), "hr_bpm": sched.mean_hr_bpm(),
        "hr_bpm_nominal": float(hr_bpm), "ibi_sd_s": float(np.nanstd(sched.ibi_s)) if sched.n_beats > 2 else 0.0,
        "n_ectopic": int(sched.is_ectopic.sum()), "morphology": morph, "morphology_template": measure_template(morph),
        "morphology_measured": summarise_morphology(table), "beats": table.to_dict(orient="list"),
        "foot_t_tangent": table["foot_t"].tolist(), "composite_scale": composite_scale(sched.foot_t, morph, sched.amplitude),
    }


def waveform_from_truth(pulse_truth: dict, t: np.ndarray) -> np.ndarray:
    """Evaluate the blood-volume waveform of a `pulse_truth` dict (from generate_pulse) at times t."""
    sched = pulse_truth.get("schedule")
    amp = np.asarray(sched["amplitude"], float) if sched else None
    return ppg_waveform(t, np.asarray(pulse_truth["foot_t"], float), pulse_truth.get("morphology"), amp)
