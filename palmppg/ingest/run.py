"""Ingest orchestrators: one streaming pass per camera that writes frame times, the proxy zarr, mean-intensity
series, calibration summary and qc.json under `work/<study_id>/<clip_id>/<camera>/` (CONTRACTS section 4).

Serves protocol section 6.1 for both cameras. Sync (clock maps, sync grade) and hand landmarks are produced by
other modules and are accepted here as optional inputs; without them the phone timeline is the identity map on
PTS (flagged in ingest.json) and `valid_clip` is False with `hand_detected` in `reasons`.
"""
from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from pathlib import Path

import numpy as np
import pandas as pd

from palmppg.core.config import Config, ConfigError, load_frozen_config
from palmppg.core.paths import ParticipantPaths, WorkLayout
from palmppg.core.timeline import ClockMap
from palmppg.ingest.bayer import BayerClipReader, ProxyZarrWriter, demosaic_preview, plane_stats
from palmppg.ingest.calibration import UnitCalibration, aperture_mask_from_flat, vignetting_residual_pct
from palmppg.ingest.qc import (
    append_qc_table,
    build_qc,
    flicker_peaks,
    lighting_drift_pct,
    register_features,
    saturation_fraction,
    saturation_fraction_planes,
    write_qc_json,
)
from palmppg.ingest.timestamps import (
    frame_grid,
    phone_frame_times,
    pi_frame_times,
    read_pi_pts,
    resample_series,
    write_frame_times,
)

PROXY_NAME = "proxy_128x72.zarr"
QC_TABLE_NAME = "qc_table.parquet"
UINT8_WHITE = 255  # format constant of 8-bit video, not a protocol threshold


def _json_dump(obj, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)

    def default(o):
        """JSON encoder fallback for numpy scalars and paths in ingest.json (CONTRACTS section 4)."""
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return None if np.isnan(o) else float(o)
        if isinstance(o, (np.bool_,)):
            return bool(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        if isinstance(o, Path):
            return str(o)
        return str(o)

    path.write_text(json.dumps(obj, indent=2, default=default), encoding="utf-8")
    return path


def _sqi_threshold(sqi_threshold: float | None) -> float | None:
    if sqi_threshold is not None:
        return float(sqi_threshold)
    try:
        return float(load_frozen_config().get("sqi.threshold"))
    except (ConfigError, OSError, TypeError, ValueError):  # frozen config absent or unreadable
        return None


def _grid_series(t: np.ndarray, series: Mapping[str, np.ndarray], grid_fs: float, nominal_fs: float, drop_factor: float) -> pd.DataFrame:
    grid = frame_grid(t, grid_fs)
    out = {"t_ref_s": grid}
    for k, v in series.items():
        out[k] = resample_series(t, v, grid, nominal_fs, drop_factor)
    return pd.DataFrame(out)


# --------------------------------------------------------------------------- Pi
def ingest_pi(participant_paths: ParticipantPaths, clip_id: str, unit_dir: str | os.PathLike | None, work: WorkLayout,
              cfg: Config, t0_ref_ns: int | None = None, hand_summary: Mapping | None = None, sync_grade: str = "none",
              sqi_best: float | None = None, sqi_threshold: float | None = None, skin_mask: np.ndarray | None = None,
              proxy_size: tuple[int, int] = (128, 72), chunk: int = 64, write_pi_proxy: bool = False) -> dict:
    """Ingest one Pi clip (section 6.1): unpack, calibrate, time-stamp, QC, proxy; returns paths and numbers.

    Writes under `work/<study_id>/<clip_id>/pi/`: `frame_times.parquet`, `proxy_128x72.zarr`,
    `mean_intensity.parquet` (per frame, per plane, calibrated units, inside `skin_mask` when given),
    `mean_intensity_grid.parquet` (uniform cfg `grid.fs` grid, NaN in drops), `qc.json`, `ingest.json`; upserts
    `work/tables/qc_table.parquet`. With `write_pi_proxy` the D-006 `pi_proxy/proxy.mp4` is also encoded.
    Pulse extraction never touches anything demosaiced here (non-negotiable 9).
    """
    register_features()
    meta = json.loads(Path(participant_paths.pi_meta(clip_id)).read_text(encoding="utf-8"))
    study_id = str(meta.get("study_id") or participant_paths.study_id)
    out_dir = work.camera(study_id, clip_id, "pi")
    nominal_fs = float(cfg.get("pi.nominal_fps"))
    drop_factor = float(cfg.get("qc.drop_factor"))
    black = float(cfg.get("pi.black_level"))
    white = float(cfg.get("pi.white_level"))
    grid_fs = float(cfg.get("grid.fs"))

    pts = read_pi_pts(participant_paths.pi_pts(clip_id))
    ft = pi_frame_times(pts, t0_ref_ns=t0_ref_ns, nominal_fs=nominal_fs, drop_factor=drop_factor)
    reader = BayerClipReader(participant_paths.pi_raw(clip_id), meta)
    n = int(min(reader.n_frames, len(ft)))
    count_mismatch = {"n_frames_raw": int(reader.n_frames), "n_frames_pts": len(ft), "trailing_bytes": int(reader.trailing_bytes)}
    ft = ft.iloc[:n].reset_index(drop=True)
    ft_path = write_frame_times(ft, out_dir / "frame_times.parquet")
    t = ft["t_ref_s"].to_numpy(dtype=float)

    cal = UnitCalibration.load(unit_dir, meta, black_level=black, sensor_size=(int(cfg.get("pi.width")), int(cfg.get("pi.height"))))
    awb = meta.get("awb_gains") or (1.0, 1.0)
    awb = (float(awb[0]), float(awb[1]))
    prev_black, prev_white = (0.0, white - black) if cal.applied else (black, white)

    writer = ProxyZarrWriter(out_dir / PROXY_NAME, n, proxy_size, t, chunk=chunk, attrs={
        "camera": "pi", "study_id": study_id, "clip_id": clip_id, "calibration_applied": cal.applied,
        "awb_gains": list(awb), "black_level": black, "white_level": white})
    means = {k: np.full(n, np.nan) for k in ("R", "G1", "G2", "B")}
    sat = np.full(n, np.nan)
    pw, ph = int(proxy_size[0]), int(proxy_size[1])
    for idx, planes in reader.iter_chunks(chunk=chunk, stop=n):
        block = np.empty((idx.size, ph, pw, 3), dtype=np.uint8)
        for j, i in enumerate(idx):
            raw = {k: v[j] for k, v in planes.items()}
            sat[i] = saturation_fraction_planes(raw, skin_mask, white)
            corr = cal.apply(raw)
            for k, m in plane_stats(corr, skin_mask).items():
                means[k][i] = m
            block[j] = demosaic_preview(corr, prev_black, prev_white, awb, 2.2, size=(pw, ph))
        writer.write(int(idx[0]), block)
    reader.close()

    mean_g = 0.5 * (means["G1"] + means["G2"])
    per_frame = pd.DataFrame({"frame_idx": ft["frame_idx"].to_numpy(), "t_ref_s": t, "mean_R": means["R"], "mean_G1": means["G1"],
                              "mean_G2": means["G2"], "mean_B": means["B"], "mean_G": mean_g, "sat_frac": sat})
    per_frame.to_parquet(out_dir / "mean_intensity.parquet", index=False)
    grid_df = _grid_series(t, {"mean_G": mean_g, "mean_R": means["R"], "mean_B": means["B"]}, grid_fs, nominal_fs, drop_factor)
    grid_df.to_parquet(out_dir / "mean_intensity_grid.parquet", index=False)

    vignetting = float("nan")
    corrected_flat = cal.corrected_flat()
    if corrected_flat is not None:
        aperture = aperture_mask_from_flat(cal.flat_norm["G1"])
        vignetting = vignetting_residual_pct(corrected_flat, aperture)

    thr = _sqi_threshold(sqi_threshold)
    sat_mean = float(np.nanmean(sat)) if n and np.isfinite(sat).any() else None
    qc = build_qc("pi", study_id, clip_id, ft, grid_df["mean_G"].to_numpy(), sat_mean, hand_summary, vignetting, None,
                  sync_grade, sqi_best, cfg, thr)
    qc_path = write_qc_json(qc, out_dir / "qc.json")
    table_path = work.tables / QC_TABLE_NAME
    append_qc_table(qc, table_path)

    mg = grid_df["mean_G"].to_numpy()
    flicker = flicker_peaks(mg, grid_fs, targets=[float(v) for v in cfg.get("qc.flicker_hz")],
                            tol=float(cfg.get("qc.flicker_tolerance_hz")), snr_db_min=float(cfg.get("qc.flicker_snr_db_min")))
    drift = lighting_drift_pct(mg, grid_df["t_ref_s"].to_numpy())
    result = {
        "camera": "pi", "study_id": study_id, "clip_id": clip_id, "n_frames": n, "t0_ref_ns": int(ft.attrs.get("t0_ref_ns", 0)),
        "paths": {"frame_times": str(ft_path), "proxy": str(writer.path), "mean_intensity": str(out_dir / "mean_intensity.parquet"),
                  "mean_intensity_grid": str(out_dir / "mean_intensity_grid.parquet"), "qc": str(qc_path),
                  "ingest": str(out_dir / "ingest.json"), "qc_table": str(table_path), "raw": str(reader.path)},
        "reader": reader.describe(), "frame_count_check": count_mismatch,
        "drops": {"drop_pct": qc["drop_pct"], "drop_flag": qc["drop_flag"], "n_dropped": int(ft["dropped_before"].sum())},
        "calibration": cal.summary(), "vignetting_residual_pct": vignetting,
        "saturation_frac_mean": sat_mean, "saturation_frac_max": float(np.nanmax(sat)) if n else None,
        "flicker": flicker, "lighting_drift_pct": drift,
        "mean_intensity": {k: float(np.nanmean(v)) for k, v in means.items()},
        "proxy": {"path": str(writer.path), "size": [pw, ph], "n_frames": n},
        "qc": qc, "colour_space": "linear_raw",
    }
    if write_pi_proxy:
        from palmppg.ingest.pi_proxy import make_pi_proxy

        proxy_dir = work.camera(study_id, clip_id, "pi_proxy")
        reader2 = BayerClipReader(participant_paths.pi_raw(clip_id), meta)
        px = make_pi_proxy(reader2, cal, meta, proxy_dir / "proxy.mp4", crf=int(cfg.get("phone.proxy_crf")), chunk=chunk,
                           t_ref_s=t, fps=nominal_fs, black_level=black, white_level=white, awb_gains=awb, n_frames=n)
        reader2.close()
        pft = pd.DataFrame({"frame_idx": np.arange(n, dtype=np.int64), "pts_s": np.arange(n) / nominal_fs, "t_ref_s": t,
                            "dropped_before": ft["dropped_before"].to_numpy()})
        write_frame_times(pft, proxy_dir / "frame_times.parquet")
        px["frame_times_path"] = str(proxy_dir / "frame_times.parquet")
        px.pop("frame_times", None)
        result["pi_proxy"] = px
        result["paths"]["pi_proxy"] = px["path"]
    _json_dump({k: v for k, v in result.items() if k != "qc"}, out_dir / "ingest.json")
    return result


# --------------------------------------------------------------------------- phone
def ingest_phone(participant_paths: ParticipantPaths, clip_id: str, unit_dir: str | os.PathLike | None, work: WorkLayout,
                 cfg: Config, clockmap: ClockMap | None = None, hand_summary: Mapping | None = None, sync_grade: str = "none",
                 sqi_best: float | None = None, sqi_threshold: float | None = None, skin_mask: np.ndarray | None = None,
                 static_regions: Sequence[tuple[int, int, int, int]] | None = None, eis_n_sample: int = 60,
                 proxy_size: tuple[int, int] = (128, 72), chunk: int = 64, mp4_path: str | os.PathLike | None = None,
                 camera: str = "phone") -> dict:
    """Ingest one phone clip (sections 5 and 6.1): PTS, decode, inverted-sRGB means, flat field, EIS, QC, proxy.

    Writes under `work/<study_id>/<clip_id>/<camera>/`: `frame_times.parquet` (frame_idx, pts_s, t_ref_s,
    dropped_before), `proxy_128x72.zarr`, `mean_intensity.parquet` (per frame R, G, B in inverted-sRGB linear-ish
    units after the phone flat field), `mean_intensity_grid.parquet`, `qc.json`, `ingest.json`; upserts the QC
    table. `clockmap` is the phone -> reference map from sync (identity when None, recorded as such).
    `camera` may be "pi_proxy" to ingest the D-006 proxy mp4 (`mp4_path`) through the same path.
    """
    register_features()
    meta_path = Path(participant_paths.phone_meta(clip_id))
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    study_id = str(meta.get("study_id") or participant_paths.study_id)
    mp4 = Path(mp4_path) if mp4_path is not None else Path(participant_paths.phone_mp4(clip_id))
    out_dir = work.camera(study_id, clip_id, camera)
    nominal_fs = float(cfg.get("phone.nominal_fps"))
    drop_factor = float(cfg.get("qc.drop_factor"))
    grid_fs = float(cfg.get("grid.fs"))

    from palmppg.ingest.phone import (
        PhoneClipReader,
        PhoneFlatField,
        detect_eis_warp,
        ffprobe_frame_pts,
        srgb_to_linear,
    )

    probe = ffprobe_frame_pts(mp4)
    cm = clockmap if clockmap is not None else ClockMap.identity(f"{camera}_video")
    ft = phone_frame_times(probe.pts_s, cm, nominal_fs=nominal_fs, drop_factor=drop_factor)
    reader = PhoneClipReader(mp4)
    n = len(ft)
    ft_path = write_frame_times(ft, out_dir / "frame_times.parquet")
    t = ft["t_ref_s"].to_numpy(dtype=float)

    flat = None
    flat_path = Path(unit_dir) / "phone_flatfield.mp4" if unit_dir is not None else None
    if flat_path is not None and flat_path.exists():
        flat = PhoneFlatField.load(flat_path)

    import cv2

    pw, ph = int(proxy_size[0]), int(proxy_size[1])
    writer = ProxyZarrWriter(out_dir / PROXY_NAME, n, proxy_size, t, chunk=chunk, attrs={
        "camera": camera, "study_id": study_id, "clip_id": clip_id, "colour_space": "srgb_decoded",
        "flat_field_applied": flat is not None, "clockmap_method": cm.method})
    means = {k: np.full(n, np.nan) for k in ("R", "G", "B")}
    sat = np.full(n, np.nan)
    block, block_start = [], 0
    decoded = 0
    for idx, _pts, rgb in reader.iter_frames(stop=n):
        decoded += 1
        sat[idx] = saturation_fraction(rgb, skin_mask, UINT8_WHITE)
        lin = srgb_to_linear(rgb)
        if flat is not None:
            lin = flat.apply(lin)
        sel = lin[np.asarray(skin_mask, dtype=bool)] if skin_mask is not None else lin.reshape(-1, 3)
        if sel.size:
            m = sel.reshape(-1, 3).mean(axis=0)
            means["R"][idx], means["G"][idx], means["B"][idx] = (float(m[0]), float(m[1]), float(m[2]))
        block.append(cv2.resize(rgb, (pw, ph), interpolation=cv2.INTER_AREA))
        if len(block) >= chunk:
            writer.write(block_start, np.stack(block))
            block_start += len(block)
            block = []
    if block:
        writer.write(block_start, np.stack(block))
    writer.set_attr("n_frames_decoded", decoded)

    per_frame = pd.DataFrame({"frame_idx": ft["frame_idx"].to_numpy(), "pts_s": ft["pts_s"].to_numpy(), "t_ref_s": t,
                              "mean_R": means["R"], "mean_G": means["G"], "mean_B": means["B"], "sat_frac": sat})
    per_frame.to_parquet(out_dir / "mean_intensity.parquet", index=False)

    # Optional SamaPalmRecorder files: the pre-encoder ROI tap and the per-frame control log. Additive to the
    # decoded path above (the frozen features key off the decoded means); absent on the Open Camera route.
    from palmppg.ingest.phone_tap import ingest_tap_files

    roi_tap = ingest_tap_files(Path(participant_paths.phone_mp4(clip_id)).parent, clip_id, out_dir, frame_times=ft) \
        if camera == "phone" else None

    grid_df = _grid_series(t, {"mean_G": means["G"], "mean_R": means["R"], "mean_B": means["B"]}, grid_fs, nominal_fs, drop_factor)
    grid_df.to_parquet(out_dir / "mean_intensity_grid.parquet", index=False)

    eis = detect_eis_warp(reader, static_regions, n_sample=eis_n_sample, warp_px_max=float(cfg.get("qc.eis_warp_px_max")))

    thr = _sqi_threshold(sqi_threshold)
    sat_mean = float(np.nanmean(sat)) if n and np.isfinite(sat).any() else None
    vignetting = flat.residual_pct() if flat is not None else None
    qc = build_qc(camera, study_id, clip_id, ft, grid_df["mean_G"].to_numpy(), sat_mean, hand_summary, vignetting, eis,
                  sync_grade, sqi_best, cfg, thr)
    qc_path = write_qc_json(qc, out_dir / "qc.json")
    table_path = work.tables / QC_TABLE_NAME
    append_qc_table(qc, table_path)

    mg = grid_df["mean_G"].to_numpy()
    flicker = flicker_peaks(mg, grid_fs, targets=[float(v) for v in cfg.get("qc.flicker_hz")],
                            tol=float(cfg.get("qc.flicker_tolerance_hz")), snr_db_min=float(cfg.get("qc.flicker_snr_db_min")))
    drift = lighting_drift_pct(mg, grid_df["t_ref_s"].to_numpy())
    probe_d = probe.to_dict()
    probe_d.pop("pts_s", None)
    result = {
        "camera": camera, "study_id": study_id, "clip_id": clip_id, "n_frames": n, "n_frames_decoded": decoded,
        "paths": {"frame_times": str(ft_path), "proxy": str(writer.path), "mean_intensity": str(out_dir / "mean_intensity.parquet"),
                  "mean_intensity_grid": str(out_dir / "mean_intensity_grid.parquet"), "qc": str(qc_path),
                  "ingest": str(out_dir / "ingest.json"), "qc_table": str(table_path), "mp4": str(mp4)},
        "probe": probe_d, "is_vfr": bool(probe.is_vfr), "reader": reader.metadata(),
        "clockmap": {"stream": cm.stream, "method": cm.method, "offset_s": cm.offset_s, "drift": cm.drift,
                     "uncertainty_s": cm.uncertainty_s, "is_identity": clockmap is None},
        "drops": {"drop_pct": qc["drop_pct"], "drop_flag": qc["drop_flag"], "n_dropped": int(ft["dropped_before"].sum())},
        "flat_field": flat.summary() if flat is not None else None, "eis": eis,
        "saturation_frac_mean": sat_mean, "saturation_frac_max": float(np.nanmax(sat)) if n and np.isfinite(sat).any() else None,
        "flicker": flicker, "lighting_drift_pct": drift,
        "mean_intensity": {k: float(np.nanmean(v)) if np.isfinite(v).any() else None for k, v in means.items()},
        "proxy": {"path": str(writer.path), "size": [pw, ph], "n_frames": n},
        "colour_space": "inverted_srgb", "linearised_from_srgb": True,
        "linearisation_note": "compressed phone video cannot be truly linearised (tone curve, denoise, chroma subsampling)",
        "roi_tap": roi_tap,
        "qc": qc,
    }
    if roi_tap is not None and roi_tap.get("tap_path"):
        result["paths"]["mean_intensity_tap"] = roi_tap["tap_path"]
    _json_dump({k: v for k, v in result.items() if k != "qc"}, out_dir / "ingest.json")
    return result
