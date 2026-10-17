"""Foundation-model embedder interfaces: no weights -> FileNotFoundError; random init is labelled (E10)."""
import numpy as np
import pytest

from palmppg.core.config import rng
from palmppg.core.tracks import FeatureRegistry, TrackViolation
from palmppg.models import fm

SMALL = {"n_block": 2, "base_filters": 4, "n_classes": 8}


def test_missing_weights_raise_with_instructions(tmp_path):
    for name in ("papagei_s", "siamquality"):
        with pytest.raises(FileNotFoundError) as e:
            fm.load_embedder(name, None)
        assert fm.EMBEDDER_SPECS[name].source_url in str(e.value) and "randominit" in str(e.value)
        with pytest.raises(FileNotFoundError):
            fm.load_embedder(name, tmp_path / "missing.pt")
    with pytest.raises(KeyError):
        fm.load_embedder("other", None)
    assert fm.EMBEDDER_SPECS["papagei_s"].segment_samples == 1250
    assert fm.EMBEDDER_SPECS["siamquality"].segment_samples == 3000


def test_resample_and_segment_ground_truth():
    fs_in, fs_out = 30.0, 125.0
    t = np.arange(0, 20, 1 / fs_in)
    x = np.sin(2 * np.pi * 1.0 * t)
    y = fm.resample_to(x, fs_in, fs_out)
    assert abs(len(y) - len(x) * fs_out / fs_in) <= 2
    spec = np.abs(np.fft.rfft(y))
    assert np.fft.rfftfreq(len(y), 1 / fs_out)[np.argmax(spec[1:]) + 1] == pytest.approx(1.0, abs=0.1)
    assert np.array_equal(fm.resample_to(x, 30.0, 30.0), x)
    with_nan = x.copy()
    with_nan[10:15] = np.nan
    assert np.isfinite(fm.resample_to(with_nan, 30.0, 125.0)).all()
    segs = fm.segment(np.arange(1000, dtype=np.float32), 300)
    assert segs.shape == (3, 300) and np.allclose(segs.mean(axis=1), 0, atol=1e-5) and np.allclose(segs.std(axis=1), 1, atol=1e-3)
    assert fm.segment(np.arange(100), 300).shape == (0, 300)
    assert fm.segment(np.arange(1000), 300, hop=100).shape == (8, 300)


def test_column_naming():
    assert fm.feature_columns("phone", method="papagei_s")[0] == "embedding__phone__fused__papagei_s__d000"
    assert fm.feature_columns("pi", "thenar", "siamquality", dim=3)[-1] == "embedding__pi__thenar__siamquality__d002"
    rand = fm.feature_columns("phone", method="randominit", dim=4)
    assert len(rand) == 4 and all("__randominit__" in c for c in rand)
    reg = FeatureRegistry()
    names = fm.register_features(reg, cameras=("pi", "phone"), rois=("fused",), methods=("papagei_s",))
    assert len(names) == 2 * 512 and fm.register_features(reg, cameras=("pi", "phone"), rois=("fused",), methods=("papagei_s",)) == names
    with pytest.raises(TrackViolation):
        reg.check_columns(fm.feature_columns("pi"), "product_candidate")
    reg.check_columns(fm.feature_columns("phone"), "product_candidate")


def test_random_init_embedder_is_labelled_and_deterministic():
    pytest.importorskip("torch")
    g = rng(1, "fm")
    sig = np.sin(2 * np.pi * 1.2 * np.arange(30 * 30) / 30) + 0.1 * g.normal(size=900)
    e = fm.RandomInitEmbedder("papagei_s", seed=0, arch_kwargs=SMALL)
    assert e.random_init and e.method == "randominit" and e.dim == 8
    names = e.feature_names("phone")
    assert len(names) == 8 and all("__randominit__" in c for c in names)
    E = e.embed(sig, 30.0)
    assert E.shape == (3, 8) and np.isfinite(E).all()                 # 30 s -> three 10 s segments
    assert np.array_equal(E, fm.RandomInitEmbedder("papagei_s", seed=0, arch_kwargs=SMALL).embed(sig, 30.0))
    assert not np.allclose(E, fm.RandomInitEmbedder("papagei_s", seed=1, arch_kwargs=SMALL).embed(sig, 30.0))
    assert np.isnan(e.embed_clip(sig[:100], 30.0)).all()
    row = e.embed_row(sig, 30.0, "phone")
    assert list(row.index) == names and np.allclose(row.to_numpy(), E.mean(axis=0), atol=1e-6)
    assert e.embed(sig, 30.0, hop_s=5.0).shape == (5, 8)
    siam = fm.RandomInitEmbedder("siamquality", seed=0, arch_kwargs=SMALL)
    assert siam.embed(np.sin(np.arange(3000) / 10), 100.0).shape == (1, 8)


def test_user_weights_round_trip(tmp_path):
    torch = pytest.importorskip("torch")
    g = rng(2, "fm2")
    sig = np.sin(2 * np.pi * 1.0 * np.arange(600) / 30) + 0.1 * g.normal(size=600)
    e = fm.RandomInitEmbedder("papagei_s", seed=3, arch_kwargs=SMALL)
    path = tmp_path / "papagei_s.pt"
    sd = dict(e.module.state_dict())
    sd["experts.0.weight"] = torch.zeros(2, 2)                       # an extra task head is ignored
    torch.save({"state_dict": sd}, path)
    loaded = fm.load_embedder("papagei_s", path, arch_kwargs=SMALL)
    assert not loaded.random_init and loaded.unexpected_keys_ == ["experts.0.weight"]
    assert loaded.feature_names("phone")[0] == "embedding__phone__fused__papagei_s__d000"
    assert np.allclose(loaded.embed(sig, 30.0), e.embed(sig, 30.0), atol=1e-5)
    partial = {k: v for k, v in e.module.state_dict().items() if not k.startswith("dense")}
    torch.save(partial, tmp_path / "partial.pt")
    with pytest.raises(RuntimeError, match="lacks"):
        fm.load_embedder("papagei_s", tmp_path / "partial.pt", arch_kwargs=SMALL)
    assert fm.load_embedder("papagei_s", tmp_path / "partial.pt", arch_kwargs=SMALL, allow_missing=True).missing_keys_
