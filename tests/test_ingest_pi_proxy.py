"""pi_proxy chain: full-resolution demosaic of calibrated Bayer frames -> H.264 mp4 with known colour and frame count."""
from __future__ import annotations

import numpy as np
import pytest

from palmppg.core.config import rng
from palmppg.ingest.bayer import BayerClipReader
from palmppg.ingest.calibration import UnitCalibration
from palmppg.ingest.phone import PhoneClipReader, ffprobe_frame_pts
from palmppg.ingest.pi_proxy import cv2_bayer_code, demosaic_full_srgb, demosaic_mosaic_preview, make_pi_proxy
from tests.test_ingest_helpers import (
    BLACK,
    FFMPEG,
    WHITE,
    make_mosaic,
    write_synthetic_pi_clip,
    write_unit_calibration,
)

pytestmark = pytest.mark.skipif(FFMPEG is None, reason="ffmpeg not on PATH")
W, H = 192, 108
LEVELS = {"R": 480.0, "G1": 720.0, "G2": 720.0, "B": 240.0}


def _expected_u8(level, gain=1.0, gamma=2.2):
    return 255.0 * min(1.0, gain * level / (WHITE - BLACK)) ** (1 / gamma)


def test_cv2_codes_for_every_pattern():
    import cv2

    gen = rng(0, "codes")
    for pattern in ("RGGB", "BGGR", "GRBG", "GBRG"):
        m = make_mosaic(LEVELS, 16, 16, None, gen, noise_sd=0.0, pattern=pattern)
        rgb = cv2.cvtColor(m, cv2_bayer_code(pattern))
        assert rgb[8, 8].tolist() == [BLACK + 480, BLACK + 720, BLACK + 240], pattern
    with pytest.raises(ValueError):
        cv2_bayer_code("RGBW")


def test_demosaic_full_srgb_known_colour():
    gen = rng(1, "demo")
    m = make_mosaic(LEVELS, 32, 32, None, gen, noise_sd=0.0)
    rgb = demosaic_full_srgb(m.astype(np.float32) - BLACK, "RGGB", WHITE - BLACK, awb_gains=(1.2, 1.5), gamma=2.2)
    assert rgb.shape == (32, 32, 3) and rgb.dtype == np.uint8
    centre = rgb[8:24, 8:24].reshape(-1, 3).mean(axis=0)
    assert abs(centre[0] - _expected_u8(480, 1.2)) < 1.5
    assert abs(centre[1] - _expected_u8(720)) < 1.5
    assert abs(centre[2] - _expected_u8(240, 1.5)) < 1.5
    prev = demosaic_mosaic_preview(m, "RGGB", BLACK, WHITE)
    assert abs(prev[16, 16, 1] - _expected_u8(720)) < 1.5


def test_make_pi_proxy_frame_count_colour_and_times(tmp_path, cfg):
    unit = tmp_path / "unit_01"
    write_unit_calibration(unit, W, H, strength=0.3)
    clip = write_synthetic_pi_clip(tmp_path / "pi", n_frames=20, width=W, height=H, strength=0.3, levels=LEVELS)
    meta = clip["meta"]
    cal = UnitCalibration.load(unit, meta, black_level=cfg.get("pi.black_level"))
    reader = BayerClipReader(clip["raw"], meta)
    t = np.arange(20) / 30.0 + 3.0
    info = make_pi_proxy(reader, cal, meta, tmp_path / "work" / "pi_proxy" / "proxy.mp4", crf=cfg.get("phone.proxy_crf"),
                         chunk=8, t_ref_s=t, black_level=cfg.get("pi.black_level"), white_level=cfg.get("pi.white_level"))
    assert info["n_frames"] == 20 and info["crf"] == cfg.get("phone.proxy_crf") and info["camera"] == "pi_proxy"
    assert info["calibration_applied"] is True and (info["width"], info["height"]) == (W, H)
    np.testing.assert_allclose(info["frame_times"], t)
    probe = ffprobe_frame_pts(info["path"])
    assert probe.n_frames == 20 and probe.codec == "h264" and probe.is_vfr is False
    r = PhoneClipReader(info["path"])
    assert r.n_frames == 20 and (r.width, r.height) == (W, H) and not r.has_audio
    means = []
    for _i, _t, rgb in r.iter_frames():
        means.append(rgb[H // 2 - 10: H // 2 + 10, W // 2 - 10: W // 2 + 10].reshape(-1, 3).mean(axis=0))
    means = np.asarray(means)
    # the vignette is calibrated away and the centre colour matches the demosaiced sRGB levels
    expect = np.array([_expected_u8(480), _expected_u8(720), _expected_u8(240)])
    np.testing.assert_allclose(means.mean(axis=0), expect, atol=6)
    corner = []
    for _i, _t, rgb in PhoneClipReader(info["path"]).iter_frames(stop=3):
        corner.append(rgb[4:14, 4:14, 1].mean())
    assert abs(np.mean(corner) - _expected_u8(720)) < 8  # corners are flat after calibration (no vignette)
    # downsized variant and the uncalibrated path
    small = make_pi_proxy(reader, None, meta, tmp_path / "work" / "small.mp4", crf=23, size=(96, 54), t_ref_s=t,
                          black_level=cfg.get("pi.black_level"), white_level=cfg.get("pi.white_level"), n_frames=5)
    assert small["n_frames"] == 5 and small["calibration_applied"] is False
    rs = PhoneClipReader(small["path"])
    assert (rs.width, rs.height, rs.n_frames) == (96, 54, 5)
    with pytest.raises(ValueError):
        make_pi_proxy(reader, None, meta, tmp_path / "bad.mp4", crf=23, size=(95, 54), black_level=64, white_level=1023)
    reader.close()
