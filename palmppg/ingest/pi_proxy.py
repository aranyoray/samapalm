"""Pi frames -> the `pi_proxy` camera stream: 8-bit sRGB, H.264 CRF-encoded mp4 that the phone pipeline then ingests.

DECISIONS D-006: `pi_proxy` is how Pi data feeds `product_candidate` models ("Pi features restricted to what a
phone can produce": demosaiced, white balanced, gamma encoded, chroma subsampled, compressed; no raw, no ECG).
Protocol section 9 (two tracks) and section 8 (compression and resolution transforms, H.264 CRF). Every Pi frame
is demosaiced at full resolution with OpenCV on the calibrated uint16 mosaic and piped raw into ffmpeg (libx264,
yuv420p, `-crf` from cfg `phone.proxy_crf`). Streamed: one frame at a time, nothing cached in RAM.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Mapping
from pathlib import Path

import numpy as np

from palmppg.ingest.bayer import BayerClipReader, merge_planes, split_planes


def cv2_bayer_code(pattern: str) -> int:
    """OpenCV demosaic code for a Bayer pattern name (explicit `COLOR_Bayer<PATTERN>2RGB` names, pattern = top-left 2x2). D-006 proxy demosaic."""
    import cv2

    p = str(pattern).upper()
    names = {"RGGB": "COLOR_BayerRGGB2RGB", "BGGR": "COLOR_BayerBGGR2RGB", "GRBG": "COLOR_BayerGRBG2RGB", "GBRG": "COLOR_BayerGBRG2RGB"}
    if p not in names:
        raise ValueError(f"unknown Bayer pattern {pattern!r}")
    return int(getattr(cv2, names[p]))


def demosaic_full_srgb(mosaic_corrected: np.ndarray, pattern: str, white_span: float, awb_gains: tuple[float, float] = (1.0, 1.0),
                       gamma: float = 2.2) -> np.ndarray:
    """Full-resolution demosaic of a dark-subtracted float mosaic -> (H, W, 3) uint8 sRGB-like frame.

    The mosaic is scaled so that `white_span` (white minus black level) maps to 1.0, quantised to 16 bits for
    OpenCV's bilinear demosaic, white balanced with (r_gain, b_gain) and encoded with a power-law gamma. This is
    the phone-like rendering of a Pi frame (D-006); it is never used for pulse extraction on the `pi` camera.
    """
    import cv2

    m = np.asarray(mosaic_corrected, dtype=np.float32)
    scaled = np.clip(m / np.float32(white_span), 0.0, 1.0)
    u16 = np.round(scaled * 65535.0).astype(np.uint16)
    rgb = cv2.cvtColor(u16, cv2_bayer_code(pattern)).astype(np.float32) / np.float32(65535.0)
    gains = np.array([float(awb_gains[0]), 1.0, float(awb_gains[1])], dtype=np.float32)
    rgb = np.clip(rgb * gains, 0.0, 1.0)
    if gamma and gamma != 1.0:
        rgb = np.power(rgb, np.float32(1.0 / float(gamma)), dtype=np.float32)
    return np.round(rgb * 255.0).astype(np.uint8)


def _ffmpeg_bin() -> str:
    exe = shutil.which("ffmpeg")
    if exe is None:
        raise RuntimeError("ffmpeg not found on PATH")
    return exe


def make_pi_proxy(reader: BayerClipReader, calibration, meta: Mapping, out_mp4: str | os.PathLike, crf: int,
                  size: tuple[int, int] | None = None, chunk: int = 64, t_ref_s=None, fps: float | None = None,
                  black_level: float | None = None, white_level: float | None = None,
                  awb_gains: tuple[float, float] | None = None, gamma: float = 2.2, preset: str = "medium",
                  n_frames: int | None = None) -> dict:
    """Encode every Pi frame of `reader` into `out_mp4` (H.264 libx264, yuv420p, `-crf crf`) as the pi_proxy stream. D-006 and section 9 product_candidate track.

    `calibration` is a `UnitCalibration` (or None: black level `black_level` is subtracted); `crf` is cfg
    `phone.proxy_crf`; `fps` defaults to meta `fps_nominal`; `awb_gains` default to meta `awb_gains`;
    `size=(w, h)` optionally downsizes (even dimensions, INTER_AREA). Returns {path, n_frames, width, height,
    crf, fps, frame_times} where `frame_times` are the Pi frame times passed in (`t_ref_s`): the proxy has
    exactly one frame per Pi frame, so its times are the Pi times, not the container's nominal PTS.
    """
    import cv2

    out_mp4 = Path(out_mp4)
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    n_total = reader.n_frames if n_frames is None else min(int(n_frames), reader.n_frames)
    if n_total <= 0:
        raise ValueError("no frames to encode")
    if white_level is None:
        white_level = float((1 << int(meta.get("bit_depth", 10))) - 1)
    if black_level is None:
        black_level = float(meta.get("black_level", 0.0))
    if awb_gains is None:
        g = meta.get("awb_gains") or (1.0, 1.0)
        awb_gains = (float(g[0]), float(g[1]))
    if fps is None:
        fps = float(meta.get("fps_nominal") or 30.0)
    span = float(white_level) - float(black_level)
    if span <= 0:
        raise ValueError("white_level must exceed black_level")
    applied = calibration is not None and bool(getattr(calibration, "applied", True))
    pattern = reader.pattern
    w_out, h_out = reader.width, reader.height
    if size is not None:
        w_out, h_out = int(size[0]), int(size[1])
    if w_out % 2 or h_out % 2:
        raise ValueError("yuv420p needs even output dimensions")
    t = None if t_ref_s is None else [float(x) for x in np.asarray(t_ref_s, dtype=float).reshape(-1)[:n_total]]
    cmd = [_ffmpeg_bin(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w_out}x{h_out}",
           "-r", f"{fps:.6f}", "-i", "pipe:0", "-an", "-c:v", "libx264", "-preset", preset, "-crf", str(int(crf)),
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out_mp4)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    written = 0
    try:
        for idx, planes in reader.iter_chunks(chunk=chunk, stop=n_total):
            for j in range(idx.size):
                single = {k: v[j] for k, v in planes.items()}
                if calibration is not None:
                    corrected = calibration.apply(single)
                else:
                    corrected = {k: np.asarray(v, dtype=np.float32) - np.float32(black_level) for k, v in single.items()}
                mosaic = merge_planes(corrected, pattern)
                rgb = demosaic_full_srgb(mosaic, pattern, span, awb_gains, gamma)
                if (w_out, h_out) != (reader.width, reader.height):
                    rgb = cv2.resize(rgb, (w_out, h_out), interpolation=cv2.INTER_AREA)
                proc.stdin.write(np.ascontiguousarray(rgb).tobytes())
                written += 1
    finally:
        proc.stdin.close()
        err = proc.stderr.read().decode("utf-8", "ignore") if proc.stderr else ""
        rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"ffmpeg failed (rc={rc}) writing {out_mp4}: {err.strip()}")
    return {"path": str(out_mp4), "camera": "pi_proxy", "n_frames": int(written), "width": w_out, "height": h_out,
            "crf": int(crf), "fps": float(fps), "codec": "h264", "pix_fmt": "yuv420p", "gamma": float(gamma),
            "awb_gains": [float(awb_gains[0]), float(awb_gains[1])], "calibration_applied": applied,
            "frame_times": t, "colour_space": "srgb_8bit_h264"}


def demosaic_mosaic_preview(mosaic_uint16: np.ndarray, pattern: str, black_level: float, white_level: float,
                            awb_gains: tuple[float, float] = (1.0, 1.0), gamma: float = 2.2) -> np.ndarray:
    """Convenience: raw uint16 mosaic -> full-resolution uint8 sRGB-like frame (black level subtracted first). Section 6.1 hand-landmark preview at full resolution."""
    planes = split_planes(mosaic_uint16, pattern)
    corrected = {k: np.asarray(v, dtype=np.float32) - np.float32(black_level) for k, v in planes.items()}
    return demosaic_full_srgb(merge_planes(corrected, pattern), pattern, float(white_level) - float(black_level), awb_gains, gamma)
