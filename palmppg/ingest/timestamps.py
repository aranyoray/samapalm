"""True frame times on the reference clock, frame drops, the uniform grid, and the daily clock-sync log.

Serves protocol section 4.1 (clock discipline, drift flag), section 6.1 ("rebuild true frame times from
sensor_ts_ns (Pi) or PTS (phone); detect drops (gap above 1.5 x nominal period); resample to a uniform 30 Hz
grid on the reference clock; log drop percentage; flag above 2 percent") and CONTRACTS section 4
(`frame_times.parquet` schemas). Nothing here aligns by wall clock or by frame index: Pi times come from
`sensor_ts_ns` (CLOCK_BOOTTIME, the reference clock) and phone times from container PTS through a ClockMap.
"""
from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from pathlib import Path

import numpy as np
import pandas as pd

from palmppg.core.timeline import ClockMap, detect_drops, resample_to_grid, uniform_grid

PI_PTS_COLUMNS: tuple[str, ...] = ("frame_idx", "sensor_ts_ns", "wall_ns", "exposure_us", "analogue_gain", "digital_gain", "lux")
PI_FRAME_TIME_COLUMNS: tuple[str, ...] = ("frame_idx", "t_ref_s", "wall_ns", "exposure_us", "analogue_gain", "digital_gain",
                                          "lux", "dropped_before")
PHONE_FRAME_TIME_COLUMNS: tuple[str, ...] = ("frame_idx", "pts_s", "t_ref_s", "dropped_before")
CLOCK_LOG_COLUMNS: tuple[str, ...] = ("date", "time_utc", "device", "offset_ms_vs_phone", "method", "operator")


# --------------------------------------------------------------------------- Pi
def read_pi_pts(csv_path: str | os.PathLike) -> pd.DataFrame:
    """Read `pi/clip1_pts.csv` (CONTRACTS section 3.2) with int64 timestamps; rows sorted by sensor_ts_ns.

    Rows may be missing where frames were dropped; duplicates (same sensor_ts_ns) are removed, keeping the first.
    """
    df = pd.read_csv(csv_path)
    missing = [c for c in PI_PTS_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"{csv_path}: missing columns {missing}; expected {list(PI_PTS_COLUMNS)}")
    df = df.loc[:, list(PI_PTS_COLUMNS)].copy()
    df["frame_idx"] = df["frame_idx"].astype(np.int64)
    df["sensor_ts_ns"] = df["sensor_ts_ns"].astype(np.int64)
    df["wall_ns"] = df["wall_ns"].astype(np.int64)
    for c in ("exposure_us", "analogue_gain", "digital_gain", "lux"):
        df[c] = pd.to_numeric(df[c], errors="coerce").astype(float)
    df = df.sort_values("sensor_ts_ns", kind="stable").drop_duplicates("sensor_ts_ns", keep="first").reset_index(drop=True)
    return df


def dropped_before_from_times(t_s: np.ndarray, nominal_fs: float, drop_factor: float) -> np.ndarray:
    """Per frame: number of frames missing immediately before it (gap > drop_factor x nominal period), int64. Section 6.1 drop rule, CONTRACTS section 4 `dropped_before` column.

    Uses the same rule as `palmppg.core.timeline.detect_drops` so the per-frame and summary counts agree.
    """
    t = np.asarray(t_s, dtype=float)
    out = np.zeros(t.size, dtype=np.int64)
    if t.size < 2:
        return out
    period = 1.0 / float(nominal_fs)
    d = np.diff(t)
    gaps = d > float(drop_factor) * period
    out[1:][gaps] = (np.round(d[gaps] / period) - 1).astype(np.int64)
    return out


def pi_frame_times(df: pd.DataFrame, t0_ref_ns: int | None = None, nominal_fs: float = 30.0,
                   drop_factor: float = 1.5) -> pd.DataFrame:
    """Pi `frame_times.parquet` rows from the pts table: t_ref_s = (sensor_ts_ns - t0_ref_ns) / 1e9 (CONTRACTS section 4).

    `t0_ref_ns` defaults to the first frame's sensor timestamp (D-001: the clip starts near zero). `nominal_fs`
    is cfg `pi.nominal_fps`, `drop_factor` is cfg `qc.drop_factor`. `dropped_before` counts frames missing just
    before each row. Serves section 6.1 timestamps.
    """
    if len(df) == 0:
        return pd.DataFrame({c: pd.Series(dtype=float) for c in PI_FRAME_TIME_COLUMNS})
    ts = df["sensor_ts_ns"].to_numpy(dtype=np.int64)
    t0 = int(ts[0]) if t0_ref_ns is None else int(t0_ref_ns)
    t_ref = (ts - np.int64(t0)) / 1e9
    out = pd.DataFrame({
        "frame_idx": df["frame_idx"].to_numpy(dtype=np.int64),
        "t_ref_s": t_ref.astype(float),
        "wall_ns": df["wall_ns"].to_numpy(dtype=np.int64),
        "exposure_us": df["exposure_us"].to_numpy(dtype=float),
        "analogue_gain": df["analogue_gain"].to_numpy(dtype=float),
        "digital_gain": df["digital_gain"].to_numpy(dtype=float),
        "lux": df["lux"].to_numpy(dtype=float),
        "dropped_before": dropped_before_from_times(t_ref, nominal_fs, drop_factor),
    })
    out.attrs["t0_ref_ns"] = t0
    return out


def drop_summary(t_ref_s: Sequence[float] | np.ndarray, nominal_fs: float, drop_factor: float, drop_pct_max: float) -> dict:
    """`detect_drops` plus the flag (cfg `qc.drop_pct_max`): {n_frames, n_dropped, drop_pct, drop_flag, gaps_idx, ...}. Section 6.1: log drop percentage, flag above the configured maximum."""
    d = detect_drops(np.asarray(t_ref_s, dtype=float), float(nominal_fs), float(drop_factor))
    d["drop_flag"] = bool(d["drop_pct"] > float(drop_pct_max))
    d["fs_median"] = float(1.0 / d["median_period_s"]) if d.get("median_period_s") and np.isfinite(d["median_period_s"]) else float("nan")
    return d


def frame_grid(t_ref_s: Sequence[float] | np.ndarray, grid_fs: float, start_s: float | None = None,
               end_s: float | None = None) -> np.ndarray:
    """Uniform grid (cfg `grid.fs`) spanning the frame times (or [start_s, end_s]) on the reference clock. Section 6.1 uniform grid on the reference clock (D-001)."""
    t = np.asarray(t_ref_s, dtype=float)
    if t.size == 0:
        return np.zeros(0, dtype=float)
    s = float(t[0]) if start_s is None else float(start_s)
    e = float(t[-1]) if end_s is None else float(end_s)
    return uniform_grid(s, e, float(grid_fs))


def resample_series(t_ref_s: Sequence[float] | np.ndarray, values: Sequence[float] | np.ndarray, grid_s: np.ndarray,
                    nominal_fs: float, drop_factor: float) -> np.ndarray:
    """Map a per-frame series (values at the true frame times) onto the grid; NaN inside drop gaps and outside the data.

    Gap width is cfg `qc.drop_factor` x nominal period, the same rule as the drop detector, so a dropped frame
    is a NaN on the grid and stays visible downstream (section 6.1). NaN input samples are left out of the
    interpolation and become gaps when the surrounding interval exceeds the gap width.
    """
    t = np.asarray(t_ref_s, dtype=float)
    v = np.asarray(values, dtype=float)
    if t.shape != v.shape:
        raise ValueError(f"t_ref_s {t.shape} and values {v.shape} differ in shape")
    ok = np.isfinite(t) & np.isfinite(v)
    if ok.sum() == 0:
        return np.full(np.asarray(grid_s).shape, np.nan)
    max_gap = float(drop_factor) / float(nominal_fs)
    return resample_to_grid(t[ok], v[ok], np.asarray(grid_s, dtype=float), max_gap_s=max_gap)


def resample_frame(df: pd.DataFrame, columns: Sequence[str], grid_s: np.ndarray, nominal_fs: float, drop_factor: float,
                   t_col: str = "t_ref_s") -> pd.DataFrame:
    """Resample several per-frame columns onto the grid; returns a DataFrame with `t_ref_s` first. Section 6.1 resampling onto the uniform grid."""
    out = {"t_ref_s": np.asarray(grid_s, dtype=float)}
    for c in columns:
        out[c] = resample_series(df[t_col].to_numpy(), df[c].to_numpy(), grid_s, nominal_fs, drop_factor)
    return pd.DataFrame(out)


# --------------------------------------------------------------------------- phone
def phone_frame_times(pts_s: Sequence[float] | np.ndarray, clockmap: ClockMap | None = None, nominal_fs: float = 30.0,
                      drop_factor: float = 1.5) -> pd.DataFrame:
    """Phone `frame_times.parquet` rows (CONTRACTS section 4): frame_idx, pts_s, t_ref_s, dropped_before.

    `pts_s` are the container presentation timestamps from ffprobe (section 5: resample by PTS, never by frame
    index). `clockmap` maps phone seconds onto the reference clock (from the LED/audio marker in simultaneous
    mode, or the coarse wall-clock/beep map in sequential mode); None means identity (t_ref_s = pts_s), which
    only happens before sync has run. Drops use the PTS gaps against cfg `phone.nominal_fps`.
    """
    pts = np.asarray(pts_s, dtype=float).reshape(-1)
    cm = clockmap if clockmap is not None else ClockMap.identity("phone_video")
    t_ref = cm.to_ref(pts) if pts.size else np.zeros(0)
    out = pd.DataFrame({
        "frame_idx": np.arange(pts.size, dtype=np.int64),
        "pts_s": pts,
        "t_ref_s": np.asarray(t_ref, dtype=float),
        "dropped_before": dropped_before_from_times(pts, nominal_fs, drop_factor),
    })
    out.attrs["clockmap"] = {"stream": cm.stream, "offset_s": cm.offset_s, "drift": cm.drift, "method": cm.method,
                             "uncertainty_s": cm.uncertainty_s}
    return out


# --------------------------------------------------------------------------- parquet helpers
def write_frame_times(df: pd.DataFrame, path: str | os.PathLike) -> Path:
    """Write a frame_times table (parquet via pyarrow). CONTRACTS section 4 frame_times.parquet."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    return path


def read_frame_times(path: str | os.PathLike) -> pd.DataFrame:
    """Read a frame_times table written by `write_frame_times` (CONTRACTS section 4)."""
    return pd.read_parquet(path)


# --------------------------------------------------------------------------- clock sync log
def read_clock_sync_log(csv_path: str | os.PathLike) -> pd.DataFrame:
    """Read `clock_sync_log.csv` (CONTRACTS section 3.8); adds `ts_utc` (datetime) from date + time_utc."""
    df = pd.read_csv(csv_path, dtype=str)
    missing = [c for c in CLOCK_LOG_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"{csv_path}: missing columns {missing}")
    df = df.loc[:, list(CLOCK_LOG_COLUMNS)].copy()
    for c in ("date", "time_utc", "device", "method", "operator"):
        df[c] = df[c].astype(str).str.strip()
    df["offset_ms_vs_phone"] = pd.to_numeric(df["offset_ms_vs_phone"], errors="coerce")
    df["ts_utc"] = pd.to_datetime(df["date"] + " " + df["time_utc"], utc=True, errors="coerce")
    return df.sort_values("ts_utc", kind="stable").reset_index(drop=True)


def daily_offsets(df: pd.DataFrame, date: str, device: str, drift_flag_s_per_8h: float) -> dict:
    """Shift-start and shift-end offsets of one device on one date, drift per 8 h and the flag (section 4.1).

    drift_ms_per_8h = (end_ms - start_ms) / hours_between * 8; `flag` is True when |drift| exceeds cfg
    `clock.drift_flag_s_per_8h` (seconds, converted to ms). With a single entry drift is NaN and the flag None
    (not measurable), never silently False.
    """
    sel = df[(df["date"] == str(date)) & (df["device"] == str(device))].sort_values("ts_utc")
    sel = sel[np.isfinite(sel["offset_ms_vs_phone"].to_numpy(dtype=float))]
    n = len(sel)
    out = {"date": str(date), "device": str(device), "n_entries": n, "start_ms": None, "end_ms": None,
           "hours_between": None, "drift_ms_per_8h": float("nan"), "flag": None}
    if n == 0:
        return out
    first, last = sel.iloc[0], sel.iloc[-1]
    out["start_ms"] = float(first["offset_ms_vs_phone"])
    out["method_start"] = str(first["method"])
    if n == 1:
        return out
    out["end_ms"] = float(last["offset_ms_vs_phone"])
    out["method_end"] = str(last["method"])
    hours = (last["ts_utc"] - first["ts_utc"]).total_seconds() / 3600.0
    out["hours_between"] = float(hours)
    if hours <= 0:
        return out
    drift = (out["end_ms"] - out["start_ms"]) / hours * 8.0
    out["drift_ms_per_8h"] = float(drift)
    out["flag"] = bool(abs(drift) > float(drift_flag_s_per_8h) * 1000.0)
    return out


def offset_at(df: pd.DataFrame, device: str, ts_utc, drift_flag_s_per_8h: float | None = None) -> dict:
    """Interpolated offset (ms vs phone) of `device` at a UTC time from the nearest log entries of that date. Section 4.1 clock discipline; used for the section 4.3 wall-clock cross-check of the Kardia start time.

    Returns {offset_ms, method, n_entries, date}; linear interpolation between shift start and end (the drift is
    assumed linear across the shift), the nearest entry when only one exists on that date.
    """
    ts = pd.Timestamp(ts_utc)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    date = ts.strftime("%Y-%m-%d")
    sel = df[(df["device"] == str(device)) & (df["date"] == date)].sort_values("ts_utc")
    sel = sel[np.isfinite(sel["offset_ms_vs_phone"].to_numpy(dtype=float))]
    if len(sel) == 0:
        return {"offset_ms": None, "method": None, "n_entries": 0, "date": date}
    x = (sel["ts_utc"] - sel["ts_utc"].iloc[0]).dt.total_seconds().to_numpy(dtype=float)
    y = sel["offset_ms_vs_phone"].to_numpy(dtype=float)
    xq = (ts - sel["ts_utc"].iloc[0]).total_seconds()
    if len(sel) == 1 or x[-1] == x[0]:
        off = float(y[0])
    else:
        off = float(np.interp(xq, x, y))
    return {"offset_ms": off, "method": "interpolated" if len(sel) > 1 else str(sel["method"].iloc[0]),
            "n_entries": len(sel), "date": date}


def meta_to_dict(d: Mapping) -> dict:
    """Plain-dict copy with numpy scalars converted, for JSON summaries. Helper for the section 3.3 meta record in ingest.json."""
    out = {}
    for k, v in d.items():
        if isinstance(v, np.generic):
            v = v.item()
        out[k] = v
    return out
