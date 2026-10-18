"""Synthetic palm scene ground truth (palmppg.synth.palm_scene)."""
import numpy as np
import pytest

from palmppg.core.config import rng
from palmppg.synth import palm_scene as ps

def _cfg():
    from palmppg.core.config import load_pipeline_config

    return load_pipeline_config()



@pytest.fixture(scope="module")
def scene():
    cfg = _cfg()
    return ps.make_palm_scene(384, 216, cfg, rng(1, "scene"), melanin=0.0)


def test_region_masks_cover_cfg_rois_and_exclude_thumb(cfg, scene):
    wanted = set(cfg.get("rois.names")) | set(cfg.get("rois.excluded"))
    assert set(scene.region_masks) == wanted
    for name, m in scene.region_masks.items():
        assert m.any(), name
        assert not (m & ~scene.skin_mask).any(), name
    assert not (scene.region_masks["thumb"] & scene.region_masks["whole_palm"]).any()
    assert not (scene.region_masks["thenar"] & scene.region_masks["thumb"]).any()


def test_led_block_never_overlaps_skin_and_thumb_block_changes_at_lift(scene):
    ys, xs = ps.block_slice(scene.led_block)
    assert not scene.skin_mask[ys, xs].any() and not scene.skin_mask_thumb_up[ys, xs].any()
    ys, xs = ps.block_slice(scene.thumb_block)
    assert scene.skin_mask[ys, xs].mean() > 0.1            # thumb rests on the card inside the block
    assert not scene.skin_mask_thumb_up[ys, xs].any()     # and leaves it entirely when lifted
    assert not (scene.skin_mask_thumb_up & ~scene.skin_mask & scene.region_masks["thenar"]).any()


def test_landmarks_in_mediapipe_order_on_the_hand(scene):
    assert scene.landmarks.shape == (21, 2)
    assert np.all(scene.landmarks >= 0) and np.all(scene.landmarks <= 1)
    h, w = scene.height, scene.width
    for i, (u, v) in enumerate(scene.landmarks):
        if ps.LANDMARK_NAMES[i].endswith("TIP"):
            continue
        assert scene.skin_mask[min(int(v * h), h - 1), min(int(u * w), w - 1)], ps.LANDMARK_NAMES[i]
    assert scene.landmarks[12, 1] < scene.landmarks[9, 1] < scene.landmarks[0, 1]   # middle tip above its MCP above the wrist
    assert scene.landmarks[4, 0] < scene.landmarks[0, 0]                           # thumb tip left of the wrist
    rec = ps.landmarks_record(scene, "clip1")
    assert rec["is_left"] and rec["palmar"] and rec["source"] == "synthetic_truth"
    assert all(f"lm{i:02d}_{c}" in rec for i in range(21) for c in "xyz")


def test_perfusion_map_weights(scene):
    means = scene.region_ac_means()
    assert abs(means["thenar"] - 1.0) < 1e-3
    assert all(means[f"pad_{f}"] > 1.0 for f in ("index", "middle", "ring", "little"))
    assert means["volar_wrist"] < 0.5
    assert scene.ac_map[~scene.skin_mask].max() == 0.0


def test_melanin_darkens_blue_most_and_red_least(cfg):
    light = ps.make_palm_scene(192, 108, cfg, rng(1, "s"), melanin=0.0)
    dark = ps.make_palm_scene(192, 108, cfg, rng(1, "s"), melanin=0.4)
    m = light.region_masks["central_palm"]
    ratio = [float(dark.reflectance[..., c][m].mean() / light.reflectance[..., c][m].mean()) for c in range(3)]
    assert ratio[2] < ratio[1] < ratio[0] < 1.0
    assert np.allclose(ratio, np.exp(-0.4 * np.asarray(ps.MELANIN_ABSORPTION)), atol=1e-3)
    assert dark.tone_label == ps.TONE_LABEL and light.tone_label is None


def test_bayer_sampling_positions_and_planes():
    rgb = np.zeros((6, 8, 3), np.float32)
    rgb[..., 0], rgb[..., 1], rgb[..., 2] = 10.0, 20.0, 30.0
    m = ps.mosaic_from_rgb(rgb, "RGGB")
    assert np.all(m[0::2, 0::2] == 10) and np.all(m[0::2, 1::2] == 20) and np.all(m[1::2, 0::2] == 20) and np.all(m[1::2, 1::2] == 30)
    planes = ps.planes_from_mosaic(m, "RGGB")
    assert set(planes) == {"R", "G1", "G2", "B"} and planes["R"].shape == (3, 4)
    assert np.all(ps.channel_mosaic((1, 2, 3), 4, 4)[1::2, 1::2] == 3)


def test_sensor_noise_statistics(cfg, scene):
    dc, ac = ps.bayer_dc_ac(scene, 0.006, {"R": 0.5, "G": 1.0, "B": 0.6})
    flat = np.full((200, 200), 400.0, np.float32)
    dn = ps.add_sensor_noise(flat, scene.sensor, rng(1, "n")).astype(float) - scene.sensor["black_level"]
    expected_sd = np.sqrt(400.0 / scene.sensor["e_per_dn"] + scene.sensor["read_noise_dn"] ** 2)
    assert abs(dn.mean() - 400.0) < 0.5 and abs(dn.std() - expected_sd) / expected_sd < 0.1
    th = scene.region_masks["thenar"]
    # G-plane AC/DC averaged over thenar pixels is the injected value (the AC map is normalised to mean 1 there;
    # a brightness-weighted sum over all four Bayer channels is a different quantity)
    gpos = np.zeros_like(th)
    gpos[0::2, 1::2] = True
    gpos[1::2, 0::2] = True
    sel = th & gpos & (dc > 0)
    assert abs(np.mean(ac[sel] / dc[sel]) / 0.006 - 1.0) < 0.02
    assert dc.max() < scene.sensor["white_level"] - scene.sensor["black_level"]


def test_scale_block_keeps_even_coordinates(cfg):
    b = ps.scale_block({"x": 8, "y": 8, "w": 32, "h": 32}, 384, 216)
    assert b["x"] % 2 == 0 and b["w"] >= 8 and b["h"] >= 8
    full = ps.scale_block(cfg.get("sync.thumb_block.pi"), 1536, 864)
    assert full == {"x": 32, "y": 700, "w": 300, "h": 150}
