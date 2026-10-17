"""Synthetic fixtures shared by the ingest tests (no tests in this file).

Everything here is built from known parameters so tests can check numbers against ground truth:
packed Bayer clips with known plane levels, a cos^4 vignette, chosen dropped frames and sensor timestamps;
unit dark/flat frames; tiny mp4s rendered with ffmpeg (CFR, VFR, with a buzzer tone, shifted per frame).
"""
from __future__ import annotations

import csv
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np

from palmppg.core.config import rng
from palmppg.ingest.bayer import default_stride, merge_planes, pack_csi2p_10bit

FFMPEG = shutil.which("ffmpeg")
BLACK = 64
WHITE = 1023


def vignette_map(h: int, w: int, strength: float = 0.35) -> np.ndarray:
    """Radial cos^4-like falloff in [1 - strength, 1] over a (h, w) plane (centre = 1)."""
    yy, xx = np.mgrid[0:h, 0:w]
    cy, cx = (h - 1) / 2.0, (w - 1) / 2.0
    r = np.sqrt(((yy - cy) / max(cy, 1)) ** 2 + ((xx - cx) / max(cx, 1)) ** 2) / np.sqrt(2.0)
    return (1.0 - strength * r**2).astype(np.float32)


def make_mosaic(levels: dict[str, float], h: int, w: int, vignette: np.ndarray | None, gen: np.random.Generator,
                noise_sd: float = 1.5, black: float = BLACK, pattern: str = "RGGB") -> np.ndarray:
    """RGGB mosaic (h, w) uint16 with per-plane signal `levels` (above black) times the vignette plus Gaussian noise."""
    planes = {}
    for k in ("R", "G1", "G2", "B"):
        sig = np.full((h // 2, w // 2), float(levels[k]), dtype=np.float32)
        if vignette is not None:
            sig = sig * vignette
        p = black + sig + gen.normal(0.0, noise_sd, size=sig.shape).astype(np.float32)
        planes[k] = np.clip(np.round(p), 0, WHITE).astype(np.uint16)
    return merge_planes(planes, pattern)


def write_unit_calibration(unit_dir: Path, width: int, height: int, strength: float = 0.35, flat_level: float = 600.0,
                           seed: int = 1, black: float = BLACK, luxmap: bool = True) -> dict:
    """Write darkframe.raw (black + noise) and flatfield.raw (white card x vignette) for the clip geometry."""
    unit_dir.mkdir(parents=True, exist_ok=True)
    gen = rng(seed, "unit")
    vig = vignette_map(height // 2, width // 2, strength)
    dark = make_mosaic({"R": 0, "G1": 0, "G2": 0, "B": 0}, height, width, None, gen, noise_sd=1.0, black=black)
    flat = make_mosaic({"R": flat_level * 0.8, "G1": flat_level, "G2": flat_level, "B": flat_level * 0.7}, height, width, vig, gen,
                       noise_sd=2.0, black=black)
    (unit_dir / "darkframe.raw").write_bytes(pack_csi2p_10bit(dark))
    (unit_dir / "flatfield.raw").write_bytes(pack_csi2p_10bit(flat))
    if luxmap:
        (unit_dir / "luxmap.json").write_text(json.dumps({"lux_grid": [[400, 410], [395, 405]], "rows": 2, "cols": 2}))
    return {"vignette": vig, "dark": dark, "flat": flat, "strength": strength}


def write_synthetic_pi_clip(pi_dir: Path, clip_id: str = "clip1", width: int = 192, height: int = 108, n_frames: int = 90,
                            fps: float = 30.0, seed: int = 7, dropped: tuple[int, ...] = (), levels: dict | None = None,
                            strength: float = 0.35, black: float = BLACK, t0_ns: int = 5_000_000_000, stride_bytes: int | None = None,
                            modulation=None, study_id: str = "SWHT-PP-003-0001", unit_id: str = "unit_01", led_block=None) -> dict:
    """Write <clip>.raw, <clip>_pts.csv and <clip>_meta.json. Frames listed in `dropped` are neither written nor logged.

    `modulation(i)` optionally returns a multiplicative factor for frame i (pulse, flicker, drift injection).
    Returns ground truth: kept frame indices, their sensor_ts_ns, the vignette and the plane levels.
    """
    pi_dir.mkdir(parents=True, exist_ok=True)
    gen = rng(seed, "clip")
    levels = levels or {"R": 500.0, "G1": 400.0, "G2": 400.0, "B": 300.0}
    vig = vignette_map(height // 2, width // 2, strength)
    stride = stride_bytes or default_stride(width)
    period_ns = round(1e9 / fps)
    kept = [i for i in range(n_frames) if i not in set(dropped)]
    raw_path = pi_dir / f"{clip_id}.raw"
    rows = []
    with open(raw_path, "wb") as fh:
        for i in kept:
            f = 1.0 if modulation is None else float(modulation(i))
            lv = {k: v * f for k, v in levels.items()}
            fh.write(pack_csi2p_10bit(make_mosaic(lv, height, width, vig, gen, black=black), stride))
            ts = t0_ns + i * period_ns
            rows.append([i, ts, 1_760_000_000_000_000_000 + ts, 8000, 2.0, 1.0, 400.0])
    with open(pi_dir / f"{clip_id}_pts.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["frame_idx", "sensor_ts_ns", "wall_ns", "exposure_us", "analogue_gain", "digital_gain", "lux"])
        w.writerows(rows)
    meta = {
        "unit_id": unit_id, "operator": "op1", "dept": "Cardio OPD", "stream": "pilot", "app_ver": "0.1", "study_id": study_id,
        "clip_id": clip_id, "width": width, "height": height, "stride_bytes": stride, "bayer_pattern": "RGGB", "bit_depth": 10,
        "fps_nominal": fps, "crop_rect": None, "exposure_us": 8000, "analogue_gain": 2.0, "digital_gain": 1.0,
        "awb_gains": [1.0, 1.0], "lens_position": 2.5, "led_current_ma": 20, "lux": 400, "sensor_temp_c": 45.0,
        "start_wall_ns": rows[0][2] if rows else 0, "stop_wall_ns": rows[-1][2] if rows else 0,
        "start_mono_ns": t0_ns, "stop_mono_ns": t0_ns + (n_frames - 1) * period_ns, "live_sqi": None, "motion_flag": False,
        "recovery_gate": "pass", "video_seconds": n_frames / fps, "capture_mode": "simultaneous",
        "n_frames_written": len(kept), "led_block": led_block or {"x": 8, "y": 8, "w": 16, "h": 16},
        "thumb_block": {"x": 8, "y": height - 24, "w": 40, "h": 16},
    }
    (pi_dir / f"{clip_id}_meta.json").write_text(json.dumps(meta, indent=1))
    return {"meta": meta, "kept": kept, "sensor_ts_ns": [r[1] for r in rows], "vignette": vig, "levels": levels, "t0_ns": t0_ns,
            "period_ns": period_ns, "raw": raw_path}


def render_mp4(path: Path, frames, fps: float = 30.0, crf: int = 18, vfr_jitter: float = 0.0, tone_hz: float | None = None,
               tone_s: float | None = None, preset: str = "ultrafast") -> Path:
    """Render uint8 RGB frames (iterable of (H, W, 3)) to H.264 mp4 with ffmpeg.

    `vfr_jitter` > 0 alternates frame intervals (1 +/- jitter) x period, producing a genuinely variable frame rate
    through `settb`/`setpts` and an explicit encoder time base. `tone_hz` adds a mono AAC sine of `tone_s` seconds.
    """
    if FFMPEG is None:
        raise RuntimeError("ffmpeg missing")
    frames = list(frames)
    h, w = frames[0].shape[:2]
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", f"{fps}", "-i", "pipe:0"]
    if tone_hz is not None:
        dur = tone_s if tone_s is not None else len(frames) / fps
        cmd += ["-f", "lavfi", "-i", f"sine=frequency={tone_hz}:sample_rate=48000:duration={dur}", "-map", "0:v", "-map", "1:a",
                "-c:a", "aac", "-b:a", "96k"]
    if vfr_jitter > 0:
        tb = 90000
        per = tb / fps
        cmd += ["-vf", f"settb=1/{tb},setpts=(N+{vfr_jitter}*mod(N\\,2))*{per:.3f}", "-fps_mode", "passthrough",
                "-enc_time_base", f"1/{tb}", "-video_track_timescale", str(tb)]
    cmd += ["-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p", str(path)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    for f in frames:
        proc.stdin.write(np.ascontiguousarray(f, dtype=np.uint8).tobytes())
    proc.stdin.close()
    err = proc.stderr.read().decode("utf-8", "ignore")
    if proc.wait() != 0:
        raise RuntimeError(f"ffmpeg failed: {err}")
    return path


def textured_frame(h: int, w: int, gen: np.random.Generator, base: int = 128, contrast: int = 60) -> np.ndarray:
    """Static high-texture RGB frame (random blobs smoothed) that optical flow can track everywhere."""
    import cv2

    noise = gen.integers(0, 256, size=(h // 4, w // 4, 3), dtype=np.uint8)
    up = cv2.resize(noise, (w, h), interpolation=cv2.INTER_CUBIC)
    f = base + (up.astype(np.float32) - 128.0) * (contrast / 128.0)
    return np.clip(f, 0, 255).astype(np.uint8)


def solid_frames(n: int, h: int, w: int, rgb: tuple[int, int, int]) -> list[np.ndarray]:
    f = np.empty((h, w, 3), dtype=np.uint8)
    f[..., 0], f[..., 1], f[..., 2] = rgb
    return [f.copy() for _ in range(n)]
