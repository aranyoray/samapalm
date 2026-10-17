"""End-to-end ingest orchestrators on a synthetic participant: Pi raw clip with drops and flicker, phone mp4."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from palmppg.core.config import rng
from palmppg.core.paths import ParticipantPaths, WorkLayout
from palmppg.core.timeline import ClockMap
from palmppg.ingest.bayer import open_proxy
from palmppg.ingest.qc import QC_KEYS, read_qc_table
from palmppg.ingest.run import ingest_phone, ingest_pi
from tests.test_ingest_helpers import (
    FFMPEG,
    render_mp4,
    textured_frame,
    write_synthetic_pi_clip,
    write_unit_calibration,
)

W, H = 192, 108
N = 240  # 8 s at 30 fps keeps the test fast while leaving room for the 10 Hz flicker test
DROPPED = (30, 31, 100)
HAND = {"hand_detected": True, "hand_is_left": True, "hand_palmar": True, "landmark_source": "mediapipe",
        "landmark_jitter_px": 0.5, "motion_flag": False}


def _participant(tmp_path, flicker=False):
    root = tmp_path / "study" / "participants" / "SWHT-PP-003-0001"
    mod = (lambda i: 1.0 + 0.01 * np.sin(2 * np.pi * 10.0 * i / 30.0)) if flicker else None
    clip = write_synthetic_pi_clip(root / "pi", n_frames=N, width=W, height=H, dropped=DROPPED, strength=0.3, modulation=mod)
    unit = tmp_path / "study" / "units" / "unit_01"
    write_unit_calibration(unit, W, H, strength=0.3)
    return ParticipantPaths("SWHT-PP-003-0001", root), unit, clip


def test_ingest_pi_end_to_end(tmp_path, cfg):
    pp, unit, clip = _participant(tmp_path)
    work = WorkLayout(tmp_path / "work")
    res = ingest_pi(pp, "clip1", unit, work, cfg, hand_summary=HAND, sync_grade="fine", sqi_best=0.8, write_pi_proxy=FFMPEG is not None)
    assert res["n_frames"] == N - len(DROPPED) and res["t0_ref_ns"] == clip["t0_ns"]
    cam = work.camera("SWHT-PP-003-0001", "clip1", "pi")
    ft = pd.read_parquet(cam / "frame_times.parquet")
    assert len(ft) == N - 3 and int(ft["dropped_before"].sum()) == 3
    assert abs(res["drops"]["drop_pct"] - 100.0 * 3 / N) < 0.05 and res["drops"]["drop_flag"] is False
    z = open_proxy(cam / "proxy_128x72.zarr")
    assert z.shape == (N - 3, 72, 128, 3) and len(z.attrs["t_ref_s"]) == N - 3 and z.attrs["calibration_applied"] is True
    assert z[:].mean() > 20  # not an empty array
    mi = pd.read_parquet(cam / "mean_intensity.parquet")
    assert list(mi.columns) == ["frame_idx", "t_ref_s", "mean_R", "mean_G1", "mean_G2", "mean_B", "mean_G", "sat_frac"]
    # calibrated means equal the injected plane levels (vignette removed) times the central-region mean of the
    # illumination profile (CONTRACTS 3.1 normalisation), within 1 %
    vig = clip["vignette"]
    centre_gain = float(vig[vig.shape[0] // 4: 3 * vig.shape[0] // 4, vig.shape[1] // 4: 3 * vig.shape[1] // 4].mean())
    for k in ("R", "G1", "G2", "B"):
        assert abs(mi[f"mean_{k}"].mean() - clip["levels"][k] * centre_gain) / clip["levels"][k] < 0.01
    # the uncalibrated raw mean (vignette included) is visibly lower than the corrected one
    assert mi["mean_G1"].std() < 1.0  # no modulation injected: frame-to-frame scatter is noise only
    grid = pd.read_parquet(cam / "mean_intensity_grid.parquet")
    assert abs(grid["t_ref_s"].diff().median() - 1 / cfg.get("grid.fs")) < 1e-9
    # NaN on the grid exactly at the grid points that fall strictly inside a drop gap (gap > drop_factor x period)
    tt, gg = ft["t_ref_s"].to_numpy(), grid["t_ref_s"].to_numpy()
    gaps = np.where(np.diff(tt) > cfg.get("qc.drop_factor") / cfg.get("pi.nominal_fps"))[0]
    assert len(gaps) == 2  # frames 30-31 and frame 100
    expected_nan = sum(int(((gg > tt[i]) & (gg < tt[i + 1])).sum()) for i in gaps)
    assert expected_nan >= 3 and grid["mean_G"].isna().sum() == expected_nan
    assert np.isnan(grid["mean_G"].to_numpy()[[30, 31, 100]]).all()
    qc = json.loads((cam / "qc.json").read_text())
    assert tuple(qc.keys()) == QC_KEYS
    assert qc["camera"] == "pi" and qc["valid_clip"] is True and qc["reasons"] == []
    assert qc["vignetting_residual_pct"] < cfg.get("qc.vignetting_residual_pct_max") and qc["vignetting_flag"] is False
    assert qc["saturation_frac"] == 0.0 and qc["flicker_flag"] is False and qc["sync_grade"] == "fine"
    assert qc["eis_warp_px"] is None and qc["sqi_flag"] is False
    ing = json.loads((cam / "ingest.json").read_text())
    assert ing["calibration"]["calibration_applied"] is True and ing["reader"]["n_frames"] == N - 3
    assert ing["colour_space"] == "linear_raw" and "qc" not in ing
    table = read_qc_table(work.tables / "qc_table.parquet")
    assert len(table) == 1 and table["camera"].iloc[0] == "pi"
    if FFMPEG is not None:
        px = res["pi_proxy"]
        assert px["n_frames"] == N - 3 and px["crf"] == cfg.get("phone.proxy_crf")
        pft = pd.read_parquet(work.camera("SWHT-PP-003-0001", "clip1", "pi_proxy") / "frame_times.parquet")
        assert list(pft.columns) == ["frame_idx", "pts_s", "t_ref_s", "dropped_before"]
        np.testing.assert_allclose(pft["t_ref_s"], ft["t_ref_s"])
    # re-running upserts rather than duplicating the qc row
    ingest_pi(pp, "clip1", unit, work, cfg, hand_summary=HAND, sync_grade="coarse", sqi_best=0.2)
    table = read_qc_table(work.tables / "qc_table.parquet")
    assert len(table) == 1 and table["sync_grade"].iloc[0] == "coarse" and table["valid_clip"].iloc[0] == np.False_


def test_ingest_pi_flags_injected_flicker_and_no_calibration(tmp_path, cfg):
    pp, unit, _ = _participant(tmp_path, flicker=True)
    work = WorkLayout(tmp_path / "work")
    res = ingest_pi(pp, "clip1", tmp_path / "no_such_unit", work, cfg, hand_summary=HAND, sqi_best=0.8)
    qc = res["qc"]
    assert qc["flicker_flag"] is True and qc["flicker_peaks_hz"] == [10.0] and qc["reasons"] == ["flicker_flag"]
    assert abs(res["flicker"]["modulation_pct"]["10.0"] - 1.0) < 0.3
    assert res["calibration"]["calibration_applied"] is False and qc["vignetting_residual_pct"] is None
    z = open_proxy(res["paths"]["proxy"])
    assert z.attrs["calibration_applied"] is False
    # without landmarks and SQI the clip cannot be valid, and says why
    res2 = ingest_pi(pp, "clip1", unit, work, cfg)
    assert res2["qc"]["valid_clip"] is False and res2["qc"]["reasons"] == ["hand_detected", "flicker_flag", "sqi_flag"]


@pytest.mark.skipif(FFMPEG is None, reason="ffmpeg not on PATH")
def test_ingest_phone_end_to_end(tmp_path, cfg):
    root = tmp_path / "study" / "participants" / "SWHT-PP-003-0002"
    (root / "phone").mkdir(parents=True)
    gen = rng(5, "phone")
    base = textured_frame(180, 320, gen)
    n = 45
    frames = [np.clip(base.astype(np.float32) * (1.0 + 0.002 * i), 0, 255).astype(np.uint8) for i in range(n)]
    render_mp4(root / "phone" / "clip1.mp4", frames, fps=30.0, crf=18, tone_hz=2500.0, tone_s=n / 30.0)
    (root / "phone" / "clip1_meta.json").write_text(json.dumps({"app": "OpenCamera", "study_id": "SWHT-PP-003-0002", "clip_id": "clip1",
                                                                "fps_nominal": 30, "stabilisation": False}))
    unit = tmp_path / "study" / "units" / "unit_01"
    unit.mkdir(parents=True)
    render_mp4(unit / "phone_flatfield.mp4", [np.full((180, 320, 3), 200, np.uint8)] * 4, fps=30.0, crf=10)
    pp = ParticipantPaths("SWHT-PP-003-0002", root)
    work = WorkLayout(tmp_path / "work")
    cm = ClockMap.fit([0.0, 1.0], [2.5, 3.5], "phone_video", "led_pattern")
    res = ingest_phone(pp, "clip1", unit, work, cfg, clockmap=cm, hand_summary=HAND, sync_grade="fine", sqi_best=0.6, eis_n_sample=8)
    assert res["n_frames"] == n and res["n_frames_decoded"] == n and res["is_vfr"] is False
    cam = work.camera("SWHT-PP-003-0002", "clip1", "phone")
    ft = pd.read_parquet(cam / "frame_times.parquet")
    assert list(ft.columns) == ["frame_idx", "pts_s", "t_ref_s", "dropped_before"]
    assert abs(ft["t_ref_s"].iloc[0] - 2.5) < 1e-6 and int(ft["dropped_before"].sum()) == 0
    z = open_proxy(cam / "proxy_128x72.zarr")
    assert z.shape == (n, 72, 128, 3) and z.attrs["flat_field_applied"] is True and z.attrs["n_frames_decoded"] == n
    mi = pd.read_parquet(cam / "mean_intensity.parquet")
    assert list(mi.columns) == ["frame_idx", "pts_s", "t_ref_s", "mean_R", "mean_G", "mean_B", "sat_frac"]
    assert mi["mean_G"].notna().all() and 0.0 < mi["mean_G"].mean() < 1.0
    qc = res["qc"]
    assert tuple(qc.keys()) == QC_KEYS and qc["camera"] == "phone"
    assert qc["eis_flag"] is False and qc["eis_warp_px"] is not None and qc["eis_warp_px"] < cfg.get("qc.eis_warp_px_max")
    assert qc["valid_clip"] is True and qc["reasons"] == []
    assert qc["lighting_drift_pct"] > 0.0  # the injected brightening ramp has a positive trend
    ing = json.loads((cam / "ingest.json").read_text())
    assert ing["colour_space"] == "inverted_srgb" and ing["linearised_from_srgb"] is True
    assert ing["clockmap"]["method"] == "led_pattern" and ing["clockmap"]["is_identity"] is False
    assert ing["flat_field"]["n_frames_used"] == 4 and ing["reader"]["has_audio"] is True
    table = read_qc_table(work.tables / "qc_table.parquet")
    assert len(table) == 1 and table["camera"].iloc[0] == "phone"
    # identity map without sync is recorded as such; pi_proxy camera label goes through the same path
    res2 = ingest_phone(pp, "clip1", None, work, cfg, camera="pi_proxy", mp4_path=root / "phone" / "clip1.mp4", eis_n_sample=4)
    assert res2["clockmap"]["is_identity"] is True and res2["camera"] == "pi_proxy" and res2["flat_field"] is None
    assert res2["qc"]["valid_clip"] is False and "hand_detected" in res2["qc"]["reasons"]
    assert len(read_qc_table(work.tables / "qc_table.parquet")) == 2
