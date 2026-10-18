"""Shared hand-written fixtures for the feature-store tests (no tests in this module).

Every number written here is the ground truth the tests compare against after the round trip through
JSON -> build_clip_features -> parquet.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from palmppg.core.timeline import ClockMap, Timeline

SID = "SWHT-PP-003-0001"

QC_PI = {
    "camera": "pi", "study_id": SID, "clip_id": "clip1", "n_frames": 1800, "duration_s": 60.0, "fs_median": 30.0,
    "drop_pct": 0.5, "drop_flag": False, "saturation_frac": 0.001, "saturation_flag": False,
    "flicker_peaks_hz": [50.0, 100.0], "flicker_flag": True, "lighting_drift_pct": 0.8, "lighting_drift_flag": False,
    "vignetting_residual_pct": 1.2, "vignetting_flag": False, "hand_detected": True, "hand_is_left": True,
    "hand_palmar": True, "landmark_source": "mediapipe", "landmark_jitter_px": 0.7, "motion_flag": False,
    "eis_warp_px": None, "eis_flag": None, "sync_grade": "fine", "sqi_best": 0.81, "sqi_flag": False,
    "valid_clip": False, "reasons": ["flicker_flag"],
}
PULSE_SQI = {
    "POS__thenar": {"sqi": 0.81, "snr_db": 9.5, "hr_bpm": 72.4},
    "CHROM__thenar": {"sqi": 0.70, "snr_db": 7.1, "hr_bpm": 72.6},
    "2SR__central_palm": {"sqi": 0.60, "snr_db": 5.0, "hr_bpm": 71.9},
    "best": "POS__thenar",
    "fused": {"sqi": 0.85, "snr_db": 10.1, "hr_bpm": 72.3},
}
BEAT_FEATURES = {
    "hrv": {"sdnn_ms": 41.2, "rmssd_ms": 30.1, "pnn50": 0.12, "sampen": 1.4},
    "morphology": {"upstroke_time_s": 0.18, "reflection_index": 0.62, "notch_present_frac": 0.9},
    "apg": {"ageing_index": -0.3, "b_a": -0.8},
    "perfusion": {"thenar": {"G1": 1.4, "R": 0.9}, "hypothenar": {"G1": 1.1}},
    "resp": {"rate_bpm": 15.0, "band_power_ratio": 0.2},
    "n_beats": 62,
    "quality_mean": 0.77,
}
PAT = {"requires_ecg": True, "pairing_rate": 0.95, "pat_mean_ms": 210.0, "pat_sd_ms": 12.0, "ectopic_capture_frac": 1.0}
ECG_FEATURES = {"hr_bpm": 72.0, "ibi_mean_s": 0.833, "rmssd_ms": 28.0, "sampen": 1.2, "clinician_rhythm": "sinus",
                "app_rhythm_label": "Normal", "ecg_digitised": False}
STATIC_COLOUR = {"colour_space": "linear_raw", "mean_R": 0.41, "mean_G": 0.52, "mean_B": 0.33, "rg_chrom": 0.79,
                 "melanin_proxy": 0.21, "pallor_index": 0.05}
CLINICIAN = {"rhythm": "sinus", "ecg_hr": 72, "lead12_obtained": False, "adverse_event": None,
             "reader_id": "r1", "read_date": "2026-10-17"}
EMBEDDING_ROWS = {"e0": [0.1, 0.3], "e1": [0.5, 0.7], "e2": [-1.0, 1.0]}  # means: 0.2, 0.6, 0.0
# 2026-10-17T10:00:00+05:30 as wall-clock epoch nanoseconds (a morning clip in Asia/Kolkata)
START_WALL_NS = int(dt.datetime(2026, 10, 17, 10, 0, 0, tzinfo=ZoneInfo("Asia/Kolkata")).timestamp()) * 10**9


def base_crf(study_id: str = SID, stream: str = "pilot", **over) -> dict:
    crf = {
        "study_id": study_id, "initials": "AB", "age": 52, "sex": "F", "pregnant": False, "height_cm": 158,
        "weight_kg": 62, "handedness": "right", "cuff_size": "adult", "mst_band": 7, "dept": "Medicine OPD",
        "flags": ["hypertension"], "antihtn_today": "yes >2 h", "acute_30m": ["none"], "hba1c": 5.6,
        "bp1": {"sbp": 150, "dbp": 92, "hr": 76, "wall_ts": "2026-10-17T09:00:00+05:30"},
        "bp2": {"sbp": 134, "dbp": 86, "hr": 74, "wall_ts": "2026-10-17T09:06:00+05:30"},
        "bp3": {"sbp": 132, "dbp": 84, "hr": 73, "wall_ts": "2026-10-17T09:09:00+05:30"},
        "spo2": 97, "irregular_pulse": False, "recovery": "pass", "imaged_hand": "left", "operator": "op1",
        "unit_id": "unit_01", "stream": stream, "app_ver": "1.0",
    }
    crf.update(over)
    return crf


def write_json(path: Path, obj) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")
    return path


def write_timeline(clip_dir: Path, study_id: str = SID, clip_id: str = "clip1", grade: str = "fine") -> Timeline:
    tl = Timeline(study_id, clip_id, 1_000_000_000)
    tl.set_map(ClockMap.identity("pi_frames"))
    if grade == "fine":
        tl.set_map(ClockMap("ecg", 1.2, 0.0, 0.033, "artefact_lift", 2))
        tl.grade(True, True, True, True, True, "artefact_lift")
    elif grade == "coarse":
        tl.set_map(ClockMap("ecg", 1.0, 0.0, 1.0, "thumb_contact", 1))
        tl.grade(False, True, False, None, True, "thumb_contact")
    else:
        tl.grade(False, False, False, None, False, None)
    tl.add_event("clip_start", 0.0, 0.0, "sync_events.csv")
    tl.add_event("clip_end", 60.0, 0.0, "sync_events.csv")
    tl.save(clip_dir / "timeline.json")
    # sync.json in the palmppg.ingest.sync report shape; the cross-correlation peak lives only here
    ecg_map = tl.maps.get("ecg")
    write_json(clip_dir / "sync.json", {
        "grade": tl.sync_grade, "grade_detail": dict(tl.sync_detail),
        "offsets": {k: {"offset_s": m.offset_s, "drift": m.drift, "uncertainty_s": m.uncertainty_s, "method": m.method}
                    for k, m in tl.maps.items()},
        "ecg": {"xcorr": {"peak": 0.81 if grade == "fine" else None}, "map": None if ecg_map is None else {"method": ecg_map.method}},
    })
    return tl


def make_clip_artefacts(clip_dir: Path, camera: str = "pi", with_ecg: bool = True, with_embedding: bool = True,
                        grade: str = "fine") -> None:
    """Write the full set of hand-written per-clip artefacts for one camera under `clip_dir`."""
    cam = clip_dir / camera
    cam.mkdir(parents=True, exist_ok=True)
    qc = dict(QC_PI, camera=camera)
    write_json(cam / "qc.json", qc)
    write_json(cam / "pulse_sqi.json", PULSE_SQI)
    write_json(cam / "beat_features.json", BEAT_FEATURES)
    colour = dict(STATIC_COLOUR, colour_space="linear_raw" if camera == "pi" else "inverted_srgb")
    write_json(cam / "static_colour.json", colour)
    if with_ecg:
        write_json(cam / "pat.json", PAT)
        write_json(clip_dir / "ecg" / "ecg_features.json", ECG_FEATURES)
    if with_embedding:
        pd.DataFrame(EMBEDDING_ROWS).to_parquet(cam / "embeddings_physnet.parquet", index=False)
    write_timeline(clip_dir, grade=grade)


def make_study_tree(study_root: Path, participants: dict[str, str], clips: dict[str, list[str]] | None = None,
                    phone: bool = True) -> None:
    """Raw study tree with crf.json, clinician.json and pi/phone clip meta per participant.
    `participants` maps study_id -> stream; `clips` maps study_id -> clip ids (default ["clip1"])."""
    clips = clips or {}
    for sid, stream in participants.items():
        root = study_root / "participants" / sid
        write_json(root / "crf.json", base_crf(sid, stream))
        write_json(root / "clinician.json", CLINICIAN)
        for cid in clips.get(sid, ["clip1"]):
            write_json(root / "pi" / f"{cid}_meta.json", {"study_id": sid, "clip_id": cid, "start_wall_ns": START_WALL_NS,
                                                          "lux": 320.0, "capture_mode": "simultaneous"})
            if phone:
                write_json(root / "phone" / f"{cid}_meta.json", {"study_id": sid, "clip_id": cid, "app": "open_camera"})
    (study_root / "clock_sync_log.csv").write_text("date,time_utc,device,offset_ms_vs_phone,method,operator\n"
                                                   "2026-10-17,03:30:00,pi_unit_01,12,chrony,op1\n", encoding="utf-8")
    write_json(study_root / "units" / "unit_01" / "luxmap.json", {"lux_grid": [[300.0]], "rows": 1, "cols": 1})
