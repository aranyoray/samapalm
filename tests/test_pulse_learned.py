"""Learned extractors: forward shapes, 2-epoch CPU training reduces the loss on a synthetic video with a
known pulse, participant-grouped split enforcement, dataset target alignment, inference (6.3, 10, 11.1)."""
import json
import time

import numpy as np
import pandas as pd
import pytest

torch = pytest.importorskip("torch")

from palmppg.pulse.learned import MODEL_NAMES, NOT_IMPLEMENTED, build_model  # noqa: E402
from palmppg.pulse.learned.common import NegPearsonLoss, TemporalShift, count_parameters, diff_normalise  # noqa: E402
from palmppg.pulse.learned.dataset import (  # noqa: E402
    ClipDataset,
    ClipRecord,
    SplitViolation,
    assert_participant_disjoint,
    participant_folds,
    split_records,
    synthetic_video_clip,
)
from palmppg.pulse.learned.infer import infer_clip, predict_pulse  # noqa: E402
from palmppg.pulse.learned.train import TrainConfig, evaluate, hr_mae_bpm, train_model  # noqa: E402

T = 32
H, W = 72, 128
torch.set_num_threads(2)


def _kw(name):
    return {"frame_depth": T} if name in ("TSCAN", "EfficientPhys") else {}


@pytest.fixture(scope="module")
def clips():
    out = []
    for i, (hr, seed) in enumerate([(66.0, 1), (84.0, 2), (75.0, 3)]):
        video, pulse = synthetic_video_clip(3 * T, 30.0, hr, seed)
        out.append(ClipRecord(f"SWHT-PP-003-000{i}", video=video, target=pulse, camera="phone"))
    return out


@pytest.fixture(scope="module")
def datasets(clips):
    return ClipDataset(clips[:2], T, T), ClipDataset(clips[2:], T, T)


def test_synthetic_clip_has_known_pulse_in_green():
    video, pulse = synthetic_video_clip(90, 30.0, 72.0, 0)
    assert video.shape == (90, H, W, 3) and video.dtype == np.uint8 and pulse.shape == (90,)
    g = video[:, 30:42, 56:72, 1].astype(float).mean(axis=(1, 2))
    assert np.corrcoef(-g, pulse)[0, 1] > 0.9                                   # intensity falls with volume


@pytest.mark.parametrize("name", MODEL_NAMES)
def test_forward_shape(name):
    m = build_model(name, width=8, **_kw(name))
    x = torch.rand(2, T, 3, H, W)
    if m.input_layout == "NCTHW":
        x = x.permute(0, 2, 1, 3, 4)
    m.eval()
    with torch.no_grad():
        out = m(x)
    assert out.shape == (2, T) and torch.isfinite(out).all()
    assert count_parameters(m) > 0


@pytest.mark.parametrize("name", MODEL_NAMES)
def test_two_epoch_training_reduces_loss(name, datasets):
    train, val = datasets
    m = build_model(name, width=8, **_kw(name))
    t0 = time.time()
    hist = train_model(m, train, val, TrainConfig(epochs=5, batch_size=4, seed=0, lr=1e-3, num_threads=2))
    assert time.time() - t0 < 45.0
    # on six windows the loss after any single epoch is noisy; learning shows as a later epoch below the first
    assert len(hist["train_loss"]) == 5 and min(hist["train_loss"][1:]) < hist["train_loss"][0]
    assert all(np.isfinite(hist["val_loss"])) and hist["n_train_windows"] == 6 and hist["n_val_windows"] == 3
    ev = evaluate(m, val, TrainConfig(num_threads=2))
    assert ev["n_windows"] == 3 and np.isfinite(ev["loss"])


def test_training_is_deterministic_for_a_fixed_seed(datasets):
    train, _ = datasets
    h1 = train_model(build_model("PhysNet", width=4), train, None, TrainConfig(epochs=1, seed=3, num_threads=2))
    h2 = train_model(build_model("PhysNet", width=4), train, None, TrainConfig(epochs=1, seed=3, num_threads=2))
    assert h1["train_loss"] == pytest.approx(h2["train_loss"], rel=1e-5)


def test_split_violation_is_enforced(clips):
    with pytest.raises(SplitViolation):
        train_model(build_model("PhysNet", width=4), ClipDataset(clips[:2], T, T), ClipDataset(clips[1:], T, T), TrainConfig(epochs=1))
    with pytest.raises(SplitViolation):
        assert_participant_disjoint({"a", "b"}, {"b"})
    assert_participant_disjoint({"a"}, {"b"})


def test_participant_folds_cover_each_participant_once(clips):
    ids = [f"P{i}" for i in range(7)]
    folds = participant_folds(ids, 3, seed=1)
    assert len(folds) == 3
    seen = [i for _, val in folds for i in val]
    assert sorted(seen) == ids
    for train, val in folds:
        assert not (train & val) and (train | val) == set(ids)
    assert participant_folds(ids, 3, seed=1) == folds
    tr, va = split_records(clips, {clips[0].study_id})
    assert len(tr) == 2 and len(va) == 1
    with pytest.raises(ValueError):
        participant_folds(ids, 8, seed=1)


def test_dataset_reads_targets_from_pulse_parquet_and_zarr(tmp_path):
    import zarr

    n = 96
    video, pulse = synthetic_video_clip(n, 30.0, 72.0, 5)
    t = np.arange(n) / 30.0
    z = zarr.create_array(store=str(tmp_path / "proxy_128x72.zarr"), shape=video.shape, chunks=(32, H, W, 3), dtype="uint8")
    z[:] = video
    z.attrs.update({"t_ref_s": [float(v) for v in t]})
    col = np.sin(2 * np.pi * 1.2 * t)
    col[80:] = np.nan
    pd.DataFrame({"t_ref_s": t, "POS__thenar": col, "GREEN__thenar": -col}).to_parquet(tmp_path / "pulse.parquet", index=False)
    (tmp_path / "pulse_sqi.json").write_text(json.dumps({"best": "POS__thenar"}))
    rec = ClipRecord("P1", video=tmp_path / "proxy_128x72.zarr", target=tmp_path / "pulse.parquet")
    assert rec.n_frames() == n and rec.frame_times().size == n
    y = rec.load_target()
    assert np.allclose(y[:80], col[:80]) and np.isnan(y[80:]).all()
    ds = ClipDataset([rec], 32, 16)
    assert len(ds) == 4                                   # windows reaching frame 80 or later are skipped (starts 0, 16, 32, 48)
    item = ds[0]
    assert item["x"].shape == (32, 3, H, W) and item["x"].dtype == np.float32 and 0 <= item["x"].max() <= 1
    assert item["y"].shape == (32,) and abs(item["y"].mean()) < 1e-6 and abs(item["y"].std() - 1) < 1e-5
    assert np.corrcoef(item["y"], col[:32])[0, 1] > 0.999
    rec2 = ClipRecord("P1", video=tmp_path / "proxy_128x72.zarr", target=tmp_path / "pulse.parquet", target_column="GREEN__thenar")
    assert np.allclose(rec2.load_target()[:80], -col[:80])
    batch = ClipDataset.collate([ds[0], ds[1]])
    assert tuple(batch["x"].shape) == (2, 32, 3, H, W) and batch["study_id"] == ["P1", "P1"]
    ds_all = ClipDataset([rec], 32, 16, require_target=False)
    assert len(ds_all) == 5


def test_stmap_mode_windows(tmp_path):
    n = 64
    patches = np.random.default_rng(0).normal(size=(n, 4, 6, 3)).astype(np.float32)
    patches[:, 0, 0, :] = np.nan
    rec = ClipRecord("P1", stmap=patches, target=np.sin(np.arange(n) / 5))
    ds = ClipDataset([rec], 32, 32, mode="stmap")
    item = ds[0]
    assert item["x"].shape == (3, 24, 32) and np.isfinite(item["x"]).all()
    assert abs(item["x"][0, 5].mean()) < 1e-5 and abs(item["x"][0, 5].std() - 1) < 1e-4


def test_inference_returns_full_length_pulse_and_rate(clips):
    m = build_model("DeepPhys", width=4)
    res = infer_clip(m, clips[0].video, 30.0, (0.5, 4.0), T, T // 2)
    assert res["pulse"].shape == (3 * T,) and np.isfinite(res["pulse"]).all()
    assert np.isfinite(res["hr_bpm"]) and abs(np.nanmean(res["pulse"])) < 1e-6
    p = predict_pulse(build_model("PhysNet", width=4), clips[0].video, T, T)
    assert p.shape == (3 * T,)


def test_losses_and_layers_ground_truth():
    a = torch.sin(torch.arange(64, dtype=torch.float32) / 4)[None]
    assert float(NegPearsonLoss()(a, a)) == pytest.approx(0.0, abs=1e-6)
    assert float(NegPearsonLoss()(a, -a)) == pytest.approx(2.0, abs=1e-6)
    x = torch.arange(2 * 4 * 3 * 2 * 2, dtype=torch.float32).view(2 * 4, 3, 2, 2)
    s = TemporalShift(4, fold_div=3)(x).view(2, 4, 3, 2, 2)
    xx = x.view(2, 4, 3, 2, 2)
    assert torch.equal(s[:, 1:, 0], xx[:, :-1, 0]) and torch.equal(s[:, :-1, 1], xx[:, 1:, 1]) and torch.equal(s[:, :, 2], xx[:, :, 2])
    assert torch.all(s[:, 0, 0] == 0)
    v = torch.rand(1, 5, 3, 4, 4)
    d = diff_normalise(v)
    assert d.shape == v.shape and torch.all(d[:, 0] == 0)
    pred = np.sin(2 * np.pi * 1.2 * np.arange(300) / 30)[None]
    targ = np.sin(2 * np.pi * 1.0 * np.arange(300) / 30)[None]
    assert abs(hr_mae_bpm(pred, targ, 30.0, (0.5, 4.0)) - 12.0) < 1.0


def test_mamba_models_are_declared_not_implemented():
    assert set(NOT_IMPLEMENTED) == {"PhysMamba", "RhythmMamba"}
    with pytest.raises(NotImplementedError):
        build_model("PhysMamba")
    with pytest.raises(ValueError):
        build_model("Unknown")
