"""End-to-end spatial stage on small synthetic Pi and phone clips (sections 6.1, 6.2)."""
import json

import numpy as np
import pandas as pd
import pytest

from palmppg.core.timeline import uniform_grid
from palmppg.spatial.landmarks import LandmarkProvider
from palmppg.spatial.run import CONFIG_DEFAULTS, default_white_level, run_spatial
from palmppg.spatial.stmaps import read_patches_zarr
from palmppg.spatial.templates import hand_template_landmarks
from palmppg.spatial.traces import srgb_inverse_lut

FULL = (216, 384)
PLANE = (108, 192)
FPS = 30.0
SECONDS = 6
N = int(FPS * SECONDS)
DC = {"R": 300.0, "G1": 500.0, "G2": 505.0, "B": 200.0}


@pytest.fixture
def clip(tmp_path):
    t = np.arange(N) / FPS
    lm = hand_template_landmarks()
    frames = [{"frame_idx": i, "lm": (lm + np.array([0.0005 * (i // 8), 0.0, 0.0])).tolist(), "is_left": True, "palmar": True}
              for i in range(0, N, 8)]
    lm_json = tmp_path / "landmarks.json"
    lm_json.write_text(json.dumps({"frames": frames, "static": lm.tolist()}))
    frame_times = pd.DataFrame({"frame_idx": np.arange(N), "t_ref_s": t, "dropped_before": 0})
    dropped = set(range(60, 63))

    def pi_frames():
        for i in range(N):
            if i in dropped:
                continue
            ac = 1.0 + 0.01 * np.sin(2 * np.pi * 1.2 * t[i])
            yield i, {ch: np.full(PLANE, v * ac, np.float32) for ch, v in DC.items()}

    def phone_frames():
        for i in range(N):
            if i in dropped:
                continue
            f = np.zeros((FULL[0], FULL[1], 3), np.uint8)
            f[..., 0], f[..., 1], f[..., 2] = 200, 100, 50
            yield i, f

    def previews():
        for i in range(N):
            yield i, t[i], np.zeros((54, 96, 3), np.uint8)

    return {"t": t, "lm_json": lm_json, "frame_times": frame_times, "pi": pi_frames, "phone": phone_frames,
            "previews": previews, "grid": uniform_grid(0.0, t[-1], FPS), "dropped": dropped}


def test_pi_path_writes_every_artefact_with_known_numbers(cfg, clip, tmp_path):
    out_dir = tmp_path / "work" / "pi"
    summary = run_spatial(out_dir, "pi", clip["pi"], clip["previews"], clip["frame_times"], clip["grid"], cfg,
                          landmark_json=clip["lm_json"], full_res_shape=FULL)
    for name in ("landmarks.parquet", "rois.json", "traces.parquet", "patches.zarr", "static_colour.json", "spatial_summary.json"):
        assert (out_dir / name).exists(), name
    assert summary["hand_detected"] is True and summary["hand_is_left"] is True and summary["hand_palmar"] is True
    assert summary["landmark_source"] == "synthetic" and summary["motion_flag"] is False
    assert summary["landmark_jitter_px"] == pytest.approx(0.0005 * FULL[1], abs=1e-6)   # 0.192 px per landmark frame
    lm = pd.read_parquet(out_dir / "landmarks.parquet")
    assert len(lm) == SECONDS * cfg.get("qc.hand_preview_fps") and (lm["source"] == "synthetic").all()
    rois = json.loads((out_dir / "rois.json").read_text())
    assert set(rois) == set(cfg.get("rois.names")) | {"thumb"}
    assert all(v["n_pixels"] > 0 for v in rois.values()) and rois["thumb"]["frame_idx"] == summary["roi_frame_idx"]
    tr = pd.read_parquet(out_dir / "traces.parquet")
    n_roi = len(cfg.get("rois.names"))
    assert tr.shape == (clip["grid"].size, 2 + n_roi * (2 * 4 + 2))
    assert tr["frame_idx"].isna().sum() == 3 and tr.loc[list(clip["dropped"]), "thenar__G1__mean"].isna().all()
    assert np.nanmean(tr["central_palm__G1__mean"]) == pytest.approx(500.0, rel=1e-3)
    assert np.nanmean(tr["whole_palm__R__median"]) == pytest.approx(300.0, rel=1e-3)
    patches, attrs = read_patches_zarr(out_dir / "patches.zarr")
    assert patches.shape == (clip["grid"].size, 16, 24, 4) and attrs["channels"] == ["R", "G1", "G2", "B"]
    assert attrs["camera"] == "pi" and len(attrs["t_ref_s"]) == clip["grid"].size
    assert np.isnan(patches[60]).all() and np.isfinite(patches[0]).sum() > 0
    sc = json.loads((out_dir / "static_colour.json").read_text())
    assert sc["colour_space"] == "linear_raw" and sc["linearised_from_srgb"] is False
    assert sc["t_window"] == [0.0, cfg.get("window.static_colour_s")]
    assert sc["n_frames_used"] == int(cfg.get("window.static_colour_s") * FPS)
    assert sc["rois"]["thenar"]["rg"] == pytest.approx(300.0 / 502.5, rel=2e-3)
    assert sc["rois"]["thenar"]["melanin_proxy"] == pytest.approx(np.log(300.0 / 200.0), rel=2e-3)
    assert sc["central_palm_pallor_index"] == pytest.approx(1.0, rel=2e-3)
    assert sc["spatial_rg_variance"] == pytest.approx(0.0, abs=1e-6)
    assert sc["features"]["static_colour__pi__whole_palm__bg"] == pytest.approx(200.0 / 502.5, rel=2e-3)
    meta = json.loads((out_dir / "traces_meta.json").read_text())
    assert meta["n_frames_placed"] == N - 3 and meta["white_level"] == default_white_level("pi", cfg)
    assert default_white_level("pi", cfg) == pytest.approx((1023 - 64) * CONFIG_DEFAULTS["qc.saturation_level_frac"])


def test_phone_path_uses_inverted_srgb(cfg, clip, tmp_path):
    out_dir = tmp_path / "work" / "phone"
    summary = run_spatial(out_dir, "phone", clip["phone"], clip["previews"], clip["frame_times"], clip["grid"], cfg,
                          landmark_json=clip["lm_json"], full_res_shape=FULL)
    assert summary["hand_detected"] is True and summary["channels"] == ["R", "G", "B"] and summary["white_level"] == 255.0
    tr = pd.read_parquet(out_dir / "traces.parquet")
    assert tr.shape[1] == 2 + len(cfg.get("rois.names")) * (2 * 3 + 2)
    lut = srgb_inverse_lut()
    assert np.nanmean(tr["thenar__R__mean"]) == pytest.approx(lut[200], abs=1e-6)
    assert (tr["thenar__sat_frac"].dropna() == 0.0).all()
    sc = json.loads((out_dir / "static_colour.json").read_text())
    assert sc["colour_space"] == "inverted_srgb" and sc["linearised_from_srgb"] is True and sc["camera"] == "phone"
    assert sc["rois"]["whole_palm"]["rg"] == pytest.approx(lut[200] / lut[100], rel=1e-5)
    assert "static_colour__phone__whole_palm__rg" in sc["features"]
    patches, attrs = read_patches_zarr(out_dir / "patches.zarr")
    assert patches.shape[-1] == 3 and attrs["colour_space"] == "inverted_srgb"


def test_no_hand_path_still_writes_artefacts(cfg, clip, tmp_path):
    class _Nothing(LandmarkProvider):
        source = "nothing"

        def detect(self, preview, frame_idx):
            return None

    out_dir = tmp_path / "work" / "pi"
    summary = run_spatial(out_dir, "pi", clip["pi"], clip["previews"], clip["frame_times"], clip["grid"], cfg,
                          provider=_Nothing(), fallback=_Nothing(), full_res_shape=FULL)
    assert summary["hand_detected"] is False and summary["landmark_source"] == "none" and summary["n_rois"] == 0
    assert json.loads((out_dir / "rois.json").read_text()) == {}
    tr = pd.read_parquet(out_dir / "traces.parquet")
    assert len(tr) == clip["grid"].size and tr["thenar__G1__mean"].isna().all() and tr["frame_idx"].isna().all()
    patches, _ = read_patches_zarr(out_dir / "patches.zarr")
    assert np.isnan(patches).all()
    sc = json.loads((out_dir / "static_colour.json").read_text())
    assert sc["n_frames_used"] == 0 and sc["rois"]["thenar"]["rg"] is None
    with pytest.raises(ValueError):
        run_spatial(out_dir, "webcam", clip["pi"], clip["previews"], clip["frame_times"], clip["grid"], cfg)
