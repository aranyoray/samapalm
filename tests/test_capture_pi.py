"""capture_pi: local packer/crop ground truth, preflight gates (exit 2), and the simulated capture flow (section 4.6)."""
from __future__ import annotations

import csv
import json
import math
import shutil
from pathlib import Path

import numpy as np
import pytest
import yaml

from palmppg.capture import capture_pi as cp
from palmppg.core.config import rng

ROOT = Path(__file__).resolve().parents[1]
UNIT_CONFIG = ROOT / "configs" / "unit_config.yaml"
TODAY = "2026-10-17"
CONTRACT_META_KEYS = [  # CONTRACTS section 3.3, verbatim
    "unit_id", "operator", "dept", "stream", "app_ver", "study_id", "clip_id", "width", "height", "stride_bytes",
    "bayer_pattern", "bit_depth", "fps_nominal", "crop_rect", "exposure_us", "analogue_gain", "digital_gain", "awb_gains",
    "lens_position", "led_current_ma", "lux", "sensor_temp_c", "start_wall_ns", "stop_wall_ns", "start_mono_ns",
    "stop_mono_ns", "live_sqi", "motion_flag", "recovery_gate", "video_seconds", "capture_mode", "n_frames_written",
    "led_block", "thumb_block",
]


# --------------------------------------------------------------------------- local fixtures (no imports from other WPs)
def unpack_local(buf: bytes, width: int, height: int, stride: int) -> np.ndarray:
    """Reference unpacker written independently of the module under test (CONTRACTS 3.1 byte layout)."""
    a = np.frombuffer(buf, dtype=np.uint8)[: height * stride].reshape(height, stride)
    n_groups = math.ceil(width / 4)
    out = np.zeros((height, n_groups * 4), dtype=np.uint16)
    for g in range(n_groups):
        b = a[:, g * 5: g * 5 + 5].astype(np.uint16)
        for k in range(4):
            out[:, g * 4 + k] = (b[:, k] << 2) | ((b[:, 4] >> (2 * k)) & 0x3)
    return out[:, :width]


def write_clock_log(path: Path, rows: list[tuple[str, str, str, str, str, str]]) -> Path:
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "time_utc", "device", "offset_ms_vs_phone", "method", "operator"])
        w.writerows(rows)
    return path


@pytest.fixture
def ucfg() -> dict:
    with open(UNIT_CONFIG, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@pytest.fixture
def good_log(tmp_path) -> Path:
    return write_clock_log(tmp_path / "clock_sync_log.csv", [
        ("2026-10-16", "03:30:00", "pi_unit_01", "0.4", "chronyd_makestep", "RB"),
        (TODAY, "03:31:12", "pi_unit_01", "0.123", "chronyd_makestep", "RB"),
        (TODAY, "03:32:40", "kardia_tablet", "-340", "manual_ntp_app", "RB"),
    ])


def write_ucfg(tmp_path: Path, ucfg: dict, **camera_overrides) -> Path:
    data = yaml.safe_load(yaml.safe_dump(ucfg))
    data["camera"].update(camera_overrides)
    p = tmp_path / "unit_config.yaml"
    p.write_text(yaml.safe_dump(data), encoding="utf-8")
    return p


def read_pts(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


# --------------------------------------------------------------------------- packing and cropping ground truth
def test_default_stride_matches_contract():
    assert cp.default_stride(1536) == 1920
    assert cp.default_stride(384) == 480
    assert cp.default_stride(256) == 320
    assert cp.default_stride(1) == 32


def test_pack_roundtrip_against_independent_unpacker():
    g = rng(1, "pack")
    frame = g.integers(0, 1024, size=(12, 20), dtype=np.uint16)
    buf = cp.pack_csi2p_10bit(frame)
    stride = cp.default_stride(20)
    assert len(buf) == stride * 12
    assert np.array_equal(unpack_local(buf, 20, 12, stride), frame)
    with pytest.raises(ValueError):
        cp.pack_csi2p_10bit(np.full((2, 4), 1024, dtype=np.uint16))


def test_crop_packed_equals_cropping_the_image():
    base = cp.simulated_base_frame(384, 216)
    assert base[0, 0] == 128 and base[0, -1] == 768 and base[-1, 0] == 192
    buf = cp.pack_csi2p_10bit(base)
    out, w, h, stride = cp.crop_packed(buf, 384, 216, 480, {"x": 100, "y": 50, "w": 120, "h": 60})
    assert (w, h, stride) == (120, 60, cp.default_stride(120)) and len(out) == stride * h
    assert np.array_equal(unpack_local(out, w, h, stride), base[50:110, 100:220])
    # unaligned request snaps outward: x down to a multiple of 4, w up; y down to even, h up
    snapped = cp.snap_crop({"x": 101, "y": 51, "w": 121, "h": 61}, 384, 216)
    assert snapped == {"x": 100, "y": 50, "w": 124, "h": 62}
    out2, w2, h2, s2 = cp.crop_packed(buf, 384, 216, 480, {"x": 101, "y": 51, "w": 121, "h": 61})
    assert np.array_equal(unpack_local(out2, w2, h2, s2), base[50:112, 100:224])
    with pytest.raises(ValueError):
        cp.snap_crop({"x": 400, "y": 0, "w": 8, "h": 8}, 384, 216)


def test_high_bytes_and_motion_energy_exact():
    base = cp.simulated_base_frame(64, 32)
    a = cp.pack_csi2p_10bit(base)
    b = cp.pack_csi2p_10bit(base + 8)          # +8 DN -> high byte +2 everywhere
    ha = cp.high_bytes_subsampled(a, 64, 32, cp.default_stride(64), 4)
    hb = cp.high_bytes_subsampled(b, 64, 32, cp.default_stride(64), 4)
    assert ha.shape == (8, 16)
    assert np.array_equal(ha, (base[::4, ::4] >> 2).astype(np.int16))
    assert cp.motion_energy_dn(ha, hb) == pytest.approx(8.0)
    mask = cp.block_mask(64, 32, 4, {"x": 0, "y": 0, "w": 16, "h": 8})
    assert mask.sum() == 4 * 2
    assert cp.motion_energy_dn(ha, hb, mask) == pytest.approx(8.0)
    assert cp.motion_energy_dn(ha, ha) == 0.0


def test_bayer_pattern_and_camera_controls(ucfg):
    assert cp.bayer_pattern_from_format("SRGGB10_CSI2P") == "RGGB"
    assert cp.bayer_pattern_from_format("SBGGR10_CSI2P") == "BGGR"
    with pytest.raises(ValueError):
        cp.bayer_pattern_from_format("YUV420")
    ctl = cp.camera_controls(ucfg)
    assert ctl["ExposureTime"] == 10000 and ctl["AnalogueGain"] == 2.0 and ctl["ColourGains"] == (1.6, 1.4)
    assert ctl["AeEnable"] is False and ctl["AwbEnable"] is False and ctl["AfMode"] == 0
    assert ctl["LensPosition"] == 2.5 and ctl["FrameDurationLimits"] == (33333, 33333)
    assert "ScalerCrop" not in ctl
    assert cp.camera_controls(ucfg, {"x": 256, "y": 144, "w": 1024, "h": 576})["ScalerCrop"] == (256, 144, 1024, 576)


def test_block_helpers():
    assert cp.scale_block({"x": 8, "y": 8, "w": 32, "h": 32}, 0.25, 0.25, 384, 216) == {"x": 2, "y": 2, "w": 8, "h": 8}
    assert cp.scale_block({"x": 32, "y": 700, "w": 300, "h": 150}, 0.25, 0.25, 384, 216) == {"x": 8, "y": 174, "w": 74, "h": 38}
    assert cp.scale_block(None, 1, 1, 10, 10) is None
    crop = {"x": 64, "y": 36, "w": 256, "h": 144}
    assert cp.translate_block({"x": 100, "y": 50, "w": 20, "h": 20}, crop) == {"x": 36, "y": 14, "w": 20, "h": 20}
    assert cp.translate_block({"x": 2, "y": 2, "w": 8, "h": 8}, crop) is None
    assert cp.translate_block({"x": 2, "y": 2, "w": 8, "h": 8}, None) == {"x": 2, "y": 2, "w": 8, "h": 8}


# --------------------------------------------------------------------------- preflight gates
def test_check_clock_stepped_today_cases(tmp_path, good_log):
    assert cp.check_clock_stepped_today(tmp_path / "absent.csv", "unit_01", TODAY)["ok"] is False
    r = cp.check_clock_stepped_today(good_log, "unit_01", TODAY)
    assert r["ok"] is True and r["last"]["time_utc"] == "03:31:12"
    assert cp.check_clock_stepped_today(good_log, "pi_unit_01", TODAY)["ok"] is True
    old = cp.check_clock_stepped_today(good_log, "unit_01", "2026-10-18")
    assert old["ok"] is False and "2026-10-17" in old["reason"]
    assert cp.check_clock_stepped_today(good_log, "unit_02", TODAY)["ok"] is False
    # a later non-makestep row for the unit does not hide the makestep row
    log2 = write_clock_log(tmp_path / "log2.csv", [
        (TODAY, "03:31:12", "pi_unit_01", "0.1", "chronyd_makestep", "RB"),
        (TODAY, "09:00:00", "pi_unit_01", "0.2", "chronyd_tracking_only", "RB"),
    ])
    assert cp.check_clock_stepped_today(log2, "unit_01", TODAY)["ok"] is True
    # the LAST makestep row counts: a stale re-run after a day change refuses
    log3 = write_clock_log(tmp_path / "log3.csv", [
        (TODAY, "03:31:12", "pi_unit_01", "0.1", "chronyd_makestep", "RB"),
        ("2026-10-18", "03:31:12", "pi_unit_01", "0.1", "chronyd_makestep", "RB"),
    ])
    assert cp.check_clock_stepped_today(log3, "unit_01", TODAY)["ok"] is False


def test_check_free_space_uses_disk_usage(tmp_path):
    free = shutil.disk_usage(tmp_path).free / 1e9
    r = cp.check_free_space(tmp_path, 0.0)
    assert r["ok"] is True and abs(r["free_gb"] - free) < 0.5
    assert cp.check_free_space(tmp_path, 1e9)["ok"] is False


def test_refuses_without_clock_step_today(tmp_path, ucfg, capsys):
    cfg_path = write_ucfg(tmp_path, ucfg)
    out = tmp_path / "p" / "pi"
    stale = write_clock_log(tmp_path / "stale.csv", [("2026-10-16", "03:30:00", "pi_unit_01", "0.4", "chronyd_makestep", "RB")])
    rc = cp.main(cfg_path, "SWHT-PP-003-0001", "clip1", out, simulate=True, video_seconds=2, clock_log_path=stale,
                 today=TODAY, min_free_gb=0.1)
    assert rc == 2
    assert "clock" in capsys.readouterr().err.lower()
    assert not (out / "clip1.raw").exists()
    rc = cp.main(cfg_path, "SWHT-PP-003-0001", "clip1", out, simulate=True, video_seconds=2,
                 clock_log_path=tmp_path / "missing.csv", today=TODAY, min_free_gb=0.1)
    assert rc == 2
    assert "clock_sync.sh" in capsys.readouterr().err


def test_refuses_when_min_free_gb_is_absurd(tmp_path, ucfg, good_log, capsys):
    cfg_path = write_ucfg(tmp_path, ucfg)
    out = tmp_path / "p" / "pi"
    rc = cp.main(cfg_path, "SWHT-PP-003-0001", "clip1", out, simulate=True, video_seconds=2, clock_log_path=good_log,
                 today=TODAY, min_free_gb=1e9)
    assert rc == 2
    err = capsys.readouterr().err
    assert "GB free" in err and "min_free_gb" in err
    assert not (out / "clip1.raw").exists()


def test_cli_exit_code_for_preflight(tmp_path, ucfg, good_log):
    cfg_path = write_ucfg(tmp_path, ucfg)
    rc = cp.cli(["--config", str(cfg_path), "--study-id", "S1", "--out-dir", str(tmp_path / "pi"), "--simulate",
                 "--video-seconds", "2", "--clock-log", str(good_log), "--today", TODAY, "--min-free-gb", "1e9"])
    assert rc == 2


# --------------------------------------------------------------------------- the simulated capture flow
def test_simulate_capture_produces_consistent_files(tmp_path, ucfg, good_log):
    cfg_path = write_ucfg(tmp_path, ucfg)
    out = tmp_path / "SWHT-PP-003-0001" / "pi"
    seconds = 8.0
    rc = cp.main(cfg_path, "SWHT-PP-003-0001", "clip1", out, simulate=True, video_seconds=seconds, operator="RB",
                 dept="Cardio OPD", clock_log_path=good_log, today=TODAY, min_free_gb=0.5, recovery_gate="pass", seed=3)
    assert rc == 0
    raw, pts_path, meta_path, ev_path = out / "clip1.raw", out / "clip1_pts.csv", out / "clip1_meta.json", out / "sync_events.csv"
    for p in (raw, pts_path, meta_path, ev_path):
        assert p.exists(), p
    meta = json.loads(meta_path.read_text())
    missing = [k for k in CONTRACT_META_KEYS if k not in meta]
    assert not missing, missing
    n, stride, h, w = meta["n_frames_written"], meta["stride_bytes"], meta["height"], meta["width"]
    assert (w, h, stride) == (384, 216, 480)
    assert raw.stat().st_size == n * stride * h
    assert abs(n - seconds * 30) <= 3
    pts = read_pts(pts_path)
    assert list(pts[0].keys()) == ["frame_idx", "sensor_ts_ns", "wall_ns", "exposure_us", "analogue_gain", "digital_gain", "lux"]
    assert len(pts) == n and [int(r["frame_idx"]) for r in pts] == list(range(n))
    ts = np.array([int(r["sensor_ts_ns"]) for r in pts])
    assert np.all(np.diff(ts) > 0)
    assert abs(np.median(np.diff(ts)) / 1e6 - 1000 / 30) < 1.0
    assert meta["start_mono_ns"] == int(ts[0]) and meta["stop_mono_ns"] >= int(ts[-1])
    assert (ts[-1] - ts[0]) / 1e9 < seconds
    assert meta["stop_wall_ns"] > meta["start_wall_ns"]
    assert float(pts[0]["exposure_us"]) == 10000.0 and float(pts[0]["analogue_gain"]) == 2.0 and float(pts[0]["lux"]) == 400.0
    # meta content
    assert meta["unit_id"] == "unit_01" and meta["operator"] == "RB" and meta["dept"] == "Cardio OPD" and meta["stream"] == "pilot"
    assert meta["bayer_pattern"] == "RGGB" and meta["bit_depth"] == 10 and meta["fps_nominal"] == 30.0
    assert meta["crop_rect"] is None and meta["exposure_us"] == 10000.0 and meta["analogue_gain"] == 2.0
    assert meta["awb_gains"] == [1.6, 1.4] and meta["lens_position"] == 2.5 and meta["led_current_ma"] == 20
    assert meta["lux"] == 400.0 and meta["sensor_temp_c"] is None
    assert meta["live_sqi"] is None and meta["motion_flag"] is False and meta["recovery_gate"] == "pass"
    assert meta["video_seconds"] == seconds and meta["capture_mode"] == "simultaneous" and meta["simulated"] is True
    assert meta["led_block"] == {"x": 2, "y": 2, "w": 8, "h": 8}
    tb = meta["thumb_block"]
    assert tb["x"] + tb["w"] <= w and tb["y"] + tb["h"] <= h
    assert meta["capture_extra"]["n_frames_dropped_est"] == 0 and meta["capture_extra"]["all_gpio_ok"] is True
    # sync events: 10 rows, placed 2 s and t_end - 5 s = 3 s after the first frame
    with open(ev_path, encoding="utf-8", newline="") as fh:
        ev = list(csv.DictReader(fh))
    assert len(ev) == 10 and [r["pattern"] for r in ev] == ["P1"] * 6 + ["P2"] * 4
    assert all(r["gpio_ok"] == "True" for r in ev)
    p1_on, p2_on = int(ev[0]["mono_ns"]), int(ev[6]["mono_ns"])
    assert abs((p1_on - meta["start_mono_ns"]) / 1e9 - 2.0) < 0.005
    assert abs((p2_on - meta["start_mono_ns"]) / 1e9 - (seconds - 5.0)) < 0.005
    # frame 0 is the known gradient (LED off, thumb not yet lifted), within the simulated noise
    frame_bytes = stride * h
    with open(raw, "rb") as fh:
        f0 = unpack_local(fh.read(frame_bytes), w, h, stride)
    base = cp.simulated_base_frame(w, h).astype(int)
    d0 = f0.astype(int) - base
    assert np.abs(d0).max() <= 8 and np.abs(d0).mean() < 1.5
    # LED block follows the logged edges: frames inside a logged on-interval read 1000, outside the gradient
    lb = meta["led_block"]
    on_intervals = [(int(a["mono_ns"]), int(b["mono_ns"])) for a, b in zip(ev[::2], ev[1::2])]
    margin = 15_000_000
    n_in = n_out = 0
    with open(raw, "rb") as fh:
        for i in range(n):
            buf = fh.read(frame_bytes)
            t = int(ts[i])
            inside = any(a + margin <= t <= b - margin for a, b in on_intervals)
            near = any(abs(t - a) < margin or abs(t - b) < margin for a, b in on_intervals)
            if near:
                continue
            fr = unpack_local(buf, w, h, stride)
            led_mean = fr[lb["y"]: lb["y"] + lb["h"], lb["x"]: lb["x"] + lb["w"]].mean()
            if inside:
                assert led_mean > 995, (i, led_mean)
                n_in += 1
            else:
                assert led_mean < 200, (i, led_mean)
                n_out += 1
    assert n_in >= 5 and n_out >= 100
    # thumb block drops by the configured step once P2 has been emitted (the fine-anchor lift of section 4.3)
    p2_end = int(ev[-1]["mono_ns"])
    with open(raw, "rb") as fh:
        first = unpack_local(fh.read(frame_bytes), w, h, stride)
        fh.seek((n - 1) * frame_bytes)
        last = unpack_local(fh.read(frame_bytes), w, h, stride)
    assert int(ts[-1]) > p2_end
    thumb_before = first[tb["y"]: tb["y"] + tb["h"], tb["x"]: tb["x"] + tb["w"]].mean()
    thumb_after = last[tb["y"]: tb["y"] + tb["h"], tb["x"]: tb["x"] + tb["w"]].mean()
    assert abs((thumb_before - thumb_after) - 150.0) < 3.0
    # a second run with the same clip id refuses to overwrite a non-empty raw file
    rc2 = cp.main(cfg_path, "SWHT-PP-003-0001", "clip1", out, simulate=True, video_seconds=1, clock_log_path=good_log,
                  today=TODAY, min_free_gb=0.5)
    assert rc2 == 1
    assert raw.stat().st_size == n * stride * h


def test_simulate_capture_with_crop_and_reshoot_clip_id(tmp_path, ucfg, good_log):
    cfg_path = write_ucfg(tmp_path, ucfg, roi_crop={"x": 256, "y": 144, "w": 1024, "h": 576})
    out = tmp_path / "SWHT-PP-003-0002" / "pi"
    rc = cp.main(cfg_path, "SWHT-PP-003-0002", "clip1b", out, simulate=True, video_seconds=3.0, clock_log_path=good_log,
                 today=TODAY, min_free_gb=0.5, seed=5)
    assert rc == 0
    meta = json.loads((out / "clip1b_meta.json").read_text())
    assert (out / "sync_events_clip1b.csv").exists() and not (out / "sync_events.csv").exists()
    assert meta["crop_rect"] == {"x": 64, "y": 36, "w": 256, "h": 144}
    n, stride, h, w = meta["n_frames_written"], meta["stride_bytes"], meta["height"], meta["width"]
    assert (w, h, stride) == (256, 144, 320)
    assert (out / "clip1b.raw").stat().st_size == n * stride * h
    assert len(read_pts(out / "clip1b_pts.csv")) == n
    assert meta["led_block"] is None                # the LED corner lies outside the aperture crop
    assert meta["capture_extra"]["controls"]["ScalerCrop"] == [64, 36, 256, 144]
    with open(out / "clip1b.raw", "rb") as fh:
        f0 = unpack_local(fh.read(stride * h), w, h, stride)
    base = cp.simulated_base_frame(384, 216).astype(int)[36:180, 64:320]
    assert np.abs(f0.astype(int) - base).max() <= 8
