"""Build one reference-clock timeline per clip from every sync source (protocol section 4 in full).

``build_timeline`` takes the Pi frame times, the marker log, the LED block traces (Pi, phone), the phone
PTS and audio, the thumb block trace, the ECG anchors and rate series, and returns a
``palmppg.core.timeline.Timeline`` with clock maps for ``pi_frames`` (identity, D-001), ``phone_video``,
``phone_audio``, ``ecg`` and ``wall`` (Pi wall-clock epoch seconds -> reference, audit only), the events ``clip_start``/``clip_end``/``p1_onset``/``p2_onset``/
``thumb_contact``/``thumb_lift``/``ecg_artefact``, the analysis window (D-002: ends at the P2 onset), the
sync grade (section 4.4, ``Timeline.grade``), and a ``sync.json``-style report dict.

Capture modes (section 2): ``simultaneous`` fits the phone to the Pi through the LED edges (and the beeps);
``sequential`` gives the phone its own coarse map from the file wall clock plus the start beep only
(method ``audio_beep``, no drift) and the phone is never frame-paired to the Pi.

Nothing here is aligned on wall clock or frame index; wall clock is an audit cross-check only.
"""
from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from palmppg.core.config import Config
from palmppg.core.timeline import ClockMap, Timeline, resample_to_grid, uniform_grid
from palmppg.core.tracks import REGISTRY
from palmppg.ingest import anchors as _anchors
from palmppg.ingest import audio as _audio
from palmppg.ingest import led as _led
from palmppg.ingest import xcorr as _xcorr
from palmppg.ingest.sync_events import (
    clip_bounds_s,
    expected_edges,
    gpio_ok_summary,
    pattern_onsets_from_log,
    pattern_specs,
)

_FEATURES: tuple[tuple[str, dict], ...] = (
    ("sync__grade", {"description": "sync quality grade fine|coarse|none (section 4.4)", "requires_ecg": True}),
    ("sync__capture_mode", {"description": "simultaneous|sequential"}),
    ("sync__p1_found", {"description": "P1 detected in the Pi LED block"}),
    ("sync__p2_found", {"description": "P2 detected in the Pi LED block"}),
    ("sync__pi_video_residual_max_frames", {"description": "Pi video vs log LED edge residual", "units": "frames"}),
    ("sync__phone_video_offset_s", {"description": "phone video -> reference offset", "units": "s"}),
    ("sync__phone_video_drift", {"description": "phone video clock drift (fraction)"}),
    ("sync__phone_video_residual_max_frames", {"description": "phone LED edge residual", "units": "frames"}),
    ("sync__phone_video_accepted", {"description": "phone LED fit accepted (D-003)"}),
    ("sync__phone_audio_offset_s", {"description": "phone audio (video time) -> reference offset", "units": "s"}),
    ("sync__phone_audio_residual_max_ms", {"description": "beep edge residual", "units": "ms"}),
    ("sync__phone_frame_pairing_allowed", {"description": "phone frames may be paired to Pi frames"}),
    ("sync__ecg_map_method", {"description": "ECG clock map method", "requires_ecg": True}),
    ("sync__ecg_offset_s", {"description": "ECG native -> reference offset", "units": "s", "requires_ecg": True}),
    ("sync__ecg_uncertainty_s", {"description": "ECG map stated uncertainty", "units": "s", "requires_ecg": True}),
    ("sync__thumb_contact_t_ref_s", {"description": "thumb-contact frame time", "units": "s"}),
    ("sync__thumb_lift_t_ref_s", {"description": "thumb-lift frame time near P2", "units": "s"}),
    ("sync__wall_vs_thumb_disagreement_s", {"description": "wall-clock vs thumb anchor", "units": "s", "requires_ecg": True}),
    ("sync__wall_vs_thumb_flag", {"description": "disagreement above clock.wall_vs_meta_disagreement_s", "requires_ecg": True}),
    ("sync__xcorr_lag_s", {"description": "HR cross-correlation lag (includes mean PAT)", "units": "s", "requires_ecg": True}),
    ("sync__xcorr_peak", {"description": "HR cross-correlation peak", "requires_ecg": True}),
    ("sync__xcorr_margin", {"description": "peak minus second-best peak", "requires_ecg": True}),
    ("sync__xcorr_accepted", {"description": "cross-correlation acceptance rule", "requires_ecg": True}),
    ("sync__analysis_window_start_s", {"description": "analysis window start", "units": "s"}),
    ("sync__analysis_window_end_s", {"description": "analysis window end (P2 onset, D-002)", "units": "s"}),
    ("sync__gpio_all_ok", {"description": "marker GPIO self-check passed for every edge"}),
)


def register_features() -> list[str]:
    """Register every sync column with the track registry (idempotent). ECG-derived ones are
    ``requires_ecg=True``; all are ``camera='any'`` clip-level QC/sync fields (CONTRACTS section 5)."""
    names = []
    for name, kw in _FEATURES:
        kw = dict(kw)
        REGISTRY.add(name, group="sync", camera="any", requires_ecg=bool(kw.pop("requires_ecg", False)),
                     requires_raw=False, tags=("qc", "sync"), **kw)
        names.append(name)
    return names


# --------------------------------------------------------------------------- small helpers
def _cfg(cfg: Config, key: str, default: Any) -> Any:
    return cfg.get(key, default) if cfg is not None else default


def _trace(tr) -> tuple[np.ndarray, np.ndarray] | None:
    if tr is None:
        return None
    if isinstance(tr, pd.DataFrame):
        return tr["frame_idx"].to_numpy(dtype=np.int64), tr["intensity"].to_numpy(dtype=float)
    idx, y = tr[0], tr[1]
    return np.asarray(idx, dtype=np.int64), np.asarray(y, dtype=float)


def _times_for_frames(frame_idx: np.ndarray, idx_to_t: Mapping[int, float]) -> np.ndarray:
    return np.array([idx_to_t.get(int(i), np.nan) for i in frame_idx], dtype=float)


def _phone_pts_lookup(phone_pts_s) -> Mapping[int, float]:
    if phone_pts_s is None:
        return {}
    if isinstance(phone_pts_s, pd.DataFrame):
        return {int(i): float(t) for i, t in zip(phone_pts_s["frame_idx"], phone_pts_s["pts_s"])}
    if isinstance(phone_pts_s, Mapping):
        return {int(k): float(v) for k, v in phone_pts_s.items()}
    arr = np.asarray(phone_pts_s, dtype=float)
    return {i: float(v) for i, v in enumerate(arr)}


def _audio_tuple(phone_audio) -> tuple[float, np.ndarray, float] | None:
    if phone_audio is None:
        return None
    if isinstance(phone_audio, Mapping):
        return float(phone_audio["fs"]), np.asarray(phone_audio["x"], dtype=float), float(phone_audio.get("start_offset_s", 0.0))
    fs, x = phone_audio[0], phone_audio[1]
    off = float(phone_audio[2]) if len(phone_audio) > 2 else 0.0
    return float(fs), np.asarray(x, dtype=float), off


def _rate_pair(rs) -> tuple[np.ndarray, np.ndarray] | None:
    if rs is None:
        return None
    if isinstance(rs, pd.DataFrame):
        tcol = "t_ref_s" if "t_ref_s" in rs.columns else ("t_ecg_s" if "t_ecg_s" in rs.columns else "t_s")
        return rs[tcol].to_numpy(dtype=float), rs["rate_bpm"].to_numpy(dtype=float)
    return np.asarray(rs[0], dtype=float), np.asarray(rs[1], dtype=float)


def _det_summary(det: dict | None) -> dict | None:
    if det is None:
        return None
    return {k: v for k, v in det.items() if k != "edges"} | {"n_edges": len(det["edges"]),
                                                             "edges": [{"t_s": e["t_s"], "kind": e["kind"]} for e in det["edges"]]}


def _map_dict(cm: ClockMap | None) -> dict | None:
    return None if cm is None else asdict(cm)


# --------------------------------------------------------------------------- the builder
def build_timeline(study_id: str, clip_id: str, pi_meta: Mapping, pts_df: pd.DataFrame, sync_events_df: pd.DataFrame | None,
                   led_trace_pi, led_trace_phone=None, phone_pts_s=None, phone_audio=None, thumb_trace_pi=None,
                   ecg: Mapping | None = None, ppg_rate_series=None, cfg: Config | None = None,
                   capture_mode: str | None = None, phone_meta: Mapping | None = None,
                   phone_sync_events_df: pd.DataFrame | None = None) -> tuple[Timeline, dict]:
    """Assemble the per-clip Timeline and sync report from every sync source (protocol section 4).

    Inputs (shapes per CONTRACTS):
      * ``pi_meta``: clip meta (start/stop_mono_ns, fps_nominal, exposure_us, start_wall_ns, unit_id ...).
      * ``pts_df``: ``frame_idx, sensor_ts_ns`` for the Pi frames; ``t0_ref_ns`` = first row.
      * ``sync_events_df``: ``read_sync_events`` output (may be None: then the Pi video detections stand in
        for the log when fitting the phone).
      * ``led_trace_pi``/``led_trace_phone``/``thumb_trace_pi``: ``(frame_idx, intensity)`` block traces.
      * ``phone_pts_s``: PTS seconds per phone frame (array indexed by frame_idx, dict, or DataFrame
        ``frame_idx, pts_s``). ``phone_audio``: ``(fs, x[, audio_start_offset_s])`` or dict.
      * ``ecg``: ``{artefact_t_ecg_s | None, rate_series (t_ecg_s, bpm) | rpeak_times_s | None,
        kardia_meta | None, day_offsets (device -> offset_ms_vs_phone) | None}``.
      * ``ppg_rate_series``: ``(t_ref_s, bpm)`` from the best-SQI palm signal, or None.
      * ``capture_mode``: ``simultaneous`` | ``sequential`` (default ``study.capture_mode``).
      * ``phone_meta``: phone clip meta (``start_wall_ns``, ``exposure_ns``, ``fps_nominal``); needed for the
        wall-clock part of the sequential phone map, and ``exposure_ns`` centres the LED edges on the exposure
        (without it the phone LED edges carry a bias of half the exposure, below half a frame period). ``phone_sync_events_df``: the marker log of the separate
        phone scan in sequential mode (defaults to ``sync_events_df``).

    Returns ``(Timeline, report)``. The report is JSON-serialisable (``write_sync_json``) and carries every
    offset, residual and flag. ECG-dependent and pulse analyses end at the P2 onset (D-002) through the
    Timeline's analysis window.
    """
    if cfg is None:
        from palmppg.core.config import load_pipeline_config
        cfg = load_pipeline_config()
    capture_mode = str(capture_mode or cfg.get("study.capture_mode", "simultaneous"))
    ecg = dict(ecg or {})
    flags: list[str] = []

    fps = float(pi_meta.get("fps_nominal") or cfg.get("pi.nominal_fps", 30))
    period = 1.0 / fps
    tol_frames = float(cfg.get("sync.edge_tolerance_frames"))
    min_edges = int(cfg.get("sync.min_edges"))
    specs = pattern_specs(cfg)
    led_kw = {
        "min_contrast": _cfg(cfg, "sync.led.min_contrast", _led.DEFAULTS["sync.led.min_contrast"]),
        "min_snr": _cfg(cfg, "sync.led.min_snr", _led.DEFAULTS["sync.led.min_snr"]),
        "baseline_window_s": _cfg(cfg, "sync.led.baseline_window_s", _led.DEFAULTS["sync.led.baseline_window_s"]),
        "duration_tol_frames": _cfg(cfg, "sync.led.duration_tol_frames", _led.DEFAULTS["sync.led.duration_tol_frames"]),
        "duration_tol_frac": _cfg(cfg, "sync.led.duration_tol_frac", _led.DEFAULTS["sync.led.duration_tol_frac"]),
    }

    # ---------------------------------------------------------------- reference clock and Pi frames
    pts = pts_df.sort_values("frame_idx").reset_index(drop=True)
    t0_ref_ns = int(pts["sensor_ts_ns"].iloc[0])
    tl = Timeline(study_id, clip_id, t0_ref_ns, capture_mode=capture_mode)
    tl.set_map(ClockMap.identity("pi_frames"))
    pi_t = (pts["sensor_ts_ns"].to_numpy(dtype=np.int64) - np.int64(t0_ref_ns)) / 1e9
    pi_idx_to_t = {int(i): float(t) for i, t in zip(pts["frame_idx"].to_numpy(), pi_t)}
    pi_exposure_s = float(pi_meta.get("exposure_us") or 0.0) / 1e6

    clip_start, clip_end = clip_bounds_s(pi_meta, t0_ref_ns)
    tl.add_event("clip_start", clip_start, 0.0, "pi_meta")
    tl.add_event("clip_end", clip_end, 0.0, "pi_meta")
    if pi_meta.get("start_wall_ns") is not None:
        # Pi wall-clock seconds (epoch) -> t_ref_s, for audit only (section 4.1; never for alignment)
        wall_minus_mono_ns = int(pi_meta["start_wall_ns"]) - int(pi_meta["start_mono_ns"])
        tl.set_map(ClockMap("wall", -(wall_minus_mono_ns + t0_ref_ns) / 1e9, 0.0,
                            float(cfg.get("sync.coarse_anchor_uncertainty_s")), "wall_clock", 1,
                            notes="Pi wall clock (epoch seconds) -> reference; audit only"))

    # ---------------------------------------------------------------- marker log
    log_edges: dict[str, list] = {}
    log_summary: dict = {"present": False}
    if sync_events_df is not None and len(sync_events_df):
        log_edges = expected_edges(sync_events_df, t0_ref_ns)
        gp = gpio_ok_summary(sync_events_df)
        log_summary = {"present": True, "gpio": gp, "onsets_s": pattern_onsets_from_log(sync_events_df, t0_ref_ns)}
        if not gp["all_ok"]:
            flags.append("gpio_self_check_failed")
        for pat, t_on in log_summary["onsets_s"].items():
            tl.add_event(f"{pat.lower()}_onset", t_on, 0.001, "sync_events.csv")
    else:
        flags.append("sync_log_missing")

    # ---------------------------------------------------------------- Pi video LED
    pi_video: dict = {"present": False, "p1": None, "p2": None, "fit": None}
    pi_det: dict[str, dict] = {}
    tr = _trace(led_trace_pi)
    if tr is not None:
        idx, y = tr
        t = _times_for_frames(idx, pi_idx_to_t)
        pi_video["present"] = True
        for pat, spec in specs.items():
            det = _led.detect_pattern(t, y, spec, fps, exposure_s=pi_exposure_s, frame_idx=idx, **led_kw)
            pi_video[pat.lower()] = _det_summary(det)
            if det is not None:
                pi_det[pat] = det
                tl.add_event(f"{pat.lower()}_onset", det["onset_s"], period, "pi_video", frame_idx=det["edges"][0]["frame_idx"])
        if log_edges and pi_det:
            _, rep = _led.fit_led_offset(pi_det, log_edges, "pi_video", fps, tol_frames, min_edges)
            pi_video["fit"] = rep
            if not rep["accepted"]:
                flags.append("pi_video_vs_log_rejected")
    else:
        flags.append("pi_led_trace_missing")
    p1_found = "P1" in pi_det
    p2_found = "P2" in pi_det
    # edges on the reference clock that the phone is fitted against: the log, else the Pi video itself
    ref_edges = log_edges if log_edges else {k: v["edges"] for k, v in pi_det.items()}

    # ---------------------------------------------------------------- phone
    phone: dict = {"capture_mode": capture_mode, "video": None, "audio": None, "frame_pairing_allowed": False}
    phone_fps = float((phone_meta or {}).get("fps_nominal") or cfg.get("phone.nominal_fps", 30))
    phone_exposure_s = float((phone_meta or {}).get("exposure_ns") or 0.0) / 1e9
    aud = _audio_tuple(phone_audio)
    audio_res: dict[str, dict | None] = {}
    if aud is not None:
        fs_a, x_a, a_off = aud
        audio_res = _audio.detect_beeps(
            x_a, fs_a, float(cfg.get("sync.audio.tone_hz")), float(cfg.get("sync.audio.bandwidth_hz")), specs,
            min_snr_db=_cfg(cfg, "sync.audio.min_snr_db", _audio.DEFAULTS["sync.audio.min_snr_db"]),
            duration_tol_s=_cfg(cfg, "sync.audio.duration_tol_s", _audio.DEFAULTS["sync.audio.duration_tol_s"]),
            duration_tol_frac=_cfg(cfg, "sync.audio.duration_tol_frac", _audio.DEFAULTS["sync.audio.duration_tol_frac"]),
            audio_start_offset_s=a_off)
        phone["audio"] = {"present": True, "audio_start_offset_s": a_off, "fs": fs_a,
                          "p1": _det_summary(audio_res.get("P1")), "p2": _det_summary(audio_res.get("P2")), "fit": None}
    beep_unc = _audio.beep_precision_s(float(cfg.get("sync.audio.onset_tolerance_ms")), float(cfg.get("sync.audio.bandwidth_hz")))

    if capture_mode == "sequential":
        _sequential_phone(tl, phone, audio_res, phone_sync_events_df if phone_sync_events_df is not None else sync_events_df,
                          t0_ref_ns, pi_meta, phone_meta, ecg.get("day_offsets"), beep_unc, cfg, flags)
    else:
        phone["frame_pairing_allowed"] = False
        ptr = _trace(led_trace_phone)
        pts_lookup = _phone_pts_lookup(phone_pts_s)
        if ptr is not None and pts_lookup:
            idx, y = ptr
            t = _times_for_frames(idx, pts_lookup)
            det_phone: dict[str, dict] = {}
            vid: dict = {"present": True, "p1": None, "p2": None, "fit": None}
            for pat, spec in specs.items():
                det = _led.detect_pattern(t, y, spec, phone_fps, exposure_s=phone_exposure_s, frame_idx=idx, **led_kw)
                vid[pat.lower()] = _det_summary(det)
                if det is not None:
                    det_phone[pat] = det
            if det_phone and ref_edges:
                cm, rep = _led.fit_led_offset(det_phone, ref_edges, "phone_video", phone_fps, tol_frames, min_edges)
                vid["fit"] = rep
                if cm is not None:
                    tl.set_map(cm)
                    phone["frame_pairing_allowed"] = bool(rep["accepted"])
                if not rep["accepted"]:
                    flags.append("phone_video_led_fit_rejected")
            else:
                flags.append("phone_video_led_not_detected")
            phone["video"] = vid
        elif ptr is None:
            phone["video"] = {"present": False}
        else:
            phone["video"] = {"present": True, "fit": None}
            flags.append("phone_pts_missing")
        if audio_res and ref_edges:
            det_edges = _audio.beep_edges(audio_res)
            if det_edges:
                cm, rep = _led.fit_led_offset(det_edges, ref_edges, "phone_audio", phone_fps, tol_frames, min_edges,
                                              method="audio_beep")
                phone["audio"]["fit"] = rep
                if cm is not None:
                    cm.uncertainty_s = max(cm.uncertainty_s, beep_unc)
                    tl.set_map(cm)
                    if "phone_video" not in tl.maps:
                        # audio and video share the container clock: the beep-anchored map stands in for video
                        cm_v = ClockMap("phone_video", cm.offset_s, cm.drift, cm.uncertainty_s, "audio_beep", cm.n_anchors,
                                        cm.residual_rms_s, cm.residual_max_s, "from beeps; LED not usable on the phone")
                        tl.set_map(cm_v)
                        phone["frame_pairing_allowed"] = bool(rep["accepted"])
                if not rep["accepted"]:
                    flags.append("phone_audio_beep_fit_rejected")
            else:
                flags.append("phone_audio_beeps_not_detected")
        elif aud is not None and not any(audio_res.values()):
            flags.append("phone_audio_beeps_not_detected")

    # ---------------------------------------------------------------- ECG anchors
    ecg_rep: dict = {"thumb_contact": None, "wall_clock": None, "anchor_comparison": None, "thumb_lift": None,
                     "fine": None, "map": None, "coverage_ref_s": None, "xcorr": None}
    coarse_unc = float(cfg.get("sync.coarse_anchor_uncertainty_s"))
    fine_unc = float(cfg.get("sync.fine_anchor_uncertainty_s"))
    k_mad = float(cfg.get("sync.artefact.k_mad"))
    p2_ev = tl.event("p2_onset")
    thumb = _trace(thumb_trace_pi)
    thumb_t = thumb_y = thumb_idx = None
    coarse_map: ClockMap | None = None
    if thumb is not None:
        thumb_idx, thumb_y = thumb
        thumb_t = _times_for_frames(thumb_idx, pi_idx_to_t)
        lift_win = _cfg(cfg, "sync.lift.search_s", _anchors.DEFAULTS["sync.lift.search_s"])
        hi = (p2_ev.t_ref_s + float(lift_win[0])) if p2_ev is not None else clip_end
        contact = _anchors.thumb_contact_frame(
            thumb_t, thumb_y, frame_idx=thumb_idx, uncertainty_s=coarse_unc,
            min_segment_s=_cfg(cfg, "sync.thumb.min_segment_s", _anchors.DEFAULTS["sync.thumb.min_segment_s"]),
            min_r2=_cfg(cfg, "sync.thumb.min_r2", _anchors.DEFAULTS["sync.thumb.min_r2"]),
            min_snr=_cfg(cfg, "sync.thumb.min_snr", _anchors.DEFAULTS["sync.thumb.min_snr"]),
            search_window=(clip_start, hi))
        ecg_rep["thumb_contact"] = contact
        if contact["found"]:
            tl.add_event("thumb_contact", contact["t_s"], coarse_unc, "pi_video", frame_idx=contact["frame_idx"],
                         confidence=contact["confidence"])
            coarse_map = _anchors.coarse_ecg_map(contact["t_s"], 0.0, coarse_unc)
        else:
            flags.append("thumb_contact_not_found")
    else:
        flags.append("thumb_trace_missing")

    kardia_meta = ecg.get("kardia_meta") or {}
    wall_map: ClockMap | None = None
    if kardia_meta.get("start_wall_ts") is not None and pi_meta.get("start_wall_ns") is not None:
        try:
            wall_map = _anchors.wall_clock_ecg_map(
                kardia_meta["start_wall_ts"], pi_meta, t0_ref_ns, ecg.get("day_offsets"), uncertainty_s=coarse_unc,
                naive_tz_offset_h=_cfg(cfg, "clock.kardia_tz_offset_h", _anchors.DEFAULTS["clock.kardia_tz_offset_h"]))
            ecg_rep["wall_clock"] = _map_dict(wall_map)
        except (KeyError, ValueError) as exc:
            flags.append(f"wall_clock_unusable:{exc}")
    cmp = _anchors.compare_anchors(coarse_map, wall_map, float(cfg.get("clock.wall_vs_meta_disagreement_s")))
    ecg_rep["anchor_comparison"] = cmp
    if cmp["flag"]:
        flags.append("wall_vs_thumb_disagreement")

    ecg_map: ClockMap | None = coarse_map
    if ecg_map is None and wall_map is not None:
        ecg_map = wall_map
        flags.append("ecg_map_from_wall_clock_only")
    coarse_anchor_found = coarse_map is not None

    # fine anchor
    fine_found = False
    lift = None
    if thumb is not None and p2_ev is not None:
        lift_win = _cfg(cfg, "sync.lift.search_s", _anchors.DEFAULTS["sync.lift.search_s"])
        lift = _anchors.thumb_lift_event(
            thumb_t, thumb_y, (p2_ev.t_ref_s + float(lift_win[0]), p2_ev.t_ref_s + float(lift_win[1])),
            frame_idx=thumb_idx, k_mad=k_mad,
            median_frames=_cfg(cfg, "sync.lift.median_frames", _anchors.DEFAULTS["sync.lift.median_frames"]),
            first_fraction=_cfg(cfg, "sync.lift.first_fraction", _anchors.DEFAULTS["sync.lift.first_fraction"]))
        ecg_rep["thumb_lift"] = lift
        if lift["found"]:
            tl.add_event("thumb_lift", lift["t_s"], period, "pi_video", frame_idx=lift["frame_idx"], z=lift["z"])
        else:
            flags.append("thumb_lift_not_found")
    art = ecg.get("artefact_t_ecg_s")
    if art is not None and lift is not None and lift["found"]:
        fine = _anchors.fine_ecg_map(lift["t_s"], float(art), fine_unc)
        if ecg_map is not None and abs(fine.offset_s - ecg_map.offset_s) > max(3.0 * ecg_map.uncertainty_s, coarse_unc) + 0.5:
            flags.append("fine_vs_coarse_anchor_disagreement")
            ecg_rep["fine"] = _map_dict(fine) | {"rejected": True,
                                                  "reason": f"offset {fine.offset_s:.3f} s vs coarse {ecg_map.offset_s:.3f} s"}
        else:
            ecg_map = fine
            fine_found = True
            ecg_rep["fine"] = _map_dict(fine)
            tl.add_event("ecg_artefact", fine.to_ref(float(art)), fine_unc, "ecg", t_ecg_s=float(art))
    elif art is None:
        flags.append("ecg_artefact_missing")

    # ---------------------------------------------------------------- analysis window (D-002)
    static_s = float(cfg.get("window.static_colour_s"))
    tail_s = float(cfg.get("window.tail_exclusion_s"))
    window = tl.derive_analysis_window(static_s, tail_s, clip_start_s=clip_start, clip_end_s=clip_end)

    # ---------------------------------------------------------------- HR cross-correlation
    xc = None
    xcorr_agree: bool | None = None
    agree_s = float(cfg.get("sync.xcorr.agree_s"))
    rate_fs = float(cfg.get("sync.xcorr.rate_fs"))
    ecg_rs = _rate_pair(ecg.get("rate_series"))
    if ecg_rs is None and ecg.get("rpeak_times_s") is not None:
        ecg_rs = _xcorr.rate_series_from_events(np.asarray(ecg["rpeak_times_s"], dtype=float), rate_fs)
    ppg_rs = _rate_pair(ppg_rate_series)
    if ecg_map is not None and ecg_rs is not None and ppg_rs is not None:
        t_e = ecg_map.to_ref(ecg_rs[0])
        lo = max(window.start_s, float(np.nanmin(t_e)), float(np.nanmin(ppg_rs[0])))
        hi = min(window.end_s, float(np.nanmax(t_e)), float(np.nanmax(ppg_rs[0])))
        if hi - lo > 0:
            grid = uniform_grid(lo, hi, rate_fs)
            gap = _cfg(cfg, "sync.xcorr.max_gap_s", _xcorr.DEFAULTS["sync.xcorr.max_gap_s"])
            a = resample_to_grid(t_e, ecg_rs[1], grid, max_gap_s=gap)
            b = resample_to_grid(ppg_rs[0], ppg_rs[1], grid, max_gap_s=gap)
            xc = _xcorr.xcorr_lag(
                a, b, rate_fs, float(cfg.get("sync.xcorr.lag_s")), float(cfg.get("sync.xcorr.min_peak")),
                float(cfg.get("sync.xcorr.min_margin")),
                second_peak_exclusion_s=_cfg(cfg, "sync.xcorr.second_peak_exclusion_s", _xcorr.DEFAULTS["sync.xcorr.second_peak_exclusion_s"]),
                min_overlap_s=_cfg(cfg, "sync.xcorr.min_overlap_s", _xcorr.DEFAULTS["sync.xcorr.min_overlap_s"]))
            xc = {k: v for k, v in xc.items() if k not in ("lags_s", "corr")} | {"grid_s": [lo, hi], "map_method": ecg_map.method}
            xcorr_agree = bool(xc["accepted"] and _xcorr.agree_with_fine(xc["lag_s"], agree_s))
            if not xc["accepted"]:
                flags.append("xcorr_not_accepted")
            elif not xcorr_agree:
                flags.append("xcorr_lag_outside_agree_s")
            if xc["accepted"] and not fine_found and ecg_map.method in ("thumb_contact", "wall_clock"):
                # refine the coarse anchor by the lag (includes mean PAT: stays coarse, D-004)
                ecg_map = ClockMap("ecg", ecg_map.offset_s + float(xc["lag_s"]), 0.0, agree_s, "xcorr_hr", 1,
                                   notes=f"{ecg_map.method} anchor shifted by HR cross-correlation lag {xc['lag_s']:+.3f} s")
    ecg_rep["xcorr"] = xc

    if ecg_map is not None:
        tl.set_map(ecg_map)
        ecg_rep["map"] = _map_dict(ecg_map)
        dur = kardia_meta.get("duration_s") or cfg.get("study.kardia_duration_s", None)
        if dur is not None:
            ecg_rep["coverage_ref_s"] = [float(ecg_map.offset_s), float(ecg_map.offset_s + float(dur))]
    else:
        flags.append("no_ecg_anchor")

    # ---------------------------------------------------------------- grade (section 4.4, D-004)
    grade = tl.grade(fine_found, p1_found, p2_found, xcorr_agree, coarse_anchor_found,
                     ecg_map.method if ecg_map is not None else None, xcorr_tolerance_s=agree_s)

    report = {
        "study_id": study_id, "clip_id": clip_id, "capture_mode": capture_mode, "t0_ref_ns": t0_ref_ns, "fps": fps,
        "clip": {"start_s": clip_start, "end_s": clip_end, "duration_s": clip_end - clip_start, "n_pi_frames": len(pts)},
        "log": log_summary, "pi_video": pi_video, "phone": phone, "ecg": ecg_rep,
        "analysis_window": asdict(window), "grade": grade, "grade_detail": dict(tl.sync_detail),
        "offsets": {k: {"offset_s": m.offset_s, "drift": m.drift, "uncertainty_s": m.uncertainty_s, "method": m.method}
                    for k, m in tl.maps.items()},
        "residuals": {
            "pi_video_max_frames": (pi_video.get("fit") or {}).get("residual_max_frames"),
            "phone_video_max_frames": ((phone.get("video") or {}).get("fit") or {}).get("residual_max_frames"),
            "phone_audio_max_ms": _ms(((phone.get("audio") or {}).get("fit") or {}).get("residual_max_s")),
        },
        "flags": flags,
    }
    return tl, _jsonable(report)


def _sequential_phone(tl: Timeline, phone: dict, audio_res: Mapping[str, dict | None], events_df, t0_ref_ns: int,
                      pi_meta: Mapping, phone_meta: Mapping | None, day_offsets, beep_unc: float, cfg: Config,
                      flags: list[str]) -> None:
    """Sequential capture (section 2): phone map from the file wall clock plus the start beep only.

    Wall clock: ``phone_meta.start_wall_ns`` (phone clock) -> Pi wall via the day offsets -> Pi monotonic ->
    ``t_ref_s``. Start beep: the P1 beep in the phone audio against the P1 onset logged for the phone scan
    gives the offset with method ``audio_beep`` (uncertainty = beep precision, no drift). The phone is never
    frame-paired to the Pi in this mode.
    """
    phone["frame_pairing_allowed"] = False
    phone["video"] = {"present": False, "note": "sequential mode: no LED pairing; participant-level comparison only"}
    wall_cm: ClockMap | None = None
    pm = phone_meta or {}
    if pm.get("start_wall_ns") is not None and pi_meta.get("start_wall_ns") is not None:
        offs = dict(day_offsets or {})
        pi_dev = pi_meta.get("unit_id") or "pi"
        off_pi = float(offs.get(pi_dev, 0.0))
        pi_wall_ns = int(pm["start_wall_ns"]) + round(off_pi * 1e6)   # phone clock is the hotspot reference
        mono_ns = pi_wall_ns - (int(pi_meta["start_wall_ns"]) - int(pi_meta["start_mono_ns"]))
        wall_cm = ClockMap("phone_video", (mono_ns - int(t0_ref_ns)) / 1e9, 0.0,
                           float(cfg.get("sync.coarse_anchor_uncertainty_s")), "wall_clock", 1,
                           notes="sequential: phone file wall clock via day offsets")
        phone["wall_clock"] = asdict(wall_cm)
    else:
        flags.append("phone_wall_clock_missing")
    beep_cm: ClockMap | None = None
    p1 = audio_res.get("P1") if audio_res else None
    if p1 is not None and events_df is not None and len(events_df):
        onsets = pattern_onsets_from_log(events_df, t0_ref_ns)
        if "P1" in onsets:
            beep_cm = ClockMap("phone_video", float(onsets["P1"]) - float(p1["onset_s"]), 0.0, float(beep_unc),
                               "audio_beep", 1, notes="sequential: start beep vs logged P1 onset; no drift")
            if wall_cm is not None:
                d = abs(beep_cm.offset_s - wall_cm.offset_s)
                phone["beep_vs_wall_disagreement_s"] = d
                if d > float(cfg.get("clock.wall_vs_meta_disagreement_s")):
                    flags.append("phone_beep_vs_wall_disagreement")
    else:
        flags.append("phone_start_beep_not_detected")
    chosen = beep_cm or wall_cm
    if chosen is None:
        flags.append("phone_unanchored")
        return
    tl.set_map(chosen)
    tl.set_map(ClockMap("phone_audio", chosen.offset_s, 0.0, chosen.uncertainty_s, chosen.method, chosen.n_anchors, notes=chosen.notes))
    if phone["audio"] is not None:
        phone["audio"]["fit"] = {"stream": "phone_audio", "method": chosen.method, "offset_s": chosen.offset_s,
                                 "uncertainty_s": chosen.uncertainty_s, "n_matched": 1 if beep_cm else 0,
                                 "accepted": beep_cm is not None, "drift": 0.0}


# --------------------------------------------------------------------------- outputs
def _ms(seconds: float | None) -> float | None:
    return None if seconds is None else 1e3 * float(seconds)


def _jsonable(o):
    if isinstance(o, Mapping):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if np.isnan(o) else float(o)
    if isinstance(o, float) and np.isnan(o):
        return None
    if isinstance(o, np.ndarray):
        return _jsonable(o.tolist())
    return o


def write_sync_json(report: Mapping, path: str | Path) -> Path:
    """Write the sync report (``work/<study_id>/<clip_id>/sync.json``)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(_jsonable(report), indent=2), encoding="utf-8")
    return p


def sync_feature_row(report: Mapping) -> dict:
    """Flatten a sync report into the registered ``sync__*`` columns (one row per clip)."""
    register_features()
    g = lambda *ks: _dig(report, ks)
    return {
        "sync__grade": report.get("grade"),
        "sync__capture_mode": report.get("capture_mode"),
        "sync__p1_found": g("grade_detail", "p1_found"),
        "sync__p2_found": g("grade_detail", "p2_found"),
        "sync__pi_video_residual_max_frames": g("residuals", "pi_video_max_frames"),
        "sync__phone_video_offset_s": g("offsets", "phone_video", "offset_s"),
        "sync__phone_video_drift": g("offsets", "phone_video", "drift"),
        "sync__phone_video_residual_max_frames": g("residuals", "phone_video_max_frames"),
        "sync__phone_video_accepted": g("phone", "video", "fit", "accepted"),
        "sync__phone_audio_offset_s": g("offsets", "phone_audio", "offset_s"),
        "sync__phone_audio_residual_max_ms": g("residuals", "phone_audio_max_ms"),
        "sync__phone_frame_pairing_allowed": g("phone", "frame_pairing_allowed"),
        "sync__ecg_map_method": g("offsets", "ecg", "method"),
        "sync__ecg_offset_s": g("offsets", "ecg", "offset_s"),
        "sync__ecg_uncertainty_s": g("offsets", "ecg", "uncertainty_s"),
        "sync__thumb_contact_t_ref_s": g("ecg", "thumb_contact", "t_s"),
        "sync__thumb_lift_t_ref_s": g("ecg", "thumb_lift", "t_s"),
        "sync__wall_vs_thumb_disagreement_s": g("ecg", "anchor_comparison", "disagreement_s"),
        "sync__wall_vs_thumb_flag": g("ecg", "anchor_comparison", "flag"),
        "sync__xcorr_lag_s": g("ecg", "xcorr", "lag_s"),
        "sync__xcorr_peak": g("ecg", "xcorr", "peak"),
        "sync__xcorr_margin": g("ecg", "xcorr", "margin"),
        "sync__xcorr_accepted": g("ecg", "xcorr", "accepted"),
        "sync__analysis_window_start_s": g("analysis_window", "start_s"),
        "sync__analysis_window_end_s": g("analysis_window", "end_s"),
        "sync__gpio_all_ok": g("log", "gpio", "all_ok"),
    }


def _dig(d: Any, keys: Sequence[str]) -> Any:
    for k in keys:
        if not isinstance(d, Mapping) or k not in d or d[k] is None:
            return None
        d = d[k]
    return d
