"""ECGFounder 1-lead on public data, through the study's own preprocessing (design section 9, H6 groundwork).

    python tools/ecgfounder_public_eval.py --weights work/ecgfounder/1_lead_ECGFounder.pth \
        --cinc work/public/cinc2017 --ptbxl work/public/ptbxl [--finetune] [--device mps]

Answers the gap noted in docs/ecg_model.md: the model's authors never evaluated it on Kardia lead I. The
PhysioNet/CinC Challenge 2017 set is 8,528 single-lead AliveCor (Kardia) recordings at 300 Hz labelled Normal,
AF, Other rhythm or Noisy; PTB-XL fold 10 (the recommended test fold, lead I, 100 Hz) is an external check on
hospital ECGs. Every strip goes through `palmppg.ecg.founder.preprocess` exactly as `palmppg ecg founder` runs it:
resample to 500 Hz, polarity check, non-overlapping 10 s windows with the tail dropped, upstream filter, z-score.
A strip shorter than 10 s gives no window and is reported as excluded, as the runner does.

Zero-shot: the pretrained ATRIAL FIBRILLATION output (index 5), combined over windows by its fixed rule (mean),
filtered and unfiltered. `--finetune`: the backbone plus a new 4-class head (N, AF, Other, Noisy) trained on the
CinC training split, the epoch picked on the validation split by the Challenge score (mean F1 of N, AF, Other),
then scored once on the test split and on PTB-XL. CinC 2017 gives no patient identifiers, so its 70/15/15 split
is by recording and one person may sit in more than one split; PTB-XL is the check that does not have that
problem. Thresholds for sensitivity and specificity are chosen on CinC validation (Youden) and carried over
unchanged.

Outputs (under --out, default work/ecgfounder/public_eval): results.json, results.md, splits.csv and, with
--finetune, ecgfounder_1lead_cinc2017_ft.pt. The weights stay under work/ (git-ignored): they are derived from
the ECGFounder checkpoint, which docs/ecg_model.md section 5 says not to redistribute.
"""
from __future__ import annotations

import argparse
import ast
import copy
import datetime as dt
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CLASSES = ["N", "A", "O", "~"]
AF_INDEX = 5
DEFAULT_OUT = ROOT / "work" / "ecgfounder" / "public_eval"


# --------------------------------------------------------------------------- data
def cinc_split(labels: dict[str, int], seed: int = 0) -> dict[str, str]:
    """Stratified 70/15/15 split by recording, deterministic for a seed."""
    from sklearn.model_selection import train_test_split

    recs = sorted(labels)
    y = [labels[r] for r in recs]
    tr, rest = train_test_split(recs, test_size=0.30, stratify=y, random_state=seed)
    va, te = train_test_split(rest, test_size=0.50, stratify=[labels[r] for r in rest], random_state=seed)
    return {**{r: "train" for r in tr}, **{r: "val" for r in va}, **{r: "test" for r in te}}


def read_cinc(cinc_dir: Path) -> tuple[dict[str, np.ndarray], dict[str, int]]:
    """CinC 2017 .mat strips in mV (ADC gain 1000) and their labels from REFERENCE-v3.csv."""
    import scipy.io

    rows = [l.strip().split(",") for l in (cinc_dir / "REFERENCE-v3.csv").read_text().splitlines() if l.strip()]
    labels = {r: CLASSES.index(c) for r, c in rows}
    data_dir = cinc_dir / "training2017" if (cinc_dir / "training2017").is_dir() else cinc_dir
    sigs = {r: scipy.io.loadmat(data_dir / f"{r}.mat")["val"][0].astype(np.float64) / 1000.0 for r in labels}
    return sigs, labels


def read_ptbxl_fold10(ptb_dir: Path) -> tuple[list[np.ndarray], np.ndarray]:
    import pandas as pd
    import wfdb

    db = pd.read_csv(ptb_dir / "ptbxl_database.csv")
    db = db[db.strat_fold == 10]
    af = db.scp_codes.apply(lambda s: int("AFIB" in ast.literal_eval(s))).to_numpy()
    sigs = []
    for f in db.filename_lr:
        sig, meta = wfdb.rdsamp(str(ptb_dir / f))
        sigs.append(sig[:, meta["sig_name"].index("I")])
    return sigs, af


def prep(sigs, fs: float, filtered: bool, founder) -> tuple[np.ndarray, np.ndarray, dict]:
    """Strips -> stacked windows, the owning strip index per window, and per-strip metadata."""
    xs, owner, flipped, short = [], [], 0, 0
    for i, s in enumerate(sigs):
        w = founder.preprocess(s, fs, filtered=filtered, polarity="auto")
        flipped += int(w.polarity_flipped)
        if len(w.x) == 0:
            short += 1
            continue
        xs.append(w.x)
        owner += [i] * len(w.x)
    return np.concatenate(xs), np.asarray(owner), {"polarity_flipped": flipped, "no_window": short}


# --------------------------------------------------------------------------- model
def run_windows(model, x: np.ndarray, device, head: str = "sigmoid", batch: int = 128) -> np.ndarray:
    import torch

    out = []
    model.eval()
    with torch.inference_mode():
        for i in range(0, len(x), batch):
            z = model(torch.from_numpy(np.ascontiguousarray(x[i:i + batch])).to(device))
            out.append((torch.sigmoid(z) if head == "sigmoid" else torch.softmax(z, 1)).cpu().numpy())
    return np.concatenate(out).astype(np.float64)


def per_strip(values: np.ndarray, owner: np.ndarray, n: int) -> np.ndarray:
    """Mean over each strip's windows (the runner's rule for sustained rhythms); NaN for strips with none."""
    out = np.full((n,) + values.shape[1:], np.nan)
    for i in np.unique(owner):
        out[i] = values[owner == i].mean(axis=0)
    return out


# --------------------------------------------------------------------------- metrics
def youden_threshold(y: np.ndarray, s: np.ndarray) -> float:
    best, thr = -1.0, float(np.min(s))
    for t in np.unique(s):
        p = s >= t
        j = p[y == 1].mean() + (~p[y == 0]).mean() - 1
        if j > best:
            best, thr = j, float(t)
    return thr


def binary_summary(y: np.ndarray, s: np.ndarray, thr: float, n_boot: int = 1000, seed: int = 0) -> dict:
    from sklearn.metrics import roc_auc_score

    rng = np.random.default_rng(seed)
    auc = roc_auc_score(y, s)
    boots = []
    for _ in range(n_boot):
        b = rng.integers(0, len(y), len(y))
        if y[b].min() != y[b].max():
            boots.append(roc_auc_score(y[b], s[b]))
    p = s >= thr
    tp, fn = int((p & (y == 1)).sum()), int((~p & (y == 1)).sum())
    tn, fp = int((~p & (y == 0)).sum()), int((p & (y == 0)).sum())
    return {"n": int(len(y)), "positives": int(y.sum()), "auroc": float(auc),
            "auroc_ci95": [float(v) for v in np.percentile(boots, [2.5, 97.5])], "threshold": float(thr),
            "sensitivity": tp / max(1, tp + fn), "specificity": tn / max(1, tn + fp),
            "tp_fn_tn_fp": [tp, fn, tn, fp]}


def challenge_summary(y: np.ndarray, prob: np.ndarray) -> dict:
    from sklearn.metrics import confusion_matrix, f1_score

    pred = prob.argmax(1)
    f1 = f1_score(y, pred, labels=[0, 1, 2, 3], average=None, zero_division=0)
    return {"F1": dict(zip(CLASSES, map(float, f1))), "challenge_F1_NAO": float(f1[:3].mean()),
            "confusion_rows_true_cols_pred": confusion_matrix(y, pred, labels=[0, 1, 2, 3]).tolist()}


# --------------------------------------------------------------------------- fine-tune
def finetune(base, xw, owner, y_strip, split_strip, device, epochs: int, seed: int, log):
    import torch

    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    model = copy.deepcopy(base)
    model.dense = torch.nn.Linear(model.dense.in_features, 4)
    model.to(device)
    idx_of = {i: np.flatnonzero(owner == i) for i in np.unique(owner)}
    tr = [i for i in idx_of if split_strip[i] == "train"]
    va = [i for i in idx_of if split_strip[i] == "val"]
    counts = np.bincount([y_strip[i] for i in tr], minlength=4)
    weight = torch.tensor((counts.sum() / counts) ** 0.5, dtype=torch.float32)
    weight = (weight / weight.mean()).to(device)
    opt = torch.optim.AdamW([
        {"params": [p for n, p in model.named_parameters() if not n.startswith("dense")], "lr": 1e-4},
        {"params": model.dense.parameters(), "lr": 1e-3}], weight_decay=1e-5)
    va_idx = np.concatenate([idx_of[i] for i in va])
    best = (-1.0, None, 0)
    history = []
    for ep in range(epochs):
        model.train()
        order = rng.permutation(tr)
        t0, total = time.time(), 0.0
        for k in range(0, len(order), 32):
            strips = order[k:k + 32]
            xb = torch.from_numpy(np.stack([xw[rng.choice(idx_of[i])] for i in strips]))   # one random window each
            xb = xb * float(rng.uniform(0.9, 1.1)) + 0.01 * torch.randn_like(xb)
            yb = torch.tensor([y_strip[i] for i in strips])
            loss = torch.nn.functional.cross_entropy(model(xb.to(device)), yb.to(device), weight=weight)
            opt.zero_grad()
            loss.backward()
            opt.step()
            total += loss.item() * len(strips)
        pv = per_strip(run_windows(model, xw[va_idx], device, "softmax"), owner[va_idx], len(y_strip))
        score = challenge_summary(y_strip[va], pv[va])["challenge_F1_NAO"]
        history.append({"epoch": ep + 1, "train_loss": total / len(order), "val_challenge_F1": score,
                        "minutes": (time.time() - t0) / 60})
        log(history[-1])
        if score > best[0]:
            best = (score, copy.deepcopy(model.state_dict()), ep + 1)
    model.load_state_dict(best[1])
    return model, history, best[2]


# --------------------------------------------------------------------------- main
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--weights", required=True)
    ap.add_argument("--cinc", required=True, help="folder with REFERENCE-v3.csv and training2017/")
    ap.add_argument("--ptbxl", help="PTB-XL 1.0.3 folder (ptbxl_database.csv, records100/)")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--device", default="cpu", help="cpu, mps or cuda")
    ap.add_argument("--finetune", action="store_true")
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--trust-pickle", action="store_true")
    a = ap.parse_args(argv)

    import torch
    from palmppg.ecg import founder

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    device = torch.device(a.device)
    log = lambda m: print(json.dumps(m, default=float), flush=True)

    base = founder.load_model(a.weights, trust_pickle=a.trust_pickle)
    model = copy.deepcopy(base).to(device)
    sigs, labels = read_cinc(Path(a.cinc))
    recs = sorted(sigs)
    split = cinc_split(labels, a.seed)
    y = np.array([labels[r] for r in recs])
    sp = np.array([split[r] for r in recs])
    (out / "splits.csv").write_text("record,label,split\n" + "".join(f"{r},{CLASSES[labels[r]]},{split[r]}\n" for r in recs))
    ptb = read_ptbxl_fold10(Path(a.ptbxl)) if a.ptbxl else None

    res = {"created_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"), "weights_sha256": base.weights_sha256,
           "torch_version": torch.__version__, "device": str(device), "seed": a.seed,
           "cinc_counts": {s: {c: int(((sp == s) & (y == i)).sum()) for i, c in enumerate(CLASSES)}
                           for s in ("train", "val", "test")}}
    windows = {}
    for filtered in (True, False):
        key = "filtered" if filtered else "unfiltered"
        xw, owner, meta = prep([sigs[r] for r in recs], 300.0, filtered, founder)
        windows[key] = (xw, owner)
        af = per_strip(run_windows(model, xw, device)[:, AF_INDEX], owner, len(recs))
        ok = ~np.isnan(af)
        isaf = (y == 1).astype(int)
        thr = youden_threshold(isaf[ok & (sp == "val")], af[ok & (sp == "val")])
        r = {"windows": int(len(xw)), **meta,
             "cinc_test": binary_summary(isaf[ok & (sp == "test")], af[ok & (sp == "test")], thr),
             "cinc_all": binary_summary(isaf[ok], af[ok], thr)}
        if ptb:
            px, po, pmeta = prep(ptb[0], 100.0, filtered, founder)
            paf = per_strip(run_windows(model, px, device)[:, AF_INDEX], po, len(ptb[0]))
            r["ptbxl_fold10"] = {**pmeta, **binary_summary(ptb[1], paf, thr)}
        res[f"zero_shot_{key}"] = r
        log({key: {k: (v["auroc"] if isinstance(v, dict) and "auroc" in v else v) for k, v in r.items()}})

    if a.finetune:
        xw, owner = windows["filtered"]
        ft, history, best_epoch = finetune(model, xw, owner, y, sp, device, a.epochs, a.seed, log)
        torch.save(ft.state_dict(), out / "ecgfounder_1lead_cinc2017_ft.pt")
        prob = per_strip(run_windows(ft, xw, device, "softmax"), owner, len(recs))
        ok = ~np.isnan(prob[:, 0])
        isaf = (y == 1).astype(int)
        thr = youden_threshold(isaf[ok & (sp == "val")], prob[ok & (sp == "val"), 1])
        te = ok & (sp == "test")
        r = {"epochs": a.epochs, "best_epoch": best_epoch, "history": history,
             "cinc_test": {**challenge_summary(y[te], prob[te]), "af": binary_summary(isaf[te], prob[te, 1], thr)}}
        if ptb:
            px, po, _ = prep(ptb[0], 100.0, True, founder)
            pprob = per_strip(run_windows(ft, px, device, "softmax"), po, len(ptb[0]))
            r["ptbxl_fold10_af"] = binary_summary(ptb[1], pprob[:, 1], thr)
        res["finetune_filtered"] = r

    (out / "results.json").write_text(json.dumps(res, indent=1, default=float))
    lines = ["| Setting | Data | n (AF) | AF AUROC (95% CI) | Sens | Spec |", "|---|---|---|---|---|---|"]
    def row(name, data, s):
        lines.append(f"| {name} | {data} | {s['n']} ({s['positives']}) | {s['auroc']:.3f} "
                     f"({s['auroc_ci95'][0]:.3f}-{s['auroc_ci95'][1]:.3f}) | {s['sensitivity']:.3f} | {s['specificity']:.3f} |")
    for key in ("filtered", "unfiltered"):
        z = res[f"zero_shot_{key}"]
        row(f"zero-shot, {key}", "CinC 2017 test", z["cinc_test"])
        if "ptbxl_fold10" in z:
            row(f"zero-shot, {key}", "PTB-XL fold 10, lead I", z["ptbxl_fold10"])
    if "finetune_filtered" in res:
        f = res["finetune_filtered"]
        row("fine-tuned, filtered", "CinC 2017 test", f["cinc_test"]["af"])
        if "ptbxl_fold10_af" in f:
            row("fine-tuned, filtered", "PTB-XL fold 10, lead I", f["ptbxl_fold10_af"])
        lines.append(f"\nFine-tuned Challenge F1 (mean of N, AF, Other) on CinC test: "
                     f"{f['cinc_test']['challenge_F1_NAO']:.3f}; best epoch {f['best_epoch']} of {f['epochs']}.")
    (out / "results.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
