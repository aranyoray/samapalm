"""Phone path on tiny ffmpeg-rendered mp4s: PTS (CFR and VFR), decode, sRGB roundtrip, audio tone, EIS, flat field."""
from __future__ import annotations

import numpy as np
import pytest

from palmppg.core.config import rng
from palmppg.ingest.phone import (
    LINEARISED_LABEL,
    PhoneClipReader,
    PhoneFlatField,
    corner_regions,
    detect_eis_warp,
    extract_audio,
    ffprobe_frame_pts,
    linear_to_srgb,
    srgb_to_linear,
)
from tests.test_ingest_helpers import FFMPEG, render_mp4, solid_frames, textured_frame

pytestmark = pytest.mark.skipif(FFMPEG is None, reason="ffmpeg not on PATH")
W, H = 320, 180


@pytest.fixture(scope="module")
def cfr_mp4(tmp_path_factory):
    d = tmp_path_factory.mktemp("cfr")
    gen = rng(1, "cfr")
    frames = [textured_frame(H, W, gen) for _ in range(10)]
    return render_mp4(d / "cfr.mp4", frames, fps=30.0)


@pytest.fixture(scope="module")
def vfr_mp4(tmp_path_factory):
    d = tmp_path_factory.mktemp("vfr")
    gen = rng(2, "vfr")
    frames = [textured_frame(H, W, gen) for _ in range(10)]
    return render_mp4(d / "vfr.mp4", frames, fps=30.0, vfr_jitter=0.6)


def test_ffprobe_pts_cfr(cfr_mp4):
    p = ffprobe_frame_pts(cfr_mp4)
    assert p.n_frames == 10 and p.pts_s.size == 10
    np.testing.assert_allclose(np.diff(p.pts_s), 1 / 30.0, atol=1e-4)
    assert p.pts_s[0] == pytest.approx(0.0, abs=1e-6)
    assert p.fps_nominal == pytest.approx(30.0)
    assert p.is_vfr is False and p.vfr_rel_std < 0.05
    assert p.codec == "h264" and (p.width, p.height) == (W, H)
    assert p.source_field == "pts_time"
    d = p.to_dict()
    assert isinstance(d["pts_s"], list) and len(d["pts_s"]) == 10


def test_ffprobe_pts_vfr_made_with_setpts(vfr_mp4):
    p = ffprobe_frame_pts(vfr_mp4)
    assert p.n_frames == 10
    d = np.diff(p.pts_s)
    # intervals alternate 1.6 and 0.4 periods, as rendered
    assert np.all(np.isclose(d[::2], 1.6 / 30.0, atol=2e-3)) and np.all(np.isclose(d[1::2], 0.4 / 30.0, atol=2e-3))
    # std of [1.6, 0.4, 1.6, ...] periods over their median (1.6) is 0.37: well above the 5 % VFR threshold
    assert p.is_vfr is True and abs(p.vfr_rel_std - 0.6 / 1.6) < 0.02
    assert p.diff_median_s == pytest.approx(np.median(d))
    with pytest.raises(FileNotFoundError):
        ffprobe_frame_pts(vfr_mp4.with_name("missing.mp4"))


def test_phone_clip_reader_count_and_colours(tmp_path):
    frames = solid_frames(12, H, W, (200, 60, 30)) + solid_frames(12, H, W, (30, 60, 200))
    mp4 = render_mp4(tmp_path / "solid.mp4", frames, fps=30.0, crf=10)
    r = PhoneClipReader(mp4)
    assert r.n_frames == 24 and len(r) == 24
    assert (r.width, r.height, r.codec, r.has_audio) == (W, H, "h264", False)
    assert r.fps_nominal == pytest.approx(30.0)
    md = r.metadata()
    assert md["n_frames"] == 24 and md["has_audio"] is False
    seen = []
    for idx, pts, rgb in r.iter_frames():
        assert rgb.shape == (H, W, 3) and rgb.dtype == np.uint8
        assert pts == pytest.approx(idx / 30.0, abs=1e-4)
        seen.append(rgb.reshape(-1, 3).mean(axis=0))
    assert len(seen) == 24
    np.testing.assert_allclose(seen[3], [200, 60, 30], atol=8)   # yuv420p + x264 keep solid colours within a few levels
    np.testing.assert_allclose(seen[20], [30, 60, 200], atol=8)
    assert [i for i, _, _ in r.iter_frames(start=2, stop=9, step=3)] == [2, 5, 8]
    pts = r.frame_pts()
    assert pts.size == 24 and np.allclose(np.diff(pts), 1 / 30.0, atol=1e-4)
    with pytest.raises(FileNotFoundError):
        PhoneClipReader(tmp_path / "nope.mp4")


def test_srgb_roundtrip_and_known_points():
    u8 = np.arange(256, dtype=np.uint8)
    lin = srgb_to_linear(u8)
    assert lin.dtype == np.float32 and lin[0] == 0.0 and lin[255] == pytest.approx(1.0)
    assert np.all(np.diff(lin) > 0)
    assert srgb_to_linear(np.array([0.5], np.float32))[0] == pytest.approx(0.2140, abs=5e-4)   # standard sRGB mid-grey
    assert srgb_to_linear(np.array([0.04045], np.float32))[0] == pytest.approx(0.04045 / 12.92, rel=1e-4)
    back = linear_to_srgb(lin, to_uint8=True)
    np.testing.assert_array_equal(back, u8)
    x = np.linspace(0, 1, 1001, dtype=np.float32)
    np.testing.assert_allclose(srgb_to_linear(linear_to_srgb(x)), x, atol=2e-6)
    assert linear_to_srgb(np.array([0.2140], np.float32))[0] == pytest.approx(0.5, abs=5e-4)
    assert LINEARISED_LABEL == "inverted_srgb"
    assert "cannot be truly linearised" in " ".join(srgb_to_linear.__doc__.split())


def test_extract_audio_tone_frequency(tmp_path):
    mp4 = render_mp4(tmp_path / "tone.mp4", solid_frames(30, 64, 64, (90, 90, 90)), fps=30.0, tone_hz=2500.0, tone_s=1.0)
    r = PhoneClipReader(mp4)
    assert r.has_audio and r.audio_rate == 48000
    fs, mono = extract_audio(mp4)
    assert fs == 48000 and mono.dtype == np.float32 and mono.ndim == 1
    assert abs(mono.size / fs - 1.0) < 0.1
    seg = mono[int(0.2 * fs): int(0.8 * fs)]
    spec = np.abs(np.fft.rfft(seg * np.hanning(seg.size)))
    f = np.fft.rfftfreq(seg.size, 1 / fs)
    assert abs(f[np.argmax(spec)] - 2500.0) < 5.0
    assert 0.1 < np.abs(seg).max() <= 1.0
    fs2, mono2 = extract_audio(mp4, target_fs=8000)
    assert fs2 == 8000 and abs(mono2.size / 8000 - 1.0) < 0.1
    silent = render_mp4(tmp_path / "silent.mp4", solid_frames(3, 64, 64, (90, 90, 90)))
    with pytest.raises(ValueError):
        extract_audio(silent)


def test_eis_detector_static_vs_shifted(tmp_path, cfg):
    gen = rng(11, "eis")
    base = textured_frame(H, W, gen)
    static = render_mp4(tmp_path / "static.mp4", [base.copy() for _ in range(20)], fps=30.0, crf=18)
    shifted = render_mp4(tmp_path / "shift.mp4", [np.roll(base, 2 * i, axis=1) for i in range(20)], fps=30.0, crf=18)
    thr = cfg.get("qc.eis_warp_px_max")
    s = detect_eis_warp(PhoneClipReader(static), n_sample=10, warp_px_max=thr)
    assert s["flag"] is False and s["n_pairs"] == 10 and s["n_pairs_valid"] == 10
    assert s["warp_px_p90"] < 0.3 and s["warp_px_median"] < 0.2
    assert len(s["regions"]) == 4 and s["regions"] == [list(r) for r in corner_regions(W, H, 0.08)]
    m = detect_eis_warp(PhoneClipReader(shifted), n_sample=10, warp_px_max=thr)
    assert m["flag"] is True
    assert abs(m["warp_px_median"] - 2.0) < 0.3 and abs(m["warp_px_p90"] - 2.0) < 0.4
    # explicit static regions (two boxes) also work
    m2 = detect_eis_warp(PhoneClipReader(shifted), static_regions=[(0, 0, 60, 60), (260, 120, 60, 60)], n_sample=5, warp_px_max=thr)
    assert m2["flag"] is True and abs(m2["warp_px_median"] - 2.0) < 0.3
    # featureless corners -> insufficient features, flag None
    flat = render_mp4(tmp_path / "flat.mp4", solid_frames(6, H, W, (120, 120, 120)))
    f = detect_eis_warp(PhoneClipReader(flat), n_sample=4, warp_px_max=thr)
    assert f["flag"] is None and f["insufficient_features"] is True
    one = render_mp4(tmp_path / "one.mp4", [base.copy()])
    assert detect_eis_warp(PhoneClipReader(one), warp_px_max=thr)["n_pairs"] == 0


def test_phone_flat_field_corrects_vignette(tmp_path):
    yy, xx = np.mgrid[0:H, 0:W]
    r2 = ((yy - H / 2) / (H / 2)) ** 2 + ((xx - W / 2) / (W / 2)) ** 2
    vig = (1.0 - 0.4 * r2 / 2.0).astype(np.float32)
    white_lin = 0.6 * vig[..., None] * np.array([1.0, 1.0, 0.9], np.float32)
    frames = [linear_to_srgb(white_lin, to_uint8=True) for _ in range(8)]
    mp4 = render_mp4(tmp_path / "phone_flatfield.mp4", frames, fps=30.0, crf=8)
    ff = PhoneFlatField.load(mp4, downscale=4, max_frames=8)
    assert ff.n_frames_used == 8 and ff.full_size == (W, H)
    assert ff.vignetting_pct() > 10.0
    assert ff.residual_pct() < 0.5
    # a frame with the same vignette becomes flat (within the compression noise)
    corrected = ff.apply(srgb_to_linear(frames[0]))
    assert corrected.shape == (H, W, 3) and corrected.dtype == np.float32
    centre = corrected[H // 2 - 5: H // 2 + 5, W // 2 - 5: W // 2 + 5].mean(axis=(0, 1))
    corner = corrected[8:18, 8:18].mean(axis=(0, 1))
    assert np.all(np.abs(corner / centre - 1.0) < 0.05)
    raw = srgb_to_linear(frames[0])
    assert raw[8:18, 8:18].mean() / raw[H // 2 - 5: H // 2 + 5, W // 2 - 5: W // 2 + 5].mean() < 0.75
    s = ff.summary()
    assert s["colour_space"] == "inverted_srgb" and s["gain_max"] > 1.1
    p = ff.save(tmp_path / "ff.npz")
    back = PhoneFlatField.load_npz(p)
    np.testing.assert_allclose(back.gain_small, ff.gain_small)
    with pytest.raises(ValueError):
        PhoneFlatField.from_frames([])
