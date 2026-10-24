"""On-site quality grades (design section 4): known answers on synthetic signals, the recorder-file readers, the
Kardia PDF vector reader, and the shared fixtures that pin the Kotlin twin android/quality-core."""
import base64
import gzip
import json
import math
from pathlib import Path

import numpy as np
import pytest

from palmppg.quality import onsite

ROOT = Path(__file__).resolve().parents[1]
FX = ROOT / "configs" / "quality_fixtures"
VIDEO = json.loads((FX / "video_cases.json").read_text())
ECG = json.loads((FX / "ecg_cases.json").read_text())
KPDF = json.loads((FX / "kardia_pdf.json").read_text())

FS = 300.0


def ungz(s: str) -> str:
    return gzip.decompress(base64.b64decode(s)).decode("ascii")


def case(cases, name):
    for c in cases:
        if c["name"] == name:
            return c
    raise KeyError(name)


# --------------------------------------------------------------------------- independent synthetic signals
def synth_ecg(seconds=30.0, bpm=75.0, fs=FS, start=0.4, rr=None, noise=0.0, invert=False, seed=0):
    """Lead-I-like beats at known times: P, QRS and T as Gaussians. Returns (mv, beat times)."""
    rng = np.random.default_rng(seed)
    n = int(round(seconds * fs))
    t = np.arange(n) / fs
    if rr is None:
        step = 60.0 / bpm
        times = [start]
        while times[-1] + step < seconds:
            times.append(times[-1] + step)
    else:
        times = [start]
        for d in rr:
            if times[-1] + d >= seconds:
                break
            times.append(times[-1] + d)
    x = np.zeros(n)
    for tb in times:
        for amp, mu, sd in ((0.12, -0.16, 0.030), (-0.10, -0.020, 0.008), (1.00, 0.0, 0.010),
                            (-0.20, 0.025, 0.010), (0.25, 0.180, 0.050)):
            x += amp * np.exp(-0.5 * ((t - (tb + mu)) / sd) ** 2)
    if noise > 0:
        x = x + rng.normal(0.0, noise, n)
    if invert:
        x = -x
    return x, times


def roi_text(seconds=20.0, fps=30.0, bpm=72.0, ac=1.0, level=1.0, clip_frac=0.004, noise=0.15,
             dark_from=None, seed=1):
    """A recorder-format roi.csv for a clip whose pulse rate is known exactly."""
    rng = np.random.default_rng(seed)
    n = int(round(seconds * fps))
    t = np.arange(n) / fps
    ph = 2.0 * math.pi * (bpm / 60.0) * t
    w = np.sin(ph) + 0.35 * np.sin(2.0 * ph - 0.8)
    dc = np.array([180.0, 110.0, 80.0]) * level
    rel = np.array([0.004, 0.010, 0.006]) * ac
    r, g, b = (dc[k] * (1.0 - rel[k] * w) + rng.normal(0.0, noise, n) for k in range(3))
    cf = np.full(n, clip_frac)
    if dark_from is not None:
        dark = t >= dark_from
        for c in (r, g, b):
            c[dark] = 2.0
    y = 0.299 * r + 0.587 * g + 0.114 * b
    head = ("roi_idx,sensor_ts_ns_raw,t_ref_ns,n_px,y_mean,u_mean,v_mean,r_mean,g_mean,b_mean,clip_frac,"
            + ",".join(onsite.GRID_COLS))
    rows = [head]
    for i in range(n):
        tref = int(round(t[i] * 1e9))
        rows.append(f"{i},{tref - 1500},{tref},36864,{y[i]:.3f},128,128,{r[i]:.3f},{g[i]:.3f},{b[i]:.3f},"
                    f"{cf[i]:.5f}," + ",".join(f"{y[i]:.2f}" for _ in range(9)))
    return "\n".join(rows) + "\n"


# --------------------------------------------------------------------------- readers
def test_roi_csv_reads_every_column_and_sorts_by_time():
    text = roi_text(seconds=2.0)
    roi = onsite.parse_roi_csv(text)
    assert roi.t_s.size == 60
    assert roi.t_s[0] == 0.0 and abs(roi.t_s[-1] - 59 / 30.0) < 1e-9
    assert roi.grid is not None and roi.grid.shape == (9, 60)
    assert 100.0 < float(np.median(roi.y)) < 160.0
    shuffled = text.splitlines()
    rows = shuffled[1:]
    out = "\n".join([shuffled[0]] + rows[::-1]) + "\n"
    assert np.allclose(onsite.parse_roi_csv(out).t_s, roi.t_s)      # order of the rows does not matter


def test_roi_csv_skips_unparsable_rows_and_needs_its_columns():
    lines = roi_text(seconds=1.0).splitlines()
    assert len(lines) == 31                                          # header plus 30 rows
    lines[3] = lines[3].replace(lines[3].split(",")[2], "x", 1)      # unreadable t_ref_ns
    lines.insert(7, "garbage")
    roi = onsite.parse_roi_csv("\n".join(lines) + "\n")
    assert roi.t_s.size == 29                                        # the two bad rows are dropped
    with pytest.raises(ValueError):
        onsite.parse_roi_csv("a,b,c\n1,2,3\n")


def test_frames_csv_times_are_relative_and_sorted():
    t = onsite.parse_frames_csv("frame_idx,sensor_ts_ns\n2,2000000000\n0,1000000000\n1,1500000000\n")
    assert np.allclose(t, [0.0, 0.5, 1.0])
    assert onsite.parse_frames_csv("").size == 0


def test_ecg_csv_recovers_the_sample_rate_from_the_timestamps():
    mv = np.arange(600) / 1000.0
    rows = ["idx,t_ref_ns,lead1_mv"] + [f"{i},{int(i * 1e9 / 300)},{v:.6f}" for i, v in enumerate(mv)]
    got, fs = onsite.parse_ecg_csv("\n".join(rows) + "\n")
    assert got.size == 600 and abs(fs - 300.0) < 0.01
    assert np.allclose(got, mv, atol=1e-6)


def test_atc_round_trip_matches_the_written_samples():
    c = case(ECG["cases"], "clean_75bpm")
    tr = onsite.read_atc(base64.b64decode(c["atc_b64"]))
    assert tr.fs == 300.0 and tr.warnings == []
    assert tr.mv.size == int(30.0 * 300)
    csv_mv, _fs = onsite.parse_ecg_csv(ungz(c["csv_gz_b64"]))
    assert np.max(np.abs(tr.mv - csv_mv)) < 2.6e-4                   # within half an ATC step (500 nV/LSB)


def test_atc_damage_becomes_a_warning_not_an_exception():
    raw = bytearray(base64.b64decode(case(ECG["cases"], "clean_75bpm")["atc_b64"]))
    raw[-40] ^= 0xFF                                                 # corrupt a sample: the CRC no longer matches
    tr = onsite.read_atc(bytes(raw))
    assert tr.mv.size > 0 and any("crc" in w for w in tr.warnings)
    with pytest.raises(ValueError):
        onsite.read_atc(b"NOTATC" + bytes(40))


# --------------------------------------------------------------------------- video known answers
def test_clean_clip_recovers_the_known_pulse_rate():
    roi = onsite.parse_roi_csv(roi_text(seconds=20.0, bpm=72.0))
    g = onsite.score_video(roi, None, 20.0)
    assert g.level == "good" and g.reasons == []
    assert abs(g.metrics["pulse_bpm"] - 72.0) < 1.0
    assert g.metrics["snr_db"] > 5.0
    assert abs(g.metrics["duration_s"] - 20.0) < 0.1
    assert g.metrics["dark_frac"] == 0.0


def test_a_clip_shorter_than_nine_tenths_of_the_length_asked_for_is_a_retake():
    roi = onsite.parse_roi_csv(roi_text(seconds=12.0, bpm=72.0))
    assert onsite.score_video(roi, None, 20.0).level == "retake"     # 12 s of 20 s
    assert onsite.score_video(roi, None, 13.0).level == "good"       # 12 s of 13 s is above 0.9
    assert "Clip too short" in onsite.score_video(roi, None, 20.0).reasons[0]


def test_dark_and_black_frames_are_caught():
    dark = onsite.parse_roi_csv(roi_text(seconds=20.0, level=0.02, noise=0.3))
    g = onsite.score_video(dark, None, 20.0)
    assert g.level == "retake" and g.reasons[0].startswith("Too dark")
    tail = onsite.parse_roi_csv(roi_text(seconds=20.0, dark_from=13.0))
    g2 = onsite.score_video(tail, None, 20.0)
    assert g2.level == "retake" and any(r.startswith("Dark or black frames") for r in g2.reasons)
    assert abs(g2.metrics["dark_frac"] - 0.35) < 0.02                # 7 s of 20 s


def test_clipping_thresholds_are_the_documented_ones():
    cfg = onsite.VideoQualityConfig()
    assert (cfg.retake_clipped_frac, cfg.borderline_clipped_frac) == (0.25, 0.05)
    hot = onsite.parse_roi_csv(roi_text(seconds=20.0, clip_frac=0.30))
    assert onsite.score_video(hot, None, 20.0).level == "retake"
    warm = onsite.parse_roi_csv(roi_text(seconds=20.0, clip_frac=0.10))
    g = onsite.score_video(warm, None, 20.0)
    assert g.level == "borderline" and abs(g.metrics["clipped_frac"] - 0.10) < 1e-6


def test_dropped_frames_are_counted_from_the_frame_times():
    t = np.arange(600) / 30.0
    keep = np.ones(600, dtype=bool)
    keep[[100, 200, 300, 400, 500, 550]] = False                     # 6 of 600 frames missing
    g = onsite.score_video(onsite.parse_roi_csv(roi_text(seconds=20.0)), t[keep], 20.0)
    assert abs(g.metrics["dropped_frac"] - 6 / 600.0) < 0.002
    assert g.level == "borderline" and any("dropped frames" in r for r in g.reasons)


def test_a_clip_with_no_pulse_is_a_retake():
    roi = onsite.parse_roi_csv(roi_text(seconds=20.0, ac=0.0, noise=3.0, seed=11))
    g = onsite.score_video(roi, None, 20.0)
    assert g.level == "retake" and any("pulse" in r for r in g.reasons)


def test_a_reference_rate_that_disagrees_lowers_the_grade():
    # With a reference rate the SNR is measured at that rate (design section 4), so a reference that disagrees
    # both loses the signal band and raises the pulse-difference reason.
    roi = onsite.parse_roi_csv(roi_text(seconds=20.0, bpm=72.0))
    assert onsite.score_video(roi, None, 20.0, ref_hr_bpm=73.0).level == "good"      # within 8 bpm
    g = onsite.score_video(roi, None, 20.0, ref_hr_bpm=85.0)                         # 13 bpm apart
    assert g.level != "good"
    assert any("differs from the reference" in r for r in g.reasons), g.reasons
    assert abs(g.metrics["pulse_bpm"] - 72.0) < 1.0                  # the measured rate is unchanged


def test_an_empty_roi_file_is_a_retake_and_not_a_crash():
    roi = onsite.parse_roi_csv(roi_text(seconds=20.0).splitlines()[0] + "\n")
    g = onsite.score_video(roi, None, 20.0)
    assert g.level == "retake" and g.metrics["pulse_bpm"] is None


# --------------------------------------------------------------------------- ECG known answers
def test_clean_ecg_recovers_the_known_rate_and_beat_count():
    mv, times = synth_ecg(seconds=30.0, bpm=75.0)
    assert len(times) == 37                                          # 0.4 s to 29.2 s every 0.8 s
    g = onsite.score_ecg(mv, FS)
    assert g.level == "good" and g.reasons == []
    assert abs(g.metrics["hr_bpm"] - 75.0) < 0.5
    assert g.metrics["n_beats"] == 37
    assert g.metrics["template_corr"] > 0.95
    assert g.metrics["flat_frac"] == 0.0 and g.metrics["irregular_flag"] == 0.0


def test_qrs_detection_lands_on_the_known_beat_times():
    mv, times = synth_ecg(seconds=20.0, bpm=60.0)
    r = onsite.detect_qrs(mv, FS)
    assert r.size == len(times)
    assert np.max(np.abs(r / FS - np.array(times))) < 0.02           # within 20 ms of where the R was placed


def test_an_inverted_recording_is_flagged_and_still_measured():
    mv, times = synth_ecg(seconds=30.0, bpm=64.0, invert=True)
    g = onsite.score_ecg(mv, FS)
    assert g.metrics["inverted"] == 1.0
    assert abs(g.metrics["hr_bpm"] - 64.0) < 0.5
    assert g.metrics["n_beats"] == len(times)
    s = onsite.summarise_ecg(mv, FS)
    assert s.inverted is True and s.rhythm == "regular"


def test_a_flat_recording_is_a_retake():
    g = onsite.score_ecg(np.zeros(int(25 * FS)), FS)
    assert g.level == "retake"
    assert g.metrics["flat_frac"] == 1.0 and g.metrics["n_beats"] == 0
    assert any("Flat line" in r for r in g.reasons)
    assert any("Too few beats" in r for r in g.reasons)


def test_a_recording_under_twenty_seconds_is_a_retake():
    mv, _ = synth_ecg(seconds=15.0, bpm=75.0)
    g = onsite.score_ecg(mv, FS)
    assert g.level == "retake" and g.reasons[0].startswith("ECG too short")
    assert abs(g.metrics["duration_s"] - 15.0) < 1e-6


def test_random_beat_spacing_sets_the_irregular_flag_without_lowering_the_grade():
    rng = np.random.default_rng(7)
    rr = list(0.8 + rng.uniform(-0.22, 0.22, 60))
    mv, times = synth_ecg(seconds=40.0, rr=rr)
    g = onsite.score_ecg(mv, FS)
    assert g.metrics["irregular_flag"] == 1.0
    assert g.metrics["rmssd_ratio"] >= 0.1 and g.metrics["shannon"] >= 0.7
    assert g.level in ("good", "borderline")                         # the flag never makes it a retake
    s = onsite.summarise_ecg(mv, FS)
    assert s.rhythm == "irregular" and s.irregular_flag is True


def test_steady_beats_are_not_flagged_as_irregular():
    mv, _ = synth_ecg(seconds=40.0, bpm=72.0)
    g = onsite.score_ecg(mv, FS)
    assert g.metrics["irregular_flag"] == 0.0 and g.metrics["rmssd_ratio"] < 0.1


def test_a_long_gap_between_beats_is_borderline():
    rr = [0.8] * 12 + [3.6] + [0.8] * 20                             # one 3.6 s pause
    mv, _ = synth_ecg(seconds=40.0, rr=rr)
    g = onsite.score_ecg(mv, FS)
    assert g.metrics["rr_max_s"] > 3.0
    assert g.level == "borderline" and any("Long gap" in r for r in g.reasons)


def test_the_ecg_thresholds_are_the_documented_ones():
    cfg = onsite.EcgQualityConfig()
    assert cfg.min_duration_s == 20.0 and cfg.min_beats == 8
    assert cfg.retake_template_corr == 0.5 and cfg.borderline_template_corr == 0.66
    assert (cfg.retake_hr_lo, cfg.retake_hr_hi) == (30.0, 220.0)
    assert (cfg.borderline_hr_lo, cfg.borderline_hr_hi) == (40.0, 180.0)


# --------------------------------------------------------------------------- participant summary
def test_the_summary_never_names_a_rhythm_and_always_closes_the_same_way():
    banned = ("fibrillation", " af ", "flutter", "tachycardia", "bradycardia", "ectopic", "arrhythmia", "normal sinus")
    for mv, _ in (synth_ecg(seconds=30.0, bpm=75.0), synth_ecg(seconds=30.0, bpm=48.0),
                  (np.zeros(int(25 * FS)), [])):
        s = onsite.summarise_ecg(np.asarray(mv), FS)
        text = s.text.lower()
        assert s.sentences[-1] == onsite.CLOSING_SENTENCE
        assert "study doctor" in text
        for w in banned:
            assert w not in text
        assert s.rhythm in ("regular", "irregular", "insufficient")


def test_an_unusable_recording_reports_insufficient_and_no_rate():
    s = onsite.summarise_ecg(np.zeros(int(25 * FS)), FS)
    assert s.rhythm == "insufficient" and s.hr_bpm is None and s.n_beats == 0


# --------------------------------------------------------------------------- Kardia PDF vector reader
def test_kardia_pdf_recovers_the_known_samples():
    exp = KPDF["expected"]
    tr = onsite.read_kardia_pdf(FX / KPDF["pdf"])
    assert tr.mv.size == exp["n"] == 9000
    assert tr.fs == exp["fs"] == 300.0
    assert tr.determination == exp["determination"]
    assert tr.hr_bpm == exp["hr_bpm"] and tr.mains_hz == exp["mains_hz"]
    assert tr.enhanced_filter is exp["enhanced_filter"]
    assert tr.warnings == exp["warnings"]
    truth, _ = onsite.parse_ecg_csv(ungz(case(ECG["cases"], KPDF["truth_case"])["csv_gz_b64"]))
    err = float(np.max(np.abs(tr.mv - truth[:tr.mv.size])))
    assert err <= KPDF["max_abs_err_mv"], f"vector trace off by {err} mV"
    assert np.allclose(tr.mv[:5], exp["first_mv"], atol=1e-12)


def test_the_pdf_trace_grades_the_same_as_the_samples_it_was_drawn_from():
    tr = onsite.read_kardia_pdf(FX / KPDF["pdf"])
    g = onsite.score_ecg(tr.mv, tr.fs)
    assert g.level == KPDF["expected"]["grade"]["level"]
    assert abs(g.metrics["hr_bpm"] - 75.0) < 1.0
    assert g.metrics["n_beats"] == 37


def test_a_file_that_is_not_a_pdf_or_holds_no_trace_raises():
    with pytest.raises(ValueError):
        onsite.read_kardia_pdf(b"not a pdf at all")
    empty = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[]/Count 0>>endobj\n"
    with pytest.raises(ValueError):
        onsite.read_kardia_pdf(empty)


# --------------------------------------------------------------------------- fixtures (these pin the Kotlin twin)
@pytest.mark.parametrize("c", VIDEO["cases"], ids=[c["name"] for c in VIDEO["cases"]])
def test_video_fixture_cases(c):
    roi = onsite.parse_roi_csv(ungz(c["roi_csv_gz_b64"]))
    ft = onsite.parse_frames_csv(ungz(c["frames_csv_gz_b64"])) if c.get("frames_csv_gz_b64") else None
    g = onsite.score_video(roi, ft, c["expected_seconds"], c["ref_hr_bpm"])
    known = c["known"]
    assert g.level == known["level"]
    if "reason_prefix" in known:
        assert any(r.startswith(known["reason_prefix"]) for r in g.reasons), g.reasons
    for key, tol in (("pulse_bpm", 1.5), ("duration_s", 0.2), ("dropped_frac", 0.01),
                     ("dark_frac", 0.05), ("clipped_frac", 0.02)):
        if key in known:
            assert abs(g.metrics[key] - known[key]) <= tol, key
    exp = c["expected"]
    assert g.level == exp["level"] and g.reasons == exp["reasons"]
    for key, want in exp["metrics"].items():
        got = g.metrics[key]
        if want is None:
            assert got is None, key
        else:
            assert abs(got - want) <= 1e-9 * max(1.0, abs(want)), key


@pytest.mark.parametrize("c", ECG["cases"], ids=[c["name"] for c in ECG["cases"]])
def test_ecg_fixture_cases(c):
    tr = onsite.read_atc(base64.b64decode(c["atc_b64"]))
    g = onsite.score_ecg(tr.mv, tr.fs)
    known = c["known"]
    assert g.level == known["level"]
    if "hr_bpm" in known:
        assert abs(g.metrics["hr_bpm"] - known["hr_bpm"]) <= 1.0
    if "n_beats" in known:
        assert g.metrics["n_beats"] == known["n_beats"]
    if "flat_frac" in known:
        assert abs(g.metrics["flat_frac"] - known["flat_frac"]) <= 0.05
    if "rr_max_s" in known:
        assert abs(g.metrics["rr_max_s"] - known["rr_max_s"]) <= 0.05
    if known.get("irregular"):
        assert g.metrics["irregular_flag"] == 1.0
    if known.get("rr_ratio_over"):
        # an irregular record turns the RR-ratio rule off, so a high ratio does not lower the grade
        assert g.metrics["rr_ratio"] > known["rr_ratio_over"] and g.level == "good"
    if "reason_prefix" in known:
        assert any(r.startswith(known["reason_prefix"]) for r in g.reasons), g.reasons
    exp = c["expected"]
    assert g.level == exp["level"] and g.reasons == exp["reasons"]
    for key, want in exp["metrics"].items():
        got = g.metrics[key]
        assert (got is None) == (want is None), key
        if want is not None:
            assert abs(got - want) <= 1e-9 * max(1.0, abs(want)), key
    s = onsite.summarise_ecg(tr.mv, tr.fs)
    want_s = c["summary"]
    assert s.rhythm == want_s["rhythm"] == known["rhythm"]
    assert s.inverted is want_s["inverted"]
    if "inverted" in known:
        assert s.inverted is known["inverted"]
    assert s.n_beats == want_s["n_beats"]
    assert s.sentences == want_s["sentences"]


CSV_CASES = [c for c in ECG["cases"] if "csv_gz_b64" in c]


@pytest.mark.parametrize("c", CSV_CASES, ids=[c["name"] for c in CSV_CASES])
def test_ecg_fixture_cases_from_the_samples_csv(c):
    mv, fs = onsite.parse_ecg_csv(ungz(c["csv_gz_b64"]))
    exp = c["csv_expected"]
    assert mv.size == exp["n"] and abs(fs - exp["fs"]) < 1e-6
    g = onsite.score_ecg(mv, fs)
    assert g.level == exp["level"] and g.reasons == exp["reasons"]
    for key, want in exp["metrics"].items():
        got = g.metrics[key]
        assert (got is None) == (want is None), key
        if want is not None:
            assert abs(got - want) <= 1e-9 * max(1.0, abs(want)), key


def test_the_fixture_files_carry_no_participant_data():
    for p in sorted(FX.glob("*.json")):
        note = json.loads(p.read_text()).get("note", "")
        assert "ynthetic" in note, f"{p.name} must say it is synthetic"
