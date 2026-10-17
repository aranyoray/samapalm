"""Per-clip, per-camera quality control: saturation, flicker, lighting drift, the qc.json builder and qc_table upsert.

Serves protocol section 6.1 (exposure: saturated-pixel fraction in the skin mask, flag above 0.5 percent;
flicker: FFT of mean frame intensity, flag peaks at 50 or 100 Hz and at the aliased 10 Hz; lighting drift:
linear trend across the clip, flag above 2 percent; `qc_table.parquet` one row per clip per camera) and
CONTRACTS section 4.1 (qc.json keys and the `valid_clip` rule). Every threshold is read from the Config.
"""
from __future__ import annotations

import json
import math
import os
from collections.abc import Mapping, Sequence
from pathlib import Path

import numpy as np
import pandas as pd

from palmppg.core.config import Config
from palmppg.core.timeline import detect_drops
from palmppg.core.tracks import CAMERAS, REGISTRY, feature_prefix

QC_KEYS: tuple[str, ...] = (
    "camera", "study_id", "clip_id", "n_frames", "duration_s", "fs_median", "drop_pct", "drop_flag", "saturation_frac",
    "saturation_flag", "flicker_peaks_hz", "flicker_flag", "lighting_drift_pct", "lighting_drift_flag",
    "vignetting_residual_pct", "vignetting_flag", "hand_detected", "hand_is_left", "hand_palmar", "landmark_source",
    "landmark_jitter_px", "motion_flag", "eis_warp_px", "eis_flag", "sync_grade", "sqi_best", "sqi_flag", "valid_clip",
    "reasons",
)
VALID_CLIP_FLAGS: tuple[str, ...] = ("hand_detected", "drop_flag", "saturation_flag", "flicker_flag", "sqi_flag")
HAND_KEYS: tuple[str, ...] = ("hand_detected", "hand_is_left", "hand_palmar", "landmark_source", "landmark_jitter_px", "motion_flag")

# Columns of the QC row that are registered as features (group "qc"); flags are booleans, numbers floats.
_QC_FEATURE_COLUMNS: dict[str, tuple[str, str]] = {
    "n_frames": ("frames", "number of frames with a timestamp"),
    "duration_s": ("s", "clip duration on the reference clock"),
    "fs_median": ("Hz", "median frame rate from true frame times"),
    "drop_pct": ("%", "dropped frames relative to expected"),
    "drop_flag": ("bool", "drop_pct above qc.drop_pct_max"),
    "saturation_frac": ("fraction", "saturated pixel fraction in the skin mask"),
    "saturation_flag": ("bool", "saturation_frac above qc.saturation_frac_max"),
    "flicker_flag": ("bool", "mains flicker peak found (50/100 Hz or aliased 10 Hz)"),
    "lighting_drift_pct": ("%", "linear trend of mean intensity over the clip relative to its mean"),
    "lighting_drift_flag": ("bool", "abs(lighting_drift_pct) above qc.lighting_drift_pct_max"),
    "vignetting_residual_pct": ("%", "residual non-uniformity of the corrected flat over the aperture"),
    "vignetting_flag": ("bool", "vignetting_residual_pct above qc.vignetting_residual_pct_max"),
    "landmark_jitter_px": ("px", "hand landmark jitter, motion proxy"),
    "motion_flag": ("bool", "motion proxy above threshold"),
    "eis_warp_px": ("px", "residual EIS warp (90th percentile of sampled pair warps)"),
    "eis_flag": ("bool", "eis_warp_px above qc.eis_warp_px_max"),
    "sqi_best": ("0..1", "best signal quality index of the clip"),
    "sqi_flag": ("bool", "sqi_best below the pilot-frozen threshold"),
    "valid_clip": ("bool", "hand detected and no drop/saturation/flicker flag and sqi above threshold"),
}


# --------------------------------------------------------------------------- registry
def register_features() -> list[str]:
    """Register every QC column as `qc__<camera>__<name>` for the three cameras (idempotent; CONTRACTS section 5).

    Pi-camera QC numbers come from the raw Bayer stream (`requires_raw=True`); phone and pi_proxy ones do not.
    """
    names = []
    for cam in CAMERAS:
        for col, (units, desc) in _QC_FEATURE_COLUMNS.items():
            name = feature_prefix("qc", cam, None, None, col)
            REGISTRY.add(name, group="qc", camera=cam, requires_raw=(cam == "pi"), requires_ecg=False,
                         units=units, description=desc)
            names.append(name)
    return names


# --------------------------------------------------------------------------- saturation
def saturation_fraction(plane_or_rgb: np.ndarray, mask: np.ndarray | None = None, white_level: float = 1023) -> float:
    """Fraction of pixels (inside `mask` when given) at or above `white_level` (section 6.1 exposure check).

    For an (H, W, 3) RGB frame a pixel counts as saturated when any channel is saturated; for a single plane
    it is the plane value. `white_level` is cfg `pi.white_level` (1023) for raw planes or 255 for 8-bit video.
    NaN when the mask is empty.
    """
    a = np.asarray(plane_or_rgb)
    if a.ndim == 3:
        sat = np.any(a >= white_level, axis=-1)
    else:
        sat = a >= white_level
    if mask is not None:
        m = np.asarray(mask, dtype=bool)
        if m.shape != sat.shape:
            raise ValueError(f"mask shape {m.shape} does not match frame {sat.shape}")
        sat = sat[m]
    return float(sat.mean()) if sat.size else float("nan")


def saturation_fraction_planes(planes: Mapping[str, np.ndarray], mask: np.ndarray | None = None, white_level: float = 1023) -> float:
    """Saturation over the union of the four Bayer planes (any plane saturated at a half-resolution site). Section 6.1 exposure check on the Pi path."""
    sat = None
    for p in planes.values():
        s = np.asarray(p) >= white_level
        sat = s if sat is None else (sat | s)
    if sat is None:
        return float("nan")
    if mask is not None:
        sat = sat[np.asarray(mask, dtype=bool)]
    return float(sat.mean()) if sat.size else float("nan")


# --------------------------------------------------------------------------- flicker
def _fill_nan(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=float).copy()
    ok = np.isfinite(x)
    if ok.all():
        return x
    if ok.sum() == 0:
        return np.zeros_like(x)
    idx = np.arange(x.size)
    x[~ok] = np.interp(idx[~ok], idx[ok], x[ok])
    return x


def flicker_peaks(mean_intensity: Sequence[float] | np.ndarray, fs: float, targets: Sequence[float] = (50.0, 100.0, 10.0),
                  tol: float = 0.3, snr_db_min: float = 6.0, segment_s: float = 4.0, neighbourhood_hz: float = 1.5) -> dict:
    """Mains-flicker test on the mean frame intensity series (section 6.1): Welch PSD, peak SNR per target frequency.

    `targets` are cfg `qc.flicker_hz` (50, 100 and the aliased 10 Hz for Indian mains at 30 fps); a target is
    tested only when it lies below the Nyquist frequency fs/2, so at 30 fps only the 10 Hz alias is observable
    and 50/100 Hz are tested on faster bench captures. For each tested target the peak power within
    +/- `tol` Hz (cfg `qc.flicker_tolerance_hz`) is compared with the median power of the surrounding
    +/- `neighbourhood_hz` band (the +/- tol core excluded); SNR in dB at or above `snr_db_min`
    (cfg `qc.flicker_snr_db_min`) is a peak. The series is NaN-bridged, linearly detrended and normalised by
    its mean, so `modulation_pct` is the fitted sinusoid amplitude in percent of the mean intensity.
    Returns {peaks_hz, flag, tested_hz, skipped_hz, snr_db: {hz: dB}, peak_hz: {hz: f}, modulation_pct: {hz: %},
    nyquist_hz, n_samples, resolution_hz}.
    """
    from scipy.signal import detrend, welch

    x = _fill_nan(np.asarray(mean_intensity, dtype=float).reshape(-1))
    fs = float(fs)
    out: dict = {"peaks_hz": [], "flag": False, "tested_hz": [], "skipped_hz": [], "snr_db": {}, "peak_hz": {},
                 "modulation_pct": {}, "nyquist_hz": fs / 2.0, "n_samples": int(x.size), "resolution_hz": float("nan")}
    if x.size < 8 or fs <= 0:
        out["skipped_hz"] = [float(t) for t in targets]
        return out
    mean = float(np.mean(x))
    if not np.isfinite(mean) or mean == 0:
        out["skipped_hz"] = [float(t) for t in targets]
        return out
    rel = detrend(x / mean, type="linear")
    nperseg = int(min(x.size, max(16, round(segment_s * fs))))
    f, p = welch(rel, fs=fs, window="hann", nperseg=nperseg, noverlap=nperseg // 2, detrend=False, scaling="density")
    df = float(f[1] - f[0]) if f.size > 1 else float("nan")
    out["resolution_hz"] = df
    nyq = fs / 2.0
    for t in targets:
        t = float(t)
        if t >= nyq or t <= 0:
            out["skipped_hz"].append(t)
            continue
        out["tested_hz"].append(t)
        core = (f >= t - tol) & (f <= t + tol)
        ring = (f >= t - neighbourhood_hz) & (f <= t + neighbourhood_hz) & ~core & (f > 0)
        if core.sum() == 0 or ring.sum() < 2:
            out["snr_db"][str(t)] = float("nan")
            continue
        peak_i = int(np.argmax(np.where(core, p, -np.inf)))
        peak = float(p[peak_i])
        noise = float(np.median(p[ring]))
        snr = 10.0 * math.log10(peak / noise) if noise > 0 and peak > 0 else float("inf") if peak > 0 else float("-inf")
        amp = math.sqrt(max(2.0 * float(np.sum(p[core])) * df, 0.0))
        out["snr_db"][str(t)] = float(snr)
        out["peak_hz"][str(t)] = float(f[peak_i])
        out["modulation_pct"][str(t)] = float(100.0 * amp)
        if snr >= snr_db_min:
            out["peaks_hz"].append(t)
    out["flag"] = bool(out["peaks_hz"])
    return out


# --------------------------------------------------------------------------- lighting drift
def lighting_drift_pct(mean_intensity: Sequence[float] | np.ndarray, t: Sequence[float] | np.ndarray) -> float:
    """Signed linear trend of mean intensity across the clip in percent of its mean (section 6.1, flag above 2 %).

    Least-squares line through (t, intensity); drift = slope x (t_last - t_first) / mean x 100. NaN samples are
    ignored. NaN when fewer than two finite samples or zero mean.
    """
    x = np.asarray(t, dtype=float).reshape(-1)
    y = np.asarray(mean_intensity, dtype=float).reshape(-1)
    if x.shape != y.shape:
        raise ValueError("t and mean_intensity differ in length")
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 2:
        return float("nan")
    x, y = x[ok], y[ok]
    mean = float(np.mean(y))
    if mean == 0 or x[-1] == x[0]:
        return float("nan")
    slope, _ = np.polyfit(x, y, 1)
    return float(100.0 * slope * (x[-1] - x[0]) / mean)


# --------------------------------------------------------------------------- qc.json
def _flag(value, threshold: float | None, above: bool = True) -> bool | None:
    if value is None or threshold is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(v):
        return None
    return bool(v > threshold) if above else bool(v < threshold)


def _opt_float(v) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if np.isfinite(f) else None


def _opt_bool(v) -> bool | None:
    if v is None:
        return None
    if isinstance(v, (float, np.floating)) and np.isnan(v):
        return None
    return bool(v)


def build_qc(camera: str, study_id: str, clip_id: str, frame_times_df: pd.DataFrame, mean_intensity_on_grid,
             saturation_frac: float | None, hand_summary: Mapping | None, vignetting_pct: float | None, eis: Mapping | None,
             sync_grade: str, sqi_best: float | None, cfg: Config, sqi_threshold: float | None) -> dict:
    """Assemble the qc.json dict for one clip and camera exactly per CONTRACTS section 4.1, with `reasons`.

    Inputs: `frame_times_df` (`t_ref_s` column, true frame times) gives n_frames, duration, fs_median and drops
    (cfg `qc.drop_factor`, `qc.drop_pct_max`, nominal fps from cfg `pi.nominal_fps` / `phone.nominal_fps`);
    `mean_intensity_on_grid` is the mean-intensity series on the uniform grid (cfg `grid.fs`) and feeds the
    flicker and lighting-drift tests; `saturation_frac` is compared with cfg `qc.saturation_frac_max`;
    `hand_summary` carries hand_detected, hand_is_left, hand_palmar, landmark_source, landmark_jitter_px,
    motion_flag (None when the landmark stage has not run); `vignetting_pct` with cfg
    `qc.vignetting_residual_pct_max`; `eis` is `detect_eis_warp`'s dict or None; `sqi_best` is compared with
    `sqi_threshold` (frozen config). `valid_clip` = hand_detected and not drop_flag and not saturation_flag and
    not flicker_flag and sqi_best >= threshold; `reasons` lists the flag names that made it False.
    """
    if camera not in CAMERAS:
        raise ValueError(f"unknown camera {camera!r}; expected one of {CAMERAS}")
    nominal_fs = float(cfg.get("phone.nominal_fps") if camera == "phone" else cfg.get("pi.nominal_fps"))
    t = np.asarray(frame_times_df["t_ref_s"].to_numpy(dtype=float)) if len(frame_times_df) else np.zeros(0)
    t = t[np.isfinite(t)]
    drops = detect_drops(t, nominal_fs, float(cfg.get("qc.drop_factor")))
    med_period = drops.get("median_period_s")
    fs_median = float(1.0 / med_period) if med_period and np.isfinite(med_period) and med_period > 0 else None
    duration = float(t[-1] - t[0] + (med_period if med_period and np.isfinite(med_period) else 0.0)) if t.size >= 2 else (0.0 if t.size else None)
    drop_pct = float(drops["drop_pct"]) if t.size else None
    drop_flag = _flag(drop_pct, float(cfg.get("qc.drop_pct_max")))

    sat = _opt_float(saturation_frac)
    saturation_flag = _flag(sat, float(cfg.get("qc.saturation_frac_max")))

    grid_fs = float(cfg.get("grid.fs"))
    mi = np.asarray(mean_intensity_on_grid, dtype=float).reshape(-1) if mean_intensity_on_grid is not None else np.zeros(0)
    if mi.size >= 8 and np.isfinite(mi).sum() >= 8:
        fl = flicker_peaks(mi, grid_fs, targets=[float(v) for v in cfg.get("qc.flicker_hz")],
                           tol=float(cfg.get("qc.flicker_tolerance_hz")), snr_db_min=float(cfg.get("qc.flicker_snr_db_min")))
        flicker_hz, flicker_flag = [float(v) for v in fl["peaks_hz"]], bool(fl["flag"])
        drift = lighting_drift_pct(mi, np.arange(mi.size) / grid_fs)
    else:
        flicker_hz, flicker_flag, drift = [], None, None
    drift = _opt_float(drift)
    drift_flag = _flag(None if drift is None else abs(drift), float(cfg.get("qc.lighting_drift_pct_max")))

    vig = _opt_float(vignetting_pct)
    vig_flag = _flag(vig, float(cfg.get("qc.vignetting_residual_pct_max")))

    hs = dict(hand_summary or {})
    hand_detected = _opt_bool(hs.get("hand_detected"))
    eis = dict(eis or {})
    eis_warp = _opt_float(eis.get("warp_px_p90", eis.get("warp_px_median")))
    eis_flag = _opt_bool(eis.get("flag")) if eis else None
    if eis_flag is None and eis_warp is not None:
        eis_flag = _flag(eis_warp, float(cfg.get("qc.eis_warp_px_max")))

    sqi = _opt_float(sqi_best)
    thr = _opt_float(sqi_threshold)
    sqi_flag = None if (sqi is None or thr is None) else bool(sqi < thr)

    reasons: list[str] = []
    if not hand_detected:
        reasons.append("hand_detected")
    if drop_flag is not False:
        reasons.append("drop_flag")
    if saturation_flag is not False:
        reasons.append("saturation_flag")
    if flicker_flag is not False:
        reasons.append("flicker_flag")
    if sqi_flag is not False:
        reasons.append("sqi_flag")
    valid_clip = not reasons

    qc = {
        "camera": camera, "study_id": str(study_id), "clip_id": str(clip_id), "n_frames": int(t.size),
        "duration_s": duration, "fs_median": fs_median, "drop_pct": drop_pct, "drop_flag": drop_flag,
        "saturation_frac": sat, "saturation_flag": saturation_flag, "flicker_peaks_hz": flicker_hz,
        "flicker_flag": flicker_flag, "lighting_drift_pct": drift, "lighting_drift_flag": drift_flag,
        "vignetting_residual_pct": vig, "vignetting_flag": vig_flag,
        "hand_detected": hand_detected, "hand_is_left": _opt_bool(hs.get("hand_is_left")),
        "hand_palmar": _opt_bool(hs.get("hand_palmar")), "landmark_source": hs.get("landmark_source"),
        "landmark_jitter_px": _opt_float(hs.get("landmark_jitter_px")), "motion_flag": _opt_bool(hs.get("motion_flag")),
        "eis_warp_px": eis_warp, "eis_flag": eis_flag, "sync_grade": str(sync_grade) if sync_grade is not None else "none",
        "sqi_best": sqi, "sqi_flag": sqi_flag, "valid_clip": bool(valid_clip), "reasons": reasons,
    }
    assert tuple(qc.keys()) == QC_KEYS
    return qc


def write_qc_json(qc: Mapping, path: str | os.PathLike) -> Path:
    """Write `<camera>/qc.json` (CONTRACTS section 4.1) with NaN rendered as null."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(qc), indent=2, default=_json_default), encoding="utf-8")
    return path


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if np.isnan(o) else float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)


# --------------------------------------------------------------------------- qc_table.parquet
def _qc_table(rows: list[dict]):
    import pyarrow as pa

    cols: dict[str, list] = {k: [] for k in QC_KEYS}
    for r in rows:
        for k in QC_KEYS:
            cols[k].append(r.get(k))
    arrays, names = [], []
    for k in QC_KEYS:
        vals = cols[k]
        if k == "flicker_peaks_hz":
            arr = pa.array([[float(v) for v in (x or [])] for x in vals], type=pa.list_(pa.float64()))
        elif k == "reasons":
            arr = pa.array([[str(v) for v in (x or [])] for x in vals], type=pa.list_(pa.string()))
        elif k in ("camera", "study_id", "clip_id", "landmark_source", "sync_grade"):
            arr = pa.array([None if v is None else str(v) for v in vals], type=pa.string())
        elif k == "n_frames":
            arr = pa.array([None if v is None else int(v) for v in vals], type=pa.int64())
        elif k.endswith("_flag") or k in ("hand_detected", "hand_is_left", "hand_palmar", "valid_clip"):
            arr = pa.array([_opt_bool(v) for v in vals], type=pa.bool_())
        else:
            arr = pa.array([_opt_float(v) for v in vals], type=pa.float64())
        arrays.append(arr)
        names.append(k)
    return pa.table(arrays, names=names)


def append_qc_table(qc_dict: Mapping, parquet_path: str | os.PathLike) -> pd.DataFrame:
    """Upsert one qc row into `qc_table.parquet` keyed by (study_id, clip_id, camera); returns the full table.

    Section 6.1: one row per clip per camera with every flag, the sync grade and `valid_clip`. Re-running ingest
    replaces the row rather than duplicating it.
    """
    import pyarrow as pa
    import pyarrow.parquet as pq

    path = Path(parquet_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    new = _qc_table([dict(qc_dict)])
    if path.exists():
        old = pq.read_table(path)
        key = (str(qc_dict["study_id"]), str(qc_dict["clip_id"]), str(qc_dict["camera"]))
        keep = [i for i in range(old.num_rows)
                if (old.column("study_id")[i].as_py(), old.column("clip_id")[i].as_py(), old.column("camera")[i].as_py()) != key]
        old = old.take(keep) if keep else old.slice(0, 0)
        old = old.select(list(QC_KEYS)) if set(QC_KEYS) <= set(old.column_names) else old
        table = pa.concat_tables([old.cast(new.schema), new]) if old.num_rows else new
    else:
        table = new
    tmp = path.with_suffix(".tmp.parquet")
    pq.write_table(table, tmp)
    os.replace(tmp, path)
    return table.to_pandas()


def read_qc_table(parquet_path: str | os.PathLike) -> pd.DataFrame:
    """Read `qc_table.parquet` (section 6.1, one row per clip per camera)."""
    return pd.read_parquet(parquet_path)
