"""STMap normalisation, NaN handling, CNN image layout and the patches.zarr round trip (section 6.2/6.3)."""
import numpy as np
import pytest

from palmppg.core.config import rng
from palmppg.spatial.stmaps import (
    open_patches_zarr,
    read_patches_zarr,
    stmap_from_patches,
    stmap_from_zarr,
    stmap_images,
    stmap_to_uint8,
    write_patches_zarr,
)


def _patches(t=120, r=2, c=3, ch=2, seed=3):
    g = rng(seed, "stmaps")
    mean = g.uniform(100, 500, size=(r, c, ch))
    std = g.uniform(1, 5, size=(r, c, ch))
    return mean + std * g.standard_normal((t, r, c, ch)), mean, std


def test_zscore_per_patch_has_zero_mean_unit_std_and_row_major_rows():
    p, _, _ = _patches()
    s = stmap_from_patches(p, "per_patch_zscore")
    assert s.shape == (120, 6, 2) and s.dtype == np.float32
    assert np.allclose(s.mean(axis=0), 0.0, atol=1e-5) and np.allclose(s.std(axis=0), 1.0, atol=1e-4)
    row = 1 * 3 + 2
    expected = (p[:, 1, 2, 0] - p[:, 1, 2, 0].mean()) / p[:, 1, 2, 0].std()
    assert np.allclose(s[:, row, 0], expected, atol=1e-4)
    flat = stmap_from_patches(p, "none")
    assert np.allclose(flat[:, row, 1], p[:, 1, 2, 1])
    with pytest.raises(ValueError):
        stmap_from_patches(p, "bogus")
    with pytest.raises(ValueError):
        stmap_from_patches(p[:, :, :, 0], "none")


def test_minmax_maps_each_patch_to_unit_range():
    p, _, _ = _patches()
    s = stmap_from_patches(p, "minmax")
    assert np.allclose(s.min(axis=0), 0.0) and np.allclose(s.max(axis=0), 1.0)
    assert s.min() >= 0.0 and s.max() <= 1.0


def test_nan_cells_and_dropped_frames_are_filled_without_biasing_the_rest():
    p, _, _ = _patches()
    p[:, 0, 0, :] = np.nan                     # a cell outside the palm
    p[50:55] = np.nan                           # dropped frames
    p[:, 1, 1, 0] = 7.0                         # constant patch: zero variance
    s = stmap_from_patches(p, "per_patch_zscore", fill_nan=0.0)
    assert np.isfinite(s).all()
    assert (s[:, 0, :] == 0.0).all() and (s[50:55] == 0.0).all() and (s[:, 4, 0] == 0.0).all()
    keep = np.ones(120, bool)
    keep[50:55] = False
    col = p[keep, 1, 2, 1]
    assert np.allclose(s[keep, 5, 1], (col - col.mean()) / col.std(), atol=1e-4)
    assert abs(s[keep, 5, 1].mean()) < 1e-5
    s2 = stmap_from_patches(p, "minmax", fill_nan=-1.0)
    assert (s2[50:55] == -1.0).all() and s2[keep, 5, 1].min() == pytest.approx(0.0) and s2[keep, 5, 1].max() == pytest.approx(1.0)


def test_images_per_channel_and_uint8_scaling():
    p, _, _ = _patches(t=50, r=4, c=6, ch=3)
    s = stmap_from_patches(p)
    img = stmap_images(s)
    assert img.shape == (3, 24, 50) and img.flags["C_CONTIGUOUS"]
    assert np.array_equal(img[2, 7, :], s[:, 7, 2])
    u = stmap_to_uint8(img[0])
    assert u.dtype == np.uint8 and u.min() == 0 and u.max() == 255
    assert stmap_to_uint8(np.array([[0.0, 0.5, 1.0]]), 0.0, 1.0).tolist() == [[0, 128, 255]]
    with pytest.raises(ValueError):
        stmap_images(p)


def test_patches_zarr_roundtrip_and_windowed_stmap(tmp_path):
    p, _, _ = _patches(t=90, r=16, c=24, ch=4)
    p[:, 0, 0, :] = np.nan
    t = np.arange(90) / 30.0
    path = write_patches_zarr(tmp_path / "patches.zarr", p, ["R", "G1", "G2", "B"], t, attrs={"roi": "whole_palm"}, chunk_frames=32)
    z = open_patches_zarr(path)
    assert z.shape == (90, 16, 24, 4) and z.chunks == (32, 16, 24, 4) and z.dtype == np.float32
    arr, attrs = read_patches_zarr(path)
    assert attrs["channels"] == ["R", "G1", "G2", "B"] and attrs["rows"] == 16 and attrs["cols"] == 24 and attrs["roi"] == "whole_palm"
    assert np.allclose(attrs["t_ref_s"], t) and np.isnan(arr[:, 0, 0, :]).all()
    assert np.allclose(arr[:, 1:, :, :], p[:, 1:, :, :].astype(np.float32))
    s, ts = stmap_from_zarr(path, "per_patch_zscore", t_window=(1.0, 2.0))
    assert s.shape == (30, 384, 4) and ts[0] == pytest.approx(1.0) and ts[-1] == pytest.approx(29 / 30 + 1.0)
    full, _ = stmap_from_zarr(path)
    assert full.shape == (90, 384, 4)
    # overwrite in place with a different length
    write_patches_zarr(path, p[:10], ["R", "G1", "G2", "B"], t[:10])
    assert open_patches_zarr(path).shape[0] == 10
    with pytest.raises(ValueError):
        write_patches_zarr(tmp_path / "bad.zarr", p, ["R"], t)
