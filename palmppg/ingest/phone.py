"""Phone (OnePlus 12) clip ingest: ffprobe PTS, PyAV streaming decode, sRGB inversion, audio, EIS residual, flat field.

Serves protocol section 5 (ingest requirements for the product proxy: per-frame PTS with ffprobe, treat as VFR
until proven otherwise, invert the sRGB transfer function and say that true linearisation is not possible on
compressed phone video, detect residual EIS by tracking static box features, weekly phone flat field) and
CONTRACTS sections 3.5 and 4. Decoding is streaming only: frames are yielded one at a time.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from palmppg.ingest.calibration import central_region_slices, vignetting_residual_pct

PTS_FIELDS: tuple[str, ...] = ("pts_time", "pkt_pts_time", "best_effort_timestamp_time")
LINEARISED_LABEL = "inverted_srgb"


# --------------------------------------------------------------------------- ffprobe
@dataclass
class FramePts:
    """Per-frame presentation timestamps of the video stream plus the stream's nominal rate and VFR verdict. Section 5 phone ingest (PTS from ffprobe, VFR until proven otherwise)."""

    pts_s: np.ndarray
    fps_nominal: float
    is_vfr: bool
    n_frames: int
    diff_median_s: float
    diff_std_s: float
    vfr_rel_std: float
    source_field: str
    codec: str | None = None
    width: int | None = None
    height: int | None = None
    duration_s: float | None = None
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """JSON-ready copy with `pts_s` as a list (ingest.json, section 5)."""
        d = asdict(self)
        d["pts_s"] = [float(x) for x in self.pts_s]
        return d


def _parse_rate(s: str | None) -> float:
    if not s:
        return float("nan")
    if "/" in s:
        a, b = s.split("/", 1)
        try:
            return float(a) / float(b) if float(b) != 0 else float("nan")
        except ValueError:
            return float("nan")
    try:
        return float(s)
    except ValueError:
        return float("nan")


def _ffprobe_bin() -> str:
    exe = shutil.which("ffprobe")
    if exe is None:
        raise RuntimeError("ffprobe not found on PATH")
    return exe


def ffprobe_frame_pts(mp4_path: str | os.PathLike, vfr_rel_std: float = 0.05) -> FramePts:
    """Per-frame PTS (seconds, presentation order) of video stream 0 via `ffprobe -of json -show_frames` (section 5).

    Field preference per frame: `pts_time`, then `pkt_pts_time`, then `best_effort_timestamp_time`. Also returns
    the nominal fps (`avg_frame_rate`, falling back to `r_frame_rate`) and `is_vfr`: True when the standard
    deviation of the PTS differences exceeds `vfr_rel_std` (5 %) of their median. The file is treated as VFR
    until this says otherwise; downstream resampling uses these PTS, never the frame index.
    """
    path = Path(mp4_path)
    if not path.exists():
        raise FileNotFoundError(path)
    cmd = [_ffprobe_bin(), "-v", "error", "-of", "json", "-select_streams", "v:0", "-show_streams", "-show_frames",
           "-show_entries", ("stream=r_frame_rate,avg_frame_rate,codec_name,width,height,nb_frames,duration:"
           "frame=pts_time,pkt_pts_time,best_effort_timestamp_time"), str(path)]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        raise RuntimeError(f"ffprobe failed on {path}: {res.stderr.strip()}")
    j = json.loads(res.stdout or "{}")
    streams = j.get("streams") or []
    st = streams[0] if streams else {}
    frames = j.get("frames") or []
    pts, used = [], None
    for fr in frames:
        val = None
        for f in PTS_FIELDS:
            v = fr.get(f)
            if v not in (None, "N/A", ""):
                try:
                    val = float(v)
                except ValueError:
                    val = None
                if val is not None:
                    used = used or f
                    break
        if val is not None:
            pts.append(val)
    pts_arr = np.asarray(sorted(pts), dtype=float)
    fps = _parse_rate(st.get("avg_frame_rate"))
    if not np.isfinite(fps) or fps <= 0:
        fps = _parse_rate(st.get("r_frame_rate"))
    d = np.diff(pts_arr) if pts_arr.size > 1 else np.zeros(0)
    med = float(np.median(d)) if d.size else float("nan")
    sd = float(np.std(d)) if d.size else float("nan")
    rel = sd / med if d.size and med > 0 else float("nan")
    is_vfr = bool(np.isfinite(rel) and rel > float(vfr_rel_std))
    if (not np.isfinite(fps) or fps <= 0) and np.isfinite(med) and med > 0:
        fps = 1.0 / med
    dur = st.get("duration")
    return FramePts(
        pts_s=pts_arr, fps_nominal=float(fps), is_vfr=is_vfr, n_frames=int(pts_arr.size), diff_median_s=med,
        diff_std_s=sd, vfr_rel_std=float(rel) if np.isfinite(rel) else float("nan"), source_field=used or "none",
        codec=st.get("codec_name"), width=int(st["width"]) if st.get("width") else None,
        height=int(st["height"]) if st.get("height") else None, duration_s=float(dur) if dur not in (None, "N/A") else None,
        detail={"r_frame_rate": st.get("r_frame_rate"), "avg_frame_rate": st.get("avg_frame_rate"),
                "nb_frames_stream": st.get("nb_frames"), "n_frames_probed": len(frames), "vfr_rel_std_threshold": vfr_rel_std},
    )


# --------------------------------------------------------------------------- PyAV reader
class PhoneClipReader:
    """Streaming PyAV decoder for `phone/clip1.mp4` (CONTRACTS section 3.5): yields (frame_idx, pts_s, rgb uint8 HxWx3).

    Metadata (`width, height, codec, has_audio, n_frames, fps_nominal, duration_s`) is read from the container
    header; `n_frames` falls back to a packet count when the header does not carry it. Nothing is cached:
    every `iter_frames` call decodes afresh and yields one frame at a time (section 12 compute hygiene).
    """

    def __init__(self, mp4_path: str | os.PathLike):
        import av

        self.path = Path(mp4_path)
        if not self.path.exists():
            raise FileNotFoundError(self.path)
        with av.open(str(self.path)) as c:
            if not c.streams.video:
                raise ValueError(f"{self.path}: no video stream")
            vs = c.streams.video[0]
            self.width = int(vs.codec_context.width)
            self.height = int(vs.codec_context.height)
            self.codec = str(vs.codec_context.name)
            self.has_audio = len(c.streams.audio) > 0
            self.audio_rate = int(c.streams.audio[0].rate) if self.has_audio else None
            rate = vs.average_rate or vs.guessed_rate or vs.base_rate
            self.fps_nominal = float(rate) if rate else float("nan")
            self.time_base = float(vs.time_base) if vs.time_base else None
            self.duration_s = float(vs.duration * vs.time_base) if vs.duration and vs.time_base else None
            n = int(vs.frames or 0)
            self.n_frames_from_header = n > 0
            self.n_frames = n if n > 0 else self._count_packets(c, vs)

    @staticmethod
    def _count_packets(container, stream) -> int:
        n = 0
        for pkt in container.demux(stream):
            if pkt.size > 0 or pkt.pts is not None:
                n += 1
        container.seek(0)
        return n

    def metadata(self) -> dict:
        """Container metadata for ingest.json (CONTRACTS section 3.5)."""
        return {"path": str(self.path), "width": self.width, "height": self.height, "codec": self.codec,
                "has_audio": self.has_audio, "audio_rate": self.audio_rate, "n_frames": int(self.n_frames),
                "n_frames_from_header": self.n_frames_from_header, "fps_nominal": self.fps_nominal,
                "duration_s": self.duration_s, "time_base": self.time_base}

    def __len__(self) -> int:
        return int(self.n_frames)

    def iter_frames(self, start: int = 0, stop: int | None = None, step: int = 1) -> Iterator[tuple[int, float, np.ndarray]]:
        """Yield (frame_idx, pts_s, rgb_uint8) for decoded frames start <= idx < stop with the given step. Section 5: PTS per frame, never the frame index.

        `pts_s` is the frame's own presentation time (frame.pts x time_base); a frame without a PTS gets NaN
        rather than a value invented from its index.
        """
        import av

        start, step = int(start), max(1, int(step))
        with av.open(str(self.path)) as c:
            vs = c.streams.video[0]
            vs.thread_type = "AUTO"
            for idx, frame in enumerate(c.decode(vs)):
                if stop is not None and idx >= int(stop):
                    break
                if idx >= start and (idx - start) % step == 0:
                    pts_s = float(frame.time) if frame.time is not None else float("nan")
                    yield idx, pts_s, frame.to_ndarray(format="rgb24")

    def frame_pts(self) -> np.ndarray:
        """PTS of every decoded frame (seconds) without converting pixels; a decode pass, streaming. Section 5 PTS cross-check against ffprobe."""
        import av

        out = []
        with av.open(str(self.path)) as c:
            vs = c.streams.video[0]
            vs.thread_type = "AUTO"
            for frame in c.decode(vs):
                out.append(float(frame.time) if frame.time is not None else np.nan)
        return np.asarray(out, dtype=float)


# --------------------------------------------------------------------------- sRGB transfer
def srgb_to_linear(x: np.ndarray) -> np.ndarray:
    """Exact inverse sRGB OETF: uint8 (0..255) or float (0..1) encoded values -> float32 linear-ish in [0, 1].

    c <= 0.04045 -> c / 12.92, else ((c + 0.055) / 1.055) ** 2.4. Compressed phone video cannot be truly
    linearised: the camera pipeline applies its own tone curve, denoising and chroma subsampling before the
    sRGB-like encoding, so the output is only "linear-ish". Every quantity derived from it is labelled
    `colour_space = "inverted_srgb"` / `linearised_from_srgb = True` (section 5, CONTRACTS rule 4).
    """
    a = np.asarray(x)
    if a.dtype.kind in "ui":
        c = a.astype(np.float32) / np.float32(255.0)
    else:
        c = np.clip(a.astype(np.float32, copy=False), 0.0, 1.0)
    low = c / np.float32(12.92)
    high = np.power((c + np.float32(0.055)) / np.float32(1.055), np.float32(2.4), dtype=np.float32)
    return np.where(c <= np.float32(0.04045), low, high).astype(np.float32)


def linear_to_srgb(x: np.ndarray, to_uint8: bool = False) -> np.ndarray:
    """Forward sRGB OETF: linear [0, 1] -> encoded float32 [0, 1] (or uint8 0..255 with `to_uint8`). Section 5 / D-006 proxy encoding.

    c <= 0.0031308 -> 12.92 c, else 1.055 c ** (1 / 2.4) - 0.055. Used by the Pi -> phone proxy chain.
    """
    c = np.clip(np.asarray(x, dtype=np.float32), 0.0, 1.0)
    low = c * np.float32(12.92)
    high = np.float32(1.055) * np.power(c, np.float32(1.0 / 2.4), dtype=np.float32) - np.float32(0.055)
    out = np.where(c <= np.float32(0.0031308), low, high).astype(np.float32)
    if to_uint8:
        return np.round(np.clip(out, 0.0, 1.0) * 255.0).astype(np.uint8)
    return out


# --------------------------------------------------------------------------- audio
def extract_audio(mp4_path: str | os.PathLike, target_fs: int | None = None) -> tuple[int, np.ndarray]:
    """Decode the first audio stream to (fs, mono float32 in [-1, 1]) with PyAV, resampling to mono (section 4.2 beep).

    `target_fs` keeps the stream rate when None. Raises ValueError when the file has no audio.
    """
    import av

    path = Path(mp4_path)
    with av.open(str(path)) as c:
        if not c.streams.audio:
            raise ValueError(f"{path}: no audio stream")
        ast = c.streams.audio[0]
        fs = int(target_fs or ast.rate)
        resampler = av.AudioResampler(format="flt", layout="mono", rate=fs)
        chunks: list[np.ndarray] = []
        for frame in c.decode(ast):
            for out in resampler.resample(frame):
                chunks.append(out.to_ndarray().reshape(-1).astype(np.float32))
        for out in resampler.resample(None):
            chunks.append(out.to_ndarray().reshape(-1).astype(np.float32))
    mono = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)
    return fs, mono


# --------------------------------------------------------------------------- EIS residual
def corner_regions(width: int, height: int, margin_frac: float = 0.08) -> list[tuple[int, int, int, int]]:
    """Four corner boxes (x, y, w, h) of `margin_frac` x frame size: the default static regions outside the skin. Section 5 EIS residual detection."""
    w = max(8, round(width * margin_frac))
    h = max(8, round(height * margin_frac))
    return [(0, 0, w, h), (width - w, 0, w, h), (0, height - h, w, h), (width - w, height - h, w, h)]


def _pair_warp(prev_gray: np.ndarray, gray: np.ndarray, regions: Sequence[tuple[int, int, int, int]],
               max_corners: int, quality: float, min_distance: int, fb_err_px: float) -> tuple[float, int]:
    """Median magnitude of the per-region median feature displacement between two frames, and the track count."""
    import cv2

    mags, n_tracks = [], 0
    lk = {"winSize": (21, 21), "maxLevel": 3, "criteria": (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01)}
    for (x, y, w, h) in regions:
        mask = np.zeros(prev_gray.shape, dtype=np.uint8)
        mask[max(0, y): y + h, max(0, x): x + w] = 255
        p0 = cv2.goodFeaturesToTrack(prev_gray, maxCorners=max_corners, qualityLevel=quality, minDistance=min_distance, mask=mask)
        if p0 is None or len(p0) < 3:
            continue
        p1, st, _ = cv2.calcOpticalFlowPyrLK(prev_gray, gray, p0, None, **lk)
        if p1 is None:
            continue
        p0b, stb, _ = cv2.calcOpticalFlowPyrLK(gray, prev_gray, p1, None, **lk)
        ok = (st.reshape(-1) == 1) & (stb.reshape(-1) == 1)
        fb = np.linalg.norm((p0b - p0).reshape(-1, 2), axis=1)
        ok &= fb < fb_err_px
        if ok.sum() < 3:
            continue
        disp = (p1 - p0).reshape(-1, 2)[ok]
        med = np.median(disp, axis=0)
        mags.append(float(np.hypot(med[0], med[1])))
        n_tracks += int(ok.sum())
    if not mags:
        return float("nan"), 0
    return float(np.median(mags)), n_tracks


def detect_eis_warp(reader: PhoneClipReader, static_regions: Sequence[tuple[int, int, int, int]] | None = None,
                    n_sample: int = 60, warp_px_max: float = 0.5, margin_frac: float = 0.08, max_corners: int = 200,
                    quality: float = 0.01, min_distance: int = 5, fb_err_px: float = 1.0, min_valid_pairs: int = 5) -> dict:
    """Residual electronic image stabilisation (section 5): track static box features frame to frame and report warps.

    `n_sample` consecutive frame pairs are sampled uniformly over the clip. In each static region
    (x, y, w, h boxes outside the skin; default the four corners with `margin_frac` margins) Shi-Tomasi
    features are tracked with pyramidal Lucas-Kanade (forward-backward checked); the pair warp is the median
    over regions of the magnitude of the median feature displacement (pixels). Returns
    {warp_px_median, warp_px_p90, warp_px_max, flag, n_pairs, n_pairs_valid, n_tracks_median, regions,
    threshold_px}. `flag` is True when the 90th percentile of pair warps exceeds `warp_px_max`
    (cfg `qc.eis_warp_px_max`), None when too few pairs had trackable texture.
    """
    import cv2

    n = int(reader.n_frames)
    regions = [tuple(int(v) for v in r) for r in static_regions] if static_regions else corner_regions(reader.width, reader.height, margin_frac)
    base = {"warp_px_median": float("nan"), "warp_px_p90": float("nan"), "warp_px_max": float("nan"), "flag": None,
            "n_pairs": 0, "n_pairs_valid": 0, "n_tracks_median": 0, "regions": [list(r) for r in regions],
            "threshold_px": float(warp_px_max), "insufficient_features": True}
    if n < 2:
        return base
    n_pairs = int(min(max(1, n_sample), n - 1))
    firsts = np.unique(np.linspace(0, n - 2, n_pairs).round().astype(int))
    first_set = {int(i) for i in firsts}
    last_needed = int(firsts.max()) + 1
    warps, tracks = [], []
    prev_gray, prev_idx = None, None
    for idx, _pts, rgb in reader.iter_frames(stop=last_needed + 1):
        needed = idx in first_set or (idx - 1) in first_set
        if not needed:
            prev_gray, prev_idx = None, None
            continue
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        if prev_gray is not None and prev_idx == idx - 1 and prev_idx in first_set:
            w, nt = _pair_warp(prev_gray, gray, regions, max_corners, quality, min_distance, fb_err_px)
            if np.isfinite(w):
                warps.append(w)
                tracks.append(nt)
        prev_gray, prev_idx = gray, idx
    base["n_pairs"] = int(firsts.size)
    base["n_pairs_valid"] = len(warps)
    if len(warps) == 0:
        return base
    w = np.asarray(warps, dtype=float)
    base.update({"warp_px_median": float(np.median(w)), "warp_px_p90": float(np.percentile(w, 90)),
                 "warp_px_max": float(w.max()), "n_tracks_median": int(np.median(tracks))})
    enough = len(warps) >= min(int(min_valid_pairs), int(firsts.size))
    base["insufficient_features"] = not enough
    base["flag"] = bool(base["warp_px_p90"] > float(warp_px_max)) if enough else None
    return base


# --------------------------------------------------------------------------- phone flat field
class PhoneFlatField:
    """Per-channel vignetting gain map of the phone path from `units/unit_##/phone_flatfield.mp4` (section 5).

    The white-card clip is decoded streaming, inverted to linear-ish RGB, reduced by `downscale` (area average),
    median-combined over frames, heavily blurred, and normalised by its central-region mean per channel.
    `gain = 1 / max(flat_norm, eps)` is stored at the reduced size and resized to the frame on `apply`.
    """

    def __init__(self, flat_norm_small: np.ndarray, full_size: tuple[int, int], eps: float = 1e-3, source: str | None = None,
                 n_frames_used: int = 0, blur_sigma_px: float = 0.0, downscale: int = 1):
        self.flat_norm_small = np.asarray(flat_norm_small, dtype=np.float32)
        self.gain_small = (1.0 / np.maximum(self.flat_norm_small, eps)).astype(np.float32)
        self.full_size = (int(full_size[0]), int(full_size[1]))
        self.eps = float(eps)
        self.source = source
        self.n_frames_used = int(n_frames_used)
        self.blur_sigma_px = float(blur_sigma_px)
        self.downscale = int(downscale)
        self._gain_cache: dict[tuple[int, int], np.ndarray] = {}

    @classmethod
    def from_frames(cls, frames: Iterable[np.ndarray], downscale: int = 8, blur_sigma_frac: float = 0.05,
                    max_frames: int = 150, central_fraction: float = 0.5, eps: float = 1e-3, source: str | None = None,
                    already_linear: bool = False) -> PhoneFlatField:
        """Build from an iterable of RGB frames (uint8 sRGB, or float linear when `already_linear`). Section 5 phone flat field."""
        import cv2

        small = []
        full_size = None
        for fr in frames:
            if len(small) >= max_frames:
                break
            lin = np.asarray(fr, dtype=np.float32) if already_linear else srgb_to_linear(fr)
            h, w = lin.shape[:2]
            full_size = (w, h)
            ws, hs = max(4, w // downscale), max(4, h // downscale)
            small.append(cv2.resize(lin, (ws, hs), interpolation=cv2.INTER_AREA))
        if not small:
            raise ValueError("phone flat field: no frames")
        stack = np.stack(small, axis=0)
        med = np.median(stack, axis=0).astype(np.float32)
        sigma = max(1.0, blur_sigma_frac * min(med.shape[:2]))
        from scipy.ndimage import gaussian_filter

        blurred = np.stack([gaussian_filter(med[..., c], sigma=sigma, mode="nearest") for c in range(3)], axis=-1)
        rs, cs = central_region_slices(blurred.shape[:2], central_fraction)
        centre = blurred[rs, cs].reshape(-1, 3).mean(axis=0)
        if np.any(~np.isfinite(centre)) or np.any(centre <= 0):
            raise ValueError("phone flat field: non-positive central mean; check the white-card clip")
        flat_norm = blurred / centre[None, None, :]
        return cls(flat_norm, full_size, eps=eps, source=source, n_frames_used=len(small), blur_sigma_px=sigma, downscale=downscale)

    @classmethod
    def load(cls, mp4_path: str | os.PathLike, downscale: int = 8, blur_sigma_frac: float = 0.05, max_frames: int = 150,
             central_fraction: float = 0.5, eps: float = 1e-3) -> PhoneFlatField:
        """Decode `phone_flatfield.mp4` streaming and build the gain map (see class docstring). Section 5 phone flat field."""
        reader = PhoneClipReader(mp4_path)
        step = max(1, int(reader.n_frames // max_frames)) if reader.n_frames > max_frames else 1
        frames = (rgb for _i, _t, rgb in reader.iter_frames(step=step))
        return cls.from_frames(frames, downscale=downscale, blur_sigma_frac=blur_sigma_frac, max_frames=max_frames,
                               central_fraction=central_fraction, eps=eps, source=str(mp4_path))

    def gain_for(self, height: int, width: int) -> np.ndarray:
        """Gain map resized (bilinear) to (height, width, 3), cached per shape. Section 5 phone flat field."""
        import cv2

        key = (int(height), int(width))
        g = self._gain_cache.get(key)
        if g is None:
            g = cv2.resize(self.gain_small, (key[1], key[0]), interpolation=cv2.INTER_LINEAR).astype(np.float32)
            self._gain_cache[key] = g
        return g

    def apply(self, rgb_linear: np.ndarray) -> np.ndarray:
        """Vignetting-corrected linear-ish RGB (float32): frame x gain. Input is `srgb_to_linear` output (H, W, 3). Section 5: vignetting correction on the phone path; output stays labelled inverted_srgb."""
        a = np.asarray(rgb_linear, dtype=np.float32)
        return a * self.gain_for(a.shape[0], a.shape[1])

    def vignetting_pct(self) -> float:
        """Uncorrected flat-field non-uniformity in percent (max over channels), the number the flat removes. Section 5 flat field; percent, same measure as the Pi vignetting residual (section 6.1)."""
        planes = {f"ch{c}": self.flat_norm_small[..., c] for c in range(3)}
        return vignetting_residual_pct(planes, sigma_frac=0.02)

    def residual_pct(self) -> float:
        """Residual after applying the gain to the flat itself (ideally 0; non-zero only from the eps floor). Section 6.1 vignetting residual applied to the phone flat (percent)."""
        corrected = self.flat_norm_small * self.gain_small
        return vignetting_residual_pct({f"ch{c}": corrected[..., c] for c in range(3)}, sigma_frac=0.02)

    def summary(self) -> dict:
        """Numbers for ingest.json: frames used, blur, gain range, vignetting removed (section 5)."""
        return {"source": self.source, "n_frames_used": self.n_frames_used, "downscale": self.downscale,
                "blur_sigma_px": self.blur_sigma_px, "full_size": list(self.full_size), "eps": self.eps,
                "vignetting_pct_uncorrected": self.vignetting_pct(), "residual_pct_on_flat": self.residual_pct(),
                "gain_min": float(self.gain_small.min()), "gain_max": float(self.gain_small.max()),
                "colour_space": LINEARISED_LABEL}

    def save(self, path: str | os.PathLike) -> Path:
        """Persist the reduced-size gain map as .npz under the work directory (section 5, weekly flat per unit)."""
        path = Path(path)
        np.savez_compressed(path, flat_norm_small=self.flat_norm_small, full_size=np.array(self.full_size), eps=self.eps,
                            n_frames_used=self.n_frames_used, blur_sigma_px=self.blur_sigma_px, downscale=self.downscale,
                            source=str(self.source or ""))
        return path if path.suffix == ".npz" else path.with_suffix(path.suffix + ".npz")

    @classmethod
    def load_npz(cls, path: str | os.PathLike) -> PhoneFlatField:
        """Reload a gain map saved by `save` (section 5)."""
        z = np.load(path, allow_pickle=False)
        return cls(z["flat_norm_small"], tuple(int(v) for v in z["full_size"]), eps=float(z["eps"]),
                   source=str(z["source"]) or None, n_frames_used=int(z["n_frames_used"]),
                   blur_sigma_px=float(z["blur_sigma_px"]), downscale=int(z["downscale"]))
