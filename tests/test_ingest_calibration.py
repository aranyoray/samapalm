"""Unit calibration: a synthetic vignette is removed to within the configured residual; fallback without files."""
from __future__ import annotations

import json

import numpy as np
import pytest

from palmppg.core.config import rng
from palmppg.ingest.bayer import BayerClipReader, pack_csi2p_10bit, split_planes
from palmppg.ingest.calibration import (
    UnitCalibration,
    aperture_mask_from_flat,
    central_region_slices,
    vignetting_residual_by_plane,
    vignetting_residual_pct,
)
from tests.test_ingest_helpers import (
    BLACK,
    make_mosaic,
    vignette_map,
    write_synthetic_pi_clip,
    write_unit_calibration,
)

W, H = 192, 108


def test_central_region_slices():
    rs, cs = central_region_slices((100, 40), 0.5)
    assert (rs.start, rs.stop) == (25, 75) and (cs.start, cs.stop) == (10, 30)


def test_vignette_removed_within_residual_limit(tmp_path, cfg):
    unit = tmp_path / "unit_01"
    truth = write_unit_calibration(unit, W, H, strength=0.35)
    clip = write_synthetic_pi_clip(tmp_path / "pi", n_frames=3, width=W, height=H, strength=0.35)
    meta = clip["meta"]
    cal = UnitCalibration.load(unit, meta, black_level=cfg.get("pi.black_level"))
    assert cal.applied and cal.luxmap is not None and cal.unit_id == "unit_01"
    reader = BayerClipReader(clip["raw"], meta)
    raw = reader.frame(0)
    # before correction the vignette is far above the limit; after it is below
    before = vignetting_residual_pct({k: v.astype(np.float32) - BLACK for k, v in raw.items()})
    assert before > 20.0
    corr = cal.apply(raw)
    assert all(v.dtype == np.float32 for v in corr.values())
    limit = float(cfg.get("qc.vignetting_residual_pct_max"))
    after = vignetting_residual_pct(corr)
    assert after < limit, f"residual {after:.2f} % not below {limit} %"
    # corrected level equals the true plane level times the central-region mean of the illumination profile
    # (CONTRACTS 3.1: flat_norm is divided by its central-region mean), within 1 %
    rs, cs = central_region_slices(truth["vignette"].shape, 0.5)
    centre_gain = float(truth["vignette"][rs, cs].mean())
    assert 0.9 < centre_gain < 1.0
    for k, lv in clip["levels"].items():
        assert abs(float(np.median(corr[k])) - lv * centre_gain) / lv < 0.01
    # the flat field corrected by itself is flat
    flat_corr = cal.corrected_flat()
    assert vignetting_residual_pct(flat_corr, aperture_mask_from_flat(cal.flat_norm["G1"])) < 0.5
    per_plane = vignetting_residual_by_plane(corr)
    assert set(per_plane) == {"R", "G1", "G2", "B"}
    s = cal.summary()
    assert s["calibration_applied"] and s["flat_vignetting_pct_uncorrected"] > 20.0
    assert abs(s["dark_mean"]["R"] - BLACK) < 1.0
    assert abs(truth["strength"] - 0.35) < 1e-9
    reader.close()


def test_stack_apply_matches_single(tmp_path, cfg):
    unit = tmp_path / "unit_01"
    write_unit_calibration(unit, W, H)
    clip = write_synthetic_pi_clip(tmp_path / "pi", n_frames=4, width=W, height=H)
    cal = UnitCalibration.load(unit, clip["meta"], black_level=cfg.get("pi.black_level"))
    reader = BayerClipReader(clip["raw"], clip["meta"])
    _ids, planes = next(reader.iter_chunks(chunk=4))
    stacked = cal.apply(planes)
    single = cal.apply(reader.frame(2))
    np.testing.assert_allclose(stacked["B"][2], single["B"])
    reader.close()


def test_no_calibration_subtracts_black_level(tmp_path, cfg):
    clip = write_synthetic_pi_clip(tmp_path / "pi", n_frames=1, width=W, height=H, strength=0.0)
    cal = UnitCalibration.load(tmp_path / "missing_unit", clip["meta"], black_level=cfg.get("pi.black_level"))
    assert not cal.applied
    assert cal.summary()["calibration_applied"] is False
    reader = BayerClipReader(clip["raw"], clip["meta"])
    corr = cal.apply(reader.frame(0))
    assert abs(float(np.median(corr["G1"])) - clip["levels"]["G1"]) < 2.0
    none = UnitCalibration.load(None, clip["meta"], black_level=cfg.get("pi.black_level"))
    assert not none.applied and none.corrected_flat() is None
    reader.close()


def test_full_sensor_frames_cropped_by_crop_rect(tmp_path, cfg):
    gen = rng(3, "crop")
    sw, sh = 128, 64
    rect = {"x": 32, "y": 16, "w": 64, "h": 32}
    vig = vignette_map(sh // 2, sw // 2, 0.3)
    flat_full = make_mosaic({"R": 500, "G1": 600, "G2": 600, "B": 400}, sh, sw, vig, gen)
    dark_full = make_mosaic({"R": 0, "G1": 0, "G2": 0, "B": 0}, sh, sw, None, gen, noise_sd=0.5)
    unit = tmp_path / "unit"
    unit.mkdir()
    (unit / "flatfield.raw").write_bytes(pack_csi2p_10bit(flat_full))
    (unit / "darkframe.raw").write_bytes(pack_csi2p_10bit(dark_full))
    meta = {"width": rect["w"], "height": rect["h"], "bayer_pattern": "RGGB", "crop_rect": rect, "unit_id": "unit_09"}
    cal = UnitCalibration.load(unit, meta, black_level=cfg.get("pi.black_level"), sensor_size=(sw, sh))
    assert cal.applied and cal.flat_norm["R"].shape == (rect["h"] // 2, rect["w"] // 2)
    # the cropped flat equals the direct crop of the full flat
    crop = flat_full[rect["y"]: rect["y"] + rect["h"], rect["x"]: rect["x"] + rect["w"]]
    planes = split_planes(crop)
    fd = planes["R"].astype(np.float32) - split_planes(dark_full[rect["y"]: rect["y"] + rect["h"], rect["x"]: rect["x"] + rect["w"]])["R"]
    rs, cs = central_region_slices(fd.shape, 0.5)
    np.testing.assert_allclose(cal.flat_norm["R"], fd / fd[rs, cs].mean(), rtol=1e-5)
    # wrong geometry raises
    bad_meta = dict(meta, width=48, height=32, crop_rect={"x": 0, "y": 0, "w": 64, "h": 32})
    with pytest.raises(ValueError):
        UnitCalibration.load(unit, bad_meta, black_level=64, sensor_size=(sw, sh))


def test_bad_flat_raises_and_luxmap_tolerated(tmp_path, cfg):
    unit = tmp_path / "unit"
    unit.mkdir()
    zero = np.full((H, W), BLACK, np.uint16)
    (unit / "flatfield.raw").write_bytes(pack_csi2p_10bit(zero))
    (unit / "luxmap.json").write_text("not json")
    meta = {"width": W, "height": H, "bayer_pattern": "RGGB"}
    with pytest.raises(ValueError):
        UnitCalibration.load(unit, meta, black_level=cfg.get("pi.black_level"))
    (unit / "luxmap.json").write_text(json.dumps({"lux_grid": [[1]], "rows": 1, "cols": 1}))
    write_unit_calibration(unit, W, H, luxmap=False)
    cal = UnitCalibration.load(unit, meta, black_level=cfg.get("pi.black_level"))
    assert cal.luxmap == {"lux_grid": [[1]], "rows": 1, "cols": 1}
