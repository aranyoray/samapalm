"""Build a synthetic study_root (protocol section 3 layout) with known truth for every participant.

Protocol sections served: 3 (clock_sync_log.csv, units/unit_01 calibration files, participants/<id>/ with
crf.json, clinician.json, pi/, phone/, ecg/), 4.1 (daily clock offsets of the Pi and the Kardia tablet
against the phone), 8 / 12 run-order step 1 (synthetic data the whole pipeline is exercised on first).

Streams frames: every clip is generated and written frame by frame (bayer_video, phone_video); nothing holds
a clip in memory. The default profile follows cfg `synth.*` (384 x 216, 60 s; DECISIONS D-012); `small=True`
uses 192 x 108, 20 s for tests. CLI: `python -m palmppg.synth.cohort --root ... --n 3 --seed 1 --small`.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import time
from pathlib import Path

import numpy as np

from palmppg.core.config import load_pipeline_config, rng
from palmppg.core.crf import STREAMS
from palmppg.core.paths import StudyLayout
from palmppg.synth import bayer_video as bv
from palmppg.synth import crf_synth as cs
from palmppg.synth import ecg_synth as es
from palmppg.synth import palm_scene as ps
from palmppg.synth import phone_video as pv
from palmppg.synth.pulse_wave import generate_pulse

SMALL_PROFILE = {"width": 192, "height": 108, "seconds": 20.0, "phone_width": 320, "phone_height": 180}
PHONE_PRE_ROLL_S = 1.5
PHONE_POST_ROLL_S = 1.0
CLIP_START_AFTER_VISIT_MIN = 7.0
T0_MONO_SPACING_NS = 900_000_000_000           # 15 min of boot time between participants


def profile(cfg, small: bool = False) -> dict:
    """Frame geometry and durations: cfg synth.* or the small test profile."""
    p = {"width": int(cfg.get("synth.width")), "height": int(cfg.get("synth.height")), "fps": float(cfg.get("synth.fps")),
         "seconds": float(cfg.get("synth.seconds")), "phone_width": int(cfg.get("synth.phone_width")),
         "phone_height": int(cfg.get("synth.phone_height")), "phone_crf": int(cfg.get("synth.phone_crf")), "small": bool(small)}
    if small:
        p.update(SMALL_PROFILE)
    return p


def participant_id(cfg, i: int) -> str:
    """SWHT-PP-003-#### from cfg study.id (the study id carries a trailing year)."""
    prefix = "-".join(str(cfg.get("study.id")).split("-")[:3])
    return f"{prefix}-{i:04d}"


# ----------------------------------------------------------------------------- study-level files
def write_clock_sync_log(path: Path, date: dt.date, pi_offset_ms: float, pi_drift_ms: float, kardia_offset_ms: float,
                         kardia_drift_ms: float, operator: str, unit_id: str = "unit_01") -> Path:
    """CONTRACTS 3.8 rows for shift start and end (section 4.1: step at start, measure drift at end)."""
    rows = [
        {"date": date.isoformat(), "time_utc": "03:30:00", "device": f"pi_{unit_id}", "offset_ms_vs_phone": round(pi_offset_ms, 1),
         "method": "chronyc makestep", "operator": operator},
        {"date": date.isoformat(), "time_utc": "03:31:00", "device": "kardia_tablet", "offset_ms_vs_phone": round(kardia_offset_ms, 1),
         "method": "ntp_offset", "operator": operator},
        {"date": date.isoformat(), "time_utc": "11:30:00", "device": f"pi_{unit_id}", "offset_ms_vs_phone": round(pi_offset_ms + pi_drift_ms, 1),
         "method": "chronyc tracking", "operator": operator},
        {"date": date.isoformat(), "time_utc": "11:31:00", "device": "kardia_tablet", "offset_ms_vs_phone": round(kardia_offset_ms + kardia_drift_ms, 1),
         "method": "ntp_offset", "operator": operator},
    ]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["date", "time_utc", "device", "offset_ms_vs_phone", "method", "operator"])
        w.writeheader()
        w.writerows(rows)
    return path


def write_unit_calibration(unit_dir: Path, prof: dict, cfg, r: np.random.Generator, sensor: dict) -> dict:
    """darkframe.raw (black level + read noise + a few hot pixels), flatfield.raw (white card under the vignetted
    box light), luxmap.json and phone_flatfield.mp4 (CONTRACTS 3.1 / 3.5, section 5)."""
    unit_dir.mkdir(parents=True, exist_ok=True)
    w, h = prof["width"], prof["height"]
    pattern = str(cfg.get("pi.bayer_pattern"))
    dark = np.zeros((h, w), np.float32)
    hot = r.integers(0, h * w, size=max(3, h * w // 20000))
    dark.flat[hot] = 180.0
    dark_dn = ps.add_sensor_noise(dark, sensor, r)
    (unit_dir / "darkframe.raw").write_bytes(bv.pack_csi2p(dark_dn))
    illum = ps.aperture_illumination(w, h)
    resp = np.asarray(sensor["responsivity"], np.float32)
    card = np.stack([illum * 0.90 * resp[0], illum * 0.90 * resp[1], illum * 0.90 * resp[2]], axis=-1)
    g_centre = float(card[h // 2, w // 2, 1])
    flat_lin = ps.mosaic_from_rgb((card * (700.0 / g_centre)).astype(np.float32), pattern)
    flat_dn = ps.add_sensor_noise(flat_lin, sensor, r)
    (unit_dir / "flatfield.raw").write_bytes(bv.pack_csi2p(flat_dn))
    rows, cols = 3, 5
    lux_nominal = 400.0
    grid = [[round(float(lux_nominal * illum[int((i + 0.5) * h / rows), int((j + 0.5) * w / cols)]), 1) for j in range(cols)] for i in range(rows)]
    (unit_dir / "luxmap.json").write_text(json.dumps({"lux_grid": grid, "rows": rows, "cols": cols, "lux_nominal": lux_nominal,
                                                      "unit_id": unit_dir.name, "synthetic": True}, indent=1), encoding="utf-8")
    pv.write_phone_flatfield(unit_dir / "phone_flatfield.mp4", (prof["phone_width"], prof["phone_height"]), prof["fps"], 2.0, cfg, r,
                             crf=prof["phone_crf"])
    return {"dark_mean_dn": float(dark_dn.mean()), "flat_centre_dn": float(flat_dn[h // 2 - 4:h // 2 + 4, w // 2 - 4:w // 2 + 4].mean()),
            "flat_corner_dn": float(flat_dn[:8, :8].mean()), "lux_grid": grid}


# ----------------------------------------------------------------------------- one participant
def build_participant(layout: StudyLayout, i: int, prof: dict, cfg, seed: int, overrides: dict | None = None,
                      clock: dict | None = None, visit_date: dt.date | None = None) -> dict:
    """Write everything under participants/<id>/ for participant number `i` (1-based) and return its truth."""
    o = dict(overrides or {})
    clock = dict(clock or {})
    sid = participant_id(cfg, i)
    paths = layout.participant(sid)
    streams = o.get("streams") or ["pilot"]
    stream = streams[(i - 1) % len(streams)]
    if stream not in STREAMS:
        raise ValueError(f"unknown stream {stream}")
    r_crf = rng(seed, f"crf:{sid}")
    latent = cs.sample_latent(sid, r_crf, cfg, o.get("latent"))
    visit_start = dt.datetime.combine(visit_date or dt.date(2026, 10, 20), dt.time(9, 0), tzinfo=es.IST) + dt.timedelta(minutes=12 * (i - 1))
    operator = o.get("operator") or cs.OPERATORS[(i - 1) % len(cs.OPERATORS)]
    crf = cs.crf_from_latent(latent, r_crf, cfg, visit_start=visit_start, stream=stream, operator=operator, unit_id=o.get("unit_id", "unit_01"))
    wall0_ns = int((visit_start + dt.timedelta(minutes=CLIP_START_AFTER_VISIT_MIN)).timestamp() * 1e9)
    t0_mono_ns = bv.DEFAULT_T0_MONO_NS + (i - 1) * T0_MONO_SPACING_NS

    scene = ps.make_palm_scene(prof["width"], prof["height"], cfg, rng(seed, f"scene:{sid}"), melanin=latent["melanin"],
                               hand_jitter=float(o.get("hand_jitter", 1.0)))
    seconds, fps = prof["seconds"], prof["fps"]
    r_pulse = rng(seed, f"pulse:{sid}")
    span = PHONE_PRE_ROLL_S + seconds + PHONE_POST_ROLL_S + 1.0
    n_est = int(span * latent["hr_bpm"] / 60.0)
    pulse_truth = generate_pulse(span, latent["hr_bpm"], r_pulse, hrv_sd_s=latent["hrv_sd_s"], resp_rate_hz=latent["resp_rate_hz"],
                                 resp_amp=latent["resp_amp"], n_ectopic=int(round(latent["ectopic_frac"] * n_est)),
                                 morphology=latent["morphology"], t_start=-PHONE_PRE_ROLL_S - 0.5)
    pulse = {"ac_dc_g": latent["ac_dc_g"], "ac_ratios": latent["ac_ratios"], "pulse_truth": pulse_truth}
    r_opt = rng(seed, f"options:{sid}")
    pi_options = {"drops_pct": float(r_opt.uniform(0.0, 1.5)), "flicker_pct": float(r_opt.choice([0.0, 0.0, 0.0, 0.5, 1.0])),
                  "drift_pct": float(r_opt.uniform(-1.0, 1.0)), "jitter_px": float(r_opt.choice([0.0, 0.0, 0.5, 1.0])),
                  "pi_wall_offset_s": float(clock.get("pi_wall_offset_s", 0.003)), "lux": float(r_opt.uniform(350, 450))}
    pi_options.update(o.get("pi_options") or {})
    meta_extra = {"unit_id": crf["unit_id"], "operator": operator, "dept": crf["dept"], "stream": stream, "study_id": sid,
                  "recovery_gate": crf["recovery"], "capture_mode": cfg.get("study.capture_mode")}
    pi_truth = bv.write_pi_clip(paths.pi, "clip1", scene, pulse, fps, seconds, t0_mono_ns=t0_mono_ns, options=pi_options,
                                rng=rng(seed, f"pi:{sid}"), cfg=cfg, meta_extra=meta_extra, wall0_ns=wall0_ns)

    phone_offset = -PHONE_PRE_ROLL_S + float(r_opt.normal(0.0, 0.2))
    phone_drift = float(r_opt.normal(0.0, 2e-5))
    phone_options = {"pre_roll_s": PHONE_PRE_ROLL_S + (phone_offset + PHONE_PRE_ROLL_S), "post_roll_s": PHONE_POST_ROLL_S,
                     "vfr_jitter_ms": float(r_opt.choice([0.0, 0.0, 0.5, 1.5])), "phone_wall_err_s": float(clock.get("phone_wall_err_s", 0.0)),
                     "custom_recorder": bool(o.get("custom_recorder", False))}
    phone_options.update(o.get("phone_options") or {})
    phone_truth = pv.write_phone_clip(paths.phone, "clip1", scene, pulse, fps, seconds, offset_s=phone_offset, drift=phone_drift,
                                      size=(prof["phone_width"], prof["phone_height"]), crf=prof["phone_crf"], rng=rng(seed, f"phone:{sid}"),
                                      cfg=cfg, options=phone_options, pi_truth=pi_truth, meta_extra=meta_extra, wall0_ns=wall0_ns)

    sched = pulse_truth["schedule"]
    kd = seconds if prof["small"] else None
    ecg_truth = es.write_ecg_record(paths.ecg, sid, i, np.asarray(pulse_truth["foot_t"]), latent["pat_s"], latent["rhythm"], cfg,
                                    rng(seed, f"ecg:{sid}"), pi_truth, seconds, wall0_ns, pi_wall_offset_s=pi_options["pi_wall_offset_s"],
                                    kardia_clock_offset_s=float(clock.get("kardia_clock_offset_s", -0.8)),
                                    export_format=o.get("ecg_format", "atc"), kardia_duration_s=kd,
                                    is_ectopic=np.asarray(sched["is_ectopic"], bool))
    clinician = cs.clinician_from_latent(latent, r_crf, cfg, ecg_hr_bpm=ecg_truth["ecg_hr_bpm"], read_date=(visit_start.date() + dt.timedelta(days=1)).isoformat())
    cs.write_participant_forms(paths.root, crf, clinician)
    truth = {
        "study_id": sid, "number": i, "stream": stream, "profile": prof, "seed": seed, "latent": latent, "crf": crf, "clinician": clinician,
        "clock": {"t0_mono_ns": t0_mono_ns, "wall0_ns": wall0_ns, "pi_wall_offset_s": pi_options["pi_wall_offset_s"],
                  "phone": phone_truth["clock_map"], "ecg": ecg_truth["clock_map"], "kardia_clock_offset_s": ecg_truth["kardia_clock_offset_s"],
                  "phone_wall_err_s": phone_options["phone_wall_err_s"]},
        "pulse": {k: pulse_truth[k] for k in ("hr_bpm", "ibi_sd_s", "n_ectopic", "morphology", "morphology_measured")},
        "pi": {k: pi_truth[k] for k in ("n_frames_written", "dropped_frame_idx", "thumb_contact_t_ref_s", "thumb_lift_t_ref_s",
                                         "thumb_down_t_ref_s", "p2_onset_t_ref_s", "led_edges", "ac_dc", "flicker_pct", "drift_pct",
                                         "jitter_px", "drops_pct", "melanin", "tone_label")},
        "phone": {k: phone_truth[k] for k in ("n_frames", "size", "crf", "vfr_jitter_ms", "led_intervals_pts_s", "beep_intervals_pts_s",
                                               "thumb_lift_pts_s", "custom_recorder")},
        "ecg": {k: ecg_truth[k] for k in ("file", "export_format", "ecg_t0_ref_s", "anchor_kind", "app_latency_s", "pat_s",
                                           "artefact_onset_ecg_s", "rhythm", "app_rhythm_label", "ecg_hr_bpm")},
        "files": {"pi_truth": "pi/clip1_truth.json", "phone_truth": "phone/clip1_truth.json", "ecg_truth": "ecg/ecg_truth.json",
                  "landmarks": "pi/clip1_landmarks.json", "roi_masks": "pi/clip1_roi_masks.npz"},
        "tone_label": scene.tone_label,
    }
    (paths.root / "truth.json").write_text(json.dumps(truth, indent=1, default=bv._json_default), encoding="utf-8")
    return truth


# ----------------------------------------------------------------------------- the cohort
def make_cohort(root: str | Path, n_participants: int, seed: int, cfg=None, overrides: dict | None = None, small: bool = False,
                progress: bool = False) -> dict:
    """Build study_root with clock_sync_log.csv, units/unit_01, participants/... and per-participant truth.json.

    overrides (all optional): streams (list cycled per participant), ecg_format ("atc" | "pdf"), custom_recorder,
    latent (dict passed to sample_latent), pi_options, phone_options, operator, unit_id, hand_jitter.
    Returns a summary dict with per-participant truths and timings.
    """
    cfg = cfg or load_pipeline_config()
    root = Path(root)
    layout = StudyLayout(root)
    prof = profile(cfg, small)
    o = dict(overrides or {})
    t_start = time.time()
    r_study = rng(seed, "study")
    unit_id = o.get("unit_id", "unit_01")
    clock = {"pi_wall_offset_s": float(r_study.uniform(0.0, 0.01)), "kardia_clock_offset_s": float(r_study.uniform(-1.2, -0.4)),
             "phone_wall_err_s": 0.0}
    root.mkdir(parents=True, exist_ok=True)
    visit_date = dt.date(2026, 10, 20)
    write_clock_sync_log(layout.clock_sync_log, visit_date, clock["pi_wall_offset_s"] * 1000, float(r_study.uniform(100, 400)),
                         clock["kardia_clock_offset_s"] * 1000, float(r_study.uniform(-50, 50)), o.get("operator", "op1"), unit_id)
    sensor = {"responsivity": [0.63, 1.0, 0.71], "black_level": float(cfg.get("pi.black_level")), "white_level": float(cfg.get("pi.white_level")),
              "read_noise_dn": 2.0, "e_per_dn": 8000.0 / (float(cfg.get("pi.white_level")) - float(cfg.get("pi.black_level")))}
    unit_info = write_unit_calibration(layout.unit(unit_id), prof, cfg, rng(seed, "unit"), sensor)
    truths = []
    for i in range(1, int(n_participants) + 1):
        t_p = time.time()
        tr = build_participant(layout, i, prof, cfg, seed, o, clock, visit_date)
        tr["build_seconds"] = time.time() - t_p
        truths.append(tr)
        if progress:
            print(f"{tr['study_id']}: {tr['build_seconds']:.1f} s", flush=True)
    summary = {"root": str(root), "n_participants": int(n_participants), "seed": int(seed), "profile": prof, "clock": clock,
               "unit": unit_info, "participants": truths, "elapsed_s": time.time() - t_start, "tone_label": ps.TONE_LABEL,
               "note": "synthetic cohort: melanin levels are a synthetic tone shift and support no equity claim"}
    (root / "cohort_truth.json").write_text(json.dumps(summary, indent=1, default=bv._json_default), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build a synthetic SWHT-PP-003 study_root with known truth.")
    ap.add_argument("--root", required=True)
    ap.add_argument("--n", type=int, default=1)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--small", action="store_true", help="192x108, 20 s test profile")
    ap.add_argument("--ecg-format", choices=["atc", "pdf"], default="atc")
    ap.add_argument("--streams", default="pilot", help="comma-separated streams cycled per participant")
    ap.add_argument("--custom-recorder", action="store_true", help="also write phone clip1_frames.csv")
    a = ap.parse_args(argv)
    over = {"ecg_format": a.ecg_format, "streams": a.streams.split(","), "custom_recorder": a.custom_recorder}
    s = make_cohort(a.root, a.n, a.seed, overrides=over, small=a.small, progress=True)
    print(f"wrote {s['n_participants']} participant(s) to {s['root']} in {s['elapsed_s']:.1f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
