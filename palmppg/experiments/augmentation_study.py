"""Section 8 synthetic augmentation study on the first clips of the pilot/development stream.

For every clip, every transform of the section 8 library and every severity, the raw Pi frames are transformed and
re-analysed with the classical methods; the measured pulse rate, SQI, coverage and morphology stability are compared
with the same clip untransformed. Outputs (work/augmentation/):
  degradation.parquet   one row per (clip, transform, severity, method)
  curves.parquet        metric versus severity per transform and method (median over clips)
  ranking.md            corruptions ranked by the median pulse-rate error they cause (feeds the phone-app design)
  benign_check.md       benign transforms checked for rate preservation within cfg augment.rate_preservation_bpm
  ablation.json / .md   training with versus without augmented copies (pulse-rate and BP-tertile tasks)
Rules kept: development/pilot clips only; augmented copies never sit in the validation fold of their source clip;
no temporal smoothing or interpolation (asserted by the library); synthetic tone shifts support no equity claim.
"""
from __future__ import annotations

import json
import time
from typing import Any

import numpy as np
import pandas as pd

from palmppg.core.config import Config, load_frozen_config, rng
from palmppg.core.paths import StudyLayout, WorkLayout
from palmppg.core.timeline import Timeline

BENIGN = ("Rotate", "Translate", "Scale", "ExposureShift", "IlluminantShift", "VignettingGain", "Quantise8bit", "TimestampJitter")
SMOKE_METHODS = ("GREEN", "CHROM", "POS", "PBV")
ALLOWED_STREAMS = ("pilot", "development")


def _skin_mask(planes_stack: np.ndarray, led_block: dict | None) -> np.ndarray:
    """Palm mask on plane coordinates from the mean G of the first frames: Otsu threshold, largest component.

    The same rule is applied to every transformed version of a clip, so ROI placement follows the transformed image
    the way landmark-based ROIs would, without needing a hand model inside the study."""
    import cv2

    g = planes_stack.astype(np.float32)
    g = (g - g.min()) / max(float(g.max() - g.min()), 1e-6)
    u8 = (255 * g).astype(np.uint8)
    _, th = cv2.threshold(u8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if led_block:
        x, y, w, h = (int(led_block[k]) // 2 for k in ("x", "y", "w", "h"))
        th[max(0, y - 2): y + h + 2, max(0, x - 2): x + w + 2] = 0
    n, lab, stats, _ = cv2.connectedComponentsWithStats((th > 0).astype(np.uint8))
    if n <= 1:
        return th > 0
    k = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    m = lab == k
    return cv2.erode(m.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)


def _frame_rgb(fr) -> np.ndarray:
    """(h, w, 3) float linear-ish image from a library Frame (Bayer planes or RGB)."""
    d = np.asarray(fr.data)
    if fr.kind == "bayer":
        p = d.astype(np.float32) - float(fr.black_level)
        return np.stack([p[0], 0.5 * (p[1] + p[2]), p[3]], axis=-1)
    x = d.astype(np.float32)
    if x.max() > 1.5:
        x = x / 255.0
    if getattr(fr, "transfer", "linear") == "srgb" or d.dtype == np.uint8:
        x = np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)
    return x


def clip_traces(frames, led_block: dict | None, n_patch=(4, 6), n_mask_frames: int = 10) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict]:
    """One streaming pass: times, whole-palm RGB means (T, 3) and patch means (T, P, 3).

    The first `n_mask_frames` images are buffered to fix the palm mask (and the patch grid over its bounding box);
    every later frame is reduced to its means immediately, so memory stays at a few frames whatever the clip size."""
    import cv2

    buf: list = []
    state: dict[str, Any] = {}
    t_list, means, patches = [], [], []

    def setup(mean_g):
        mask = _skin_mask(mean_g, led_block)
        ys, xs = np.where(mask)
        state["mask"] = mask
        state["rows"] = np.linspace(ys.min(), ys.max() + 1, n_patch[0] + 1).astype(int)
        state["cols"] = np.linspace(xs.min(), xs.max() + 1, n_patch[1] + 1).astype(int)
        state["shape"] = mask.shape

    def reduce(t, im):
        m, rows, cols = state["mask"], state["rows"], state["cols"]
        if im.shape[:2] != state["shape"]:
            sy, sx = im.shape[0] / state["shape"][0], im.shape[1] / state["shape"][1]
            m = cv2.resize(m.astype(np.uint8), (im.shape[1], im.shape[0]), interpolation=cv2.INTER_NEAREST).astype(bool)
            rows, cols = (rows * sy).astype(int), (cols * sx).astype(int)
        t_list.append(t)
        means.append(im[m].mean(axis=0) if m.any() else np.full(3, np.nan))
        pp = []
        for i in range(n_patch[0]):
            for j in range(n_patch[1]):
                sm = m[rows[i]:rows[i + 1], cols[j]:cols[j + 1]]
                pp.append(im[rows[i]:rows[i + 1], cols[j]:cols[j + 1]][sm].mean(axis=0) if sm.any() else np.full(3, np.nan))
        patches.append(pp)

    for fr in frames:
        img = _frame_rgb(fr)
        if "mask" not in state:
            buf.append((fr.t_s, img))
            if len(buf) >= n_mask_frames:
                setup(np.mean([b[1][..., 1] for b in buf if b[1].shape == buf[0][1].shape], axis=0))
                for t, im in buf:
                    reduce(t, im)
                buf = []
            continue
        reduce(fr.t_s, img)
    if "mask" not in state and buf:
        setup(np.mean([b[1][..., 1] for b in buf], axis=0))
        for t, im in buf:
            reduce(t, im)
    info = {"mask_px": int(state["mask"].sum()) if "mask" in state else 0, "n_frames": len(t_list)}
    return np.asarray(t_list, float), np.asarray(means, float), np.asarray(patches, float), info


def _on_grid(t: np.ndarray, x: np.ndarray, grid: np.ndarray, fs: float) -> np.ndarray:
    order = np.argsort(t)
    t, x = t[order], x[order]
    out = np.stack([np.interp(grid, t, x[:, k], left=np.nan, right=np.nan) for k in range(x.shape[1])], axis=1) if x.ndim == 2 else np.interp(grid, t, x)
    gaps = np.where(np.diff(t) > 1.5 / fs)[0]
    for i in gaps:
        out[(grid > t[i]) & (grid < t[i + 1])] = np.nan
    return out


def analyse(t, rgb, patches, window, cfg: Config, methods) -> dict[str, dict]:
    """Rate, SQI and (GREEN only) upstroke time per method on the analysis window."""
    from palmppg.pulse.classical import run_method
    from palmppg.pulse.sqi import snr_band_sqi
    from palmppg.synth.positive_control import reference_recovery

    fs = float(cfg.get("grid.fs"))
    grid = np.arange(window[0], window[1], 1 / fs)
    rg = _on_grid(t, rgb, grid, fs)
    pg = np.stack([_on_grid(t, patches[:, p, :], grid, fs) for p in range(patches.shape[1])], axis=1)
    ok = np.isfinite(rg).all(axis=1)
    if ok.sum() < 10 * fs:
        return {m: {"hr_bpm": np.nan, "sqi": np.nan, "upstroke_s": np.nan, "note": "too few frames"} for m in methods}
    band = tuple(cfg.get("pulse.band_rate"))
    out = {}
    for m in methods:
        try:
            src = np.nan_to_num(pg, nan=np.nanmean(pg)) if m == "2SR" else np.where(np.isfinite(rg), rg, np.nanmean(rg, axis=0))
            x = run_method(m, src, fs, cfg)
            s = snr_band_sqi(x, fs, band, float(cfg.get("pulse.window_s")), float(cfg.get("pulse.step_s")))
            rec = {"hr_bpm": float(s.get("hr_bpm", np.nan)), "sqi": float(s.get("sqi", np.nan)), "upstroke_s": np.nan}
            if m == "GREEN":
                rr = reference_recovery(grid[ok], rg[ok, 1], cfg=cfg)
                rec["hr_dense_bpm"] = float(rr["hr_bpm"])
                rec["upstroke_s"] = float((rr.get("morphology") or {}).get("upstroke_s", np.nan))
            out[m] = rec
        except Exception as exc:  # noqa: BLE001 - a method that fails on a corrupted clip is a failure, recorded
            out[m] = {"hr_bpm": np.nan, "sqi": np.nan, "upstroke_s": np.nan, "error": f"{type(exc).__name__}: {exc}"}
    return out


def _clip_frames(pp, meta, cal, t_ref):
    from palmppg.ingest.bayer import BayerClipReader
    from palmppg.synth.augment import Frame

    reader = BayerClipReader(pp.pi_raw("clip1"), meta)
    black = 0.0 if cal is not None and cal.applied else float(meta.get("black_level", 64))
    try:
        for idx, planes in reader.iter_frames():
            if idx >= len(t_ref):
                break
            p = cal.apply(planes) if cal is not None else planes
            stack = np.stack([p["R"], p["G1"], p["G2"], p["B"]]).astype(np.float32)
            stack = np.clip(stack + 64.0, 0, 1023).astype(np.uint16) if black == 0.0 else stack.astype(np.uint16)
            yield Frame.bayer(stack, float(t_ref[idx]), int(idx), black_level=64.0, white_level=1023.0)
    finally:
        reader.close()


def run_augmentation_study(layout: StudyLayout, work: WorkLayout, cfg: Config, n_clips: int = 100, smoke: bool = False,
                           methods: tuple[str, ...] | None = None, transforms: list[str] | None = None,
                           allowed_streams: tuple[str, ...] = ALLOWED_STREAMS) -> dict:
    from palmppg.core.crf import derive_file
    from palmppg.ingest.calibration import UnitCalibration
    from palmppg.ingest.timestamps import read_frame_times
    from palmppg.synth.augment import TRANSFORMS, apply_chain, severity_grid

    t_start = time.time()
    out_dir = work.root / "augmentation"
    out_dir.mkdir(parents=True, exist_ok=True)
    methods = tuple(methods or (SMOKE_METHODS if smoke else tuple(cfg.get("pulse.methods"))))
    grid = severity_grid(cfg)
    names = transforms or list(TRANSFORMS)
    thr = float(load_frozen_config().get("sqi.threshold"))
    parts = []
    for pp in layout.participants():
        try:
            crf = derive_file(pp.crf, cfg.section("crf"))
        except Exception:  # noqa: BLE001
            continue
        if crf.get("stream") in allowed_streams and (work.clip(pp.study_id, "clip1") / "timeline.json").exists():
            parts.append((pp, crf))
    parts = parts[:n_clips]
    rows, logs = [], {}
    for ci, (pp, crf) in enumerate(parts):
        clip_dir = work.clip(pp.study_id, "clip1")
        tl = Timeline.load(clip_dir / "timeline.json")
        win = (tl.analysis_window.start_s, tl.analysis_window.end_s)
        meta = json.loads(pp.pi_meta("clip1").read_text())
        unit = layout.unit(str(meta.get("unit_id", "unit_01")))
        cal = UnitCalibration.load(unit if unit.exists() else None, meta, black_level=float(cfg.get("pi.black_level")),
                                   sensor_size=(int(cfg.get("pi.width")), int(cfg.get("pi.height"))))
        t_ref = read_frame_times(clip_dir / "pi" / "frame_times.parquet")["t_ref_s"].to_numpy(float)
        led = meta.get("led_block")
        ref_hr = None
        truth_p = pp.pi / "clip1_truth.json"
        if truth_p.exists():
            tr = json.loads(truth_p.read_text())
            hs = tr.get("hr_series") or {}
            tt, hb = np.asarray(hs.get("t_ref_s", []), float), np.asarray(hs.get("hr_bpm", []), float)
            m = (tt >= win[0]) & (tt < win[1])
            ref_hr = float(np.mean(hb[m])) if m.sum() >= 2 else None
        if ref_hr is None:
            ef = clip_dir / "ecg" / "ecg_features.json"
            ref_hr = json.loads(ef.read_text()).get("hr_median_bpm") if ef.exists() else None
        t, rgb, pat, _ = clip_traces(_clip_frames(pp, meta, cal, t_ref), led)
        base = analyse(t, rgb, pat, win, cfg, methods)
        for mth, r in base.items():
            rows.append({"study_id": pp.study_id, "transform": "none", "severity": 0, "level": None, "method": mth, **r,
                         "hr_orig_bpm": r["hr_bpm"], "ref_hr_bpm": ref_hr})
        for name in names:
            levels = grid.get(name) or [None]
            for si, level in enumerate(levels):
                log: list = []
                try:
                    frames = apply_chain(_clip_frames(pp, meta, cal, t_ref), [(name, si)], rng(int(cfg.get("study.seed")), f"aug:{pp.study_id}:{name}:{si}"), log, cfg)
                    t2, rgb2, pat2, _ = clip_traces(frames, led)
                    res = analyse(t2, rgb2, pat2, win, cfg, methods)
                except Exception as exc:  # noqa: BLE001 - a transform that breaks the chain is a recorded failure
                    res = {m: {"hr_bpm": np.nan, "sqi": np.nan, "upstroke_s": np.nan, "error": f"{type(exc).__name__}: {exc}"} for m in methods}
                logs[f"{pp.study_id}:{name}:{si}"] = log
                for mth, r in res.items():
                    rows.append({"study_id": pp.study_id, "transform": name, "severity": si + 1, "level": str(level), "method": mth, **r,
                                 "hr_orig_bpm": base[mth]["hr_bpm"], "ref_hr_bpm": ref_hr, "upstroke_orig_s": base[mth].get("upstroke_s")})
    df = pd.DataFrame(rows)
    if df.empty:
        return {"n_clips": 0, "note": "no eligible clips"}
    df["abs_err_vs_orig_bpm"] = (df["hr_bpm"] - df["hr_orig_bpm"]).abs()
    df["abs_err_vs_ref_bpm"] = (df["hr_bpm"] - df["ref_hr_bpm"]).abs()
    df["covered"] = df["sqi"] >= thr
    df["upstroke_rel_change"] = (df["upstroke_s"] - df.get("upstroke_orig_s")).abs() / df.get("upstroke_orig_s")
    df.to_parquet(out_dir / "degradation.parquet", index=False)
    curves = df.groupby(["transform", "severity", "level", "method"], dropna=False).agg(
        n=("study_id", "nunique"), median_abs_err_vs_ref_bpm=("abs_err_vs_ref_bpm", "median"),
        median_abs_err_vs_orig_bpm=("abs_err_vs_orig_bpm", "median"), median_sqi=("sqi", "median"),
        coverage_pct=("covered", lambda s: 100 * s.mean()), upstroke_rel_change=("upstroke_rel_change", "median")).reset_index()
    curves.to_parquet(out_dir / "curves.parquet", index=False)
    rank = (curves[curves["transform"] != "none"].groupby("transform")["median_abs_err_vs_ref_bpm"].max().sort_values(ascending=False))
    tol = float(cfg.get("augment.rate_preservation_bpm"))
    benign = curves[curves["transform"].isin(BENIGN)]
    lines = ["# Augmentation study: corruptions ranked by the pulse-rate error they cause", "",
             (f"{df['study_id'].nunique()} clips, {len(names)} transforms, methods {', '.join(methods)}. Error = |rate - reference| in bpm, "
              "worst severity, median over clips and methods. Reference = generator truth on synthetic clips, ECG median HR otherwise."), "",
             "| rank | transform | worst median error (bpm) |", "|---|---|---|"]
    lines += [f"| {i + 1} | {k} | {v:.2f} |" for i, (k, v) in enumerate(rank.items())]
    base_err = curves[curves["transform"] == "none"]["median_abs_err_vs_ref_bpm"].median()
    lines += ["", f"Untransformed clips: median error {base_err:.2f} bpm.", "",
              "Synthetic tone shift rows are labelled `SyntheticToneShift` and support no equity claim."]
    (out_dir / "ranking.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    bl = ["# Benign transforms: is the rate recovered from the original preserved?", "", f"Tolerance {tol} bpm (cfg augment.rate_preservation_bpm).", "",
          "| transform | severity | level | method | median abs change from original (bpm) | preserved |", "|---|---|---|---|---|---|"]
    for _, r in benign.iterrows():
        v = r["median_abs_err_vs_orig_bpm"]
        bl.append(f"| {r['transform']} | {r['severity']} | {r['level']} | {r['method']} | {v:.2f} | {bool(np.isfinite(v) and v <= tol)} |")
    (out_dir / "benign_check.md").write_text("\n".join(bl) + "\n", encoding="utf-8")
    (out_dir / "transform_logs.json").write_text(json.dumps(logs, default=str)[:5_000_000], encoding="utf-8")
    abl = training_ablation(df, parts, cfg)
    (out_dir / "ablation.json").write_text(json.dumps(abl, indent=1, default=float), encoding="utf-8")
    (out_dir / "ablation.md").write_text(abl["markdown"], encoding="utf-8")
    return {"n_clips": int(df["study_id"].nunique()), "n_transforms": len(names), "methods": list(methods), "smoke": smoke,
            "report": str(out_dir / "ranking.md"), "elapsed_s": round(time.time() - t_start, 1)}


def training_ablation(df: pd.DataFrame, parts, cfg: Config) -> dict:
    """With versus without augmented training copies, participant-grouped CV; augmented copies of a validation
    participant are never used (section 8). Tasks: pulse rate (reference HR) and BP tertile (cut points from the
    training fold) from per-clip spectral features (rate and SQI of each method)."""
    from sklearn.linear_model import LogisticRegression, RidgeCV

    from palmppg.features.splits import grouped_kfold

    feats = df.pivot_table(index=["study_id", "transform", "severity"], columns="method", values=["hr_bpm", "sqi"]).reset_index()
    feats.columns = ["__".join(c for c in col if c) if isinstance(col, tuple) else col for col in feats.columns]
    crf = {pp.study_id: c for pp, c in parts}
    feats["ref_hr"] = feats["study_id"].map(df.groupby("study_id")["ref_hr_bpm"].first())
    feats["sbp"] = feats["study_id"].map({k: v.get("bp_target_sbp") for k, v in crf.items()})
    xcols = [c for c in feats.columns if c.startswith(("hr_bpm__", "sqi__"))]
    ids = sorted(feats["study_id"].unique())
    res: dict[str, Any] = {"n_participants": len(ids), "caveat": "small-sample ablation; differences at this n are not distinguishable from noise"}
    if len(ids) < 10:
        res["status"] = "not estimable"
        res["markdown"] = f"# Training ablation\n\nNot estimable with {len(ids)} participants (needs at least 10).\n"
        return res
    folds = grouped_kfold(ids, 5, int(cfg.get("study.seed")))
    X = feats[xcols].to_numpy(float)
    X = np.where(np.isfinite(X), X, np.nanmedian(X, axis=0))
    out = {}
    for task in ("pulse_rate", "bp_tertile"):
        for arm in ("without_augmentation", "with_augmentation"):
            errs, accs = [], []
            for tr, te in folds:
                tr_m = feats["study_id"].isin(tr).to_numpy() & (np.ones(len(feats), bool) if arm == "with_augmentation" else (feats["transform"] == "none").to_numpy())
                te_m = feats["study_id"].isin(te).to_numpy() & (feats["transform"] == "none").to_numpy()
                if task == "pulse_rate":
                    y = feats["ref_hr"].to_numpy(float)
                    ok = tr_m & np.isfinite(y)
                    if ok.sum() < 5 or te_m.sum() == 0:
                        continue
                    p = RidgeCV(alphas=np.logspace(-2, 3, 12)).fit(X[ok], y[ok]).predict(X[te_m])
                    errs += list(np.abs(p - y[te_m]))
                else:
                    sbp = feats["sbp"].to_numpy(float)
                    orig_tr = feats["study_id"].isin(tr).to_numpy() & (feats["transform"] == "none").to_numpy()
                    cuts = np.nanpercentile(sbp[orig_tr], [100 / 3, 200 / 3])
                    y = np.digitize(sbp, cuts)
                    ok = tr_m & np.isfinite(sbp)
                    if len(np.unique(y[ok])) < 2 or te_m.sum() == 0:
                        continue
                    p = LogisticRegression(max_iter=2000).fit(X[ok], y[ok]).predict(X[te_m])
                    accs += list(p == y[te_m])
            out[f"{task}:{arm}"] = {"mae_bpm": float(np.mean(errs)) if errs else None, "n": len(errs)} if task == "pulse_rate" else \
                {"accuracy": float(np.mean(accs)) if accs else None, "chance": 1 / 3, "n": len(accs)}
    res["results"] = out
    lines = ["# Training ablation (with versus without augmented copies)", "", res["caveat"] + ".", "", "| task | arm | metric | n |", "|---|---|---|---|"]
    for k, v in out.items():
        task, arm = k.split(":")
        metric = f"MAE {v['mae_bpm']:.2f} bpm" if "mae_bpm" in v and v["mae_bpm"] is not None else (f"accuracy {v['accuracy']:.2f} (chance 0.33)" if v.get("accuracy") is not None else "NA")
        lines.append(f"| {task} | {arm} | {metric} | {v['n']} |")
    res["status"] = "ok"
    res["markdown"] = "\n".join(lines) + "\n"
    return res
