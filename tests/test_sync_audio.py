"""Buzzer beep detection on synthetic 48 kHz audio: sub-millisecond onsets, absent patterns (section 4.2)."""
import numpy as np
import pytest

from palmppg.core.config import rng
from palmppg.ingest.audio import (
    audio_to_video_time,
    beep_edges,
    beep_precision_s,
    detect_beeps,
    tone_envelope,
)
from palmppg.ingest.bench import on_intervals, synth_audio
from palmppg.ingest.led import fit_led_offset
from palmppg.ingest.sync_events import pattern_edges, pattern_specs

FS = 48000.0


def test_beep_onsets_within_1ms_with_noise(cfg):
    specs = pattern_specs(cfg)
    tone = cfg.get("sync.audio.tone_hz")
    bw = cfg.get("sync.audio.bandwidth_hz")
    p1, p2 = 2.000437, 6.1234
    x = synth_audio(FS, 9.0, on_intervals({"P1": p1, "P2": p2}, specs), tone, 0.3, 0.1, 0.0, rng(11, "audio"))
    res = detect_beeps(x, FS, tone, bw, specs)
    assert res["P1"] is not None and res["P2"] is not None
    assert abs(res["P1"]["onset_s"] - p1) < 0.001
    assert abs(res["P2"]["onset_s"] - p2) < 0.001
    for name, onset in (("P1", p1), ("P2", p2)):
        ideal = pattern_edges(onset, specs[name])
        assert len(res[name]["edges"]) == len(ideal)
        for e, (ti, ki) in zip(res[name]["edges"], ideal):
            assert e["kind"] == ki and abs(e["t_s"] - ti) < 0.001
    assert res["P1"]["snr_db"] > 20


def test_beep_detection_with_audio_start_offset_and_fit(cfg):
    """Audio PTS origin differs from video: edges come back in video time and fit the log offset."""
    specs = pattern_specs(cfg)
    tone, bw = cfg.get("sync.audio.tone_hz"), cfg.get("sync.audio.bandwidth_hz")
    a_start, video_offset = 0.0213, 0.75  # t_video = t_audio + a_start; t_ref = t_video + video_offset
    ideal = {k: pattern_edges(t, specs[k]) for k, t in (("P1", 2.0), ("P2", 7.0))}
    ints_audio = [(a - video_offset - a_start, b - video_offset - a_start) for a, b in on_intervals({"P1": 2.0, "P2": 7.0}, specs)]
    x = synth_audio(FS, 9.0, ints_audio, tone, 0.2, 0.1, 0.0, rng(12, "audio"))
    res = detect_beeps(x, FS, tone, bw, specs, audio_start_offset_s=a_start)
    assert res["P1"]["onset_audio_s"] + a_start == pytest.approx(res["P1"]["onset_s"])
    assert abs(res["P1"]["onset_s"] - (2.0 - video_offset)) < 0.001
    cm, rep = fit_led_offset(beep_edges(res), ideal, "phone_audio", 30.0, 1.0, 6)
    assert cm.method == "audio_beep" and rep["accepted"] and rep["n_matched"] == 10
    assert abs(cm.offset_s - video_offset) < 0.001
    assert rep["residual_max_s"] < 0.001
    assert audio_to_video_time([1.0, 2.0], a_start).tolist() == pytest.approx([1.0213, 2.0213])


def test_absent_pattern_returns_none_and_silence_detects_nothing(cfg):
    specs = pattern_specs(cfg)
    tone, bw = cfg.get("sync.audio.tone_hz"), cfg.get("sync.audio.bandwidth_hz")
    gen = rng(13, "absent")
    x = synth_audio(FS, 6.0, on_intervals({"P1": 1.5}, specs), tone, 0.3, 0.1, 0.0, gen)
    res = detect_beeps(x, FS, tone, bw, specs)
    assert res["P1"] is not None and res["P2"] is None
    silence = gen.normal(0, 0.1, size=int(4 * FS))
    res2 = detect_beeps(silence, FS, tone, bw, specs)
    assert res2 == {"P1": None, "P2": None}
    # a tone at the wrong frequency (outside the band) is not a beep
    t = np.arange(int(5 * FS)) / FS
    other = 0.3 * np.sin(2 * np.pi * 800 * t) * ((t > 1) & (t < 1.1)) + gen.normal(0, 0.05, size=t.size)
    assert detect_beeps(other, FS, tone, bw, specs) == {"P1": None, "P2": None}


def test_tone_envelope_is_symmetric_about_onset(cfg):
    tone, bw = cfg.get("sync.audio.tone_hz"), cfg.get("sync.audio.bandwidth_hz")
    t = np.arange(int(1.0 * FS)) / FS
    x = 0.5 * np.sin(2 * np.pi * tone * t) * (t >= 0.5)
    env = tone_envelope(x, FS, tone, bw)
    i = int(np.argmin(np.abs(env - 0.25)))  # half of the steady amplitude
    assert abs(t[i] - 0.5) < 0.0005
    assert beep_precision_s(cfg.get("sync.audio.onset_tolerance_ms"), bw) == pytest.approx(0.02)
