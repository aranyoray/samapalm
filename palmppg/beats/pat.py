"""Beat-level ECG-to-pulse analyses: pulse arrival time and IBI comparison (protocol section 6.6).

Every function here runs only when the clip's timeline carries sync grade "fine" (section 4.4) and raises
`SyncGradeError` otherwise; every output is `requires_ecg = True` and never enters a product-candidate
model (CONTRACTS section 0.8). Inputs are plain arrays of times in seconds on the reference clock: R-peak
times (ecg/rpeaks.parquet `t_ref_s` after the ECG clock map is applied) and pulse feet (beats.parquet
`foot_t`). PAT = foot time - R time in ms for the first foot inside cfg `sync.pat_window_ms` after each R.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

REQUIRED_GRADE = "fine"
MS_PER_S = 1000.0
# "Ectopic" interval definition (part of the section 6.6 feature definition): an IBI that deviates by more
# than this fraction from the local median of its neighbours, computed over +/- LOCAL_HALF_WINDOW intervals.
ECTOPIC_REL_DEV = 0.20
LOCAL_HALF_WINDOW = 5

PAIR_COLUMNS = ("r_t", "foot_t", "pat_ms", "paired")
SUMMARY_KEYS = ("pairing_rate", "pat_mean_ms", "pat_sd_ms", "pat_median_ms", "n_pairs", "n_rpeaks")
COMPARE_KEYS = ("n_compared", "ibi_diff_mean_ms", "ibi_diff_sd_ms", "ibi_diff_mad_ms", "ibi_corr", "n_ectopic_ecg",
                "n_ectopic_captured", "ectopic_capture_fraction")


class SyncGradeError(RuntimeError):
    """Raised when a beat-level ECG analysis is requested on a clip whose sync grade is not 'fine'."""


def sync_grade_of(timeline) -> str:
    """Sync grade of a Timeline, a Timeline dict, or a plain grade string; "none" when unknown."""
    if timeline is None:
        return "none"
    if isinstance(timeline, str):
        return timeline
    if isinstance(timeline, dict):
        return str(timeline.get("sync_grade", "none"))
    return str(getattr(timeline, "sync_grade", "none"))


def pat_allowed(timeline) -> tuple[bool, str]:
    """(allowed, reason) for section 6.6 analyses: allowed only with sync grade "fine"."""
    g = sync_grade_of(timeline)
    if g == REQUIRED_GRADE:
        return True, f"sync grade is '{g}'"
    return False, f"beat-level ECG-to-pulse analyses need sync grade '{REQUIRED_GRADE}' (section 6.6); clip grade is '{g}'"


def require_fine(timeline, what: str = "PAT") -> None:
    """Raise `SyncGradeError` with a clear message unless the timeline's sync grade is "fine"."""
    ok, reason = pat_allowed(timeline)
    if not ok:
        raise SyncGradeError(f"{what} refused: {reason}")


def pair_r_to_foot(rpeak_t_ref_s, foot_t_ref_s, window_ms: tuple[float, float], timeline) -> pd.DataFrame:
    """Pair each ECG R-peak with the first pulse foot `window_ms[0]`..`window_ms[1]` ms after it (cfg
    `sync.pat_window_ms`); a foot is used at most once, in time order. Grade "fine" only.

    Returns one row per R-peak: r_t, foot_t (NaN when unpaired), pat_ms, paired (bool). Section 6.6.
    """
    require_fine(timeline, "PAT pairing")
    r = np.sort(np.asarray(rpeak_t_ref_s, dtype=float))
    r = r[np.isfinite(r)]
    f = np.sort(np.asarray(foot_t_ref_s, dtype=float))
    f = f[np.isfinite(f)]
    lo, hi = float(window_ms[0]) / MS_PER_S, float(window_ms[1]) / MS_PER_S
    rows = []
    j = 0
    for t_r in r:
        while j < f.size and f[j] < t_r + lo:
            j += 1
        if j < f.size and f[j] <= t_r + hi:
            rows.append({"r_t": float(t_r), "foot_t": float(f[j]), "pat_ms": float((f[j] - t_r) * MS_PER_S), "paired": True})
            j += 1
        else:
            rows.append({"r_t": float(t_r), "foot_t": float("nan"), "pat_ms": float("nan"), "paired": False})
    df = pd.DataFrame(rows, columns=list(PAIR_COLUMNS))
    df["paired"] = df["paired"].astype(bool)
    return df


def pat_summary(pairs: pd.DataFrame, timeline) -> dict:
    """{pairing_rate, pat_mean_ms, pat_sd_ms, pat_median_ms, n_pairs, n_rpeaks} of a pairing table. Grade "fine" only."""
    require_fine(timeline, "PAT summary")
    n = int(len(pairs))
    paired = pairs["paired"].to_numpy(dtype=bool) if n else np.zeros(0, dtype=bool)
    pat = pairs["pat_ms"].to_numpy(dtype=float)[paired] if n else np.zeros(0)
    nan = float("nan")
    return {"pairing_rate": float(paired.mean()) if n else nan,
            "pat_mean_ms": float(np.mean(pat)) if pat.size else nan,
            "pat_sd_ms": float(np.std(pat, ddof=1)) if pat.size >= 2 else nan,
            "pat_median_ms": float(np.median(pat)) if pat.size else nan,
            "n_pairs": int(pat.size), "n_rpeaks": n}


def local_median_deviation(ibi, half_window: int = LOCAL_HALF_WINDOW) -> np.ndarray:
    """Signed relative deviation (ibi / local median - 1) of each interval from the median of up to
    `half_window` intervals on each side (itself excluded); NaN without neighbours."""
    v = np.asarray(ibi, dtype=float)
    out = np.full(v.size, np.nan)
    for k in range(v.size):
        lo, hi = max(k - half_window, 0), min(k + half_window + 1, v.size)
        ref = np.concatenate([v[lo:k], v[k + 1:hi]])
        ref = ref[np.isfinite(ref)]
        if ref.size and np.isfinite(v[k]):
            med = float(np.median(ref))
            if med > 0:
                out[k] = v[k] / med - 1.0
    return out


def compare_ibis(rpeak_t_ref_s, foot_t_ref_s, pairs: pd.DataFrame, timeline, rel_dev: float = ECTOPIC_REL_DEV) -> dict:
    """Beat-by-beat ECG-versus-pulse IBI comparison and the ectopic capture fraction (section 6.6).

    ECG IBIs end at each R-peak, pulse IBIs at each foot. An R-peak's intervals are compared when it and
    the previous R-peak are paired (`pairs` from `pair_r_to_foot`) with consecutive feet. An ECG interval
    is "ectopic" when it deviates by more than `rel_dev` from the local median of its neighbours
    (`local_median_deviation`); it is "captured" when its R-peak is paired and the pulse interval ending
    at the paired foot deviates by more than `rel_dev` in the same direction. Returns {"table": DataFrame
    (r_t, ecg_ibi_s, foot_t, pulse_ibi_s, diff_ms, ecg_ectopic, pulse_deviates, captured), n_compared,
    ibi_diff_mean_ms, ibi_diff_sd_ms, ibi_diff_mad_ms (median |diff|), ibi_corr, n_ectopic_ecg,
    n_ectopic_captured, ectopic_capture_fraction}. Grade "fine" only.
    """
    require_fine(timeline, "ECG-versus-pulse IBI comparison")
    r = np.sort(np.asarray(rpeak_t_ref_s, dtype=float))
    r = r[np.isfinite(r)]
    f = np.sort(np.asarray(foot_t_ref_s, dtype=float))
    f = f[np.isfinite(f)]
    ecg_ibi = np.concatenate([[np.nan], np.diff(r)]) if r.size else np.zeros(0)
    pulse_ibi = np.concatenate([[np.nan], np.diff(f)]) if f.size else np.zeros(0)
    ecg_dev = local_median_deviation(ecg_ibi)
    pulse_dev = local_median_deviation(pulse_ibi)
    foot_of = np.full(r.size, -1, dtype=int)
    if len(pairs):
        p_r = pairs["r_t"].to_numpy(dtype=float)
        p_f = pairs["foot_t"].to_numpy(dtype=float)
        for t_r, t_f in zip(p_r, p_f, strict=True):
            if not np.isfinite(t_f):
                continue
            j = int(np.argmin(np.abs(r - t_r))) if r.size else -1
            k = int(np.argmin(np.abs(f - t_f))) if f.size else -1
            if j >= 0 and k >= 0 and abs(r[j] - t_r) < 1e-6 and abs(f[k] - t_f) < 1e-6:
                foot_of[j] = k
    rows = []
    for j in range(r.size):
        k = foot_of[j]
        compared = j >= 1 and k >= 1 and foot_of[j - 1] == k - 1
        ectopic = bool(np.isfinite(ecg_dev[j]) and abs(ecg_dev[j]) > rel_dev)
        deviates = bool(k >= 1 and np.isfinite(pulse_dev[k]) and abs(pulse_dev[k]) > rel_dev)
        captured = bool(ectopic and deviates and np.sign(pulse_dev[k]) == np.sign(ecg_dev[j]))
        rows.append({"r_t": float(r[j]), "ecg_ibi_s": float(ecg_ibi[j]), "foot_t": float(f[k]) if k >= 0 else float("nan"),
                     "pulse_ibi_s": float(pulse_ibi[k]) if k >= 1 else float("nan"),
                     "diff_ms": float((pulse_ibi[k] - ecg_ibi[j]) * MS_PER_S) if compared else float("nan"),
                     "ecg_ectopic": ectopic, "pulse_deviates": deviates, "captured": captured})
    table = pd.DataFrame(rows, columns=["r_t", "ecg_ibi_s", "foot_t", "pulse_ibi_s", "diff_ms", "ecg_ectopic", "pulse_deviates", "captured"])
    nan = float("nan")
    out: dict = {"table": table}
    d = table["diff_ms"].to_numpy(dtype=float) if len(table) else np.zeros(0)
    ok = np.isfinite(d)
    out["n_compared"] = int(ok.sum())
    out["ibi_diff_mean_ms"] = float(np.mean(d[ok])) if ok.any() else nan
    out["ibi_diff_sd_ms"] = float(np.std(d[ok], ddof=1)) if ok.sum() >= 2 else nan
    out["ibi_diff_mad_ms"] = float(np.median(np.abs(d[ok]))) if ok.any() else nan
    if ok.sum() >= 3:
        e = table["ecg_ibi_s"].to_numpy(dtype=float)[ok]
        p = table["pulse_ibi_s"].to_numpy(dtype=float)[ok]
        out["ibi_corr"] = float(np.corrcoef(e, p)[0, 1]) if np.std(e) > 0 and np.std(p) > 0 else nan
    else:
        out["ibi_corr"] = nan
    n_ect = int(table["ecg_ectopic"].sum()) if len(table) else 0
    n_cap = int(table["captured"].sum()) if len(table) else 0
    out["n_ectopic_ecg"], out["n_ectopic_captured"] = n_ect, n_cap
    out["ectopic_capture_fraction"] = (n_cap / n_ect) if n_ect else nan
    return out
