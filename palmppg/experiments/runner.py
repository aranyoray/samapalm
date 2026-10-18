"""E0..E17 runners (protocol section 9). Each returns a JSON-serialisable dict and writes tables under
work/experiments/<E>/. Every regression or classification table carries the predict-the-mean and the
demographics-only baselines; every model is wrapped in TrackGuard; failed and abstained clips are failures.

Which camera answers which track (D-022):
  product_candidate : phone, and pi_proxy (Pi frames through the 8-bit sRGB H.264 chain)
  science           : pi (raw Bayer) plus ECG-derived and PAT features where an endpoint needs them
The pilot go/no-go criteria are evaluated on the Pi (lab reference), with phone and pi_proxy reported alongside.
"""
from __future__ import annotations

import datetime as dt
import json
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from palmppg.core.config import CONFIG_DIR, Config, load_frozen_config, load_pipeline_config, verify_frozen
from palmppg.eval.metrics import bp_metrics, pulse_rate_metrics, rhythm_metrics
from palmppg.experiments import cv as cvm
from palmppg.experiments.data import (
    STATIC_GROUPS,
    TEMPORAL_GROUPS,
    demographics_columns,
    group_columns,
    load_features,
    numeric_matrix,
    valid_mask,
)

TRACK_CAMERAS = {"product_candidate": ("phone", "pi_proxy"), "science": ("pi",)}
SYNTHETIC_NOTE = "Synthetic cohort: numbers measure the pipeline on generated data and say nothing about people."


# --------------------------------------------------------------------------- utilities
def _jsonable(o):
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, pd.DataFrame):
        return o.replace({np.nan: None}).to_dict(orient="records")
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (float, np.floating)):
        f = float(o)
        return f if np.isfinite(f) else None
    if isinstance(o, np.ndarray):
        return _jsonable(o.tolist())
    return o


def experiment_config() -> dict:
    return yaml.safe_load((CONFIG_DIR / "experiments" / "experiments.yaml").read_text(encoding="utf-8"))


class Context:
    """Shared state for one run: config, feature frames, output dir, seed, folds per camera."""

    def __init__(self, cfg: Config, work_root: Path, frames: dict[str, pd.DataFrame] | None = None, synthetic: bool | None = None):
        self.cfg = cfg
        self.work_root = Path(work_root)
        self.out = self.work_root / "experiments"
        self.out.mkdir(parents=True, exist_ok=True)
        self.frames = frames if frames is not None else load_features(self.work_root)
        self.exp = experiment_config()
        self.seed = int(cfg.get("study.seed"))
        d = self.exp.get("defaults", {}).get("cv", {})
        self.n_splits = int(d.get("n_outer", cfg.get("splits.n_outer")))
        self.demo_cols = [c for c in demographics_columns(cfg.with_overrides({"experiments": {"demographics_columns": self.exp["defaults"]["demographics_columns"]}}))]
        self.folds: dict[str, Any] = {}
        any_df = next(iter(self.frames.values())) if self.frames else pd.DataFrame()
        self.synthetic = synthetic if synthetic is not None else bool(len(any_df) and any_df["study_id"].astype(str).str.startswith("SWHT-PP-003-").all()
                                                                       and (self.work_root.name.startswith(("synth", "positive")) or "synth" in str(self.work_root)))

    def frame(self, camera: str) -> pd.DataFrame | None:
        return self.frames.get(camera)

    def folds_for(self, camera: str):
        if camera not in self.folds:
            self.folds[camera] = cvm.folds_for(self.frames[camera], self.n_splits, self.seed)
        return self.folds[camera]

    def demo(self, df: pd.DataFrame) -> pd.DataFrame:
        return numeric_matrix(df, [c for c in self.demo_cols if c in df.columns])

    def write(self, name: str, result: dict) -> dict:
        d = self.out / name
        d.mkdir(parents=True, exist_ok=True)
        result.setdefault("synthetic", self.synthetic)
        if self.synthetic:
            result.setdefault("note", SYNTHETIC_NOTE)
        (d / "results.json").write_text(json.dumps(_jsonable(result), indent=1), encoding="utf-8")
        md = result.get("markdown")
        if md:
            (d / "results.md").write_text(md, encoding="utf-8")
        return result


def _fmt(v, nd=2):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "NA"
    if isinstance(v, (float, np.floating)):
        return f"{v:.{nd}f}"
    return str(v)


def bp_table(rows: list[dict], title: str) -> str:
    lines = [f"## {title}", "", "| track | camera | model | n attempted | n covered | coverage % | bias | error SD | MAE | LoA low | LoA high |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        m = r["metrics"]
        lines.append(f"| {r['track']} | {r['camera']} | {r['model']} | {m.get('n_attempted')} | {m.get('n')} | {_fmt(m.get('coverage_pct'),1)} | "
                     f"{_fmt(m.get('bias'))} | {_fmt(m.get('error_sd'))} | {_fmt(m.get('mae'))} | {_fmt(m.get('loa_low'))} | {_fmt(m.get('loa_high'))} |")
    return "\n".join(lines) + "\n"


def _bp(y, p) -> dict:
    m = bp_metrics(y, p)
    return {k: v for k, v in m.items() if not isinstance(v, pd.DataFrame)}


# --------------------------------------------------------------------------- BP regression core (E0, E3, E5)
def bp_regression(ctx: Context, target: str, track: str, camera: str, arms: dict[str, list[str]], model: str = "ridge",
                  shuffled_arm: str | None = None) -> list[dict]:
    """Out-of-fold predictions per arm plus both baselines; returns metric rows and stores predictions."""
    df = ctx.frame(camera)
    if df is None or target not in df.columns:
        return []
    y = pd.to_numeric(df[target], errors="coerce").to_numpy(float)
    valid = valid_mask(df, camera)
    folds = ctx.folds_for(camera)
    demo = ctx.demo(df)
    base = cvm.baseline_predictions(df, y, valid, demo, ctx.n_splits, ctx.seed, folds)
    rows, preds = [], {"study_id": df["study_id"].to_numpy(), "y": y, "valid": valid}
    for name, p in base.items():
        rows.append({"track": track, "camera": camera, "model": name, "target": target, "metrics": _bp(y, p)})
        preds[name] = p
    model_fn = (lambda: cvm.gbdt_model(ctx.seed)) if model == "lightgbm" else cvm.ridge_model
    for arm, cols in arms.items():
        cols = [c for c in cols if c in df.columns]
        if not cols:
            rows.append({"track": track, "camera": camera, "model": arm, "target": target, "metrics": {"n_attempted": len(df), "n": 0, "note": "no features"}})
            continue
        X = numeric_matrix(df, cols)
        if arm == shuffled_arm:
            temporal = [c for c in X.columns if c.split("__")[0] in TEMPORAL_GROUPS]
            X = cvm.shuffled_within_folds(X, df, temporal, folds, ctx.seed)
        p = cvm.cv_predict(df, X, y, valid, model_fn, track, ctx.n_splits, ctx.seed, folds=folds)
        rows.append({"track": track, "camera": camera, "model": arm, "target": target, "n_features": X.shape[1], "metrics": _bp(y, p)})
        preds[arm] = p
    pd.DataFrame(preds).to_parquet(ctx.out / f"preds_{target}_{track}_{camera}_{model}.parquet", index=False)
    return rows


def arms_for(ctx: Context, track: str, camera: str, include_ecg: bool = False) -> dict[str, list[str]]:
    df = ctx.frame(camera)
    static = group_columns(df, track, camera, STATIC_GROUPS)
    temporal = group_columns(df, track, camera, TEMPORAL_GROUPS)
    demo = [c for c in ctx.demo_cols if c in df.columns]
    arms = {"static_only": static + demo, "temporal_only": temporal + demo, "static_plus_temporal": static + temporal + demo}
    if include_ecg and track == "science":
        ecg = group_columns(df, track, camera, ("ecg", "pat"))
        arms["static_temporal_ecg"] = static + temporal + ecg + demo
    return arms


# --------------------------------------------------------------------------- experiments
def e0_baselines(ctx: Context) -> dict:
    rows = []
    for track, cams in TRACK_CAMERAS.items():
        for cam in cams:
            for tgt in ("bp_target_sbp", "bp_target_dbp"):
                rows += [r for r in bp_regression(ctx, tgt, track, cam, {}) if r["model"] in ("predict_mean", "demographics_only")]
    md = "# E0 baselines\n\n" + bp_table([r for r in rows if r["target"] == "bp_target_sbp"], "SBP") + "\n" + bp_table([r for r in rows if r["target"] == "bp_target_dbp"], "DBP")
    return ctx.write("E0", {"status": "ok", "rows": rows, "markdown": md})


def e1_pulse_rate(ctx: Context) -> dict:
    tol = float(load_frozen_config().get("go_no_go.pulse_rate_tolerance_bpm"))
    rows, per_band = [], []
    for cam in ("pi", "phone", "pi_proxy"):
        df = ctx.frame(cam)
        if df is None:
            continue
        # D-024: median-interval rates on both sides (a missed beat doubles one interval and drags a mean)
        ref = pd.to_numeric(df.get("ecg__hr_median_bpm", df.get("ecg__hr_mean_bpm")), errors="coerce").to_numpy(float)
        med_ibi = pd.to_numeric(df.get(f"hrv__{cam}__median_ibi_ms"), errors="coerce").to_numpy(float)
        hr = np.where(med_ibi > 0, 60000.0 / med_ibi, np.nan)
        valid = valid_mask(df, cam)
        hr_valid = np.where(valid, hr, np.nan)
        m_all = pulse_rate_metrics(np.where(np.isfinite(hr), hr, np.nan), ref, tol)     # all attempted
        m_valid = pulse_rate_metrics(hr[valid], ref[valid], tol) if valid.any() else {"n": 0}
        rows.append({"camera": cam, "subset": "valid clips", **m_valid})
        rows.append({"camera": cam, "subset": "all attempted (failures count)", **pulse_rate_metrics(hr_valid, ref, tol)})
        rows.append({"camera": cam, "subset": "all attempted, ignoring QC", **m_all})
        for band, g in df.groupby("mst_band"):
            v = valid_mask(g, cam)
            mi = pd.to_numeric(g.get(f"hrv__{cam}__median_ibi_ms"), errors="coerce").to_numpy(float)
            hb = np.where(v & (mi > 0), 60000.0 / np.where(mi > 0, mi, 1.0), np.nan)
            per_band.append({"camera": cam, "mst_band": band, "n_attempted": len(g), **pulse_rate_metrics(hb, pd.to_numeric(g.get("ecg__hr_median_bpm", g.get("ecg__hr_mean_bpm")), errors="coerce"), tol)})
    lines = ["# E1 pulse rate versus ECG HR", "", f"Tolerance {tol} bpm (frozen). Pulse rate = 60 / median beat interval over the analysis window, against the ECG median-interval HR (D-024).", "",
             "| camera | subset | n | MAE (bpm) | bias (bpm) | within tolerance % |", "|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['camera']} | {r['subset']} | {r.get('n')} | {_fmt(r.get('mae'))} | {_fmt(r.get('bias'))} | {_fmt(r.get('within_tol_pct'),1)} |")
    lines += ["", "## By MST band (all attempted, failures count; every cell here is under 20 at pilot-test scale and is shown unpooled with its n)", "", "| camera | MST band | n attempted | within tolerance % |", "|---|---|---|---|"]
    for r in per_band:
        lines.append(f"| {r['camera']} | {r['mst_band']} | {r['n_attempted']} | {_fmt(r.get('within_tol_pct'),1)} |")
    return ctx.write("E1", {"status": "ok", "tolerance_bpm": tol, "rows": rows, "per_band": per_band, "markdown": "\n".join(lines) + "\n"})


def e2_coverage(ctx: Context) -> dict:
    from sklearn.linear_model import LogisticRegression

    rows, models = [], []
    for cam, df in ctx.frames.items():
        valid = valid_mask(df, cam)
        reasons = df.get(f"qc__{cam}__reasons", pd.Series([""] * len(df))).fillna("").astype(str)
        counts: dict[str, int] = {}
        for r in reasons:
            for k in [x for x in r.split(";") if x]:
                counts[k] = counts.get(k, 0) + 1
        sqi = pd.to_numeric(df.get(f"qc__{cam}__sqi_best"), errors="coerce")
        rows.append({"camera": cam, "n_attempted": len(df), "n_valid": int(valid.sum()), "coverage_pct": 100 * valid.mean() if len(df) else None,
                     "sqi_median": float(sqi.median()) if sqi.notna().any() else None, "failure_reasons": counts})
        X = numeric_matrix(df, [c for c in ("mst_band", "flag_hypertension", "flag_diabetes", "flag_chronic_kidney_disease", "flag_arrhythmia",
                                             "flag_anaemia_thalassaemia", f"qc__{cam}__landmark_jitter_px") if c in df.columns])
        fail = (~valid).astype(int)
        if X.shape[1] and 0 < fail.sum() < len(fail):
            Xf = X.fillna(X.median())
            lr = LogisticRegression(max_iter=2000).fit((Xf - Xf.mean()) / Xf.std(ddof=0).replace(0, 1), fail)
            models.append({"camera": cam, "coef_per_sd": dict(zip(X.columns, lr.coef_[0].tolist(), strict=True)), "n": len(fail), "n_fail": int(fail.sum())})
        else:
            models.append({"camera": cam, "note": "failure model not estimable (no variation in failure or covariates)"})
    lines = ["# E2 SQI and coverage", "", "Failed and abstained clips count as failures (protocol 11.3).", "",
             "| camera | attempted | valid | coverage % | median best SQI | failure reasons |", "|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['camera']} | {r['n_attempted']} | {r['n_valid']} | {_fmt(r['coverage_pct'],1)} | {_fmt(r['sqi_median'])} | "
                     + ", ".join(f"{k} {v}" for k, v in sorted(r["failure_reasons"].items(), key=lambda kv: -kv[1])) + " |")
    lines += ["", "Logistic failure model coefficients (log-odds per SD; exploratory, n tests = number of coefficients):", ""]
    for m in models:
        lines.append(f"- {m['camera']}: " + (", ".join(f"{k} {v:+.2f}" for k, v in m.get("coef_per_sd", {}).items()) or m.get("note", "")))
    return ctx.write("E2", {"status": "ok", "rows": rows, "failure_models": models, "markdown": "\n".join(lines) + "\n"})


def e3_bp_features(ctx: Context) -> dict:
    rows = []
    for track, cams in TRACK_CAMERAS.items():
        for cam in cams:
            if ctx.frame(cam) is None:
                continue
            arms = {"static_plus_temporal": arms_for(ctx, track, cam)["static_plus_temporal"]}
            for tgt in ("bp_target_sbp", "bp_target_dbp", "bp_target_23_sbp"):
                rows += bp_regression(ctx, tgt, track, cam, arms, model="ridge")
                if tgt != "bp_target_23_sbp":
                    rows += [dict(r, model=r["model"] + " (lightgbm)") for r in bp_regression(ctx, tgt, track, cam, arms, model="lightgbm") if r["model"] == "static_plus_temporal"]
    md = "# E3 BP from features\n\n" + "\n".join(bp_table([r for r in rows if r["target"] == t], t) for t in ("bp_target_sbp", "bp_target_dbp", "bp_target_23_sbp"))
    return ctx.write("E3", {"status": "ok", "rows": rows, "markdown": md})


def e4_bp_deep(ctx: Context) -> dict:
    """1D CNN on per-beat sequences (IBI, amplitude, quality) from beats.parquet, grouped CV, both baselines."""
    try:
        import torch  # noqa: F401
    except ImportError:
        return ctx.write("E4", {"status": "skipped", "reason": "torch not installed"})
    from palmppg.models.temporal import TorchSequenceRegressor

    rows = []
    for track, cams in TRACK_CAMERAS.items():
        for cam in cams:
            df = ctx.frame(cam)
            if df is None:
                continue
            seqs, ok = [], []
            for sid in df["study_id"]:
                p = ctx.work_root / str(sid) / "clip1" / cam / "beats.parquet"
                if p.exists():
                    b = pd.read_parquet(p)
                    cols = [c for c in ("ibi_s", "amplitude", "quality") if c in b.columns]
                    seqs.append(b[cols].fillna(0.0).to_numpy(np.float32)[:96])
                    ok.append(len(b) >= 10)
                else:
                    seqs.append(np.zeros((1, 3), np.float32))
                    ok.append(False)
            y = pd.to_numeric(df["bp_target_sbp"], errors="coerce").to_numpy(float)
            valid = valid_mask(df, cam) & np.array(ok)
            folds = ctx.folds_for(cam)
            pred = np.full(len(df), np.nan)
            ids = df["study_id"].astype(str).to_numpy()
            for tr_ids, te_ids in folds:
                tr = np.isin(ids, list(tr_ids)) & valid
                te = np.isin(ids, list(te_ids)) & valid
                if tr.sum() < 8 or te.sum() == 0:
                    continue
                m = TorchSequenceRegressor("conv1d", epochs=40, lr=1e-3, seed=ctx.seed)
                m.fit([seqs[i] for i in np.where(tr)[0]], y[tr])
                pred[te] = m.predict([seqs[i] for i in np.where(te)[0]])
            base = cvm.baseline_predictions(df, y, valid_mask(df, cam), ctx.demo(df), ctx.n_splits, ctx.seed, folds)
            for name, p in {**base, "conv1d_beats": pred}.items():
                rows.append({"track": track, "camera": cam, "model": name, "target": "bp_target_sbp", "metrics": _bp(y, p)})
    return ctx.write("E4", {"status": "ok", "rows": rows, "markdown": "# E4 BP deep (1D CNN on beat sequences)\n\n" + bp_table(rows, "SBP")})


def e5_static_vs_temporal(ctx: Context) -> dict:
    margin = float(load_frozen_config().get("go_no_go.temporal_vs_demographics_sbp_sd_reduction_mmhg"))
    rows = []
    for track, cams in TRACK_CAMERAS.items():
        for cam in cams:
            if ctx.frame(cam) is None:
                continue
            arms = arms_for(ctx, track, cam)
            arms["pulse_shuffled_control"] = arms["static_plus_temporal"]
            for tgt in ("bp_target_sbp", "bp_target_dbp"):
                rows += bp_regression(ctx, tgt, track, cam, arms, model="ridge", shuffled_arm="pulse_shuffled_control")
    summary = []
    for track, cams in TRACK_CAMERAS.items():
        for cam in cams:
            r = {x["model"]: x["metrics"] for x in rows if x["camera"] == cam and x["track"] == track and x["target"] == "bp_target_sbp"}
            if "demographics_only" in r and "temporal_only" in r:
                red = (r["demographics_only"].get("error_sd") or np.nan) - (r["temporal_only"].get("error_sd") or np.nan)
                summary.append({"track": track, "camera": cam, "sbp_sd_demographics": r["demographics_only"].get("error_sd"),
                                "sbp_sd_temporal": r["temporal_only"].get("error_sd"), "reduction_mmhg": red, "margin_mmhg": margin,
                                "meets_margin": bool(np.isfinite(red) and red >= margin),
                                "sbp_sd_shuffled": r.get("pulse_shuffled_control", {}).get("error_sd")})
    lines = ["# E5 static versus temporal", "", f"Pilot margin: temporal features reduce SBP error SD by at least {margin} mmHg over demographics only (frozen).", "",
             "| track | camera | SBP SD demographics | SBP SD temporal | reduction | meets margin | SBP SD pulse-shuffled |", "|---|---|---|---|---|---|---|"]
    for s in summary:
        lines.append(f"| {s['track']} | {s['camera']} | {_fmt(s['sbp_sd_demographics'])} | {_fmt(s['sbp_sd_temporal'])} | {_fmt(s['reduction_mmhg'])} | {s['meets_margin']} | {_fmt(s['sbp_sd_shuffled'])} |")
    md = "\n".join(lines) + "\n\n" + bp_table([r for r in rows if r["target"] == "bp_target_sbp"], "SBP, all arms") + "\n" + bp_table([r for r in rows if r["target"] == "bp_target_dbp"], "DBP, all arms")
    return ctx.write("E5", {"status": "ok", "rows": rows, "summary": summary, "markdown": md})


def _results_rows(ctx: Context, camera: str, track: str, target: str = "bp_target_sbp", arm: str = "static_plus_temporal") -> pd.DataFrame | None:
    p = ctx.out / f"preds_{target}_{track}_{camera}_ridge.parquet"
    df = ctx.frame(camera)
    if not p.exists() or df is None:
        return None
    pr = pd.read_parquet(p)
    out = df[["study_id", "mst_band", "age", "sex_f", "bmi", target]].copy()
    out["pred"] = pr[arm].to_numpy() if arm in pr.columns else np.nan
    out["error"] = out["pred"] - pd.to_numeric(out[target], errors="coerce")
    out["covered"] = np.isfinite(out["pred"])
    out["bp_target"] = pd.to_numeric(out[target], errors="coerce")
    return out


def e6_equity(ctx: Context) -> dict:
    from palmppg.audits.equity import equity_audit, equity_markdown, mst_leakage_probe

    res: dict[str, Any] = {"status": "ok", "audits": {}, "leakage_probe": {}}
    md = ["# E6 equity", ""]
    for track, cams in TRACK_CAMERAS.items():
        for cam in cams:
            rr = _results_rows(ctx, cam, track)
            if rr is None:
                continue
            try:
                a = equity_audit(rr, covariates=("age", "sex_f", "bmi", "bp_target"), cfg=ctx.cfg)
                res["audits"][f"{track}:{cam}"] = a
                md += [f"## {track} / {cam}", "", equity_markdown(a), ""]
            except Exception as exc:  # noqa: BLE001 - an inestimable audit is reported, not hidden
                res["audits"][f"{track}:{cam}"] = {"error": f"{type(exc).__name__}: {exc}"}
                md += [f"## {track} / {cam}", "", f"Not estimable: {exc}", ""]
            df = ctx.frame(cam)
            cols = group_columns(df, track, cam, TEMPORAL_GROUPS)
            try:
                lp = mst_leakage_probe(df, cols, seed=ctx.seed)
                res["leakage_probe"][f"{track}:{cam}"] = lp
                md += [f"MST leakage probe ({track}/{cam}): " + json.dumps(_jsonable({k: v for k, v in lp.items() if not isinstance(v, (dict, list, pd.DataFrame))}))[:600], ""]
            except Exception as exc:  # noqa: BLE001
                res["leakage_probe"][f"{track}:{cam}"] = {"error": str(exc)}
    md.append("Synthetic tone shifts in generated data support no equity claim." if ctx.synthetic else "")
    res["markdown"] = "\n".join(md) + "\n"
    return ctx.write("E6", res)


def _binary_task(ctx: Context, name: str, y_fn: Callable[[pd.DataFrame], np.ndarray], feature_groups: dict[str, tuple[str, ...]],
                 operating_point: float = 0.5, tracks=TRACK_CAMERAS) -> dict:
    rows = []
    for track, cams in tracks.items():
        for cam in cams:
            df = ctx.frame(cam)
            if df is None:
                continue
            y = y_fn(df)
            keep = np.isfinite(y)
            if keep.sum() < 6 or len(np.unique(y[keep])) < 2:
                rows.append({"track": track, "camera": cam, "model": "all", "note": f"not estimable: {int(keep.sum())} labelled, {int(np.nansum(y))} positive"})
                continue
            valid = valid_mask(df, cam) & keep
            folds = ctx.folds_for(cam)
            prev = float(np.nanmean(y[keep]))
            demo = ctx.demo(df)
            preds = {"predict_prevalence": np.where(keep, prev, np.nan)}
            if demo.shape[1]:
                preds["demographics_only"] = cvm.cv_predict(df, demo, np.nan_to_num(y), keep, lambda: cvm.logistic_model(ctx.seed), "product_candidate",
                                                            ctx.n_splits, ctx.seed, task="classification", folds=folds)
            for fs_name, groups in feature_groups.items():
                cols = group_columns(df, track, cam, groups) + list(demo.columns)
                X = numeric_matrix(df, cols)
                preds[fs_name] = cvm.cv_predict(df, X, np.nan_to_num(y), valid, lambda: cvm.logistic_model(ctx.seed), track, ctx.n_splits, ctx.seed,
                                                task="classification", folds=folds)
            for m, p in preds.items():
                yy, pp = y[keep], p[keep]
                try:
                    met = rhythm_metrics(yy.astype(int), pp, operating_point)
                except Exception as exc:  # noqa: BLE001
                    met = {"error": str(exc)}
                rows.append({"track": track, "camera": cam, "model": m, "n": int(keep.sum()), "n_pos": int(yy.sum()), "metrics": met})
    lines = [f"# {name}", "", f"Operating point {operating_point} (pre-specified). Exact binomial intervals. Failed clips count as negative predictions.", "",
             "| track | camera | model | n | positives | AUROC | sensitivity | specificity |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        m = r.get("metrics", {})
        lines.append(f"| {r['track']} | {r['camera']} | {r['model']} | {r.get('n', '')} | {r.get('n_pos', '')} | {_fmt(m.get('auroc', m.get('auc')))} | "
                     f"{_fmt(m.get('sensitivity'))} | {_fmt(m.get('specificity'))} | {r.get('note', '')}")
    return {"status": "ok", "rows": rows, "markdown": "\n".join(lines) + "\n"}


def e7_rhythm(ctx: Context) -> dict:
    hard = set(ctx.cfg.get("ecg.hard_non_af"))

    def af_vs_sinus(df):
        r = df.get("clinician__rhythm", pd.Series([None] * len(df))).astype(str)
        return np.where(r == "af", 1.0, np.where(r == "sinus", 0.0, np.nan))

    def af_vs_hard(df):
        r = df.get("clinician__rhythm", pd.Series([None] * len(df))).astype(str)
        return np.where(r == "af", 1.0, np.where(r.isin(hard), 0.0, np.nan))

    groups = {"irregularity_only": ("hrv",), "morphology": ("hrv", "morphology", "apg")}
    a = _binary_task(ctx, "E7 rhythm: AF versus sinus", af_vs_sinus, groups)
    b = _binary_task(ctx, "E7 rhythm: AF versus hard non-AF", af_vs_hard, groups)
    return ctx.write("E7", {"status": "ok", "af_vs_sinus": a, "af_vs_hard_non_af": b, "markdown": a["markdown"] + "\n" + b["markdown"]})


def _regression_task(ctx: Context, name: str, target: str, feature_groups: tuple[str, ...]) -> dict:
    rows = []
    for track, cams in TRACK_CAMERAS.items():
        for cam in cams:
            df = ctx.frame(cam)
            if df is None or target not in df.columns or pd.to_numeric(df[target], errors="coerce").notna().sum() < 8:
                rows.append({"track": track, "camera": cam, "model": "all", "target": target, "metrics": {"note": "fewer than 8 labelled participants"}})
                continue
            cols = group_columns(df, track, cam, feature_groups)
            rows += bp_regression(ctx, target, track, cam, {"features": cols + [c for c in ctx.demo_cols if c in df.columns and c != target]})
    return {"status": "ok", "rows": rows, "markdown": f"# {name}\n\n" + bp_table([r for r in rows if "n_attempted" in r["metrics"] or r["metrics"].get("n") is not None], target)}


def e8_anaemia(ctx: Context) -> dict:
    return ctx.write("E8", _regression_task(ctx, "E8 haemoglobin (where Hb exists)", "hb_gdl", ("static_colour", "perfusion")))


def e9_vascular_age(ctx: Context) -> dict:
    saved = ctx.demo_cols
    ctx.demo_cols = [c for c in saved if c != "age"]
    try:
        r = _regression_task(ctx, "E9 vascular age (age from morphology and APG)", "age", ("morphology", "apg", "hrv"))
    finally:
        ctx.demo_cols = saved
    return ctx.write("E9", r)


def e10_fm(ctx: Context) -> dict:
    from palmppg.models import fm

    status = {}
    for name in ("papagei_s", "siamquality"):
        try:
            fm.load_embedder(name, None)
            status[name] = "loaded"
        except (FileNotFoundError, TypeError, ValueError, KeyError) as exc:
            status[name] = f"not run: {exc}"[:300]
    return ctx.write("E10", {"status": "skipped", "reason": "foundation-model weights are user-supplied and not present", "embedders": status,
                             "markdown": "# E10 foundation-model transfer\n\nNot run: PaPaGei and SiamQuality weights are not in this environment. "
                                         "No random-init stand-in is reported as a result.\n"})


def e11_shortcut(ctx: Context) -> dict:
    from palmppg.audits.shortcut import shortcut_audit, shortcut_markdown

    res, md = {"status": "ok", "audits": {}}, ["# E11 shortcut audit", ""]
    nuis = list(ctx.exp["experiments"]["E11"]["nuisance"])
    for track, cams in TRACK_CAMERAS.items():
        for cam in cams:
            df = ctx.frame(cam)
            if df is None:
                continue
            rr = _results_rows(ctx, cam, track)
            d2 = df.copy()
            if rr is not None:
                d2["residual"] = rr["error"].to_numpy()
            cols = group_columns(df, track, cam, STATIC_GROUPS + TEMPORAL_GROUPS)
            try:
                a = shortcut_audit(d2, cols, [c for c in nuis if c in d2.columns and d2[c].nunique() > 1], seed=ctx.seed,
                                   residual_col="residual" if rr is not None else None, min_level_n=3)
                res["audits"][f"{track}:{cam}"] = a.table
                md += [f"## {track} / {cam}", "", shortcut_markdown(a.table, rr is not None), ""]
            except Exception as exc:  # noqa: BLE001
                res["audits"][f"{track}:{cam}"] = {"error": str(exc)}
                md += [f"## {track} / {cam}", "", f"Not estimable: {exc}", ""]
    single = [c for c in nuis if all((f is None or c not in f.columns or f[c].nunique() <= 1) for f in ctx.frames.values())]
    if single:
        md.append(f"Nuisance variables with a single level in this data (not auditable): {', '.join(single)}.")
    res["markdown"] = "\n".join(md) + "\n"
    return ctx.write("E11", res)


def e12_elevated(ctx: Context) -> dict:
    def y(df):
        c = df.get("bp_category", pd.Series([None] * len(df))).astype(str)
        return np.where(c.isin(["stage 1", "stage 2"]), 1.0, np.where(c.isin(["normal", "elevated"]), 0.0, np.nan))

    return ctx.write("E12", _binary_task(ctx, "E12 current elevated BP (stage 1 or above on the cuff mean)", y,
                                          {"static_plus_temporal": STATIC_GROUPS + TEMPORAL_GROUPS}))


def e13_glucose(ctx: Context) -> dict:
    a = _regression_task(ctx, "E13 glucose boundary: capillary glucose", "glucose_mgdl", STATIC_GROUPS + TEMPORAL_GROUPS)
    b = _regression_task(ctx, "E13 glucose boundary: HbA1c", "hba1c", STATIC_GROUPS + TEMPORAL_GROUPS)
    return ctx.write("E13", {"status": "ok", "glucose": a, "hba1c": b, "markdown": a["markdown"] + "\n" + b["markdown"]
                             + "\nReported in full whatever the direction; no diabetes claim is made from any number here.\n"})


def e14_repeatability(ctx: Context) -> dict:
    re_frames = load_features(ctx.work_root, clip_ids=("clip1b",))
    if not re_frames:
        return ctx.write("E14", {"status": "skipped", "reason": "no re-shot clips (clip1b) in this data",
                                 "markdown": "# E14 repeatability\n\nNo re-shot clips in this data; nothing to report.\n"})
    rows = []
    for cam, rb in re_frames.items():
        a = ctx.frame(cam)
        if a is None:
            continue
        m = a.merge(rb, on="study_id", suffixes=("_1", "_2"))
        for feat in (f"hrv__{cam}__mean_hr_bpm", f"qc__{cam}__sqi_best"):
            if f"{feat}_1" in m:
                x1, x2 = pd.to_numeric(m[f"{feat}_1"], errors="coerce"), pd.to_numeric(m[f"{feat}_2"], errors="coerce")
                ok = x1.notna() & x2.notna()
                d = (x1 - x2)[ok]
                rows.append({"camera": cam, "feature": feat, "n_pairs": int(ok.sum()), "within_sd": float(d.std(ddof=1) / np.sqrt(2)) if ok.sum() > 2 else None})
    return ctx.write("E14", {"status": "ok", "rows": rows})


def e15_extras(ctx: Context) -> dict:
    rows = []
    df = ctx.frame("pi")
    if df is not None:
        for c in [c for c in df.columns if c.startswith("perfusion__pi__") and c.endswith("__G")]:
            v = pd.to_numeric(df[c], errors="coerce")
            rows.append({"feature": c, "n": int(v.notna().sum()), "median": float(v.median()) if v.notna().any() else None})
        r = pd.to_numeric(df.get("resp__pi__resp_rate_bpm"), errors="coerce")
        rows.append({"feature": "resp__pi__resp_rate_bpm", "n": int(r.notna().sum()), "median": float(r.median()) if r.notna().any() else None})
    lines = ["# E15 extras (descriptive only; no reference exists for these)", "", "| feature | n | median |", "|---|---|---|"]
    lines += [f"| {r['feature']} | {r['n']} | {_fmt(r['median'],3)} |" for r in rows]
    return ctx.write("E15", {"status": "ok", "rows": rows, "markdown": "\n".join(lines) + "\n"})


def _strip_camera(df: pd.DataFrame, camera: str) -> pd.DataFrame:
    return df.rename(columns={c: c.replace(f"__{camera}__", "__CAM__") for c in df.columns if f"__{camera}__" in c})


def e16_transfer(ctx: Context) -> dict:
    """Train on pi_proxy, test on phone (and the other arms) with features renamed to a camera-neutral form."""
    from palmppg.features.splits import grouped_kfold

    a, b = ctx.frame("pi_proxy"), ctx.frame("phone")
    if a is None or b is None:
        return ctx.write("E16", {"status": "skipped", "reason": "needs both pi_proxy and phone feature tables"})
    A, B = _strip_camera(a, "pi_proxy"), _strip_camera(b, "phone")
    feats_a = set(arms_for(ctx, "product_candidate", "pi_proxy")["static_plus_temporal"])
    common = sorted({c.replace("__pi_proxy__", "__CAM__") for c in feats_a} & set(B.columns))
    common = [c for c in common if c in A.columns]
    ids = sorted(set(A["study_id"]) & set(B["study_id"]))
    folds = grouped_kfold(ids, min(ctx.n_splits, len(ids)), ctx.seed)
    y_a = pd.to_numeric(A.set_index("study_id").loc[ids, "bp_target_sbp"], errors="coerce").to_numpy()
    va = pd.Series(valid_mask(a, "pi_proxy"), index=a["study_id"]).loc[ids].to_numpy()
    vb = pd.Series(valid_mask(b, "phone"), index=b["study_id"]).loc[ids].to_numpy()
    XA = numeric_matrix(A.set_index("study_id").loc[ids].reset_index(), common)
    XB = numeric_matrix(B.set_index("study_id").loc[ids].reset_index(), common)
    cols = [c for c in XA.columns if c in XB.columns]
    XA, XB = XA[cols], XB[cols]
    arms = {}
    for arm, (Xtr, vtr, Xte, vte) in {"pi_proxy_to_phone": (XA, va, XB, vb), "phone_to_phone": (XB, vb, XB, vb),
                                      "pi_proxy_to_pi_proxy": (XA, va, XA, va)}.items():
        pred = np.full(len(ids), np.nan)
        for tr, te in folds:
            tr_m = np.isin(ids, list(tr)) & vtr & np.isfinite(y_a)
            te_m = np.isin(ids, list(te)) & vte
            if tr_m.sum() < 5 or te_m.sum() == 0 or not cols:
                continue
            m = cvm.ridge_model().fit(Xtr[tr_m], y_a[tr_m])
            pred[te_m] = m.predict(Xte[te_m])
        arms[arm] = _bp(y_a, pred)
    arms["pi_proxy_aug_to_phone"] = {"note": "compression-augmented training copies come from the section 8 study (augment study --n 100)"}
    lines = ["# E16 Pi-versus-phone transfer (product_candidate)", "", f"{len(cols)} camera-neutral features; {len(ids)} participants with both cameras.", "",
             "| arm | n covered | coverage % | bias | error SD | MAE |", "|---|---|---|---|---|---|"]
    for k, m in arms.items():
        lines.append(f"| {k} | {m.get('n', '')} | {_fmt(m.get('coverage_pct'),1)} | {_fmt(m.get('bias'))} | {_fmt(m.get('error_sd'))} | {_fmt(m.get('mae'))} |")
    return ctx.write("E16", {"status": "ok", "arms": arms, "n_features": len(cols), "markdown": "\n".join(lines) + "\n"})


def e17_pat(ctx: Context) -> dict:
    df = ctx.frame("pi")
    if df is None:
        return ctx.write("E17", {"status": "skipped", "reason": "no Pi features"})
    fine = df.get("sync__grade", pd.Series([None] * len(df))).astype(str) == "fine"
    pat = pd.to_numeric(df.get("pat__pi__pat_mean_ms"), errors="coerce")
    sbp = pd.to_numeric(df["bp_target_sbp"], errors="coerce")
    ok = fine & pat.notna() & sbp.notna()
    res = {"status": "ok", "requires_ecg": True, "track": "science", "n_fine": int(fine.sum()), "n_with_pat": int(ok.sum()),
           "pairing_rate_median": float(pd.to_numeric(df.get("pat__pi__pairing_rate"), errors="coerce")[fine].median()) if fine.any() else None,
           "ectopic_capture_fraction_median": float(pd.to_numeric(df.get("pat__pi__ectopic_capture_fraction"), errors="coerce")[fine].median()) if fine.any() else None}
    if ok.sum() >= 5:
        from scipy import stats

        r, p = stats.pearsonr(pat[ok], sbp[ok])
        res["pat_vs_sbp"] = {"pearson_r": r, "p": p, "n": int(ok.sum()), "note": "cross-sectional, exploratory; foot definition = intersecting tangents (D-020)"}
        res["pat_by_mst_band"] = df[ok].assign(pat=pat[ok]).groupby("mst_band")["pat"].agg(["count", "median"]).reset_index()
    lines = ["# E17 beat-level ECG-to-pulse (science track, sync grade fine only, requires_ecg)", "",
             f"Clips graded fine: {res['n_fine']}; with PAT: {res['n_with_pat']}; median pairing rate {_fmt(res['pairing_rate_median'])}; "
             f"median ectopic capture fraction {_fmt(res['ectopic_capture_fraction_median'])}.", ""]
    if "pat_vs_sbp" in res:
        lines.append(f"PAT versus SBP across participants: r = {res['pat_vs_sbp']['pearson_r']:.2f} (p = {res['pat_vs_sbp']['p']:.3f}, n = {res['pat_vs_sbp']['n']}); exploratory.")
    lines.append("Nothing in this experiment may enter a product_candidate model.")
    res["markdown"] = "\n".join(lines) + "\n"
    return ctx.write("E17", res)


EXPERIMENTS: dict[str, Callable[[Context], dict]] = {
    "E0": e0_baselines, "E1": e1_pulse_rate, "E2": e2_coverage, "E3": e3_bp_features, "E4": e4_bp_deep, "E5": e5_static_vs_temporal,
    "E6": e6_equity, "E7": e7_rhythm, "E8": e8_anaemia, "E9": e9_vascular_age, "E10": e10_fm, "E11": e11_shortcut, "E12": e12_elevated,
    "E13": e13_glucose, "E14": e14_repeatability, "E15": e15_extras, "E16": e16_transfer, "E17": e17_pat,
}
ORDER = list(EXPERIMENTS)
DEPENDS = {"E6": ["E3"], "E11": ["E3"]}


def run_experiments(names: list[str], cfg: Config | None = None, work_root: str | Path | None = None, ctx: Context | None = None) -> dict:
    """Run the named experiments in protocol order (dependencies first); failures are recorded, not raised."""
    cfg = cfg or load_pipeline_config()
    verify_frozen()
    ctx = ctx or Context(cfg, Path(work_root or cfg.get("paths.work_root")))
    wanted = [n for n in ORDER if n in set(names) | {d for n in names for d in DEPENDS.get(n, [])}]
    out = {}
    for n in wanted:
        try:
            out[n] = EXPERIMENTS[n](ctx)
        except Exception as exc:  # noqa: BLE001 - a crashed experiment is reported as failed with its traceback
            out[n] = ctx.write(n, {"status": "failed", "error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()[-3000:]})
    (ctx.out / "run_summary.json").write_text(json.dumps({"run_utc": dt.datetime.now(dt.UTC).isoformat(), "config_sha256": cfg.sha256(),
                                                          "statuses": {k: v.get("status") for k, v in out.items()}}, indent=1), encoding="utf-8")
    return out


def run_all(cfg: Config | None = None, work_root: str | Path | None = None) -> dict:
    return run_experiments(ORDER, cfg, work_root)
