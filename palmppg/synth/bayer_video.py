"""Packed 10-bit Pi clip writer with pts csv, meta, sync_events and ground truth (CONTRACTS section 3.1-3.4).

Protocol sections served: 3 (data layout, byte-exact), 4.2 (LED marker patterns P1/P2 logged as mono_ns and
wall_ns with a gpio_ok self-check; the LED block is bright during pulses in every Bayer plane), 4.3 (the
thumb lands on the Kardia card early in the clip and lifts for about half a second after P2), 6.1 (frame
drops, 50 Hz flicker sampled at the frame rate, linear lighting drift), 8 / 12 step 1 (known pulse).

Frame model, per written frame k at true capture instant t_k (reference clock, s from the first frame):
    DN(x, y) = [DC(x, y) - AC(x, y) * W(t_k)] * flicker(t_k) * drift(t_k)
with DC/AC from `palm_scene.bayer_dc_ac`, W the unit-peak blood-volume waveform (intensity falls as blood
volume rises), the LED block replaced by LED radiance in proportion to the fraction of the exposure window
during which the LED is on, Poisson shot noise, Gaussian read noise, black level, 10-bit clip, CSI2P packing.
Frames are generated, packed and appended one at a time; nothing holds the clip in memory.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import math
from pathlib import Path

import numpy as np

from palmppg.synth import palm_scene as ps
from palmppg.synth.pulse_wave import generate_pulse, waveform_from_truth

DEFAULT_T0_MONO_NS = 4_000_000_000_000           # a CLOCK_BOOTTIME-like origin (4000 s after boot)
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
DEFAULT_WALL0_NS = int(dt.datetime(2026, 10, 20, 9, 30, tzinfo=IST).timestamp()) * 1_000_000_000   # Unix ns
LED_ON_DN = 880.0                                  # LED block level above black when fully on (all planes)
PTS_JITTER_S = 1.0e-4                              # sensor timestamp jitter, uniform +/- 0.1 ms (< 0.2 ms)
GPIO_LOG_LATENCY_S = (1.0e-4, 4.0e-4)             # logged edge lags the optical edge by this range
DEFAULT_OPTIONS = {
    "drops_pct": 0.5, "flicker_pct": 0.0, "drift_pct": 0.0, "jitter_px": 0.0, "thumb_lift_at_p2": True,
    "thumb_contact_s": 1.0, "lift_reaction_s": 0.6, "lift_duration_s": 0.5, "exposure_us": 8000,
    "analogue_gain": 2.0, "digital_gain": 1.0, "awb_gains": [1.6, 1.4], "lens_position": 2.5,
    "led_current_ma": 20, "lux": 400.0, "sensor_temp_c": 41.5, "pi_wall_offset_s": 0.0,
}


# ----------------------------------------------------------------------------- packing (CONTRACTS 3.1)
def stride_bytes_for(width: int) -> int:
    """CSI2P stride: ceil(width * 10 / 8) rounded up to a multiple of 32 (1536 -> 1920)."""
    raw = math.ceil(width * 10 / 8)
    return int(math.ceil(raw / 32) * 32)


def pack_csi2p(frame: np.ndarray, stride: int | None = None) -> bytes:
    """Pack a (H, W) uint16 frame (0..1023) as SRGGB10_CSI2P: 4 pixels in 5 bytes, rows padded to `stride`."""
    h, w = frame.shape
    if w % 4:
        raise ValueError("width must be a multiple of 4")
    stride = stride or stride_bytes_for(w)
    px = np.ascontiguousarray(frame, dtype=np.uint16).reshape(h, w // 4, 4)
    out = np.zeros((h, stride), dtype=np.uint8)
    body = out[:, : w * 5 // 4].reshape(h, w // 4, 5)
    body[..., :4] = (px >> 2).astype(np.uint8)
    low = px & 3
    body[..., 4] = (low[..., 0] | (low[..., 1] << 2) | (low[..., 2] << 4) | (low[..., 3] << 6)).astype(np.uint8)
    return out.tobytes()


def unpack_csi2p(buf: bytes | np.ndarray, width: int, height: int, stride: int | None = None) -> np.ndarray:
    """Inverse of pack_csi2p (the generator's own reference; the ingest unpacker is built independently)."""
    stride = stride or stride_bytes_for(width)
    arr = np.frombuffer(buf, dtype=np.uint8, count=stride * height).reshape(height, stride)
    body = arr[:, : width * 5 // 4].reshape(height, width // 4, 5).astype(np.uint16)
    out = np.empty((height, width // 4, 4), dtype=np.uint16)
    for i in range(4):
        out[..., i] = (body[..., i] << 2) | ((body[..., 4] >> (2 * i)) & 3)
    return out.reshape(height, width)


def iter_raw_frames(raw_path: str | Path, meta: dict):
    """Stream (frame_number, mosaic uint16) from a packed clip using its meta (never loads the whole file)."""
    w, h = int(meta["width"]), int(meta["height"])
    stride = int(meta.get("stride_bytes") or stride_bytes_for(w))
    nbytes = stride * h
    with open(raw_path, "rb") as fh:
        k = 0
        while True:
            buf = fh.read(nbytes)
            if len(buf) < nbytes:
                return
            yield k, unpack_csi2p(buf, w, h, stride)
            k += 1


# ----------------------------------------------------------------------------- LED / buzzer schedule (4.2)
def led_schedule(cfg, seconds: float) -> list[dict]:
    """On/off intervals (s from clip start) of P1 and P2 from cfg `sync.p1` / `sync.p2`.

    P1 at `at_s_after_start`; P2 at `t_end - at_s_before_end` (mode before_end) or `at_s_after_start`
    (mode after_start, the 30 s Kardia app case). Returns dicts {pattern, pulse, on_s, off_s}.
    """
    out = []
    p1 = cfg.section("sync.p1")
    t = float(p1["at_s_after_start"])
    for i in range(int(p1["pulses"])):
        out.append({"pattern": "P1", "pulse": i, "on_s": t, "off_s": t + p1["on_ms"] / 1000.0})
        t += (p1["on_ms"] + p1["off_ms"]) / 1000.0
    p2 = cfg.section("sync.p2")
    mode = p2.get("mode", "before_end")
    t = float(seconds - p2["at_s_before_end"]) if mode == "before_end" else float(p2["at_s_after_start"])
    for i in range(int(p2["pulses"])):
        out.append({"pattern": "P2", "pulse": i, "on_s": t, "off_s": t + p2["on_ms"] / 1000.0})
        t += (p2["on_ms"] + p2["off_ms"]) / 1000.0
    return out


def led_fraction(t_frame_s: np.ndarray, exposure_s: float, schedule: list[dict]) -> np.ndarray:
    """Fraction of each exposure window [t, t + exposure] during which the LED is on (0..1)."""
    t = np.asarray(t_frame_s, dtype=float)
    frac = np.zeros_like(t)
    for p in schedule:
        overlap = np.minimum(t + exposure_s, p["off_s"]) - np.maximum(t, p["on_s"])
        frac += np.clip(overlap, 0.0, exposure_s) / exposure_s
    return np.clip(frac, 0.0, 1.0)


def sync_event_rows(schedule: list[dict], t0_mono_ns: int, wall0_ns: int, rng: np.random.Generator) -> tuple[list[dict], list[dict]]:
    """CONTRACTS 3.4 rows (one per edge, logged a little after the optical edge) and the optical truth."""
    rows, truth = [], []
    eid = 0
    for p in schedule:
        for kind, t in (("start", p["on_s"]), ("end", p["off_s"])):
            lag = float(rng.uniform(*GPIO_LOG_LATENCY_S))
            mono = int(t0_mono_ns + round((t + lag) * 1e9))
            rows.append({"event_id": eid, "kind": kind, "pattern": p["pattern"], "mono_ns": mono,
                         "wall_ns": int(wall0_ns + round((t + lag) * 1e9)), "gpio_ok": True})
            truth.append({"event_id": eid, "pattern": p["pattern"], "pulse": p["pulse"], "kind": kind,
                          "t_ref_s": float(t), "logged_t_ref_s": float(t + lag)})
            eid += 1
    return rows, truth


def write_sync_events(path: str | Path, rows: list[dict]) -> Path:
    path = Path(path)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["event_id", "kind", "pattern", "mono_ns", "wall_ns", "gpio_ok"])
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return path


def sync_events_path(pi_dir: Path, clip_id: str) -> Path:
    return pi_dir / ("sync_events.csv" if clip_id == "clip1" else f"sync_events_{clip_id}.csv")


# ----------------------------------------------------------------------------- frame timing (6.1)
def frame_times(n_nominal: int, fps: float, drops_pct: float, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """True capture instants (s) of every nominal frame with sub-period jitter, and the dropped indices."""
    period = 1.0 / fps
    t = np.arange(n_nominal) * period + rng.uniform(-PTS_JITTER_S, PTS_JITTER_S, n_nominal)
    t[0] = 0.0
    n_drop = int(round(drops_pct / 100.0 * n_nominal))
    dropped = np.sort(rng.choice(np.arange(1, n_nominal), size=n_drop, replace=False)) if n_drop > 0 else np.zeros(0, int)
    return t, dropped


def thumb_state(t_s: np.ndarray, contact_s: float, lift_s: float | None, lift_duration_s: float) -> np.ndarray:
    """True where the thumb is OFF the card (before contact and during the lift)."""
    t = np.asarray(t_s, dtype=float)
    up = t < contact_s
    if lift_s is not None:
        up |= (t >= lift_s) & (t < lift_s + lift_duration_s)
    return up


# ----------------------------------------------------------------------------- the writer
def write_pi_clip(out_dir: str | Path, clip_id: str, scene: ps.PalmScene, pulse: dict, fps: float, seconds: float,
                  width: int | None = None, height: int | None = None, t0_mono_ns: int = DEFAULT_T0_MONO_NS,
                  options: dict | None = None, rng: np.random.Generator | None = None, cfg=None,
                  meta_extra: dict | None = None, wall0_ns: int = DEFAULT_WALL0_NS) -> dict:
    """Write `<clip_id>.raw`, `<clip_id>_pts.csv`, `<clip_id>_meta.json`, `sync_events.csv`, `<clip_id>_truth.json`,
    `<clip_id>_landmarks.json` and `<clip_id>_roi_masks.npz` into `out_dir` (the participant's pi/ folder).

    pulse: {"ac_dc_g": peak-to-peak AC/DC in G at the thenar, "ac_ratios": {"R","G","B"} relative amplitudes,
            "pulse_truth": dict from pulse_wave.generate_pulse (or "hr_bpm" to generate one here)}
    options: see DEFAULT_OPTIONS (drops_pct, flicker_pct at the aliased mains, drift_pct over the clip,
            jitter_px per-frame integer scene shifts, thumb_lift_at_p2, thumb_contact_s, exposure_us ...).
    Returns the truth dict that was written. Sections 3, 4.2, 4.3, 6.1, 8.
    """
    if cfg is None:
        from palmppg.core.config import load_pipeline_config

        cfg = load_pipeline_config()
    if rng is None:
        from palmppg.core.config import rng as _rng

        rng = _rng(0, f"pi:{clip_id}")
    opt = dict(DEFAULT_OPTIONS)
    opt.update(options or {})
    width = width or scene.width
    height = height or scene.height
    if (width, height) != (scene.width, scene.height):
        raise ValueError("width/height must match the scene geometry")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = str(cfg.get("pi.bayer_pattern"))
    stride = stride_bytes_for(width)
    ac_dc_g = float(pulse["ac_dc_g"])
    ratios = pulse.get("ac_ratios", {"R": 0.5, "G": 1.0, "B": 0.6})
    rt = ps._ratio_tuple(ratios)
    truth_pulse = pulse.get("pulse_truth") or generate_pulse(seconds, float(pulse["hr_bpm"]), rng)

    # timing
    n_nominal = int(round(seconds * fps))
    t_all, dropped = frame_times(n_nominal, fps, float(opt["drops_pct"]), rng)
    keep = np.ones(n_nominal, bool)
    keep[dropped] = False
    schedule = led_schedule(cfg, seconds)
    exposure_s = float(opt["exposure_us"]) * 1e-6
    led_frac = led_fraction(t_all, exposure_s, schedule)
    p2_onset = min(p["on_s"] for p in schedule if p["pattern"] == "P2")
    lift_s = (p2_onset + float(opt["lift_reaction_s"])) if opt["thumb_lift_at_p2"] else None
    thumb_up = thumb_state(t_all, float(opt["thumb_contact_s"]), lift_s, float(opt["lift_duration_s"]))
    w_all = waveform_from_truth(truth_pulse, t_all)
    flicker_phase = float(rng.uniform(0, 2 * math.pi))
    flick = 1.0 + float(opt["flicker_pct"]) / 100.0 * np.sin(2 * math.pi * 50.0 * t_all + flicker_phase)
    drift = 1.0 + float(opt["drift_pct"]) / 100.0 * (t_all / max(seconds, 1e-9))
    jitter_px = float(opt["jitter_px"])
    shifts = np.rint(rng.normal(0.0, jitter_px, size=(n_nominal, 2))).astype(int) if jitter_px > 0 else np.zeros((n_nominal, 2), int)

    # static images (DC / AC) for both thumb poses; RGB versions only when the scene must shift per frame
    resp = np.asarray(scene.sensor["responsivity"], np.float32) * scene.sensor["exposure_scale"]
    dc, ac, rgb_dc, rgb_ac = {}, {}, {}, {}
    for up in (False, True):
        dc[up], ac[up] = ps.bayer_dc_ac(scene, ac_dc_g, rt, thumb_up=up, pattern=pattern)
        if jitter_px > 0:
            rad = ps.linear_radiance(scene, up) * resp[None, None, :]
            amap = scene.ac_map_thumb_up if up else scene.ac_map
            rgb_dc[up] = rad.astype(np.float32)
            rgb_ac[up] = (rad * np.asarray(rt, np.float32)[None, None, :] * (ac_dc_g * amap)[..., None]).astype(np.float32)
    ys, xs = ps.block_slice(scene.led_block)
    sensor = scene.sensor

    # files
    raw_path = out_dir / f"{clip_id}.raw"
    pts_path = out_dir / f"{clip_id}_pts.csv"
    written_t: list[float] = []
    written_idx: list[int] = []
    sat_frac_sum = 0.0
    with open(raw_path, "wb") as fraw, open(pts_path, "w", newline="", encoding="utf-8") as fpts:
        pw = csv.writer(fpts)
        pw.writerow(["frame_idx", "sensor_ts_ns", "wall_ns", "exposure_us", "analogue_gain", "digital_gain", "lux"])
        for k in range(n_nominal):
            if not keep[k]:
                continue
            up = bool(thumb_up[k])
            if jitter_px > 0 and (shifts[k] != 0).any():
                dx, dy = int(shifts[k, 0]), int(shifts[k, 1])
                sdc = np.roll(rgb_dc[up], (dy, dx), axis=(0, 1))
                sac = np.roll(rgb_ac[up], (dy, dx), axis=(0, 1))
                frame = ps.mosaic_from_rgb(sdc, pattern) - ps.mosaic_from_rgb(sac, pattern) * float(w_all[k])
            else:
                frame = dc[up] - ac[up] * float(w_all[k])
            frame = frame * float(flick[k] * drift[k])
            f = float(led_frac[k])
            if f > 0:
                frame[ys, xs] = frame[ys, xs] * (1.0 - f) + LED_ON_DN * f
            dn = ps.add_sensor_noise(frame, sensor, rng)
            sat_frac_sum += float((dn[scene.skin_mask] >= sensor["white_level"]).mean())
            fraw.write(pack_csi2p(dn, stride))
            ts_ns = int(t0_mono_ns + round(t_all[k] * 1e9))
            pw.writerow([k, ts_ns, int(wall0_ns + round((t_all[k] + opt["pi_wall_offset_s"]) * 1e9)), int(opt["exposure_us"]),
                         float(opt["analogue_gain"]), float(opt["digital_gain"]), round(float(opt["lux"]) + float(rng.normal(0, 1.5)), 1)])
            written_t.append(float(t_all[k]))
            written_idx.append(int(k))
    n_written = len(written_idx)

    # sync events
    rows, led_truth = sync_event_rows(schedule, t0_mono_ns, wall0_ns + int(opt["pi_wall_offset_s"] * 1e9), rng)
    write_sync_events(sync_events_path(out_dir, clip_id), rows)

    # meta (CONTRACTS 3.3)
    extra = dict(meta_extra or {})
    meta = {
        "unit_id": extra.get("unit_id", "unit_01"), "operator": extra.get("operator", "op1"), "dept": extra.get("dept", "Medicine OPD"),
        "stream": extra.get("stream", "pilot"), "app_ver": extra.get("app_ver", "synth-0.1"), "study_id": extra.get("study_id", "SWHT-PP-003-0000"),
        "clip_id": clip_id, "width": width, "height": height, "stride_bytes": stride, "bayer_pattern": pattern,
        "bit_depth": int(cfg.get("pi.bit_depth")), "fps_nominal": float(fps), "crop_rect": None,
        "exposure_us": int(opt["exposure_us"]), "analogue_gain": float(opt["analogue_gain"]), "digital_gain": float(opt["digital_gain"]),
        "awb_gains": [float(v) for v in opt["awb_gains"]], "lens_position": float(opt["lens_position"]),
        "led_current_ma": float(opt["led_current_ma"]), "lux": float(opt["lux"]), "sensor_temp_c": float(opt["sensor_temp_c"]),
        "start_wall_ns": int(wall0_ns + opt["pi_wall_offset_s"] * 1e9), "stop_wall_ns": int(wall0_ns + (seconds + opt["pi_wall_offset_s"]) * 1e9),
        "start_mono_ns": int(t0_mono_ns), "stop_mono_ns": int(t0_mono_ns + round(seconds * 1e9)),
        "live_sqi": float(extra.get("live_sqi", 0.62)), "motion_flag": bool(extra.get("motion_flag", False)),
        "recovery_gate": extra.get("recovery_gate", "pass"), "video_seconds": float(seconds),
        "capture_mode": extra.get("capture_mode", cfg.get("study.capture_mode")), "n_frames_written": n_written,
        "led_block": dict(scene.led_block), "thumb_block": dict(scene.thumb_block),
        "format": "SRGGB10_CSI2P", "synthetic": True,
    }
    (out_dir / f"{clip_id}_meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    ps.write_landmarks(out_dir / f"{clip_id}_landmarks.json", scene, clip_id)
    ps.write_roi_masks(out_dir / f"{clip_id}_roi_masks.npz", scene)

    hr_t = np.arange(0.0, seconds, 0.25)
    truth = {
        "clip_id": clip_id, "study_id": meta["study_id"], "camera": "pi", "t0_mono_ns": int(t0_mono_ns), "wall0_ns": int(wall0_ns),
        "pi_wall_offset_s": float(opt["pi_wall_offset_s"]), "fps": float(fps), "seconds": float(seconds),
        "n_frames_nominal": n_nominal, "n_frames_written": n_written, "dropped_frame_idx": [int(i) for i in dropped],
        "frame_idx": written_idx, "frame_t_ref_s": written_t, "waveform_at_frames": [float(w_all[i]) for i in written_idx],
        "hr_bpm": float(truth_pulse["hr_bpm"]), "hr_series": {"t_ref_s": hr_t.tolist(),
                                                              "hr_bpm": np.interp(hr_t, hr_t, _hr_curve(truth_pulse, hr_t)).tolist()},
        "foot_t_ref_s": [float(v) for v in truth_pulse["foot_t"]],
        "foot_tangent_t_ref_s": [float(v) for v in truth_pulse.get("foot_t_tangent", truth_pulse["foot_t"])], "beats": truth_pulse["beats"],
        "morphology_params": truth_pulse["morphology"], "morphology_measured": truth_pulse["morphology_measured"],
        "n_ectopic": int(truth_pulse.get("n_ectopic", 0)), "pulse_truth": truth_pulse,
        "ac_dc": {"R": ac_dc_g * rt[0], "G": ac_dc_g, "B": ac_dc_g * rt[2]}, "ac_dc_g": ac_dc_g,
        "ac_ratios": {"R": rt[0], "G": rt[1], "B": rt[2]}, "ac_map_region_means": scene.region_ac_means(),
        "led_edges": led_truth, "led_schedule": schedule, "led_on_dn": LED_ON_DN, "exposure_s": exposure_s,
        "p2_onset_t_ref_s": float(p2_onset), "thumb_contact_t_ref_s": float(opt["thumb_contact_s"]),
        "thumb_lift_t_ref_s": lift_s, "thumb_down_t_ref_s": (lift_s + float(opt["lift_duration_s"])) if lift_s is not None else None,
        "flicker_pct": float(opt["flicker_pct"]), "flicker_phase": flicker_phase, "drift_pct": float(opt["drift_pct"]),
        "jitter_px": jitter_px, "drops_pct": float(opt["drops_pct"]), "melanin": scene.melanin, "tone_label": scene.tone_label,
        "saturation_frac_mean": sat_frac_sum / max(n_written, 1), "scene": scene.summary(),
    }
    (out_dir / f"{clip_id}_truth.json").write_text(json.dumps(truth, indent=1, default=_json_default), encoding="utf-8")
    return truth


def _hr_curve(truth_pulse: dict, t: np.ndarray) -> np.ndarray:
    from palmppg.synth.pulse_wave import instantaneous_hr

    return instantaneous_hr(np.asarray(truth_pulse["foot_t"], float), t)


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, float) and not math.isfinite(o):
        return None
    return str(o)
