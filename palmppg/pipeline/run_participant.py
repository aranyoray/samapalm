"""Run one participant end to end: ingest -> ECG -> sync -> spatial -> pulse -> beats -> QC -> features.

Order of operations (why it is this order):
  1. Pi ingest (unpack, calibrate, frame times, mean intensities, proxy video, pi_proxy mp4).
  2. ECG processing (independent of video): clean, R-peaks, rate series, artefact onset.
  3. LED and thumb block traces from the calibrated Bayer planes (one streaming pass).
  4. Spatial on the Pi (landmarks, ROIs, traces, patches, static colour).
  5. Timeline v1 (no PPG rate yet) so the pulse stage knows the analysis window.
  6. Pulse on the Pi; the best-SQI signal gives the PPG rate series.
  7. Timeline v2 with the ECG-versus-PPG rate cross-correlation -> sync grade; timeline.json, sync.json.
  8. ECG samples and R-peaks mapped onto the reference clock when an ECG map exists.
  9. Phone: LED trace + audio -> phone clock map came from step 7; ingest with that map, spatial, pulse.
 10. pi_proxy (D-006): same chain on the H.264 proxy of the Pi frames.
 11. Beats (+ PAT when the grade is fine) per camera.
 12. QC finalised per camera with hand summary, best SQI and sync grade; qc_table upserted.
 13. One feature row per camera -> features_<camera>.parquet.
Each stage records status in pipeline.json; a failing camera is recorded as failed, never dropped silently
(protocol 11.3: failures count).
"""
from __future__ import annotations

import datetime as dt
import json
import time
import traceback
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from palmppg.core.config import Config, load_frozen_config, load_pipeline_config
from palmppg.core.crf import derive_file
from palmppg.core.paths import ParticipantPaths, StudyLayout, WorkLayout
from palmppg.core.timeline import Timeline, uniform_grid

CAMERAS = ("pi", "phone", "pi_proxy")


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if np.isnan(o) else float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, Path):
        return str(o)
    return str(o)


def _dump(obj: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, default=_json_default), encoding="utf-8")


def _load_json(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


class StageLog:
    """Collects per-stage status for pipeline.json."""

    def __init__(self) -> None:
        self.stages: list[dict] = []

    def run(self, name: str, fn: Callable[[], Any], required: bool = False) -> Any:
        t0 = time.time()
        try:
            out = fn()
            self.stages.append({"stage": name, "status": "ok", "seconds": round(time.time() - t0, 2)})
            return out
        except Exception as exc:
            self.stages.append({"stage": name, "status": "failed", "seconds": round(time.time() - t0, 2),
                                "error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()[-4000:]})
            if required:
                raise
            return None

    def status(self, name: str) -> str | None:
        for s in self.stages:
            if s["stage"] == name:
                return s["status"]
        return None


# --------------------------------------------------------------------------- Pi helpers
def _pi_calibration(pp: ParticipantPaths, clip_id: str, meta: dict, unit_dir: Path | None, cfg: Config):
    from palmppg.ingest.calibration import UnitCalibration

    return UnitCalibration.load(unit_dir, meta, black_level=float(cfg.get("pi.black_level")),
                                sensor_size=(int(cfg.get("pi.width")), int(cfg.get("pi.height"))))


def _pi_frames_factory(pp: ParticipantPaths, clip_id: str, meta: dict, cal, n_max: int | None = None):
    from palmppg.ingest.bayer import BayerClipReader

    def factory() -> Iterator[tuple[int, dict]]:
        reader = BayerClipReader(pp.pi_raw(clip_id), meta)
        try:
            for idx, planes in reader.iter_frames(stop=n_max):
                yield int(idx), cal.apply(planes)
        finally:
            reader.close()

    return factory


def _pi_preview_factory(pp: ParticipantPaths, clip_id: str, meta: dict, cal, t_of_frame: Mapping[int, float],
                        cfg: Config, n_max: int | None = None):
    from palmppg.ingest.bayer import BayerClipReader, demosaic_preview

    nominal = float(meta.get("fps_nominal") or cfg.get("pi.nominal_fps"))
    step = max(1, round(nominal / float(cfg.get("qc.hand_preview_fps"))))
    white = float(cfg.get("pi.white_level")) - float(cfg.get("pi.black_level"))
    awb = tuple(meta.get("awb_gains") or (1.0, 1.0))

    def factory() -> Iterator[tuple[int, float, np.ndarray]]:
        reader = BayerClipReader(pp.pi_raw(clip_id), meta)
        try:
            for idx, planes in reader.iter_frames(step=step, stop=n_max):
                if int(idx) not in t_of_frame:
                    continue
                yield int(idx), float(t_of_frame[int(idx)]), demosaic_preview(cal.apply(planes), black_level=0.0,
                                                                              white_level=white, awb_gains=awb)
        finally:
            reader.close()

    return factory


def _block_slices(block: Mapping, scale: int) -> tuple[slice, slice]:
    x, y, w, h = (int(block[k]) for k in ("x", "y", "w", "h"))
    return slice(y // scale, max(y // scale + 1, (y + h) // scale)), slice(x // scale, max(x // scale + 1, (x + w) // scale))


def block_traces_pi(frames_factory, blocks: Mapping[str, Mapping]) -> dict[str, tuple[np.ndarray, np.ndarray, str]]:
    """One streaming pass over calibrated Bayer planes: mean of each named block per plane, best-contrast plane.

    Returns {name: (frame_idx, intensity, plane)} for the LED block (section 4.2) and the thumb block (4.3).
    Block coordinates are full-resolution Bayer coordinates; planes are half resolution.
    """
    from palmppg.ingest.led import select_best_plane

    idx_list: list[int] = []
    acc: dict[str, dict[str, list[float]]] = {name: {} for name in blocks}
    sl = {name: _block_slices(b, 2) for name, b in blocks.items()}
    for idx, planes in frames_factory():
        idx_list.append(idx)
        for name, (ys, xs) in sl.items():
            for plane, arr in planes.items():
                acc[name].setdefault(plane, []).append(float(np.mean(arr[ys, xs])))
    out = {}
    fi = np.asarray(idx_list, dtype=np.int64)
    for name in blocks:
        traces = {p: np.asarray(v, dtype=float) for p, v in acc[name].items()}
        if not traces:
            continue
        best = select_best_plane(traces)
        out[name] = (fi, traces[best], best)
    return out


def block_trace_rgb(frames_iter: Iterator[tuple[int, float, np.ndarray]], block: Mapping) -> tuple[np.ndarray, np.ndarray, str]:
    """LED block trace on an RGB stream (phone); best-contrast channel (section 4.2)."""
    from palmppg.ingest.led import select_best_plane

    ys, xs = _block_slices(block, 1)
    idx_list, acc = [], {"R": [], "G": [], "B": []}
    for idx, _pts, rgb in frames_iter:
        idx_list.append(int(idx))
        patch = rgb[ys, xs].astype(np.float32)
        for k, c in zip(("R", "G", "B"), range(3), strict=True):
            acc[k].append(float(patch[..., c].mean()))
    traces = {k: np.asarray(v, dtype=float) for k, v in acc.items()}
    best = select_best_plane(traces)
    return np.asarray(idx_list, dtype=np.int64), traces[best], best


# --------------------------------------------------------------------------- phone helpers
def _phone_frames_factory(mp4: Path, n_max: int | None = None):
    from palmppg.ingest.phone import PhoneClipReader

    def factory() -> Iterator[tuple[int, np.ndarray]]:
        reader = PhoneClipReader(mp4)
        for idx, _pts, rgb in reader.iter_frames(stop=n_max):
            yield int(idx), rgb

    return factory


def _phone_preview_factory(mp4: Path, t_of_frame: Mapping[int, float], fps_nominal: float, cfg: Config, n_max: int | None = None):
    from palmppg.ingest.phone import PhoneClipReader

    step = max(1, round(fps_nominal / float(cfg.get("qc.hand_preview_fps"))))
    size = (128, 72)

    def factory() -> Iterator[tuple[int, float, np.ndarray]]:
        import cv2

        reader = PhoneClipReader(mp4)
        for idx, _pts, rgb in reader.iter_frames(step=step, stop=n_max):
            if int(idx) not in t_of_frame:
                continue
            small = cv2.resize(rgb, (max(size[0], rgb.shape[1] // 4), max(size[1], rgb.shape[0] // 4)), interpolation=cv2.INTER_AREA)
            yield int(idx), float(t_of_frame[int(idx)]), small

    return factory


# --------------------------------------------------------------------------- clock sync log
def _day_offsets(layout: StudyLayout, pi_meta: Mapping, cfg: Config) -> dict[str, float] | None:
    """{device: offset_ms_vs_phone} for the clip's date from clock_sync_log.csv (section 4.1)."""
    from palmppg.ingest.timestamps import offset_at, read_clock_sync_log

    path = layout.clock_sync_log
    if not path.exists():
        return None
    try:
        df = read_clock_sync_log(path)
    except Exception:  # noqa: BLE001 - a malformed log is reported through the sync flags, not fatal here
        return None
    start_wall_ns = pi_meta.get("start_wall_ns")
    if start_wall_ns is None:
        return None
    ts = dt.datetime.fromtimestamp(int(start_wall_ns) / 1e9, tz=dt.UTC)
    out = {}
    for device in sorted(df["device"].dropna().unique()):
        try:
            r = offset_at(df, device, ts, float(cfg.get("clock.drift_flag_s_per_8h")))
            if r.get("offset_ms") is not None and np.isfinite(r["offset_ms"]):
                out[device] = float(r["offset_ms"])
        except Exception:  # noqa: BLE001
            continue
    return out or None


# --------------------------------------------------------------------------- landmark ground truth adapter
def provider_landmarks_json(src: Path, dst: Path) -> Path | None:
    """Adapt a ground-truth landmarks file to the SyntheticLandmarkProvider layout.

    The synthetic generator writes {"landmarks": [{"name", "x", "y", "z"} x 21], "is_left", "palmar", "static": true}
    (or {"frames": [...]}); the provider reads {"frames": [{"frame_idx", "lm": [[x, y, z] x 21]}], "static": [[x, y, z] x 21]}.
    Returns the path to pass as `landmark_json`, or None when `src` is absent.
    """
    if not src.exists():
        return None
    data = json.loads(src.read_text(encoding="utf-8"))
    if isinstance(data.get("static"), list) or (isinstance(data.get("frames"), list) and data["frames"] and "lm" in data["frames"][0]):
        return src
    out: dict[str, Any] = {"is_left": bool(data.get("is_left", True)), "palmar": bool(data.get("palmar", True)), "source": data.get("source", "synthetic")}

    def _lm(entries):
        return [[float(e["x"]), float(e["y"]), float(e.get("z", 0.0))] for e in entries]

    if isinstance(data.get("landmarks"), list) and data["landmarks"] and isinstance(data["landmarks"][0], Mapping):
        out["static"] = _lm(data["landmarks"])
    if isinstance(data.get("frames"), list) and data["frames"] and "landmarks" in data["frames"][0]:
        out["frames"] = [{"frame_idx": int(f.get("frame_idx", i)), "lm": _lm(f["landmarks"]),
                          "is_left": bool(f.get("is_left", out["is_left"])), "palmar": bool(f.get("palmar", out["palmar"]))}
                         for i, f in enumerate(data["frames"])]
    if "static" not in out and "frames" not in out:
        return None
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(out), encoding="utf-8")
    return dst


# --------------------------------------------------------------------------- QC finalisation
def _skin_series(camera_dir: Path, timeline: Timeline | None) -> tuple[np.ndarray | None, float | None]:
    """Mean skin intensity on the grid (whole_palm G) inside the analysis window, and the skin saturation fraction.

    Protocol 6.1 measures saturation "in the skin mask" and flicker on the mean intensity; the whole-frame series
    from ingest includes the blinking LED block (whose P1 pattern has a 10 Hz harmonic), so the finalised QC uses the
    whole_palm ROI trace from spatial when it exists.
    """
    p = camera_dir / "traces.parquet"
    if not p.exists():
        return None, None
    df = pd.read_parquet(p)
    gcols = [c for c in ("whole_palm__G__mean", "whole_palm__G1__mean") if c in df.columns]
    if not gcols:
        return None, None
    g = df[gcols[0]].to_numpy(float)
    if gcols[0].endswith("G1__mean") and "whole_palm__G2__mean" in df.columns:
        g = 0.5 * (g + df["whole_palm__G2__mean"].to_numpy(float))
    t = df["t_ref_s"].to_numpy(float)
    mask = timeline.valid_mask(t) if timeline is not None and timeline.analysis_window is not None else np.isfinite(g)
    series = g[mask] if mask.any() else g
    sat = None
    if "whole_palm__sat_frac" in df.columns:
        sv = df["whole_palm__sat_frac"].to_numpy(float)
        sv = sv[mask] if mask.any() else sv
        sat = float(np.nanmean(sv)) if np.isfinite(sv).any() else None
    return series, sat


def finalise_qc(camera_dir: Path, camera: str, study_id: str, clip_id: str, cfg: Config, hand_summary: Mapping | None,
                sqi_best: float | None, sync_grade: str, sqi_threshold: float | None, tables_dir: Path,
                timeline: Timeline | None = None) -> dict:
    """Rebuild qc.json with everything the later stages learned (hand, SQI, sync grade, skin-mask series); upsert qc_table (6.1)."""
    from palmppg.ingest.qc import append_qc_table, build_qc, write_qc_json
    from palmppg.ingest.timestamps import read_frame_times

    ft = read_frame_times(camera_dir / "frame_times.parquet")
    grid = pd.read_parquet(camera_dir / "mean_intensity_grid.parquet")
    ingest = _load_json(camera_dir / "ingest.json") or {}
    col = "mean_G" if "mean_G" in grid.columns else next(c for c in grid.columns if c.startswith("mean_"))
    series, sat = _skin_series(camera_dir, timeline)
    if series is None:
        series, sat = grid[col].to_numpy(), ingest.get("saturation_frac_mean")
    eis = (ingest.get("eis") if isinstance(ingest.get("eis"), Mapping) else None)
    qc = build_qc(camera, study_id, clip_id, ft, series, sat, hand_summary,
                  ingest.get("vignetting_residual_pct"), eis, sync_grade, sqi_best, cfg, sqi_threshold)
    qc["qc_series_source"] = "whole_palm_trace" if (camera_dir / "traces.parquet").exists() else "whole_frame"
    write_qc_json(qc, camera_dir / "qc.json")
    append_qc_table(qc, tables_dir / "qc_table.parquet")
    return qc


def _best_sqi(camera_dir: Path) -> float | None:
    s = _load_json(camera_dir / "pulse_sqi.json")
    if not s or not s.get("best"):
        return None
    entry = s.get(s["best"]) or {}
    v = entry.get("sqi")
    return float(v) if v is not None else None


def _hand_summary(camera_dir: Path) -> dict | None:
    s = _load_json(camera_dir / "spatial_summary.json")
    if not s:
        return None
    src = s.get("landmarks") if isinstance(s.get("landmarks"), Mapping) else s
    keys = ("hand_detected", "hand_is_left", "hand_palmar", "landmark_source", "landmark_jitter_px", "motion_flag")
    return {k: src.get(k) for k in keys}


# --------------------------------------------------------------------------- pulse -> rate series
def _ppg_rate_series(camera_dir: Path, cfg: Config) -> tuple[np.ndarray, np.ndarray] | None:
    from palmppg.pulse.rate import instantaneous_rate

    s = _load_json(camera_dir / "pulse_sqi.json")
    p = camera_dir / "pulse.parquet"
    if not s or not s.get("best") or not p.exists():
        return None
    df = pd.read_parquet(p)
    if s["best"] not in df.columns:
        return None
    t = df["t_ref_s"].to_numpy(dtype=float)
    x = df[s["best"]].to_numpy(dtype=float)
    ok = np.isfinite(x) & np.isfinite(t)
    if ok.sum() < 10 * cfg.get("grid.fs"):
        return None
    t, x = t[ok], x[ok]
    fs = float(cfg.get("grid.fs"))
    rt, bpm = instantaneous_rate(x, fs, method="peaks", grid_fs=float(cfg.get("sync.xcorr.rate_fs")), t0=float(t[0]),
                                 band=tuple(cfg.get("pulse.band_rate")), ibi_bounds_s=tuple(cfg.get("beats.ibi_bounds_s")))
    return rt, bpm


# --------------------------------------------------------------------------- main runner
def run_participant(layout: StudyLayout, study_id: str, work: WorkLayout, cfg: Config | None = None, clip_id: str = "clip1",
                    cameras: tuple[str, ...] = CAMERAS, sqi_threshold: float | None = None, n_max_frames: int | None = None) -> dict:
    """Process one participant's clip through every stage; returns the pipeline.json dict."""
    cfg = cfg or load_pipeline_config()
    if sqi_threshold is None:
        sqi_threshold = float(load_frozen_config().get("sqi.threshold"))
    pp = layout.participant(study_id)
    clip_dir = work.clip(study_id, clip_id)
    log = StageLog()
    result: dict[str, Any] = {"study_id": study_id, "clip_id": clip_id, "cameras": list(cameras), "started_utc": dt.datetime.now(dt.UTC).isoformat()}

    crf = log.run("crf", lambda: derive_file(pp.crf, cfg.section("crf")), required=True)
    clinician = log.run("clinician", lambda: _load_json(pp.clinician))
    pi_meta = json.loads(pp.pi_meta(clip_id).read_text(encoding="utf-8"))
    unit_dir = layout.unit(str(pi_meta.get("unit_id") or crf.get("unit_id") or "unit_01"))
    unit_dir = unit_dir if unit_dir.exists() else None
    want_proxy = "pi_proxy" in cameras

    # 1. Pi ingest -----------------------------------------------------------------------------------
    from palmppg.ingest.run import ingest_phone, ingest_pi

    pi_ing = log.run("ingest_pi", lambda: ingest_pi(pp, clip_id, unit_dir, work, cfg, sqi_threshold=sqi_threshold,
                                                    write_pi_proxy=want_proxy), required=True)
    pi_dir = work.camera(study_id, clip_id, "pi")
    from palmppg.ingest.timestamps import read_frame_times

    ft_pi = read_frame_times(pi_dir / "frame_times.parquet")
    n_pi = len(ft_pi) if n_max_frames is None else min(len(ft_pi), n_max_frames)
    t_of_pi = dict(zip(ft_pi["frame_idx"].astype(int), ft_pi["t_ref_s"].astype(float), strict=True))
    int(pi_ing.get("t0_ref_ns") or 0)
    pts_df = pd.read_csv(pp.pi_pts(clip_id))
    grid_fs = float(cfg.get("grid.fs"))
    grid_t = uniform_grid(float(ft_pi["t_ref_s"].iloc[0]), float(ft_pi["t_ref_s"].iloc[n_pi - 1]), grid_fs)
    cal = _pi_calibration(pp, clip_id, pi_meta, unit_dir, cfg)

    # 2. ECG ------------------------------------------------------------------------------------------
    from palmppg.ecg.run import process_ecg

    ecg_res = log.run("ecg", lambda: process_ecg(pp, clip_dir, cfg, clip_id=clip_id))
    ecg_dir = clip_dir / "ecg"

    # 3. LED + thumb traces (one pass) -----------------------------------------------------------------
    led_block = pi_meta.get("led_block") or cfg.get("sync.led_block.pi")
    thumb_block = pi_meta.get("thumb_block") or cfg.get("sync.thumb_block.pi")
    blocks = {"led": led_block, "thumb": thumb_block}
    traces = log.run("pi_block_traces", lambda: block_traces_pi(_pi_frames_factory(pp, clip_id, pi_meta, cal, n_pi), blocks)) or {}

    # 4. Spatial on the Pi ----------------------------------------------------------------------------
    from palmppg.spatial.run import run_spatial

    lm_json = provider_landmarks_json(pp.pi / f"{clip_id}_landmarks.json", clip_dir / "landmarks_provider.json")
    full_res = (int(pi_meta.get("height") or cfg.get("pi.height")), int(pi_meta.get("width") or cfg.get("pi.width")))

    def _spatial_pi():
        return run_spatial(pi_dir, "pi", _pi_frames_factory(pp, clip_id, pi_meta, cal, n_pi),
                           _pi_preview_factory(pp, clip_id, pi_meta, cal, t_of_pi, cfg, n_pi), ft_pi.iloc[:n_pi], grid_t, cfg,
                           landmark_json=lm_json, full_res_shape=full_res,
                           static_window_start_s=float(ft_pi["t_ref_s"].iloc[0]))

    log.run("spatial_pi", _spatial_pi)

    # 5. Timeline v1 and 6. pulse on the Pi ------------------------------------------------------------
    from palmppg.ingest.sync import build_timeline, write_sync_json
    from palmppg.ingest.sync_events import read_sync_events
    from palmppg.pulse.run import run_pulse

    se_path = pp.sync_events(clip_id)
    sync_events_df = read_sync_events(se_path) if se_path.exists() else None
    kardia_meta = _load_json(pp.ecg_meta)
    ecg_inputs: dict = {"kardia_meta": kardia_meta, "day_offsets": _day_offsets(layout, pi_meta, cfg), "artefact_t_ecg_s": None, "rate_series": None}
    if ecg_res:
        art = _load_json(ecg_dir / "artefact.json") or {}
        if art.get("found"):
            ecg_inputs["artefact_t_ecg_s"] = float(art["onset_t_ecg_s"])
        rs = ecg_dir / "rate_series.parquet"
        if rs.exists():
            r = pd.read_parquet(rs)
            ecg_inputs["rate_series"] = (r["t_ecg_s"].to_numpy(float), r["bpm"].to_numpy(float))

    # phone sync inputs (LED trace, PTS, audio) ---------------------------------------------------------
    phone_mp4 = pp.phone_mp4(clip_id)
    phone_meta = _load_json(pp.phone_meta(clip_id)) or {}
    capture_mode = str(pi_meta.get("capture_mode") or phone_meta.get("capture_mode") or cfg.get("study.capture_mode"))
    phone_inputs: dict = {"led": None, "pts": None, "audio": None}
    if "phone" in cameras and phone_mp4.exists():
        from palmppg.ingest.phone import PhoneClipReader, extract_audio, ffprobe_frame_pts

        def _phone_sync_inputs():
            fp = ffprobe_frame_pts(phone_mp4)
            out = {"pts": fp.pts_s, "fps": fp.fps_nominal, "is_vfr": fp.is_vfr, "n_frames": fp.n_frames, "led": None, "audio": None}
            blk = phone_meta.get("led_block") or cfg.get("sync.led_block.phone")
            if blk:
                reader = PhoneClipReader(phone_mp4)
                fi, y, ch = block_trace_rgb(reader.iter_frames(), blk)
                out["led"] = (fi, y)
                out["led_channel"] = ch
            try:
                out["audio"] = extract_audio(phone_mp4)
            except Exception as exc:  # noqa: BLE001 - audio is optional for the video LED map
                out["audio_error"] = f"{type(exc).__name__}: {exc}"
            return out

        got = log.run("phone_sync_inputs", _phone_sync_inputs)
        if got:
            phone_inputs = got

    led_pi = traces.get("led")
    thumb_pi = traces.get("thumb")

    def _timeline(ppg_rate):
        return build_timeline(study_id, clip_id, pi_meta, pts_df[["frame_idx", "sensor_ts_ns"]], sync_events_df,
                              (led_pi[0], led_pi[1]) if led_pi else None,
                              led_trace_phone=phone_inputs.get("led"), phone_pts_s=phone_inputs.get("pts"),
                              phone_audio=phone_inputs.get("audio"), thumb_trace_pi=(thumb_pi[0], thumb_pi[1]) if thumb_pi else None,
                              ecg=ecg_inputs, ppg_rate_series=ppg_rate, cfg=cfg, capture_mode=capture_mode, phone_meta=phone_meta or None)

    tl_v1 = log.run("timeline_v1", lambda: _timeline(None), required=True)[0]
    log.run("pulse_pi", lambda: run_pulse(pi_dir, "pi", cfg, tl_v1))
    ppg_rate = log.run("ppg_rate_series", lambda: _ppg_rate_series(pi_dir, cfg))

    # 7. Timeline v2 ----------------------------------------------------------------------------------
    tl_rep = log.run("timeline_v2", lambda: _timeline(ppg_rate))
    if tl_rep is None:
        tl, sync_report = tl_v1, {"note": "timeline v2 failed; v1 kept"}
    else:
        tl, sync_report = tl_rep
    tl.capture_mode = capture_mode
    tl.save(clip_dir / "timeline.json")
    write_sync_json(sync_report, clip_dir / "sync.json")
    result["sync_grade"] = tl.sync_grade

    # 8. ECG onto the reference clock -----------------------------------------------------------------
    rpeaks_ref: np.ndarray | None = None
    if ecg_res and "ecg" in tl.maps:
        def _map_ecg():
            nonlocal rpeaks_ref
            for name in ("rpeaks.parquet", "ecg_clean.parquet"):
                p = ecg_dir / name
                if p.exists():
                    df = pd.read_parquet(p)
                    df["t_ref_s"] = tl.to_ref("ecg", df["t_ecg_s"].to_numpy(float))
                    df.to_parquet(p, index=False)
                    if name == "rpeaks.parquet":
                        rpeaks_ref = df["t_ref_s"].to_numpy(float)
            return {"method": tl.maps["ecg"].method, "uncertainty_s": tl.maps["ecg"].uncertainty_s}

        result["ecg_map"] = log.run("ecg_to_ref", _map_ecg)

    # 9. Phone chain ----------------------------------------------------------------------------------
    cam_dirs = {"pi": pi_dir}
    if "phone" in cameras and phone_mp4.exists():
        phone_dir = work.camera(study_id, clip_id, "phone")
        cam_dirs["phone"] = phone_dir
        cm = tl.maps.get("phone_video")

        def _ingest_phone():
            return ingest_phone(pp, clip_id, unit_dir, work, cfg, clockmap=cm, sqi_threshold=sqi_threshold)

        if log.run("ingest_phone", _ingest_phone):
            ft_ph = read_frame_times(phone_dir / "frame_times.parquet")
            n_ph = len(ft_ph) if n_max_frames is None else min(len(ft_ph), n_max_frames)
            t_of_ph = dict(zip(ft_ph["frame_idx"].astype(int), ft_ph["t_ref_s"].astype(float), strict=True))
            fps_ph = float(phone_inputs.get("fps") or phone_meta.get("fps_nominal") or cfg.get("phone.nominal_fps"))
            ph_full = None
            if phone_meta.get("resolution"):
                ph_full = (int(phone_meta["resolution"][1]), int(phone_meta["resolution"][0]))

            def _spatial_phone():
                return run_spatial(phone_dir, "phone", _phone_frames_factory(phone_mp4, n_ph),
                                   _phone_preview_factory(phone_mp4, t_of_ph, fps_ph, cfg, n_ph), ft_ph.iloc[:n_ph], grid_t, cfg,
                                   full_res_shape=ph_full, static_window_start_s=float(ft_pi["t_ref_s"].iloc[0]))

            log.run("spatial_phone", _spatial_phone)
            log.run("pulse_phone", lambda: run_pulse(phone_dir, "phone", cfg, tl))

    # 10. pi_proxy chain --------------------------------------------------------------------------------
    if want_proxy and pi_ing.get("pi_proxy"):
        proxy_dir = work.camera(study_id, clip_id, "pi_proxy")
        cam_dirs["pi_proxy"] = proxy_dir
        proxy_mp4 = Path(pi_ing["pi_proxy"]["path"])

        def _ingest_proxy():
            from palmppg.core.timeline import ClockMap

            return ingest_phone(pp, clip_id, unit_dir, work, cfg, clockmap=ClockMap.identity("pi_proxy"), sqi_threshold=sqi_threshold,
                                mp4_path=proxy_mp4, camera="pi_proxy")

        if log.run("ingest_pi_proxy", _ingest_proxy):
            # proxy frames are one per Pi frame: reuse the Pi frame times
            ft_px = pd.DataFrame({"frame_idx": np.arange(n_pi, dtype=np.int64), "t_ref_s": ft_pi["t_ref_s"].to_numpy(float)[:n_pi]})
            t_of_px = dict(zip(ft_px["frame_idx"].astype(int), ft_px["t_ref_s"].astype(float), strict=True))
            fps_px = float(pi_meta.get("fps_nominal") or cfg.get("pi.nominal_fps"))

            def _spatial_proxy():
                return run_spatial(proxy_dir, "pi_proxy", _phone_frames_factory(proxy_mp4, n_pi),
                                   _phone_preview_factory(proxy_mp4, t_of_px, fps_px, cfg, n_pi), ft_px, grid_t, cfg,
                                   landmark_json=lm_json,
                                   full_res_shape=(full_res[0] // 2, full_res[1] // 2) if pi_ing["pi_proxy"].get("half_res") else full_res,
                                   static_window_start_s=float(ft_pi["t_ref_s"].iloc[0]))

            log.run("spatial_pi_proxy", _spatial_proxy)
            log.run("pulse_pi_proxy", lambda: run_pulse(proxy_dir, "pi_proxy", cfg, tl))

    # 11. Beats per camera ------------------------------------------------------------------------------
    try:
        from palmppg.beats.run import run_beats
    except ImportError:  # beats module absent: recorded as a failed stage below
        run_beats = None
    for cam, d in cam_dirs.items():
        if run_beats is None:
            log.stages.append({"stage": f"beats_{cam}", "status": "failed", "error": "palmppg.beats.run not available"})
            continue
        log.run(f"beats_{cam}", lambda d=d, cam=cam: run_beats(d, cam, cfg, tl, ecg_rpeaks_t_ref_s=rpeaks_ref if tl.sync_grade == "fine" else None))

    # 12. QC finalisation and 13. features ---------------------------------------------------------------
    from palmppg.features.store import build_clip_features

    result["qc"] = {}
    for cam, d in cam_dirs.items():
        qc = log.run(f"qc_{cam}", lambda d=d, cam=cam: finalise_qc(d, cam, study_id, clip_id, cfg, _hand_summary(d), _best_sqi(d),
                                                                    tl.sync_grade, sqi_threshold, work.tables, timeline=tl))
        if qc:
            result["qc"][cam] = {"valid_clip": qc.get("valid_clip"), "reasons": qc.get("reasons"), "sqi_best": qc.get("sqi_best")}

        def _features(d=d, cam=cam):
            df = build_clip_features(study_id, clip_id, cam, clip_dir, crf, clinician, cfg, clip_meta=pi_meta)
            df.to_parquet(clip_dir / f"features_{cam}.parquet", index=False)
            return int(df.shape[1])

        log.run(f"features_{cam}", _features)

    result["stages"] = log.stages
    result["finished_utc"] = dt.datetime.now(dt.UTC).isoformat()
    result["ok"] = all(s["status"] == "ok" for s in log.stages)
    _dump(result, clip_dir / "pipeline.json")
    return result


def run_cohort(layout: StudyLayout, work: WorkLayout, cfg: Config | None = None, limit: int | None = None,
               study_ids: list[str] | None = None, cameras: tuple[str, ...] = CAMERAS, continue_on_error: bool = True,
               n_max_frames: int | None = None) -> pd.DataFrame:
    """Run every participant (or `study_ids`) and write work/tables/pipeline_runs.parquet (one row per clip)."""
    cfg = cfg or load_pipeline_config()
    parts = layout.participants()
    if study_ids:
        parts = [p for p in parts if p.study_id in set(study_ids)]
    if limit:
        parts = parts[:limit]
    rows = []
    for pp in parts:
        for clip_id in (pp.clip_ids() or ["clip1"]):
            try:
                r = run_participant(layout, pp.study_id, work, cfg, clip_id=clip_id, cameras=cameras, n_max_frames=n_max_frames)
                rows.append({"study_id": pp.study_id, "clip_id": clip_id, "ok": r["ok"], "sync_grade": r.get("sync_grade"),
                             "failed_stages": ";".join(s["stage"] for s in r["stages"] if s["status"] != "ok"),
                             "valid_pi": (r.get("qc", {}).get("pi") or {}).get("valid_clip"),
                             "valid_phone": (r.get("qc", {}).get("phone") or {}).get("valid_clip"),
                             "valid_pi_proxy": (r.get("qc", {}).get("pi_proxy") or {}).get("valid_clip")})
            except Exception as exc:
                rows.append({"study_id": pp.study_id, "clip_id": clip_id, "ok": False, "sync_grade": None,
                             "failed_stages": f"fatal: {type(exc).__name__}: {exc}", "valid_pi": None, "valid_phone": None, "valid_pi_proxy": None})
                if not continue_on_error:
                    raise
    df = pd.DataFrame(rows)
    df.to_parquet(work.tables / "pipeline_runs.parquet", index=False)
    return df


def rerun_downstream(layout: StudyLayout, study_id: str, work: WorkLayout, cfg: Config | None = None, clip_id: str = "clip1",
                     sqi_threshold: float | None = None) -> dict:
    """Re-run pulse -> beats -> QC -> features for one clip from the saved timeline and spatial outputs.

    Used after a change to pulse selection or beat analysis; ingest, ECG, sync and spatial outputs are reused. The
    timeline is not rebuilt, so the sync grade stays as computed by the full run (recorded in the result).
    """
    from palmppg.beats.run import run_beats
    from palmppg.features.store import build_clip_features
    from palmppg.pulse.run import run_pulse

    cfg = cfg or load_pipeline_config()
    if sqi_threshold is None:
        sqi_threshold = float(load_frozen_config().get("sqi.threshold"))
    pp = layout.participant(study_id)
    clip_dir = work.clip(study_id, clip_id)
    tl = Timeline.load(clip_dir / "timeline.json")
    crf = derive_file(pp.crf, cfg.section("crf"))
    clinician = _load_json(pp.clinician)
    pi_meta = json.loads(pp.pi_meta(clip_id).read_text(encoding="utf-8"))
    rp = clip_dir / "ecg" / "rpeaks.parquet"
    rpeaks_ref = pd.read_parquet(rp)["t_ref_s"].to_numpy(float) if rp.exists() else None
    log = StageLog()
    result: dict[str, Any] = {"study_id": study_id, "clip_id": clip_id, "mode": "rerun_downstream", "sync_grade": tl.sync_grade, "qc": {}}
    for cam in CAMERAS:
        d = clip_dir / cam
        if not (d / "traces.parquet").exists():
            continue
        log.run(f"pulse_{cam}", lambda d=d, cam=cam: run_pulse(d, cam, cfg, tl))
        log.run(f"beats_{cam}", lambda d=d, cam=cam: run_beats(d, cam, cfg, tl, ecg_rpeaks_t_ref_s=rpeaks_ref if tl.sync_grade == "fine" else None))
        qc = log.run(f"qc_{cam}", lambda d=d, cam=cam: finalise_qc(d, cam, study_id, clip_id, cfg, _hand_summary(d), _best_sqi(d),
                                                                    tl.sync_grade, sqi_threshold, work.tables, timeline=tl))
        if qc:
            result["qc"][cam] = {"valid_clip": qc.get("valid_clip"), "reasons": qc.get("reasons"), "sqi_best": qc.get("sqi_best")}

        def _features(cam=cam):
            df = build_clip_features(study_id, clip_id, cam, clip_dir, crf, clinician, cfg, clip_meta=pi_meta)
            df.to_parquet(clip_dir / f"features_{cam}.parquet", index=False)
            return int(df.shape[1])

        log.run(f"features_{cam}", _features)
    result["stages"] = log.stages
    result["ok"] = all(s["status"] == "ok" for s in log.stages)
    _dump(result, clip_dir / "pipeline_rerun.json")
    return result
