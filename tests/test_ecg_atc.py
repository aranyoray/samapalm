"""ATC writer / parser round trip, tolerance to bad CRCs and unknown blocks, clip detection (CONTRACTS 3.6)."""
from __future__ import annotations

import datetime as dt
import struct
import zlib

import numpy as np
import pytest

from palmppg.ecg.atc import (
    DEFAULT_RESOLUTION_NV,
    HEADER_LEN,
    INT16_MAX,
    MAGIC,
    ATCError,
    describe,
    parse_atc,
    parse_atc_datetime,
    walk_blocks,
    write_atc,
)
from tests.test_ecg_helpers import synthetic_ecg

TZ = dt.timezone(dt.timedelta(hours=5, minutes=30))


def _signal(seconds=10.0):
    return synthetic_ecg(duration_s=seconds, hr_bpm=70.0, seed=1)["x"]


def test_roundtrip_samples_fs_start_time_info_and_blocks(tmp_path):
    x = _signal()
    start = dt.datetime(2026, 10, 17, 9, 15, 30, tzinfo=TZ)
    info = {"uuid": "ABC-123", "phone_model": "OnePlus 12", "recorder_sw": "kardia 3.2", "location": "Kolkata"}
    res = write_atc(tmp_path / "k.atc", x, fs=300, start_time=start, info=info, annotations=b"\x01\x02",
                    extra_blocks=[(b"xtra", b"\xde\xad\xbe\xef" * 3)])
    assert res["n_clipped"] == 0 and res["n_samples"] == x.size
    p = parse_atc(tmp_path / "k.atc")
    assert p["fs"] == 300.0 and p["resolution_nv"] == DEFAULT_RESOLUTION_NV
    assert p["n_samples"] == x.size and abs(p["duration_s"] - 10.0) < 1e-9
    assert p["samples_mv"].dtype == np.float32
    # quantisation at 500 nV/LSB: every sample within half an LSB (0.00025 mV)
    assert np.max(np.abs(p["samples_mv"].astype(np.float64) - x)) <= 0.5 * DEFAULT_RESOLUTION_NV * 1e-6 + 1e-9
    assert p["start_time"] == start and p["start_time"].utcoffset() == dt.timedelta(hours=5, minutes=30)
    assert p["info"]["uuid"] == "ABC-123" and p["info"]["phone_model"] == "OnePlus 12"
    assert p["info"]["location"] == "Kolkata" and p["info"]["recorder_hw"] == ""
    assert p["blocks"] == ["info", "fmt", "ecg", "ann", "xtra"]
    assert p["unknown_blocks"] == ["xtra"] and p["ann_bytes"] == b"\x01\x02"
    assert all(p["crc_ok"].values()) and p["problems"] == []
    assert p["clipped"] is False and p["n_clipped"] == 0
    assert p["version"] == (1, 0, 0) and p["format"] == 1


def test_crc_mismatch_is_logged_not_fatal_and_strict_raises(tmp_path):
    x = _signal(5.0)
    path = tmp_path / "bad.atc"
    write_atc(path, x, fs=300, start_time="2026-10-17T09:15:30+05:30")
    data = bytearray(path.read_bytes())
    blocks, _ = walk_blocks(bytes(data))
    ecg = next(b for b in blocks if b["name"] == "ecg")
    k = ecg["offset"] + 8 + 100          # inside the ecg payload
    data[k] ^= 0xFF
    path.write_bytes(bytes(data))
    p = parse_atc(path)
    assert p["crc_ok"] == {"info": True, "fmt": True, "ecg": False}
    assert p["n_samples"] == x.size      # samples still returned
    assert any("crc mismatch" in m and "ecg" in m for m in p["problems"])
    assert "BAD" in describe(path)
    with pytest.raises(ATCError):
        parse_atc(path, strict=True)


def test_clip_detection_of_int16_saturation(tmp_path):
    x = _signal(4.0) * 30.0              # +/- 30 mV exceeds the 16.38 mV int16 range at 500 nV/LSB
    res = write_atc(tmp_path / "clip.atc", x, fs=300)
    assert res["n_clipped"] > 0
    p = parse_atc(tmp_path / "clip.atc")
    assert p["clipped"] is True and p["n_clipped"] == res["n_clipped"]
    assert abs(p["clipped_frac"] - res["n_clipped"] / x.size) < 1e-12
    assert int(p["raw_int16"].max()) == INT16_MAX
    assert abs(float(p["samples_mv"].max()) - INT16_MAX * DEFAULT_RESOLUTION_NV * 1e-6) < 1e-6
    unclipped = parse_atc(tmp_path / "clip.atc")["raw_int16"]
    assert (np.abs(unclipped) == INT16_MAX).sum() + (unclipped == -INT16_MAX - 1).sum() == res["n_clipped"]


def test_describe_lists_every_block_with_crc_state(tmp_path):
    write_atc(tmp_path / "d.atc", _signal(2.0), fs=300, start_time="2026-10-17T09:15:30",
              extra_blocks=[(b"zzzz", b"\x00" * 7)])
    text = describe(tmp_path / "d.atc")
    for name in ("b'info'", "b'fmt '", "b'ecg '", "b'zzzz'"):
        assert name in text
    assert "600 int16 samples" in text and "unknown block" in text and "no problems" in text
    assert "frequency_hz=300" in text and "resolution_nv=500" in text


def test_truncated_file_is_tolerated_and_unknown_fmt_defaults(tmp_path):
    path = tmp_path / "t.atc"
    write_atc(path, _signal(3.0), fs=300)
    data = path.read_bytes()
    path.write_bytes(data[:-50])         # chop the end of the ecg block and its CRC
    p = parse_atc(path)
    assert any("truncated" in m for m in p["problems"]) and "ecg" not in p["blocks"]
    assert p["n_samples"] == 0 and p["fs"] == 300.0
    # a file with only an ecg block (no fmt) falls back to the defaults and says so
    payload = np.arange(-5, 5, dtype="<i2").tobytes()
    chunk = struct.pack("<I", len(payload)) + b"ecg " + payload + struct.pack("<I", zlib.crc32(b"ecg " + payload))
    (tmp_path / "nofmt.atc").write_bytes(MAGIC + b"\x01\x00\x00" + chunk)
    q = parse_atc(tmp_path / "nofmt.atc", fs_default=250.0)
    assert q["fs"] == 250.0 and q["n_samples"] == 10 and any("no fmt block" in m for m in q["problems"])
    assert q["start_time"] is None and q["info"] == {}
    assert np.allclose(q["samples_mv"], np.arange(-5, 5) * 500e-6)


def test_not_an_atc_file_raises(tmp_path):
    (tmp_path / "x.atc").write_bytes(b"%PDF-1.4 not an atc")
    with pytest.raises(ATCError):
        parse_atc(tmp_path / "x.atc")
    assert "not an ATC file" in describe(tmp_path / "x.atc")
    (tmp_path / "short.atc").write_bytes(MAGIC[:3])
    with pytest.raises(ATCError):
        parse_atc(tmp_path / "short.atc")
    assert len(MAGIC) + 3 == HEADER_LEN


def test_datetime_parsing_variants():
    assert parse_atc_datetime("2026-10-17T09:15:30Z") == dt.datetime(2026, 10, 17, 9, 15, 30, tzinfo=dt.UTC)
    assert parse_atc_datetime("2026-10-17 09:15:30") == dt.datetime(2026, 10, 17, 9, 15, 30)
    assert parse_atc_datetime("20261017T091530") == dt.datetime(2026, 10, 17, 9, 15, 30)
    assert parse_atc_datetime("") is None and parse_atc_datetime(None) is None
    assert parse_atc_datetime("yesterday") is None
