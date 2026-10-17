"""Fine-anchor artefact onset (protocol 4.3): a 2 mV baseline step with ringing at t = 50 s is found within
10 ms on the raw and on the cleaned ECG; a clean ECG yields found = False with a reason."""
from __future__ import annotations

import numpy as np

from palmppg.ecg.artefact import adaptive_threshold, artefact_onset, exclusion_window_ecg, slew_feature
from palmppg.ecg.clean import clean_ecg, notch
from tests.test_ecg_helpers import FS, add_lift_artefact, synthetic_ecg


def test_step_with_ringing_found_within_10_ms_raw_and_clean(cfg):
    syn = synthetic_ecg(duration_s=60.0, hr_bpm=72.0, noise_mv=0.01, seed=11)
    x, t_step = add_lift_artefact(syn["x"], FS, 50.0, step_mv=2.0, ring_mv=1.0)
    assert t_step == 50.0
    for label, sig in (("raw", x), ("clean", clean_ecg(x, FS, cfg=cfg)), ("notched", notch(x, FS, cfg.get("ecg.notch_hz")))):
        res = artefact_onset(sig, FS, search_from_s=45.0, cfg=cfg)
        assert res["found"] is True, label
        assert abs(res["onset_t_s"] - 50.0) <= 0.010, (label, res["onset_t_s"])
        assert res["score"] >= 1.0 and res["threshold"] > 0 and res["feature"] in ("slew", "excursion")
        assert res["clean_window_s"] == [45.0 - cfg.get("sync.artefact.clean_window_s"), 45.0]
        assert res["k_mad"] == cfg.get("sync.artefact.k_mad")
    # a late search start still finds the same onset; an early one finds nothing before the step
    late = artefact_onset(x, FS, search_from_s=49.5, cfg=cfg)
    assert late["found"] and abs(late["onset_t_s"] - 50.0) <= 0.010
    early = artefact_onset(x, FS, search_from_s=10.0, search_to_s=40.0, cfg=cfg)
    assert early["found"] is False


def test_clean_ecg_returns_not_found_with_reason(cfg):
    syn = synthetic_ecg(duration_s=60.0, hr_bpm=72.0, noise_mv=0.01, seed=12)
    for sig in (syn["x"], clean_ecg(syn["x"], FS, cfg=cfg)):
        res = artefact_onset(sig, FS, search_from_s=45.0, cfg=cfg)
        assert res["found"] is False and res["onset_t_s"] is None and res["score"] is None
        assert "no excursion above the adaptive threshold" in res["reason"]
        assert all(not c["found"] for c in res["candidates"].values())
        assert all(c["max_ratio"] < 1.0 for c in res["candidates"].values())
    # amplitude modulation of the QRS (respiration, +20 %) must not trigger
    mod = syn["x"] * (1.0 + 0.2 * np.sin(2 * np.pi * 0.25 * syn["t"]))
    assert artefact_onset(mod, FS, search_from_s=45.0, cfg=cfg)["found"] is False


def test_mains_noise_does_not_hide_the_step_after_notch(cfg):
    syn = synthetic_ecg(duration_s=60.0, hr_bpm=60.0, mains_mv=0.2, noise_mv=0.01, seed=13)
    x, _ = add_lift_artefact(syn["x"], FS, 50.0, step_mv=2.5, ring_mv=1.0)
    res = artefact_onset(notch(x, FS, cfg.get("ecg.notch_hz")), FS, search_from_s=46.0, cfg=cfg)
    assert res["found"] and abs(res["onset_t_s"] - 50.0) <= 0.010


def test_edge_cases_and_helpers(cfg):
    syn = synthetic_ecg(duration_s=20.0, seed=14)
    x = syn["x"]
    beyond = artefact_onset(x, FS, search_from_s=25.0, cfg=cfg)
    assert beyond["found"] is False and "beyond the signal end" in beyond["reason"]
    short = artefact_onset(x, FS, search_from_s=0.001, cfg=cfg)
    assert short["found"] is False and "clean window" in short["reason"]
    empty = artefact_onset(np.full(100, np.nan), FS, search_from_s=0.1, cfg=cfg)
    assert empty["found"] is False
    thr = adaptive_threshold(np.array([1.0, 1.0, 1.0, 1.0, 3.0]), k_mad=8.0, margin=1.5)
    assert thr["median"] == 1.0 and thr["mad"] == 0.0 and thr["threshold"] == 4.5    # margin * max wins
    f, k = slew_feature(np.array([0.0, 0.0, 1.0, 2.0, 2.0, 2.0]), fs=300.0, span_s=0.01)
    assert k == 3 and f.tolist() == [2.0, 2.0, 1.0, 0.0, 0.0]
    w = exclusion_window_ecg(50.0, 60.0)
    assert w["start_s"] == 50.0 and w["end_s"] == 60.0 and w["reason"]
