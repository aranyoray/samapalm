"""PDF digitiser on a rendered synthetic Kardia-style strip: R-peak times within 20 ms of the source,
amplitude within 15 %, grid calibration and deskew recovered (protocol 6.4 fallback path)."""
from __future__ import annotations

import numpy as np
import pytest

from palmppg.ecg.clean import clean_ecg
from palmppg.ecg.pdf_digitiser import (
    MM_PER_INCH,
    DigitiserError,
    classify_pixels,
    digitise_pdf,
    grid_bbox,
    line_pitch_px,
    rasterise_pdf,
    render_synthetic_strip_pdf,
)
from palmppg.ecg.rpeaks import detect_rpeaks
from tests.test_ecg_helpers import nearest_offsets

FS = 300


def _source(duration, hr, seed):
    nk = pytest.importorskip("neurokit2")
    return nk.ecg_simulate(duration=duration, sampling_rate=FS, heart_rate=hr, heart_rate_std=1, noise=0.01,
                           random_state=seed)


def _compare(src, dig, cfg):
    n = min(src.size, dig.size)
    cs = clean_ecg(src[:n], FS, cfg=cfg)
    cd = clean_ecg(dig[:n], FS, cfg=cfg)
    rs = detect_rpeaks(cs, FS, cfg=cfg)["idx"]
    rd = detect_rpeaks(cd, FS, cfg=cfg)["idx"]
    off = nearest_offsets(rs, rd)
    amp_ratio = cd[np.clip(rs + off.astype(int), 0, n - 1)] / cs[rs]
    return {"n_src": rs.size, "n_dig": rd.size, "offset_ms": off * 1000.0 / FS, "amp_ratio": amp_ratio,
            "corr": float(np.corrcoef(cs, cd)[0, 1])}


def test_digitised_strip_matches_source_within_tolerances(tmp_path, cfg):
    src = _source(30, 72, 5)
    info = render_synthetic_strip_pdf(tmp_path / "strip.pdf", src, FS, skew_deg=0.6)
    assert info["rows"] == 3 and info["pages"] == 1 and info["row_seconds"] == 10.0
    res = digitise_pdf(tmp_path / "strip.pdf", fs_out=FS)
    assert res["ecg_digitised"] is True and res["fs"] == FS and res["rows_found"] == 3 and res["n_pages"] == 1
    y = res["samples_mv"]
    assert y.dtype == np.float32 and abs(y.size - src.size) <= 2 and np.isfinite(y).all()
    cal = res["calibration"]
    expected_ppm = cal["dpi"] / MM_PER_INCH
    assert abs(cal["px_per_mm"] / expected_ppm - 1.0) < 0.005                     # grid pitch from the image
    assert abs(abs(cal["skew_deg"][0]) - 0.6) < 0.1                                  # deskew recovered
    assert cal["pitch_basis"] == ["fine"] and cal["speed_mm_s"] == 25.0 and cal["gain_mm_mv"] == 10.0
    assert all(abs(d - 10.0) < 0.02 for d in res["quality"]["row_durations_s"])
    cmp = _compare(src, y, cfg)
    assert cmp["n_src"] == cmp["n_dig"] >= 30
    assert np.max(np.abs(cmp["offset_ms"])) <= 20.0                                   # R-peaks within 20 ms
    assert 0.85 <= np.median(cmp["amp_ratio"]) <= 1.15 and cmp["amp_ratio"].min() > 0.8   # amplitude within 15 %
    assert cmp["corr"] > 0.98
    q = res["quality"]
    assert q["ok"] is True and q["trace_coverage"] > 0.99 and q["gap_frac"] == 0.0 and q["problems"] == []
    assert abs(q["anisotropy"] - 1.0) < 0.01


def test_partial_last_row_and_negative_skew(tmp_path, cfg):
    src = _source(25, 60, 2)
    render_synthetic_strip_pdf(tmp_path / "s.pdf", src, FS, skew_deg=-1.2)
    res = digitise_pdf(tmp_path / "s.pdf", fs_out=FS)
    assert res["rows_found"] == 3 and [r["full"] for r in res["rows"]] == [True, True, False]
    assert abs(res["duration_s"] - (src.size - 1) / FS) < 0.02
    assert abs(abs(res["calibration"]["skew_deg"][0]) - 1.2) < 0.1
    cmp = _compare(src, res["samples_mv"], cfg)
    assert cmp["n_src"] == cmp["n_dig"] and np.max(np.abs(cmp["offset_ms"])) <= 20.0
    assert 0.85 <= np.median(cmp["amp_ratio"]) <= 1.15


def test_two_pages_and_fast_rate(tmp_path, cfg):
    src = _source(60, 110, 13)
    info = render_synthetic_strip_pdf(tmp_path / "two.pdf", src, FS)
    assert info["pages"] == 2 and info["rows"] == 6
    res = digitise_pdf(tmp_path / "two.pdf", fs_out=FS)
    assert res["n_pages"] == 2 and res["rows_found"] == 6 and abs(res["samples_mv"].size - src.size) <= 2
    cmp = _compare(src, res["samples_mv"], cfg)
    assert cmp["n_src"] == cmp["n_dig"] >= 100 and np.max(np.abs(cmp["offset_ms"])) <= 20.0
    assert 0.85 <= np.median(cmp["amp_ratio"]) <= 1.15 and cmp["corr"] > 0.98


def test_pixel_classes_grid_pitch_and_errors(tmp_path):
    src = _source(10, 70, 1)
    render_synthetic_strip_pdf(tmp_path / "one.pdf", src, FS)
    rgb = rasterise_pdf(tmp_path / "one.pdf", 300)[0]
    grid, trace = classify_pixels(rgb)
    assert not (grid & trace).any() and trace.sum() > 1000 and grid.sum() > trace.sum()
    x0, x1, y0, y1 = grid_bbox(grid)
    width_mm = (x1 - x0) / (300 / MM_PER_INCH)
    assert abs(width_mm - 250.0) < 1.0                       # 10 s at 25 mm/s
    pitch = line_pitch_px(grid[y0:y1, x0:x1].sum(axis=0).astype(float))
    assert abs(pitch["pitch_px"] - 300 / MM_PER_INCH) < 0.05 and pitch["n_lines"] == 251
    assert pitch["residual_px"] < 0.5
    assert abs(pitch["first_px"] + x0 - 20.0 * 300 / MM_PER_INCH) < 1.0
    with pytest.raises(ValueError):
        render_synthetic_strip_pdf(tmp_path / "wide.pdf", src, FS, row_seconds=20.0)
    # a page without a grid cannot be digitised
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(tmp_path / "blank.pdf"))
    c.drawString(100, 700, "no strip here")
    c.save()
    with pytest.raises(DigitiserError):
        digitise_pdf(tmp_path / "blank.pdf")
