"""Known-answer tests for palmppg.beats (protocol 6.5, 6.6) on a synthetic PPG with known beats and morphology."""
import json

import numpy as np
import pandas as pd
import pytest

from palmppg.beats import apg, hrv, morphology, pat, perfusion, quality, resp
from palmppg.beats.run import run_beats
from palmppg.beats.segmentation import detect_beats
from palmppg.core.config import rng
from palmppg.core.timeline import Timeline

FS = 30.0
DUR = 60.0
SYS_T, DIA_T = 0.18, 0.42      # systolic and diastolic (dicrotic) peak times after the foot (s)


def synth_ppg(hr=70.0, hrv_bpm=5.0, resp_hz=0.25, resp_amp=0.0, seed=1, ectopic_at=()):
    """Sum of two Gaussians per beat; returns (t, x, foot_times, ibis)."""
    r = rng(seed, "beats")
    feet, t = [], 0.5
    k = 0
    while t < DUR - 1.5:
        feet.append(t)
        inst = hr + hrv_bpm * np.sin(2 * np.pi * 0.1 * t) + r.normal(0, 0.3)
        ibi = 60.0 / inst
        if k in ectopic_at:
            ibi *= 0.7
        elif k - 1 in ectopic_at:
            ibi *= 1.3
        t += ibi
        k += 1
    feet = np.array(feet)
    tt = np.arange(0, DUR, 1 / FS)
    x = np.zeros_like(tt)
    for f in feet:
        x += 1.0 * np.exp(-0.5 * ((tt - f - SYS_T) / 0.07) ** 2) + 0.35 * np.exp(-0.5 * ((tt - f - DIA_T) / 0.06) ** 2)
    x *= 1.0 + resp_amp * np.sin(2 * np.pi * resp_hz * tt)
    return tt, x, feet, np.diff(feet)


def test_segmentation_finds_every_beat_within_one_frame():
    _t, x, feet, _ = synth_ppg()
    b = detect_beats(x, FS, (0.33, 2.0), t0=0.0)
    peaks_true = feet + SYS_T
    got = b["peak_t"].to_numpy()
    err = np.array([np.min(np.abs(got - p)) for p in peaks_true[1:-1]])
    assert len(b) >= len(feet) - 2
    assert np.median(err) < 1 / FS and np.max(err) < 2 / FS


def test_hrv_matches_generator():
    _, x, _feet, ibis = synth_ppg()
    b = detect_beats(x, FS, (0.33, 2.0))
    got = b["ibi_s"].dropna().to_numpy()
    h_true = hrv.hrv_features(ibis)
    h = hrv.hrv_features(got)
    assert abs(h["mean_hr_bpm"] - h_true["mean_hr_bpm"]) < 1.0
    assert abs(h["sdnn_ms"] - h_true["sdnn_ms"]) / h_true["sdnn_ms"] < 0.15
    for k in ("rmssd_ms", "pnn50", "sampen", "sd1_ms", "sd2_ms", "tpr", "ibi_hist_entropy"):
        assert k in h


def test_morphology_notch_and_upstroke():
    _, x, _, _ = synth_ppg(hrv_bpm=0.0)
    b = detect_beats(x, FS, (0.33, 2.0))
    q = quality.beat_quality(b, x, FS)
    pb = morphology.beat_morphology(b, x, FS)
    ens = morphology.ensemble_morphology(pb, q["quality"], 0.5)
    assert ens["dicrotic_notch_present"] is True
    # tangent foot to systolic peak: the Gaussian upstroke (sigma 70 ms) puts the tangent foot about 2 sigma before the peak
    assert 0.08 < ens["upstroke_time_s"] < SYS_T + 0.04
    assert DIA_T - 0.15 < ens["notch_time_s"] < DIA_T + 0.05
    assert 0.0 < ens["reflection_index"] < 1.0
    assert q["quality"].median() > 0.8


def test_apg_wave_order_and_signs():
    _, x, _, _ = synth_ppg(hrv_bpm=0.0)
    b = detect_beats(x, FS, (0.33, 2.0))
    q = quality.beat_quality(b, x, FS)
    w = apg.ensemble_apg(b, x, FS, q["quality"], 0.5)
    assert w["a"] > 0 and w["b"] < 0
    assert w["b_a"] < 0 and np.isfinite(w["ageing_index"])


def test_perfusion_index_recovers_injected_ac_dc():
    t = np.arange(0, DUR, 1 / FS)
    dc, ac_frac = 400.0, 0.008
    sig = dc * (1 - ac_frac / 2 * np.sin(2 * np.pi * 1.2 * t))   # peak-to-peak AC = ac_frac * dc
    df = pd.DataFrame({"t_ref_s": t, "thenar__G__mean": sig})
    r = perfusion.perfusion_index(df, "thenar", "G", (0.5, 4.0), FS)
    assert abs(r["pi_pct"] - 0.8) < 0.1


def test_resp_proxy_recovers_modulation():
    _, x, _, _ = synth_ppg(hrv_bpm=0.0, resp_amp=0.2, resp_hz=0.25)
    b = detect_beats(x, FS, (0.33, 2.0))
    r = resp.respiratory_proxy(x, FS, (0.1, 0.5), foot_t=b["foot_t"].to_numpy(), amplitude=b["amplitude"].to_numpy(),
                               ibi_s=b["ibi_s"].to_numpy())
    assert abs(r["resp_rate_am_bpm"] - 15.0) < 1.5


def _tl(grade):
    tl = Timeline("SWHT-PP-003-0001", "clip1", 0)
    tl.sync_grade = grade
    return tl


def test_pat_pairing_recovers_known_delay_and_refuses_without_fine():
    _, _, feet, _ = synth_ppg()
    r_peaks = feet - 0.220
    pairs = pat.pair_r_to_foot(r_peaks, feet, (120, 450), _tl("fine"))
    s = pat.pat_summary(pairs, _tl("fine"))
    assert abs(s["pat_mean_ms"] - 220.0) < 5.0 and s["pairing_rate"] > 0.95
    with pytest.raises(pat.SyncGradeError):
        pat.pair_r_to_foot(r_peaks, feet, (120, 450), _tl("coarse"))


def test_ectopic_capture():
    _, _, feet, _ = synth_ppg(hrv_bpm=0.0, ectopic_at=(10, 20, 30, 40, 50))
    r_peaks = feet - 0.2
    pairs = pat.pair_r_to_foot(r_peaks, feet, (120, 450), _tl("fine"))
    c = pat.compare_ibis(r_peaks, feet, pairs, _tl("fine"))
    assert c["n_ectopic_ecg"] >= 5 and c["ectopic_capture_fraction"] > 0.9


def test_run_beats_end_to_end(tmp_path, cfg):
    t, x, feet, _ = synth_ppg()
    cam = tmp_path / "pi"
    cam.mkdir()
    pd.DataFrame({"t_ref_s": t, "GREEN__thenar": x}).to_parquet(cam / "pulse_morph.parquet")
    (cam / "pulse_sqi.json").write_text(json.dumps({"GREEN__thenar": {"sqi": 0.9, "hr_bpm": 70.0}, "best": "GREEN__thenar"}))
    pd.DataFrame({"t_ref_s": t, "thenar__G__mean": 400 * (1 - 0.004 * x)}).to_parquet(cam / "traces.parquet")
    tl = _tl("fine")
    tl.add_event("clip_start", 0.0, 0.0, "test")
    tl.derive_analysis_window(2.0, 5.0, clip_end_s=DUR)
    # PAT is defined to the detected (intersecting-tangent) foot, which lies after the generator's beat origin;
    # place the R-peaks 250 ms before the feet the detector reports (the definition offset is measured separately)
    det_feet = detect_beats(x, FS, (0.33, 2.0))["foot_t"].to_numpy()
    out = run_beats(cam, "pi", cfg, tl, ecg_rpeaks_t_ref_s=det_feet - 0.25)
    f = json.loads((cam / "beat_features.json").read_text())
    p = json.loads((cam / "pat.json").read_text())
    assert (cam / "beats.parquet").exists() and len(out["beats"]) > 40
    assert abs(f["hrv"]["mean_hr_bpm"] - 70.0) < 2.0
    assert p["requires_ecg"] is True and abs(p["pat_mean_ms"] - 250.0) < 10.0
    assert out["beats"]["foot_t"].min() >= 2.0 - 1 / FS and out["beats"]["foot_t"].max() <= DUR - 5.0
    tl2 = _tl("coarse")
    tl2.analysis_window = tl.analysis_window
    out2 = run_beats(cam, "pi", cfg, tl2, ecg_rpeaks_t_ref_s=feet - 0.25)
    assert "skipped" in out2["pat"]
