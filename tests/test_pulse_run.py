"""run_pulse end to end on a temp camera_dir: synthetic traces.parquet (Pi planes and phone RGB), a Timeline,
optional patches.zarr for 2SR; outputs, masks, SQI, fusion and the feature registry (6.3, CONTRACTS 4-5)."""
import json

import numpy as np
import pandas as pd
import pytest

from palmppg.core.config import load_pipeline_config, rng
from palmppg.core.timeline import Timeline
from palmppg.core.tracks import REGISTRY, FeatureRegistry, TrackViolation
from palmppg.pulse.run import (
    PI_CHANNELS,
    RGB_CHANNELS,
    patches_to_pixels,
    register_features,
    roi_rgb,
    run_pulse,
    trace_channels,
    trace_rois,
)
from tests.test_pulse_synth import DC, FS, HR_BPM, pi_planes_from_rgb, synth_traces

SID = "SWHT-PP-003-0001"
ROIS = ("thenar", "hypothenar", "central_palm")


def _timeline():
    tl = Timeline(SID, "clip1", 0)
    tl.add_event("clip_start", 0.0, 0.0, "sync_events.csv")
    tl.add_event("clip_end", 60.0, 0.0, "sync_events.csv")
    tl.add_event("p2_onset", 55.0, 0.033, "pi_video")
    tl.derive_analysis_window(2.0, 5.0, clip_end_s=60.0)
    return tl


def _traces(camera: str, drops=(400, 401, 402)) -> tuple[pd.DataFrame, np.ndarray]:
    base = synth_traces()
    g = rng(21, "roi_noise")
    cols = {"t_ref_s": base["t"], "frame_idx": np.arange(base["t"].size)}
    chans = PI_CHANNELS if camera == "pi" else RGB_CHANNELS
    for roi, scale, noise in (("thenar", 1.0, 0.0), ("hypothenar", 0.9, 0.02), ("central_palm", 1.1, 0.0), ("thumb", 0.5, 0.0)):
        rgb = base["rgb"] * scale * (1 + g.normal(0, noise, base["rgb"].shape))
        planes = pi_planes_from_rgb(rgb) if camera == "pi" else {"R": rgb[:, 0], "G": rgb[:, 1], "B": rgb[:, 2]}
        for ch in chans:
            cols[f"{roi}__{ch}__mean"] = planes[ch]
            cols[f"{roi}__{ch}__median"] = planes[ch]
        cols[f"{roi}__npix"] = np.full(base["t"].size, 1000)
        cols[f"{roi}__sat_frac"] = np.zeros(base["t"].size)
    df = pd.DataFrame(cols)
    for i in drops:
        df.loc[i, [c for c in df.columns if c.endswith("__mean") or c.endswith("__median")]] = np.nan
    return df, base["volume"]


def _write_patches(path, t, volume, rows=4, cols=6):
    import zarr

    g = rng(31, "patches")
    n = t.size
    dcs = DC[[0, 1, 1, 2]] * (1 + 0.3 * g.uniform(-1, 1, (rows, cols, 1)))
    ratios = np.array([0.5, 1.0, 1.0, 0.6]) * 0.005 * (1 + 0.2 * g.uniform(-1, 1, (rows, cols, 1)))
    drift = 0.02 * np.sin(2 * np.pi * 0.3 * t + 0.4)
    arr = dcs[None] * (1 + drift[:, None, None, None] - ratios[None] * volume[:, None, None, None])
    arr = arr + g.normal(0, 0.002, arr.shape) * dcs[None]
    arr[:, 0, 0, :] = np.nan                                   # a cell off the palm
    z = zarr.create_array(store=str(path), shape=arr.shape, chunks=(256, rows, cols, 4), dtype="float32", fill_value=np.nan)
    z[:] = arr.astype(np.float32)
    z.attrs.update({"channels": ["R", "G1", "G2", "B"], "t_ref_s": [float(v) for v in t], "rows": rows, "cols": cols})


@pytest.fixture(scope="module")
def cfg():
    return load_pipeline_config()


@pytest.fixture(scope="module")
def pi_run(tmp_path_factory, cfg):
    cam = tmp_path_factory.mktemp("work") / SID / "clip1" / "pi"
    cam.mkdir(parents=True)
    df, volume = _traces("pi")
    df.to_parquet(cam / "traces.parquet", index=False)
    out = run_pulse(cam, "pi", cfg, _timeline())
    return cam, out, df, volume


def test_outputs_exist_and_columns_follow_the_contract(pi_run, cfg):
    cam, out, df, _ = pi_run
    for name in ("pulse.parquet", "pulse_morph.parquet", "pulse_sqi.json", "pulse_rate.parquet", "pulse_run.json"):
        assert (cam / name).exists()
    pulse = pd.read_parquet(cam / "pulse.parquet")
    methods = cfg.get("pulse.methods")
    expected = {f"{m}__{r}" for m in methods if m != "2SR" for r in ROIS} | {f"{m}__fused" for m in methods} | {"2SR__roi_set"}
    assert set(pulse.columns) == {"t_ref_s"} | expected
    assert not any("thumb" in c for c in pulse.columns)
    assert list(pd.read_parquet(cam / "pulse_morph.parquet").columns) == list(pulse.columns)
    assert len(pulse) == len(df)


def test_values_only_inside_valid_mask(pi_run):
    cam, out, df, _ = pi_run
    pulse = pd.read_parquet(cam / "pulse.parquet")
    t = pulse["t_ref_s"].to_numpy()
    inside = (t >= 2.0) & (t < 55.0)
    for col in ("POS__thenar", "GREEN__central_palm", "2SR__roi_set", "POS__fused"):
        v = pulse[col].to_numpy()
        assert np.isnan(v[~inside]).all()
        assert np.isnan(v[400:403]).all()                                   # dropped frames stay NaN
        keep = inside.copy()
        keep[400:403] = False
        assert np.isfinite(v[keep]).all(), col


def test_sqi_best_fused_and_rates_recover_72_bpm(pi_run, cfg):
    cam, out, df, volume = pi_run
    sqi = json.loads((cam / "pulse_sqi.json").read_text())
    assert sqi["camera"] == "pi" and sqi["requires_raw"] is True and sqi["study_id"] == SID and sqi["ssr_input"] == "roi_means"
    best = sqi["best"]
    assert best in sqi and "__" in best
    for key in (best, "POS__thenar", "CHROM__central_palm", "GREEN__fused"):
        assert abs(sqi[key]["hr_bpm"] - HR_BPM) <= 1.0, key
    # 2SR on the 14 ROI means (the documented fallback when no patch grid exists) estimates its subspace from
    # 14 "pixels" instead of hundreds; it is held to 3 bpm, the patch-grid 2SR path to 1 bpm elsewhere
        assert set(sqi[key]) >= {"sqi", "snr_db", "hr_bpm", "template_corr", "skewness", "kurtosis"}
    assert abs(sqi["2SR__roi_set"]["hr_bpm"] - HR_BPM) <= 3.0
    assert sqi["POS__thenar"]["sqi"] > sqi["POS__hypothenar"]["sqi"]
    assert sqi["fused"]["method"] == best.split("__")[0] and abs(sqi["fused"]["hr_bpm"] - HR_BPM) <= 1.0
    assert best.split("__", 1)[1] in ("whole_palm", "fused") and sqi["selection"]["mode"] == "consensus_sqi"  # D-023
    run = json.loads((cam / "pulse_run.json").read_text())
    w = run["fusion_weights"]["POS"]
    assert sum(w.values()) == pytest.approx(1.0) and w["thenar"] > w["hypothenar"]
    assert run["green_merge"] == "G = (G1 + G2) / 2" and run["n_valid"] == int(((df["t_ref_s"] >= 2) & (df["t_ref_s"] < 55)).sum())
    rate = pd.read_parquet(cam / "pulse_rate.parquet")
    assert rate["t_ref_s"].iloc[0] == pytest.approx(2.0) and rate["t_ref_s"].iloc[-1] <= 55.0
    assert abs(np.nanmedian(rate["bpm_stft"]) - HR_BPM) <= 2.0 and abs(np.nanmedian(rate["bpm_peaks"]) - HR_BPM) <= 2.0
    pulse = pd.read_parquet(cam / "pulse.parquet")
    inside = (pulse["t_ref_s"] >= 2.0) & (pulse["t_ref_s"] < 55.0)
    v = pulse.loc[inside, best].to_numpy()
    ok = np.isfinite(v)
    assert np.corrcoef(v[ok], volume[inside.to_numpy()][ok])[0, 1] > 0.75                 # volume polarity


def test_morph_band_keeps_harmonics(pi_run):
    cam, *_ = pi_run
    from palmppg.pulse.sqi import periodogram

    a = pd.read_parquet(cam / "pulse.parquet")["POS__thenar"].to_numpy()[100:1600]
    b = pd.read_parquet(cam / "pulse_morph.parquet")["POS__thenar"].to_numpy()[100:1600]
    f, pa = periodogram(a, FS)
    _, pb = periodogram(b, FS)
    hi = f > 4.5
    assert pb[hi].sum() / pb.sum() > 3 * pa[hi].sum() / pa.sum()


def test_ssr_uses_patches_when_present(tmp_path, cfg):
    cam = tmp_path / SID / "clip1" / "pi"
    cam.mkdir(parents=True)
    df, volume = _traces("pi")
    df.to_parquet(cam / "traces.parquet", index=False)
    _write_patches(cam / "patches.zarr", df["t_ref_s"].to_numpy(), volume)
    small = cfg.with_overrides({"pulse": {"methods": ["GREEN", "2SR"]}})
    out = run_pulse(cam, "pi", small, _timeline())
    assert out["details"]["ssr_input"] == "patches"
    assert "2SR__whole_palm" in out["pulse"].columns and "2SR__roi_set" not in out["pulse"].columns
    assert abs(out["sqi"]["2SR__whole_palm"]["hr_bpm"] - HR_BPM) <= 1.0
    pix = patches_to_pixels(np.ones((5, 2, 3, 4)) * np.array([1, 2, 4, 8]), ["R", "G1", "G2", "B"])
    assert pix.shape == (5, 6, 3) and np.allclose(pix[0, 0], [1, 3, 8])


def test_phone_rgb_path_and_registry(tmp_path, cfg):
    cam = tmp_path / SID / "clip1" / "phone"
    cam.mkdir(parents=True)
    df, _ = _traces("phone", drops=())
    df.to_parquet(cam / "traces.parquet", index=False)
    assert trace_channels(df.columns) == RGB_CHANNELS and trace_rois(df.columns, RGB_CHANNELS, exclude=["thumb"]) == list(ROIS)
    assert roi_rgb(df, "thenar", RGB_CHANNELS).shape == (1800, 3)
    small = cfg.with_overrides({"pulse": {"methods": ["POS", "GREEN"]}})
    out = run_pulse(cam, "phone", small, _timeline())
    assert out["sqi"]["requires_raw"] is False and abs(out["sqi"]["POS__thenar"]["hr_bpm"] - HR_BPM) <= 1.0
    n1 = register_features(cfg)
    n2 = register_features(cfg)
    assert n1 == n2 > 0
    assert REGISTRY.get("pulse__pi__thenar__POS__hr_bpm").requires_raw is True
    assert REGISTRY.get("pulse__phone__thenar__POS__hr_bpm").requires_raw is False
    assert REGISTRY.get("pulse__pi_proxy__central_palm__2SR__sqi").requires_raw is False
    assert "pulse__pi__whole_palm__2SR__snr_db" in REGISTRY and "pulse__pi__fused__POS__sqi" in REGISTRY
    assert "pulse__phone__best" in REGISTRY and "pulse__phone__fused__hr_bpm" in REGISTRY
    assert REGISTRY.get("pulse__pi__thenar__POS__hr_bpm").units == "bpm"
    reg = FeatureRegistry()
    reg.add("pulse__pi__thenar__POS__hr_bpm", group="pulse", camera="pi", requires_raw=False)
    with pytest.raises(TrackViolation):
        register_features(cfg, registry=reg)


def test_pi_channel_detection_and_green_merge():
    df, _ = _traces("pi", drops=())
    assert trace_channels(df.columns) == PI_CHANNELS
    rgb = roi_rgb(df, "thenar", PI_CHANNELS)
    assert np.allclose(rgb[:, 1], 0.5 * (df["thenar__G1__mean"] + df["thenar__G2__mean"]))


def test_window_too_short_gives_nan_outputs_without_error(tmp_path, cfg):
    cam = tmp_path / SID / "clip1" / "pi"
    cam.mkdir(parents=True)
    df, _ = _traces("pi", drops=())
    df.to_parquet(cam / "traces.parquet", index=False)
    tl = Timeline(SID, "clip1", 0)
    tl.add_event("clip_start", 0.0, 0.0, "x")
    tl.add_event("p2_onset", 3.0, 0.0, "x")
    tl.derive_analysis_window(2.0, 5.0, clip_end_s=60.0)
    small = cfg.with_overrides({"pulse": {"methods": ["POS"]}})
    out = run_pulse(cam, "pi", small, tl, write=False)
    assert out["pulse"]["POS__thenar"].isna().all() and out["sqi"]["POS__thenar"]["sqi"] == 0.0
    assert len(out["pulse_rate"]) == 0
    with pytest.raises(ValueError):
        run_pulse(cam, "webcam", small, tl)


def test_select_best_prefers_consensus_over_isolated_high_sqi(cfg):
    """D-023: an isolated high-SQI candidate at the wrong rate loses to the rate most methods agree on."""
    from palmppg.pulse.run import select_best

    sqi = {"ICA__fused": {"sqi": 0.53, "hr_bpm": 68.1}, "PCA__fused": {"sqi": 0.39, "hr_bpm": 68.1},
           "POS__whole_palm": {"sqi": 0.21, "hr_bpm": 93.2}, "PBV__whole_palm": {"sqi": 0.21, "hr_bpm": 93.2},
           "ICA__whole_palm": {"sqi": 0.20, "hr_bpm": 93.1}, "2SR__whole_palm": {"sqi": 0.36, "hr_bpm": 93.5},
           "POS__fused": {"sqi": 0.35, "hr_bpm": 93.3}, "GREEN__prox_little": {"sqi": 0.90, "hr_bpm": 60.0}}
    best, sel = select_best(sqi, cfg)
    assert best == "2SR__whole_palm" and abs(sel["consensus_hr_bpm"] - 93.2) < 0.5
    best2, _ = select_best(sqi, cfg.with_overrides({"pulse": {"best_selection": "max_sqi"}}))
    assert best2 == "ICA__fused"            # max over the same pre-specified candidates; prox_little is never a candidate
