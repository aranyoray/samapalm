"""Augmentation library: every protocol section 8 transform as a class, a registry and a logged chain.

Protocol section 8 (synthetic augmentation study on the first 100 clips): geometric (rotation, translation,
scale, mild perspective, per-frame micro-jitter), photometric (exposure, illuminant, vignetting gain, moving
shadow), noise (shot noise by lower effective light, read noise, 8-bit quantisation), blur (defocus, motion),
temporal (frame drops, timestamp jitter, variable-frame-rate timestamps, 50 Hz flicker sampled at frame times
so it aliases to 10 Hz at 30 fps), compression and resolution (H.264 / H.265 CRF lists, downscale, chroma
subsampling) and the synthetic skin-tone shift (melanin darkening, every output labelled "synthetic tone shift").

Rules encoded here
  * No temporal smoothing or frame interpolation anywhere: every transform declares
    `temporal_interpolation = False` and `apply_chain` asserts it. Timestamp transforms relabel times, they
    never resample content. (A true variable-frame-rate *capture* exists only in the generator:
    phone_video.write_phone_clip(vfr_jitter_ms=...).)
  * Geometric and photometric transforms are per clip (one parameter draw) unless the transform explicitly
    simulates motion (MicroJitter, MovingShadow), which are per frame.
  * Severity levels come from cfg `augment.*` (three levels; the compression lists have four). Keys the
    pipeline config does not carry yet fall back to DEFAULT_LEVELS and are reported for addition.
  * Parameters are logged per clip by `apply_chain(frames, chain, rng, log)`; temporal transforms also log the
    frame indices they dropped.

Frames: `Frame` holds Bayer planes (4, h/2, w/2) uint16 in the order R, G1, G2, B (CONTRACTS 3.1) or an RGB
image (h, w, 3) (uint8 sRGB, or float32 linear), plus its true capture time `t_s` and index. Photometric
transforms act in linear light (Bayer: DN above black level over the white range; sRGB: inverted transfer).
Compression and chroma transforms need an RGB image; Bayer input is turned into the half-resolution
R, mean(G1, G2), B 8-bit sRGB proxy first (DECISIONS D-006, `pi_proxy`) and the output is labelled so.
"""
from __future__ import annotations

import math
import tempfile
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Iterable, Iterator

import numpy as np

from palmppg.synth.palm_scene import MELANIN_ABSORPTION, TONE_LABEL, srgb_eotf, srgb_oetf

PLANE_NAMES = ("R", "G1", "G2", "B")
DEFAULT_LEVELS = {                     # cfg augment.* keys that pipeline.yaml does not define yet
    "perspective": [0.01, 0.02, 0.04],
    "illuminant_shift": [0.05, 0.10, 0.15],
    "vignetting_gain": [0.10, 0.20, 0.30],
    "moving_shadow": [0.10, 0.20, 0.30],
    "read_noise_frac": [0.002, 0.004, 0.008],
    "quantise_bits": [8],
    "timestamp_jitter_ms": [1.0, 3.0, 10.0],
    "vfr_ms": [0.5, 1.0, 2.0],
    "h265_crf": [18, 23, 28, 35],
    "chroma_subsampling": ["422", "420"],
}


# ----------------------------------------------------------------------------- frames
@dataclass
class Frame:
    data: np.ndarray
    kind: str                       # "bayer" | "rgb"
    t_s: float
    idx: int
    black_level: float = 0.0
    white_level: float = 1.0
    transfer: str = "linear"        # "linear" | "srgb"
    labels: tuple[str, ...] = ()
    meta: dict = field(default_factory=dict)

    @staticmethod
    def bayer(planes: np.ndarray, t_s: float, idx: int, black_level: float = 64.0, white_level: float = 1023.0) -> "Frame":
        planes = np.asarray(planes)
        if planes.ndim != 3 or planes.shape[0] != 4:
            raise ValueError("bayer planes must be (4, h/2, w/2) in the order R, G1, G2, B")
        return Frame(planes, "bayer", float(t_s), int(idx), float(black_level), float(white_level), "linear")

    @staticmethod
    def from_mosaic(mosaic: np.ndarray, t_s: float, idx: int, black_level: float = 64.0, white_level: float = 1023.0) -> "Frame":
        m = np.asarray(mosaic)
        planes = np.stack([m[0::2, 0::2], m[0::2, 1::2], m[1::2, 0::2], m[1::2, 1::2]])
        return Frame.bayer(planes, t_s, idx, black_level, white_level)

    @staticmethod
    def rgb(img: np.ndarray, t_s: float, idx: int) -> "Frame":
        img = np.asarray(img)
        if img.ndim != 3 or img.shape[2] != 3:
            raise ValueError("rgb image must be (h, w, 3)")
        if img.dtype == np.uint8:
            return Frame(img, "rgb", float(t_s), int(idx), 0.0, 255.0, "srgb")
        return Frame(img.astype(np.float32), "rgb", float(t_s), int(idx), 0.0, 1.0, "linear")

    @property
    def shape_hw(self) -> tuple[int, int]:
        return (self.data.shape[1], self.data.shape[2]) if self.kind == "bayer" else (self.data.shape[0], self.data.shape[1])

    def linear(self) -> np.ndarray:
        """Linear light in 0..1 (white = 1), same layout as `data`."""
        x = (self.data.astype(np.float32) - self.black_level) / (self.white_level - self.black_level)
        return srgb_eotf(np.clip(x, 0, 1)) if self.transfer == "srgb" else x

    def with_linear(self, lin: np.ndarray, dither: np.random.Generator | None = None, **changes) -> "Frame":
        """New frame of the same kind/dtype from linear light (clipped, re-encoded, quantised).

        Integer frames are re-quantised with a uniform +/- 0.5 DN dither drawn from `dither` when given: the
        input is already integer, so a small multiplicative change (a pulse of a few tenths of a DN) would
        otherwise round the same way in every pixel and leave a coherent sawtooth error at the pulse rate.
        """
        lin = np.clip(lin, 0.0, 1.0)
        enc = srgb_oetf(lin) if self.transfer == "srgb" else lin
        out = enc * (self.white_level - self.black_level) + self.black_level
        if np.issubdtype(self.data.dtype, np.integer):
            if dither is not None:
                out = out + dither.uniform(-0.5, 0.5, size=out.shape).astype(np.float32)
            out = np.clip(np.rint(out), 0, self.white_level).astype(self.data.dtype)
        else:
            out = out.astype(np.float32)
        return replace(self, data=out, meta=dict(self.meta), **changes)

    def with_data(self, data: np.ndarray, **changes) -> "Frame":
        return replace(self, data=data, **changes)

    def planes(self) -> list[np.ndarray]:
        return [self.data[i] for i in range(4)] if self.kind == "bayer" else [self.data]

    def mosaic(self) -> np.ndarray:
        if self.kind != "bayer":
            raise ValueError("not a Bayer frame")
        h, w = self.data.shape[1] * 2, self.data.shape[2] * 2
        m = np.empty((h, w), self.data.dtype)
        m[0::2, 0::2], m[0::2, 1::2], m[1::2, 0::2], m[1::2, 1::2] = self.data
        return m

    def to_proxy_rgb8(self) -> "Frame":
        """Bayer -> half-resolution R, mean(G1, G2), B, white balanced to the G plane, sRGB 8-bit (pi_proxy)."""
        if self.kind == "rgb":
            return self
        lin = self.linear()
        rgb = np.stack([lin[0], 0.5 * (lin[1] + lin[2]), lin[3]], axis=-1)
        wb = np.array([1.0 / 0.63, 1.0, 1.0 / 0.71], np.float32)     # nominal responsivity (palm_scene default)
        rgb = np.clip(rgb * wb[None, None, :], 0, 1)
        img = (srgb_oetf(rgb) * 255.0 + 0.5).astype(np.uint8)
        return Frame(img, "rgb", self.t_s, self.idx, 0.0, 255.0, "srgb", self.labels + ("pi_proxy",), dict(self.meta))


def frames_from_mosaics(mosaics: Iterable[tuple[int, np.ndarray]], t_s: np.ndarray, black_level: float = 64.0,
                        white_level: float = 1023.0) -> Iterator[Frame]:
    """Wrap (k, mosaic) pairs (e.g. bayer_video.iter_raw_frames) with their true times into Bayer frames."""
    t_s = np.asarray(t_s, dtype=float)
    for k, m in mosaics:
        yield Frame.from_mosaic(m, float(t_s[k]), int(k), black_level, white_level)


def _map_planes(frame: Frame, fn) -> Frame:
    """Apply a 2D (or 3-channel for rgb) image function to every plane and keep dtype."""
    if frame.kind == "bayer":
        out = np.stack([fn(frame.data[i]) for i in range(4)])
    else:
        out = fn(frame.data)
    if np.issubdtype(frame.data.dtype, np.integer):
        out = np.clip(np.rint(out), 0, frame.white_level).astype(frame.data.dtype)
    return frame.with_data(out.astype(frame.data.dtype))


# ----------------------------------------------------------------------------- base
class Transform:
    """Base class: (name, severity_index, params); per-frame mapping with per-clip state drawn once."""

    name = "base"
    levels_key: str | None = None
    level_param: str | None = None
    temporal = False
    changes_frame_count = False
    temporal_interpolation = False      # must stay False everywhere (section 8 rule); apply_chain asserts it
    label: str | None = None
    benign = True                        # expected to keep the pulse rate (section 8 verification list)

    def __init__(self, severity_index: int | None = None, cfg=None, **params):
        self.severity_index = severity_index
        self.params = dict(params)
        self.runtime: dict = {}
        if self.levels_key is not None:
            levels = self.levels(cfg)
            if severity_index is not None:
                if not 0 <= severity_index < len(levels):
                    raise ValueError(f"{self.name}: severity_index {severity_index} outside 0..{len(levels) - 1}")
                self.params.setdefault(self.level_param, levels[severity_index])
            elif self.level_param not in self.params:
                raise ValueError(f"{self.name}: give severity_index or {self.level_param}")
        self.level = self.params.get(self.level_param) if self.level_param else None

    @classmethod
    def levels(cls, cfg=None) -> list:
        default = DEFAULT_LEVELS.get(cls.levels_key, [])
        if cfg is None:
            from palmppg.core.config import load_pipeline_config

            cfg = load_pipeline_config()
        return list(cfg.get(f"augment.{cls.levels_key}", default))

    def describe(self) -> dict:
        d = {"name": self.name, "severity_index": self.severity_index, "params": dict(self.params), "temporal": self.temporal,
             "changes_frame_count": self.changes_frame_count, "runtime": self.runtime}
        if self.label:
            d["label"] = self.label
        return d

    def start(self, first: Frame, rng: np.random.Generator) -> None:
        """Draw per-clip state from the first frame (shape) and rng."""

    def frame(self, f: Frame, rng: np.random.Generator) -> Frame | None:
        return f

    def apply(self, frames: Iterable[Frame], rng: np.random.Generator) -> Iterator[Frame]:
        started = False
        for f in frames:
            if not started:
                self.start(f, rng)
                started = True
            out = self.frame(f, rng)
            if out is None:
                continue
            if self.label:
                out = replace(out, labels=tuple(dict.fromkeys(out.labels + (self.label,))))
            yield out

    def apply_times(self, t_s: np.ndarray, rng: np.random.Generator) -> np.ndarray:
        """Timestamp-vector counterpart for transforms that touch times (identity otherwise)."""
        return np.asarray(t_s, dtype=float).copy()


# ----------------------------------------------------------------------------- geometric
def _warp_affine(img: np.ndarray, M: np.ndarray, border: float) -> np.ndarray:
    import cv2

    h, w = img.shape[:2]
    return cv2.warpAffine(img.astype(np.float32), M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=border)


class Rotate(Transform):
    """In-plane rotation about the frame centre by cfg augment.rotation_deg (per clip; sign drawn once)."""

    name, levels_key, level_param = "Rotate", "rotation_deg", "deg"

    def start(self, first, rng):
        self.runtime["sign"] = int(rng.choice([-1, 1])) if self.params.get("sign") is None else int(self.params["sign"])

    def frame(self, f, rng):
        import cv2

        deg = self.params["deg"] * self.runtime["sign"]

        def fn(img):
            h, w = img.shape[:2]
            M = cv2.getRotationMatrix2D((w / 2 - 0.5, h / 2 - 0.5), deg, 1.0)
            return _warp_affine(img, M, f.black_level)

        return _map_planes(f, fn)


class Translate(Transform):
    """Translation by cfg augment.translation_pct of the width along a per-clip random direction."""

    name, levels_key, level_param = "Translate", "translation_pct", "pct"

    def start(self, first, rng):
        self.runtime["angle_deg"] = float(rng.uniform(0, 360)) if self.params.get("angle_deg") is None else float(self.params["angle_deg"])

    def frame(self, f, rng):
        a = math.radians(self.runtime["angle_deg"])

        def fn(img):
            h, w = img.shape[:2]
            d = self.params["pct"] / 100.0 * w
            M = np.float32([[1, 0, d * math.cos(a)], [0, 1, d * math.sin(a)]])
            return _warp_affine(img, M, f.black_level)

        return _map_planes(f, fn)


class Scale(Transform):
    """Isotropic scale about the centre by cfg augment.scale (0.95 = hand further away)."""

    name, levels_key, level_param = "Scale", "scale", "factor"

    def frame(self, f, rng):
        import cv2

        def fn(img):
            h, w = img.shape[:2]
            M = cv2.getRotationMatrix2D((w / 2 - 0.5, h / 2 - 0.5), 0.0, float(self.params["factor"]))
            return _warp_affine(img, M, f.black_level)

        return _map_planes(f, fn)


class Perspective(Transform):
    """Mild perspective: corners moved by `strength` x frame size (per clip random directions)."""

    name, levels_key, level_param = "Perspective", "perspective", "strength"

    def start(self, first, rng):
        self.runtime["corner_shift"] = rng.uniform(-1, 1, (4, 2)).tolist()

    def frame(self, f, rng):
        import cv2

        s = float(self.params["strength"])
        shift = np.asarray(self.runtime["corner_shift"], np.float32)

        def fn(img):
            h, w = img.shape[:2]
            src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
            dst = src + shift * s * np.float32([w, h])
            H = cv2.getPerspectiveTransform(src, dst)
            return cv2.warpPerspective(img.astype(np.float32), H, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
                                       borderValue=f.black_level)

        return _map_planes(f, fn)


class MicroJitter(Transform):
    """Per-frame translation ~ N(0, cfg augment.jitter_px) in full-resolution pixels (tremor); simulates motion."""

    name, levels_key, level_param = "MicroJitter", "jitter_px", "px"

    def start(self, first, rng):
        self.runtime["n"] = 0
        self.runtime["rms_px"] = 0.0

    def frame(self, f, rng):
        dx, dy = rng.normal(0.0, float(self.params["px"]), 2)
        self.runtime["n"] += 1
        self.runtime["rms_px"] = math.sqrt(((self.runtime["rms_px"] ** 2) * (self.runtime["n"] - 1) + dx * dx + dy * dy) / self.runtime["n"])
        half = 0.5 if f.kind == "bayer" else 1.0

        def fn(img):
            M = np.float32([[1, 0, dx * half], [0, 1, dy * half]])
            return _warp_affine(img, M, f.black_level)

        return _map_planes(f, fn)


# ----------------------------------------------------------------------------- photometric
class ExposureShift(Transform):
    """Exposure change of cfg augment.exposure_ev stops, multiplicative in linear light (sign per clip)."""

    name, levels_key, level_param = "ExposureShift", "exposure_ev", "ev"

    def start(self, first, rng):
        self.runtime["sign"] = int(rng.choice([-1, 1])) if self.params.get("sign") is None else int(self.params["sign"])

    def frame(self, f, rng):
        return f.with_linear(f.linear() * 2.0 ** (self.params["ev"] * self.runtime["sign"]), dither=rng)


class IlluminantShift(Transform):
    """von Kries per-channel scaling toward warmer (R up, B down) or cooler by `strength` (per clip direction)."""

    name, levels_key, level_param = "IlluminantShift", "illuminant_shift", "strength"

    def start(self, first, rng):
        self.runtime["direction"] = self.params.get("direction") or str(rng.choice(["warmer", "cooler"]))

    def frame(self, f, rng):
        s = float(self.params["strength"]) * (1.0 if self.runtime["direction"] == "warmer" else -1.0)
        lin = f.linear()
        if f.kind == "bayer":
            lin = lin.copy()
            lin[0] *= 1.0 + s
            lin[3] *= 1.0 - s
        else:
            lin = lin * np.array([1.0 + s, 1.0, 1.0 - s], np.float32)[None, None, :]
        return f.with_linear(lin, dither=rng)


class VignettingGain(Transform):
    """Extra radial falloff: gain = 1 - strength * (r / r_corner)^2 (per clip)."""

    name, levels_key, level_param = "VignettingGain", "vignetting_gain", "strength"

    def start(self, first, rng):
        h, w = first.shape_hw
        ys, xs = np.mgrid[0:h, 0:w]
        r2 = ((xs - w / 2) ** 2 + (ys - h / 2) ** 2) / ((w / 2) ** 2 + (h / 2) ** 2)
        self.runtime["gain"] = (1.0 - float(self.params["strength"]) * r2).astype(np.float32)

    def frame(self, f, rng):
        g = self.runtime["gain"]
        lin = f.linear()
        return f.with_linear(lin * (g[None] if f.kind == "bayer" else g[..., None]), dither=rng)


class MovingShadow(Transform):
    """A soft shadow edge of depth `depth` sweeping across the frame over `period_s` seconds (per frame, by t_s)."""

    name, levels_key, level_param = "MovingShadow", "moving_shadow", "depth"

    def start(self, first, rng):
        self.runtime["t_first"] = first.t_s
        self.runtime["period_s"] = float(self.params.get("period_s", 20.0))
        self.runtime["direction"] = int(rng.choice([-1, 1]))

    def frame(self, f, rng):
        h, w = f.shape_hw
        phase = ((f.t_s - self.runtime["t_first"]) / self.runtime["period_s"]) % 1.0
        x0 = (-0.2 + 1.4 * phase) * w
        if self.runtime["direction"] < 0:
            x0 = w - x0
        xs = np.arange(w, dtype=np.float32)
        edge = 1.0 / (1.0 + np.exp(-(xs - x0) / (0.08 * w)))
        gain = (1.0 - float(self.params["depth"]) * edge).astype(np.float32)
        lin = f.linear()
        return f.with_linear(lin * (gain[None, None, :] if f.kind == "bayer" else gain[None, :, None]), dither=rng)


# ----------------------------------------------------------------------------- noise
class ShotNoise(Transform):
    """Shot noise of a capture at `light_factor` of the light: adds the variance difference
    lin * (1/light_factor - 1) / full_well_e in linear light (Gaussian draw)."""

    name, levels_key, level_param = "ShotNoise", "shot_noise_light_factor", "light_factor"

    def frame(self, f, rng):
        fw = float(self.params.get("full_well_e", 8000.0 if f.kind == "bayer" else 3000.0))
        lin = f.linear()
        var = np.maximum(lin, 0.0) * (1.0 / float(self.params["light_factor"]) - 1.0) / fw
        return f.with_linear(lin + np.sqrt(var) * rng.standard_normal(lin.shape, dtype=np.float32), dither=rng)


class ReadNoise(Transform):
    """Gaussian read noise with sigma `frac` of the white range, in linear light."""

    name, levels_key, level_param = "ReadNoise", "read_noise_frac", "frac"

    def frame(self, f, rng):
        lin = f.linear()
        return f.with_linear(lin + float(self.params["frac"]) * rng.standard_normal(lin.shape, dtype=np.float32), dither=rng)


class Quantise8bit(Transform):
    """Quantise linear light to `bits` (8) levels over the white range; the frame keeps its container dtype
    (10-bit planes then hold multiples of 4 DN). An 8-bit sRGB frame is unchanged and logged as such."""

    name, levels_key, level_param = "Quantise8bit", "quantise_bits", "bits"

    def frame(self, f, rng):
        if f.kind == "rgb" and f.data.dtype == np.uint8:
            self.runtime["already_8bit"] = True
            return f
        q = 2 ** int(self.params["bits"]) - 1
        lin = np.rint(np.clip(f.linear(), 0, 1) * q) / q
        return f.with_linear(lin)


# ----------------------------------------------------------------------------- blur
class Defocus(Transform):
    """Gaussian blur with sigma cfg augment.defocus_sigma_px (full-resolution px; half on Bayer planes)."""

    name, levels_key, level_param = "Defocus", "defocus_sigma_px", "sigma_px"

    def frame(self, f, rng):
        import cv2

        sigma = float(self.params["sigma_px"]) * (0.5 if f.kind == "bayer" else 1.0)
        k = int(2 * math.ceil(3 * sigma) + 1)
        return _map_planes(f, lambda img: cv2.GaussianBlur(img.astype(np.float32), (k, k), sigma, borderType=cv2.BORDER_REPLICATE))


class MotionBlur(Transform):
    """Linear motion blur with a kernel of cfg augment.motion_blur_px (full-res px) at a per-clip angle."""

    name, levels_key, level_param = "MotionBlur", "motion_blur_px", "kernel_px"

    def start(self, first, rng):
        self.runtime["angle_deg"] = float(rng.uniform(0, 180)) if self.params.get("angle_deg") is None else float(self.params["angle_deg"])

    def frame(self, f, rng):
        import cv2

        k = int(self.params["kernel_px"]) * (1 if f.kind == "rgb" else 1)
        if f.kind == "bayer":
            k = max(1, int(round(k / 2)))
        if k <= 1:
            return f
        kern = np.zeros((k, k), np.float32)
        c = (k - 1) / 2
        a = math.radians(self.runtime["angle_deg"])
        for i in range(k):
            x = c + (i - c) * math.cos(a)
            y = c + (i - c) * math.sin(a)
            kern[int(round(y)), int(round(x))] = 1.0
        kern /= kern.sum()
        return _map_planes(f, lambda img: cv2.filter2D(img.astype(np.float32), -1, kern, borderType=cv2.BORDER_REPLICATE))


# ----------------------------------------------------------------------------- temporal
class FrameDrops(Transform):
    """Drop frames with probability cfg augment.frame_drop_pct (never the first); dropped indices are logged.
    The timestamp vector loses the same entries (apply_times)."""

    name, levels_key, level_param = "FrameDrops", "frame_drop_pct", "pct"
    temporal = True
    changes_frame_count = True

    def start(self, first, rng):
        self.runtime["dropped_idx"] = []
        self.runtime["n_in"] = 0

    def frame(self, f, rng):
        self.runtime["n_in"] += 1
        if self.runtime["n_in"] > 1 and rng.random() < float(self.params["pct"]) / 100.0:
            self.runtime["dropped_idx"].append(int(f.idx))
            return None
        return f

    def apply_times(self, t_s, rng):
        t = np.asarray(t_s, dtype=float)
        keep = np.ones(t.size, bool)
        keep[1:] = rng.random(t.size - 1) >= float(self.params["pct"]) / 100.0
        self.runtime["dropped_idx"] = np.where(~keep)[0].tolist()
        return t[keep]


class TimestampJitter(Transform):
    """Independent Gaussian jitter of the recorded timestamps (sigma cfg augment.timestamp_jitter_ms); content
    unchanged, so the pipeline's resampling sees mislabelled capture instants."""

    name, levels_key, level_param = "TimestampJitter", "timestamp_jitter_ms", "sigma_ms"
    temporal = True

    def frame(self, f, rng):
        return replace(f, t_s=f.t_s + float(rng.normal(0.0, self.params["sigma_ms"] / 1000.0)))

    def apply_times(self, t_s, rng):
        t = np.asarray(t_s, dtype=float)
        return t + rng.normal(0.0, float(self.params["sigma_ms"]) / 1000.0, t.size)


class VFRResample(Transform):
    """Variable-frame-rate container timestamps as phones write them: a period drift, a slow wobble and an
    alternating +/- `amplitude_ms`; frame content is untouched (no interpolation)."""

    name, levels_key, level_param = "VFRResample", "vfr_ms", "amplitude_ms"
    temporal = True

    def start(self, first, rng):
        self.runtime["t_first"] = first.t_s
        self.runtime["drift"] = float(self.params.get("drift", 1e-3))
        self.runtime["wobble_s"] = float(self.params.get("wobble_period_s", 7.0))

    def _relabel(self, t: np.ndarray, t_first: float, idx: np.ndarray) -> np.ndarray:
        a = float(self.params["amplitude_ms"]) / 1000.0
        rel = t - t_first
        return t_first + rel * (1.0 + self.runtime["drift"]) + a * np.sin(2 * math.pi * rel / self.runtime["wobble_s"]) + a * np.where(idx % 2 == 0, 1.0, -1.0)

    def frame(self, f, rng):
        return replace(f, t_s=float(self._relabel(np.array([f.t_s]), self.runtime["t_first"], np.array([f.idx]))[0]))

    def apply_times(self, t_s, rng):
        t = np.asarray(t_s, dtype=float)
        self.runtime.setdefault("drift", float(self.params.get("drift", 1e-3)))
        self.runtime.setdefault("wobble_s", float(self.params.get("wobble_period_s", 7.0)))
        return self._relabel(t, float(t[0]), np.arange(t.size))


class FlickerModulation(Transform):
    """50 Hz mains flicker of amplitude cfg augment.flicker_pct, evaluated at each frame's true time (so it
    aliases to 10 Hz at 30 fps), multiplicative in linear light."""

    name, levels_key, level_param = "FlickerModulation", "flicker_pct", "pct"
    temporal = True

    def start(self, first, rng):
        self.runtime["phase"] = float(rng.uniform(0, 2 * math.pi))
        self.runtime["mains_hz"] = float(self.params.get("mains_hz", 50.0))

    def frame(self, f, rng):
        g = 1.0 + float(self.params["pct"]) / 100.0 * math.sin(2 * math.pi * self.runtime["mains_hz"] * f.t_s + self.runtime["phase"])
        return f.with_linear(f.linear() * g, dither=rng)


# ----------------------------------------------------------------------------- compression and resolution
MIN_CODEC_SIZE = 64                  # encoders misbehave below this; smaller frames are edge-padded for the round trip


class _Codec(Transform):
    codec = "libx264"
    pix_fmt = "yuv420p"
    temporal = True                      # inter-frame prediction: output frame k depends on its neighbours

    def apply(self, frames, rng):
        import av
        import cv2

        tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        tmp.close()
        path = Path(tmp.name)
        order: list[tuple[int, float, tuple, dict]] = []
        container = av.open(str(path), "w")
        vs = None
        crop = (0, 0)
        try:
            for f in frames:
                g = f.to_proxy_rgb8()
                if vs is None:
                    h, w = g.data.shape[:2]
                    h, w = h - h % 2, w - w % 2
                    crop = (h, w)
                    pad_h, pad_w = max(MIN_CODEC_SIZE - h, 0), max(MIN_CODEC_SIZE - w, 0)
                    vs = container.add_stream(self.codec, rate=30)
                    vs.width, vs.height, vs.pix_fmt = w + pad_w, h + pad_h, self.pix_fmt
                    vs.options = {"crf": str(int(self.params["crf"])), "preset": str(self.params.get("preset", "veryfast"))}
                    if self.codec == "libx265":
                        vs.options["x265-params"] = "log-level=none"
                    self.runtime["size"] = [w, h]
                    self.runtime["padded_to"] = [vs.width, vs.height]
                img = np.ascontiguousarray(g.data[: crop[0], : crop[1]])
                if (vs.height, vs.width) != crop:
                    img = cv2.copyMakeBorder(img, 0, vs.height - crop[0], 0, vs.width - crop[1], cv2.BORDER_REPLICATE)
                vf = av.VideoFrame.from_ndarray(np.ascontiguousarray(img), format="rgb24")
                vf.pts = len(order)
                for pk in vs.encode(vf):
                    container.mux(pk)
                order.append((g.idx, g.t_s, g.labels, g.meta))
            if vs is not None:
                for pk in vs.encode():
                    container.mux(pk)
        finally:
            container.close()
        self.runtime["bytes"] = path.stat().st_size if path.exists() else 0
        self.runtime["n_frames"] = len(order)
        try:
            if order:
                dec = av.open(str(path))
                k = 0
                for vf in dec.decode(video=0):
                    if k >= len(order):
                        break
                    idx, t_s, labels, meta = order[k]
                    img = np.ascontiguousarray(vf.to_ndarray(format="rgb24")[: crop[0], : crop[1]])
                    yield Frame(img, "rgb", t_s, idx, 0.0, 255.0, "srgb", tuple(dict.fromkeys(labels + (self.label,))), dict(meta))
                    k += 1
                dec.close()
        finally:
            path.unlink(missing_ok=True)


class H264Compress(_Codec):
    """H.264 (libx264) round trip at cfg augment.h264_crf; Bayer input becomes the pi_proxy sRGB image."""

    name, levels_key, level_param = "H264Compress", "h264_crf", "crf"
    label = "h264"


class H265Compress(_Codec):
    """H.265 (libx265) round trip at cfg augment.h265_crf (same CRF list as H.264 by default)."""

    name, levels_key, level_param = "H265Compress", "h265_crf", "crf"
    codec = "libx265"
    label = "h265"


class Downscale(Transform):
    """Resize by target_height / cfg phone.height (720p or 480p relative to the 1080p phone frame), area filter."""

    name, levels_key, level_param = "Downscale", "downscale", "target_height"

    def __init__(self, severity_index=None, cfg=None, **params):
        super().__init__(severity_index, cfg, **params)
        if cfg is None:
            from palmppg.core.config import load_pipeline_config

            cfg = load_pipeline_config()
        self.params["reference_height"] = int(self.params.get("reference_height", cfg.get("phone.height")))

    def frame(self, f, rng):
        import cv2

        s = float(self.params["target_height"]) / float(self.params["reference_height"])
        self.runtime["scale"] = s

        def fn(img):
            h, w = img.shape[:2]
            nh, nw = max(2, int(round(h * s)) // 2 * 2), max(2, int(round(w * s)) // 2 * 2)
            return cv2.resize(img.astype(np.float32), (nw, nh), interpolation=cv2.INTER_AREA)

        return _map_planes(f, fn)


class ChromaSubsample(Transform):
    """4:2:2 or 4:2:0 chroma subsampling (YCrCb, area down, linear up) on the 8-bit sRGB image."""

    name, levels_key, level_param = "ChromaSubsample", "chroma_subsampling", "mode"
    label = "chroma_subsampled"

    def frame(self, f, rng):
        import cv2

        g = f.to_proxy_rgb8()
        ycc = cv2.cvtColor(g.data, cv2.COLOR_RGB2YCrCb)
        h, w = ycc.shape[:2]
        fy = 2 if str(self.params["mode"]) == "420" else 1
        out = ycc.copy()
        for c in (1, 2):
            small = cv2.resize(ycc[..., c], (w // 2, h // fy), interpolation=cv2.INTER_AREA)
            out[..., c] = cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)
        return g.with_data(cv2.cvtColor(out, cv2.COLOR_YCrCb2RGB))


# ----------------------------------------------------------------------------- synthetic skin tone
class SyntheticToneShift(Transform):
    """Multiplicative melanin darkening exp(-level * k_c) with k = MELANIN_ABSORPTION (B most, R least) at cfg
    augment.melanin_levels; optional `mask` (h, w) bool restricts it to skin. Every output is labelled
    "synthetic tone shift" and supports no equity claim (section 8)."""

    name, levels_key, level_param = "SyntheticToneShift", "melanin_levels", "level"
    label = TONE_LABEL

    def frame(self, f, rng):
        fac = np.exp(-float(self.params["level"]) * np.asarray(MELANIN_ABSORPTION, np.float32))
        lin = f.linear()
        mask = self.params.get("mask")
        if f.kind == "bayer":
            g = np.array([fac[0], fac[1], fac[1], fac[2]], np.float32)[:, None, None]
            if mask is not None:
                m = np.asarray(mask, bool)
                mh = np.stack([m[0::2, 0::2], m[0::2, 1::2], m[1::2, 0::2], m[1::2, 1::2]])
                g = np.where(mh, g, 1.0)
            out = lin * g
        else:
            g = fac[None, None, :]
            out = lin * g if mask is None else np.where(np.asarray(mask, bool)[..., None], lin * g, lin)
        return f.with_linear(out, dither=rng)


# ----------------------------------------------------------------------------- registry and chains
TRANSFORMS: dict[str, type[Transform]] = {cls.name: cls for cls in (
    Rotate, Translate, Scale, Perspective, MicroJitter, ExposureShift, IlluminantShift, VignettingGain, MovingShadow,
    ShotNoise, ReadNoise, Quantise8bit, Defocus, MotionBlur, FrameDrops, TimestampJitter, VFRResample, FlickerModulation,
    H264Compress, H265Compress, Downscale, ChromaSubsample, SyntheticToneShift)}


def make_transform(spec, cfg=None) -> Transform:
    """Build a transform from an instance, a (name, severity_index) tuple or a dict {name, severity_index, params}."""
    if isinstance(spec, Transform):
        return spec
    if isinstance(spec, (tuple, list)):
        name, sev = spec[0], spec[1] if len(spec) > 1 else None
        params = spec[2] if len(spec) > 2 else {}
    elif isinstance(spec, dict):
        name, sev, params = spec["name"], spec.get("severity_index"), spec.get("params", {})
    else:
        raise TypeError(f"bad transform spec {spec!r}")
    if name not in TRANSFORMS:
        raise KeyError(f"unknown transform {name}; known: {sorted(TRANSFORMS)}")
    return TRANSFORMS[name](sev, cfg, **params)


def assert_no_temporal_interpolation(chain: Iterable[Transform]) -> None:
    bad = [t.name for t in chain if getattr(t, "temporal_interpolation", False)]
    if bad:
        raise AssertionError(f"temporal smoothing or interpolation is forbidden (section 8): {bad}")


def apply_chain(frames: Iterable[Frame], chain: Iterable, rng: np.random.Generator, log: list | dict | None = None, cfg=None) -> Iterator[Frame]:
    """Apply transforms in order to a frame iterator, logging (name, severity_index, params, runtime) per transform.

    `log` is a list that receives one dict per transform (or a dict whose "chain" list does), filled as the
    stream runs; runtime details (dropped indices, drawn directions) land in each entry's "runtime".
    """
    ts = [make_transform(s, cfg) for s in chain]
    assert_no_temporal_interpolation(ts)
    entries = [t.describe() for t in ts]
    if isinstance(log, dict):
        log.setdefault("chain", []).extend(entries)
    elif log is not None:
        log.extend(entries)
    it: Iterable[Frame] = frames
    for t in ts:
        it = t.apply(it, rng)
    return iter(it)


def apply_chain_times(t_s: np.ndarray, chain: Iterable, rng: np.random.Generator, cfg=None) -> np.ndarray:
    """Timestamp-vector counterpart of apply_chain (only temporal transforms change it)."""
    t = np.asarray(t_s, dtype=float)
    for spec in chain:
        t = make_transform(spec, cfg).apply_times(t, rng)
    return t


def severity_grid(cfg=None) -> dict[str, list]:
    """Every transform's severity levels (cfg augment.* or DEFAULT_LEVELS) for the section 8 study design."""
    return {name: cls.levels(cfg) for name, cls in TRANSFORMS.items()}
