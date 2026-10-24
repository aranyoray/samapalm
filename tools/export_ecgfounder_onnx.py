"""Export ECGFounder 1-lead to fp32 ONNX and check ONNX Runtime against torch (design section 9, on-phone hook).

    python tools/export_ecgfounder_onnx.py --weights work/ecgfounder/1_lead_ECGFounder.pth
    python tools/export_ecgfounder_onnx.py --random-weights          # pipeline check only, outputs meaningless

Writes the model (default work/ecgfounder/ecgfounder_1lead_fp32.onnx) and a JSON report next to it
(<model>.report.json): versions, opset, operator list, weights and model sha256, size, and the parity of ONNX
Runtime against torch on random z-scored windows and on synthetic ECG windows run through
`palmppg.ecg.founder.preprocess` (sinus, AF, ectopy, inverted). Pass: max |delta p| < 1e-4 on every window and
all 150 outputs. Needs the `ecgmodel` extra (onnx, onnxruntime) and torch. Exit code 0 on pass, 3 on fail.

Graph: input `ecg` (batch, 1, 5000) float32 = 10 s at 500 Hz after preprocessing; outputs `logits` and `probs`
(batch, 150), label i = line i + 1 of configs/ecgfounder_tasks.txt. The zero pad before each max-pool is a Concat
of zeros so ONNX Runtime cannot fuse it into MaxPool's -inf padding (founder.onnx_export_mode).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from palmppg.ecg import founder

TOL_DP = 1e-4
DEFAULT_OUT = ROOT / "work" / "ecgfounder" / "ecgfounder_1lead_fp32.onnx"


def synthetic_windows(seed: int = 0) -> tuple[np.ndarray, list[str]]:
    """Preprocessed windows from synthetic 30 s Kardia-like strips (300 Hz) of known rhythm."""
    from palmppg.synth.ecg_synth import ecg_waveform

    rng = np.random.default_rng(seed)
    fs, dur = 300.0, 30.0
    t = np.arange(int(fs * dur)) / fs
    strips = {}
    strips["sinus_72"] = (np.arange(0.4, dur, 60 / 72), {})
    rr = rng.uniform(0.45, 1.0, 80)
    strips["af_like"] = (np.cumsum(rr)[np.cumsum(rr) < dur], {"p_wave": False})
    r = list(np.arange(0.4, dur, 0.8))
    r[10] -= 0.3
    r[25] -= 0.3
    strips["ectopy"] = (np.asarray(r), {})
    strips["sinus_inverted"] = (np.arange(0.3, dur, 60 / 60), {})
    xs, names = [], []
    for name, (rt, kw) in strips.items():
        mv = ecg_waveform(t, rt, rng, **kw)
        if name.endswith("inverted"):
            mv = -mv
        for filtered in (True, False):
            w = founder.preprocess(mv, fs, filtered=filtered)
            xs.append(w.x)
            names += [f"{name}/{'filtered' if filtered else 'unfiltered'}/w{i}" for i in range(len(w.x))]
    return np.concatenate(xs), names


def parity(model, onnx_path: Path, x: np.ndarray) -> dict:
    import onnxruntime as ort
    import torch

    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    logits, probs = sess.run(None, {founder.ONNX_INPUT: x.astype(np.float32)})
    with torch.inference_mode():
        ref = model(torch.from_numpy(x.astype(np.float32))).double().numpy()
    p_ref = 1.0 / (1.0 + np.exp(-ref))
    dp = np.abs(probs.astype(np.float64) - p_ref)
    return {"n_windows": len(x), "max_abs_dp": float(dp.max()), "mean_abs_dp": float(dp.mean()),
            "max_abs_dlogit": float(np.abs(logits - ref).max()),
            "max_abs_dp_rhythm_labels": float(dp[:, sorted(founder.RHYTHM_LABELS)].max()),
            "pass": bool(dp.max() < TOL_DP)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--weights", type=Path, help="1_lead_ECGFounder.pth")
    g.add_argument("--random-weights", action="store_true", help="random initialisation (export check only)")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--report", type=Path, default=None, help="default <out>.report.json")
    ap.add_argument("--trust-pickle", action="store_true", help="full unpickle of the checkpoint (see load_model)")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args(argv)

    import onnx
    import onnxruntime as ort
    import torch

    torch.manual_seed(args.seed)
    if args.random_weights:
        model = founder.build_model()
        weights = {"path": None, "sha256": None, "random": True}
    else:
        model = founder.load_model(args.weights, trust_pickle=args.trust_pickle)
        weights = {"path": str(args.weights), "sha256": model.weights_sha256, "random": False}
    out = founder.export_onnx(model, args.out)
    onnx.checker.check_model(str(out))
    graph = onnx.load(str(out)).graph

    rng = np.random.default_rng(args.seed)
    x_rand = founder.z_score(rng.standard_normal((8, 1, founder.WIN))).astype(np.float32)
    x_syn, syn_names = synthetic_windows(args.seed)
    checks = {"random": parity(model, out, x_rand), "synthetic": parity(model, out, x_syn)}
    checks["synthetic"]["windows"] = syn_names
    ok = all(c["pass"] for c in checks.values())
    report = {
        "created_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "onnx_path": str(out), "onnx_sha256": founder.sha256_file(out), "onnx_size_mb": round(out.stat().st_size / 1e6, 2),
        "weights": weights, "opset": founder.ONNX_OPSET, "input": {"name": founder.ONNX_INPUT,
                                                                  "shape": ["batch", 1, founder.WIN], "dtype": "float32"},
        "outputs": {k: ["batch", founder.N_CLASSES] for k in founder.ONNX_OUTPUTS},
        "operators": sorted({n.op_type for n in graph.node}),
        "preprocessing": {"fs": founder.FS_MODEL, "window_s": founder.WIN_S, "filtered_default": founder.FILTER_DESC[True],
                          "unfiltered": founder.FILTER_DESC[False], "zscore_eps": founder.ZSCORE_EPS},
        "labels_file": "configs/ecgfounder_tasks.txt", "rhythm_labels": {str(k): v for k, v in founder.RHYTHM_LABELS.items()},
        "tolerance_dp": TOL_DP, "checks": checks, "pass": ok,
        "versions": {"torch": torch.__version__, "onnx": onnx.__version__, "onnxruntime": ort.__version__},
        "use": founder.USE_NOTE,
    }
    rep = args.report or out.with_suffix(".report.json")
    rep.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("onnx_path", "onnx_size_mb", "pass")}
                     | {k: {m: v[m] for m in ("max_abs_dp", "max_abs_dlogit")} for k, v in checks.items()}, indent=1))
    print(f"report: {rep}")
    return 0 if ok else 3


if __name__ == "__main__":
    sys.exit(main())
