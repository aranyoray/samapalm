"""ROI polygons, rasterisation, thumb exclusion, downsampling and the 16 x 24 patch grid (section 6.2)."""
import json

import numpy as np
import pytest

from palmppg.spatial import rois as R
from palmppg.spatial.templates import hand_template_landmarks, transform_landmarks

SHAPE = (864, 1536)


@pytest.fixture(scope="module")
def hand():
    lm = hand_template_landmarks()
    px = R.landmarks_to_px(lm, SHAPE)
    polys = R.roi_polygons(px, SHAPE)
    return polys, R.roi_masks(polys, SHAPE)


def _shoelace(poly):
    x, y = poly[:, 0], poly[:, 1]
    return 0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))


def test_landmarks_to_px_scales_by_width_and_height():
    lm = np.array([[0.5, 0.25, 0.0], [1.0, 1.0, 0.0]])
    px = R.landmarks_to_px(lm, (100, 200))
    assert px.tolist() == [[100.0, 25.0], [200.0, 100.0]]


def test_every_roi_and_the_thumb_are_non_empty(cfg, hand):
    polys, masks = hand
    for name in cfg.get("rois.names"):
        assert name in polys and name in masks, name
        assert masks[name].sum() > 0, name
    assert masks["thumb"].sum() > 0
    assert isinstance(polys["mid_phalanges"], list) and len(polys["mid_phalanges"]) == 4
    assert set(masks) == set(cfg.get("rois.names")) | {"thumb"}


def test_thumb_is_excluded_from_every_pulse_roi(cfg, hand):
    polys, masks = hand
    thumb = masks["thumb"]
    raw = {name: R.rasterise(polys[name], SHAPE) for name in ("thenar", "whole_palm")}
    assert (raw["thenar"] & thumb).any() and (raw["whole_palm"] & thumb).any(), "fixture must overlap the thumb"
    for name in cfg.get("rois.names"):
        assert not (masks[name] & thumb).any(), name
    assert masks["whole_palm"].sum() == raw["whole_palm"].sum() - (raw["whole_palm"] & thumb).sum()


def test_whole_palm_contains_central_palm_and_hull_vertices(hand):
    polys, masks = hand
    assert not (masks["central_palm"] & ~masks["whole_palm"]).any()
    assert masks["whole_palm"].sum() > masks["central_palm"].sum()
    # wrist band and hypothenar ulnar edge are part of the hull
    for p in polys["hypothenar"][2:4]:
        x, y = int(min(p[0], SHAPE[1] - 1)), int(min(p[1], SHAPE[0] - 1))
        assert masks["whole_palm"][max(y - 2, 0):y + 3, max(x - 2, 0):x + 3].any()


def test_band_geometry_width_is_ratio_of_length():
    band = R.segment_band(np.array([10.0, 10.0]), np.array([110.0, 10.0]), 0.6)
    assert band.shape == (4, 2)
    assert _shoelace(band) == pytest.approx(100.0 * 60.0)
    assert np.ptp(band[:, 1]) == pytest.approx(60.0)


def test_rasterise_matches_polygon_area_and_accepts_rings():
    tri = np.array([[10.0, 10.0], [310.0, 10.0], [10.0, 210.0]])
    m = R.rasterise(tri, (300, 400))
    assert m.dtype == bool and m.shape == (300, 400)
    assert abs(m.sum() - _shoelace(tri)) / _shoelace(tri) < 0.02
    a = np.array([[0.0, 0.0], [50.0, 0.0], [50.0, 50.0], [0.0, 50.0]])
    b = a + 100.0
    both = R.rasterise([a, b], (200, 200))
    assert both.sum() == R.rasterise(a, (200, 200)).sum() + R.rasterise(b, (200, 200)).sum()
    assert R.rasterise(np.zeros((0, 2)), (20, 20)).sum() == 0


def test_downsample_mask_takes_every_second_row_and_column():
    rng = np.random.default_rng(0)
    m = rng.random((9, 11)) > 0.5
    d = R.downsample_mask(m)
    assert d.shape == (5, 6)
    assert np.array_equal(d, m[::2, ::2])
    assert R.downsample_mask(m, 1).shape == m.shape


def test_patch_grid_has_rows_times_cols_cells_tiling_the_bbox(hand):
    _, masks = hand
    palm = R.downsample_mask(masks["whole_palm"])
    cells = R.patch_grid(palm, 16, 24)
    assert len(cells) == 16 * 24
    assert [(r, c) for r, c, _ in cells] == [(r, c) for r in range(16) for c in range(24)]
    x0, y0, x1, y1 = R.mask_bbox(palm)
    area = sum((bx1 - bx0) * (by1 - by0) for _, _, (bx0, by0, bx1, by1) in cells)
    assert area == (x1 - x0) * (y1 - y0)
    assert cells[0][2][:2] == (x0, y0) and cells[-1][2][2:] == (x1, y1)
    labels, counts = R.patch_labels(palm, 16, 24)
    assert counts.sum() == palm.sum() and labels.max() == 16 * 24 - 1
    assert (labels[~palm] == -1).all()
    empty = R.patch_grid(np.zeros((10, 10), bool), 2, 3)
    assert len(empty) == 6 and all(b == (0, 0, 0, 0) for _, _, b in empty)


def test_volar_wrist_is_clipped_to_the_image(hand):
    polys, _ = hand
    v = polys["volar_wrist"]
    assert v.shape[0] >= 3
    assert v[:, 0].min() >= 0 and v[:, 0].max() <= SHAPE[1]
    assert v[:, 1].min() >= 0 and v[:, 1].max() <= SHAPE[0]
    assert v[:, 1].max() == pytest.approx(SHAPE[0])


def test_clip_polygon_to_rect_known_area():
    sq = np.array([[-50.0, -50.0], [50.0, -50.0], [50.0, 50.0], [-50.0, 50.0]])
    c = R.clip_polygon_to_rect(sq, 200, 100)
    assert _shoelace(c) == pytest.approx(2500.0)
    assert R.clip_polygon_to_rect(sq + 1000.0, 200, 100).shape == (0, 2)


def test_rotation_keeps_pixel_counts(cfg):
    shape = (1200, 1200)
    base = hand_template_landmarks()
    a = R.roi_masks(R.roi_polygons(R.landmarks_to_px(base, shape), shape), shape)
    rot = transform_landmarks(base, rotate_deg=90.0, centre=(0.5, 0.5))
    b = R.roi_masks(R.roi_polygons(R.landmarks_to_px(rot, shape), shape), shape)
    for name in cfg.get("rois.names"):
        if name == "volar_wrist":
            continue  # clipped against the image border in the unrotated pose
        assert abs(a[name].sum() - b[name].sum()) / a[name].sum() < 0.05, name


def test_rois_json_roundtrip(tmp_path, hand, cfg):
    polys, masks = hand
    payload = R.rois_to_json(polys, masks, frame_idx=42)
    path = R.write_rois_json(tmp_path / "rois.json", payload)
    back = json.loads(path.read_text())
    assert set(back) == set(cfg.get("rois.names")) | {"thumb"}
    assert back["thenar"]["frame_idx"] == 42
    assert back["thenar"]["n_pixels"] == int(masks["thenar"].sum())
    assert len(back["mid_phalanges"]["rings"]) == 4 and back["mid_phalanges"]["polygon"] == back["mid_phalanges"]["rings"][0]
    rebuilt = R.rois_from_json(back)
    assert isinstance(rebuilt["mid_phalanges"], list) and rebuilt["central_palm"].shape == (5, 2)
    assert R.rasterise(rebuilt["central_palm"], SHAPE).sum() == R.rasterise(polys["central_palm"], SHAPE).sum()
