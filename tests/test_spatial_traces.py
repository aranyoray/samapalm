"""ROI / patch statistics streamed onto the uniform grid with a known DC, AC and drops (section 6.2)."""
import numpy as np
import pandas as pd
import pytest

from palmppg.core.timeline import uniform_grid
from palmppg.spatial import rois as R
from palmppg.spatial.landmarks import _row, landmarks_frame
from palmppg.spatial.stmaps import read_patches_zarr
from palmppg.spatial.templates import hand_template_landmarks
from palmppg.spatial.traces import (
    PI_CHANNELS,
    MaskSchedule,
    MaskSet,
    mask_set_from_landmarks,
    roi_stats,
    run_traces,
    srgb_inverse_lut,
    trace_columns,
)

FULL = (216, 384)
PLANE = (108, 192)
FPS = 30.0
AC_HZ = 1.2
AC_FRAC = 0.01
DC = {"R": 300.0, "G1": 500.0, "G2": 505.0, "B": 200.0}


def _landmark_df(lm_by_time):
    rows = [_row(i, t, {"source": "synthetic", "confidence": 1.0, "is_left": True, "palmar": True, "lm": lm})
            for i, t, lm in lm_by_time]
    return landmarks_frame(rows)


@pytest.fixture(scope="module")
def schedule():
    lm = hand_template_landmarks()
    df = _landmark_df([(i, i / FPS, lm) for i in range(0, 300, 8)])
    return MaskSchedule(df, FULL, plane_scale=2, rows=16, cols=24)


def _fit_amplitude(t, x, hz):
    ok = np.isfinite(x)
    y = x[ok] - x[ok].mean()
    a = np.column_stack([np.sin(2 * np.pi * hz * t[ok]), np.cos(2 * np.pi * hz * t[ok])])
    coef, *_ = np.linalg.lstsq(a, y, rcond=None)
    return float(np.hypot(*coef) / x[ok].mean())


def test_mask_set_from_landmarks_is_in_plane_coordinates(schedule):
    ms = schedule.masks_at(0.0)
    assert ms.shape == PLANE and ms.key == 0
    assert "thumb" not in ms.roi_index and ms.roi_npix["whole_palm"] > ms.roi_npix["central_palm"] > 0
    full = R.roi_masks(R.roi_polygons(R.landmarks_to_px(hand_template_landmarks(), FULL), FULL), FULL)
    assert ms.roi_npix["thenar"] == int(R.downsample_mask(full["thenar"]).sum())
    assert ms.patch_counts.sum() == ms.roi_npix["whole_palm"]
    assert schedule.nearest(0.13) == 0 and schedule.nearest(0.14) == 1 and schedule.nearest(99.0) == len(schedule.t) - 1
    assert schedule.masks_at(0.0) is ms  # cached


def test_roi_stats_known_means_medians_and_saturation():
    shape = (40, 60)
    a = np.zeros(shape, bool)
    a[5:15, 5:25] = True                       # 200 px
    b = np.zeros(shape, bool)
    b[20:30, 30:40] = True                     # 100 px
    planes = {ch: np.full(shape, v, np.float32) for ch, v in DC.items()}
    planes["R"][a] = np.linspace(100, 300, a.sum()).astype(np.float32)   # mean 200, median 200
    planes["G1"][b] = 1000.0                                             # 100 px at the clip level
    planes["G1"][20:30, 30:35] = 1023.0                                  # half of ROI b saturated above
    st = roi_stats(planes, {"a": a, "b": b, "empty": np.zeros(shape, bool)}, white_level=1000.0)
    assert st["a"]["npix"] == 200 and st["a"]["mean"]["R"] == pytest.approx(200.0, abs=1e-3)
    assert st["a"]["median"]["R"] == pytest.approx(200.0, abs=1.0) and st["a"]["mean"]["B"] == 200.0
    assert st["a"]["sat_frac"] == 0.0
    assert st["b"]["sat_frac"] == 1.0                                   # every b pixel reaches white in G1
    st2 = roi_stats(planes, {"b": b}, white_level=1010.0)
    assert st2["b"]["sat_frac"] == pytest.approx(0.5)
    assert st["empty"]["npix"] == 0 and np.isnan(st["empty"]["mean"]["R"]) and np.isnan(st["empty"]["sat_frac"])
    ms = MaskSet({"a": a}, shape, 2, 2)
    assert roi_stats(planes, ms, 1000.0)["a"]["mean"]["R"] == st["a"]["mean"]["R"]
    with pytest.raises(ValueError):
        roi_stats(planes, {"a": a[:20]}, 1000.0)


def test_roi_stats_rgb_frame_with_inverse_srgb():
    lut = srgb_inverse_lut()
    assert lut[0] == 0.0 and lut[255] == pytest.approx(1.0, abs=1e-6)
    assert lut[128] == pytest.approx(((128 / 255 + 0.055) / 1.055) ** 2.4, abs=1e-6)
    rgb = np.zeros((30, 40, 3), np.uint8)
    rgb[..., 0], rgb[..., 1], rgb[..., 2] = 200, 128, 64
    rgb[0:3, :, 2] = 255
    m = np.ones((30, 40), bool)
    st = roi_stats(rgb, {"all": m}, 255.0, transfer="srgb_inverse")["all"]
    assert st["mean"]["R"] == pytest.approx(lut[200], abs=1e-6) and st["median"]["G"] == pytest.approx(lut[128], abs=1e-6)
    assert st["sat_frac"] == pytest.approx(3 / 30)
    raw = roi_stats(rgb, {"all": m}, 255.0)["all"]
    assert raw["mean"]["R"] == 200.0


def _synthetic_frames(schedule, n=300, drop=range(100, 105), region="central_palm", bump=100.0):
    ms = schedule.masks_at(0.0)
    region_mask = np.zeros(PLANE, bool)
    region_mask.ravel()[ms.roi_index[region]] = True
    t = np.arange(n) / FPS

    def gen():
        for i in range(n):
            if i in drop:
                continue
            ac = 1.0 + AC_FRAC * np.sin(2 * np.pi * AC_HZ * t[i])
            planes = {}
            for ch, v in DC.items():
                f = np.full(PLANE, v * ac, np.float32)
                f[region_mask] = (v + bump) * ac
                planes[ch] = f
            yield i, planes

    return gen(), t


def test_run_traces_recovers_dc_ac_and_marks_dropped_frames(schedule, tmp_path):
    frames, t = _synthetic_frames(schedule)
    grid = uniform_grid(0.0, t[-1], FPS)
    times = pd.DataFrame({"frame_idx": np.arange(300), "t_ref_s": t})
    df, patches, info = run_traces(frames, schedule, times, grid, PI_CHANNELS, white_level=1000.0,
                                   patches_path=tmp_path / "patches.zarr")
    assert list(df.columns) == ["t_ref_s", "frame_idx"] + trace_columns(schedule.roi_names or R.DEFAULT_ROI_NAMES, PI_CHANNELS)
    assert len(df) == grid.size == 300 and info["n_frames_placed"] == 295 and info["n_grid_missing"] == 5
    missing = df.index[df["frame_idx"].isna()].tolist()
    assert missing == [100, 101, 102, 103, 104]
    assert df.loc[missing, "central_palm__G1__mean"].isna().all() and df.loc[missing, "central_palm__npix"].isna().all()
    assert df["frame_idx"].dropna().astype(int).tolist() == [i for i in range(300) if not 100 <= i < 105]
    x = df["central_palm__G1__mean"].to_numpy()
    assert np.nanmean(x) == pytest.approx(600.0, rel=1e-3)
    assert np.nanmean(df["thenar__G1__mean"]) == pytest.approx(500.0, rel=1e-3)
    assert np.nanmean(df["thenar__R__median"]) == pytest.approx(300.0, rel=1e-3)
    amp = _fit_amplitude(grid, x, AC_HZ)
    assert abs(amp - AC_FRAC) / AC_FRAC < 0.10
    assert abs(_fit_amplitude(grid, df["whole_palm__B__mean"].to_numpy(), AC_HZ) - AC_FRAC) / AC_FRAC < 0.10
    assert df["whole_palm__npix"].dropna().nunique() == 1 and (df["thenar__sat_frac"].dropna() == 0).all()
    # patches: grid shape, NaN outside the palm, means consistent with the region values
    assert patches.shape == (300, 16, 24, 4) and patches.dtype == np.float32
    ms = schedule.masks_at(0.0)
    empty_cells = (ms.patch_counts == 0).reshape(16, 24)
    assert np.isnan(patches[0][empty_cells]).all() and np.isfinite(patches[0][~empty_cells]).all()
    assert np.isnan(patches[100]).all()
    inside = patches[0][~empty_cells]
    assert inside[:, 1].min() >= 500.0 * 0.99 and inside[:, 1].max() <= 600.0 * 1.01
    arr, attrs = read_patches_zarr(tmp_path / "patches.zarr")
    assert arr.shape == patches.shape and attrs["channels"] == list(PI_CHANNELS) and len(attrs["t_ref_s"]) == 300
    assert np.allclose(arr[0][~empty_cells], patches[0][~empty_cells])


def test_run_traces_follows_the_nearest_landmark_frame():
    lm_a = hand_template_landmarks()
    lm_b = lm_a.copy()
    lm_b[:, 0] += 0.1                                                  # hand shifts right by 0.1 x 384 = 38.4 full-res px
    df_lm = _landmark_df([(0, 0.0, lm_a), (150, 5.0, lm_b)])
    sched = MaskSchedule(df_lm, FULL, plane_scale=2)
    col = np.tile(np.arange(PLANE[1], dtype=np.float32), (PLANE[0], 1))  # pixel value = column index
    planes = {ch: col for ch in PI_CHANNELS}
    n = 300
    t = np.arange(n) / FPS
    grid = uniform_grid(0.0, t[-1], FPS)
    df, _, info = run_traces(((i, planes) for i in range(n)), sched, {i: t[i] for i in range(n)}, grid, PI_CHANNELS, 1e9)
    early = df.loc[df["t_ref_s"] < 2.4, "central_palm__R__mean"].mean()
    late = df.loc[df["t_ref_s"] > 2.6, "central_palm__R__mean"].mean()
    assert late - early == pytest.approx(0.1 * PLANE[1], abs=1.0)
    assert info["mask_keys_used"] == [0, 150]
    assert df["central_palm__npix"].nunique() <= 2


def test_run_traces_static_masks_off_grid_and_contested_slots():
    shape = (20, 30)
    m = np.zeros(shape, bool)
    m[2:10, 3:12] = True
    grid = uniform_grid(0.0, 1.0, 10.0)                                 # 11 slots, 0.1 s apart
    frames = [(0, 0.0), (1, 0.12), (2, 0.09), (3, 0.5), (4, 5.0), (5, 0.26)]
    times = {i: t for i, t in frames}
    planes_of = {i: {"R": np.full(shape, float(i), np.float32), "G": np.full(shape, 1.0, np.float32), "B": np.full(shape, 1.0, np.float32)}
                 for i, _ in frames}
    df, patches, info = run_traces(((i, planes_of[i]) for i, _ in frames), {"roi": m}, times, grid, ["R", "G", "B"], 255.0,
                                   rows=2, cols=3)
    assert info["n_frames_off_grid"] == 1 and info["n_frames_replaced"] == 1 and info["n_frames_placed"] == 4
    assert info["n_frames_no_time"] == 0 and info["n_grid_missing"] == 7
    assert df["frame_idx"].tolist()[:2] == [0, 2] and pd.isna(df["frame_idx"].iloc[2])    # 0.09 beats 0.12 for the 0.1 slot
    assert df["frame_idx"].iloc[3] == 5 and pd.isna(df["frame_idx"].iloc[4]) and df["frame_idx"].iloc[5] == 3
    assert df["roi__R__mean"].iloc[1] == 2.0 and df["roi__R__mean"].iloc[5] == 3.0 and df["roi__npix"].iloc[0] == 72
    assert patches.shape == (11, 2, 3, 3) and np.isnan(patches[2]).all() and np.isfinite(patches[1]).all()
    assert list(df.columns) == ["t_ref_s", "frame_idx"] + trace_columns(["roi"], ["R", "G", "B"])
    with pytest.raises(ValueError):
        run_traces(iter([(0, {"R": np.zeros((5, 5)), "G": np.zeros((5, 5)), "B": np.zeros((5, 5))})]), {"roi": m}, times, grid,
                   ["R", "G", "B"], 255.0)


def test_mask_set_from_landmarks_matches_schedule(schedule):
    ms = mask_set_from_landmarks(hand_template_landmarks(), FULL, 2, 16, 24, key=7)
    ref = schedule.masks_at(0.0)
    assert ms.key == 7 and ms.roi_npix == ref.roi_npix
    assert np.array_equal(ms.patch_counts, ref.patch_counts)
