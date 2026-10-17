"""Phone proxy clip: the same scene through an 8-bit sRGB pipeline, H.264 + AAC beeps (CONTRACTS 3.5).

Protocol sections served: 2 (capture_mode simultaneous: the phone views the same palm, sees the LED and
hears the buzzer), 4.2 (audio marker: 2.5 kHz tone bursts coincident with the LED pulses, so the phone
audio onset and LED block can be matched against the Pi log), 5 (1080p30 H.264 with audio, treated as
variable frame rate; constant settings; no stabilisation), 8 (compression as the phone-transfer simulation).

Clock model (CONTRACTS section 0 / Timeline.ClockMap): a phone frame with container pts `p` seconds was
captured at reference time `t_ref = p * (1 + drift) + offset_s`. `offset_s` is the reference-clock time of
phone pts 0 (negative when the phone started before the Pi). Frames are rendered at those instants, so the
pulse, the LED and the thumb lift are consistent with the Pi clip on the reference clock. Optional VFR
jitter perturbs the true capture instants (and the written pts with them) - no interpolation anywhere.

Encoding goes through PyAV (ffmpeg's libavcodec/libavformat: libx264 at the requested CRF, yuv420p, AAC
mono 48 kHz) one frame at a time with explicit per-frame pts on a 90 kHz time base, so VFR timestamps
survive the mp4 round trip and ffprobe reads them back.
"""
from __future__ import annotations

import csv
import fractions
import json
import math
from pathlib import Path

import numpy as np

from palmppg.synth import palm_scene as ps
from palmppg.synth.bayer_video import DEFAULT_WALL0_NS, _json_default, led_schedule, thumb_state
from palmppg.synth.pulse_wave import generate_pulse, waveform_from_truth

AUDIO_FS = 48000
AUDIO_CHUNK = 4800
PHONE_MONO0_NS = 9_000_000_000_000
DEFAULT_PHONE_OPTIONS = {
    "pre_roll_s": 1.5, "post_roll_s": 1.0, "preset": "veryfast", "bitrate_mbps": 20.0, "iso": 400, "exposure_ns": 8_000_000,
    "app": "OpenCamera", "device_model": "OnePlus 12", "os_build": "OxygenOS 15.0 (synthetic)",
    "full_well_e": 3000.0, "read_noise": 0.004, "target_skin_g": 0.42, "flicker_pct": 0.0, "drift_pct": 0.0,
    "audio_level": 0.5, "audio_noise_dbfs": -45.0, "audio_ramp_s": 0.005, "acoustic_delay_s": 0.001,
    "phone_wall_err_s": 0.0, "vfr_jitter_ms": 0.0, "custom_recorder": False, "perspective": 0.03,
    "thumb_contact_s": 1.0, "lift_reaction_s": 0.6, "lift_duration_s": 0.5, "led_on_linear": 0.95,
}


# ----------------------------------------------------------------------------- phone view of the scene
def phone_view(scene: ps.PalmScene, size: tuple[int, int], cfg, rng: np.random.Generator, torch: bool,
               perspective: float = 0.03) -> dict:
    """Warp the Pi scene into the phone frame (slight perspective difference, own vignette, white balanced).

    Returns arrays at (h, w): refl[False|True] (thumb down/up, linear RGB), ac[False|True], illum, skin masks,
    the 3x3 homography (Pi full-res pixels -> phone pixels) and the phone LED block from cfg `sync.led_block.phone`
    scaled from cfg `phone.width` x `phone.height`.
    """
    import cv2

    w, h = int(size[0]), int(size[1])
    W, H = scene.width, scene.height
    src = np.float32([[0, 0], [W, 0], [W, H], [0, H]])
    jit = perspective * np.array([w, h], np.float32)
    dst = np.float32([[0, 0], [w, 0], [w, h], [0, h]]) + rng.uniform(-1, 1, (4, 2)).astype(np.float32) * jit
    Hm = cv2.getPerspectiveTransform(src, dst)
    bg = tuple(float(v) for v in ps.BACKGROUND_REFLECTANCE)

    def warp(img, nearest=False, border=0.0):
        flags = cv2.INTER_NEAREST if nearest else cv2.INTER_LINEAR
        return cv2.warpPerspective(img, Hm, (w, h), flags=flags, borderMode=cv2.BORDER_CONSTANT, borderValue=border)

    out = {"homography": Hm, "refl": {}, "ac": {}, "skin": {}}
    for up in (False, True):
        refl = scene.reflectance_thumb_up if up else scene.reflectance
        amap = scene.ac_map_thumb_up if up else scene.ac_map
        skin = scene.skin_mask_thumb_up if up else scene.skin_mask
        out["refl"][up] = warp(refl.astype(np.float32), border=bg)
        out["ac"][up] = warp(amap.astype(np.float32))
        out["skin"][up] = warp(skin.astype(np.uint8), nearest=True).astype(bool)
    X, Y = ps._grid(w, h)
    cx, cy = 0.5 * w / h + 0.03, 0.5 - 0.02
    r2 = (X - cx) ** 2 + (Y - cy) ** 2
    illum = (1.0 / (1.0 + r2 / (2.6 * 2.6))) ** 2
    if torch:
        illum = 0.75 * illum + 0.45 * np.exp(-r2 / (2 * 0.35**2))
    illum = (illum / illum[h // 2, w // 2]).astype(np.float32)
    out["illum"] = illum
    out["wb"] = np.array([1.0, 1.0, 1.08 if torch else 1.0], np.float32)   # torch: slightly cooler
    phone_ref = (int(cfg.get("phone.width")), int(cfg.get("phone.height")))
    out["led_block"] = ps.scale_block(cfg.get("sync.led_block.phone"), w, h, ref_wh=phone_ref)
    cp = scene.region_masks["central_palm"]
    cp_phone = warp(cp.astype(np.uint8), nearest=True).astype(bool)
    out["central_palm"] = cp_phone
    return out


def _srgb_lut(n: int = 4096) -> np.ndarray:
    lin = np.arange(n, dtype=np.float32) / (n - 1)
    return (ps.srgb_oetf(lin) * 255.0 + 0.5).astype(np.uint8)


# ----------------------------------------------------------------------------- audio
def beep_envelope(p_s: np.ndarray, intervals: list[tuple[float, float]], ramp_s: float) -> np.ndarray:
    """0..1 envelope of tone bursts over the phone-time intervals with raised-cosine ramps."""
    env = np.zeros_like(p_s)
    for on, off in intervals:
        x = np.clip((p_s - on) / ramp_s, 0.0, 1.0)
        y = np.clip((off - p_s) / ramp_s, 0.0, 1.0)
        env = np.maximum(env, 0.5 * (1 - np.cos(math.pi * x)) * 0.5 * (1 - np.cos(math.pi * y)))
    return env


# ----------------------------------------------------------------------------- the writer
def write_phone_clip(out_dir: str | Path, clip_id: str, scene: ps.PalmScene, pulse: dict, fps: float, seconds: float,
                     offset_s: float = -1.5, drift: float = 0.0, size: tuple[int, int] | None = None, crf: int | None = None,
                     torch: bool | None = None, rng: np.random.Generator | None = None, cfg=None, options: dict | None = None,
                     pi_truth: dict | None = None, meta_extra: dict | None = None, wall0_ns: int = DEFAULT_WALL0_NS) -> dict:
    """Write `<clip_id>.mp4`, `<clip_id>_meta.json`, `<clip_id>_truth.json` (and `<clip_id>_frames.csv` when
    `options["custom_recorder"]`) into `out_dir` (the participant's phone/ folder). Sections 2, 4.2, 5, 8.

    `pulse` as for bayer_video.write_pi_clip. `seconds` is the Pi clip length; the phone records from
    `offset_s` (reference clock) for pre_roll + seconds + post_roll. `size` defaults to cfg synth.phone_width x
    phone_height, `crf` to cfg synth.phone_crf, `torch` to cfg phone.torch == "on".
    """
    import av

    if cfg is None:
        from palmppg.core.config import load_pipeline_config

        cfg = load_pipeline_config()
    if rng is None:
        from palmppg.core.config import rng as _rng

        rng = _rng(0, f"phone:{clip_id}")
    opt = dict(DEFAULT_PHONE_OPTIONS)
    opt.update(options or {})
    size = size or (int(cfg.get("synth.phone_width")), int(cfg.get("synth.phone_height")))
    w, h = int(size[0]), int(size[1])
    if w % 2 or h % 2:
        raise ValueError("phone frame size must be even for yuv420p")
    crf = int(cfg.get("synth.phone_crf")) if crf is None else int(crf)
    torch = (str(cfg.get("phone.torch")).lower() == "on") if torch is None else bool(torch)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ac_dc_g = float(pulse["ac_dc_g"])
    rt = ps._ratio_tuple(pulse.get("ac_ratios", {"R": 0.5, "G": 1.0, "B": 0.6}))
    truth_pulse = pulse.get("pulse_truth") or generate_pulse(seconds, float(pulse["hr_bpm"]), rng)

    # events on the reference clock (from the Pi truth when given, else the same rules as the Pi writer)
    if pi_truth is not None:
        schedule = pi_truth["led_schedule"]
        contact_s = float(pi_truth["thumb_contact_t_ref_s"])
        lift_s = pi_truth.get("thumb_lift_t_ref_s")
        lift_dur = float(pi_truth["thumb_down_t_ref_s"] - lift_s) if lift_s is not None else float(opt["lift_duration_s"])
    else:
        schedule = led_schedule(cfg, seconds)
        contact_s = float(opt["thumb_contact_s"])
        p2 = min(p["on_s"] for p in schedule if p["pattern"] == "P2")
        lift_s = p2 + float(opt["lift_reaction_s"])
        lift_dur = float(opt["lift_duration_s"])

    # phone frame instants
    phone_seconds = float(opt["pre_roll_s"]) + seconds + float(opt["post_roll_s"])
    n_frames = int(round(phone_seconds * fps))
    pts = np.arange(n_frames) / fps
    vfr = float(opt["vfr_jitter_ms"]) / 1000.0
    if vfr > 0:
        pts = pts + rng.normal(0.0, vfr, n_frames)
        pts[0] = 0.0
        pts = np.maximum.accumulate(pts + np.arange(n_frames) * 1e-9)
        for k in range(1, n_frames):           # keep a minimum spacing so pts stay strictly increasing
            if pts[k] - pts[k - 1] < 0.002:
                pts[k] = pts[k - 1] + 0.002
    t_ref = pts * (1.0 + drift) + offset_s
    w_all = waveform_from_truth(truth_pulse, t_ref)
    thumb_up = thumb_state(t_ref, contact_s, lift_s, lift_dur)
    flick = 1.0 + float(opt["flicker_pct"]) / 100.0 * np.sin(2 * math.pi * 50.0 * t_ref + float(rng.uniform(0, 2 * math.pi)))
    drift_gain = 1.0 + float(opt["drift_pct"]) / 100.0 * np.clip(t_ref / max(seconds, 1e-9), 0, 1)
    exposure_s = float(opt["exposure_ns"]) * 1e-9
    led_frac = np.zeros(n_frames)
    for p in schedule:
        overlap = np.minimum(t_ref + exposure_s, p["off_s"]) - np.maximum(t_ref, p["on_s"])
        led_frac += np.clip(overlap, 0.0, exposure_s) / exposure_s
    led_frac = np.clip(led_frac, 0, 1)

    # static phone images
    view = phone_view(scene, (w, h), cfg, rng, torch, float(opt["perspective"]))
    dc, acm = {}, {}
    g_centre = float((view["refl"][False][..., 1] * view["illum"])[view["central_palm"]].mean()) if view["central_palm"].any() else 0.3
    exposure = float(opt["target_skin_g"]) / max(g_centre, 1e-6)
    for up in (False, True):
        rad = view["refl"][up] * view["illum"][..., None] * view["wb"][None, None, :] * exposure
        dc[up] = rad.astype(np.float32)
        acm[up] = (rad * np.asarray(rt, np.float32)[None, None, :] * (ac_dc_g * view["ac"][up])[..., None]).astype(np.float32)
    lut = _srgb_lut()
    ys, xs = ps.block_slice(view["led_block"])
    fw = float(opt["full_well_e"])
    read = float(opt["read_noise"])

    # audio plan in phone time
    delay = float(opt["acoustic_delay_s"])
    led_pts = [((p["on_s"] - offset_s) / (1.0 + drift), (p["off_s"] - offset_s) / (1.0 + drift)) for p in schedule]
    beep_pts = [(a + delay, b + delay) for a, b in led_pts]
    tone_hz = float(cfg.get("sync.audio.tone_hz"))
    noise_amp = 10 ** (float(opt["audio_noise_dbfs"]) / 20.0)
    level = float(opt["audio_level"])
    ramp = float(opt["audio_ramp_s"])
    total_samples = int(math.ceil(phone_seconds * AUDIO_FS))

    def audio_chunk(s0: int, s1: int) -> np.ndarray:
        p = np.arange(s0, s1) / AUDIO_FS
        env = beep_envelope(p, beep_pts, ramp)
        sig = level * env * np.sin(2 * math.pi * tone_hz * p)
        sig += noise_amp * rng.standard_normal(p.size) + 0.3 * noise_amp * np.sin(2 * math.pi * 50.0 * p)
        return np.clip(sig, -1, 1).astype(np.float32)

    # encode
    mp4 = out_dir / f"{clip_id}.mp4"
    tb = fractions.Fraction(1, 90000)
    container = av.open(str(mp4), "w")
    vs = container.add_stream("libx264")
    vs.codec_context.time_base = tb
    vs.codec_context.framerate = fractions.Fraction(fps).limit_denominator(1000)
    vs.width, vs.height, vs.pix_fmt = w, h, "yuv420p"
    vs.options = {"crf": str(crf), "preset": str(opt["preset"])}
    aus = container.add_stream("aac", rate=AUDIO_FS, layout="mono")
    aus.bit_rate = 96000
    a_tb = fractions.Fraction(1, AUDIO_FS)
    a_pos = 0
    frames_rows = []
    try:
        for k in range(n_frames):
            up = bool(thumb_up[k])
            lin = (dc[up] - acm[up] * float(w_all[k])) * float(flick[k] * drift_gain[k])
            f = float(led_frac[k])
            if f > 0:
                lin[ys, xs] = lin[ys, xs] * (1.0 - f) + float(opt["led_on_linear"]) * f
            noisy = ps.shot_read_noise(lin, fw, read, rng)
            rgb8 = np.take(lut, (np.clip(noisy, 0.0, 1.0) * (lut.size - 1)).astype(np.int16))
            vf = av.VideoFrame.from_ndarray(np.ascontiguousarray(rgb8), format="rgb24")
            vf.pts = int(round(pts[k] * 90000))
            vf.time_base = tb
            for pk in vs.encode(vf):
                container.mux(pk)
            while a_pos / AUDIO_FS < pts[k] and a_pos < total_samples:
                s1 = min(a_pos + AUDIO_CHUNK, total_samples)
                af = av.AudioFrame.from_ndarray(audio_chunk(a_pos, s1).reshape(1, -1), format="flt", layout="mono")
                af.sample_rate = AUDIO_FS
                af.pts = a_pos
                af.time_base = a_tb
                for pk in aus.encode(af):
                    container.mux(pk)
                a_pos = s1
            if opt["custom_recorder"]:
                frames_rows.append([k, int(PHONE_MONO0_NS + round(pts[k] * 1e9)),
                                    int(wall0_ns + round((offset_s + opt["phone_wall_err_s"] + pts[k]) * 1e9)),
                                    int(opt["iso"]), int(opt["exposure_ns"])])
        while a_pos < total_samples:
            s1 = min(a_pos + AUDIO_CHUNK, total_samples)
            af = av.AudioFrame.from_ndarray(audio_chunk(a_pos, s1).reshape(1, -1), format="flt", layout="mono")
            af.sample_rate = AUDIO_FS
            af.pts = a_pos
            af.time_base = a_tb
            for pk in aus.encode(af):
                container.mux(pk)
            a_pos = s1
        for pk in vs.encode():
            container.mux(pk)
        for pk in aus.encode():
            container.mux(pk)
    finally:
        container.close()

    extra = dict(meta_extra or {})
    start_wall_ns = int(wall0_ns + round((offset_s + float(opt["phone_wall_err_s"])) * 1e9))
    meta = {
        "app": "custom_camera2" if opt["custom_recorder"] else opt["app"], "device_model": opt["device_model"], "os_build": opt["os_build"],
        "resolution": [w, h], "fps_nominal": float(fps), "bitrate_mbps": float(opt["bitrate_mbps"]), "iso": int(opt["iso"]),
        "exposure_ns": int(opt["exposure_ns"]), "wb_locked": True, "focus_locked": True, "stabilisation": False, "hdr": False,
        "torch": "on" if torch else "off", "capture_mode": extra.get("capture_mode", cfg.get("study.capture_mode")),
        "start_wall_ns": start_wall_ns, "led_block": dict(view["led_block"]), "study_id": extra.get("study_id", "SWHT-PP-003-0000"),
        "clip_id": clip_id, "codec": "h264", "crf": crf, "synthetic": True,
    }
    (out_dir / f"{clip_id}_meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    if opt["custom_recorder"]:
        with open(out_dir / f"{clip_id}_frames.csv", "w", newline="", encoding="utf-8") as fh:
            cw = csv.writer(fh)
            cw.writerow(["frame_idx", "sensor_ts_ns", "wall_ns", "iso", "exposure_ns"])
            cw.writerows(frames_rows)
    truth = {
        "clip_id": clip_id, "study_id": meta["study_id"], "camera": "phone", "fps": float(fps), "n_frames": n_frames,
        "size": [w, h], "crf": crf, "torch": torch, "pts_s": pts.tolist(), "t_ref_s": t_ref.tolist(),
        "clock_map": {"stream": "phone_video", "offset_s": float(offset_s), "drift": float(drift), "method": "synthetic_truth"},
        "waveform_at_frames": w_all.tolist(), "led_intervals_pts_s": led_pts, "beep_intervals_pts_s": beep_pts,
        "led_schedule_ref_s": schedule, "thumb_contact_pts_s": (contact_s - offset_s) / (1 + drift),
        "thumb_lift_pts_s": ((lift_s - offset_s) / (1 + drift)) if lift_s is not None else None,
        "thumb_down_pts_s": ((lift_s + lift_dur - offset_s) / (1 + drift)) if lift_s is not None else None,
        "vfr_jitter_ms": float(opt["vfr_jitter_ms"]), "led_block": dict(view["led_block"]), "exposure_s": exposure_s,
        "audio": {"fs": AUDIO_FS, "tone_hz": tone_hz, "level": level, "ramp_s": ramp, "noise_dbfs": float(opt["audio_noise_dbfs"]),
                  "acoustic_delay_s": delay}, "phone_wall_err_s": float(opt["phone_wall_err_s"]), "start_wall_ns": start_wall_ns,
        "homography": view["homography"].tolist(), "perspective": float(opt["perspective"]), "colour_space": "srgb_8bit",
        "ac_dc_g": ac_dc_g, "ac_ratios": {"R": rt[0], "G": rt[1], "B": rt[2]}, "hr_bpm": float(truth_pulse["hr_bpm"]),
        "foot_t_ref_s": [float(v) for v in truth_pulse["foot_t"]], "melanin": scene.melanin, "tone_label": scene.tone_label,
        "custom_recorder": bool(opt["custom_recorder"]),
    }
    (out_dir / f"{clip_id}_truth.json").write_text(json.dumps(truth, indent=1, default=_json_default), encoding="utf-8")
    return truth


def write_phone_flatfield(path: str | Path, size: tuple[int, int], fps: float, seconds: float, cfg, rng: np.random.Generator,
                          crf: int | None = None) -> Path:
    """Phone flat field: the white card under the box light through the phone vignette (section 5, weekly per
    unit). Video only, H.264, same encoder settings as the clips."""
    import av

    w, h = int(size[0]), int(size[1])
    crf = int(cfg.get("synth.phone_crf")) if crf is None else int(crf)
    X, Y = ps._grid(w, h)
    cx, cy = 0.5 * w / h + 0.03, 0.5 - 0.02
    illum = (1.0 / (1.0 + ((X - cx) ** 2 + (Y - cy) ** 2) / (2.6 * 2.6))) ** 2
    illum = (illum / illum[h // 2, w // 2]).astype(np.float32)
    lin = np.stack([illum * 0.78, illum * 0.78, illum * 0.76], axis=-1)
    lut = _srgb_lut()
    path = Path(path)
    container = av.open(str(path), "w")
    vs = container.add_stream("libx264", rate=int(round(fps)))
    vs.width, vs.height, vs.pix_fmt = w, h, "yuv420p"
    vs.options = {"crf": str(crf), "preset": "veryfast"}
    try:
        for _ in range(int(round(seconds * fps))):
            noisy = ps.shot_read_noise(lin, 3000.0, 0.004, rng)
            rgb8 = np.take(lut, (np.clip(noisy, 0.0, 1.0) * (lut.size - 1)).astype(np.int16))
            for pk in vs.encode(av.VideoFrame.from_ndarray(np.ascontiguousarray(rgb8), format="rgb24")):
                container.mux(pk)
        for pk in vs.encode():
            container.mux(pk)
    finally:
        container.close()
    return path
