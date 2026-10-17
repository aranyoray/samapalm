"""R-peak detection with a two-detector agreement check, and the IBI series (protocol section 6.4).

NeuroKit2 `ecg_peaks` is run once per method in `ecg.detectors` (the first is the primary). Detectors
place their fiducial on different derived signals (Pan-Tompkins and Hamilton mark the integrated or
band-passed signal 30 to 60 ms after the R apex), so every detector's peaks are first snapped to the apex
of the cleaned ECG within `SNAP_MS`; then every primary peak is matched to each other detector within
`ecg.agreement_ms` (one-to-one, nearest first) and carries an `agree` flag. The primary peaks are what
every downstream module uses; the agreement fraction is a per-clip quality number. IBIs are bounded by
`beats.ibi_bounds_s` (the same physiological bounds as the palm beats so ECG and pulse IBIs are comparable).
"""
from __future__ import annotations

import numpy as np

from palmppg.core.config import Config

SNAP_MS = 80.0   # apex search half-window; far below half the shortest physiological IBI (330 ms)


def _cfg(cfg: Config | None) -> Config:
    if cfg is None:
        from palmppg.core.config import load_pipeline_config

        cfg = load_pipeline_config()
    return cfg


def snap_to_apex(x, idx, fs: float, window_ms: float = SNAP_MS) -> np.ndarray:
    """Move each index to the maximum of `x` within +/- `window_ms` (the R apex; positive-R convention).

    Returns sorted unique int64 indices; two detections that snap to the same apex collapse into one.
    """
    x = np.asarray(x, dtype=np.float64)
    idx = np.asarray(idx, dtype=np.int64)
    if idx.size == 0 or x.size == 0:
        return np.zeros(0, dtype=np.int64)
    w = max(1, round(float(window_ms) * 1e-3 * float(fs)))
    out = np.empty(idx.size, dtype=np.int64)
    for k, i in enumerate(idx):
        lo, hi = max(0, i - w), min(x.size, i + w + 1)
        seg = x[lo:hi]
        out[k] = lo + int(np.nanargmax(seg)) if np.isfinite(seg).any() else i
    return np.unique(out)


def run_detector(x_clean, fs: float, method: str, snap_ms: float | None = SNAP_MS) -> dict:
    """One NeuroKit2 detector -> {idx (int64 array, sorted, unique, snapped to the R apex), n_peaks,
    n_raw (before snapping), error (None | str)}."""
    import neurokit2 as nk

    x = np.asarray(x_clean, dtype=np.float64)
    x = np.where(np.isfinite(x), x, 0.0)
    try:
        _, info = nk.ecg_peaks(x, sampling_rate=round(fs), method=method, correct_artifacts=False)
        idx = np.unique(np.asarray(info.get("ECG_R_Peaks", []), dtype=np.int64))
        idx = idx[(idx >= 0) & (idx < x.size)]
    except Exception as exc:  # noqa: BLE001 - any third-party detector failure is recorded, never raised
        return {"idx": np.zeros(0, dtype=np.int64), "n_peaks": 0, "n_raw": 0, "error": f"{type(exc).__name__}: {exc}"}
    n_raw = int(idx.size)
    if snap_ms:
        idx = snap_to_apex(x, idx, fs, snap_ms)
    return {"idx": idx, "n_peaks": int(idx.size), "n_raw": n_raw, "error": None}


def match_peaks(primary: np.ndarray, other: np.ndarray, tol: float) -> tuple[np.ndarray, np.ndarray]:
    """One-to-one nearest matching within `tol` (same units as the inputs).

    Returns (matched_primary: bool[len(primary)], matched_other: bool[len(other)]). Pairs are taken in
    order of increasing distance so a single `other` peak can only be claimed by its closest primary.
    """
    p = np.asarray(primary, dtype=np.float64)
    o = np.asarray(other, dtype=np.float64)
    mp = np.zeros(p.size, dtype=bool)
    mo = np.zeros(o.size, dtype=bool)
    if p.size == 0 or o.size == 0:
        return mp, mo
    pos = np.searchsorted(o, p)
    cand: list[tuple[float, int, int]] = []
    for i, k in enumerate(pos):
        for j in (k - 1, k):
            if 0 <= j < o.size:
                d = abs(p[i] - o[j])
                if d <= tol:
                    cand.append((d, i, j))
    for d, i, j in sorted(cand):
        if not mp[i] and not mo[j]:
            mp[i] = True
            mo[j] = True
    return mp, mo


def detect_rpeaks(x_clean, fs: float, detectors: list[str] | None = None, agreement_ms: float | None = None,
                  cfg: Config | None = None, snap_ms: float | None = SNAP_MS) -> dict:
    """R-peaks of a cleaned ECG with the detector agreement check (protocol 6.4; CONTRACTS 4 `rpeaks.parquet`).

    Returns {idx (int64 samples of the primary detector, at the R apex), t_s (idx / fs), agree (bool per
    peak: matched by every other detector within `agreement_ms`), agree_count, agree_frac (fraction of
    primary peaks with agree=True; NaN when no second detector ran), per_detector {name: {idx, n_peaks,
    n_raw, matched_frac, error}}, primary, detectors_run, agreement_ms, fs, n_peaks}. Defaults come from
    `ecg.detectors` and `ecg.agreement_ms`; `snap_ms=None` keeps each detector's own fiducial.
    """
    if detectors is None or agreement_ms is None:
        c = _cfg(cfg)
        detectors = list(c.get("ecg.detectors")) if detectors is None else list(detectors)
        agreement_ms = float(c.get("ecg.agreement_ms")) if agreement_ms is None else float(agreement_ms)
    if not detectors:
        raise ValueError("at least one detector is required")
    tol = float(agreement_ms) * 1e-3 * float(fs)
    per: dict[str, dict] = {m: run_detector(x_clean, fs, m, snap_ms) for m in detectors}
    primary = detectors[0]
    idx = per[primary]["idx"]
    per[primary]["matched_frac"] = 1.0 if idx.size else float("nan")
    agree_count = np.zeros(idx.size, dtype=np.int64)
    n_ran = 0
    for m in detectors[1:]:
        res = per[m]
        if res["error"] is not None:
            res["matched_frac"] = float("nan")
            continue
        n_ran += 1
        mp, mo = match_peaks(idx, res["idx"], tol)
        agree_count += mp.astype(np.int64)
        res["matched_frac"] = float(mo.mean()) if mo.size else float("nan")
    agree = agree_count >= n_ran if n_ran else np.zeros(idx.size, dtype=bool)
    agree_frac = float(agree.mean()) if (n_ran and idx.size) else float("nan")
    return {
        "idx": idx, "t_s": idx.astype(np.float64) / float(fs), "agree": agree, "agree_count": agree_count,
        "agree_frac": agree_frac, "per_detector": per, "primary": primary, "detectors_run": list(detectors),
        "n_secondary_ran": int(n_ran), "agreement_ms": float(agreement_ms), "fs": float(fs), "n_peaks": int(idx.size),
    }


def ibi_series(t_peaks, bounds_s: tuple[float, float] | None = None, cfg: Config | None = None) -> dict:
    """Inter-beat intervals from R-peak times (seconds) with physiological bounds (`beats.ibi_bounds_s`).

    Returns {t_s (time of the second peak of each interval), ibi_s, valid (lo <= ibi <= hi), n, n_rejected,
    bounds_s, t_valid_s, ibi_valid_s}. Intervals outside the bounds are kept in `ibi_s` with valid=False so
    callers can see where beats were missed or doubled.
    """
    if bounds_s is None:
        bounds_s = tuple(_cfg(cfg).get("beats.ibi_bounds_s"))
    lo, hi = float(bounds_s[0]), float(bounds_s[1])
    t = np.sort(np.asarray(t_peaks, dtype=np.float64))
    if t.size < 2:
        empty = np.zeros(0)
        return {"t_s": empty, "ibi_s": empty, "valid": np.zeros(0, dtype=bool), "n": 0, "n_rejected": 0,
                "bounds_s": (lo, hi), "t_valid_s": empty, "ibi_valid_s": empty}
    ibi = np.diff(t)
    valid = (ibi >= lo) & (ibi <= hi)
    return {"t_s": t[1:], "ibi_s": ibi, "valid": valid, "n": int(ibi.size), "n_rejected": int((~valid).sum()),
            "bounds_s": (lo, hi), "t_valid_s": t[1:][valid], "ibi_valid_s": ibi[valid]}
