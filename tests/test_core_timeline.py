import numpy as np
import pytest

from palmppg.core.timeline import ClockMap, Timeline, detect_drops, resample_to_grid, uniform_grid


def test_clockmap_fit_recovers_offset_and_drift():
    native = np.array([0.0, 10.0, 20.0, 55.0])
    ref = native * 1.0001 + 3.25
    m = ClockMap.fit(native, ref, "phone_video", "led_pattern")
    assert abs(m.offset_s - 3.25) < 1e-9
    assert abs(m.drift - 1e-4) < 1e-9
    assert m.residual_max_s < 1e-9
    assert np.allclose(m.from_ref(m.to_ref(native)), native)


def test_single_anchor_gives_offset_only():
    m = ClockMap.fit([5.0], [7.0], "ecg", "thumb_contact", uncertainty_s=1.0)
    assert m.offset_s == 2.0 and m.drift == 0.0 and m.uncertainty_s == 1.0
    assert not m.is_fine_capable


def test_window_from_p2_onset_and_fallback():
    tl = Timeline("SWHT-PP-003-0001", "clip1", 1_000_000_000)
    tl.add_event("clip_start", 0.0, 0.0, "sync_events.csv")
    tl.add_event("clip_end", 60.0, 0.0, "sync_events.csv")
    tl.add_event("p2_onset", 55.02, 0.01, "pi_video")
    w = tl.derive_analysis_window(2.0, 5.0)
    assert w.start_s == 2.0 and abs(w.end_s - 55.02) < 1e-9
    t = np.array([1.0, 2.0, 30.0, 55.5, 59.0])
    assert tl.valid_mask(t).tolist() == [False, True, True, False, False]
    tl2 = Timeline("x", "clip1", 0)
    tl2.add_event("clip_start", 0.0, 0.0, "s")
    w2 = tl2.derive_analysis_window(2.0, 5.0, clip_end_s=30.0)
    assert w2.end_s == 25.0


def test_grade_rules():
    tl = Timeline("x", "clip1", 0)
    assert tl.grade(True, True, True, True, True, "artefact_lift") == "fine"
    assert tl.grade(True, True, True, False, True, "artefact_lift") == "coarse"
    assert tl.grade(True, True, True, True, True, "wall_clock") == "coarse"
    assert tl.grade(False, True, True, None, False, None) == "none"
    assert not tl.beat_level_ecg_allowed


def test_roundtrip_json(tmp_path):
    tl = Timeline("x", "clip1", 123)
    tl.set_map(ClockMap.fit([0, 1, 2], [0.5, 1.5, 2.5], "ecg", "artefact_lift"))
    tl.add_event("p1_onset", 2.0, 0.03, "pi_video", frame=60)
    tl.add_exclusion(50, 61, "tail")
    tl.save(tmp_path / "tl.json")
    back = Timeline.load(tmp_path / "tl.json")
    assert back.maps["ecg"].offset_s == pytest.approx(0.5)
    assert back.events[0].detail == {"frame": 60}
    assert back.exclusions[0].reason == "tail"


def test_detect_drops_and_resample():
    t = np.arange(0, 100) / 30.0
    t = np.delete(t, [10, 11, 50])  # 3 dropped frames
    d = detect_drops(t, 30.0)
    assert d["n_dropped"] == 3
    assert abs(d["drop_pct"] - 3.0) < 0.1
    grid = uniform_grid(0, t[-1], 30.0)
    v = resample_to_grid(t, np.sin(t), grid, max_gap_s=1.5 / 30.0)
    assert np.isnan(v[10]) and np.isnan(v[11]) and np.isnan(v[50])
    assert np.isfinite(v[5])
