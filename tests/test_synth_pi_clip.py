"""Pi clip writer: byte-exact packed raw, pts csv, meta, sync_events, LED and thumb blocks (palmppg.synth.bayer_video)."""
import csv
import json
import math

import numpy as np
import pytest

from palmppg.core.config import rng
from palmppg.synth import bayer_video as bv
from palmppg.synth import palm_scene as ps
from palmppg.synth.pulse_wave import generate_pulse

META_KEYS = ("unit_id operator dept stream app_ver study_id clip_id width height stride_bytes bayer_pattern bit_depth fps_nominal "
             "crop_rect exposure_us analogue_gain digital_gain awb_gains lens_position led_current_ma lux sensor_temp_c start_wall_ns "
             "stop_wall_ns start_mono_ns stop_mono_ns live_sqi motion_flag recovery_gate video_seconds capture_mode n_frames_written "
             "led_block thumb_block").split()
W, H, FPS, SECONDS, HR = 192, 108, 30.0, 12.0, 72.0

def _cfg():
    from palmppg.core.config import load_pipeline_config

    return load_pipeline_config()



def local_unpack(buf: bytes, width: int, height: int) -> np.ndarray:
    """Independent 10-bit CSI2P unpacker (CONTRACTS 3.1): 4 px in 5 bytes, stride ceil(w*10/8) up to 32."""
    stride = int(math.ceil(math.ceil(width * 10 / 8) / 32) * 32)
    rows = np.frombuffer(buf, np.uint8, stride * height).reshape(height, stride)[:, : width * 5 // 4]
    g = rows.reshape(height, width // 4, 5).astype(np.uint16)
    out = np.empty((height, width // 4, 4), np.uint16)
    for i in range(4):
        out[:, :, i] = (g[:, :, i] << 2) | ((g[:, :, 4] >> (2 * i)) & 3)
    return out.reshape(height, width)


@pytest.fixture(scope="module")
def clip(tmp_path_factory):
    cfg = _cfg()
    out = tmp_path_factory.mktemp("pi")
    scene = ps.make_palm_scene(W, H, cfg, rng(1, "scene"))
    pt = generate_pulse(SECONDS + 4, HR, rng(1, "pulse"), hrv_sd_s=0.0, resp_amp=0.0, t_start=-2.0)
    truth = bv.write_pi_clip(out, "clip1", scene, {"ac_dc_g": 0.006, "ac_ratios": {"R": 0.5, "G": 1.0, "B": 0.6}, "pulse_truth": pt},
                             FPS, SECONDS, options={"drops_pct": 2.0}, rng=rng(1, "w"), cfg=cfg,
                             meta_extra={"study_id": "SWHT-PP-003-0001"})
    meta = json.loads((out / "clip1_meta.json").read_text())
    stride = int(math.ceil(math.ceil(W * 10 / 8) / 32) * 32)
    raw = (out / "clip1.raw").read_bytes()
    frames = [local_unpack(raw[i * stride * H:(i + 1) * stride * H], W, H) for i in range(len(raw) // (stride * H))]
    with open(out / "clip1_pts.csv") as fh:
        pts = list(csv.DictReader(fh))
    masks = np.load(out / "clip1_roi_masks.npz")
    return {"dir": out, "scene": scene, "truth": truth, "meta": meta, "frames": frames, "pts": pts, "masks": masks, "stride": stride}


def test_packing_roundtrip_and_full_res_stride():
    r = rng(3, "pack")
    for w, h, stride in ((192, 108, 256), (1536, 864, 1920), (384, 216, 480)):
        assert bv.stride_bytes_for(w) == stride
        frame = r.integers(0, 1024, size=(h, w), dtype=np.uint16)
        buf = bv.pack_csi2p(frame)
        assert len(buf) == stride * h
        assert np.array_equal(local_unpack(buf, w, h), frame)
        assert np.array_equal(bv.unpack_csi2p(buf, w, h), frame)


def test_raw_pts_and_dropped_rows(clip):
    truth, meta, pts, frames = clip["truth"], clip["meta"], clip["pts"], clip["frames"]
    assert list(pts[0].keys()) == ["frame_idx", "sensor_ts_ns", "wall_ns", "exposure_us", "analogue_gain", "digital_gain", "lux"]
    assert len(frames) == len(pts) == meta["n_frames_written"] == truth["n_frames_written"]
    assert meta["stride_bytes"] == clip["stride"] and meta["width"] == W and meta["height"] == H
    idx = np.array([int(r["frame_idx"]) for r in pts])
    missing = sorted(set(range(int(SECONDS * FPS))) - set(idx.tolist()))
    assert missing == truth["dropped_frame_idx"] and len(missing) == round(0.02 * SECONDS * FPS)
    ts = np.array([int(r["sensor_ts_ns"]) for r in pts], dtype=np.int64)
    rel = (ts - meta["start_mono_ns"]) / 1e9
    assert rel[0] == 0.0
    assert np.allclose(rel, truth["frame_t_ref_s"], atol=2e-9)
    gaps = np.diff(rel) - np.diff(idx) / FPS
    assert np.abs(gaps).max() < 2e-4                                   # jitter below 0.2 ms
    assert np.abs(np.diff(rel)[np.diff(idx) == 1] - 1 / FPS).max() < 2e-4
    assert np.max([int(r["exposure_us"]) for r in pts]) == meta["exposure_us"]
    for k in META_KEYS:
        assert k in meta, k
    assert meta["crop_rect"] is None and meta["bayer_pattern"] == "RGGB" and meta["bit_depth"] == 10


def test_thenar_green_shows_injected_ac(clip, cfg):
    truth, frames, masks = clip["truth"], clip["frames"], clip["masks"]
    g1 = masks["thenar"][0::2, 1::2]
    trace = np.array([f[0::2, 1::2][g1].mean() for f in frames]) - cfg.get("pi.black_level")
    t = np.array(truth["frame_t_ref_s"])
    w = np.array(truth["waveform_at_frames"])
    sel = (t >= cfg.get("window.static_colour_s")) & (t < truth["p2_onset_t_ref_s"])
    coef = np.linalg.lstsq(np.c_[np.ones(sel.sum()), w[sel]], trace[sel], rcond=None)[0]
    ac_dc = -coef[1] / coef[0]
    assert abs(ac_dc - 0.006) / 0.006 < 0.10
    x = trace[sel] - trace[sel].mean()
    f = np.arange(0.5, 4.0, 0.005)
    power = np.abs(np.exp(-2j * np.pi * np.outer(f, t[sel])) @ x) ** 2
    assert abs(f[np.argmax(power)] - HR / 60.0) < 0.02                 # 1.2 Hz line


def test_sync_events_rows_and_spacing(clip, cfg):
    with open(clip["dir"] / "sync_events.csv") as fh:
        rows = list(csv.DictReader(fh))
    assert list(rows[0].keys()) == ["event_id", "kind", "pattern", "mono_ns", "wall_ns", "gpio_ok"]
    assert len(rows) == 10 and all(r["gpio_ok"] == "True" for r in rows)
    assert [r["pattern"] for r in rows] == ["P1"] * 6 + ["P2"] * 4
    assert [r["kind"] for r in rows] == ["start", "end"] * 5
    t0 = clip["meta"]["start_mono_ns"]
    t = np.array([(int(r["mono_ns"]) - t0) / 1e9 for r in rows])
    p1, p2 = cfg.section("sync.p1"), cfg.section("sync.p2")
    exp = []
    s = p1["at_s_after_start"]
    for _ in range(p1["pulses"]):
        exp += [s, s + p1["on_ms"] / 1000]
        s += (p1["on_ms"] + p1["off_ms"]) / 1000
    s = SECONDS - p2["at_s_before_end"]
    for _ in range(p2["pulses"]):
        exp += [s, s + p2["on_ms"] / 1000]
        s += (p2["on_ms"] + p2["off_ms"]) / 1000
    assert np.all(t - np.array(exp) >= 0) and np.all(t - np.array(exp) < 5e-4)   # logged just after the optical edge
    wall = np.array([int(r["wall_ns"]) for r in rows]) - clip["meta"]["start_wall_ns"]
    assert np.allclose(wall / 1e9, t, atol=1e-6)


def test_led_block_bright_exactly_during_pulses(clip):
    truth, meta, frames = clip["truth"], clip["meta"], clip["frames"]
    b = meta["led_block"]
    ys, xs = slice(b["y"], b["y"] + b["h"]), slice(b["x"], b["x"] + b["w"])
    t = np.array(truth["frame_t_ref_s"])
    exp = truth["exposure_s"]
    on = np.zeros(t.size, bool)
    off = np.ones(t.size, bool)
    for p in truth["led_schedule"]:
        on |= (t >= p["on_s"]) & (t + exp <= p["off_s"])
        off &= (t + exp <= p["on_s"]) | (t >= p["off_s"])
    assert on.sum() >= 20 and off.sum() > 300
    planes = {"R": (0, 0), "G1": (0, 1), "G2": (1, 0), "B": (1, 1)}
    for name, (r, c) in planes.items():
        block = np.array([f[ys, xs][r::2, c::2].mean() for f in frames])
        assert block[on].min() > 700, name
        assert block[off].max() < 200, name


def test_thumb_block_changes_at_contact_and_lift(clip):
    truth, meta, frames = clip["truth"], clip["meta"], clip["frames"]
    b = meta["thumb_block"]
    ys, xs = slice(b["y"], b["y"] + b["h"]), slice(b["x"], b["x"] + b["w"])
    t = np.array(truth["frame_t_ref_s"])
    g = np.array([f[ys, xs][0::2, 1::2].mean() for f in frames])
    lift, down, contact = truth["thumb_lift_t_ref_s"], truth["thumb_down_t_ref_s"], truth["thumb_contact_t_ref_s"]
    during = g[(t >= lift) & (t < down)].mean()
    before = g[(t >= lift - 1.0) & (t < lift)].mean()
    after = g[(t >= down) & (t < down + 1.0)].mean()
    assert abs(during - before) / before > 0.03 and abs(during - after) / after > 0.03
    assert abs(g[t < contact].mean() - during) / during < 0.01       # thumb absent before contact looks like the lift
    assert lift > truth["p2_onset_t_ref_s"] and down - lift == pytest.approx(0.5)


def test_landmarks_and_masks_files(clip):
    rec = json.loads((clip["dir"] / "clip1_landmarks.json").read_text())
    assert rec["is_left"] and rec["palmar"] and rec["image_size"] == [W // 2, H // 2]
    assert "lm20_z" in rec and len(rec["landmarks"]) == 21
    assert {"thenar", "thumb", "whole_palm", "skin", "ac_map", "thumb_up__skin"} <= set(clip["masks"].files)
    assert clip["truth"]["hr_bpm"] == pytest.approx(HR) and len(clip["truth"]["led_edges"]) == 10
