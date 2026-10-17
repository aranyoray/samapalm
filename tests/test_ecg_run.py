"""process_ecg end to end on temporary participant folders (ATC and PDF), CONTRACTS section 4 outputs."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from palmppg.core.paths import WorkLayout
from palmppg.core.tracks import REGISTRY
from palmppg.ecg.run import ECGInputError, default_search_from_s, process_ecg
from tests.test_ecg_helpers import FS, add_lift_artefact, synthetic_ecg, write_participant

CLINICIAN = {"rhythm": "Atrial fibrillation", "ecg_hr": 66, "lead12_obtained": True, "adverse_event": None,
             "reader_id": "R2", "read_date": "2026-10-17"}


def test_process_ecg_from_atc(tmp_path, cfg):
    syn = synthetic_ecg(duration_s=60.0, hr_bpm=66.0, rsa_bpm=2.0, noise_mv=0.01, seed=21)
    x, t_step = add_lift_artefact(syn["x"], FS, 54.2, step_mv=3.0, ring_mv=1.5)
    pp = write_participant(tmp_path / "study", "SWHT-PP-003-0001", ecg_mv=x, clinician=CLINICIAN, app_label="Possible AF")
    work = WorkLayout(tmp_path / "work")
    clip_dir = work.clip("SWHT-PP-003-0001", "clip1")
    res = process_ecg(pp, clip_dir, cfg)
    assert res["export_format"] == "atc" and res["ecg_digitised"] is False and res["fs"] == FS
    assert res["n_samples"] == x.size and res["duration_s"] == 60.0 and res["problems"] == []
    ecg_dir = clip_dir / "ecg"
    clean = pd.read_parquet(ecg_dir / "ecg_clean.parquet")
    assert list(clean.columns) == ["t_ecg_s", "t_ref_s", "mv"] and len(clean) == x.size
    assert clean["t_ref_s"].isna().all() and clean["mv"].dtype == np.float32
    assert abs(clean["t_ecg_s"].iloc[-1] - (x.size - 1) / FS) < 1e-9
    rp = pd.read_parquet(ecg_dir / "rpeaks.parquet")
    assert list(rp.columns) == ["idx", "t_ecg_s", "t_ref_s", "detector_agree"]
    assert rp["t_ref_s"].isna().all() and rp["detector_agree"].dtype == bool
    before = rp[rp["t_ecg_s"] < 54.0]
    true_before = syn["r_times_s"][syn["r_times_s"] < 54.0]
    assert len(before) == true_before.size
    assert np.max(np.abs(before["t_ecg_s"].to_numpy() - true_before)) <= 0.010
    assert before["detector_agree"].mean() > 0.95
    art = json.loads((ecg_dir / "artefact.json").read_text())
    assert art["found"] is True and abs(art["onset_t_ecg_s"] - t_step) <= 0.010 and art["score"] >= 1.0
    assert art["search_from_s"] == default_search_from_s(cfg, 60.0)["search_from_s"]
    feats = json.loads((ecg_dir / "ecg_features.json").read_text())
    assert feats["requires_ecg"] is True and feats["study_id"] == "SWHT-PP-003-0001" and feats["clip_id"] == "clip1"
    assert abs(feats["hr_mean_bpm"] - syn["hr_true_bpm"]) < 1.0
    assert feats["clinician_rhythm"] == "af" and feats["app_rhythm_label"] == "Possible AF"
    assert feats["clinician_ecg_hr"] == 66.0 and feats["hard_non_af"] is False
    assert feats["ecg_digitised"] is False and feats["export_format"] == "atc" and feats["export_format_meta"] == "atc"
    assert feats["start_time"] == "2026-10-17T10:30:05+05:30" and feats["crc_ok_all"] is True
    assert feats["artefact_found"] is True and feats["feature_window_end_s"] == art["onset_t_ecg_s"]
    assert feats["n_beats"] == len(rp[rp["t_ecg_s"] < art["onset_t_ecg_s"]])
    assert feats["detectors"] == ";".join(cfg.get("ecg.detectors")) and feats["detector_agree_frac"] > 0.95
    assert feats["digitiser_rows_found"] is None and feats["clipped_frac"] == 0.0
    assert all(v is None or not (isinstance(v, float) and np.isnan(v)) for v in feats.values())
    rate = pd.read_parquet(ecg_dir / "rate_series.parquet")
    assert list(rate.columns) == ["t_ecg_s", "bpm"]
    assert abs(np.nanmedian(rate["bpm"]) - 66.0) < 2.5          # RSA of +/- 2 bpm around 66
    for key in ("hr_mean_bpm", "clinician_rhythm", "ecg_digitised", "artefact_onset_t_ecg_s"):
        assert REGISTRY.get(f"ecg__{key}").requires_ecg is True
    assert res["registered_columns"] >= 40


def test_process_ecg_from_pdf_fallback(tmp_path, cfg):
    syn = synthetic_ecg(duration_s=30.0, hr_bpm=78.0, rsa_bpm=2.0, seed=22)
    pp = write_participant(tmp_path / "study", "SWHT-PP-003-0002", pdf_mv=syn["x"], clinician={"rhythm": "sinus", "ecg_hr": 78, "lead12_obtained": False})
    clip_dir = WorkLayout(tmp_path / "work").clip("SWHT-PP-003-0002", "clip1")
    res = process_ecg(pp, clip_dir, cfg)
    assert res["export_format"] == "pdf" and res["ecg_digitised"] is True and res["fs"] == float(cfg.get("ecg.fs"))
    assert abs(res["n_samples"] - syn["x"].size) <= 2
    assert abs(res["hr_mean_bpm"] - syn["hr_true_bpm"]) < 1.0
    assert res["artefact"]["found"] is False
    feats = json.loads((clip_dir / "ecg" / "ecg_features.json").read_text())
    assert feats["ecg_digitised"] is True and feats["digitiser_rows_found"] == 3
    assert abs(feats["digitiser_px_per_mm"] - 300 / 25.4) < 0.1 and feats["digitiser_trace_coverage"] > 0.99
    assert feats["clinician_rhythm"] == "sinus" and feats["crc_ok_all"] is None and feats["start_time"] is None
    assert feats["feature_window_end_s"] == pytest.approx(res["duration_s"] - cfg.get("window.tail_exclusion_s"), abs=0.01)
    rp = pd.read_parquet(clip_dir / "ecg" / "rpeaks.parquet")
    inside = syn["r_times_s"][(syn["r_times_s"] > 0.3) & (syn["r_times_s"] < 29.7)]
    found = rp["t_ecg_s"].to_numpy()
    assert all(np.min(np.abs(found - t)) <= 0.020 for t in inside)


def test_missing_ecg_and_search_defaults(tmp_path, cfg):
    pp = write_participant(tmp_path / "study", "SWHT-PP-003-0003", ecg_mv=None)
    with pytest.raises(ECGInputError):
        process_ecg(pp, tmp_path / "work" / "x", cfg)
    d = default_search_from_s(cfg, 60.0)
    p2 = cfg.get("study.video_seconds") - cfg.get("sync.p2.at_s_before_end")
    assert d["p2_expected_ecg_s"] == p2 and d["mode"] == "before_end"
    assert d["search_from_s"] == p2 - cfg.get("sync.coarse_anchor_uncertainty_s") - cfg.get("sync.xcorr.lag_s")
    short = default_search_from_s(cfg, 30.0)          # ECG shorter than the clip: its own end stands in
    assert short["p2_expected_ecg_s"] == 30.0 - cfg.get("sync.p2.at_s_before_end")
    after = default_search_from_s(cfg.with_overrides({"sync": {"p2": {"mode": "after_start"}}}), 30.0)
    assert after["p2_expected_ecg_s"] == cfg.get("sync.p2.at_s_after_start") and after["mode"] == "after_start"
    assert default_search_from_s(cfg, 3.0)["search_from_s"] == cfg.get("sync.artefact.clean_window_s")


def test_caller_search_window_and_prefer_pdf(tmp_path, cfg):
    syn = synthetic_ecg(duration_s=40.0, hr_bpm=70.0, seed=23)
    x, t_step = add_lift_artefact(syn["x"], FS, 30.0, step_mv=2.0)
    pp = write_participant(tmp_path / "study", "SWHT-PP-003-0004", ecg_mv=x, pdf_mv=syn["x"][:int(20 * FS)], clinician=CLINICIAN)
    clip_dir = WorkLayout(tmp_path / "work").clip("SWHT-PP-003-0004", "clip1")
    res = process_ecg(pp, clip_dir, cfg, search_from_s=25.0)
    assert res["export_format"] == "atc" and res["artefact"]["found"] and abs(res["artefact"]["onset_t_ecg_s"] - t_step) <= 0.010
    art = json.loads((clip_dir / "ecg" / "artefact.json").read_text())
    assert art["search_from_s"] == 25.0 and art["search_source"] == "caller"
    res2 = process_ecg(pp, clip_dir, cfg, prefer="pdf")
    assert res2["export_format"] == "pdf" and res2["ecg_digitised"] is True and abs(res2["duration_s"] - 20.0) < 0.05
