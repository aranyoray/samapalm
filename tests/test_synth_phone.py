"""Phone proxy clip: frame count, VFR pts, audio beeps, LED block, meta (palmppg.synth.phone_video)."""
import csv
import json
import subprocess

import numpy as np
import pytest

from palmppg.core.config import rng
from palmppg.synth import palm_scene as ps
from palmppg.synth import phone_video as pv
from palmppg.synth.pulse_wave import generate_pulse

SIZE, FPS, SECONDS = (320, 180), 30.0, 12.0
META_KEYS = ("app device_model os_build resolution fps_nominal bitrate_mbps iso exposure_ns wb_locked focus_locked stabilisation hdr "
             "torch capture_mode start_wall_ns led_block study_id clip_id").split()

def _cfg():
    from palmppg.core.config import load_pipeline_config

    return load_pipeline_config()



@pytest.fixture(scope="module")
def clip(tmp_path_factory):
    cfg = _cfg()
    out = tmp_path_factory.mktemp("phone")
    scene = ps.make_palm_scene(192, 108, cfg, rng(1, "scene"))
    pt = generate_pulse(SECONDS + 5, 72.0, rng(1, "pulse"), hrv_sd_s=0.0, resp_amp=0.0, t_start=-2.5)
    truth = pv.write_phone_clip(out, "clip1", scene, {"ac_dc_g": 0.006, "ac_ratios": {"R": 0.5, "G": 1.0, "B": 0.6}, "pulse_truth": pt},
                                FPS, SECONDS, offset_s=-1.5, drift=4e-5, size=SIZE, crf=23, rng=rng(1, "ph"), cfg=cfg,
                                options={"vfr_jitter_ms": 1.0, "custom_recorder": True}, meta_extra={"study_id": "SWHT-PP-003-0001"})
    return {"dir": out, "truth": truth, "mp4": out / "clip1.mp4", "meta": json.loads((out / "clip1_meta.json").read_text())}


def ffprobe(path, *args):
    out = subprocess.run(["ffprobe", "-v", "error", *args, "-of", "json", str(path)], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def test_streams_and_frame_count(clip):
    streams = ffprobe(clip["mp4"], "-show_streams")["streams"]
    v = [s for s in streams if s["codec_type"] == "video"][0]
    a = [s for s in streams if s["codec_type"] == "audio"][0]
    assert v["codec_name"] == "h264" and v["pix_fmt"] == "yuv420p" and [v["width"], v["height"]] == list(SIZE)
    assert a["codec_name"] == "aac" and int(a["sample_rate"]) == 48000 and int(a["channels"]) == 1
    frames = ffprobe(clip["mp4"], "-select_streams", "v:0", "-show_frames", "-show_entries", "frame=pts_time")["frames"]
    assert len(frames) == clip["truth"]["n_frames"] == round((1.5 + SECONDS + 1.0) * FPS)
    pts = np.array([float(f["pts_time"]) for f in frames])
    assert np.max(np.abs(pts - np.array(clip["truth"]["pts_s"]))) < 1e-3     # VFR pts survive the container
    d = np.diff(pts)
    assert d.min() > 0 and np.std(d) > 5e-4                               # truly variable frame rate


def test_audio_beeps_at_led_times(clip, cfg):
    from scipy.signal import butter, hilbert, sosfiltfilt

    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(clip["mp4"]), "-f", "s16le", "-ac", "1", "-ar", "48000", "pipe:1"],
                         capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.int16).astype(float) / 32768.0
    f0, bw = cfg.get("sync.audio.tone_hz"), cfg.get("sync.audio.bandwidth_hz")
    sos = butter(4, [f0 - bw / 2, f0 + bw / 2], btype="band", fs=48000, output="sos")
    env = np.abs(hilbert(sosfiltfilt(sos, x)))
    on = env > 0.3 * env.max()
    onsets = np.where(np.diff(on.astype(int)) == 1)[0] / 48000.0
    truth = np.array([b[0] for b in clip["truth"]["beep_intervals_pts_s"]])
    assert len(onsets) == 5 and len(truth) == 5
    assert np.max(np.abs(onsets - truth)) * 1000 < cfg.get("sync.audio.onset_tolerance_ms")
    durations = np.where(np.diff(on.astype(int)) == -1)[0] / 48000.0 - onsets
    assert np.allclose(durations[:3], 0.1, atol=0.01) and np.allclose(durations[3:], 0.3, atol=0.01)


def test_led_block_bright_during_pulses_in_decoded_frames(clip):
    import av

    truth = clip["truth"]
    b = truth["led_block"]
    t_ref = np.array(truth["t_ref_s"])
    exp = truth["exposure_s"]
    on = np.zeros(t_ref.size, bool)
    off = np.ones(t_ref.size, bool)
    for p in truth["led_schedule_ref_s"]:
        on |= (t_ref >= p["on_s"]) & (t_ref + exp <= p["off_s"])
        off &= (t_ref + exp <= p["on_s"]) | (t_ref >= p["off_s"])
    means = []
    with av.open(str(clip["mp4"])) as c:
        for k, fr in enumerate(c.decode(video=0)):
            img = fr.to_ndarray(format="rgb24")
            means.append(img[b["y"]:b["y"] + b["h"], b["x"]:b["x"] + b["w"]].mean())
    means = np.array(means)
    assert means.size == t_ref.size
    assert means[on].min() > 150 and means[off].max() < 100
    assert on.sum() >= 10


def test_meta_frames_csv_and_clock_map(clip):
    meta, truth = clip["meta"], clip["truth"]
    for k in META_KEYS:
        assert k in meta, k
    assert meta["stabilisation"] is False and meta["hdr"] is False and meta["wb_locked"] is True
    assert meta["torch"] in ("on", "off") and meta["resolution"] == list(SIZE) and meta["app"] == "custom_camera2"
    with open(clip["dir"] / "clip1_frames.csv") as fh:
        rows = list(csv.DictReader(fh))
    assert list(rows[0].keys()) == ["frame_idx", "sensor_ts_ns", "wall_ns", "iso", "exposure_ns"] and len(rows) == truth["n_frames"]
    pts = np.array(truth["pts_s"])
    assert np.allclose(np.array(truth["t_ref_s"]), pts * (1 + truth["clock_map"]["drift"]) + truth["clock_map"]["offset_s"])
    assert truth["clock_map"]["offset_s"] == -1.5 and truth["thumb_lift_pts_s"] > truth["thumb_contact_pts_s"]
