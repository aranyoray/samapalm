"""Packed 10-bit Bayer: roundtrips at full geometry and padded stride, plane split, streaming reader, preview, proxy zarr."""
from __future__ import annotations

import numpy as np
import pytest

from palmppg.core.config import rng
from palmppg.ingest.bayer import (
    BayerClipReader,
    default_stride,
    demosaic_preview,
    merge_planes,
    open_proxy,
    pack_csi2p_10bit,
    payload_bytes,
    plane_offsets,
    split_planes,
    unpack_csi2p_10bit,
    write_proxy_video,
)


def test_default_stride_matches_contract():
    assert default_stride(1536) == 1920
    assert payload_bytes(1536) == 1920
    assert default_stride(384) == 480
    assert default_stride(100) == 128  # ceil(125) -> next multiple of 32
    assert default_stride(4) == 32


def test_known_byte_layout_four_pixels():
    # pixels 0..3 = 1023, 0, 513, 2 -> high bytes 255, 0, 128, 0 ; low bits 3,0,1,2 -> 0b10_01_00_11 = 0x93
    frame = np.array([[1023, 0, 513, 2]], dtype=np.uint16)
    packed = pack_csi2p_10bit(frame, stride_bytes=32)
    assert len(packed) == 32
    assert packed[:5] == bytes([255, 0, 128, 0, 0x93])
    assert packed[5:] == bytes(27)
    back = unpack_csi2p_10bit(packed, 4, 1, 32)
    assert back.tolist() == [[1023, 0, 513, 2]]


@pytest.mark.parametrize("width,height,stride", [(1536, 864, None), (384, 216, 512), (64, 8, None), (20, 6, 64)])
def test_roundtrip_random(width, height, stride):
    gen = rng(123, f"roundtrip-{width}")
    frame = gen.integers(0, 1024, size=(height, width), dtype=np.uint16)
    packed = pack_csi2p_10bit(frame, stride)
    expected_stride = stride or default_stride(width)
    assert len(packed) == expected_stride * height
    back = unpack_csi2p_10bit(packed, width, height, expected_stride)
    assert back.dtype == np.uint16
    np.testing.assert_array_equal(back, frame)


def test_unpack_rejects_short_buffer_and_pack_rejects_overflow():
    with pytest.raises(ValueError):
        unpack_csi2p_10bit(bytes(10), 8, 2, 32)
    with pytest.raises(ValueError):
        pack_csi2p_10bit(np.array([[1024]], dtype=np.uint16))


def test_unpack_stack_of_frames():
    gen = rng(5, "stack")
    frames = gen.integers(0, 1024, size=(3, 6, 8), dtype=np.uint16)
    buf = b"".join(pack_csi2p_10bit(f) for f in frames)
    back = unpack_csi2p_10bit(buf, 8, 6, default_stride(8))
    assert back.shape == (3, 6, 8)
    np.testing.assert_array_equal(back, frames)


def test_split_planes_rggb_known_pattern():
    h, w = 6, 8
    frame = np.zeros((h, w), dtype=np.uint16)
    frame[0::2, 0::2] = 900  # R
    frame[0::2, 1::2] = 500  # G1
    frame[1::2, 0::2] = 510  # G2
    frame[1::2, 1::2] = 100  # B
    p = split_planes(frame, "RGGB")
    assert set(p) == {"R", "G1", "G2", "B"}
    for k, v in {"R": 900, "G1": 500, "G2": 510, "B": 100}.items():
        assert p[k].shape == (3, 4)
        assert np.all(p[k] == v)
    np.testing.assert_array_equal(merge_planes(p, "RGGB"), frame)
    # other patterns: the same mosaic read as BGGR swaps R and B
    q = split_planes(frame, "BGGR")
    assert np.all(q["B"] == 900) and np.all(q["R"] == 100)
    assert plane_offsets("GRBG") == {"G1": (0, 0), "R": (0, 1), "B": (1, 0), "G2": (1, 1)}
    with pytest.raises(ValueError):
        split_planes(frame, "RGBW")


def _write_clip(tmp_path, n_frames=10, width=64, height=16, trailing=100, seed=9):
    gen = rng(seed, "clip")
    frames = gen.integers(0, 1024, size=(n_frames, height, width), dtype=np.uint16)
    raw = tmp_path / "clip1.raw"
    with open(raw, "wb") as fh:
        fh.writelines(pack_csi2p_10bit(f) for f in frames)
        fh.write(bytes(trailing))
    meta = {"width": width, "height": height, "bayer_pattern": "RGGB"}
    return raw, meta, frames


def test_reader_streams_ten_frames_and_reports_trailing_partial_frame(tmp_path):
    raw, meta, frames = _write_clip(tmp_path)
    r = BayerClipReader(raw, meta)
    assert r.n_frames == 10 and len(r) == 10
    assert r.trailing_bytes == 100 and not r.size_is_whole_frames
    assert r.stride_bytes == default_stride(64) and r.frame_bytes == default_stride(64) * 16
    d = r.describe()
    assert d["n_frames"] == 10 and d["trailing_bytes"] == 100
    # frame access returns the exact planes
    for i in (0, 4, 9):
        expect = split_planes(frames[i], "RGGB")
        got = r.frame(i)
        for k in expect:
            np.testing.assert_array_equal(got[k], expect[k])
    np.testing.assert_array_equal(r.mosaic(-1), frames[9])
    with pytest.raises(IndexError):
        r.frame(10)
    # iteration order and step
    idx = [i for i, _ in r.iter_frames(start=1, stop=8, step=3)]
    assert idx == [1, 4, 7]
    # chunked iteration covers every frame once with identical content
    seen = []
    for ids, planes in r.iter_chunks(chunk=4):
        assert planes["R"].shape[0] == ids.size
        for j, i in enumerate(ids):
            np.testing.assert_array_equal(planes["G2"][j], split_planes(frames[i])["G2"])
            seen.append(int(i))
    assert seen == list(range(10))
    r.close()


def test_reader_requires_geometry(tmp_path):
    raw, meta, _ = _write_clip(tmp_path, n_frames=2, trailing=0)
    with pytest.raises(KeyError):
        BayerClipReader(raw, {"height": 16})
    r = BayerClipReader(raw, meta)
    assert r.size_is_whole_frames and r.n_frames == 2


def test_demosaic_preview_known_values():
    h, w = 4, 6
    planes = {"R": np.full((h, w), 64 + 480, np.uint16), "G1": np.full((h, w), 64 + 960, np.uint16),
              "G2": np.full((h, w), 64 + 940, np.uint16), "B": np.full((h, w), 64 + 240, np.uint16)}
    out = demosaic_preview(planes, black_level=64, white_level=1023, awb_gains=(1.0, 2.0), gamma=2.2)
    assert out.shape == (h, w, 3) and out.dtype == np.uint8
    span = 1023 - 64
    exp_r = round(255 * (480 / span) ** (1 / 2.2))
    exp_g = round(255 * (950 / span) ** (1 / 2.2))
    exp_b = round(255 * min(1.0, 2.0 * 240 / span) ** (1 / 2.2))
    assert abs(int(out[0, 0, 0]) - exp_r) <= 1
    assert abs(int(out[0, 0, 1]) - exp_g) <= 1
    assert abs(int(out[0, 0, 2]) - exp_b) <= 1
    small = demosaic_preview(planes, 64, 1023, size=(3, 2))
    assert small.shape == (2, 3, 3)
    # gamma=1 is linear: 50 % signal -> 128
    lin = demosaic_preview({k: np.full((2, 2), 64 + span // 2, np.uint16) for k in planes}, 64, 1023, gamma=1.0)
    assert abs(int(lin[0, 0, 1]) - 128) <= 1


def test_write_proxy_video_streams_to_zarr(tmp_path):
    raw, meta, frames = _write_clip(tmp_path, n_frames=10, width=64, height=16, trailing=0)
    meta["awb_gains"] = [1.0, 1.0]
    r = BayerClipReader(raw, meta)
    t = np.arange(10) / 30.0 + 0.5
    info = write_proxy_video(r, tmp_path / "proxy.zarr", t, size=(16, 4), chunk=4, black_level=64, white_level=1023)
    assert info["n_frames"] == 10 and info["calibration_applied"] is False
    z = open_proxy(tmp_path / "proxy.zarr")
    assert z.shape == (10, 4, 16, 3) and z.dtype == np.uint8
    assert z.attrs["size"] == [16, 4]
    assert np.allclose(z.attrs["t_ref_s"], t)
    assert z.attrs["camera"] == "pi"
    # content matches a direct preview of frame 7
    expect = demosaic_preview(split_planes(frames[7]), 64, 1023, (1.0, 1.0), 2.2, size=(16, 4))
    np.testing.assert_array_equal(z[7], expect)
    with pytest.raises(ValueError):
        write_proxy_video(r, tmp_path / "bad.zarr", t[:3], size=(16, 4), black_level=64, white_level=1023)
