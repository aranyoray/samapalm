"""Equity audit (protocol section 7, E6): non-inferiority of coverage and of SBP error SD for MST 7-10 versus
4-6 against the margins frozen in ``configs/frozen_config.yaml`` (one-sided), a cluster-robust regression of
error on MST band with covariates, and the "predict MST band from pulse features" leakage probe.

Inputs are per-clip result rows (study_id, mst_band, mst_equity_arm, error = pred - true in mmHg, covered) and a
feature table for the probe. Margins, arms and alpha come from the frozen config; nothing here sets them.
"""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from palmppg.audits._cv import design_matrix, grouped_cv_classification
from palmppg.core.config import Config, load_pipeline_config, verify_frozen
from palmppg.eval.noninferiority import (
    coverage_noninferiority,
    error_sd_ratio_noninferiority,
    error_sd_ratio_noninferiority_bootstrap,
)

DEFAULT_COVARIATES: tuple[str, ...] = ("age", "sex", "bmi", "bp_target_sbp")
CATEGORICAL_COVARIATES: tuple[str, ...] = ("sex",)


def equity_arm_from_band(band) -> np.ndarray:
    """'4-6' for bands 4..6, '7-10' for 7..10, None otherwise (DECISIONS D-005 equity arms)."""
    b = pd.to_numeric(pd.Series(band), errors="coerce")
    out = np.select([b.between(4, 6), b.between(7, 10)], ["4-6", "7-10"], default=None)
    return out.astype(object)


def frozen_equity_settings(frozen_path: str | Path | None = None) -> dict[str, Any]:
    """Equity margins and arms from the *verified* frozen config."""
    data = verify_frozen(frozen_path)
    eq = data.get("equity") or {}
    for k in ("coverage_margin_points", "error_sd_ratio_margin", "reference_arm", "comparison_arm", "one_sided_alpha"):
        if k not in eq:
            raise KeyError(f"frozen config lacks equity.{k}")
    return dict(eq)


def error_on_mst_regression(df: pd.DataFrame, error_col: str = "error", band_col: str = "mst_band",
                            covariates: Sequence[str] = DEFAULT_COVARIATES, id_col: str = "study_id",
                            categorical: Sequence[str] = CATEGORICAL_COVARIATES) -> dict[str, Any]:
    """OLS of error on MST band (numeric slope per band) plus covariates with cluster-robust standard errors by
    participant (section 7). Covariates absent from the frame are dropped and named in the note."""
    import statsmodels.formula.api as smf

    used = [c for c in covariates if c in df.columns]
    dropped = [c for c in covariates if c not in df.columns]
    terms = [band_col] + [f"C({c})" if c in categorical else c for c in used]
    cols = [error_col, band_col, id_col] + used
    work = df[cols].copy()
    work[band_col] = pd.to_numeric(work[band_col], errors="coerce")
    work[error_col] = pd.to_numeric(work[error_col], errors="coerce")
    for c in used:
        if c not in categorical:
            work[c] = pd.to_numeric(work[c], errors="coerce")
    work = work.dropna()
    note = f"covariates absent and dropped: {dropped}" if dropped else ""
    if len(work) < len(terms) + 2 or work[id_col].nunique() < 2:
        return {"table": pd.DataFrame(columns=["term", "coef", "se", "ci_lo", "ci_hi", "p"]), "n": len(work),
                "n_clusters": int(work[id_col].nunique()), "formula": "", "note": note + "; too few rows to fit"}
    formula = f"{error_col} ~ " + " + ".join(terms)
    groups = pd.factorize(work[id_col].astype(str))[0]
    fit = smf.ols(formula, data=work).fit(cov_type="cluster", cov_kwds={"groups": groups})
    ci = fit.conf_int()
    table = pd.DataFrame({"term": fit.params.index, "coef": fit.params.to_numpy(), "se": fit.bse.to_numpy(),
                          "ci_lo": ci.iloc[:, 0].to_numpy(), "ci_hi": ci.iloc[:, 1].to_numpy(), "p": fit.pvalues.to_numpy()})
    band_row = table[table["term"] == band_col].iloc[0]
    return {"table": table, "n": int(fit.nobs), "n_clusters": len(np.unique(groups)), "formula": formula,
            "band_coef": float(band_row["coef"]), "band_se": float(band_row["se"]), "band_p": float(band_row["p"]),
            "r2": float(fit.rsquared), "note": note}


def equity_audit(results_df: pd.DataFrame, frozen_path: str | Path | None = None, error_col: str = "error",
                 covered_col: str = "covered", arm_col: str = "mst_equity_arm", band_col: str = "mst_band",
                 id_col: str = "study_id", covariates: Sequence[str] = DEFAULT_COVARIATES,
                 n_resamples: int | None = None, seed: int | None = None, cfg: Config | None = None) -> dict[str, Any]:
    """End-to-end E6 audit on per-clip rows.

    * coverage per arm = covered rows / all rows of the arm (abstentions and failed clips count as not covered,
      section 11.3) -> Farrington-Manning and Wald-cc one-sided non-inferiority of the comparison arm (7-10)
      versus the reference arm (4-6) at the frozen margin in points;
    * SBP error SD per arm over covered rows -> one-sided F-test and participant bootstrap at the frozen ratio;
    * error ~ mst_band + covariates OLS with cluster-robust SEs by participant.
    Returns a dict of result dicts, an ``arms`` table and a ``markdown`` summary.
    """
    eq = frozen_equity_settings(frozen_path)
    cfg = cfg or load_pipeline_config()
    n_resamples = int(cfg.get("bootstrap.n_resamples")) if n_resamples is None else int(n_resamples)
    seed = int(cfg.get("study.seed")) if seed is None else int(seed)
    df = results_df.copy()
    if arm_col not in df.columns:
        if band_col not in df.columns:
            raise KeyError(f"need {arm_col} or {band_col}")
        df[arm_col] = equity_arm_from_band(df[band_col])
    if error_col not in df.columns:
        raise KeyError(f"{error_col} not in frame")
    err = pd.to_numeric(df[error_col], errors="coerce")
    covered = df[covered_col].astype(bool).to_numpy() if covered_col in df.columns else err.notna().to_numpy()
    covered = covered & err.notna().to_numpy()
    ref, cmp_ = str(eq["reference_arm"]), str(eq["comparison_arm"])
    arms = []
    per = {}
    for arm in (ref, cmp_):
        m = (df[arm_col].astype(object).map(lambda v: None if v is None else str(v)) == arm).to_numpy()
        n_att = int(m.sum())
        n_cov = int((m & covered).sum())
        e = err.to_numpy(dtype=float)[m & covered]
        ids = df[id_col].to_numpy()[m & covered] if id_col in df.columns else np.arange(e.size)
        per[arm] = {"n_attempted": n_att, "n_covered": n_cov, "coverage_pct": 100.0 * n_cov / n_att if n_att else float("nan"),
                    "errors": e, "ids": ids, "error_sd": float(np.std(e, ddof=1)) if e.size > 1 else float("nan"),
                    "n_participants": len(np.unique(ids.astype(str))) if id_col in df.columns else n_cov}
        arms.append({"arm": arm, "role": "reference" if arm == ref else "comparison", **{k: v for k, v in per[arm].items() if k not in ("errors", "ids")}})
    alpha = float(eq["one_sided_alpha"])
    cov_fm = coverage_noninferiority(per[cmp_]["coverage_pct"], per[cmp_]["n_attempted"], per[ref]["coverage_pct"],
                                     per[ref]["n_attempted"], float(eq["coverage_margin_points"]), alpha, "farrington_manning")
    cov_wald = coverage_noninferiority(per[cmp_]["coverage_pct"], per[cmp_]["n_attempted"], per[ref]["coverage_pct"],
                                       per[ref]["n_attempted"], float(eq["coverage_margin_points"]), alpha, "wald_cc")
    sd_f = error_sd_ratio_noninferiority(per[cmp_]["errors"], per[ref]["errors"], float(eq["error_sd_ratio_margin"]), alpha)
    sd_boot = error_sd_ratio_noninferiority_bootstrap(per[cmp_]["errors"], per[ref]["errors"], float(eq["error_sd_ratio_margin"]),
                                                      alpha, per[cmp_]["ids"], per[ref]["ids"], n_resamples, seed, "equity_sd_ratio")
    reg_df = df.loc[covered].copy()
    reg_df[error_col] = err[covered].to_numpy()
    regression = error_on_mst_regression(reg_df, error_col, band_col, covariates, id_col) if band_col in df.columns else {
        "table": pd.DataFrame(), "note": f"{band_col} absent; regression skipped", "n": 0, "n_clusters": 0}
    out = {"settings": eq, "arms": pd.DataFrame(arms), "coverage_ni": cov_fm, "coverage_ni_wald": cov_wald,
           "sd_ratio_ni_f": sd_f, "sd_ratio_ni_bootstrap": sd_boot, "regression": regression}
    out["markdown"] = equity_markdown(out)
    return out


def equity_markdown(res: dict[str, Any]) -> str:
    eq = res["settings"]
    head = f"## Equity audit (E6): MST {eq['comparison_arm']} versus {eq['reference_arm']}, one-sided alpha {eq['one_sided_alpha']:g}"
    lines = [head, "",
             "| arm | role | n attempted | n covered | coverage % | error SD | n participants |", "|---|---|---|---|---|---|---|"]
    for _, r in res["arms"].iterrows():
        lines.append(f"| {r['arm']} | {r['role']} | {r['n_attempted']} | {r['n_covered']} | {r['coverage_pct']:.1f} | "
                     f"{r['error_sd']:.2f} | {r['n_participants']} |")
    lines += ["", "| test | estimate | one-sided bound | margin | non-inferior | p |", "|---|---|---|---|---|---|"]
    for name, key in (("coverage difference, points (Farrington-Manning)", "coverage_ni"),
                      ("coverage difference, points (Wald, continuity corrected)", "coverage_ni_wald"),
                      ("error SD ratio (F-test)", "sd_ratio_ni_f"), ("error SD ratio (participant bootstrap)", "sd_ratio_ni_bootstrap")):
        r = res[key]
        lines.append(f"| {name} | {r['estimate']:.3f} | {r['ci_bound']:.3f} | {r['margin']:g} | "
                     f"{'yes' if r['noninferior'] else 'no'} | {r['p']:.4f} |")
    reg = res["regression"]
    reg_note = f": {reg['note']}" if reg.get("note") else ""
    reg_line = (f"Regression `{reg.get('formula', '')}` (cluster-robust by participant, n={reg.get('n', 0)}, "
                f"clusters={reg.get('n_clusters', 0)}){reg_note}")
    lines += ["", reg_line, ""]
    t = reg.get("table")
    if t is not None and len(t):
        lines += ["| term | coef | se | 95% CI | p |", "|---|---|---|---|---|"]
        for _, r in t.iterrows():
            lines.append(f"| {r['term']} | {r['coef']:.3f} | {r['se']:.3f} | {r['ci_lo']:.3f} .. {r['ci_hi']:.3f} | {r['p']:.4f} |")
    return "\n".join(lines) + "\n"


def mst_leakage_probe(features_df: pd.DataFrame, feature_cols: Sequence[str], cv: int = 5, seed: int | None = 0,
                      id_col: str = "study_id", band_col: str = "mst_band", arm_col: str | None = "mst_equity_arm") -> dict[str, Any]:
    """Section 7 leakage probe: balanced accuracy and macro-F1 of predicting the MST band (and the 4-6 versus
    7-10 arm) from pulse features in participant-grouped CV, each with its chance level. Rows without a band are
    dropped; the arm is derived from the band when ``arm_col`` is absent."""
    missing = [c for c in feature_cols if c not in features_df.columns]
    if missing:
        raise KeyError(f"feature columns not in frame: {missing}")
    df = features_df.copy()
    band = pd.to_numeric(df[band_col], errors="coerce")
    df = df[band.notna()]
    band = band[band.notna()].astype(int)
    if arm_col is None or arm_col not in df.columns:
        arm = pd.Series(equity_arm_from_band(band), index=df.index)
    else:
        arm = df[arm_col].astype(object)
    X = design_matrix(df, feature_cols)
    g = df[id_col].to_numpy()
    out: dict[str, Any] = {}
    band_res = grouped_cv_classification(X, band.to_numpy().astype(str), g, cv, seed, "mst_probe:band")
    out["band"] = {k: v for k, v in band_res.items() if k != "y_pred"}
    m = arm.notna().to_numpy()
    if m.sum() >= 2 * cv:
        arm_res = grouped_cv_classification(X[m], arm[m].to_numpy().astype(str), g[m], cv, seed, "mst_probe:arm")
        out["arm"] = {k: v for k, v in arm_res.items() if k != "y_pred"}
    else:
        out["arm"] = {"balanced_accuracy": float("nan"), "macro_f1": float("nan"), "chance": float("nan"),
                      "chance_macro_f1": float("nan"), "n": int(m.sum()), "n_classes": 0, "note": "too few rows with an arm"}
    out["table"] = pd.DataFrame([{"target": "mst_band", **out["band"]}, {"target": "mst_equity_arm", **out["arm"]}])
    return out
