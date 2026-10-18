"""SQI threshold calibration against null clips (D-025; feeds the run-order step 3 freeze of `sqi.threshold`).

A null clip is a recording with no pulse in the imaged region: on the bench, the box with a static white card or a
pulseless phantom in place of the palm; in synthesis, a participant generated with AC/DC = 0. The best-SQI value the
pipeline reports on null clips is the noise floor of the selection; a threshold below its 95th percentile passes
noise as a valid clip. The procedure is fixed before real data and uses no outcome, so it can set the frozen value.
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

import numpy as np


def best_sqi_values(work_root: str | Path, camera: str) -> np.ndarray:
    vals = []
    for p in glob.glob(str(Path(work_root) / "*" / "clip1" / camera / "qc.json")):
        q = json.loads(Path(p).read_text(encoding="utf-8"))
        if q.get("sqi_best") is not None:
            vals.append(float(q["sqi_best"]))
    return np.asarray(vals, float)


def calibration_table(null_root: str | Path, signal_root: str | Path, provisional: float, quantile: float = 95.0) -> list[dict]:
    rows = []
    for cam in ("pi", "phone", "pi_proxy"):
        n, s = best_sqi_values(null_root, cam), best_sqi_values(signal_root, cam)
        if n.size == 0 or s.size == 0:
            continue
        thr = float(np.percentile(n, quantile))
        rows.append({"camera": cam, "n_null": int(n.size), "n_signal": int(s.size), "null_median": float(np.median(n)), "null_q": thr,
                     "signal_median": float(np.median(s)), "null_pass_at_provisional": float(np.mean(n >= provisional)),
                     "signal_pass_at_provisional": float(np.mean(s >= provisional)), "signal_pass_at_null_q": float(np.mean(s >= thr))})
    return rows


def calibration_markdown(rows: list[dict], provisional: float, quantile: float = 95.0, synthetic: bool = True) -> str:
    lines = ["# SQI threshold calibration against null clips", ""]
    if synthetic:
        lines += ["Synthetic null clips (AC/DC = 0) and synthetic pulse clips at the small test geometry. This calibrates the procedure, "
                  "not the study threshold, which is frozen at run-order step 3 from bench null recordings on the real unit.", ""]
    lines += [f"Provisional threshold {provisional}. Null quantile {quantile:g}.", "",
              "| camera | null n | signal n | null median | null q | signal median | null clips passing provisional | signal clips passing provisional | signal clips at or above null q |",
              "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['camera']} | {r['n_null']} | {r['n_signal']} | {r['null_median']:.3f} | {r['null_q']:.3f} | {r['signal_median']:.3f} | "
                     f"{100 * r['null_pass_at_provisional']:.0f}% | {100 * r['signal_pass_at_provisional']:.0f}% | {100 * r['signal_pass_at_null_q']:.0f}% |")
    lines += ["", "Where the signal median does not exceed the null quantile, the camera path carries no recoverable pulse at this geometry "
              "and compression; that is reported as a negative result, not tuned away."]
    return "\n".join(lines) + "\n"
