"""Static colour features with a known R/G ratio, pallor index and spatial variance (section 6.2)."""
import json

import numpy as np
import pandas as pd
import pytest

from palmppg.core.tracks import REGISTRY
from palmppg.spatial.static_colour import (
    CLIP_FEATURES,
    PER_ROI_FEATURES,
    patch_rg,
    register_features,
    static_colour_features,
    write_static_colour_json,
)
from palmppg.spatial.traces import srgb_inverse_lut

ROIS = ["thenar", "central_palm", "whole_palm"]


def _pi_traces(n=90, fs=30.0):
    t = np.arange(n) / fs
    df = pd.DataFrame({"t_ref_s": t, "frame_idx": pd.array(np.arange(n), dtype="Int64")})
    vals = {"thenar": (200.0, 98.0, 102.0, 50.0), "central_palm": (180.0, 98.0, 102.0, 50.0), "whole_palm": (200.0, 98.0, 102.0, 50.0)}
    for roi, (r, g1, g2, b) in vals.items():
        for ch, v in zip(("R", "G1", "G2", "B"), (r, g1, g2, b)):
            col = np.full(n, v)
            col[t >= 2.0] = 999.0                       # outside the window: must not leak in
            df[f"{roi}__{ch}__mean"] = col
            df[f"{roi}__{ch}__median"] = col
        df[f"{roi}__npix"] = 1000.0
        df[f"{roi}__sat_frac"] = 0.0
    df.loc[[10, 11], [c for c in df.columns if c.startswith("whole_palm__")]] = np.nan   # two dropped frames
    return df


def test_pi_features_match_known_ratios():
    df = _pi_traces()
    out = static_colour_features(df, (0.0, 2.0), ROIS, "linear_raw")
    assert out["camera"] == "pi" and out["colour_space"] == "linear_raw" and out["linearised_from_srgb"] is False
    assert out["n_frames_used"] == 58
    th = out["rois"]["thenar"]
    assert th["R_mean"] == 200.0 and th["G_mean"] == 100.0 and th["B_mean"] == 50.0 and th["n_frames"] == 60
    assert th["rg"] == pytest.approx(2.0) and th["bg"] == pytest.approx(0.5)
    assert th["melanin_proxy"] == pytest.approx(np.log(4.0))
    assert out["rois"]["central_palm"]["rg"] == pytest.approx(1.8)
    assert out["central_palm_pallor_index"] == pytest.approx(0.9)
    assert np.isnan(out["spatial_rg_variance"])
    f = out["features"]
    assert f["static_colour__pi__thenar__rg"] == pytest.approx(2.0)
    assert f["static_colour__pi__central_palm_pallor_index"] == pytest.approx(0.9)
    assert f["static_colour__pi__n_frames_used"] == 58.0
    assert set(f) == {f"static_colour__pi__{r}__{n}" for r in ROIS for n in PER_ROI_FEATURES} | {
        f"static_colour__pi__{n}" for n in CLIP_FEATURES}


def test_spatial_variance_from_patch_grid():
    df = _pi_traces()
    t = df["t_ref_s"].to_numpy()
    patches = np.full((90, 2, 2, 4), np.nan, np.float32)
    rg_targets = np.array([[1.0, 2.0], [3.0, np.nan]])
    for r in range(2):
        for c in range(2):
            if np.isnan(rg_targets[r, c]):
                continue
            patches[:, r, c, 0] = 100.0 * rg_targets[r, c]
            patches[:, r, c, 1] = 90.0
            patches[:, r, c, 2] = 110.0
            patches[:, r, c, 3] = 40.0
    patches[t >= 2.0, 0, 0, 0] = 1e6                     # outside the window
    rg = patch_rg(patches[t < 2.0], ["R", "G1", "G2", "B"])
    assert np.allclose(rg[np.isfinite(rg)], [1.0, 2.0, 3.0]) and np.isnan(rg[1, 1])
    out = static_colour_features(df, (0.0, 2.0), ROIS, "linear_raw", patches=patches, patch_t_ref_s=t,
                                 patch_channels=["R", "G1", "G2", "B"])
    assert out["spatial_rg_variance"] == pytest.approx(np.var([1.0, 2.0, 3.0]))
    assert out["features"]["static_colour__pi__spatial_rg_variance"] == pytest.approx(np.var([1.0, 2.0, 3.0]))


def test_phone_inverted_srgb_labelling_and_naming(tmp_path):
    lut = srgb_inverse_lut()
    n = 60
    df = pd.DataFrame({"t_ref_s": np.arange(n) / 30.0, "frame_idx": pd.array(np.arange(n), dtype="Int64")})
    for roi in ("thenar", "whole_palm"):
        for ch, code in zip(("R", "G", "B"), (200, 100, 50)):
            df[f"{roi}__{ch}__mean"] = lut[code]
            df[f"{roi}__{ch}__median"] = lut[code]
        df[f"{roi}__npix"] = 10.0
        df[f"{roi}__sat_frac"] = 0.0
    out = static_colour_features(df, (0.0, 2.0), ["thenar", "whole_palm"], "inverted_srgb")
    assert out["camera"] == "phone" and out["linearised_from_srgb"] is True
    assert out["rois"]["thenar"]["rg"] == pytest.approx(lut[200] / lut[100])
    assert "static_colour__phone__thenar__melanin_proxy" in out["features"]
    assert np.isnan(out["central_palm_pallor_index"])
    out2 = static_colour_features(df, (0.0, 2.0), ["thenar", "whole_palm", "absent"], "inverted_srgb", camera="pi_proxy")
    assert "static_colour__pi_proxy__thenar__rg" in out2["features"] and np.isnan(out2["rois"]["absent"]["rg"])
    path = write_static_colour_json(tmp_path / "static_colour.json", out2)
    back = json.loads(path.read_text())
    assert back["colour_space"] == "inverted_srgb" and back["rois"]["absent"]["rg"] is None
    with pytest.raises(ValueError):
        static_colour_features(df, (0.0, 2.0), ["thenar"], "linear")


def test_non_positive_channels_give_nan_not_errors():
    df = _pi_traces()
    df["thenar__G1__mean"] = 0.0
    df["thenar__G2__mean"] = 0.0
    df["thenar__B__mean"] = -1.0
    out = static_colour_features(df, (0.0, 2.0), ["thenar"], "linear_raw")
    th = out["rois"]["thenar"]
    assert np.isnan(th["rg"]) and np.isnan(th["bg"]) and np.isnan(th["melanin_proxy"])
    empty = static_colour_features(df, (50.0, 52.0), ROIS, "linear_raw")
    assert empty["n_frames_used"] == 0 and np.isnan(empty["rois"]["thenar"]["R_mean"])


def test_register_features_is_idempotent_and_track_aware(cfg):
    names = register_features(cfg)
    names2 = register_features(cfg)
    assert names == names2
    assert len(names) == 3 * (len(cfg.get("rois.names")) * len(PER_ROI_FEATURES) + len(CLIP_FEATURES))
    pi = REGISTRY.get("static_colour__pi__thenar__rg")
    phone = REGISTRY.get("static_colour__phone__thenar__rg")
    proxy = REGISTRY.get("static_colour__pi_proxy__central_palm_pallor_index")
    assert pi.requires_raw is True and pi.camera == "pi" and pi.group == "static_colour" and not pi.requires_ecg
    assert phone.requires_raw is False and proxy.requires_raw is False
    product = set(REGISTRY.columns("product_candidate", groups=["static_colour"]))
    assert "static_colour__phone__thenar__rg" in product and "static_colour__pi_proxy__thenar__rg" in product
    assert "static_colour__pi__thenar__rg" not in product
    assert "static_colour__pi__thenar__rg" in REGISTRY.columns("science", camera="pi", groups=["static_colour"])
    out = static_colour_features(_pi_traces(), (0.0, 2.0), list(cfg.get("rois.names")), "linear_raw")
    assert all(k in REGISTRY for k in out["features"])
