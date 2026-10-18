"""Positive control (protocol section 8, run-order step 1): a known pulse must come back out of the whole pipeline.

A one-participant synthetic cohort is generated with every nuisance switched off (no drops, flicker, drift or
jitter) and a known pulse injected into otherwise static palm frames (the synthetic scene). The full per-participant
pipeline then runs on the Pi raw path and on the Pi->phone proxy at the configured CRF and at CRF 28, and the
recovered heart rate, foot times and morphology are scored against the generator's truth with the tolerances in
`palmppg.synth.positive_control.tolerances` (HR within 1 bpm, feet within one frame median, morphology within
tolerance). Nothing here is tuned: a failure is reported as a failure.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from palmppg.core.config import Config, load_pipeline_config
from palmppg.core.paths import StudyLayout, WorkLayout
from palmppg.core.timeline import Timeline

MORPH_MAP = {  # beats module names -> positive-control scored names
    "upstroke_time_s": "upstroke_s", "upstroke_s": "upstroke_s",
    "systolic_width_50": "systolic_width_s", "systolic_width_50_s": "systolic_width_s", "systolic_width_s": "systolic_width_s",
    "notch_time_s": "notch_time_s", "reflection_index": "reflection_index", "decay_tau_s": "decay_tau_s",
}


def _load(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def recovered_from_work(camera_dir: Path, timeline: Timeline, cfg: Config) -> dict[str, Any]:
    """{hr_bpm, foot_times, morphology, source} from the pipeline outputs of one camera.

    Prefers the beats stage (beats.parquet feet, beat_features.json ensemble morphology); when the beats stage is
    absent it falls back to the generator's reference recovery on the pipeline's own whole-palm trace, which still
    proves the Bayer -> ROI -> trace chain and is labelled `source = "trace_reference"`.
    """
    out: dict[str, Any] = {"hr_bpm": float("nan"), "foot_times": np.zeros(0), "morphology": {}, "source": None}
    sqi = _load(camera_dir / "pulse_sqi.json")
    if sqi and sqi.get("best"):
        out["sqi_window_hr_bpm"] = float(sqi[sqi["best"]].get("hr_bpm", float("nan")))
        out["best_signal"] = sqi["best"]
        out["sqi"] = sqi[sqi["best"]].get("sqi")
    beats = camera_dir / "beats.parquet"
    bf = _load(camera_dir / "beat_features.json")
    if beats.exists():
        b = pd.read_parquet(beats)
        col = "foot_t" if "foot_t" in b.columns else ("foot_t_ref_s" if "foot_t_ref_s" in b.columns else None)
        if col:
            feet = np.sort(b[col].to_numpy(float))
            feet = feet[np.isfinite(feet)]
            out["foot_times"] = feet
            out["source"] = "beats"
            win = timeline.analysis_window
            if win is not None:
                feet = feet[(feet >= win.start_s) & (feet < win.end_s)]
            ibi = np.diff(feet)
            lo, hi = cfg.get("beats.ibi_bounds_s")
            ibi = ibi[(ibi >= lo) & (ibi <= hi)]
            if ibi.size >= 3:
                out["hr_bpm"] = float(60.0 / np.mean(ibi))  # D-018: beat-based rate over the window
    if bf:
        morph = bf.get("morphology") or {}
        ens = morph.get("ensemble", morph) if isinstance(morph, dict) else {}
        for k, v in ens.items():
            if k in MORPH_MAP and isinstance(v, (int, float)):
                out["morphology"][MORPH_MAP[k]] = float(v)
    if out["source"] is None:
        from palmppg.synth.positive_control import reference_recovery

        tr = pd.read_parquet(camera_dir / "traces.parquet")
        t = tr["t_ref_s"].to_numpy(float)
        if "whole_palm__G__mean" in tr.columns:
            g = tr["whole_palm__G__mean"].to_numpy(float)
        else:
            g = 0.5 * (tr["whole_palm__G1__mean"].to_numpy(float) + tr["whole_palm__G2__mean"].to_numpy(float))
        m = np.isfinite(g) & timeline.valid_mask(t)
        ref = reference_recovery(t[m], g[m], cfg=cfg)
        out["foot_times"] = np.asarray(ref["foot_times"], float)
        out["morphology"] = {MORPH_MAP.get(k, k): float(v) for k, v in (ref["morphology"] or {}).items() if isinstance(v, (int, float))}
        out["source"] = "trace_reference"
        out["hr_bpm"] = float(ref["hr_bpm"])  # dense-DFT peak over the window (D-018)
    if not np.isfinite(out["hr_bpm"]):
        out["hr_bpm"] = out.get("sqi_window_hr_bpm", float("nan"))
    return out


def truth_in_window(truth: dict, window: tuple[float, float] | None) -> dict:
    """Truth dict with `hr_bpm` replaced by the window mean of the generator's instantaneous rate series (D-018)."""
    t = dict(truth)
    hs = truth.get("hr_series") or {}
    tt, hb = np.asarray(hs.get("t_ref_s", []), float), np.asarray(hs.get("hr_bpm", []), float)
    if window is not None and tt.size and hb.size:
        m = (tt >= window[0]) & (tt < window[1])
        if m.sum() >= 2:
            t["hr_bpm"] = float(np.mean(hb[m]))
            t["hr_window_s"] = list(window)
    return t


def run_positive_control(out_root: str | Path, cfg: Config | None = None, seed: int = 1, small: bool = False,
                         proxy_crfs: tuple[int, ...] | None = None, cameras: tuple[str, ...] = ("pi", "pi_proxy")) -> dict:
    """Generate the clean synthetic participant, run the pipeline, score, and write positive_control.{json,md}."""
    from palmppg.pipeline.run_participant import run_participant
    from palmppg.synth.cohort import make_cohort
    from palmppg.synth.positive_control import score_recovery

    cfg = cfg or load_pipeline_config()
    out_root = Path(out_root)
    study_root = out_root / "study"
    overrides = {"pi_options": {"drops_pct": 0.0, "flicker_pct": 0.0, "drift_pct": 0.0, "jitter_px": 0.0}, "streams": ["development"]}
    make_cohort(study_root, 1, seed, cfg, overrides=overrides, small=small)
    layout = StudyLayout(study_root)
    pp = layout.participants()[0]
    truth = _load(pp.pi / "clip1_truth.json") or {}
    fps = float(truth.get("fps") or cfg.get("pi.nominal_fps"))
    crfs = tuple(proxy_crfs) if proxy_crfs else (int(cfg.get("phone.proxy_crf")), 28)
    crfs = tuple(dict.fromkeys(crfs))
    results: dict[str, Any] = {"seed": seed, "small": small, "study_root": str(study_root), "study_id": pp.study_id,
                               "truth": {"hr_bpm": truth.get("hr_bpm"), "ac_dc": truth.get("ac_dc"), "morphology_measured": truth.get("morphology_measured")},
                               "runs": {}, "generated_utc": dt.datetime.now(dt.UTC).isoformat()}
    overall = True
    for crf in crfs:
        work = WorkLayout(out_root / f"work_crf{crf}")
        c = cfg.with_overrides({"phone": {"proxy_crf": int(crf)}})
        pipe = run_participant(layout, pp.study_id, work, c, cameras=cameras)
        clip_dir = work.clip(pp.study_id, "clip1")
        tl = Timeline.load(clip_dir / "timeline.json")
        win = (tl.analysis_window.start_s, tl.analysis_window.end_s) if tl.analysis_window else None
        run: dict[str, Any] = {"crf": crf, "sync_grade": tl.sync_grade, "pipeline_ok": pipe["ok"],
                               "failed_stages": [s["stage"] for s in pipe["stages"] if s["status"] != "ok"], "cameras": {}}
        for cam in cameras:
            cam_dir = clip_dir / cam
            if not (cam_dir / "pulse_sqi.json").exists():
                run["cameras"][cam] = {"pass": False, "reason": "pulse stage produced no output"}
                overall = False
                continue
            rec = recovered_from_work(cam_dir, tl, c)
            score = score_recovery(truth_in_window(truth, win), rec, fps=fps, cfg=c, window_s=win)
            score["recovery_source"] = rec["source"]
            score["best_signal"] = rec.get("best_signal")
            score["sqi"] = rec.get("sqi")
            run["cameras"][cam] = score
            overall &= bool(score.get("pass", False))
        results["runs"][f"crf{crf}"] = run
    results["pass"] = bool(overall)
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "positive_control.json").write_text(json.dumps(results, indent=1, default=_json_default), encoding="utf-8")
    (out_root / "positive_control.md").write_text(positive_control_markdown(results), encoding="utf-8")
    return results


def _json_default(o):
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.floating, np.integer)):
        v = o.item()
        return None if isinstance(v, float) and np.isnan(v) else v
    return str(o)


def positive_control_markdown(r: dict) -> str:
    lines = [f"# Positive control ({'small' if r.get('small') else 'default'} synthetic geometry, seed {r.get('seed')})", "",
             f"Overall: **{'PASS' if r.get('pass') else 'FAIL'}**. Truth HR {r['truth'].get('hr_bpm'):.2f} bpm; injected AC/DC {r['truth'].get('ac_dc')}.", "",
             "| run | camera | sync | source | HR truth | HR recovered | abs err (bpm) | feet matched | foot median err (frames) | morphology passes | pass |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for name, run in r["runs"].items():
        for cam, s in run["cameras"].items():
            if "hr" not in s:
                lines.append(f"| {name} | {cam} | {run.get('sync_grade')} | - | - | - | - | - | - | - | FAIL ({s.get('reason')}) |")
                continue
            m = s.get("morphology", {}) or {}
            mp = sum(1 for v in m.values() if isinstance(v, dict) and v.get("pass")) if m else 0
            mn = sum(1 for v in m.values() if isinstance(v, dict) and v.get("pass") is not None) if m else 0
            f = s.get("feet", {})
            lines.append(f"| {name} | {cam} | {run.get('sync_grade')} | {s.get('recovery_source')} | {s['hr']['truth_bpm']:.2f} | {s['hr']['recovered_bpm']:.2f} | "
                         f"{s['hr']['abs_err_bpm']:.2f} | {f.get('n_matched')}/{f.get('n_truth')} | {f.get('median_abs_err_frames', float('nan')):.2f} | {mp}/{mn} | "
                         f"{'PASS' if s.get('pass') else 'FAIL'} |")
        if run.get("failed_stages"):
            lines.append(f"\nFailed pipeline stages in {name}: {', '.join(run['failed_stages'])}\n")
    lines += ["", "Tolerances: HR within 1 bpm; foot timing median within one frame; morphology parameters within the configured relative tolerance.",
              "A failing row is reported as it is; nothing is re-tuned on this result."]
    return "\n".join(lines) + "\n"
