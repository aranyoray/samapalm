"""build_timeline on fully synthetic sets: grade fine / coarse / none, sequential mode, report and features
(protocol section 4 in full, 4.4 grading, D-002 window, D-004 grade logic)."""
import json

import numpy as np
import pandas as pd
import pytest

from palmppg.core.config import rng
from palmppg.core.timeline import COARSE_METHODS, Timeline
from palmppg.core.tracks import REGISTRY
from palmppg.ingest.bench import on_intervals, synth_audio, synth_led_trace, synth_thumb_trace
from palmppg.ingest.sync import build_timeline, register_features, sync_feature_row, write_sync_json
from palmppg.ingest.sync_events import pattern_edges, pattern_specs, read_sync_events

FPS = 30.0
T0 = 5_000_000_000_000
START_WALL = 1_760_000_000_000_000_000
DAY = {"unit_01": 120.0, "kardia_tablet": -300.0}


def _beats(duration_s, gen, hr=72.0, start=0.0):
    t, out = start, []
    while t < duration_s:
        rate = hr + 6.0 * np.sin(2 * np.pi * 0.25 * t) + 4.0 * np.sin(2 * np.pi * 0.08 * t + 1.0)
        t += 60.0 / rate + gen.normal(0, 0.01)
        out.append(t)
    return np.array(out)


def _rate_pair(beats):
    ibi = np.diff(beats)
    return 0.5 * (beats[:-1] + beats[1:]), 60.0 / ibi


def make_set(cfg, seed=41, clip_s=60.0, phone_offset=1.234, phone_drift=5e-5, ecg_offset=1.5, pat_s=0.2,
             contact_s=1.2, lift_after_p2_s=0.9):
    """Everything build_timeline needs, with the ground truth attached under 'truth'."""
    gen = rng(seed, "timeline-set")
    specs = pattern_specs(cfg)
    n = int(clip_s * FPS)
    pts = pd.DataFrame({"frame_idx": np.arange(n), "sensor_ts_ns": T0 + (np.arange(n) * 1e9 / FPS).astype(np.int64)})
    t_pi = (pts["sensor_ts_ns"].to_numpy() - T0) / 1e9
    start_mono = T0 - 10_000_000
    pi_meta = {"start_mono_ns": start_mono, "stop_mono_ns": T0 + int(clip_s * 1e9), "start_wall_ns": START_WALL,
               "fps_nominal": FPS, "exposure_us": 8000, "unit_id": "unit_01", "video_seconds": clip_s,
               "led_block": {"x": 8, "y": 8, "w": 32, "h": 32}, "thumb_block": {"x": 32, "y": 700, "w": 300, "h": 150}}
    clip_start = (start_mono - T0) / 1e9
    p1 = clip_start + cfg.get("sync.p1.at_s_after_start")
    p2 = clip_s - cfg.get("sync.p2.at_s_before_end")
    rows, eid = [], 0
    for name, onset in (("P1", p1), ("P2", p2)):
        for t, kind in pattern_edges(onset, specs[name]):
            eid += 1
            mono = T0 + round(t * 1e9)
            rows.append({"event_id": eid, "kind": kind, "pattern": name, "mono_ns": mono,
                         "wall_ns": START_WALL + (mono - start_mono), "gpio_ok": True})
    events = read_sync_events(pd.DataFrame(rows))
    intervals = on_intervals({"P1": p1, "P2": p2}, specs)
    led_pi = (np.arange(n), synth_led_trace(t_pi, intervals, 0.0, 0.0, 0.008, 90.0, 380.0, 3.0, gen))
    n_ph = n + 90
    t_ph = np.arange(n_ph) / FPS + gen.uniform(-5e-4, 5e-4, size=n_ph)
    led_ph = (np.arange(n_ph), synth_led_trace(t_ph, intervals, phone_offset, phone_drift, 0.9 / FPS, 40.0, 220.0, 2.5, gen))
    a_start = 0.0213
    fs_a = 48000.0
    ints_audio = [((a - phone_offset) / (1 + phone_drift) - a_start, (b - phone_offset) / (1 + phone_drift) - a_start)
                  for a, b in intervals]
    audio = (fs_a, synth_audio(fs_a, clip_s + 2.0, ints_audio, cfg.get("sync.audio.tone_hz"), 0.3, 0.1, 0.0, gen), a_start)
    lift = p2 + lift_after_p2_s
    thumb = (np.arange(n), synth_thumb_trace(t_pi, contact_s, lift, 0.8, 300.0, -60.0, 35.0, 3.0, gen))
    beats_ref = _beats(clip_s - 0.5, gen, start=ecg_offset + 0.3)
    ecg_t, ecg_rate = _rate_pair(beats_ref - ecg_offset)      # ECG native seconds
    ppg_t, ppg_rate = _rate_pair(beats_ref + pat_s)            # pulse feet, reference seconds
    pi_wall_at_ecg0 = START_WALL + (T0 + round(ecg_offset * 1e9) - start_mono)
    kardia_wall = pi_wall_at_ecg0 - round(DAY["unit_01"] * 1e6) + round(DAY["kardia_tablet"] * 1e6)
    iso = np.datetime64(kardia_wall, "ns").astype("datetime64[us]").item().isoformat() + "+00:00"
    ecg = {"artefact_t_ecg_s": lift - ecg_offset, "rate_series": (ecg_t, ecg_rate),
           "kardia_meta": {"start_wall_ts": iso, "duration_s": 60.0, "fs": 300}, "day_offsets": DAY}
    return {"pi_meta": pi_meta, "pts": pts, "events": events, "led_pi": led_pi, "led_phone": led_ph, "phone_pts": t_ph,
            "audio": audio, "thumb": thumb, "ecg": ecg, "ppg": (ppg_t, ppg_rate),
            "truth": {"phone_offset": phone_offset, "phone_drift": phone_drift, "ecg_offset": ecg_offset, "p1": p1, "p2": p2,
                      "lift": lift, "contact": contact_s, "clip_start": clip_start, "pat_s": pat_s, "a_start": a_start}}


def test_fully_consistent_set_grades_fine(cfg, tmp_path):
    s = make_set(cfg)
    tr = s["truth"]
    phone_meta = {"exposure_ns": round(0.9 / FPS * 1e9), "fps_nominal": FPS, "capture_mode": "simultaneous"}
    tl, rep = build_timeline("SWHT-PP-003-0001", "clip1", s["pi_meta"], s["pts"], s["events"], s["led_pi"], s["led_phone"],
                             s["phone_pts"], s["audio"], s["thumb"], s["ecg"], s["ppg"], cfg, "simultaneous", phone_meta=phone_meta)
    assert isinstance(tl, Timeline) and tl.t0_ref_ns == T0
    assert rep["grade"] == "fine" and tl.sync_grade == "fine" and tl.beat_level_ecg_allowed
    assert rep["flags"] == []
    # maps
    assert tl.maps["pi_frames"].method == "identity"
    pv = tl.maps["phone_video"]
    assert pv.method == "led_pattern" and abs(pv.offset_s - tr["phone_offset"]) < 0.006 and abs(pv.drift - tr["phone_drift"]) < 2e-4
    assert rep["phone"]["video"]["fit"]["accepted"] and rep["phone"]["frame_pairing_allowed"]
    pa = tl.maps["phone_audio"]
    assert pa.method == "audio_beep" and abs(pa.offset_s - tr["phone_offset"]) < 0.002
    assert rep["residuals"]["phone_audio_max_ms"] < cfg.get("sync.audio.onset_tolerance_ms")
    assert rep["residuals"]["pi_video_max_frames"] < 1.0 and rep["pi_video"]["fit"]["accepted"]
    e = tl.maps["ecg"]
    assert e.method == "artefact_lift" and abs(e.offset_s - tr["ecg_offset"]) <= 0.5 / FPS + 1e-9
    assert e.uncertainty_s == cfg.get("sync.fine_anchor_uncertainty_s")
    assert abs(rep["ecg"]["wall_clock"]["offset_s"] - tr["ecg_offset"]) < 1e-6
    assert tl.maps["wall"].method == "wall_clock" and not tl.maps["wall"].is_fine_capable
    assert tl.maps["wall"].to_ref(START_WALL / 1e9) == pytest.approx(tr["clip_start"], abs=1e-6)
    assert rep["ecg"]["anchor_comparison"]["disagreement_s"] < 1.0 and not rep["ecg"]["anchor_comparison"]["flag"]
    # events
    assert abs(tl.event("p1_onset").t_ref_s - tr["p1"]) < 0.002       # the log entry (lowest uncertainty)
    assert abs(tl.event("p2_onset").t_ref_s - tr["p2"]) < 0.002
    assert abs(tl.event("thumb_contact").t_ref_s - tr["contact"]) <= 1 / FPS + 1e-9
    assert abs(tl.event("thumb_lift").t_ref_s - tr["lift"]) <= 0.5 / FPS + 1e-9
    assert abs(tl.event("ecg_artefact").t_ref_s - tl.event("thumb_lift").t_ref_s) < 1e-9
    assert tl.event("clip_start").t_ref_s == pytest.approx(tr["clip_start"]) and tl.event("clip_end").t_ref_s == 60.0
    # window (D-002): starts static_colour_s after clip start, ends at the P2 onset
    w = tl.analysis_window
    assert w.start_s == pytest.approx(tr["clip_start"] + cfg.get("window.static_colour_s"))
    assert abs(w.end_s - tr["p2"]) < 0.002
    assert not tl.valid_mask(np.array([tr["p2"] + 0.5]))[0] and tl.valid_mask(np.array([30.0]))[0]
    # xcorr lag is the pulse arrival time, inside agree_s
    xc = rep["ecg"]["xcorr"]
    assert xc["accepted"] and abs(xc["lag_s"] - tr["pat_s"]) < 0.15 and rep["grade_detail"]["xcorr_agree"]
    assert rep["ecg"]["coverage_ref_s"][0] == pytest.approx(e.offset_s) and rep["ecg"]["coverage_ref_s"][1] == pytest.approx(e.offset_s + 60.0)
    # report is json-serialisable and round-trips; the timeline saves and loads
    p = write_sync_json(rep, tmp_path / "sync.json")
    back = json.loads(p.read_text())
    assert back["grade"] == "fine" and back["offsets"]["ecg"]["method"] == "artefact_lift"
    tl.save(tmp_path / "timeline.json")
    assert Timeline.load(tmp_path / "timeline.json").sync_grade == "fine"
    row = sync_feature_row(rep)
    assert row["sync__grade"] == "fine" and row["sync__phone_video_accepted"] and row["sync__xcorr_accepted"]
    assert all(k in REGISTRY for k in row)
    assert REGISTRY.get("sync__ecg_offset_s").requires_ecg and not REGISTRY.get("sync__p1_found").requires_ecg
    assert register_features() == register_features()  # idempotent


def test_missing_artefact_grades_coarse(cfg):
    s = make_set(cfg, seed=42)
    s["ecg"]["artefact_t_ecg_s"] = None
    tl, rep = build_timeline("x", "clip1", s["pi_meta"], s["pts"], s["events"], s["led_pi"], s["led_phone"], s["phone_pts"],
                             None, s["thumb"], s["ecg"], s["ppg"], cfg, "simultaneous")
    assert rep["grade"] == "coarse" and not tl.beat_level_ecg_allowed
    assert "ecg_artefact_missing" in rep["flags"]
    # without phone meta no exposure-centre correction is applied: the LED fit is biased by half the exposure
    assert abs(tl.maps["phone_video"].offset_s - s["truth"]["phone_offset"]) < 0.5 / FPS
    assert tl.maps["ecg"].method in COARSE_METHODS
    assert tl.event("ecg_artefact") is None and tl.event("thumb_contact") is not None
    # the coarse anchor (thumb contact 1.2 s) is within its stated 1 s of the true ECG offset (1.5 s)
    assert abs(tl.maps["ecg"].offset_s - s["truth"]["ecg_offset"]) < cfg.get("sync.coarse_anchor_uncertainty_s")
    assert rep["grade_detail"]["fine_anchor_found"] is False and rep["grade_detail"]["p1_found"] and rep["grade_detail"]["p2_found"]
    # fine anchor but no xcorr (no rate series) also cannot be fine
    s2 = make_set(cfg, seed=43)
    tl2, rep2 = build_timeline("x", "clip1", s2["pi_meta"], s2["pts"], s2["events"], s2["led_pi"], None, None, None,
                               s2["thumb"], s2["ecg"], None, cfg, "simultaneous")
    assert rep2["grade"] == "coarse" and tl2.maps["ecg"].method == "artefact_lift" and rep2["grade_detail"]["xcorr_agree"] is None


def test_wall_clock_only_is_coarse_and_disagreement_flagged(cfg):
    s = make_set(cfg, seed=44)
    s["ecg"]["artefact_t_ecg_s"] = None
    flat = (s["thumb"][0], 300.0 + rng(44, "flat").normal(0, 3.0, size=s["thumb"][0].size))  # no thumb step
    tl, rep = build_timeline("x", "clip1", s["pi_meta"], s["pts"], s["events"], s["led_pi"], None, None, None, flat,
                             s["ecg"], None, cfg, "simultaneous")
    assert rep["grade"] == "coarse" and tl.maps["ecg"].method == "wall_clock"
    assert "thumb_contact_not_found" in rep["flags"] and "ecg_map_from_wall_clock_only" in rep["flags"]
    # data-entry error: Kardia start 10 s off -> disagreement with the thumb anchor is flagged
    s3 = make_set(cfg, seed=45)
    meta = s3["ecg"]["kardia_meta"]
    bad = np.datetime64(meta["start_wall_ts"].replace("+00:00", "")) + np.timedelta64(10, "s")
    meta["start_wall_ts"] = str(bad) + "+00:00"
    tl3, rep3 = build_timeline("x", "clip1", s3["pi_meta"], s3["pts"], s3["events"], s3["led_pi"], None, None, None,
                               s3["thumb"], s3["ecg"], s3["ppg"], cfg, "simultaneous")
    assert rep3["ecg"]["anchor_comparison"]["flag"] and "wall_vs_thumb_disagreement" in rep3["flags"]
    assert rep3["ecg"]["anchor_comparison"]["disagreement_s"] == pytest.approx(10.3, abs=0.05)
    assert tl3.maps["ecg"].method == "artefact_lift"  # the thumb anchors still win; the wall clock is audit only


def test_nothing_anchors_grades_none(cfg):
    s = make_set(cfg, seed=46)
    tl, rep = build_timeline("x", "clip1", s["pi_meta"], s["pts"], s["events"], s["led_pi"], None, None, None, None,
                             {}, None, cfg, "simultaneous")
    assert rep["grade"] == "none" and "ecg" not in tl.maps and "no_ecg_anchor" in rep["flags"]
    assert rep["grade_detail"]["coarse_anchor_found"] is False
    assert tl.analysis_window is not None and abs(tl.analysis_window.end_s - s["truth"]["p2"]) < 0.002
    # no log and no LED trace at all: window falls back to clip_end - tail, patterns not found
    tl2, rep2 = build_timeline("x", "clip1", s["pi_meta"], s["pts"], None, None, None, None, None, None, {}, None, cfg)
    assert rep2["grade"] == "none" and "sync_log_missing" in rep2["flags"] and "pi_led_trace_missing" in rep2["flags"]
    assert tl2.analysis_window.end_s == pytest.approx(60.0 - cfg.get("window.tail_exclusion_s"))
    assert tl2.event("p1_onset") is None


def test_sequential_mode_phone_map_from_beep_only(cfg):
    s = make_set(cfg, seed=47)
    specs = pattern_specs(cfg)
    gen = rng(47, "seq")
    # phone scan 2 min after the box clip: its own marker log has a P1 at t_ref = 120.0
    scan_p1_ref = 120.0
    rows = [{"event_id": i + 1, "kind": k, "pattern": "P1", "mono_ns": T0 + round(t * 1e9),
             "wall_ns": START_WALL + round(t * 1e9), "gpio_ok": True} for i, (t, k) in enumerate(pattern_edges(scan_p1_ref, specs["P1"]))]
    phone_log = read_sync_events(pd.DataFrame(rows))
    beep_video_t, a_start = 3.0, 0.02
    true_offset = scan_p1_ref - beep_video_t
    audio = (48000.0, synth_audio(48000.0, 8.0, on_intervals({"P1": beep_video_t - a_start}, specs), cfg.get("sync.audio.tone_hz"),
                                  0.3, 0.1, 0.0, gen), a_start)
    wall_minus_mono = s["pi_meta"]["start_wall_ns"] - s["pi_meta"]["start_mono_ns"]
    phone_meta = {"start_wall_ns": T0 + round(true_offset * 1e9) + wall_minus_mono - round(DAY["unit_01"] * 1e6) + 250_000_000,
                  "fps_nominal": 30, "capture_mode": "sequential"}
    tl, rep = build_timeline("x", "clip1", s["pi_meta"], s["pts"], s["events"], s["led_pi"], s["led_phone"], s["phone_pts"],
                             audio, s["thumb"], s["ecg"], s["ppg"], cfg, "sequential", phone_meta=phone_meta,
                             phone_sync_events_df=phone_log)
    assert tl.capture_mode == "sequential"
    pv = tl.maps["phone_video"]
    assert pv.method == "audio_beep" and pv.drift == 0.0
    assert abs(pv.offset_s - true_offset) < 0.002
    assert pv.uncertainty_s == pytest.approx(cfg.get("sync.audio.onset_tolerance_ms") / 1e3)
    assert tl.maps["phone_audio"].offset_s == pv.offset_s
    assert rep["phone"]["frame_pairing_allowed"] is False and rep["phone"]["video"]["present"] is False
    assert rep["phone"]["beep_vs_wall_disagreement_s"] == pytest.approx(0.25, abs=0.003)
    assert abs(rep["phone"]["wall_clock"]["offset_s"] - (true_offset + 0.25)) < 1e-6
    # the ECG side is unaffected by the phone mode
    assert rep["grade"] == "fine"
    # no beep: wall clock only, flagged
    tl2, rep2 = build_timeline("x", "clip1", s["pi_meta"], s["pts"], s["events"], s["led_pi"], None, None, None, s["thumb"],
                               s["ecg"], s["ppg"], cfg, "sequential", phone_meta=phone_meta, phone_sync_events_df=phone_log)
    assert tl2.maps["phone_video"].method == "wall_clock" and "phone_start_beep_not_detected" in rep2["flags"]
    tl3, rep3 = build_timeline("x", "clip1", s["pi_meta"], s["pts"], s["events"], s["led_pi"], None, None, None, s["thumb"],
                               s["ecg"], s["ppg"], cfg, "sequential")
    assert "phone_video" not in tl3.maps and "phone_unanchored" in rep3["flags"]


def test_phone_audio_stands_in_when_phone_led_unusable(cfg):
    s = make_set(cfg, seed=48)
    tl, rep = build_timeline("x", "clip1", s["pi_meta"], s["pts"], s["events"], s["led_pi"], None, None, s["audio"], s["thumb"],
                             s["ecg"], s["ppg"], cfg, "simultaneous")
    pv = tl.maps["phone_video"]
    assert pv.method == "audio_beep" and abs(pv.offset_s - s["truth"]["phone_offset"]) < 0.002
    assert rep["phone"]["frame_pairing_allowed"] and rep["phone"]["video"] == {"present": False}
    assert rep["grade"] == "fine"
