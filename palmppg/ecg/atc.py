"""AliveCor ATC v1 chunk files: tolerant parser, chunk lister and a writer for synthetic data.

Serves protocol section 6.4 ("ingest ATC: parse header for start time, fs, gain; samples to millivolts")
against the layout fixed in CONTRACTS section 3.6:

  header  : b"ALIVE" + 3 version bytes (8 bytes)
  block   : u32 length (LE) | 4-byte id | data[length] | u32 crc32 (LE), crc32 over id + data
  "info"  : date 32 B ASCII ISO8601 | uuid 40 B | phone udid 44 B | phone model 32 B |
            recorder sw 32 B | recorder hw 32 B | location 52 B  (264 B, NUL padded)
  "fmt "  : u8 format | u16 frequency Hz | u16 resolution nV/LSB (500) | u8 flags | u16 reserved (8 B)
  "ecg "  : int16 LE samples, lead I
  "ann "  : optional annotations (kept as bytes)

Unknown blocks are skipped and listed; a bad CRC is recorded in `crc_ok` and logged, never fatal
(DECISIONS D-007: the first real Kardia export must be opened with `describe()` before any ECG result is
trusted). Units: samples in millivolts (resolution_nv * 1e-6 mV per LSB), fs in Hz, duration in seconds.
"""
from __future__ import annotations

import datetime as dt
import logging
import struct
import zlib
from collections.abc import Mapping, Sequence
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

MAGIC = b"ALIVE"
HEADER_LEN = 8
DEFAULT_VERSION = (1, 0, 0)
INFO_FIELDS: tuple[tuple[str, int], ...] = (
    ("date", 32), ("uuid", 40), ("phone_udid", 44), ("phone_model", 32),
    ("recorder_sw", 32), ("recorder_hw", 32), ("location", 52),
)
INFO_LEN = sum(n for _, n in INFO_FIELDS)  # 264
FMT_STRUCT = struct.Struct("<BHHBH")        # format, frequency, resolution_nv, flags, reserved
U32 = struct.Struct("<I")
ID_INFO, ID_FMT, ID_ECG, ID_ANN = b"info", b"fmt ", b"ecg ", b"ann "
KNOWN_IDS = (ID_INFO, ID_FMT, ID_ECG, ID_ANN)
INT16_MIN, INT16_MAX = -32768, 32767
NV_PER_MV = 1e6
DEFAULT_RESOLUTION_NV = 500
DEFAULT_FS = 300.0


class ATCError(ValueError):
    """Raised when a file is not an ATC file at all (bad magic / too short), or on CRC failure in strict mode."""


# --------------------------------------------------------------------------- low-level helpers
def _crc(block_id: bytes, payload: bytes) -> int:
    return zlib.crc32(block_id + payload) & 0xFFFFFFFF


def _chunk(block_id: bytes, payload: bytes) -> bytes:
    if len(block_id) != 4:
        raise ValueError(f"block id must be 4 bytes, got {block_id!r}")
    return U32.pack(len(payload)) + block_id + payload + U32.pack(_crc(block_id, payload))


def _fixed_ascii(value: str | None, width: int) -> bytes:
    raw = (value or "").encode("ascii", "replace")[:width]
    return raw + b"\x00" * (width - len(raw))


def _ascii_field(raw: bytes) -> str:
    return raw.split(b"\x00", 1)[0].decode("ascii", "replace").strip()


def _block_name(block_id: bytes) -> str:
    return block_id.decode("ascii", "replace").strip()


def parse_atc_datetime(text: str | None) -> dt.datetime | None:
    """ISO8601 text from the info block -> datetime (tz-aware when the text carries an offset), else None."""
    if not text:
        return None
    s = text.strip().replace("Z", "+00:00")
    try:
        return dt.datetime.fromisoformat(s)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y%m%dT%H%M%S", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def walk_blocks(data: bytes) -> tuple[list[dict], list[str]]:
    """Tolerant chunk walk. Returns ([{id, name, offset, length, payload, crc_stored, crc_calc, crc_ok}], problems)."""
    blocks: list[dict] = []
    problems: list[str] = []
    pos = HEADER_LEN
    n = len(data)
    while pos + 8 <= n:
        length = U32.unpack_from(data, pos)[0]
        block_id = data[pos + 4:pos + 8]
        start = pos + 8
        end = start + length
        if end + 4 > n:
            problems.append(f"truncated block {_block_name(block_id)!r} at offset {pos}: "
                            f"declares {length} B but only {n - start} B remain")
            break
        payload = data[start:end]
        crc_stored = U32.unpack_from(data, end)[0]
        crc_calc = _crc(block_id, payload)
        ok = crc_stored == crc_calc
        if not ok:
            problems.append(f"crc mismatch in block {_block_name(block_id)!r} at offset {pos} "
                            f"(stored 0x{crc_stored:08x}, computed 0x{crc_calc:08x})")
        blocks.append({"id": block_id, "name": _block_name(block_id), "offset": pos, "length": length,
                       "payload": payload, "crc_stored": crc_stored, "crc_calc": crc_calc, "crc_ok": ok})
        pos = end + 4
    if pos != n:
        problems.append(f"{n - pos} trailing byte(s) after the last complete block")
    return blocks, problems


def _parse_info(payload: bytes) -> dict:
    info: dict = {}
    pos = 0
    for name, width in INFO_FIELDS:
        info[name] = _ascii_field(payload[pos:pos + width]) if pos < len(payload) else ""
        pos += width
    return info


def _parse_fmt(payload: bytes) -> dict | None:
    if len(payload) < FMT_STRUCT.size:
        return None
    fmt, freq, res, flags, reserved = FMT_STRUCT.unpack_from(payload, 0)
    return {"format": int(fmt), "frequency_hz": int(freq), "resolution_nv": int(res),
            "flags": int(flags), "reserved": int(reserved)}


# --------------------------------------------------------------------------- public API
def parse_atc(path: str | Path, strict: bool = False, fs_default: float = DEFAULT_FS,
              resolution_nv_default: int = DEFAULT_RESOLUTION_NV) -> dict:
    """Parse an ATC file into samples in millivolts plus every header field (protocol 6.4, CONTRACTS 3.6).

    Returns a dict with: `fs` (Hz), `samples_mv` (float32, mV = raw * resolution_nv / 1e6), `raw_int16`,
    `resolution_nv`, `start_time` (datetime | None, from the info date), `info` (dict of the info fields),
    `blocks` (list of block names in file order), `crc_ok` ({block name: bool}), `n_samples`, `duration_s`,
    `version`, `format`, `flags`, `unknown_blocks`, `ann_bytes`, `n_clipped`, `clipped_frac`, `clipped`
    (int16 saturation at either rail), `problems` (list of human-readable issues) and `path`.

    Bad CRCs and unknown blocks are tolerated (logged, listed in `problems`), `strict=True` raises ATCError
    on any CRC failure. A missing `fmt ` block falls back to `fs_default` / `resolution_nv_default` and is
    listed as a problem.
    """
    path = Path(path)
    data = path.read_bytes()
    if len(data) < HEADER_LEN or data[:len(MAGIC)] != MAGIC:
        raise ATCError(f"{path}: not an ATC file (magic {data[:len(MAGIC)]!r}, {len(data)} bytes)")
    version = tuple(int(b) for b in data[len(MAGIC):HEADER_LEN])
    blocks, problems = walk_blocks(data)
    for p in problems:
        log.warning("%s: %s", path.name, p)
    if strict and any(not b["crc_ok"] for b in blocks):
        raise ATCError(f"{path}: CRC failure ({'; '.join(problems)})")

    info: dict = {}
    fmt: dict | None = None
    raw = np.zeros(0, dtype=np.int16)
    ann = b""
    unknown: list[str] = []
    names: list[str] = []
    crc_ok: dict[str, bool] = {}
    seen: dict[str, int] = {}
    for b in blocks:
        name = b["name"]
        seen[name] = seen.get(name, 0) + 1
        key = name if seen[name] == 1 else f"{name}#{seen[name]}"
        names.append(key)
        crc_ok[key] = bool(b["crc_ok"])
        bid, payload = b["id"], b["payload"]
        if bid == ID_INFO:
            info = _parse_info(payload)
        elif bid == ID_FMT:
            fmt = _parse_fmt(payload)
            if fmt is None:
                problems.append(f"fmt block too short ({len(payload)} B)")
        elif bid == ID_ECG:
            usable = len(payload) - (len(payload) % 2)
            if usable != len(payload):
                problems.append("ecg block has an odd byte count; last byte ignored")
            raw = np.frombuffer(payload[:usable], dtype="<i2").astype(np.int16)
        elif bid == ID_ANN:
            ann = payload
        else:
            unknown.append(key)
    if not any(b["id"] == ID_ECG for b in blocks):
        problems.append("no ecg block found")
    if fmt is None:
        problems.append(f"no fmt block: assuming fs={fs_default} Hz, resolution={resolution_nv_default} nV/LSB")
        fs = float(fs_default)
        resolution_nv = int(resolution_nv_default)
        fmt_format, fmt_flags = None, None
    else:
        fs = float(fmt["frequency_hz"]) if fmt["frequency_hz"] > 0 else float(fs_default)
        resolution_nv = int(fmt["resolution_nv"]) if fmt["resolution_nv"] > 0 else int(resolution_nv_default)
        if fmt["frequency_hz"] <= 0 or fmt["resolution_nv"] <= 0:
            problems.append("fmt block has a zero frequency or resolution; defaults applied")
        fmt_format, fmt_flags = fmt["format"], fmt["flags"]
    samples_mv = (raw.astype(np.float64) * (resolution_nv / NV_PER_MV)).astype(np.float32)
    n = int(raw.size)
    clipped = (raw >= INT16_MAX) | (raw <= INT16_MIN)
    n_clipped = int(clipped.sum())
    start_time = parse_atc_datetime(info.get("date"))
    if info and info.get("date") and start_time is None:
        problems.append(f"info date not ISO8601: {info.get('date')!r}")
    return {
        "path": str(path), "version": version, "fs": fs, "samples_mv": samples_mv, "raw_int16": raw,
        "resolution_nv": resolution_nv, "start_time": start_time, "info": info, "blocks": names,
        "crc_ok": crc_ok, "n_samples": n, "duration_s": n / fs if fs > 0 else float("nan"),
        "format": fmt_format, "flags": fmt_flags, "unknown_blocks": unknown, "ann_bytes": ann,
        "n_clipped": n_clipped, "clipped_frac": (n_clipped / n) if n else 0.0, "clipped": n_clipped > 0,
        "problems": problems,
    }


def describe(path: str | Path) -> str:
    """Human-readable chunk listing of an ATC file (DECISIONS D-007: run on the first real export).

    One line per block with offset, declared length, CRC state and a content summary; header problems
    (truncation, trailing bytes, bad CRC) are listed at the end. Never raises on a malformed body.
    """
    path = Path(path)
    data = path.read_bytes()
    lines = [f"{path} ({len(data)} bytes)"]
    if len(data) < HEADER_LEN or data[:len(MAGIC)] != MAGIC:
        lines.append(f"  not an ATC file: magic={data[:len(MAGIC)]!r}")
        return "\n".join(lines)
    version = ".".join(str(b) for b in data[len(MAGIC):HEADER_LEN])
    lines.append(f"  header: magic {MAGIC!r} version {version}")
    blocks, problems = walk_blocks(data)
    for b in blocks:
        state = "ok" if b["crc_ok"] else f"BAD (stored 0x{b['crc_stored']:08x}, computed 0x{b['crc_calc']:08x})"
        head = f"  block {b['id']!r:8} offset {b['offset']:>8} length {b['length']:>8} B crc {state}"
        bid, payload = b["id"], b["payload"]
        if bid == ID_INFO:
            info = _parse_info(payload)
            detail = ", ".join(f"{k}={v!r}" for k, v in info.items() if v)
        elif bid == ID_FMT:
            fmt = _parse_fmt(payload)
            detail = "too short" if fmt is None else ", ".join(f"{k}={v}" for k, v in fmt.items())
        elif bid == ID_ECG:
            raw = np.frombuffer(payload[:len(payload) - len(payload) % 2], dtype="<i2")
            if raw.size:
                detail = (f"{raw.size} int16 samples, min {int(raw.min())} max {int(raw.max())}, "
                          f"{int(((raw >= INT16_MAX) | (raw <= INT16_MIN)).sum())} at the int16 rails")
            else:
                detail = "0 samples"
        elif bid == ID_ANN:
            detail = f"{len(payload)} annotation bytes"
        else:
            detail = f"unknown block, first bytes {payload[:16].hex()}"
        lines.append(f"{head}\n      {detail}")
    if problems:
        lines.append("  problems:")
        lines.extend(f"    - {p}" for p in problems)
    else:
        lines.append("  no problems")
    return "\n".join(lines)


def write_atc(path: str | Path, samples_mv, fs: float = 300, start_time: dt.datetime | str | None = None,
              resolution_nv: int = DEFAULT_RESOLUTION_NV, info: Mapping[str, str] | None = None,
              annotations: bytes | None = None, extra_blocks: Sequence[tuple[bytes, bytes]] = (),
              fmt_format: int = 1, flags: int = 0, version: tuple[int, int, int] = DEFAULT_VERSION) -> dict:
    """Write an ATC v1 file that `parse_atc` reads back (synthetic participants, bench tests; CONTRACTS 3.6).

    `samples_mv` (float, millivolts) are quantised to int16 at `resolution_nv` nV/LSB and clipped to the
    int16 rails (the count is returned so a test can check the parser's clip detection). `start_time` goes
    into the info date field as ISO8601 (a datetime is written with `isoformat()`, a string verbatim).
    `extra_blocks` are `(4-byte id, payload)` pairs appended after the known blocks (unknown-block tests).
    Returns {path, n_samples, n_clipped, bytes}.
    """
    path = Path(path)
    x = np.asarray(samples_mv, dtype=np.float64)
    if x.ndim != 1:
        raise ValueError("samples_mv must be one-dimensional")
    lsb = np.round(x * (NV_PER_MV / float(resolution_nv)))
    n_clipped = int(np.sum((lsb > INT16_MAX) | (lsb < INT16_MIN)))
    raw = np.clip(lsb, INT16_MIN, INT16_MAX).astype("<i2")

    if isinstance(start_time, dt.datetime):
        date_text = start_time.isoformat()
    else:
        date_text = start_time or ""
    fields = {k: "" for k, _ in INFO_FIELDS}
    fields.update({k: str(v) for k, v in (info or {}).items() if k in fields})
    fields["date"] = date_text
    info_payload = b"".join(_fixed_ascii(fields[name], width) for name, width in INFO_FIELDS)
    fmt_payload = FMT_STRUCT.pack(int(fmt_format), round(fs), int(resolution_nv), int(flags), 0)

    out = bytearray(MAGIC + bytes(int(v) & 0xFF for v in version))
    out += _chunk(ID_INFO, info_payload)
    out += _chunk(ID_FMT, fmt_payload)
    out += _chunk(ID_ECG, raw.tobytes())
    if annotations:
        out += _chunk(ID_ANN, bytes(annotations))
    for block_id, payload in extra_blocks:
        out += _chunk(bytes(block_id), bytes(payload))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(out))
    return {"path": str(path), "n_samples": int(raw.size), "n_clipped": n_clipped, "bytes": len(out)}
