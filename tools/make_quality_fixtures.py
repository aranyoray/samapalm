"""Build configs/quality_fixtures/: synthetic clips and ECGs with known answers, in the recorder's own file formats,
plus the Python grades that the Kotlin module (android/quality-core) must reproduce.

* video_cases.json: `<clip>_roi.csv` (and `<clip>_frames.csv`) text, gzip + base64, 20 s clips at 30 fps.
* ecg_cases.json: lead-I ECGs as `<clip>_ecg.atc` bytes (base64, 153 nV/LSB like AtcWriter) and, for one case,
  the matching `<clip>_ecg_samples.csv` text (gzip + base64).
* kardia_synthetic.pdf + kardia_pdf.json: a vector Kardia-like 1-lead page (US Letter, 4 strips, 0.2362 pt per
  sample, 1 mV calibration pulse, beat ticks, grid, baselines) drawn from the clean ECG case, so the samples the
  reader recovers can be checked against the ATC samples.

Each case carries `known` (what the synthetic signal was built with) and `expected` (the reference output). The
known answers are asserted before anything is written. Re-run after changing palmppg/quality/onsite.py and review
the diff: python tools/make_quality_fixtures.py
"""
import base64
import gzip
import json
import math
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from palmppg.ecg.atc import write_atc  # noqa: E402
from palmppg.quality import onsite  # noqa: E402

OUT = ROOT / "configs" / "quality_fixtures"
FPS = 30.0
T0_NS = 81_234_567_890_123        # a boot-clock origin like the phone's
VIDEO_S = 20.0
ECG_FS = 300.0
ATC_NV = 153                       # AtcWriter.RESOLUTION_NV


def gz64(text: str) -> str:
    return base64.b64encode(gzip.compress(text.encode("ascii"), mtime=0)).decode("ascii")


def clean_metrics(m: dict) -> dict:
    return {k: (None if v is None else float(v)) for k, v in m.items()}


# --------------------------------------------------------------------------- video
def ppg(t: np.ndarray, f_hz: float) -> np.ndarray:
    ph = 2.0 * math.pi * f_hz * t
    return np.sin(ph) + 0.35 * np.sin(2.0 * ph - 0.8) + 0.1 * np.sin(3.0 * ph - 1.6)


def roi_csv(t_s, r, g, b, clip, grid) -> str:
    y = 0.299 * r + 0.587 * g + 0.114 * b
    u = 128.0 - 0.168736 * r - 0.331264 * g + 0.5 * b
    v = 128.0 + 0.5 * r - 0.418688 * g - 0.081312 * b
    head = ("roi_idx,sensor_ts_ns_raw,t_ref_ns,n_px,y_mean,u_mean,v_mean,r_mean,g_mean,b_mean,clip_frac,"
            + ",".join(onsite.GRID_COLS))
    rows = [head]
    for i in range(t_s.size):
        tref = T0_NS + int(round(t_s[i] * 1e9))
        rows.append(f"{i},{tref - 1500},{tref},36864,{y[i]:.3f},{u[i]:.3f},{v[i]:.3f},{r[i]:.3f},{g[i]:.3f},"
                    f"{b[i]:.3f},{clip[i]:.5f}," + ",".join(f"{grid[k, i]:.2f}" for k in range(9)))
    return "\n".join(rows) + "\n"


def frames_csv(t_s) -> str:
    rows = ["frame_idx,sensor_ts_ns,wall_ns,iso,exposure_ns"]
    for i, t in enumerate(t_s):
        ts = T0_NS + int(round(t * 1e9))
        rows.append(f"{i},{ts},{1_761_300_000_000_000_000 + ts},400,8000000")
    return "\n".join(rows) + "\n"


def make_clip(seed: int, seconds: float = VIDEO_S, bpm: float = 72.0, ac: float = 1.0, noise: float = 0.15,
              level: float = 1.0, clip_frac: float = 0.004, black_from: float | None = None,
              drop_frac: float = 0.0, motion: float = 0.0):
    rng = np.random.default_rng(seed)
    n_all = int(round(seconds * FPS))
    t = np.arange(n_all) / FPS + rng.normal(0.0, 0.0004, n_all)
    t[0] = 0.0
    keep = np.ones(n_all, dtype=bool)
    if drop_frac > 0:
        drop = rng.choice(np.arange(5, n_all - 5), size=int(round(drop_frac * n_all)), replace=False)
        keep[drop] = False
    w = ppg(t, bpm / 60.0)
    light = 1.0 + 0.01 * np.sin(2.0 * math.pi * 0.11 * t)          # torch / ambient drift, cancelled by POS
    dc = np.array([180.0, 110.0, 80.0]) * level
    rel = np.array([0.004, 0.010, 0.006]) * ac
    chans = [dc[k] * light * (1.0 - rel[k] * w) + rng.normal(0.0, noise, n_all) for k in range(3)]
    r, g, b = chans
    cf = np.clip(clip_frac + rng.normal(0.0, 0.0005, n_all), 0.0, 1.0)
    y = 0.299 * r + 0.587 * g + 0.114 * b
    offs = np.linspace(-0.08, 0.08, 9)[:, None]
    grid = y[None, :] * (1.0 + offs) + rng.normal(0.0, 0.05, (9, n_all))
    if motion > 0:
        grid = grid * (1.0 + np.cumsum(rng.normal(0.0, motion, (9, n_all)), axis=1) * 0.2
                       + rng.normal(0.0, motion, (9, n_all)))
    if black_from is not None:
        dark = t >= black_from
        for c in (r, g, b):
            c[dark] = 2.0 + rng.normal(0.0, 0.3, int(dark.sum()))
        grid[:, dark] = 2.0
        cf[dark] = 0.0
    return t[keep], r[keep], g[keep], b[keep], cf[keep], grid[:, keep]


VIDEO_CASES = [
    # name, make_clip kwargs, expected_seconds, ref_hr, use frames.csv, known answers
    ("clean_72bpm", dict(seed=1), VIDEO_S, None, True,
     {"level": "good", "pulse_bpm": 72.0, "duration_s": 20.0, "dropped_frac": 0.0}),
    ("clean_with_ref_hr", dict(seed=2, bpm=66.0), VIDEO_S, 67.0, True,
     {"level": "good", "pulse_bpm": 66.0}),
    ("noisy_no_pulse", dict(seed=3, ac=0.02, noise=3.0), VIDEO_S, None, True,
     {"level": "retake", "reason_prefix": "No clear pulse"}),
    ("black_frames_tail", dict(seed=4, black_from=13.0), VIDEO_S, None, True,
     {"level": "retake", "reason_prefix": "Dark or black frames", "dark_frac": 0.35}),
    ("all_black", dict(seed=5, level=0.015, noise=0.3), VIDEO_S, None, False,
     {"level": "retake", "reason_prefix": "Too dark"}),
    ("short_12s_of_20", dict(seed=6, seconds=12.0), VIDEO_S, None, True,
     {"level": "retake", "reason_prefix": "Clip too short", "duration_s": 12.0}),
    ("clipped", dict(seed=7, clip_frac=0.35), VIDEO_S, None, True,
     {"level": "retake", "reason_prefix": "Overexposed", "clipped_frac": 0.35}),
    ("dropped_3pct", dict(seed=8, drop_frac=0.03), VIDEO_S, None, True,
     {"level": "borderline", "reason_prefix": "Some dropped frames", "dropped_frac": 0.03}),
    ("hand_motion", dict(seed=9, motion=0.03), VIDEO_S, None, True,
     {"level": "borderline", "reason_prefix": "Hand or phone moved"}),
]


def video_fixtures() -> list[dict]:
    out = []
    for name, kw, expected_s, ref, with_frames, known in VIDEO_CASES:
        t, r, g, b, cf, grid = make_clip(**kw)
        roi_text = roi_csv(t, r, g, b, cf, grid)
        frames_text = frames_csv(t) if with_frames else None
        roi = onsite.parse_roi_csv(roi_text)
        ft = onsite.parse_frames_csv(frames_text) if frames_text else None
        gr = onsite.score_video(roi, ft, expected_s, ref)
        m = gr.metrics
        assert gr.level == known["level"], (name, gr.level, gr.reasons)
        if "reason_prefix" in known:
            assert gr.reasons and gr.reasons[0].startswith(known["reason_prefix"]), (name, gr.reasons)
        if "pulse_bpm" in known:
            assert abs(m["pulse_bpm"] - known["pulse_bpm"]) < 1.5, (name, m["pulse_bpm"])
        for k, tol in (("duration_s", 0.05), ("dropped_frac", 0.002), ("dark_frac", 0.01), ("clipped_frac", 0.002)):
            if k in known:
                assert abs(m[k] - known[k]) <= tol, (name, k, m[k])
        out.append({"name": name, "expected_seconds": expected_s, "ref_hr_bpm": ref, "known": known,
                    "roi_csv_gz_b64": gz64(roi_text), "frames_csv_gz_b64": gz64(frames_text) if frames_text else None,
                    "expected": {"level": gr.level, "reasons": gr.reasons, "metrics": clean_metrics(m)}})
        print(f"video {name:20s} {gr.level:10s} {gr.reasons}")
    return out


# --------------------------------------------------------------------------- ECG
WAVES = (  # (offset s from R, amplitude mV, width s): P, Q, R, S, T
    (-0.20, 0.12, 0.025), (-0.03, -0.10, 0.008), (0.0, 1.0, 0.010), (0.03, -0.25, 0.010), (0.28, 0.30, 0.045))


def ecg_from_r(r_times, seconds: float, rng, p_wave: bool = True, white: float = 0.01, wander: float = 0.1,
               mains: float = 0.02) -> np.ndarray:
    n = int(round(seconds * ECG_FS))
    t = np.arange(n) / ECG_FS
    x = np.zeros(n)
    for rt in r_times:
        for off, amp, wid in WAVES:
            if off == -0.20 and not p_wave:
                continue
            c = rt + off
            lo, hi = max(0, int((c - 5 * wid) * ECG_FS)), min(n, int((c + 5 * wid) * ECG_FS) + 1)
            if hi > lo:
                x[lo:hi] += amp * np.exp(-0.5 * ((t[lo:hi] - c) / wid) ** 2)
    x += wander * np.sin(2.0 * math.pi * 0.25 * t + 0.3) + mains * np.sin(2.0 * math.pi * 50.0 * t)
    x += rng.normal(0.0, white, n)
    return x


def regular_r(seconds: float, bpm: float, rsa: float = 0.03, start: float = 0.4) -> list[float]:
    out, tt = [], start
    rr0 = 60.0 / bpm
    while tt < seconds - 0.3:
        out.append(tt)
        tt += rr0 * (1.0 + rsa * math.sin(2.0 * math.pi * 0.25 * tt))
    return out


def atc_bytes(mv: np.ndarray) -> bytes:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "x.atc"
        write_atc(p, mv, fs=ECG_FS, start_time="2026-10-24T10:00:00.000+0530", resolution_nv=ATC_NV,
                  info={"recorder_sw": "SamaHealth onboarding PalmRecorder", "recorder_hw": "synthetic"})
        return p.read_bytes()


def ecg_csv(mv: np.ndarray) -> str:
    rows = ["t_ref_ns,sample_idx,lead1_raw,lead2_raw,lead1_mv,lead2_mv"]
    for i, v in enumerate(mv):
        raw = int(round(v / (10.0 / 65536.0)))
        rows.append(f"{T0_NS + int(round(i * 1e9 / ECG_FS))},{i},{raw},0,{raw * (10.0 / 65536.0):.5f},0.00000")
    return "\n".join(rows) + "\n"


def ecg_signals():
    rng = np.random.default_rng(100)
    cases = []
    r = regular_r(30.0, 75.0)
    clean = ecg_from_r(r, 30.0, rng)
    cases.append(("clean_75bpm", clean, {"level": "good", "hr_bpm": 75.0, "n_beats": len(r), "rhythm": "regular",
                                          "inverted": False}))
    rng = np.random.default_rng(101)
    r = regular_r(30.0, 80.0)
    noisy = ecg_from_r(r, 30.0, rng, white=0.35) + 0.4 * np.sin(2.0 * math.pi * 1.1 * np.arange(9000) / ECG_FS) * \
        rng.normal(0.0, 1.0, 9000)
    cases.append(("noisy", noisy, {"level": "retake", "rhythm": "insufficient"}))
    rng = np.random.default_rng(102)
    r = regular_r(30.0, 70.0)
    flat = ecg_from_r(r, 30.0, rng)
    flat[int(16.0 * ECG_FS):int(28.0 * ECG_FS)] = 0.0             # lead off, zero-filled: 12 of 30 windows flat
    cases.append(("flat_12s", flat, {"level": "retake", "flat_frac": 0.4, "reason_prefix": "Flat line",
                                      "rhythm": "insufficient"}))
    rng = np.random.default_rng(103)
    r = regular_r(30.0, 64.0)
    inv = -ecg_from_r(r, 30.0, rng)
    cases.append(("inverted_64bpm", inv, {"level": "good", "hr_bpm": 64.0, "inverted": True, "rhythm": "regular"}))
    rng = np.random.default_rng(106)            # a draw whose turning points sit inside the random band
    r, tt = [], 0.4
    while tt < 29.7:
        r.append(tt)
        tt += rng.uniform(0.42, 1.05)
    af = ecg_from_r(r, 30.0, rng, p_wave=False) + 0.03 * np.sin(2.0 * math.pi * 6.0 * np.arange(9000) / ECG_FS)
    cases.append(("irregular_rr", af, {"level": "good", "irregular": True, "rhythm": "irregular",
                                       "n_beats": len(r), "rr_ratio_over": 2.2}))
    rng = np.random.default_rng(105)
    r = [t for t in regular_r(30.0, 70.0, rsa=0.02)]
    k = next(i for i, t in enumerate(r) if t > 12.0)
    r = r[:k + 1] + [t + 2.75 for t in r[k + 1:] if t + 2.75 < 29.7]   # one 3.6 s pause
    pause = ecg_from_r(r, 30.0, rng)
    cases.append(("pause_3p6s", pause, {"level": "borderline", "rr_max_s": 60.0 / 70.0 + 2.75,
                                        "reason_prefix": "Long gap between beats", "rhythm": "regular"}))
    rng = np.random.default_rng(106)
    r = regular_r(15.0, 90.0)
    short = ecg_from_r(r, 15.0, rng)
    cases.append(("short_15s", short, {"level": "retake", "reason_prefix": "ECG too short", "rhythm": "insufficient"}))
    return cases


def ecg_fixtures() -> tuple[list[dict], bytes]:
    out = []
    clean_atc = b""
    for name, mv, known in ecg_signals():
        blob = atc_bytes(mv)
        tr = onsite.read_atc(blob)
        gr = onsite.score_ecg(tr.mv, tr.fs)
        sm = onsite.summarise_ecg(tr.mv, tr.fs)
        m = gr.metrics
        assert gr.level == known["level"], (name, gr.level, gr.reasons, m)
        if "reason_prefix" in known:
            assert gr.reasons and gr.reasons[0].startswith(known["reason_prefix"]), (name, gr.reasons)
        if "hr_bpm" in known:
            assert abs(m["hr_bpm"] - known["hr_bpm"]) < 1.5, (name, m["hr_bpm"])
        if "n_beats" in known:
            assert m["n_beats"] == known["n_beats"], (name, m["n_beats"], known["n_beats"])
        if "inverted" in known:
            assert sm.inverted == known["inverted"], (name, sm.inverted)
        if "irregular" in known:
            assert (m["irregular_flag"] == 1.0) == known["irregular"], (name, m)
        if "flat_frac" in known:
            assert abs(m["flat_frac"] - known["flat_frac"]) < 0.034, (name, m["flat_frac"])
        if "rr_ratio_over" in known:
            assert m["rr_ratio"] > known["rr_ratio_over"] and not gr.reasons, (name, m["rr_ratio"], gr.reasons)
        if "rr_max_s" in known:
            assert abs(m["rr_max_s"] - known["rr_max_s"]) < 0.05, (name, m["rr_max_s"])
        assert sm.rhythm == known["rhythm"], (name, sm.rhythm)
        case = {"name": name, "known": known, "atc_b64": base64.b64encode(blob).decode("ascii"),
                "expected": {"level": gr.level, "reasons": gr.reasons, "metrics": clean_metrics(m)},
                "summary": {"hr_bpm": sm.hr_bpm, "rhythm": sm.rhythm, "inverted": sm.inverted,
                            "n_beats": sm.n_beats, "rr_min_s": sm.rr_min_s, "rr_max_s": sm.rr_max_s,
                            "irregular_flag": sm.irregular_flag, "sentences": sm.sentences}}
        if name == "clean_75bpm":
            clean_atc = blob
            csv_text = ecg_csv(tr.mv)
            mv2, fs2 = onsite.parse_ecg_csv(csv_text)
            g2 = onsite.score_ecg(mv2, fs2)
            assert g2.level == "good" and abs(fs2 - ECG_FS) < 1e-3
            case["csv_gz_b64"] = gz64(csv_text)
            case["csv_expected"] = {"fs": fs2, "n": int(mv2.size), "level": g2.level, "reasons": g2.reasons,
                                    "metrics": clean_metrics(g2.metrics)}
        out.append(case)
        print(f"ecg   {name:20s} {gr.level:10s} {sm.rhythm:12s} {gr.reasons}")
    return out, clean_atc


# --------------------------------------------------------------------------- Kardia-like PDF
def render_kardia_like_pdf(path: Path, mv: np.ndarray, bpm_text: int, r_idx) -> dict:
    """US-Letter page laid out like a Kardia 1-lead export: 4 strips of 8 s, 60 mm apart, 0.2362 pt per sample,
    1 mV x 0.2 s calibration pulse before strip 1, beat ticks under the strips, 1 s grid and black baselines."""
    from reportlab.pdfgen import canvas

    mm = onsite.MM
    dx = 25.0 * mm / ECG_FS
    left, width = 22.53543, 200.0 * mm
    base_y = [792.0 - 164.0467 - i * 60.0 * mm for i in range(4)]       # baselines, y up
    per_strip = int(round(8.0 * ECG_FS))
    from reportlab import rl_config

    rl_config.useA85 = 0                                                # plain /FlateDecode, as Kardia writes it
    c = canvas.Canvas(str(path), pagesize=(612.0, 792.0), invariant=1, pageCompression=1)
    c.setTitle("Synthetic Kardia-like strip")
    c.setFont("Helvetica", 8)
    c.drawString(132.6, 765.0, "Patient: Synthetic Test")
    c.drawString(452.4, 765.0, f"Heart Rate: {bpm_text} BPM")
    c.drawString(452.4, 755.0, "Duration: 30s")
    c.drawString(132.6, 743.0, "Kardia Determination:")
    c.drawString(213.8, 743.0, "Normal Sinus Rhythm")
    c.drawString(376.8, 715.0, "Enhanced Filter, Mains Frequency: 50Hz    Scale: 25mm/s, 10mm/mV")
    c.setStrokeColorRGB(0.5, 0.5, 0.5)
    c.setLineWidth(0.3)
    for s in range(1, 8):                                               # 1 s grid lines
        x = left + s * 25.0 * mm
        c.line(x, 32.68, x, 712.99)
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(0.4)
    c.rect(left, 32.68, width, 680.31, stroke=1, fill=0)
    for y in base_y:
        c.line(left, y, left + width, y)
    c.setLineWidth(1.5)                                                 # calibration pulse: 1 mV x 0.2 s
    p = c.beginPath()
    p.moveTo(left + 2.5 * mm, base_y[0])
    p.lineTo(left + 5.0 * mm, base_y[0])
    p.lineTo(left + 5.0 * mm, base_y[0] + 10.0 * mm)
    p.lineTo(left + 10.0 * mm, base_y[0] + 10.0 * mm)
    p.lineTo(left + 10.0 * mm, base_y[0])
    p.lineTo(left + 12.5 * mm, base_y[0])
    c.drawPath(p, stroke=1, fill=0)
    c.setLineWidth(0.4)
    c.setLineJoin(1)
    first = int(round(0.5 * ECG_FS))                                    # strip 1 starts after the 0.5 s pulse
    pos = 0
    strip_of = []
    for s in range(4):
        k0 = first if s == 0 else 0
        n_here = min(per_strip - k0, mv.size - pos)
        idx = np.arange(n_here)
        xs = left + (k0 + idx) * dx
        ys = base_y[s] + mv[pos:pos + n_here] * 10.0 * mm
        for a in range(0, n_here - 1, 127):                              # Kardia-style chunks sharing endpoints
            b = min(n_here, a + 128)
            p = c.beginPath()
            p.moveTo(xs[a], ys[a])
            for j in range(a + 1, b):
                p.lineTo(xs[j], ys[j])
            c.drawPath(p, stroke=1, fill=0)
        strip_of.append((pos, pos + n_here, k0, s))
        pos += n_here
    c.setLineWidth(1.0)                                                 # beat ticks under each strip
    for ri in r_idx:
        for a, b, k0, s in strip_of:
            if a <= ri < b:
                x = left + (k0 + ri - a) * dx
                c.line(x, base_y[s] - 85.0, x, base_y[s] - 87.8)
    c.showPage()
    c.save()
    return {"n": int(pos)}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    note = ("Synthetic signals only (no participant data). Generated by tools/make_quality_fixtures.py; "
            "thresholds are the PROVISIONAL defaults of palmppg/quality/onsite.py.")
    video = video_fixtures()
    (OUT / "video_cases.json").write_text(json.dumps({"version": 1, "note": note, "cases": video}, indent=1) + "\n")
    ecg, clean_atc = ecg_fixtures()
    (OUT / "ecg_cases.json").write_text(json.dumps({"version": 1, "note": note, "cases": ecg}, indent=1) + "\n")

    truth = onsite.read_atc(clean_atc)
    r_idx = onsite.detect_qrs(truth.mv, truth.fs)
    pdf_path = OUT / "kardia_synthetic.pdf"
    info = render_kardia_like_pdf(pdf_path, truth.mv, 75, r_idx)
    tr = onsite.read_kardia_pdf(pdf_path)
    err = float(np.max(np.abs(tr.mv - truth.mv))) if tr.mv.size == truth.mv.size else float("inf")
    assert tr.mv.size == info["n"] == truth.mv.size == 9000, (tr.mv.size, info)
    assert tr.fs == 300.0 and err < 0.002, (tr.fs, err)
    assert tr.determination == "Normal Sinus Rhythm" and tr.hr_bpm == 75 and tr.mains_hz == 50
    assert tr.enhanced_filter is True and tr.warnings == [], tr.warnings
    gr = onsite.score_ecg(tr.mv, tr.fs)
    kardia = {"version": 1, "note": note, "pdf": pdf_path.name, "truth_case": "clean_75bpm",
              "max_abs_err_mv": 0.002, "observed_max_abs_err_mv": err,
              "expected": {"n": int(tr.mv.size), "fs": tr.fs, "determination": tr.determination,
                           "hr_bpm": tr.hr_bpm, "mains_hz": tr.mains_hz, "enhanced_filter": tr.enhanced_filter,
                           "warnings": tr.warnings, "first_mv": [float(v) for v in tr.mv[:5]],
                           "grade": {"level": gr.level, "reasons": gr.reasons, "metrics": clean_metrics(gr.metrics)}}}
    (OUT / "kardia_pdf.json").write_text(json.dumps(kardia, indent=1) + "\n")
    print(f"kardia pdf: {tr.mv.size} samples, max error {err:.5f} mV, {gr.level} {gr.reasons}, "
          f"{pdf_path.stat().st_size} bytes")


if __name__ == "__main__":
    main()
