"""Thumb contact (coarse), thumb lift (fine), wall-clock cross-check and ECG maps (section 4.3)."""
import numpy as np
import pytest

from palmppg.core.config import rng
from palmppg.core.timeline import COARSE_METHODS, FINE_METHODS
from palmppg.ingest.anchors import (
    coarse_ecg_map,
    compare_anchors,
    fine_ecg_map,
    parse_wall_ts_ns,
    thumb_contact_frame,
    thumb_lift_event,
    wall_clock_ecg_map,
)
from palmppg.ingest.bench import synth_thumb_trace

FPS = 30.0
T0 = 5_000_000_000_000


def test_thumb_contact_step_detected_within_one_frame(cfg):
    t = np.arange(int(60 * FPS)) / FPS
    contact = 1.47
    y = synth_thumb_trace(t, contact, 56.0, 0.8, 300.0, -60.0, 35.0, 3.0, rng(21, "thumb"))
    r = thumb_contact_frame(t, y, uncertainty_s=cfg.get("sync.coarse_anchor_uncertainty_s"))
    assert r["found"] and r["confidence"] > 0.6        # the lift bump at 56 s is unexplained by one step
    rw = thumb_contact_frame(t, y, search_window=(0.0, 54.0))
    assert rw["confidence"] > 0.9 and rw["frame_idx"] == int(np.ceil(contact * FPS))
    assert 0 <= r["t_s"] - contact < 1 / FPS + 1e-9   # first frame after the step
    assert r["frame_idx"] == int(np.ceil(contact * FPS))
    assert r["shift"] == pytest.approx(-60.0, abs=3.0)
    assert r["uncertainty_s"] == 1.0
    # a search window excluding the step finds nothing sustained
    r2 = thumb_contact_frame(t, y, search_window=(5.0, 50.0))
    assert not r2["found"]


def test_thumb_contact_noise_only_not_found():
    t = np.arange(int(30 * FPS)) / FPS
    y = 300.0 + rng(22, "noise").normal(0, 3.0, size=t.size)
    r = thumb_contact_frame(t, y)
    assert not r["found"] and r["confidence"] < 0.2
    assert thumb_contact_frame(t[:5], y[:5])["found"] is False


def test_thumb_lift_transient_detected_and_lift_chosen_over_putback(cfg):
    t = np.arange(int(60 * FPS)) / FPS
    lift = 55.9
    gen = rng(23, "lift")
    # put-back jump larger than the lift jump: the earliest jump above half the maximum must win
    y = 240.0 + gen.normal(0, 3.0, size=t.size)
    y += 30.0 * ((t >= lift) & (t < lift + 0.8))
    y -= 20.0 * (t >= lift + 0.8)  # put-back overshoots: total drop 50 vs lift 30
    p2 = 55.0
    win = cfg.get("sync.lift.search_s", [-1.0, 4.0])
    r = thumb_lift_event(t, y, (p2 + win[0], p2 + win[1]), k_mad=cfg.get("sync.artefact.k_mad"))
    assert r["found"] and r["z"] > 8
    assert abs(r["t_s"] - lift) <= 0.5 / FPS + 1e-9
    assert r["frame_idx"] == int(np.ceil(lift * FPS))
    assert r["jump"] > 0
    # nothing in the window
    r2 = thumb_lift_event(t, y, (10.0, 20.0), k_mad=8.0)
    assert not r2["found"]
    assert thumb_lift_event(t, y, (10.0, 10.05))["found"] is False


def test_coarse_and_fine_maps():
    c = coarse_ecg_map(1.2, 0.0, 1.0)
    assert c.stream == "ecg" and c.method == "thumb_contact" and c.offset_s == 1.2 and c.uncertainty_s == 1.0
    assert c.method in COARSE_METHODS and not c.is_fine_capable
    assert c.to_ref(10.0) == pytest.approx(11.2)
    f = fine_ecg_map(55.95, 54.45, 0.033)
    assert f.method == "artefact_lift" and f.method in FINE_METHODS and f.offset_s == pytest.approx(1.5)
    assert f.uncertainty_s == 0.033 and f.drift == 0.0
    assert f.from_ref(55.95) == pytest.approx(54.45)


def test_wall_clock_map_and_compare_anchors(cfg):
    pi_meta = {"start_wall_ns": 1_760_000_000_000_000_000, "start_mono_ns": T0 - 10_000_000, "unit_id": "unit_01"}
    # ECG t0 truly at t_ref = 1.5 s -> Pi wall at that instant
    pi_wall = pi_meta["start_wall_ns"] + (T0 + 1_500_000_000 - pi_meta["start_mono_ns"])
    day = {"unit_01": 120.0, "kardia_tablet": -300.0}   # device minus phone, ms
    kardia_wall_ns = pi_wall - 120_000_000 - 300_000_000
    iso = np.datetime64(kardia_wall_ns, "ns").astype("datetime64[us]").item().isoformat() + "+00:00"
    assert parse_wall_ts_ns(iso) == kardia_wall_ns
    w = wall_clock_ecg_map(iso, pi_meta, T0, day, uncertainty_s=1.0)
    assert w.method == "wall_clock" and w.offset_s == pytest.approx(1.5, abs=1e-6)
    # without the day offsets the map is 0.42 s off
    w0 = wall_clock_ecg_map(iso, pi_meta, T0, None)
    assert w0.offset_s == pytest.approx(1.5 - 0.42, abs=1e-6)
    # naive timestamp with a device-local offset
    naive = iso[:-6]
    assert wall_clock_ecg_map(naive, pi_meta, T0, day).offset_s == pytest.approx(1.5, abs=1e-6)
    assert wall_clock_ecg_map(naive, pi_meta, T0, day, naive_tz_offset_h=5.5).offset_s == pytest.approx(1.5 - 5.5 * 3600, abs=1e-3)
    c = coarse_ecg_map(1.2)
    cmp = compare_anchors(c, w, cfg.get("clock.wall_vs_meta_disagreement_s"))
    assert cmp["disagreement_s"] == pytest.approx(0.3, abs=1e-6) and not cmp["flag"]
    far = wall_clock_ecg_map(parse_wall_ts_ns(iso) + 10_000_000_000, pi_meta, T0, day)
    assert compare_anchors(c, far, 3.0)["flag"]
    assert compare_anchors(c, None, 3.0) == {"disagreement_s": None, "flag": False, "threshold_s": 3.0, "comparable": False}
