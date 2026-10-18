"""One command regenerates every report from the pipeline outputs (protocol 11.6): `palmppg reports build`.

Writes into <work_root>/reports/: stard.md, tripod.md, data_dictionary.md, strata/<E>_<target>_<track>_<camera>.md,
experiments.md (all E0..E17 result pages concatenated), gonogo.md, bench_sync_report.md (copied), positive_control.md
(copied when present), augmentation/*.md (copied when present) and summary.md. Every page passes the vocabulary lint.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from palmppg.core.config import Config, load_pipeline_config
from palmppg.core.lint import scan_text


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


def strata_tables(work_root: Path, cfg: Config, out_dir: Path, n_resamples: int | None = None) -> list[Path]:
    """Per-stratum tables with participant bootstrap CIs and both baselines for the primary BP tables (E3, ridge)."""
    from palmppg.eval.metrics import reference_tertile_cuts
    from palmppg.eval.strata import StrataEngine, table_to_markdown
    from palmppg.experiments.data import load_features

    frames = load_features(work_root)
    eng = StrataEngine(cfg)
    if n_resamples is not None:
        eng.n_resamples = int(n_resamples)
    paths = []
    exp = work_root / "experiments"
    for p in sorted(exp.glob("preds_bp_target_sbp_*_ridge.parquet")):
        track_cam = p.stem[len("preds_bp_target_sbp_"):-len("_ridge")]
        track = "product_candidate" if track_cam.startswith("product_candidate") else "science"
        cam = track_cam[len(track) + 1:]
        if cam not in frames:
            continue
        pr = pd.read_parquet(p)
        df = frames[cam].reset_index(drop=True).copy()
        model_col = "static_plus_temporal" if "static_plus_temporal" in pr.columns else None
        if model_col is None or len(pr) != len(df):
            continue
        df["pred_model"], df["pred_mean"], df["pred_demo"] = pr[model_col].to_numpy(), pr["predict_mean"].to_numpy(), pr["demographics_only"].to_numpy()
        df["camera"] = cam
        y = pd.to_numeric(df["bp_target_sbp"], errors="coerce").to_numpy()
        cuts = reference_tertile_cuts(y[np.isfinite(y)]) if np.isfinite(y).sum() >= 3 else None

        def err_sd(yt, yp):
            e = np.asarray(yp, float) - np.asarray(yt, float)
            e = e[np.isfinite(e)]
            return float(np.std(e, ddof=1)) if e.size >= 2 else float("nan")

        tab = eng.metric_table_with_baselines(df, err_sd, {"model": "pred_model", "predict_mean": "pred_mean", "demographics_only": "pred_demo"},
                                              y_col="bp_target_sbp", tertile_cuts=cuts, metric_name="sbp_error_sd")
        out = out_dir / "strata" / f"E3_sbp_error_sd_{track}_{cam}.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(table_to_markdown(tab, title=f"SBP error SD by stratum: {track} / {cam} (participant bootstrap "
                                                     f"{eng.n_resamples} resamples; cells under {eng.min_cell} pooled)"), encoding="utf-8")
        tab.to_parquet(out.with_suffix(".parquet"), index=False)
        paths.append(out)
    return paths


def build_all_reports(cfg: Config | None = None, work_root: str | Path | None = None, study_root: str | Path | None = None,
                      n_resamples: int | None = None) -> list[Path]:
    from palmppg.experiments.data import load_features
    from palmppg.features.dictionary import data_dictionary_markdown
    from palmppg.reports.stard import FlowCounts, stard_markdown
    from palmppg.reports.tripod import tripod_markdown

    cfg = cfg or load_pipeline_config()
    work_root = Path(work_root or cfg.get("paths.work_root"))
    out = work_root / "reports"
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    synthetic = "synth" in str(work_root)
    banner = "> Synthetic cohort: these pages measure the pipeline on generated data and are not study results.\n\n" if synthetic else ""

    frames = load_features(work_root)
    pi = frames.get("pi", pd.DataFrame())
    qc_path = work_root / "tables" / "qc_table.parquet"
    qc = pd.read_parquet(qc_path) if qc_path.exists() else pd.DataFrame()
    runs_p = work_root / "tables" / "pipeline_runs.parquet"
    runs = pd.read_parquet(runs_p) if runs_p.exists() else pd.DataFrame()
    reasons: dict[str, int] = {}
    if len(qc):
        for r in qc[(qc["camera"] == "pi")]["reasons"].dropna():
            for k in (list(r) if not isinstance(r, str) else r.split(";")):
                if k:
                    reasons[str(k)] = reasons.get(str(k), 0) + 1
    grade = pi.get("sync__grade", pd.Series(dtype=object)).astype(str)
    clin = pi.get("clinician__rhythm", pd.Series(dtype=object)).astype(str)
    fc = FlowCounts(enrolled=int(pi["study_id"].nunique()) if len(pi) else 0, crf_valid=len(pi), clips_captured=int(len(runs) or len(pi)), reshoots=0,
                    clips_valid_pi=int(pi.get("qc__pi__valid_clip", pd.Series(dtype=bool)).fillna(False).astype(bool).sum()),
                    clips_valid_phone=int(frames.get("phone", pd.DataFrame()).get("qc__phone__valid_clip", pd.Series(dtype=bool)).fillna(False).astype(bool).sum()),
                    sync_fine=int((grade == "fine").sum()), sync_coarse=int((grade == "coarse").sum()), sync_none=int((grade == "none").sum()),
                    ecg_readable=int((clin != "unreadable").sum()), ecg_digitised=int(pi.get("ecg_digitised", pd.Series(dtype=bool)).fillna(False).astype(bool).sum()),
                    analysed_bp=int(pi.get("qc__pi__valid_clip", pd.Series(dtype=bool)).fillna(False).astype(bool).sum()),
                    analysed_rhythm=int(pi.get("qc__pi__valid_clip", pd.Series(dtype=bool)).fillna(False).astype(bool).sum()), abstained_bp=0, exclusion_reasons=reasons)
    pages = {"stard.md": banner + stard_markdown(fc), "tripod.md": banner + tripod_markdown(),
             "data_dictionary.md": data_dictionary_markdown()}
    exp = work_root / "experiments"
    exp_pages = []
    for e in [f"E{i}" for i in range(18)]:
        md = _read(exp / e / "results.md")
        res = json.loads(_read(exp / e / "results.json") or "{}")
        if not md:
            md = f"# {e}\n\nStatus: {res.get('status', 'not run')}. {res.get('reason', '') or res.get('error', '')}\n"
        exp_pages.append(md)
    pages["experiments.md"] = banner + "\n\n---\n\n".join(exp_pages)
    for name in ("gonogo.md", "gonogo_interim.md"):
        if (exp / name).exists():
            pages[name] = _read(exp / name)
    for src, dst in ((Path("reports/bench_sync_report.md"), "bench_sync_report.md"), (work_root / "augmentation" / "ranking.md", "augmentation_ranking.md"),
                     (work_root / "augmentation" / "benign_check.md", "augmentation_benign_check.md"), (work_root / "augmentation" / "ablation.md", "augmentation_ablation.md")):
        if src.exists():
            pages[dst] = _read(src)
    pc = Path(cfg.get("paths.work_root")) / "positive_control" / "positive_control.md"
    if not pc.exists():
        pc = Path("work/positive_control/positive_control.md")
    if pc.exists():
        pages["positive_control.md"] = _read(pc)
    for name, text in pages.items():
        p = out / name
        p.write_text(text, encoding="utf-8")
        written.append(p)
    written += strata_tables(work_root, cfg, out, n_resamples)
    summary = summary_markdown(work_root, frames, pages, synthetic)
    (out / "summary.md").write_text(summary, encoding="utf-8")
    written.append(out / "summary.md")
    hits = {str(p): scan_text(p.read_text(encoding="utf-8")) for p in written}
    hits = {k: v for k, v in hits.items() if v}
    if hits:
        raise ValueError(f"banned vocabulary in generated reports: {list(hits)[:5]}")
    return written


def summary_markdown(work_root: Path, frames: dict, pages: dict, synthetic: bool) -> str:
    lines = ["# Run summary", ""]
    if synthetic:
        lines += ["This run used a synthetic cohort. It shows the pipeline running end to end and reports what it measured on "
                  "generated data; it carries no information about people.", ""]
    for cam, df in frames.items():
        v = df.get(f"qc__{cam}__valid_clip", pd.Series(dtype=bool)).fillna(False).astype(bool)
        lines.append(f"- {cam}: {len(df)} clips attempted, {int(v.sum())} valid ({100 * v.mean():.0f} percent).")
    st = json.loads(_read(work_root / "experiments" / "run_summary.json") or "{}")
    if st:
        lines += ["", "Experiment statuses: " + ", ".join(f"{k} {v}" for k, v in st.get("statuses", {}).items())]
    if "gonogo.md" in pages:
        lines += ["", "Go/no-go: see gonogo.md (frozen thresholds, evaluated once)."]
    lines += ["", "Limitations that apply to every page: single site, one visit per participant, cuff readings that bracket rather than "
              "accompany the clip, MST band self-selected from a swatch card, and synthetic tone shifts that support no equity claim."]
    return "\n".join(lines) + "\n"
