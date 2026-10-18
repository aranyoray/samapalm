"""Frozen pilot go/no-go (protocol section 10) from the measured experiment results. Thresholds are read from the
signed frozen config and never changed here; `interim=True` labels the dashboard as the first-100 interim view.

Inputs (D-022): coverage from E2 on the Pi (lab reference) with the MST 4-6 versus 7-10 split, pulse rate from E1
(Pi criterion, phone alongside), SBP error SD reduction from E5 on the science track (Pi), with the product track
shown alongside in the markdown.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from palmppg.core.config import Config, load_frozen_config, load_pipeline_config
from palmppg.eval.gonogo import evaluate_go_no_go
from palmppg.experiments.data import load_features, valid_mask


def _load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def gonogo_inputs(work_root: Path, frames: dict | None = None) -> dict:
    exp = work_root / "experiments"
    e1, e5 = _load(exp / "E1" / "results.json"), _load(exp / "E5" / "results.json")
    frames = frames if frames is not None else load_features(work_root)
    res: dict = {"pulse_rate_tolerance_bpm": e1.get("tolerance_bpm")}
    pi = frames.get("pi")
    if pi is not None:
        v = valid_mask(pi, "pi")
        band = pd.to_numeric(pi["mst_band"], errors="coerce").to_numpy()
        res["coverage_overall_pct"] = 100 * float(v.mean()) if len(v) else np.nan
        lo, hi = (band >= 4) & (band <= 6), (band >= 7) & (band <= 10)
        res["coverage_mst_4_6_pct"] = 100 * float(v[lo].mean()) if lo.any() else np.nan
        res["coverage_mst_7_10_pct"] = 100 * float(v[hi].mean()) if hi.any() else np.nan
        res["n_mst_4_6"], res["n_mst_7_10"] = int(lo.sum()), int(hi.sum())
    for r in e1.get("rows", []):
        if r.get("subset") == "valid clips":
            res[f"pulse_rate_within_tolerance_pct_{r['camera']}"] = r.get("within_tol_pct")
    for s in e5.get("summary", []):
        if s["track"] == "science" and s["camera"] == "pi":
            res["sbp_error_sd_demographics_only"] = s.get("sbp_sd_demographics")
            res["sbp_error_sd_temporal"] = s.get("sbp_sd_temporal")
    res["product_track_e5"] = [s for s in e5.get("summary", []) if s["track"] == "product_candidate"]
    return res


def run_gonogo(cfg: Config | None = None, interim: bool = False, work_root: str | Path | None = None, synthetic: bool | None = None) -> dict:
    cfg = cfg or load_pipeline_config()
    work_root = Path(work_root or cfg.get("paths.work_root"))
    inputs = gonogo_inputs(work_root)
    clean = {k: (np.nan if v is None else v) for k, v in inputs.items() if not isinstance(v, list)}
    rep = evaluate_go_no_go(clean, load_frozen_config())
    synthetic = synthetic if synthetic is not None else "synth" in str(work_root)
    head = ["# Interim go/no-go dashboard (first 100; thresholds unchanged)" if interim else "# Pilot go/no-go", ""]
    if synthetic:
        head += ["**Synthetic cohort.** This run measures the pipeline on generated data; it is not a study result.", ""]
    head += [f"MST 4-6 n = {inputs.get('n_mst_4_6')}, MST 7-10 n = {inputs.get('n_mst_7_10')}.", ""]
    tail = ["", "Product track alongside (E5, not a criterion):", ""]
    for s in inputs.get("product_track_e5", []):
        tail.append(f"- {s['camera']}: SBP SD demographics {s.get('sbp_sd_demographics')}, temporal {s.get('sbp_sd_temporal')}, reduction {s.get('reduction_mmhg')}")
    md = "\n".join(head) + rep.markdown + "\n".join(tail) + "\n"
    if not rep.go:
        md += "\nAt least one frozen criterion failed: the protocol says stop and report.\n"
    out = work_root / "experiments" / ("gonogo_interim.md" if interim else "gonogo.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    return {"go": rep.go, "n_failed": rep.n_failed, "inputs": inputs, "markdown": md, "path": str(out), "frozen_sha256": rep.frozen_sha256}
