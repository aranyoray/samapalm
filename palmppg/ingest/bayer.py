"""10-bit packed CSI-2 Bayer frames: unpack, pack, plane split, streaming reader, preview and proxy video.

Serves protocol section 3 (on-disk Pi raw format, CONTRACTS section 3.1) and section 6.1 (keep R, G1, G2, B
planes separate; never demosaic before pulse extraction; the demosaiced 8-bit preview exists only for hand
landmarks and for the 128x72 proxy video). Nothing here holds a full clip in memory: the reader memory-maps
the file and yields frames or chunks of frames.

Packing (`SRGGB10_CSI2P`): every 4 pixels occupy 5 bytes. Bytes 0..3 hold the high 8 bits of pixels 0..3;
byte 4 holds the low 2 bits: bits 0-1 -> px0, 2-3 -> px1, 4-5 -> px2, 6-7 -> px3. Rows are padded to
`stride_bytes`, which defaults to ceil(width * 10 / 8) rounded up to a multiple of 32 (1920 for 1536 wide).
"""
from __future__ import annotations

import math
import os
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Self

import numpy as np

PLANE_NAMES: tuple[str, ...] = ("R", "G1", "G2", "B")
BAYER_PATTERNS: tuple[str, ...] = ("RGGB", "BGGR", "GRBG", "GBRG")
PIXELS_PER_GROUP = 4
BYTES_PER_GROUP = 5
MAX_10BIT = 1023


# --------------------------------------------------------------------------- stride and geometry
def default_stride(width: int) -> int:
    """Row stride in bytes for a 10-bit packed row of `width` pixels (CONTRACTS section 3.1).

    ceil(width * 10 / 8) rounded up to a multiple of 32 bytes; 1536 pixels -> 1920 bytes.
    """
    raw = math.ceil(int(width) * 10 / 8)
    return int(math.ceil(raw / 32) * 32)


def payload_bytes(width: int) -> int:
    """Bytes actually carrying pixel data in one packed row (groups of 4 pixels in 5 bytes). CONTRACTS section 3.1 packing."""
    return math.ceil(int(width) / PIXELS_PER_GROUP) * BYTES_PER_GROUP


def frame_bytes(height: int, stride_bytes: int) -> int:
    """Size of one packed frame on disk (section 3.1: `stride_bytes * height`, no header)."""
    return int(height) * int(stride_bytes)


def _check_geometry(width: int, height: int, stride_bytes: int) -> None:
    if width <= 0 or height <= 0:
        raise ValueError(f"invalid geometry {width}x{height}")
    if stride_bytes < payload_bytes(width):
        raise ValueError(f"stride {stride_bytes} bytes is smaller than the packed payload {payload_bytes(width)} "
                         f"bytes needed for {width} pixels")


# --------------------------------------------------------------------------- unpack / pack
def unpack_csi2p_10bit(buf, width: int, height: int, stride_bytes: int | None = None) -> np.ndarray:
    """Unpack one (or several stacked) 10-bit packed CSI-2 Bayer frame(s) into uint16 mosaics, values 0..1023.

    `buf` is bytes, a buffer or a uint8 array holding `k * stride_bytes * height` bytes (k >= 1). Returns an
    array of shape (height, width) for one frame or (k, height, width) for several. Stride padding beyond the
    packed payload is ignored. Pure numpy, vectorised: rows -> groups of 5 bytes -> 4 pixels.
    Serves protocol section 6.1 ("unpack 10-bit packed Bayer to uint16").
    """
    width, height = int(width), int(height)
    stride_bytes = int(stride_bytes) if stride_bytes is not None else default_stride(width)
    _check_geometry(width, height, stride_bytes)
    fb = frame_bytes(height, stride_bytes)
    a = np.frombuffer(buf, dtype=np.uint8) if not isinstance(buf, np.ndarray) else buf.reshape(-1).view(np.uint8)
    if a.size < fb:
        raise ValueError(f"buffer holds {a.size} bytes, one frame needs {fb}")
    k = a.size // fb
    a = a[: k * fb].reshape(k, height, stride_bytes)
    n_groups = math.ceil(width / PIXELS_PER_GROUP)
    g = a[:, :, : n_groups * BYTES_PER_GROUP].reshape(k, height, n_groups, BYTES_PER_GROUP)
    hi = g[:, :, :, :PIXELS_PER_GROUP].astype(np.uint16) << 2
    low = g[:, :, :, PIXELS_PER_GROUP].astype(np.uint16)
    shifts = np.array([0, 2, 4, 6], dtype=np.uint16)
    lo = (low[..., None] >> shifts) & 0x3
    px = (hi | lo).reshape(k, height, n_groups * PIXELS_PER_GROUP)[:, :, :width]
    return px[0] if k == 1 else px


def pack_csi2p_10bit(frame_uint16: np.ndarray, stride_bytes: int | None = None) -> bytes:
    """Inverse of `unpack_csi2p_10bit`: (H, W) uint16 values 0..1023 -> packed bytes with stride padding (zeros).

    Used by synthetic writers (section 8 positive control) and roundtrip tests. Values above 1023 raise.
    """
    f = np.asarray(frame_uint16)
    if f.ndim != 2:
        raise ValueError("pack expects a single (H, W) frame")
    if f.dtype.kind not in "ui":
        raise ValueError("pack expects an integer frame")
    if f.size and int(f.max()) > MAX_10BIT:
        raise ValueError("pixel values above 1023 cannot be packed into 10 bits")
    f = f.astype(np.uint16, copy=False)
    height, width = f.shape
    stride_bytes = int(stride_bytes) if stride_bytes is not None else default_stride(width)
    _check_geometry(width, height, stride_bytes)
    n_groups = math.ceil(width / PIXELS_PER_GROUP)
    padded = np.zeros((height, n_groups * PIXELS_PER_GROUP), dtype=np.uint16)
    padded[:, :width] = f
    grp = padded.reshape(height, n_groups, PIXELS_PER_GROUP)
    out = np.zeros((height, stride_bytes), dtype=np.uint8)
    body = out[:, : n_groups * BYTES_PER_GROUP].reshape(height, n_groups, BYTES_PER_GROUP)
    body[:, :, :PIXELS_PER_GROUP] = (grp >> 2).astype(np.uint8)
    low = grp & 0x3
    body[:, :, PIXELS_PER_GROUP] = (low[:, :, 0] | (low[:, :, 1] << 2) | (low[:, :, 2] << 4) | (low[:, :, 3] << 6)).astype(np.uint8)
    return out.tobytes()


# --------------------------------------------------------------------------- planes
def plane_offsets(pattern: str = "RGGB") -> dict[str, tuple[int, int]]:
    """(row, col) offset of each plane inside the 2x2 Bayer cell for the given pattern (G1 before G2 in raster order). CONTRACTS section 3.1 Bayer order."""
    p = str(pattern).upper()
    if p not in BAYER_PATTERNS:
        raise ValueError(f"unknown Bayer pattern {pattern!r}; expected one of {BAYER_PATTERNS}")
    cells = [(0, 0), (0, 1), (1, 0), (1, 1)]
    out: dict[str, tuple[int, int]] = {}
    g_seen = 0
    for letter, cell in zip(p, cells):
        if letter == "G":
            g_seen += 1
            out[f"G{g_seen}"] = cell
        else:
            out[letter] = cell
    return out


def split_planes(frame: np.ndarray, pattern: str = "RGGB") -> dict[str, np.ndarray]:
    """Split a Bayer mosaic (…, H, W) into planes {R, G1, G2, B} of shape (…, H/2, W/2) (CONTRACTS section 3.1).

    RGGB: R at (even row, even col), G1 (even, odd), G2 (odd, even), B (odd, odd). Views, not copies.
    Serves section 6.1 (keep the four planes separate) and non-negotiable 9 (work on Bayer planes).
    """
    f = np.asarray(frame)
    if f.shape[-1] % 2 or f.shape[-2] % 2:
        raise ValueError(f"Bayer frame needs even height and width, got {f.shape[-2:]}")
    offs = plane_offsets(pattern)
    return {name: f[..., r::2, c::2] for name, (r, c) in offs.items()}


def merge_planes(planes: Mapping[str, np.ndarray], pattern: str = "RGGB") -> np.ndarray:
    """Inverse of `split_planes`: planes {R, G1, G2, B} of (…, h, w) -> mosaic (…, 2h, 2w) of the planes' dtype. Used by the D-006 proxy chain and synthetic writers (section 8)."""
    offs = plane_offsets(pattern)
    ref = np.asarray(planes["R"])
    out = np.empty(ref.shape[:-2] + (ref.shape[-2] * 2, ref.shape[-1] * 2), dtype=ref.dtype)
    for name, (r, c) in offs.items():
        out[..., r::2, c::2] = planes[name]
    return out


def plane_stats(planes: Mapping[str, np.ndarray], mask: np.ndarray | None = None) -> dict[str, float]:
    """Mean of each plane (optionally inside a half-resolution boolean mask), as plain floats; NaN when empty. Per-plane mean intensity series feed the section 6.1 flicker and drift tests."""
    out = {}
    for name, p in planes.items():
        p = np.asarray(p, dtype=np.float64)
        sel = p[mask] if mask is not None else p
        out[name] = float(sel.mean()) if sel.size else float("nan")
    return out


# --------------------------------------------------------------------------- streaming reader
class BayerClipReader:
    """Memory-mapped reader for `pi/clip1.raw` (CONTRACTS section 3.1): concatenated packed frames, no header.

    `meta` is the clip meta dict (section 3.3) and must carry `width` and `height`; `stride_bytes` and
    `bayer_pattern` are optional (defaults: `default_stride(width)`, "RGGB"). `n_frames` is derived from the
    file size; a trailing partial frame is reported in `trailing_bytes` and never read as a frame.
    Frames are unpacked on demand; iteration is streaming (never the whole file).
    """

    def __init__(self, raw_path: str | os.PathLike, meta: Mapping):
        self.path = Path(raw_path)
        self.meta = dict(meta)
        try:
            self.width = int(meta["width"])
            self.height = int(meta["height"])
        except KeyError as e:
            raise KeyError(f"clip meta lacks required key {e}") from e
        self.stride_bytes = int(meta.get("stride_bytes") or default_stride(self.width))
        self.pattern = str(meta.get("bayer_pattern") or "RGGB").upper()
        if self.pattern not in BAYER_PATTERNS:
            raise ValueError(f"unknown bayer_pattern {self.pattern!r}")
        _check_geometry(self.width, self.height, self.stride_bytes)
        self.frame_bytes = frame_bytes(self.height, self.stride_bytes)
        self.file_bytes = self.path.stat().st_size
        self.n_frames = self.file_bytes // self.frame_bytes
        self.trailing_bytes = self.file_bytes % self.frame_bytes
        self._mm = np.memmap(self.path, dtype=np.uint8, mode="r") if self.file_bytes else np.zeros(0, np.uint8)

    # ----------------------------------------------------------------- properties
    @property
    def plane_shape(self) -> tuple[int, int]:
        """Half-resolution (H/2, W/2) shape of each Bayer plane (CONTRACTS section 3.1)."""
        return self.height // 2, self.width // 2

    @property
    def size_is_whole_frames(self) -> bool:
        """True when the file size is a multiple of the frame size (section 3.1 integrity check)."""
        return self.trailing_bytes == 0

    def describe(self) -> dict:
        """Geometry and integrity summary for ingest.json. Section 3.1 geometry and file integrity (reported in ingest.json)."""
        return {
            "path": str(self.path), "width": self.width, "height": self.height, "stride_bytes": self.stride_bytes,
            "bayer_pattern": self.pattern, "frame_bytes": self.frame_bytes, "file_bytes": int(self.file_bytes),
            "n_frames": int(self.n_frames), "trailing_bytes": int(self.trailing_bytes),
            "n_frames_meta": self.meta.get("n_frames_written"),
        }

    def close(self) -> None:
        """Release the memory map (section 12 compute hygiene: nothing stays resident)."""
        mm = self._mm
        if isinstance(mm, np.memmap):
            try:
                mm._mmap.close()  # type: ignore[attr-defined]
            except (AttributeError, ValueError):
                pass
        self._mm = np.zeros(0, np.uint8)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def __len__(self) -> int:
        return int(self.n_frames)

    # ----------------------------------------------------------------- frame access
    def _check_index(self, i: int) -> int:
        i = int(i)
        if i < 0:
            i += self.n_frames
        if not 0 <= i < self.n_frames:
            raise IndexError(f"frame {i} out of range (n_frames={self.n_frames})")
        return i

    def mosaic(self, i: int) -> np.ndarray:
        """Full-resolution (H, W) uint16 Bayer mosaic of frame i (for the demosaiced preview only). Section 6.1 unpack to uint16."""
        i = self._check_index(i)
        buf = self._mm[i * self.frame_bytes: (i + 1) * self.frame_bytes]
        return unpack_csi2p_10bit(buf, self.width, self.height, self.stride_bytes)

    def frame(self, i: int) -> dict[str, np.ndarray]:
        """Planes {R, G1, G2, B} of frame i, each (H/2, W/2) uint16. Section 6.1: planes kept separate, never demosaiced for pulse extraction."""
        return split_planes(self.mosaic(i), self.pattern)

    def mosaics(self, start: int, stop: int) -> np.ndarray:
        """Frames start..stop-1 as one (n, H, W) uint16 stack (bounded by the caller's chunk size). Streaming access per section 12 (never the whole clip)."""
        start, stop = int(start), int(stop)
        if start < 0 or stop > self.n_frames or stop < start:
            raise IndexError(f"frames [{start}, {stop}) out of range (n_frames={self.n_frames})")
        if stop == start:
            return np.zeros((0, self.height, self.width), dtype=np.uint16)
        buf = self._mm[start * self.frame_bytes: stop * self.frame_bytes]
        out = unpack_csi2p_10bit(buf, self.width, self.height, self.stride_bytes)
        return out[None] if out.ndim == 2 else out

    def iter_frames(self, start: int = 0, stop: int | None = None, step: int = 1) -> Iterator[tuple[int, dict[str, np.ndarray]]]:
        """Yield (frame_idx, planes) for frames start, start+step, ... < stop. Streaming, one frame at a time. Section 12 compute hygiene."""
        stop = self.n_frames if stop is None else min(int(stop), self.n_frames)
        for i in range(int(start), stop, int(step)):
            yield i, self.frame(i)

    def iter_chunks(self, chunk: int = 64, start: int = 0, stop: int | None = None) -> Iterator[tuple[np.ndarray, dict[str, np.ndarray]]]:
        """Yield (frame_indices, planes) where each plane is a (n, H/2, W/2) uint16 stack of at most `chunk` frames. Section 12 compute hygiene (chunked streaming)."""
        chunk = max(1, int(chunk))
        stop = self.n_frames if stop is None else min(int(stop), self.n_frames)
        for s in range(int(start), stop, chunk):
            e = min(s + chunk, stop)
            stack = self.mosaics(s, e)
            yield np.arange(s, e), split_planes(stack, self.pattern)


# --------------------------------------------------------------------------- preview
def demosaic_preview(planes: Mapping[str, np.ndarray], black_level: float, white_level: float,
                     awb_gains: tuple[float, float] = (1.0, 1.0), gamma: float = 2.2,
                     size: tuple[int, int] | None = None) -> np.ndarray:
    """Half-resolution 8-bit sRGB-like preview (R, mean(G1, G2), B) with white balance and gamma.

    Used only for hand landmarks (section 6.1, MediaPipe on a demosaiced 8-bit preview) and the 128x72 proxy
    video (section 12 compute hygiene); never for pulse extraction. Input planes may be raw uint16 (then
    `black_level` is subtracted) or calibrated float planes (pass `black_level=0`). Output (h, w, 3) uint8, or
    resized with OpenCV INTER_AREA to `size=(width, height)` when given.
    """
    r = np.asarray(planes["R"], dtype=np.float32)
    g = 0.5 * (np.asarray(planes["G1"], dtype=np.float32) + np.asarray(planes["G2"], dtype=np.float32))
    b = np.asarray(planes["B"], dtype=np.float32)
    scale = float(white_level) - float(black_level)
    if scale <= 0:
        raise ValueError("white_level must exceed black_level")
    rgb = np.stack([r, g, b], axis=-1)
    rgb = (rgb - float(black_level)) / scale
    gains = np.array([float(awb_gains[0]), 1.0, float(awb_gains[1])], dtype=np.float32)
    rgb = np.clip(rgb * gains, 0.0, 1.0)
    if gamma and gamma != 1.0:
        rgb = np.power(rgb, 1.0 / float(gamma), dtype=np.float32)
    out = np.round(rgb * 255.0).astype(np.uint8)
    if size is not None:
        import cv2

        w, h = int(size[0]), int(size[1])
        if (w, h) != (out.shape[1], out.shape[0]):
            out = cv2.resize(out, (w, h), interpolation=cv2.INTER_AREA)
    return out


# --------------------------------------------------------------------------- proxy zarr
class ProxyZarrWriter:
    """Chunked writer for `<camera>/proxy_128x72.zarr`: array (n_frames, h, w, 3) uint8, zarr v3 API (CONTRACTS section 4).

    Frames are written in blocks (`write(start, block)`) so the producer streams; attrs carry `t_ref_s` (list),
    `size` ([w, h]) and whatever the producer adds.
    """

    def __init__(self, out_path: str | os.PathLike, n_frames: int, size: tuple[int, int], t_ref_s,
                 chunk: int = 64, attrs: Mapping | None = None):
        import zarr

        self.path = Path(out_path)
        self.n_frames = int(n_frames)
        self.size = (int(size[0]), int(size[1]))
        w, h = self.size
        t = [float(x) for x in np.asarray(t_ref_s, dtype=float).reshape(-1)]
        if len(t) != self.n_frames:
            raise ValueError(f"t_ref_s has {len(t)} entries for {self.n_frames} frames")
        attributes = {"t_ref_s": t, "size": [w, h], "layout": "frame,row,col,rgb", "dtype": "uint8",
                      "colour_space": "srgb_preview"}
        if attrs:
            attributes.update({k: _jsonable(v) for k, v in attrs.items()})
        self.array = zarr.create_array(store=str(self.path), shape=(self.n_frames, h, w, 3), dtype="uint8",
                                       chunks=(max(1, min(int(chunk), max(self.n_frames, 1))), h, w, 3),
                                       attributes=attributes, overwrite=True)
        self.written = 0

    def write(self, start: int, block: np.ndarray) -> None:
        """Write a block of (n, h, w, 3) uint8 preview frames starting at `start` (CONTRACTS section 4 proxy array)."""
        block = np.asarray(block, dtype=np.uint8)
        if block.ndim == 3:
            block = block[None]
        w, h = self.size
        if block.shape[1:] != (h, w, 3):
            raise ValueError(f"block shape {block.shape[1:]} does not match proxy size {(h, w, 3)}")
        self.array[int(start): int(start) + block.shape[0]] = block
        self.written = max(self.written, int(start) + block.shape[0])

    def set_attr(self, key: str, value) -> None:
        """Set one JSON attribute on the proxy array (e.g. `n_frames_decoded`), CONTRACTS section 4."""
        self.array.attrs[key] = _jsonable(value)


def _jsonable(v):
    if isinstance(v, np.ndarray):
        return v.tolist()
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, tuple):
        return list(v)
    if isinstance(v, dict):
        return {k: _jsonable(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_jsonable(x) for x in v]
    return v


def open_proxy(path: str | os.PathLike):
    """Open a proxy zarr array read-only (zarr v3 API); `.attrs["t_ref_s"]` holds the frame times. CONTRACTS section 4 proxy_128x72.zarr."""
    import zarr

    return zarr.open_array(str(path), mode="r")


def write_proxy_video(reader: BayerClipReader, out_zarr_path: str | os.PathLike, t_ref_s, size: tuple[int, int] = (128, 72),
                      calibration=None, chunk: int = 64, black_level: float | None = None, white_level: float | None = None,
                      awb_gains: tuple[float, float] | None = None, gamma: float = 2.2, n_frames: int | None = None) -> dict:
    """Stream a Pi clip into `proxy_128x72.zarr`: (n_frames, h, w, 3) uint8 demosaiced preview, attrs t_ref_s and size.

    `calibration` is an object with `.apply(planes) -> float planes` (palmppg.ingest.calibration.UnitCalibration)
    or None. With a calibration the dark level is already removed, so the preview maps 0..(white - black) to
    0..1; without one `black_level` is subtracted (both levels from cfg `pi.black_level` / `pi.white_level`,
    passed by the caller). `awb_gains` default to the clip meta `awb_gains` (r, b). Serves section 12 compute
    hygiene (cache a 128x72 demosaiced proxy per clip) and section 6.1 (preview for hand landmarks).
    """
    n_total = reader.n_frames if n_frames is None else min(int(n_frames), reader.n_frames)
    t = np.asarray(t_ref_s, dtype=float).reshape(-1)[:n_total]
    if t.size != n_total:
        raise ValueError(f"t_ref_s has {t.size} entries for {n_total} frames")
    if white_level is None:
        white_level = float((1 << int(reader.meta.get("bit_depth", 10))) - 1)
    if black_level is None:
        black_level = float(reader.meta.get("black_level", 0.0))
    if awb_gains is None:
        g = reader.meta.get("awb_gains") or (1.0, 1.0)
        awb_gains = (float(g[0]), float(g[1]))
    applied = calibration is not None and bool(getattr(calibration, "applied", True))
    if applied:
        prev_black, prev_white = 0.0, float(white_level) - float(black_level)
    else:
        prev_black, prev_white = float(black_level), float(white_level)
    writer = ProxyZarrWriter(out_zarr_path, n_total, size, t, chunk=chunk, attrs={
        "camera": "pi", "gamma": gamma, "awb_gains": list(awb_gains), "calibration_applied": applied,
        "black_level": black_level, "white_level": white_level, "source": str(reader.path),
    })
    w, h = int(size[0]), int(size[1])
    for idx, planes in reader.iter_chunks(chunk=chunk, stop=n_total):
        block = np.empty((idx.size, h, w, 3), dtype=np.uint8)
        for j in range(idx.size):
            single = {k: v[j] for k, v in planes.items()}
            if calibration is not None:
                single = calibration.apply(single)
            block[j] = demosaic_preview(single, prev_black, prev_white, awb_gains, gamma, size=(w, h))
        writer.write(int(idx[0]), block)
    return {"path": str(writer.path), "n_frames": int(n_total), "size": [w, h], "calibration_applied": applied}
