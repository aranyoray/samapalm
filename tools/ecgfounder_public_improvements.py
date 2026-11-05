"""Cheap changes to the ECGFounder AF pre-read, tested on public data (docs/ecg_model.md section 5.1).

    python tools/ecgfounder_public_improvements.py --weights work/ecgfounder/1_lead_ECGFounder.pth \
        --cinc work/public/cinc2017 --ptbxl work/public/ptbxl --device mps

Same preprocessing, splits and threshold rule as tools/ecgfounder_public_eval.py. Compared: the current AF output
on 10 s windows; half-overlapping 5 s steps; AF or flutter; a logistic layer on all 150 outputs; RR-interval
irregularity alone and fused with the AF output; and Platt calibration of the AF output. Anything fitted uses the
CinC training split (calibration: validation), and is scored once on CinC test and on PTB-XL fold 10 lead I.
Writes work/ecgfounder/public_eval/improvements.json.
"""
import argparse, sys, json, numpy as np, torch
from pathlib import Path
from scipy.signal import find_peaks, butter, filtfilt
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from palmppg.ecg import founder
import tools.ecgfounder_public_eval as ev
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
ap = argparse.ArgumentParser()
ap.add_argument('--weights', required=True); ap.add_argument('--cinc', required=True); ap.add_argument('--ptbxl', required=True)
ap.add_argument('--device', default='cpu'); ap.add_argument('--out', default=str(ROOT / 'work/ecgfounder/public_eval/improvements.json'))
A = ap.parse_args()
dev = torch.device(A.device)
m = founder.load_model(A.weights).to(dev).eval()
m.return_features = True
def outputs(x):
    L, E = [], []
    with torch.inference_mode():
        for i in range(0, len(x), 128):
            z, f = m(torch.from_numpy(np.ascontiguousarray(x[i:i+128])).to(dev)); L.append(z.cpu().numpy()); E.append(f.cpu().numpy())
    return np.concatenate(L).astype(np.float64), np.concatenate(E)
def rr_features(sig, fs):
    """RR irregularity on the whole strip (polarity-corrected, band-passed): the classic AF cues."""
    y, _ = founder.resample_to_model(np.nan_to_num(sig), fs)
    flip, _, _ = founder.polarity_check(y)
    if flip: y = -y
    b, a = butter(3, [5, 30], btype='band', fs=500); yb = filtfilt(b, a, y)
    e = np.abs(yb); h = 0.5 * np.percentile(e, 99)
    pk, _ = find_peaks(e, height=h, distance=int(0.3 * 500))
    rr = np.diff(pk) / 500.0
    rr = rr[(rr > 0.25) & (rr < 2.5)]
    if len(rr) < 4: return np.full(6, np.nan)
    d = np.diff(rr)
    return np.array([rr.std() / rr.mean(), np.sqrt(np.mean(d ** 2)) / rr.mean(), np.mean(np.abs(d) > 0.05),
                     np.median(np.abs(d)) / rr.mean(), 60 / rr.mean(), np.mean(np.diff(np.sign(d)) != 0)])
res = {}
sigs, labels = ev.read_cinc(Path(A.cinc))
split = ev.cinc_split(labels, 0); recs = sorted(sigs)
y = np.array([labels[r] == 1 for r in recs]).astype(int); sp = np.array([split[r] for r in recs])
ps, pa = ev.read_ptbxl_fold10(Path(A.ptbxl))
data = {}
for name, S, fs in (('cinc', [sigs[r] for r in recs], 300.0), ('ptb', ps, 100.0)):
    for step in (10.0, 5.0):
        xs, own = [], []
        for i, s in enumerate(S):
            w = founder.preprocess(s, fs, filtered=True, step_s=step)
            if len(w.x): xs.append(w.x); own += [i] * len(w.x)
        xs = np.concatenate(xs); own = np.array(own)
        L, E = outputs(xs)
        data[(name, step)] = (ev.per_strip(L, own, len(S)), ev.per_strip(E, own, len(S)))
        print(name, step, xs.shape, flush=True)
    data[(name, 'rr')] = np.array([rr_features(s, fs) for s in S])
sig = lambda z: 1 / (1 + np.exp(-z))
def score(name, s_c, s_p):
    ok = ~np.isnan(s_c); va, te = ok & (sp == 'val'), ok & (sp == 'test')
    thr = ev.youden_threshold(y[va], s_c[va]); okp = ~np.isnan(s_p)
    res[name] = {'cinc_test': ev.binary_summary(y[te], s_c[te], thr), 'ptbxl': ev.binary_summary(pa[okp], s_p[okp], thr)}
    a, b = res[name]['cinc_test'], res[name]['ptbxl']
    print(f"{name:42s} CinC {a['auroc']:.3f} ({a['auroc_ci95'][0]:.3f}-{a['auroc_ci95'][1]:.3f}) se {a['sensitivity']:.3f} sp {a['specificity']:.3f} | PTB {b['auroc']:.3f} ({b['auroc_ci95'][0]:.3f}-{b['auroc_ci95'][1]:.3f}) se {b['sensitivity']:.3f} sp {b['specificity']:.3f}", flush=True)
Lc, Ec = data[('cinc', 10.0)]; Lp, Ep = data[('ptb', 10.0)]
score('A. current app (AF output, 10 s windows)', sig(Lc[:, 5]), sig(Lp[:, 5]))
score('B. half-overlapping 5 s step', sig(data[('cinc', 5.0)][0][:, 5]), sig(data[('ptb', 5.0)][0][:, 5]))
score('C. AF or atrial flutter (max of the two)', np.maximum(sig(Lc[:, 5]), sig(Lc[:, 32])), np.maximum(sig(Lp[:, 5]), sig(Lp[:, 32])))
tr = (sp == 'train') & ~np.isnan(Lc[:, 0])
def fit(Xc, Xp, name, C=0.1):
    imp = np.nanmedian(Xc[tr], axis=0); Xc = np.where(np.isnan(Xc), imp, Xc); Xp = np.where(np.isnan(Xp), imp, Xp)
    sc = StandardScaler().fit(Xc[tr]); clf = LogisticRegression(C=C, max_iter=5000).fit(sc.transform(Xc[tr]), y[tr])
    pc = clf.predict_proba(sc.transform(Xc))[:, 1]; pc[np.isnan(Lc[:, 0])] = np.nan
    pp = clf.predict_proba(sc.transform(Xp))[:, 1]; pp[np.isnan(Lp[:, 0])] = np.nan
    score(name, pc, pp)
fit(Lc, Lp, 'D. logistic layer on all 150 outputs')
fit(data[('cinc', 'rr')], data[('ptb', 'rr')], 'E. RR-irregularity features alone')
fit(np.column_stack([Lc[:, 5], data[('cinc', 'rr')]]), np.column_stack([Lp[:, 5], data[('ptb', 'rr')]]), 'F. AF output + RR irregularity')
# calibration of the current output: Platt on CinC val, checked on CinC test and PTB
from sklearn.metrics import brier_score_loss
va = (sp == 'val') & ~np.isnan(Lc[:, 5]); te = (sp == 'test') & ~np.isnan(Lc[:, 5])
pl = LogisticRegression(C=1e6).fit(Lc[va, 5:6], y[va])
cal = {'raw_brier_cinc_test': brier_score_loss(y[te], sig(Lc[te, 5])), 'platt_brier_cinc_test': brier_score_loss(y[te], pl.predict_proba(Lc[te, 5:6])[:, 1]),
       'raw_brier_ptb': brier_score_loss(pa, sig(Lp[:, 5])), 'platt_brier_ptb': brier_score_loss(pa, pl.predict_proba(Lp[:, 5:6])[:, 1]),
       'platt_coef': float(pl.coef_[0, 0]), 'platt_intercept': float(pl.intercept_[0]),
       'raw_mean_prob_nonAF_cinc_test': float(sig(Lc[te & (y == 0), 5]).mean()), 'raw_mean_prob_AF_cinc_test': float(sig(Lc[te & (y == 1), 5]).mean())}
res['calibration'] = cal; print(json.dumps(cal, indent=1))
Path(A.out).parent.mkdir(parents=True, exist_ok=True)
json.dump(res, open(A.out, 'w'), indent=1, default=float)
