"""Raw Bayer capture on the recording Pi with picamera2 (protocol section 4.6).

What it does, in order:
  1. Preflight: free space on the output volume >= ``capture.min_free_gb`` (section 4.6: "refuses to start
     if free space is under 20 GB") and a ``chronyc makestep`` row for this unit dated today in
     ``clock_sync_log.csv`` (section 4.1). Either failure exits with code 2 and a one-line reason.
  2. Camera: fixed exposure, analogue gain, AWB gains, lens position and sensor mode from ``unit_config.yaml``
     (``camera.*``); AE/AWB/AF disabled; optional crop to the aperture rectangle (``camera.roi_crop``).
  3. Capture loop: each request's raw stream buffer is already 10-bit packed CSI-2 (CONTRACTS section 3.1),
     so it is appended to ``<clip_id>.raw`` as is (cropped in the packed domain when a crop is configured),
     with one row per frame in ``<clip_id>_pts.csv`` carrying picamera2's ``SensorTimestamp`` (CLOCK_BOOTTIME,
     the reference clock, D-001) and the wall clock for audit. The sync marker schedule (section 4.2) starts
     from the first frame's SensorTimestamp. The loop stops after ``video_seconds`` of sensor time.
  4. ``<clip_id>_meta.json`` with every CONTRACTS section 3.3 key, plus ``sync_events.csv`` from the marker.

``--simulate`` runs the identical loop on a software source: flat gradient frames at a reduced geometry,
packed with the local packer below, with the LED block painted from the marker's real pin state, paced in
real time; nothing from other work packages is imported. picamera2 and gpiozero are imported lazily.

Frames are never held in memory beyond the one being written; the raw file is streamed.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import logging
import math
import os
import re
import shutil
import sys
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml

from palmppg.capture import register_features
from palmppg.capture.sync_marker import (
    DEFAULT_UNIT_CONFIG,
    SyncMarker,
    build_marker,
    mono_ns,
    sleep_until,
    wall_ns,
)
from palmppg.core.config import Config, load_pipeline_config, rng

log = logging.getLogger(__name__)

APP_VERSION = "capture_pi/0.1.0"
EXIT_OK, EXIT_ERROR, EXIT_PREFLIGHT = 0, 1, 2
PTS_COLUMNS: tuple[str, ...] = ("frame_idx", "sensor_ts_ns", "wall_ns", "exposure_us", "analogue_gain", "digital_gain", "lux")
META_KEYS: tuple[str, ...] = (
    "unit_id", "operator", "dept", "stream", "app_ver", "study_id", "clip_id", "width", "height", "stride_bytes",
    "bayer_pattern", "bit_depth", "fps_nominal", "crop_rect", "exposure_us", "analogue_gain", "digital_gain",
    "awb_gains", "lens_position", "led_current_ma", "lux", "sensor_temp_c", "start_wall_ns", "stop_wall_ns",
    "start_mono_ns", "stop_mono_ns", "live_sqi", "motion_flag", "recovery_gate", "video_seconds", "capture_mode",
    "n_frames_written", "led_block", "thumb_block",
)
PIXELS_PER_GROUP, BYTES_PER_GROUP, MAX_10BIT = 4, 5, 1023
# Fallbacks for keys unit_config.yaml may lack (not protocol quantities; see DECISIONS report).
DEFAULTS = {
    "simulate_size": (384, 216),       # 1/4 of 1536x864, same aspect, same packing (D-012 geometry)
    "motion_energy_dn_max": 8.0,       # 10-bit DN of mean |frame difference| above which motion_flag is set
    "motion_subsample": 8,             # evaluate the motion proxy on every 8th row and column
    "warmup_frames": 5,                # requests discarded before the first written frame (hardware only)
    "sim_noise_dn": 1.0,               # per-pixel Gaussian noise of the simulated frames, 10-bit DN
}


class PreflightError(RuntimeError):
    """A refusal to start (free space, clock step); maps to exit code 2."""


# --------------------------------------------------------------------------- packing (local copy, CONTRACTS 3.1)
def default_stride(width: int) -> int:
    """Row stride for a 10-bit packed row: ceil(width * 10 / 8) rounded up to a multiple of 32 (1536 -> 1920)."""
    return int(math.ceil(math.ceil(int(width) * 10 / 8) / 32.0) * 32)


def pack_csi2p_10bit(frame: np.ndarray, stride_bytes: int | None = None) -> bytes:
    """Pack one (H, W) uint16 frame (0..1023) as CSI-2 10-bit: 4 pixels in 5 bytes, zero stride padding.

    Bytes 0..3 hold the high 8 bits of pixels 0..3; byte 4 holds the low 2 bits (bits 0-1 px0 ... 6-7 px3).
    Local copy of the format in CONTRACTS section 3.1 so the simulator never imports the ingest package.
    """
    f = np.asarray(frame)
    if f.ndim != 2 or f.dtype.kind not in "ui":
        raise ValueError("pack expects a single integer (H, W) frame")
    if f.size and int(f.max()) > MAX_10BIT:
        raise ValueError("values above 1023 cannot be packed into 10 bits")
    f = f.astype(np.uint16, copy=False)
    height, width = f.shape
    stride = int(stride_bytes) if stride_bytes is not None else default_stride(width)
    n_groups = math.ceil(width / PIXELS_PER_GROUP)
    padded = np.zeros((height, n_groups * PIXELS_PER_GROUP), dtype=np.uint16)
    padded[:, :width] = f
    grp = padded.reshape(height, n_groups, PIXELS_PER_GROUP)
    out = np.zeros((height, stride), dtype=np.uint8)
    body = out[:, : n_groups * BYTES_PER_GROUP].reshape(height, n_groups, BYTES_PER_GROUP)
    body[:, :, :PIXELS_PER_GROUP] = (grp >> 2).astype(np.uint8)
    low = grp & 0x3
    body[:, :, PIXELS_PER_GROUP] = (low[:, :, 0] | (low[:, :, 1] << 2) | (low[:, :, 2] << 4) | (low[:, :, 3] << 6)).astype(np.uint8)
    return out.tobytes()


def snap_crop(crop: Mapping, width: int, height: int) -> dict:
    """Align a crop rectangle to the packing/Bayer grid: x, w to multiples of 4; y, h to even; clipped to the frame.

    x and y move down, w and h grow, so the requested aperture is always inside the written frame.
    """
    x = max(0, (int(crop["x"]) // 4) * 4)
    y = max(0, (int(crop["y"]) // 2) * 2)
    w = int(math.ceil(int(crop["w"]) / 4.0) * 4)
    h = int(math.ceil(int(crop["h"]) / 2.0) * 2)
    w = min(w, width - x)
    h = min(h, height - y)
    if w <= 0 or h <= 0:
        raise ValueError(f"crop {dict(crop)} lies outside a {width}x{height} frame")
    return {"x": x, "y": y, "w": w, "h": h}


def crop_packed(buf, width: int, height: int, stride_bytes: int, crop: Mapping) -> tuple[bytes, int, int, int]:
    """Crop a packed frame to an aligned rectangle without unpacking; returns (bytes, w, h, new_stride).

    Columns are cut on packed byte groups (x and w multiples of 4 pixels), rows on even indices so the Bayer
    phase (RGGB) of the written frame is unchanged. Serves section 4.6 (optional sensor crop to the aperture).
    """
    c = snap_crop(crop, width, height)
    a = np.frombuffer(buf, dtype=np.uint8) if not isinstance(buf, np.ndarray) else buf.reshape(-1).view(np.uint8)
    a = a[: height * stride_bytes].reshape(height, stride_bytes)
    xb, nb = c["x"] * BYTES_PER_GROUP // PIXELS_PER_GROUP, c["w"] * BYTES_PER_GROUP // PIXELS_PER_GROUP
    new_stride = default_stride(c["w"])
    out = np.zeros((c["h"], new_stride), dtype=np.uint8)
    out[:, :nb] = a[c["y"]: c["y"] + c["h"], xb: xb + nb]
    return out.tobytes(), c["w"], c["h"], new_stride


def high_bytes_subsampled(buf, width: int, height: int, stride_bytes: int, step: int) -> np.ndarray:
    """The high 8 bits of every ``step``-th pixel on every ``step``-th row, straight from the packed buffer.

    No unpacking and no demosaic: bytes 0..3 of each 5-byte group are the top 8 bits of 4 pixels.
    Used for the frame-difference motion proxy (CONTRACTS 3.3 ``motion_flag``).
    """
    a = np.frombuffer(buf, dtype=np.uint8) if not isinstance(buf, np.ndarray) else buf.reshape(-1).view(np.uint8)
    a = a[: height * stride_bytes].reshape(height, stride_bytes)[::step]
    n_groups = math.ceil(width / PIXELS_PER_GROUP)
    hi = a[:, : n_groups * BYTES_PER_GROUP].reshape(a.shape[0], n_groups, BYTES_PER_GROUP)[:, :, :PIXELS_PER_GROUP]
    return hi.reshape(a.shape[0], n_groups * PIXELS_PER_GROUP)[:, :width][:, ::step].astype(np.int16)


def motion_energy_dn(prev_hi: np.ndarray, cur_hi: np.ndarray, mask: np.ndarray | None = None) -> float:
    """Mean absolute frame difference in 10-bit DN (high-byte difference x 4) outside ``mask`` (True = excluded)."""
    d = np.abs(cur_hi.astype(np.int16) - prev_hi.astype(np.int16))
    if mask is not None:
        d = d[~mask]
    return float(d.mean()) * 4.0 if d.size else 0.0


def block_mask(width: int, height: int, step: int, block: Mapping | None) -> np.ndarray | None:
    """Boolean mask on the subsampled grid that is True inside ``block`` (the LED, excluded from motion)."""
    if block is None:
        return None
    rows = np.arange(0, height, step)
    cols = np.arange(0, width, step)
    r = (rows >= block["y"]) & (rows < block["y"] + block["h"])
    c = (cols >= block["x"]) & (cols < block["x"] + block["w"])
    return r[:, None] & c[None, :]


# --------------------------------------------------------------------------- preflight (section 4.6 / 4.1)
def free_space_gb(path: str | os.PathLike) -> float:
    """Free space on the volume holding ``path`` in GB (1e9 bytes), via ``shutil.disk_usage``."""
    return shutil.disk_usage(path).free / 1e9


def check_free_space(path: str | os.PathLike, min_free_gb: float) -> dict:
    """``{"ok", "free_gb", "min_free_gb", "path"}``; ok when free space >= ``capture.min_free_gb``."""
    free = free_space_gb(path)
    return {"ok": bool(free >= float(min_free_gb)), "free_gb": round(free, 3), "min_free_gb": float(min_free_gb),
            "path": str(path)}


def read_clock_sync_log(path: str | os.PathLike) -> list[dict]:
    """Rows of ``clock_sync_log.csv`` (CONTRACTS 3.8) as dicts with stripped strings; [] when the file is absent."""
    p = Path(path)
    if not p.exists():
        return []
    with open(p, "r", encoding="utf-8", newline="") as fh:
        return [{k: (v or "").strip() for k, v in row.items() if k} for row in csv.DictReader(fh)]


def last_clock_step(rows: list[dict], unit_id: str) -> dict | None:
    """The last row for device ``pi_<unit_id>`` whose method contains "makestep", or None."""
    device = unit_id if str(unit_id).startswith("pi_") else f"pi_{unit_id}"
    hits = [r for r in rows if r.get("device") == device and "makestep" in r.get("method", "").lower()]
    return hits[-1] if hits else None


def check_clock_stepped_today(clock_log_path: str | os.PathLike, unit_id: str, today: str | None = None) -> dict:
    """Section 4.1 gate: the last ``chronyc makestep`` row for this unit must be dated ``today`` (UTC date).

    Returns ``{"ok", "reason", "last", "today", "path"}``. Missing log, no makestep row for the unit, or a
    row from another day all give ok=False with the reason spelled out.
    """
    today = today or dt.datetime.now(dt.UTC).date().isoformat()
    path = Path(clock_log_path)
    out = {"ok": False, "reason": "", "last": None, "today": today, "path": str(path)}
    if not path.exists():
        out["reason"] = f"no clock sync log at {path}: run clock_sync.sh first"
        return out
    last = last_clock_step(read_clock_sync_log(path), unit_id)
    out["last"] = last
    if last is None:
        out["reason"] = f"no 'makestep' row for pi_{unit_id} in {path}: run clock_sync.sh first"
        return out
    if last.get("date") != today:
        out["reason"] = f"last clock step for pi_{unit_id} is dated {last.get('date')}, not {today}: run clock_sync.sh"
        return out
    out["ok"] = True
    out["reason"] = f"clock stepped {last.get('date')} {last.get('time_utc')} UTC ({last.get('method')})"
    return out


def resolve_clock_log_path(ucfg: Mapping, override: str | os.PathLike | None = None) -> Path:
    """``capture.clock_sync_log`` joined onto ``capture.study_root`` unless absolute (or overridden)."""
    if override is not None:
        return Path(override)
    cap = ucfg.get("capture", {})
    p = Path(str(cap.get("clock_sync_log", "clock_sync_log.csv")))
    return p if p.is_absolute() else Path(str(cap.get("study_root", "."))) / p


def preflight(ucfg: Mapping, out_dir: str | os.PathLike, clock_log_path: str | os.PathLike | None = None,
              today: str | None = None, min_free_gb: float | None = None) -> dict:
    """Run both gates; raise PreflightError (exit code 2) on the first failure; return both results."""
    cap = ucfg.get("capture", {})
    need_gb = float(min_free_gb if min_free_gb is not None else cap.get("min_free_gb", 20))
    space = check_free_space(out_dir, need_gb)
    if not space["ok"]:
        raise PreflightError(f"refusing to start: {space['free_gb']:.2f} GB free on {out_dir}, "
                             f"need >= {need_gb:g} GB (capture.min_free_gb)")
    clock = {"ok": True, "reason": "clock step check disabled by capture.require_clock_step_today", "last": None}
    if bool(cap.get("require_clock_step_today", True)):
        clock = check_clock_stepped_today(resolve_clock_log_path(ucfg, clock_log_path), str(ucfg["unit_id"]), today)
        if not clock["ok"]:
            raise PreflightError(f"refusing to start: {clock['reason']}")
    return {"free_space": space, "clock_step": clock}


# --------------------------------------------------------------------------- camera configuration
def bayer_pattern_from_format(fmt: str) -> str:
    """``SRGGB10_CSI2P`` -> ``RGGB`` (the four-letter Bayer order, CONTRACTS 3.1 ``bayer_pattern``)."""
    s = str(fmt).upper()
    for order in ("RGGB", "BGGR", "GRBG", "GBRG"):
        if order in s:
            return order
    raise ValueError(f"cannot read a Bayer order from sensor format {fmt!r}")


def sensor_bit_depth(fmt: str) -> int:
    """``SRGGB10_CSI2P`` -> 10: how many bits of the 16-bit container an unpacked frame actually carries."""
    m = re.search(r"(\d+)", str(fmt))
    if not m:
        raise ValueError(f"cannot read a bit depth from sensor format {fmt!r}")
    return int(m.group(1))


def unpacked_raw_format(fmt: str) -> str:
    """``SRGGB10_CSI2P`` -> ``SRGGB10``: the unpacked spelling of a raw format, for what we ask libcamera for.

    On a Pi 5 the PiSP front end never hands back CSI-2 packed 10-bit. Ask for ``SRGGB10_CSI2P`` and the
    configured stream comes back as ``BGGR_PISP_COMP1``, a compressed 8-bit-per-pixel format at stride
    ``width``, which no part of the ingest side can read; ask for the unpacked spelling and it comes back as
    ``SBGGR16``, the same sensor values left-shifted into 16 bits with nothing lost. So always request the
    unpacked form and pack to the CONTRACTS 3.1 layout ourselves (see ``Picamera2Source``).
    """
    return re.sub(r"_CSI2P$", "", str(fmt).upper())


def camera_controls(ucfg: Mapping, crop: Mapping | None = None) -> dict:
    """picamera2 control dict for a locked camera (section 4.6): fixed exposure, gain, AWB gains, lens position.

    AE, AWB and AF are off; frame duration is pinned to ``camera.frame_duration_us``; ``AfMode`` is manual
    (libcamera enum value 0). ``ScalerCrop`` is set when a crop is given (it applies to the ISP streams; the
    raw stream is cropped in the packed domain by ``crop_packed``).
    """
    cam = ucfg["camera"]
    fd = int(cam.get("frame_duration_us", round(1e6 / float(cam["sensor_mode"]["fps"]))))
    ctl = {
        "AeEnable": False, "AwbEnable": False,
        "ExposureTime": int(cam["exposure_us"]), "AnalogueGain": float(cam["analogue_gain"]),
        "ColourGains": (float(cam["awb_gains"][0]), float(cam["awb_gains"][1])),
        "AfMode": 0, "LensPosition": float(cam["lens_position"]),
        "FrameDurationLimits": (fd, fd),
    }
    if crop:
        ctl["ScalerCrop"] = (int(crop["x"]), int(crop["y"]), int(crop["w"]), int(crop["h"]))
    return ctl


# --------------------------------------------------------------------------- frame sources
@dataclass
class Frame:
    packed: bytes | np.ndarray           # one packed frame, stride_bytes * height bytes
    sensor_ts_ns: int                    # CLOCK_BOOTTIME ns (reference clock)
    wall_ns: int
    exposure_us: float
    analogue_gain: float
    digital_gain: float
    lux: float | None
    sensor_temp_c: float | None = None


class SimulatedSource:
    """Software stand-in for the camera: gradient frames, LED block from the marker pin, real-time pacing.

    Geometry defaults to 384x216 (1/4 scale of the sensor mode, same packing) so a clip of a few seconds
    is tens of MB. The LED block is painted to 1000 DN while the marker's LED pin reads on, and the thumb
    block drops by ``thumb_step_dn`` once P2 has been emitted (the fine-anchor lift of section 4.3), so the
    written clip carries the same markers a bench recording would. ``drop_frames`` skips those frame
    indices (timestamp gaps, never index gaps) for drop-detection tests.
    """

    def __init__(self, ucfg: Mapping, marker: SyncMarker | None, led_block: Mapping | None,
                 thumb_block: Mapping | None, size: tuple[int, int] | None = None, seed: int = 0,
                 realtime: bool = True, drop_frames: set[int] | None = None, thumb_step_dn: int = 150):
        cam = ucfg["camera"]
        sim = ucfg.get("simulate", {}) or {}
        self.width, self.height = tuple(int(v) for v in (size or sim.get("size") or DEFAULTS["simulate_size"]))
        self.stride = default_stride(self.width)
        self.fps = float(cam["sensor_mode"]["fps"])
        self.period_ns = round(1e9 / self.fps)
        self.marker = marker
        self.led_block = dict(led_block) if led_block else None
        self.thumb_block = dict(thumb_block) if thumb_block else None
        self.exposure_us = float(cam["exposure_us"])
        self.analogue_gain = float(cam["analogue_gain"])
        self.lux = float(ucfg.get("illumination", {}).get("lux_nominal", 0.0))
        self.realtime = bool(realtime)
        self.drop_frames = set(drop_frames or ())
        self.thumb_step_dn = int(thumb_step_dn)
        self.noise_dn = float(sim.get("noise_dn", DEFAULTS["sim_noise_dn"]))
        self._rng = rng(seed, "capture_sim")
        self.base = simulated_base_frame(self.width, self.height)
        self.started = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.started = False

    def frames(self) -> Iterator[Frame]:
        t0 = mono_ns() + self.period_ns
        i = 0
        while self.started:
            target = t0 + i * self.period_ns
            if self.realtime:
                sleep_until(target)
            if i in self.drop_frames:
                i += 1
                continue
            img = self.base.astype(np.int32)
            if self.noise_dn > 0:
                img += np.round(self._rng.normal(0.0, self.noise_dn, img.shape)).astype(np.int32)
            if self.led_block and self.marker is not None and self.marker.led_is_on:
                b = self.led_block
                img[b["y"]: b["y"] + b["h"], b["x"]: b["x"] + b["w"]] = 1000
            if self.thumb_block and self.marker is not None and "P2" in self.marker.emitted:
                b = self.thumb_block
                img[b["y"]: b["y"] + b["h"], b["x"]: b["x"] + b["w"]] -= self.thumb_step_dn
            frame = np.clip(img, 0, MAX_10BIT).astype(np.uint16)
            ts = target if self.realtime else mono_ns()
            yield Frame(pack_csi2p_10bit(frame, self.stride), int(ts), wall_ns(), self.exposure_us,
                        self.analogue_gain, 1.0, self.lux, None)
            i += 1


def simulated_base_frame(width: int, height: int) -> np.ndarray:
    """Deterministic flat gradient (uint16, 10-bit): 128 + 640 * x/(W-1) horizontally, + 64 * y/(H-1) vertically.

    Exposed so tests can compare an unpacked written frame with the known pattern.
    """
    x = np.linspace(0.0, 1.0, int(width), dtype=np.float64)[None, :]
    y = np.linspace(0.0, 1.0, int(height), dtype=np.float64)[:, None]
    return np.round(128.0 + 640.0 * x + 64.0 * y).astype(np.uint16)


class Picamera2Source:
    """picamera2 raw-stream source (hardware only; the import happens here, lazily).

    Configures a video stream with the raw stream at the unit's sensor mode and the locked controls from
    ``camera_controls``; yields each request's raw buffer with its ``SensorTimestamp`` and metadata.
    """

    def __init__(self, ucfg: Mapping, crop: Mapping | None, warmup_frames: int):
        from picamera2 import Picamera2  # lazy: Pi-only dependency

        cam = ucfg["camera"]
        self.picam2 = Picamera2()
        size = tuple(int(v) for v in cam["sensor_mode"]["size"])
        fmt = str(cam["sensor_mode"]["format"])
        controls = camera_controls(ucfg, crop)
        try:
            from libcamera import controls as lc

            controls["AfMode"] = lc.AfModeEnum.Manual
        except ImportError:  # pragma: no cover - libcamera absent off the Pi
            log.debug("libcamera not importable; AfMode stays the integer manual value")
        cfg = self.picam2.create_video_configuration(main={"size": (640, 360), "format": "YUV420"},
                                                     raw={"size": size, "format": unpacked_raw_format(fmt)},
                                                     controls=controls, buffer_count=6)
        self.picam2.configure(cfg)
        rc = self.picam2.camera_configuration()["raw"]
        actual = str(rc["format"])
        self.width, self.height = int(rc["size"][0]), int(rc["size"][1])
        self.src_stride = int(rc["stride"])
        # The Bayer order comes from the stream libcamera actually configured, never from what the unit
        # config asked for: the imx708 binned modes are BGGR even though the full-resolution mode is RGGB,
        # and recording the requested order would swap red and blue in every plane downstream.
        self.bayer_pattern = bayer_pattern_from_format(actual)
        if self.src_stride >= 2 * self.width:
            # Unpacked 16-bit (SBGGR16 on a Pi 5): the sensor's 10 bits sit in the high bits, so the shift
            # below is lossless. Packing costs about 9 ms a frame on a Pi 5, inside the 33 ms budget.
            self.repack, self.shift = True, 16 - sensor_bit_depth(fmt)
            self.stride = default_stride(self.width)
        elif self.src_stride >= math.ceil(self.width * 10 / 8):
            self.repack, self.shift, self.stride = False, 0, self.src_stride
        else:
            raise RuntimeError(
                f"the camera configured a {actual} stream at stride {self.src_stride} for {self.width} px, "
                f"which is neither unpacked 16-bit nor 10-bit packed (CONTRACTS 3.1). A compressed PiSP "
                f"format cannot be recorded; check the sensor mode in the unit config.")
        self.checked_low_bits = False
        self.fps = float(cam["sensor_mode"]["fps"])
        self.warmup_frames = int(warmup_frames)
        self.started = False

    def to_packed(self, buf) -> bytes:
        """One camera buffer as a CONTRACTS 3.1 packed 10-bit frame, shifting down when the stream is 16-bit."""
        if not self.repack:
            return buf
        a = np.frombuffer(buf, dtype=np.uint8)[: self.height * self.src_stride]
        a = a.reshape(self.height, self.src_stride).view(np.uint16)[:, : self.width]
        if not self.checked_low_bits:
            # Verify once that the bits we are about to drop are the padding we think they are, rather
            # than silently throwing away a least-significant bit of every pixel for a whole study.
            lost = int((a & ((1 << self.shift) - 1)).max()) if self.shift else 0
            if lost:
                raise RuntimeError(f"the low {self.shift} bits of the 16-bit stream are not padding "
                                   f"(max {lost}); shifting down would lose sensor data")
            self.checked_low_bits = True
        return pack_csi2p_10bit(a >> self.shift, self.stride)

    def start(self) -> None:
        self.picam2.start()
        self.started = True
        for _ in range(self.warmup_frames):
            req = self.picam2.capture_request()
            req.release()

    def stop(self) -> None:
        self.started = False
        try:
            self.picam2.stop()
        finally:
            self.picam2.close()

    def frames(self) -> Iterator[Frame]:
        while self.started:
            req = self.picam2.capture_request()
            try:
                md = req.get_metadata()
                buf = self.to_packed(req.make_buffer("raw"))
            finally:
                req.release()
            yield Frame(buf, int(md["SensorTimestamp"]), wall_ns(), float(md.get("ExposureTime", 0)),
                        float(md.get("AnalogueGain", 0.0)), float(md.get("DigitalGain", 1.0)),
                        float(md["Lux"]) if md.get("Lux") is not None else None,
                        float(md["SensorTemperature"]) if md.get("SensorTemperature") is not None else None)


# --------------------------------------------------------------------------- blocks and geometry helpers
def scale_block(block: Mapping | None, sx: float, sy: float, width: int, height: int) -> dict | None:
    """Scale a pixel block to another geometry (even-aligned, at least 4x4, clipped); None if nothing remains."""
    if block is None:
        return None
    x = (round(block["x"] * sx) // 2) * 2
    y = (round(block["y"] * sy) // 2) * 2
    w = max(4, (round(block["w"] * sx) // 2) * 2)
    h = max(4, (round(block["h"] * sy) // 2) * 2)
    x, y = min(x, max(0, width - w)), min(y, max(0, height - h))
    w, h = min(w, width - x), min(h, height - y)
    if w <= 0 or h <= 0:
        return None
    return {"x": x, "y": y, "w": w, "h": h}


def translate_block(block: Mapping | None, crop: Mapping | None) -> dict | None:
    """Express a full-frame block in the written (cropped) frame's coordinates; None when it falls outside."""
    if block is None:
        return None
    if not crop:
        return {k: int(block[k]) for k in ("x", "y", "w", "h")}
    x0, y0 = int(block["x"]) - int(crop["x"]), int(block["y"]) - int(crop["y"])
    x1, y1 = min(x0 + int(block["w"]), int(crop["w"])), min(y0 + int(block["h"]), int(crop["h"]))
    x0, y0 = max(x0, 0), max(y0, 0)
    if x1 <= x0 or y1 <= y0:
        log.warning("block %s lies outside crop %s; recorded as null", dict(block), dict(crop))
        return None
    return {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0}


def _median_or_none(values: list) -> float | None:
    v = [float(x) for x in values if x is not None and np.isfinite(x)]
    return float(np.median(v)) if v else None


def _json_default(o):
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return str(o)


# --------------------------------------------------------------------------- the capture loop
def run_capture(source, marker: SyncMarker, out_dir: str | os.PathLike, clip_id: str, video_seconds: float,
                kardia_duration_s: float | None, crop: Mapping | None, meta_static: Mapping,
                led_block: Mapping | None, thumb_block: Mapping | None, motion_threshold_dn: float,
                motion_subsample: int, overwrite: bool = False) -> dict:
    """Stream frames from ``source`` to ``<clip_id>.raw`` + ``<clip_id>_pts.csv`` and write ``<clip_id>_meta.json``.

    The marker schedule starts from the first frame's SensorTimestamp; the loop ends once a frame's sensor
    time is ``video_seconds`` past the first. Each frame is written as it arrives (never buffered as a clip).
    The motion proxy is the median per-frame mean absolute difference of subsampled high bytes outside the
    LED block (10-bit DN); ``motion_flag`` = proxy > ``motion_threshold_dn``. ``live_sqi`` is None until a
    live estimator exists. Returns the meta dict (also written to disk). Serves section 4.6 / CONTRACTS 3.3.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_path, pts_path, meta_path = out_dir / f"{clip_id}.raw", out_dir / f"{clip_id}_pts.csv", out_dir / f"{clip_id}_meta.json"
    if raw_path.exists() and raw_path.stat().st_size > 0 and not overwrite:
        raise FileExistsError(f"{raw_path} exists and is not empty; use a new clip id (clip1b for a re-shoot) or --overwrite")
    src_w, src_h, src_stride = int(source.width), int(source.height), int(source.stride)
    crop_rect = snap_crop(crop, src_w, src_h) if crop else None
    if crop_rect:
        out_w, out_h, out_stride = crop_rect["w"], crop_rect["h"], default_stride(crop_rect["w"])
    else:
        out_w, out_h, out_stride = src_w, src_h, src_stride
    led_out, thumb_out = translate_block(led_block, crop_rect), translate_block(thumb_block, crop_rect)
    mmask = block_mask(out_w, out_h, motion_subsample, led_out)
    period_ns = round(1e9 / float(source.fps))

    t0 = start_wall = None
    n = 0
    prev_hi = None
    energies: list[float] = []
    lux, temps, again, dgain, expo = [], [], [], [], []
    last_ts = None
    source.start()
    try:
        with open(raw_path, "wb", buffering=8 << 20) as raw_fh, open(pts_path, "w", encoding="utf-8", newline="") as pts_fh:
            writer = csv.writer(pts_fh)
            writer.writerow(PTS_COLUMNS)
            for fr in source.frames():
                if t0 is None:
                    t0, start_wall = int(fr.sensor_ts_ns), int(fr.wall_ns)
                    marker.schedule(t0, video_seconds, kardia_duration_s)
                if (int(fr.sensor_ts_ns) - t0) >= round(float(video_seconds) * 1e9):
                    break
                packed = fr.packed
                if crop_rect:
                    packed, _, _, _ = crop_packed(packed, src_w, src_h, src_stride, crop_rect)
                raw_fh.write(packed)
                writer.writerow([n, int(fr.sensor_ts_ns), int(fr.wall_ns), fr.exposure_us, fr.analogue_gain,
                                 fr.digital_gain, "" if fr.lux is None else fr.lux])
                hi = high_bytes_subsampled(packed, out_w, out_h, out_stride, motion_subsample)
                if prev_hi is not None:
                    energies.append(motion_energy_dn(prev_hi, hi, mmask))
                prev_hi = hi
                lux.append(fr.lux)
                temps.append(fr.sensor_temp_c)
                again.append(fr.analogue_gain)
                dgain.append(fr.digital_gain)
                expo.append(fr.exposure_us)
                last_ts = int(fr.sensor_ts_ns)
                n += 1
    finally:
        source.stop()
    stop_mono, stop_wall = mono_ns(), wall_ns()
    marker.wait(timeout_s=max(1.0, 2.0 * (period_ns / 1e9) + 2.0))
    if t0 is None:
        raise RuntimeError("the source produced no frames")
    energy = float(np.median(energies)) if energies else 0.0
    expected = round((last_ts - t0) / period_ns) + 1 if last_ts is not None else n
    meta = dict(meta_static)
    meta.update({
        "clip_id": clip_id, "width": out_w, "height": out_h, "stride_bytes": out_stride,
        "crop_rect": crop_rect, "exposure_us": _median_or_none(expo), "analogue_gain": _median_or_none(again),
        "digital_gain": _median_or_none(dgain), "lux": _median_or_none(lux), "sensor_temp_c": _median_or_none(temps),
        "start_wall_ns": start_wall, "stop_wall_ns": stop_wall, "start_mono_ns": t0, "stop_mono_ns": stop_mono,
        "live_sqi": None, "motion_flag": bool(energy > float(motion_threshold_dn)), "video_seconds": float(video_seconds),
        "n_frames_written": n, "led_block": led_out, "thumb_block": thumb_out,
    })
    meta.setdefault("capture_extra", {})
    meta["capture_extra"].update({
        "motion_energy_dn": energy, "motion_threshold_dn": float(motion_threshold_dn),
        "n_frames_expected_from_timestamps": expected, "n_frames_dropped_est": max(0, expected - n),
        "raw_bytes": raw_path.stat().st_size, "frame_bytes": out_stride * out_h,
        "sync_schedule": marker.schedule_info, "sync_events_csv": str(marker.events_csv_path),
        "all_gpio_ok": all(r["gpio_ok"] for r in marker.rows) if marker.rows else None, "n_sync_rows": len(marker.rows),
    })
    missing = [k for k in META_KEYS if k not in meta]
    if missing:
        raise RuntimeError(f"meta lacks CONTRACTS 3.3 keys {missing}")
    meta_path.write_text(json.dumps(meta, indent=2, default=_json_default), encoding="utf-8")
    return meta


# --------------------------------------------------------------------------- entry point
def load_unit_config(path: str | os.PathLike | None) -> dict:
    """Load ``unit_config.yaml`` (default: configs/unit_config.yaml)."""
    with open(path or DEFAULT_UNIT_CONFIG, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if "unit_id" not in data or "camera" not in data:
        raise ValueError(f"{path}: not a unit config (needs unit_id and camera)")
    return data


def main(config_path: str | os.PathLike | None, study_id: str, clip_id: str, out_dir: str | os.PathLike,
         simulate: bool, video_seconds: float | None = None, operator: str = "", dept: str = "", stream: str = "pilot",
         clock_log_path: str | os.PathLike | None = None, today: str | None = None, min_free_gb: float | None = None,
         recovery_gate: str | None = None, pipeline_cfg: Config | None = None, overwrite: bool = False,
         seed: int | None = None) -> int:
    """Capture one clip. Returns the process exit code: 0 ok, 2 preflight refusal, 1 any other failure.

    ``video_seconds`` overrides ``capture.video_seconds``; ``clock_log_path``/``today``/``min_free_gb`` exist so
    the gates can be exercised without the real study mount. Section 4.6.
    """
    try:
        ucfg = load_unit_config(config_path)
        pcfg = pipeline_cfg if pipeline_cfg is not None else load_pipeline_config()
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        gates = preflight(ucfg, out_dir, clock_log_path, today, min_free_gb)
        log.info("preflight ok: %s; %s", gates["free_space"], gates["clock_step"]["reason"])
    except PreflightError as exc:
        print(f"capture_pi: {exc}", file=sys.stderr)
        return EXIT_PREFLIGHT
    except Exception as exc:  # noqa: BLE001 - entry point: any start-up failure maps to exit code 1
        print(f"capture_pi: cannot start: {exc}", file=sys.stderr)
        return EXIT_ERROR

    try:
        register_features()
        cam, cap = ucfg["camera"], ucfg.get("capture", {})
        seconds = float(video_seconds if video_seconds is not None else cap.get("video_seconds", pcfg.get("study.video_seconds")))
        kardia_s = pcfg.get("study.kardia_duration_s", None)
        crop = cam.get("roi_crop") or None
        full_w, full_h = (int(v) for v in cam["sensor_mode"]["size"])
        led_block = ucfg.get("led", {}).get("block_px") or pcfg.get("sync.led_block.pi", None)
        thumb_block = ucfg.get("thumb_block_px") or pcfg.get("sync.thumb_block.pi", None)
        motion_thr = float(cap.get("motion_energy_dn_max", DEFAULTS["motion_energy_dn_max"]))
        motion_sub = int(cap.get("motion_subsample", DEFAULTS["motion_subsample"]))
        events_path = out_dir / ("sync_events.csv" if clip_id == "clip1" else f"sync_events_{clip_id}.csv")
        marker = build_marker(ucfg, events_path, simulate=simulate)
        try:
            if simulate:
                size = tuple(int(v) for v in (ucfg.get("simulate", {}) or {}).get("size", DEFAULTS["simulate_size"]))
                sx, sy = size[0] / full_w, size[1] / full_h
                led_block = scale_block(led_block, sx, sy, size[0], size[1])
                thumb_block = scale_block(thumb_block, sx, sy, size[0], size[1])
                crop = scale_block(crop, sx, sy, size[0], size[1]) if crop else None
                source = SimulatedSource(ucfg, marker, led_block, thumb_block, size=size,
                                         seed=int(seed if seed is not None else pcfg.get("study.seed", 0)))
            else:
                source = Picamera2Source(ucfg, crop, int(cap.get("warmup_frames", DEFAULTS["warmup_frames"])))
            meta_static = {
                "unit_id": ucfg["unit_id"], "operator": operator, "dept": dept, "stream": stream, "app_ver": APP_VERSION,
                "study_id": study_id,
                "bayer_pattern": getattr(source, "bayer_pattern", None) or bayer_pattern_from_format(cam["sensor_mode"]["format"]),
                "bit_depth": 10, "fps_nominal": float(cam["sensor_mode"]["fps"]), "awb_gains": [float(v) for v in cam["awb_gains"]],
                "lens_position": float(cam["lens_position"]), "led_current_ma": cap.get("box_led_current_ma"),
                "recovery_gate": recovery_gate, "capture_mode": str(ucfg.get("phone", {}).get("capture_mode", pcfg.get("study.capture_mode"))),
                "simulated": bool(simulate), "capture_extra": {"preflight": gates, "sensor_mode": dict(cam["sensor_mode"]),
                                                                 "controls": {k: list(v) if isinstance(v, tuple) else v
                                                                              for k, v in camera_controls(ucfg, crop).items()}},
            }
            meta = run_capture(source, marker, out_dir, clip_id, seconds, kardia_s, crop, meta_static, led_block,
                               thumb_block, motion_thr, motion_sub, overwrite=overwrite)
        finally:
            marker.close()
        print(json.dumps({"clip_id": clip_id, "n_frames_written": meta["n_frames_written"], "width": meta["width"],
                          "height": meta["height"], "stride_bytes": meta["stride_bytes"], "motion_flag": meta["motion_flag"],
                          "n_sync_rows": meta["capture_extra"]["n_sync_rows"], "out_dir": str(out_dir)}))
        return EXIT_OK
    except Exception as exc:
        log.exception("capture failed")
        print(f"capture_pi: capture failed: {exc}", file=sys.stderr)
        return EXIT_ERROR


def cli(argv: list[str] | None = None) -> int:
    """``python -m palmppg.capture.capture_pi --study-id ID --out-dir DIR [--simulate] [--video-seconds N] ...``"""
    ap = argparse.ArgumentParser(description="SWHT-PP-003 Pi raw capture (section 4.6)")
    ap.add_argument("--config", default=str(DEFAULT_UNIT_CONFIG), help="unit_config.yaml")
    ap.add_argument("--study-id", required=True)
    ap.add_argument("--clip-id", default="clip1")
    ap.add_argument("--out-dir", required=True, help="participant pi/ directory")
    ap.add_argument("--simulate", action="store_true")
    ap.add_argument("--video-seconds", type=float, default=None)
    ap.add_argument("--operator", default="")
    ap.add_argument("--dept", default="")
    ap.add_argument("--stream", default="pilot")
    ap.add_argument("--clock-log", default=None, help="override capture.study_root/capture.clock_sync_log")
    ap.add_argument("--today", default=None, help="UTC date YYYY-MM-DD (default: now)")
    ap.add_argument("--min-free-gb", type=float, default=None)
    ap.add_argument("--recovery-gate", default=None)
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    return main(args.config, args.study_id, args.clip_id, args.out_dir, args.simulate, args.video_seconds,
                args.operator, args.dept, args.stream, args.clock_log, args.today, args.min_free_gb,
                args.recovery_gate, overwrite=args.overwrite, seed=args.seed)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(cli())
