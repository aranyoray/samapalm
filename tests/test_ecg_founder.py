"""ECGFounder runner (design section 9) with randomly initialised weights: no download needed.

Known answers: the published architecture size (about 30.8 M parameters), 30 s at 300 Hz -> 15000 samples at
500 Hz -> three 10 s windows, a resampled sine against the analytic sine, filter gains at 50 Hz / 10 Hz, an
inverted synthetic ECG flipped back to the upright one, hand-computed window combinations, torch == ONNX Runtime.
"""
from __future__ import annotations

import hashlib
import json
import math

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from palmppg.ecg import founder
from palmppg.ecg.atc import write_atc
from palmppg.synth.ecg_synth import ecg_waveform

FS_KARDIA = 300.0


def kardia_strip(seconds: float = 30.0, hr: float = 72.0, seed: int = 0, fs: float = FS_KARDIA) -> np.ndarray:
    rng = np.random.default_rng(seed)
    t = np.arange(round(seconds * fs)) / fs
    return ecg_waveform(t, np.arange(0.3, seconds, 60.0 / hr), rng)


@pytest.fixture(scope="module")
def model():
    torch.manual_seed(0)
    return founder.build_model()


@pytest.fixture(scope="module")
def weights(model, tmp_path_factory):
    """A checkpoint shaped like the official one: DataParallel prefix, optimiser state, a numpy scalar metric."""
    p = tmp_path_factory.mktemp("w") / "random_1_lead.pth"
    sd = {f"module.{k}": v for k, v in model.state_dict().items()}
    torch.save({"state_dict": sd, "optimizer": {"lr": 1e-4}, "epoch": 3, "auroc": np.float64(0.91)}, p)
    return p


# --------------------------------------------------------------------------- labels
def test_tasks_file_and_rhythm_subset():
    tasks = founder.load_tasks()
    assert len(tasks) == 150
    assert tasks[0] == "ABNORMAL ECG" and tasks[-1] == "MULTIFOCAL ATRIAL TACHYCARDIA"
    for i, name in founder.RHYTHM_LABELS.items():
        assert tasks[i] == name, (i, tasks[i], name)
    assert len(founder.RHYTHM_LABELS) == 18
    # max rule only for ectopic beats and the pause; every max label is in the subset
    names = {founder.RHYTHM_LABELS[i] for i in founder.MAX_RULE_LABELS}
    assert names == {"PREMATURE VENTRICULAR COMPLEXES", "PREMATURE ATRIAL COMPLEXES",
                     "PREMATURE SUPRAVENTRICULAR COMPLEXES", "IN A PATTERN OF BIGEMINY", "WITH SINUS PAUSE"}
    assert founder.combine_rule(5) == "mean" and founder.combine_rule(9) == "max"


# --------------------------------------------------------------------------- architecture
@pytest.mark.deep
def test_architecture_shape_and_parameter_count(model):
    n = sum(p.numel() for p in model.parameters())
    assert abs(n - 30.8e6) < 0.05e6, n
    assert n == 30_807_750
    with torch.inference_mode():
        y = model(torch.randn(2, 1, founder.WIN))
    assert tuple(y.shape) == (2, 150)
    assert model.dense.in_features == 1024 and not model.use_bn and not model.use_do
    # SAME padding with stride 2 at each of first conv + 7 stages: 5000 -> ceil(5000 / 2**8) = 20 samples
    feats = {}

    def keep(m, i, o):
        feats["x"] = o                 # returns None: the output is left unchanged

    h = model.stage_list[-1].register_forward_hook(keep)
    try:
        with torch.inference_mode():
            model(torch.randn(1, 1, founder.WIN))
    finally:
        h.remove()
    assert tuple(feats["x"].shape) == (1, 1024, math.ceil(5000 / 2 ** 8))


# --------------------------------------------------------------------------- preprocessing
def test_resample_300_to_500_matches_analytic_sine():
    t300 = np.arange(9000) / 300.0
    y, ud = founder.resample_to_model(np.sin(2 * np.pi * 5.0 * t300), 300.0)
    assert ud == (5, 3)
    assert y.size == 15000
    t500 = np.arange(15000) / 500.0
    core = slice(500, -500)            # polyphase edge effects
    assert np.max(np.abs(y[core] - np.sin(2 * np.pi * 5.0 * t500[core]))) < 1e-3


def test_window_counts():
    assert founder.preprocess(kardia_strip(30), FS_KARDIA).starts_s == [0.0, 10.0, 20.0]
    assert founder.preprocess(kardia_strip(30), FS_KARDIA, step_s=5.0).starts_s == [0.0, 5.0, 10.0, 15.0, 20.0]
    assert len(founder.preprocess(kardia_strip(32), FS_KARDIA).starts_s) == 3     # 2 s tail dropped
    assert len(founder.preprocess(kardia_strip(60), FS_KARDIA).starts_s) == 6
    w = founder.preprocess(kardia_strip(9), FS_KARDIA)
    assert w.x.shape == (0, 1, 5000) and w.notes
    w = founder.preprocess(kardia_strip(30), FS_KARDIA)
    assert w.x.shape == (3, 1, 5000) and w.x.dtype == np.float32
    assert w.fs_in == 300.0 and w.duration_s == pytest.approx(30.0)


@pytest.mark.parametrize("filtered", [True, False])
def test_zscore_per_window(filtered):
    w = founder.preprocess(kardia_strip(30) + 3.0, FS_KARDIA, filtered=filtered)   # DC offset removed by z-score
    assert np.allclose(w.x.mean(axis=-1), 0.0, atol=1e-5)
    assert np.allclose(w.x.std(axis=-1), 1.0, atol=1e-5)
    assert w.filtered is filtered


def test_unfiltered_window_is_plain_zscore_of_resampled_segment():
    x = kardia_strip(30)
    w = founder.preprocess(x, FS_KARDIA, filtered=False)
    from scipy.signal import resample_poly
    seg = resample_poly(x, 5, 3)[5000:10000]
    expect = (seg - seg.mean()) / (seg.std() + 1e-8)
    assert np.allclose(w.x[1, 0], expect, atol=1e-5)


def test_filter_gains():
    t = np.arange(5000) / 500.0
    def gain(f_hz):
        y = founder.filter_bandpass(np.sin(2 * np.pi * f_hz * t), 500.0)[0][1000:-1000]
        return np.sqrt(2 * np.mean(y ** 2))
    assert gain(50.0) < 0.03          # notch: > 30 dB down
    assert gain(10.0) == pytest.approx(1.0, abs=0.05)
    assert gain(0.1) < 0.1            # baseline wander removed


def test_polarity_flip_on_inverted_ecg():
    x = kardia_strip(30, hr=66, seed=3)
    up = founder.preprocess(x, FS_KARDIA)
    inv = founder.preprocess(-x, FS_KARDIA)
    assert not up.polarity_flipped and up.polarity_negative_fraction < 0.1
    assert inv.polarity_flipped and inv.polarity_negative_fraction > 0.9
    assert up.polarity_beats == 33 == inv.polarity_beats            # 30 s at 66 bpm from t = 0.3 s
    assert np.allclose(inv.x, up.x, atol=1e-5)                       # flipped back = upright input
    keep = founder.preprocess(-x, FS_KARDIA, polarity="keep")
    assert not keep.polarity_flipped and np.allclose(keep.x, -up.x, atol=1e-5)


def test_polarity_not_flipped_on_noise_or_short_strip():
    rng = np.random.default_rng(0)
    w = founder.preprocess(rng.normal(0, 0.05, 9000), FS_KARDIA)    # symmetric noise: about half negative
    assert not w.polarity_flipped and 0.3 < w.polarity_negative_fraction < 0.7
    flip, _neg, beats = founder.polarity_check(np.zeros(500))
    assert not flip and beats == 0


# --------------------------------------------------------------------------- window combination
def test_combine_windows_rules():
    p = np.full((3, 150), 0.1)
    p[:, 5] = [0.2, 0.5, 0.8]          # AF: mean -> 0.5
    p[:, 9] = [0.1, 0.9, 0.2]          # PVC: max -> 0.9
    p[:, 142] = [0.0, 0.0, 0.6]        # sinus pause: max -> 0.6
    p[:, 98] = [0.0, 0.0, 0.6]         # VT: sustained rhythm rule -> mean 0.2
    c = founder.combine_windows(p)
    assert c.shape == (150,)
    assert c[5] == pytest.approx(0.5) and c[9] == pytest.approx(0.9)
    assert c[142] == pytest.approx(0.6) and c[98] == pytest.approx(0.2) and c[0] == pytest.approx(0.1)
    assert np.isnan(founder.combine_windows(np.zeros((0, 150)))).all()


# --------------------------------------------------------------------------- inference and loading
@pytest.mark.deep
def test_predict_output(model):
    r = founder.predict(model, kardia_strip(30), FS_KARDIA)
    assert r["n_windows"] == 3 and r["window_starts_s"] == [0.0, 10.0, 20.0]
    assert r["filtered"] is True and "notch" in r["filter"] and r["polarity_flipped"] is False
    assert len(r["labels"]) == 18 and len(r["all_labels"]) == 150 and np.shape(r["window_probs"]) == (3, 150)
    af = r["labels"]["ATRIAL FIBRILLATION"]
    pvc = r["labels"]["PREMATURE VENTRICULAR COMPLEXES"]
    assert af["rule"] == "mean" and af["prob"] == pytest.approx(np.mean(af["window_probs"]), abs=2e-6)
    assert pvc["rule"] == "max" and pvc["prob"] == pytest.approx(max(pvc["window_probs"]), abs=2e-6)
    assert all(0.0 <= v <= 1.0 for v in r["all_labels"].values())
    assert "clinician" in r["use"]
    json.dumps(r)                                                   # JSON-ready
    ru = founder.predict(model, kardia_strip(30), FS_KARDIA, filtered=False)
    assert ru["filtered"] is False and ru["filter"].startswith("none")
    short = founder.predict(model, kardia_strip(5), FS_KARDIA)
    assert short["n_windows"] == 0 and short["labels"]["ATRIAL FIBRILLATION"]["prob"] is None


@pytest.mark.deep
def test_load_model_roundtrip(model, weights, tmp_path):
    m2 = founder.load_model(weights)
    assert m2.weights_sha256 == hashlib.sha256(weights.read_bytes()).hexdigest()
    x = torch.randn(2, 1, founder.WIN)
    with torch.inference_mode():
        assert torch.equal(model(x), m2(x))
    # a checkpoint missing a weight is refused
    sd = dict(model.state_dict())
    sd.pop("dense.weight")
    bad = tmp_path / "bad.pth"
    torch.save({"state_dict": sd}, bad)
    with pytest.raises(AssertionError, match="lacks 1"):
        founder.load_model(bad)


@pytest.mark.deep
def test_onnx_concat_pad_matches_torch(model, tmp_path):
    ort = pytest.importorskip("onnxruntime")
    onnx = pytest.importorskip("onnx")
    path = founder.export_onnx(model, tmp_path / "m.onnx")
    m = onnx.load(str(path))
    assert m.opset_import[0].version == 17
    dims = m.graph.input[0].type.tensor_type.shape.dim
    assert dims[2].dim_value == 5000 and [o.name for o in m.graph.output] == ["logits", "probs"]
    sess = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    rng = np.random.default_rng(1)
    x = np.concatenate([founder.z_score(rng.standard_normal((3, 1, 5000))).astype(np.float32),
                        founder.preprocess(kardia_strip(30), FS_KARDIA).x,
                        founder.preprocess(-kardia_strip(20, hr=110), FS_KARDIA, filtered=False).x])
    logits, probs = sess.run(None, {"ecg": x})
    with torch.inference_mode():
        ref = torch.sigmoid(model(torch.from_numpy(x))).numpy()
    assert np.max(np.abs(probs - ref)) < 1e-4
    assert np.allclose(probs, 1 / (1 + np.exp(-logits)), atol=1e-6)


# --------------------------------------------------------------------------- folder runner and CLI
def _write_samples_csv(path, mv, fs, seed=0):
    rng = np.random.default_rng(seed)
    t = (np.arange(mv.size) / fs * 1e9 + rng.normal(0, 2e5, mv.size)).astype(np.int64)  # 0.2 ms jitter
    t[0], t[-1] = 0, int((mv.size - 1) / fs * 1e9)
    lines = ["t_ref_ns,sample_idx,lead1_raw,lead2_raw,lead1_mv,lead2_mv"]
    lines += [f"{t[i]},{i},0,0,{mv[i]:.5f},0.00000" for i in range(mv.size)]
    path.write_text("\n".join(lines) + "\n")


@pytest.mark.deep
def test_run_participants_writes_json_per_clip(model, tmp_path):
    root = tmp_path / "participants"
    (root / "P001").mkdir(parents=True)
    (root / "P002").mkdir()
    _write_samples_csv(root / "P001" / "clip1_ecg_samples.csv", kardia_strip(30), FS_KARDIA)
    write_atc(root / "P001" / "clip1_ecg.atc", kardia_strip(30), fs=300)       # same clip: CSV wins
    _write_samples_csv(root / "P001" / "clip2_ecg_samples.csv", kardia_strip(6), FS_KARDIA)  # too short
    write_atc(root / "P002" / "clip1_ecg.atc", -kardia_strip(30, seed=2), fs=300)            # inverted leads
    rows = founder.run_participants(model, tmp_path)                 # study root: participants/ found
    by = {(r["pid"], r["clip"]): r for r in rows}
    assert set(by) == {("P001", "clip1"), ("P001", "clip2"), ("P002", "clip1")}
    assert by[("P001", "clip1")]["kind"] == "ble_csv" and by[("P002", "clip1")]["kind"] == "ble_atc"
    assert all(r["error"] is None for r in rows)
    assert by[("P001", "clip2")]["n_windows"] == 0
    assert by[("P002", "clip1")]["polarity_flipped"] is True
    out = json.loads((root / "P001" / "clip1_ecg_founder.json").read_text())
    assert out["pid"] == "P001" and out["clip"] == "clip1" and out["n_windows"] == 3
    assert out["fs_in"] == 300.0 and abs(out["fs_measured"] - 300.0) < 0.5
    assert (root / "P002" / "clip1_ecg_founder.json").exists()


@pytest.mark.deep
def test_cli_founder_on_atc(weights, tmp_path, capsys):
    from palmppg.cli import build_parser, main

    atc = tmp_path / "kardia_0001.atc"
    write_atc(atc, kardia_strip(30), fs=300)
    assert main(["ecg", "founder", "--weights", str(weights), "--atc", str(atc), "--unfiltered",
                 "--out", str(tmp_path / "out")]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["n_windows"] == 3 and printed["filtered"] is False
    res = json.loads((tmp_path / "out" / "kardia_0001_ecg_founder.json").read_text())
    assert res["weights_sha256"] == hashlib.sha256(weights.read_bytes()).hexdigest()
    with pytest.raises(SystemExit):
        build_parser().parse_args(["ecg", "founder", "--weights", "w.pth", "--atc", "a", "--participants", "d"])


@pytest.mark.deep
def test_export_tool_report(tmp_path):
    pytest.importorskip("onnxruntime")
    pytest.importorskip("onnx")
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "export_ecgfounder_onnx", Path(__file__).resolve().parents[1] / "tools" / "export_ecgfounder_onnx.py")
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    out = tmp_path / "rand.onnx"
    assert tool.main(["--random-weights", "--out", str(out)]) == 0
    rep = json.loads(out.with_suffix(".report.json").read_text())
    assert rep["pass"] is True and rep["opset"] == 17 and rep["weights"]["random"] is True
    assert rep["checks"]["random"]["max_abs_dp"] < 1e-4 and rep["checks"]["synthetic"]["max_abs_dp"] < 1e-4
    assert rep["checks"]["synthetic"]["n_windows"] == 24      # 4 strips x 2 filter settings x 3 windows
    assert "Concat" in rep["operators"] and rep["input"]["shape"] == ["batch", 1, 5000]
