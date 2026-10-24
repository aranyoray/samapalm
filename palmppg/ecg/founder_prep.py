"""ECGFounder preprocessing: the signal chain that turns a single-lead strip into model input.

Split out of `palmppg.ecg.founder` so it can be imported, tested and used to generate golden fixtures without
torch, which the phone-side Kotlin port in android/ecg-model is checked against. `founder` re-exports
everything here, so `founder.preprocess` and the rest keep working.

Source of the chain: https://github.com/PKUDigitalHealth/ECGFounder (MIT), util.filter_bandpass and
dataset.py z_score_normalization.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path

import numpy as np
from scipy.signal import butter, filtfilt, find_peaks, iirnotch, medfilt, resample_poly

SOURCE_URL = "https://github.com/PKUDigitalHealth/ECGFounder"
WEIGHTS_URL = "https://huggingface.co/PKUDigitalHealth/ECGFounder/blob/main/1_lead_ECGFounder.pth"
TASKS_PATH = Path(__file__).resolve().parents[2] / "configs" / "ecgfounder_tasks.txt"
FS_MODEL = 500
WIN_S = 10.0
WIN = int(FS_MODEL * WIN_S)          # 5000 samples
N_CLASSES = 150
ZSCORE_EPS = 1e-8
POLARITY_NEG_FRAC = 0.7              # flip when at least this share of beats has a negative dominant deflection
POLARITY_MIN_BEATS = 3
OUTPUT_SUFFIX = "_ecg_founder.json"
USE_NOTE = ("Research annotation for the study clinician and the clinician-read comparison (H6). Not a result for "
            "the participant without ethics approval and a clinician over-read (design section 9).")
FILTER_DESC = {True: "util.filter_bandpass (dataset.py): 50 Hz notch Q=30, Butterworth order 4 0.67-40 Hz filtfilt, "
                     "minus 0.4 s running median; then z-score",
               False: "none (ptbxl_eval.py): z-score only"}

# Rhythm subset (index into the 150 outputs: tasks.txt name), checked against configs/ecgfounder_tasks.txt.
RHYTHM_LABELS: dict[int, str] = {
    1: "NORMAL SINUS RHYTHM", 3: "SINUS RHYTHM", 4: "SINUS BRADYCARDIA", 5: "ATRIAL FIBRILLATION",
    6: "SINUS TACHYCARDIA", 9: "PREMATURE VENTRICULAR COMPLEXES", 16: "PREMATURE ATRIAL COMPLEXES",
    19: "PREMATURE SUPRAVENTRICULAR COMPLEXES", 32: "ATRIAL FLUTTER", 33: "MARKED SINUS BRADYCARDIA",
    34: "WITH SINUS ARRHYTHMIA", 39: "UNDETERMINED RHYTHM", 49: "JUNCTIONAL RHYTHM", 79: "WITH 1ST DEGREE AV BLOCK",
    91: "IN A PATTERN OF BIGEMINY", 93: "SUPRAVENTRICULAR TACHYCARDIA", 98: "VENTRICULAR TACHYCARDIA",
    142: "WITH SINUS PAUSE",
}
# Window rule fixed before any study data: ectopic beats and pauses can sit in one window only -> max over
# windows; sustained rhythms (every other label) -> mean. Per-window probabilities are always kept as well.
MAX_RULE_LABELS = frozenset({9, 16, 19, 91, 142})


def combine_rule(index: int) -> str:
    return "max" if index in MAX_RULE_LABELS else "mean"


def load_tasks(path: str | Path = TASKS_PATH) -> list[str]:
    names = [t.strip() for t in Path(path).read_text(encoding="utf-8").splitlines() if t.strip()]
    if len(names) != N_CLASSES:
        raise ValueError(f"{path}: expected {N_CLASSES} labels, found {len(names)}")
    return names



def filter_bandpass(signal: np.ndarray, fs: float) -> np.ndarray:
    """util.filter_bandpass from ECGFounder (MIT), same calls; `signal` is (channels, time)."""
    signal = np.atleast_2d(np.asarray(signal, dtype=np.float64))
    b, a = iirnotch(50, 30, fs)
    filtered_signal = np.zeros_like(signal)
    for c in range(signal.shape[0]):
        filtered_signal[c] = filtfilt(b, a, signal[c])
    b, a = butter(N=4, Wn=[0.67, 40], btype='bandpass', fs=fs)
    for c in range(signal.shape[0]):
        filtered_signal[c] = filtfilt(b, a, filtered_signal[c])
    baseline = np.zeros_like(filtered_signal)
    kernel_size = int(0.4 * fs) + 1
    if kernel_size % 2 == 0:
        kernel_size += 1
    for c in range(filtered_signal.shape[0]):
        baseline[c] = medfilt(filtered_signal[c], kernel_size=kernel_size)
    return filtered_signal - baseline


def z_score(w: np.ndarray) -> np.ndarray:
    """Per-window (x - mean) / (std + 1e-8) over the last axis (dataset.py z_score_normalization)."""
    w = np.asarray(w, dtype=np.float64)
    return (w - w.mean(axis=-1, keepdims=True)) / (w.std(axis=-1, keepdims=True) + ZSCORE_EPS)


def resample_to_model(x: np.ndarray, fs: float) -> tuple[np.ndarray, tuple[int, int]]:
    """Polyphase resampling to 500 Hz; 300 Hz uses resample_poly(x, 5, 3). Returns (y, (up, down))."""
    ratio = Fraction(FS_MODEL / float(fs)).limit_denominator(1000)
    up, down = ratio.numerator, ratio.denominator
    if up == down:
        return np.asarray(x, dtype=np.float64).copy(), (1, 1)
    return resample_poly(np.asarray(x, dtype=np.float64), up, down), (up, down)


def polarity_check(x500: np.ndarray, fs: float = FS_MODEL) -> tuple[bool, float, int]:
    """(flip, negative fraction, beats): is the dominant QRS deflection negative in most beats?

    Beats are peaks of |band-passed signal| above half its 99th percentile, at least 0.3 s apart; the sign of
    the signal at each peak is its dominant deflection. Flip only when at least 70 percent of at least 3 beats
    are negative (an inverted lead I, for example reversed fingers on the Kardia). Recorded in the output.
    """
    if x500.size < int(2 * fs):
        return False, float("nan"), 0
    y = filter_bandpass(x500, fs)[0]
    a = np.abs(y)
    top = float(np.percentile(a, 99))
    if not np.isfinite(top) or top <= 0:
        return False, float("nan"), 0
    peaks, _ = find_peaks(a, height=0.5 * top, distance=int(0.3 * fs))
    if peaks.size < POLARITY_MIN_BEATS:
        return False, float("nan"), int(peaks.size)
    neg = float(np.mean(y[peaks] < 0))
    return neg >= POLARITY_NEG_FRAC, neg, int(peaks.size)


@dataclass
class Windows:
    """Model input cut from one strip, with what was done to it."""
    x: np.ndarray                    # (n, 1, 5000) float32
    starts_s: list[float]            # window start times in the strip, s
    filtered: bool
    step_s: float
    fs_in: float
    resample_up_down: tuple[int, int]
    duration_s: float
    polarity_flipped: bool
    polarity_negative_fraction: float
    polarity_beats: int
    notes: list[str] = field(default_factory=list)


def preprocess(x, fs: float, filtered: bool = True, step_s: float = WIN_S, polarity: str = "auto") -> Windows:
    """Single-lead strip in mV at `fs` -> 10 s windows ready for Net1D.

    NaN -> 0, resample to 500 Hz, polarity check on the whole strip (`polarity="auto"` flips an inverted
    strip, "keep" never flips), windows of 5000 samples every `step_s` seconds (10 s: non-overlapping, 5 s:
    half overlap; a tail shorter than 10 s is dropped), each window filtered on its own as in training when
    `filtered`, then z-scored.
    """
    x = np.nan_to_num(np.asarray(x, dtype=np.float64).ravel(), nan=0.0)
    y, ud = resample_to_model(x, fs)
    flip, neg, beats = polarity_check(y) if polarity == "auto" else (False, float("nan"), 0)
    if flip:
        y = -y
    step = round(step_s * FS_MODEL)
    if step <= 0:
        raise ValueError("step_s must be positive")
    starts = list(range(0, y.size - WIN + 1, step)) if y.size >= WIN else []
    notes = []
    if not starts:
        notes.append(f"strip shorter than {WIN_S:.0f} s ({y.size / FS_MODEL:.1f} s): no window")
        w = np.zeros((0, WIN))
    else:
        w = np.stack([y[s:s + WIN] for s in starts])
        if filtered:
            w = filter_bandpass(w, FS_MODEL)
        w = z_score(w)
    return Windows(x=w[:, None, :].astype(np.float32), starts_s=[s / FS_MODEL for s in starts], filtered=filtered,
                   step_s=float(step_s), fs_in=float(fs), resample_up_down=ud, duration_s=x.size / float(fs),
                   polarity_flipped=bool(flip), polarity_negative_fraction=neg, polarity_beats=beats, notes=notes)


def combine_windows(window_probs: np.ndarray) -> np.ndarray:
    """(n_windows, 150) -> (150,): max over windows for MAX_RULE_LABELS, mean for every other label."""
    p = np.asarray(window_probs, dtype=np.float64)
    if p.ndim != 2 or p.shape[0] == 0:
        return np.full(p.shape[-1] if p.ndim == 2 else N_CLASSES, np.nan)
    out = p.mean(axis=0)
    idx = sorted(MAX_RULE_LABELS)
    out[idx] = p[:, idx].max(axis=0)
    return out


