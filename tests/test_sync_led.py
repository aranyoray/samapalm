"""LED block trace, pattern detection with sub-frame onsets, and the offset+drift fit (section 4.2, D-003)."""
import numpy as np
import pytest

from palmppg.core.config import rng
from palmppg.ingest.bench import on_intervals, synth_led_trace
from palmppg.ingest.led import (
    block_to_plane_coords,
    detect_pattern,
    fit_led_offset,
    led_trace,
    led_trace_with_plane,
    plane_contrast,
    select_best_plane,
)
from palmppg.ingest.sync_events import pattern_edges, pattern_spec, pattern_specs

FPS = 30.0


def _pi_frames(n, block, lit_frames, gen):
    """Tiny Bayer-plane frames: LED lights the block on the R plane strongly, G1 weakly, B not at all."""
    pb = block_to_plane_coords(block)
    for k in range(n):
        planes = {}
        for name, gain in (("R", 300.0), ("G1", 60.0), ("G2", 60.0), ("B", 0.0)):
            arr = 80.0 + gen.normal(0, 2, size=(20, 24))
            if k in lit_frames:
                arr[pb["y"]:pb["y"] + pb["h"], pb["x"]:pb["x"] + pb["w"]] += gain
            planes[name] = arr.astype(np.uint16)
        yield k, planes


def test_led_trace_picks_best_contrast_bayer_plane():
    gen = rng(1, "frames")
    block = {"x": 8, "y": 8, "w": 8, "h": 8}
    lit = set(range(10, 13)) | set(range(19, 22))
    idx, y, plane = led_trace_with_plane(_pi_frames(40, block, lit, gen), block)
    assert plane == "R"
    assert idx.tolist() == list(range(40))
    assert y[11] - y[0] > 250 and abs(y[5] - y[0]) < 10
    _idx2, y2 = led_trace(_pi_frames(40, block, lit, gen), block, plane_selector="G1")
    assert 40 < y2[11] - y2[0] < 80
    with pytest.raises(KeyError):
        led_trace(_pi_frames(4, block, set(), gen), block, plane_selector="Y")


def test_led_trace_rgb_channel_and_contrast_score():
    gen = rng(2, "rgb")
    block = {"x": 4, "y": 4, "w": 6, "h": 6}

    def frames():
        for k in range(30):
            img = np.full((32, 32, 3), 40, dtype=np.uint8)
            if 10 <= k < 13:
                img[4:10, 4:10, 1] = 220  # green LED
            yield k, img

    _idx, y, ch = led_trace_with_plane(frames(), block)
    assert ch == "G" and y[11] == 220 and y[0] == 40
    assert plane_contrast(np.array([1.0, 1.0, 1.0, 3.0] * 25)) == pytest.approx(2.0, abs=0.1)
    assert select_best_plane({"a": np.r_[np.ones(99), 2.0], "b": np.r_[np.ones(99), 5.0]}) == "b"
    assert plane_contrast(np.array([np.nan, 1.0])) == 0.0
    _ = gen


@pytest.mark.parametrize("onset", [2.0123, 2.0291, 2.0005])
def test_detect_pattern_recovers_subframe_onset_within_10ms(cfg, onset):
    """Full-frame exposure (as on the phone at 30 fps): each edge is recovered to a few ms."""
    specs = pattern_specs(cfg)
    gen = rng(3, f"led-{onset}")
    t = np.arange(int(10 * FPS)) / FPS
    exposure = 0.9 / FPS
    y = synth_led_trace(t, on_intervals({"P1": onset}, specs), 0.0, 0.0, exposure, 100.0, 400.0, 2.0, gen)
    det = detect_pattern(t, y, specs["P1"], FPS, exposure_s=exposure)
    assert det is not None
    assert abs(det["onset_s"] - onset) < 0.010
    ideal = pattern_edges(onset, specs["P1"])
    assert len(det["edges"]) == 6
    for e, (ti, ki) in zip(det["edges"], ideal):
        assert e["kind"] == ki and abs(e["t_s"] - ti) < 0.010
        assert 0.0 <= e["subframe_frac"] <= 1.0 and e["frame_idx"] == e["frame_before"] + 1
        assert e["confidence"] > 0.3
    # the first lit frame is the one whose exposure contains the onset (partially lit) or the next one
    assert det["edges"][0]["frame_idx"] in (int(np.floor(onset * FPS)), int(np.ceil(onset * FPS)))


def test_detect_pattern_short_exposure_bounded_by_half_gap(cfg):
    """Pi exposure 8 ms at 30 fps: the onset lies in the dark gap between exposures; the midpoint estimate
    is within half that gap (plus noise)."""
    specs = pattern_specs(cfg)
    exposure = 0.008
    for onset in (2.010, 2.020, 2.0333):
        y = synth_led_trace(np.arange(300) / FPS, on_intervals({"P1": onset}, specs), 0.0, 0.0, exposure,
                            90.0, 380.0, 3.0, rng(4, str(onset)))
        det = detect_pattern(np.arange(300) / FPS, y, specs["P1"], FPS, exposure_s=exposure)
        assert det is not None
        assert abs(det["onset_s"] - onset) <= 0.5 * (1 / FPS - exposure) + 0.002


def test_detect_pattern_absent_or_wrong_pattern_returns_none(cfg):
    specs = pattern_specs(cfg)
    t = np.arange(int(10 * FPS)) / FPS
    gen = rng(5, "absent")
    noise_only = 100.0 + gen.normal(0, 2, size=t.size)
    assert detect_pattern(t, noise_only, specs["P1"], FPS) is None
    # P2 present but we ask for P1 (and vice versa)
    y2 = synth_led_trace(t, on_intervals({"P2": 3.0}, specs), 0.0, 0.0, 0.0, 100.0, 400.0, 2.0, gen)
    assert detect_pattern(t, y2, specs["P1"], FPS) is None
    assert detect_pattern(t, y2, specs["P2"], FPS) is not None
    # a single long flash is neither
    y3 = 100.0 + 300.0 * ((t > 4) & (t < 5)) + gen.normal(0, 2, size=t.size)
    assert detect_pattern(t, y3, specs["P1"], FPS) is None and detect_pattern(t, y3, specs["P2"], FPS) is None
    # slow box-light drift does not break detection (baseline removal)
    y4 = synth_led_trace(t, on_intervals({"P1": 6.0}, specs), 0.0, 0.0, 0.0, 100.0, 400.0, 2.0, gen) + 40.0 * t
    d4 = detect_pattern(t, y4, specs["P1"], FPS)
    assert d4 is not None and abs(d4["onset_s"] - 6.0) < 1 / FPS


def test_detect_pattern_handles_dropped_frames_and_search_window(cfg):
    specs = pattern_specs(cfg)
    t = np.arange(int(8 * FPS)) / FPS
    y = synth_led_trace(t, on_intervals({"P1": 2.0, "P2": 5.0}, specs), 0.0, 0.0, 0.0, 100.0, 400.0, 2.0, rng(6, "d"))
    keep = np.ones(t.size, bool)
    keep[[30, 31, 100, 200]] = False  # drops away from the edges
    det = detect_pattern(t[keep], y[keep], specs["P2"], FPS, frame_idx=np.arange(t.size)[keep])
    assert det is not None and abs(det["onset_s"] - 5.0) < 1 / FPS
    assert det["edges"][0]["frame_idx"] == 150
    assert detect_pattern(t, y, specs["P2"], FPS, search_window=(0.0, 4.0)) is None


def _edges_from_ideal(ideal, offset, drift, jitter_s, gen):
    out = {}
    for pat, edges in ideal.items():
        out[pat] = [{"t_s": (t - offset) / (1 + drift) + gen.uniform(-jitter_s, jitter_s), "kind": k} for t, k in edges]
    return out


def test_fit_led_offset_recovers_offset_and_drift_from_10_edges(cfg):
    ideal = {"P1": pattern_edges(2.0, pattern_spec(cfg, "P1")), "P2": pattern_edges(55.0, pattern_spec(cfg, "P2"))}
    det = _edges_from_ideal(ideal, 1.234, 5e-5, 0.0, rng(7, "fit"))
    cm, rep = fit_led_offset(det, ideal, "phone_video", FPS, cfg.get("sync.edge_tolerance_frames"), cfg.get("sync.min_edges"))
    assert cm is not None and cm.method == "led_pattern" and cm.stream == "phone_video"
    assert cm.offset_s == pytest.approx(1.234, abs=1e-6)
    assert cm.drift == pytest.approx(5e-5, abs=1e-8)
    assert rep["n_matched"] == 10 and rep["drift_fitted"] and rep["accepted"]
    assert rep["residual_max_frames"] < 1e-3
    assert len(rep["residuals"]) == 10 and all(abs(r["residual_frames"]) < 1e-3 for r in rep["residuals"])
    assert cm.is_fine_capable
    # sub-frame jitter (quarter frame) still accepted; offset within a few ms
    det2 = _edges_from_ideal(ideal, 1.234, 5e-5, 0.25 / FPS, rng(8, "fit"))
    cm2, rep2 = fit_led_offset(det2, ideal, "phone_video", FPS, 1.0, 6)
    assert rep2["accepted"] and abs(cm2.offset_s - 1.234) < 0.01 and rep2["residual_max_frames"] <= 0.5


def test_fit_led_offset_rejects_three_frame_jitter_and_too_few_edges(cfg):
    ideal = {"P1": pattern_edges(2.0, pattern_spec(cfg, "P1")), "P2": pattern_edges(55.0, pattern_spec(cfg, "P2"))}
    gen = rng(9, "jitter")
    det = _edges_from_ideal(ideal, 1.234, 5e-5, 3.0 / FPS, gen)
    cm, rep = fit_led_offset(det, ideal, "phone_video", FPS, 1.0, 6)
    assert cm is not None and not rep["accepted"]
    assert rep["residual_max_frames"] > 1.0 and "exceeds" in rep["reason"]
    # only P2 (4 edges) matched: below min_edges, offset-only fit
    _cm3, rep3 = fit_led_offset({"P2": det["P2"]}, ideal, "phone_video", FPS, 1.0, 6)
    assert rep3["n_matched"] == 4 and rep3["drift_fitted"] and not rep3["accepted"]
    cm4, rep4 = fit_led_offset({"P1": det["P1"][:2]}, ideal, "phone_video", FPS, 1.0, 6)
    assert rep4["n_matched"] == 2 and not rep4["drift_fitted"] and cm4.drift == 0.0 and not rep4["accepted"]
    cm5, rep5 = fit_led_offset({}, ideal, "phone_video", FPS, 1.0, 6)
    assert cm5 is None and rep5["reason"] == "no edges matched"


def test_detector_plus_fit_end_to_end_phone_offset(cfg):
    """Phone trace generated with offset 1.234 s and drift 5e-5 through the detector then the fit."""
    specs = pattern_specs(cfg)
    gen = rng(10, "e2e")
    intervals = on_intervals({"P1": 2.0, "P2": 55.0}, specs)
    ideal = {k: pattern_edges(t, specs[k]) for k, t in (("P1", 2.0), ("P2", 55.0))}
    t = np.arange(int(60 * FPS)) / FPS + gen.uniform(-5e-4, 5e-4, size=int(60 * FPS))
    exposure = 0.9 / FPS
    y = synth_led_trace(t, intervals, 1.234, 5e-5, exposure, 40.0, 220.0, 2.5, gen)
    det = {k: detect_pattern(t, y, specs[k], FPS, exposure_s=exposure) for k in specs}
    assert all(d is not None for d in det.values())
    cm, rep = fit_led_offset(det, ideal, "phone_video", FPS, 1.0, 6)
    assert rep["accepted"] and rep["n_matched"] == 10
    assert abs(cm.offset_s - 1.234) < 0.006
    assert abs(cm.drift - 5e-5) < 2e-4
    assert cm.uncertainty_s < 0.01
