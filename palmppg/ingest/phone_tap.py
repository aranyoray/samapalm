"""Pre-encoder ROI tap and per-frame control log written by SamaPalmRecorder (CONTRACTS section 3.5, optional files).

`phone/clip1_roi.csv` is the mean colour of the centred palm ROI taken from the camera's YUV analysis stream
*before* H.264 — no quantisation, no chroma subsampling, no encoder — one row per analysis frame, timestamped with
the same `SENSOR_TIMESTAMP` the video frames carry. `phone/clip1_controls.csv` is what the camera reported it was
doing on every recorded frame: ISO, shutter, focus distance, lens state, zoom, colour gains, control modes, flash.

Both are *additional* to the decoded-video path in `ingest_phone`, never a replacement: the frozen pipeline keys
its product-candidate features off the decoded means (section 5), and the tap is there so that the gap between
what the sensor saw and what survived compression can be measured instead of assumed.

Clock: the phone stamps these rows on its own CLOCK_BOOTTIME. Where `clip1_frames.csv` exists its `sensor_ts_ns`
values are bit-identical to the tap's, so the tap joins to `frame_idx` and from there to the reference-clock
`frame_times` the sync step produced. Without that join the table carries phone-clock seconds only.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd

ROI_REQUIRED: tuple[str, ...] = (
    "roi_idx", "sensor_ts_ns_raw", "t_ref_ns", "n_px", "y_mean", "u_mean", "v_mean",
    "r_mean", "g_mean", "b_mean", "clip_frac",
)
ROI_GRID: tuple[str, ...] = tuple(f"g{r}{c}" for r in range(3) for c in range(3))
CONTROLS_REQUIRED: tuple[str, ...] = (
    "frame_idx", "sensor_ts_ns", "iso", "exposure_ns", "focus_diopters", "lens_state", "zoom_ratio",
    "gain_r", "gain_g_even", "gain_g_odd", "gain_b", "awb_mode", "ae_mode", "af_mode", "tonemap_mode",
    "shading_mode", "flash_state",
)
FRAMES_REQUIRED: tuple[str, ...] = ("frame_idx", "sensor_ts_ns", "wall_ns", "iso", "exposure_ns")

# Camera2 enum values the summary names, so a reader of ingest.json need not look them up.
LENS_STATE_MOVING = 1
FLASH_STATE_FIRED = 3
AF_MODE_OFF = 0
AE_MODE_OFF = 0
AWB_MODE_OFF = 0
TONEMAP_CONTRAST_CURVE = 0
SHADING_OFF = 0


def _require(df: pd.DataFrame, cols: tuple[str, ...], path: str | os.PathLike) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"{path}: missing columns {missing}")


def read_phone_roi_csv(path: str | os.PathLike) -> pd.DataFrame:
    """Read `clip1_roi.csv`; rows sorted by `t_ref_ns`, numeric columns coerced, `t_phone_s` added (phone clock)."""
    df = pd.read_csv(path)
    _require(df, ROI_REQUIRED, path)
    for c in ROI_REQUIRED[:4]:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("int64")
    for c in ROI_REQUIRED[4:] + tuple(g for g in ROI_GRID if g in df.columns):
        df[c] = pd.to_numeric(df[c], errors="coerce").astype(float)
    df = df.sort_values("t_ref_ns", kind="stable").reset_index(drop=True)
    df["t_phone_s"] = (df["t_ref_ns"] - df["t_ref_ns"].iloc[0]) / 1e9 if len(df) else np.array([], dtype=float)
    return df


def read_phone_controls_csv(path: str | os.PathLike) -> pd.DataFrame:
    """Read `clip1_controls.csv`; rows sorted by `frame_idx`, numeric columns coerced (blank gains become NaN)."""
    df = pd.read_csv(path)
    _require(df, CONTROLS_REQUIRED, path)
    for c in CONTROLS_REQUIRED:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in ("frame_idx", "sensor_ts_ns", "iso", "exposure_ns"):
        df[c] = df[c].astype("int64")
    return df.sort_values("frame_idx", kind="stable").reset_index(drop=True)


def read_phone_frames_csv(path: str | os.PathLike) -> pd.DataFrame:
    """Read the contract `clip1_frames.csv` (section 3.5) with int64 columns, sorted by `frame_idx`."""
    df = pd.read_csv(path)
    _require(df, FRAMES_REQUIRED, path)
    for c in FRAMES_REQUIRED:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("int64")
    return df.sort_values("frame_idx", kind="stable").reset_index(drop=True)


def roi_tap_table(roi: pd.DataFrame, frames: pd.DataFrame | None = None,
                  frame_times: pd.DataFrame | None = None) -> pd.DataFrame:
    """The tap as a per-frame intensity table shaped like `mean_intensity.parquet`.

    Values are 8-bit sRGB code values as the camera delivered them (0-255), *not* linearised and *not* flat-fielded:
    the tap is the sensor-side record, and the ingest's inversion belongs to the decoded path. `frame_idx` and
    `t_ref_s` are filled by joining on `sensor_ts_ns` to `clip1_frames.csv` and then on `frame_idx` to the sync
    step's `frame_times`; rows without a match keep NaN there rather than an invented time. Where the encoder dropped
    frames the join is still exact — the logger counted every capture, so `frame_idx` is the capture index.
    """
    t_ref_ns = roi["t_ref_ns"].to_numpy(dtype="int64")
    t_phone = (roi["t_phone_s"].to_numpy(dtype=float) if "t_phone_s" in roi.columns
               else (t_ref_ns - t_ref_ns[0]) / 1e9 if len(roi) else np.array([], dtype=float))
    out = pd.DataFrame({
        "roi_idx": roi["roi_idx"].to_numpy(),
        "sensor_ts_ns": roi["sensor_ts_ns_raw"].to_numpy(dtype="int64"),
        "t_phone_s": t_phone,
        "mean_R": roi["r_mean"].to_numpy(dtype=float),
        "mean_G": roi["g_mean"].to_numpy(dtype=float),
        "mean_B": roi["b_mean"].to_numpy(dtype=float),
        "y_mean": roi["y_mean"].to_numpy(dtype=float),
        "clip_frac": roi["clip_frac"].to_numpy(dtype=float),
        "n_px": roi["n_px"].to_numpy(),
    })
    frame_idx = pd.array([pd.NA] * len(out), dtype="Int64")
    if frames is not None and len(frames):
        key = frames[["sensor_ts_ns", "frame_idx"]].drop_duplicates("sensor_ts_ns")
        # frames.csv holds the reference-clock stamp; the tap holds both the raw sensor stamp and its
        # reference-clock conversion. On a REALTIME sensor the two are equal; try the raw stamp first.
        for col in (out["sensor_ts_ns"], pd.Series(t_ref_ns, name="sensor_ts_ns")):
            hit = pd.DataFrame({"sensor_ts_ns": col.to_numpy()}).merge(key, on="sensor_ts_ns", how="left")["frame_idx"]
            if hit.notna().any():
                frame_idx = pd.array(hit.to_numpy(dtype=float), dtype="Int64")
                break
    out["frame_idx"] = frame_idx
    out["t_ref_s"] = np.nan
    if frame_times is not None and len(frame_times) and {"frame_idx", "t_ref_s"} <= set(frame_times.columns):
        ft = frame_times[["frame_idx", "t_ref_s"]].drop_duplicates("frame_idx")
        ft = ft.assign(frame_idx=pd.array(ft["frame_idx"].to_numpy(dtype=float), dtype="Int64"))
        out = out.drop(columns="t_ref_s").merge(ft, on="frame_idx", how="left")
    return out


def controls_summary(df: pd.DataFrame) -> dict:
    """What the camera held fixed, and what it did not, over the recorded frames.

    A pinned clip has one ISO, one exposure and one focus value, a stationary lens on every frame, AF/AE/AWB all
    OFF, the sRGB contrast curve and shading correction off. Every count here is a departure from that, reported
    as a number rather than a verdict so the QC thresholds stay in the frozen config, not in this file.
    """
    n = int(len(df))
    if n == 0:
        return {"n_rows": 0}

    def distinct(col: str) -> int:
        return int(df[col].dropna().round(6).nunique())

    gains = df[["gain_r", "gain_g_even", "gain_g_odd", "gain_b"]].dropna()
    return {
        "n_rows": n,
        "iso_distinct": distinct("iso"),
        "exposure_ns_distinct": distinct("exposure_ns"),
        "exposure_ns_max": int(df["exposure_ns"].max()),
        "focus_diopters_distinct": distinct("focus_diopters"),
        "focus_diopters_median": float(df["focus_diopters"].median()),
        "lens_moving_frames": int((df["lens_state"] == LENS_STATE_MOVING).sum()),
        "zoom_ratio_min": float(df["zoom_ratio"].min()),
        "zoom_ratio_max": float(df["zoom_ratio"].max()),
        "colour_gains_distinct": int(gains.round(4).drop_duplicates().shape[0]) if len(gains) else None,
        "af_mode_off_frames": int((df["af_mode"] == AF_MODE_OFF).sum()),
        "ae_mode_off_frames": int((df["ae_mode"] == AE_MODE_OFF).sum()),
        "awb_mode_off_frames": int((df["awb_mode"] == AWB_MODE_OFF).sum()),
        "tonemap_contrast_curve_frames": int((df["tonemap_mode"] == TONEMAP_CONTRAST_CURVE).sum()),
        "shading_off_frames": int((df["shading_mode"] == SHADING_OFF).sum()),
        "flash_fired_frames": int((df["flash_state"] == FLASH_STATE_FIRED).sum()),
    }


def ingest_tap_files(phone_dir: str | os.PathLike, clip_id: str, out_dir: str | os.PathLike,
                     frame_times: pd.DataFrame | None = None) -> dict | None:
    """Read whichever of the optional phone files exist and write `mean_intensity_tap.parquet`.

    Returns None when neither optional file is present (the Open Camera route), otherwise a dict for ingest.json
    with paths, row counts, the join coverage and the controls summary.
    """
    phone_dir = Path(phone_dir)
    out_dir = Path(out_dir)
    roi_path = phone_dir / f"{clip_id}_roi.csv"
    controls_path = phone_dir / f"{clip_id}_controls.csv"
    frames_path = phone_dir / f"{clip_id}_frames.csv"
    if not roi_path.exists() and not controls_path.exists():
        return None

    result: dict = {"roi_file": str(roi_path) if roi_path.exists() else None,
                    "controls_file": str(controls_path) if controls_path.exists() else None,
                    "units": "8-bit sRGB code values as delivered by the camera; not linearised, not flat-fielded"}
    frames = read_phone_frames_csv(frames_path) if frames_path.exists() else None

    if roi_path.exists():
        roi = read_phone_roi_csv(roi_path)
        tap = roi_tap_table(roi, frames, frame_times)
        out_dir.mkdir(parents=True, exist_ok=True)
        tap_path = out_dir / "mean_intensity_tap.parquet"
        tap.to_parquet(tap_path, index=False)
        joined = int(tap["frame_idx"].notna().sum())
        result.update({
            "tap_path": str(tap_path), "n_roi_rows": int(len(tap)), "n_joined_to_frames": joined,
            "n_with_t_ref": int(np.isfinite(tap["t_ref_s"].to_numpy(dtype=float)).sum()),
            "roi_mean": {k: float(tap[k].mean()) for k in ("mean_R", "mean_G", "mean_B", "y_mean")},
            "roi_dark_fraction": float((tap["y_mean"] < 40).mean()),
            "roi_clip_frac_max": float(tap["clip_frac"].max()),
        })
    if controls_path.exists():
        result["controls"] = controls_summary(read_phone_controls_csv(controls_path))
    return result
