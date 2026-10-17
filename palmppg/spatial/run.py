"""Orchestrate the spatial stage for one clip and camera (protocol sections 6.1 hand presence, 6.2).

landmarks (4 fps on the 8-bit preview) -> ROI polygons -> streamed ROI traces and patch grid ->
static colour. Writes, under `camera_dir` (work/<study_id>/<clip_id>/<camera>/, CONTRACTS section 4):
landmarks.parquet, rois.json, traces.parquet, patches.zarr, static_colour.json and a
spatial_summary.json with the QC-facing landmark summary.
"""
from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from pathlib import Path

import numpy as np
import pandas as pd

from palmppg.core.config import Config
from palmppg.spatial import rois as R
from palmppg.spatial.landmarks import (
    LandmarkProvider,
    MediaPipeHandsProvider,
    SkinSegmentationFallback,
    SyntheticLandmarkProvider,
    run_landmarks,
)
from palmppg.spatial.static_colour import (
    nan_to_none,
    register_features,
    static_colour_features,
    write_static_colour_json,
)
from palmppg.spatial.stmaps import write_patches_zarr
from palmppg.spatial.traces import PI_CHANNELS, RGB_CHANNELS, MaskSchedule, empty_traces, run_traces

CAMERA_SETTINGS = {
    "pi": {"channels": PI_CHANNELS, "plane_scale": 2, "transfer": "none", "colour_space": "linear_raw"},
    "phone": {"channels": RGB_CHANNELS, "plane_scale": 1, "transfer": "srgb_inverse", "colour_space": "inverted_srgb"},
    "pi_proxy": {"channels": RGB_CHANNELS, "plane_scale": 1, "transfer": "srgb_inverse", "colour_space": "inverted_srgb"},
}

# Keys read with defaults because configs/pipeline.yaml does not carry them yet (reported as config additions).
CONFIG_DEFAULTS = {
    "qc.landmark_jitter_px_max": 3.0,
    "qc.hand_detect_min_frac": 0.5,
    "qc.hand_mirror": False,
    "qc.hand_palmar_convention": "left_thumb_right",
    "qc.hand_model_path": None,
    "qc.skin_min_area_frac": 0.05,
    "qc.saturation_level_frac": 0.98,
    "rois.band_width_ratio": 0.6,
}


def _cfg(cfg: Config, key: str):
    return cfg.get(key, CONFIG_DEFAULTS[key])


def camera_settings(camera: str) -> dict:
    if camera not in CAMERA_SETTINGS:
        raise ValueError(f"camera must be one of {sorted(CAMERA_SETTINGS)}")
    return dict(CAMERA_SETTINGS[camera])


def default_full_res_shape(camera: str, cfg: Config) -> tuple[int, int]:
    """(height, width) of the written frame: Pi sensor size or phone resolution from the config."""
    if camera == "pi":
        return int(cfg.get("pi.height")), int(cfg.get("pi.width"))
    return int(cfg.get("phone.height")), int(cfg.get("phone.width"))


def default_white_level(camera: str, cfg: Config) -> float:
    """Clip level in the units the frames arrive in: calibrated Pi planes clip near (white - black)
    times qc.saturation_level_frac; 8-bit video at 255."""
    if camera == "pi":
        return float(cfg.get("pi.white_level") - cfg.get("pi.black_level")) * float(_cfg(cfg, "qc.saturation_level_frac"))
    return 255.0


def build_provider(cfg: Config, landmark_json: str | Path | None = None, provider: LandmarkProvider | None = None):
    """Synthetic ground truth when a landmark JSON is given, else the caller's provider, else MediaPipe."""
    if landmark_json is not None:
        return SyntheticLandmarkProvider(landmark_json)
    if provider is not None:
        return provider
    return MediaPipeHandsProvider(
        mirror=bool(_cfg(cfg, "qc.hand_mirror")), palmar_convention=str(_cfg(cfg, "qc.hand_palmar_convention")),
        model_path=_cfg(cfg, "qc.hand_model_path"),
    )


def run_spatial(
    camera_dir: str | Path,
    camera: str,
    frames_iter_factory: Callable[[], Iterator[tuple[int, object]]],
    preview_iter_factory: Callable[[], Iterator[tuple[int, float, np.ndarray]]],
    frame_times_df: pd.DataFrame,
    grid_t_s: np.ndarray,
    cfg: Config,
    landmark_json: str | Path | None = None,
    full_res_shape: tuple[int, int] | None = None,
    provider: LandmarkProvider | None = None,
    fallback: LandmarkProvider | None = None,
    white_level: float | None = None,
    static_window_start_s: float | None = None,
) -> dict:
    """Run landmarks -> ROIs -> traces/patches -> static colour for one clip and camera; write artefacts.

    `frames_iter_factory()` yields (frame_idx, frame) with frame = Bayer planes dict (pi) or an (H, W, 3)
    8-bit RGB array (phone, pi_proxy); `preview_iter_factory()` yields (frame_idx, t_ref_s, rgb_uint8)
    demosaiced previews for the landmark pass; `frame_times_df` has frame_idx and t_ref_s;
    `grid_t_s` is the uniform reference-clock grid (grid.fs). `full_res_shape` (height, width) of the
    written frame defaults to the config camera size (pass it when the Pi frame is ROI-cropped).
    `static_window_start_s` defaults to the first grid time; the window length is window.static_colour_s.
    Returns the summary dict (landmark summary, paths, counts) that QC reads for hand_detected,
    hand_is_left, hand_palmar, landmark_source, landmark_jitter_px and motion_flag. Sections 6.1, 6.2.
    """
    camera_dir = Path(camera_dir)
    camera_dir.mkdir(parents=True, exist_ok=True)
    settings = camera_settings(camera)
    channels = list(settings["channels"])
    full_res = tuple(full_res_shape) if full_res_shape else default_full_res_shape(camera, cfg)
    rows, cols = int(cfg.get("rois.patch_grid.rows")), int(cfg.get("rois.patch_grid.cols"))
    roi_names = list(cfg.get("rois.names"))
    grid = np.asarray(grid_t_s, dtype=float)
    white = float(white_level) if white_level is not None else default_white_level(camera, cfg)
    register_features(cfg)

    # 1. landmarks at qc.hand_preview_fps on the preview
    lm_provider = build_provider(cfg, landmark_json, provider)
    fb = fallback if fallback is not None else SkinSegmentationFallback(min_area_frac=float(_cfg(cfg, "qc.skin_min_area_frac")))
    try:
        lm_df, lm_summary = run_landmarks(
            preview_iter_factory(), lm_provider, float(cfg.get("qc.hand_preview_fps")), fb,
            full_res_shape=full_res, jitter_px_max=float(_cfg(cfg, "qc.landmark_jitter_px_max")),
            min_detect_frac=float(_cfg(cfg, "qc.hand_detect_min_frac")),
        )
    finally:
        lm_provider.close()
    lm_df.to_parquet(camera_dir / "landmarks.parquet", index=False)
    summary = dict(lm_summary)
    summary.update({"camera": camera, "channels": channels, "colour_space": settings["colour_space"],
                    "full_res_shape": [int(full_res[0]), int(full_res[1])], "white_level": white})
    if isinstance(lm_provider, MediaPipeHandsProvider):
        summary["mediapipe_api"] = lm_provider.api
        summary["mediapipe_unavailable_reason"] = lm_provider.unavailable_reason

    static_start = float(grid[0]) if static_window_start_s is None else float(static_window_start_s)
    t_window = (static_start, static_start + float(cfg.get("window.static_colour_s")))
    detected = lm_df[lm_df["source"] != "none"]

    if len(detected) == 0:
        # nothing to mask: write empty artefacts so downstream readers find every file
        R.write_rois_json(camera_dir / "rois.json", {})
        traces = empty_traces(grid, roi_names, channels)
        traces.to_parquet(camera_dir / "traces.parquet", index=False)
        patches = np.full((grid.size, rows, cols, len(channels)), np.nan, dtype=np.float32)
        write_patches_zarr(camera_dir / "patches.zarr", patches, channels, grid, attrs={"roi": "whole_palm"})
        sc = static_colour_features(traces, t_window, roi_names, settings["colour_space"], camera=camera)
        write_static_colour_json(camera_dir / "static_colour.json", sc)
        summary.update({"traces_info": None, "n_rois": 0, "static_colour_n_frames_used": 0})
        _write_summary(camera_dir, summary)
        return summary

    # 2. ROI polygons of the representative landmark frame (closest to the median landmark set)
    schedule = MaskSchedule(
        lm_df, full_res, plane_scale=int(settings["plane_scale"]), rows=rows, cols=cols,
        roi_kwargs={"band_width_ratio": float(_cfg(cfg, "rois.band_width_ratio"))}, roi_names=roi_names,
    )
    rep = schedule.representative_pos()
    lm_px = R.landmarks_to_px(schedule.lm[rep][:, :2], full_res)
    polys = R.roi_polygons(lm_px, full_res, band_width_ratio=float(_cfg(cfg, "rois.band_width_ratio")))
    masks = R.roi_masks(polys, full_res)
    rois_payload = R.rois_to_json(polys, masks, int(schedule.frame_idx[rep]))
    R.write_rois_json(camera_dir / "rois.json", rois_payload)

    # 3. streamed traces and patch grid on the uniform grid
    traces, patches, info = run_traces(
        frames_iter_factory(), schedule, frame_times_df, grid, channels, white, transfer=settings["transfer"],
        patches_path=camera_dir / "patches.zarr", rows=rows, cols=cols, roi_names=roi_names,
        patch_attrs={"camera": camera, "colour_space": settings["colour_space"]},
    )
    traces.to_parquet(camera_dir / "traces.parquet", index=False)
    (camera_dir / "traces_meta.json").write_text(json.dumps(nan_to_none({
        "camera": camera, "channels": channels, "colour_space": settings["colour_space"],
        "linearised_from_srgb": settings["transfer"] == "srgb_inverse", "white_level": white,
        "grid_fs": float(cfg.get("grid.fs")), "n_grid": int(grid.size), **{k: v for k, v in info.items()},
    }), indent=1, default=_json_default), encoding="utf-8")

    # 4. static colour on the first window.static_colour_s seconds
    sc = static_colour_features(
        traces, t_window, roi_names, settings["colour_space"], camera=camera,
        patches=patches, patch_t_ref_s=grid, patch_channels=channels,
    )
    write_static_colour_json(camera_dir / "static_colour.json", sc)

    summary.update({
        "traces_info": info, "n_rois": len(roi_names), "roi_frame_idx": int(schedule.frame_idx[rep]),
        "static_colour_n_frames_used": sc["n_frames_used"], "static_window": list(t_window),
        "paths": {k: str(camera_dir / k) for k in
                  ("landmarks.parquet", "rois.json", "traces.parquet", "patches.zarr", "static_colour.json")},
    })
    _write_summary(camera_dir, summary)
    return summary


def _write_summary(camera_dir: Path, summary: dict) -> None:
    (camera_dir / "spatial_summary.json").write_text(
        json.dumps(nan_to_none(summary), indent=1, default=_json_default), encoding="utf-8"
    )


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)
