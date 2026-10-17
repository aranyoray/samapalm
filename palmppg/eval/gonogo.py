"""Pilot go/no-go against the frozen thresholds (protocol section 10, "frozen before running").

The criteria and their thresholds live in ``configs/frozen_config.yaml`` under ``go_no_go`` and are signed.
``evaluate_go_no_go`` refuses to run unless ``verify_frozen`` passes on that file, takes no threshold overrides,
and writes a markdown table of criterion, threshold, measured value and pass/fail plus the overall decision.
If any criterion fails the decision is "no-go: stop and report" (section 10: do not tune thresholds after
seeing results).

Expected keys of ``results`` (all numbers measured by the pipeline, nothing here computes them):
  coverage_overall_pct                 coverage over all attempted clips (section 11.3 rule)
  coverage_mst_4_6_pct                 coverage in MST 4-6
  coverage_mst_7_10_pct                coverage in MST 7-10
  pulse_rate_within_tolerance_pct_pi   percent of valid Pi clips with |pulse rate - ECG HR| <= tolerance
  pulse_rate_within_tolerance_pct_phone  same for the phone (reported alongside, not a criterion)
  pulse_rate_tolerance_bpm             tolerance actually used (must equal the frozen value)
  sbp_error_sd_demographics_only       SBP error SD of the demographics-only baseline (grouped CV)
  sbp_error_sd_temporal                SBP error SD with temporal palm features (grouped CV)
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from palmppg.core.config import Config, ConfigError, frozen_payload_hash, verify_frozen

RESULT_KEYS: tuple[str, ...] = (
    "coverage_overall_pct", "coverage_mst_4_6_pct", "coverage_mst_7_10_pct",
    "pulse_rate_within_tolerance_pct_pi", "pulse_rate_within_tolerance_pct_phone", "pulse_rate_tolerance_bpm",
    "sbp_error_sd_demographics_only", "sbp_error_sd_temporal",
)


@dataclass(frozen=True)
class GoNoGoReport:
    table: pd.DataFrame
    go: bool
    frozen_sha256: str
    markdown: str
    n_criteria: int
    n_failed: int


def _num(results: Mapping[str, Any], key: str) -> float:
    v = results.get(key)
    if v is None:
        return float("nan")
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def _row(criterion: str, comparator: str, threshold: float, measured: float, note: str = "",
         is_criterion: bool = True) -> dict[str, Any]:
    if not is_criterion:
        ok = None
    elif not np.isfinite(measured):
        ok = False
        note = (note + "; " if note else "") + "measurement missing: counts as a fail"
    elif comparator == ">=":
        ok = bool(measured >= threshold)
    elif comparator == "<=":
        ok = bool(measured <= threshold)
    else:
        raise ValueError(comparator)
    return {"criterion": criterion, "comparator": comparator, "threshold": threshold, "measured": measured,
            "passed": ok, "is_criterion": is_criterion, "note": note}


def evaluate_go_no_go(results: Mapping[str, Any], frozen: Config | None = None, frozen_path: str | Path | None = None,
                      markdown_path: str | Path | None = None) -> GoNoGoReport:
    """Evaluate the four frozen pilot criteria (section 10) on measured ``results``.

    ``frozen_path`` is the signed frozen config (default configs/frozen_config.yaml); ``verify_frozen`` must pass
    or ``ConfigError`` is raised and nothing is evaluated. If a ``frozen`` Config object is also given, its
    payload hash must equal the verified file's (a tampered in-memory copy is refused too). Thresholds are never
    modified. The markdown report is returned and, when ``markdown_path`` is given, written.
    """
    data = verify_frozen(frozen_path)  # raises ConfigError on a tampered file
    sha = frozen_payload_hash(data)
    if frozen is not None and frozen_payload_hash(frozen.data) != sha:
        raise ConfigError("frozen Config object does not match the signed frozen file; refusing to evaluate")
    th = data.get("go_no_go") or {}
    for k in ("coverage_min_pct", "coverage_equity_max_drop_points", "pulse_rate_tolerance_bpm",
              "pulse_rate_within_tolerance_min_pct", "temporal_vs_demographics_sbp_sd_reduction_mmhg"):
        if k not in th:
            raise ConfigError(f"frozen config lacks go_no_go.{k}")

    rows = []
    rows.append(_row("coverage_overall_pct", ">=", float(th["coverage_min_pct"]), _num(results, "coverage_overall_pct")))

    drop = _num(results, "coverage_mst_4_6_pct") - _num(results, "coverage_mst_7_10_pct")
    rows.append(_row("coverage_drop_points_mst_4_6_minus_7_10", "<=", float(th["coverage_equity_max_drop_points"]), drop,
                     note=f"MST 4-6 {_num(results, 'coverage_mst_4_6_pct'):.1f} vs 7-10 {_num(results, 'coverage_mst_7_10_pct'):.1f}"))

    tol_used = _num(results, "pulse_rate_tolerance_bpm")
    tol_frozen = float(th["pulse_rate_tolerance_bpm"])
    note = f"tolerance {tol_frozen:g} bpm"
    pr = _num(results, "pulse_rate_within_tolerance_pct_pi")
    if np.isfinite(tol_used) and not np.isclose(tol_used, tol_frozen):
        note += f"; measured at {tol_used:g} bpm, not the frozen tolerance: fails"
        pr = float("nan")
    rows.append(_row("pulse_rate_within_tolerance_pct_pi", ">=", float(th["pulse_rate_within_tolerance_min_pct"]), pr, note))
    rows.append(_row("pulse_rate_within_tolerance_pct_phone", ">=", float(th["pulse_rate_within_tolerance_min_pct"]),
                     _num(results, "pulse_rate_within_tolerance_pct_phone"), "reported alongside; not a criterion", False))

    red = _num(results, "sbp_error_sd_demographics_only") - _num(results, "sbp_error_sd_temporal")
    rows.append(_row("sbp_error_sd_reduction_temporal_vs_demographics_mmhg", ">=",
                     float(th["temporal_vs_demographics_sbp_sd_reduction_mmhg"]), red,
                     note=f"demographics-only {_num(results, 'sbp_error_sd_demographics_only'):.2f} vs temporal {_num(results, 'sbp_error_sd_temporal'):.2f}"))

    table = pd.DataFrame(rows)
    crit = table[table["is_criterion"]]
    n_failed = int((~crit["passed"].astype(bool)).sum())
    go = n_failed == 0
    md = go_no_go_markdown(table, go, sha, data.get("frozen_on"))
    if markdown_path is not None:
        p = Path(markdown_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(md, encoding="utf-8")
    return GoNoGoReport(table, go, sha, md, len(crit), n_failed)


def go_no_go_markdown(table: pd.DataFrame, go: bool, sha: str, frozen_on: Any = None) -> str:
    lines = ["## Pilot go/no-go (frozen thresholds)", "",
             f"Frozen config payload sha256: `{sha}`" + (f" (frozen on {frozen_on})" if frozen_on else ""), "",
             "| criterion | threshold | measured | result | note |", "|---|---|---|---|---|"]
    for _, r in table.iterrows():
        meas = "" if not np.isfinite(r["measured"]) else f"{r['measured']:.2f}"
        res = "report only" if r["passed"] is None else ("pass" if r["passed"] else "FAIL")
        lines.append(f"| {r['criterion']} | {r['comparator']} {r['threshold']:g} | {meas} | {res} | {r['note']} |")
    decision = "GO" if go else "NO-GO: stop and report"
    lines += ["", (f"**Decision: {decision}.** Thresholds were read from the signed frozen config and were not "
                   "modified after seeing results.")]
    return "\n".join(lines) + "\n"
