"""Agreement, rhythm and pulse-rate metrics (protocol section 10; coverage rule of section 11.3).

Conventions
  * ``error = y_pred - y_true`` (predicted minus reference), in the units of the target (mmHg for BP).
  * A reading counts as *covered* only when it was attempted, produced a finite prediction and was not
    abstained. Failed clips (NaN prediction) and abstentions count as failures in coverage (section 11.3).
  * The AAMI-style and IEEE 1708-style tables are output *formats* borrowed from those documents so the pilot
    numbers can be read in a familiar layout. Every such table carries the label
    ``"format only, not a compliance claim"`` and nothing here asserts compliance with either document.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

FORMAT_LABEL = "format only, not a compliance claim"

# Published cut-offs of the two summary formats (not study thresholds; the study thresholds live in
# configs/frozen_config.yaml). Kept as named defaults so a table can be rebuilt with other cut-offs if needed.
IEEE1708_MAD_GRADE_CUTS_MMHG: tuple[float, float, float] = (5.0, 6.0, 7.0)   # A <= 5, B <= 6, C <= 7, D above
IEEE1708_GRADES: tuple[str, ...] = ("A", "B", "C", "D")
WITHIN_BANDS_MMHG: tuple[float, ...] = (5.0, 10.0, 15.0)                     # cumulative |error| bands


def _as_float(a) -> np.ndarray:
    return np.asarray(a, dtype=float).ravel()


def coverage_mask(y_pred, abstain_mask=None) -> np.ndarray:
    """Boolean mask of covered readings: finite prediction and not abstained (section 11.3)."""
    p = _as_float(y_pred)
    covered = np.isfinite(p)
    if abstain_mask is not None:
        a = np.asarray(abstain_mask, dtype=bool).ravel()
        if a.shape != p.shape:
            raise ValueError("abstain_mask must have the same length as y_pred")
        covered &= ~a
    return covered


def limits_of_agreement(errors, ci: float = 0.95) -> tuple[float, float, float, float]:
    """Bland-Altman bias, SD (ddof=1) and the ``ci`` limits of agreement bias +/- z * SD (section 10)."""
    e = _as_float(errors)
    e = e[np.isfinite(e)]
    if e.size < 2:
        return (float(np.mean(e)) if e.size else float("nan"), float("nan"), float("nan"), float("nan"))
    bias = float(np.mean(e))
    sd = float(np.std(e, ddof=1))
    z = float(stats.norm.ppf(1.0 - (1.0 - ci) / 2.0))
    return bias, sd, bias - z * sd, bias + z * sd


def reference_tertile_cuts(y_true) -> tuple[float, float]:
    """Tertile cut points (33.3rd and 66.7th percentiles) of a reference distribution; compute these once on
    development data and pass them to ``bp_metrics`` / ``StrataEngine`` (section 10, error by reference tertile)."""
    y = _as_float(y_true)
    y = y[np.isfinite(y)]
    if y.size == 0:
        raise ValueError("no finite reference values")
    c1, c2 = np.percentile(y, [100.0 / 3.0, 200.0 / 3.0])
    return float(c1), float(c2)


def tertile_names(cuts: Sequence[float]) -> list[str]:
    """The three tertile labels for a pair of cut points: 'T1 (< c1)', 'T2 (c1 .. c2)', 'T3 (>= c2)'."""
    c1, c2 = float(cuts[0]), float(cuts[1])
    if not c1 < c2:
        raise ValueError("tertile cuts must be increasing")
    return [f"T1 (< {c1:g})", f"T2 ({c1:g} .. {c2:g})", f"T3 (>= {c2:g})"]


def tertile_labels(y_true, cuts: Sequence[float]) -> np.ndarray:
    """Map reference values onto the ``tertile_names`` labels; non-finite references map to None."""
    c1, c2 = float(cuts[0]), float(cuts[1])
    y = _as_float(y_true)
    names = np.array(tertile_names(cuts), dtype=object)
    idx = np.where(y < c1, 0, np.where(y < c2, 1, 2))
    out = names[idx].astype(object)
    out[~np.isfinite(y)] = None
    return out


def error_by_reference_tertile(y_true, y_pred, cuts: Sequence[float], abstain_mask=None) -> pd.DataFrame:
    """Bias, error SD, MAE and n per reference tertile (cut points passed in; section 10)."""
    y = _as_float(y_true)
    p = _as_float(y_pred)
    cov = coverage_mask(p, abstain_mask) & np.isfinite(y)
    labels = tertile_labels(y, cuts)
    rows = []
    for name in tertile_names(cuts):
        m = cov & (labels == name)
        e = p[m] - y[m]
        bias, sd, _, _ = limits_of_agreement(e)
        rows.append({"tertile": name, "n": int(m.sum()), "bias": bias, "error_sd": sd,
                     "mae": float(np.mean(np.abs(e))) if e.size else float("nan")})
    return pd.DataFrame(rows)


def aami_format_table(errors, label: str = FORMAT_LABEL) -> pd.DataFrame:
    """Mean error, SD and n in the AAMI/ISO 81060-2 summary *layout* (one row). Labelled as format only."""
    e = _as_float(errors)
    e = e[np.isfinite(e)]
    bias, sd, _, _ = limits_of_agreement(e)
    return pd.DataFrame([{"n": int(e.size), "mean_error": bias, "error_sd": sd, "label": label}])


def ieee1708_format_table(errors, grade_cuts: Sequence[float] = IEEE1708_MAD_GRADE_CUTS_MMHG,
                          within_bands: Sequence[float] = WITHIN_BANDS_MMHG, label: str = FORMAT_LABEL) -> pd.DataFrame:
    """Mean absolute difference (MAD), the A-D grade band it falls in (cuts 5/6/7 by default) and the cumulative
    percentage of |error| within each band (5/10/15 by default), in the IEEE 1708 summary *layout*. Format only."""
    e = _as_float(errors)
    e = e[np.isfinite(e)]
    mad = float(np.mean(np.abs(e))) if e.size else float("nan")
    grade = None
    if np.isfinite(mad):
        grade = IEEE1708_GRADES[-1]
        for g, cut in zip(IEEE1708_GRADES, grade_cuts):
            if mad <= cut:
                grade = g
                break
    row: dict[str, Any] = {"n": int(e.size), "mad": mad, "grade": grade,
                           "grade_cuts": ", ".join(f"{g} <= {c:g}" for g, c in zip(IEEE1708_GRADES, grade_cuts))}
    for b in within_bands:
        row[f"pct_within_{b:g}"] = float(100.0 * np.mean(np.abs(e) <= b)) if e.size else float("nan")
    row["label"] = label
    return pd.DataFrame([row])


def bp_metrics(y_true, y_pred, abstain_mask=None, tertile_cuts: Sequence[float] | None = None,
               n_attempted: int | None = None, ci: float = 0.95) -> dict[str, Any]:
    """BP agreement summary (section 10) on covered readings, with coverage per section 11.3.

    Returns bias, error_sd (ddof=1), mae, rmse, loa_low/loa_high (``ci`` limits of agreement), n (covered),
    n_abstained, n_failed (non-finite prediction), n_attempted, coverage_pct = 100 * n / n_attempted,
    error_by_reference_tertile (DataFrame when ``tertile_cuts`` is given, else None), aami_format_table and
    ieee1708_format_table (both labelled format only). ``n_attempted`` defaults to len(y_true); pass a larger
    number when failed clips were dropped before scoring so they still count as failures.
    """
    y = _as_float(y_true)
    p = _as_float(y_pred)
    if y.shape != p.shape:
        raise ValueError("y_true and y_pred must have the same length")
    abst = np.zeros_like(p, dtype=bool) if abstain_mask is None else np.asarray(abstain_mask, dtype=bool).ravel()
    cov = coverage_mask(p, abst) & np.isfinite(y)
    n_att = int(len(y) if n_attempted is None else n_attempted)
    if n_att < len(y):
        raise ValueError("n_attempted cannot be smaller than the number of scored rows")
    e = p[cov] - y[cov]
    bias, sd, lo, hi = limits_of_agreement(e, ci)
    out: dict[str, Any] = {
        "bias": bias, "error_sd": sd, "mae": float(np.mean(np.abs(e))) if e.size else float("nan"),
        "rmse": float(np.sqrt(np.mean(e**2))) if e.size else float("nan"),
        "loa_low": lo, "loa_high": hi, "loa_ci": ci,
        "n": int(cov.sum()), "n_abstained": int(abst.sum()),
        "n_failed": int((~np.isfinite(p) & ~abst).sum()), "n_attempted": n_att,
        "coverage_pct": float(100.0 * cov.sum() / n_att) if n_att else float("nan"),
        "error_by_reference_tertile": (error_by_reference_tertile(y, p, tertile_cuts, abst)
                                       if tertile_cuts is not None else None),
        "tertile_cuts": tuple(float(c) for c in tertile_cuts) if tertile_cuts is not None else None,
        "aami_format_table": aami_format_table(e),
        "ieee1708_format_table": ieee1708_format_table(e),
        "format_label": FORMAT_LABEL,
    }
    return out


# --------------------------------------------------------------------------- rhythm
def clopper_pearson(k: int, n: int, ci: float = 0.95) -> tuple[float, float]:
    """Exact binomial (Clopper-Pearson) two-sided ``ci`` interval for k successes in n trials."""
    if n <= 0:
        return float("nan"), float("nan")
    a = 1.0 - ci
    lo = 0.0 if k == 0 else float(stats.beta.ppf(a / 2.0, k, n - k + 1))
    hi = 1.0 if k == n else float(stats.beta.ppf(1.0 - a / 2.0, k + 1, n - k))
    return lo, hi


def threshold_for_target(y_true, y_score, sensitivity_target: float | None = None,
                         specificity_target: float | None = None) -> float:
    """Choose an operating threshold on *development* data: the largest threshold reaching the sensitivity
    target, or the smallest reaching the specificity target (section 10, pre-specified operating points).
    Never call this on the data being reported."""
    if (sensitivity_target is None) == (specificity_target is None):
        raise ValueError("give exactly one of sensitivity_target / specificity_target")
    y = np.asarray(y_true).astype(int).ravel()
    s = _as_float(y_score)
    cands = np.unique(s)
    if sensitivity_target is not None:
        pos = s[y == 1]
        for t in cands[::-1]:
            if np.mean(pos >= t) >= sensitivity_target:
                return float(t)
        return float(cands[0])
    neg = s[y == 0]
    for t in cands:
        if np.mean(neg < t) >= specificity_target:
            return float(t)
    return float(cands[-1]) + 1.0


def rhythm_metrics(y_true, y_score, operating_point: float, ci: float = 0.95) -> dict[str, Any]:
    """Sensitivity, specificity, PPV, NPV (each with exact Clopper-Pearson ``ci`` intervals), AUROC and AUPRC
    at a pre-specified operating point (predict positive when score >= operating_point); section 10 rhythm.
    Rows with a non-finite score count as negative predictions and are reported in ``n_failed``."""
    from sklearn.metrics import average_precision_score, roc_auc_score

    y = np.asarray(y_true).astype(int).ravel()
    s = _as_float(y_score)
    if y.shape != s.shape:
        raise ValueError("y_true and y_score must have the same length")
    finite = np.isfinite(s)
    pred = finite & (s >= float(operating_point))
    tp = int(np.sum(pred & (y == 1)))
    fp = int(np.sum(pred & (y == 0)))
    fn = int(np.sum(~pred & (y == 1)))
    tn = int(np.sum(~pred & (y == 0)))

    def _rate(k, n):
        p = (k / n) if n else float("nan")
        lo, hi = clopper_pearson(k, n, ci)
        return p, lo, hi

    out: dict[str, Any] = {"threshold": float(operating_point), "n": int(y.size), "n_failed": int((~finite).sum()),
                           "n_pos": int((y == 1).sum()), "n_neg": int((y == 0).sum()),
                           "tp": tp, "fp": fp, "fn": fn, "tn": tn, "ci": ci}
    for name, k, n in (("sensitivity", tp, tp + fn), ("specificity", tn, tn + fp),
                       ("ppv", tp, tp + fp), ("npv", tn, tn + fn)):
        v, lo, hi = _rate(k, n)
        out[name], out[name + "_lo"], out[name + "_hi"] = v, lo, hi
    both = finite & np.isin(y, (0, 1))
    if np.unique(y[both]).size == 2:
        out["auc"] = float(roc_auc_score(y[both], s[both]))
        out["auprc"] = float(average_precision_score(y[both], s[both]))
    else:
        out["auc"] = float("nan")
        out["auprc"] = float("nan")
    return out


# --------------------------------------------------------------------------- pulse rate
def pulse_rate_metrics(hr_ppg, hr_ecg, tol_bpm: float) -> dict[str, Any]:
    """Pulse rate versus ECG heart rate (section 9 E1, go/no-go of section 10): MAE and bias in bpm over clips
    with a finite pulse-rate estimate, and ``within_tol_pct`` = 100 * |diff| <= tol over *all attempted*
    clips, so a clip with no pulse-rate estimate counts as outside tolerance (section 11.3)."""
    a = _as_float(hr_ppg)
    b = _as_float(hr_ecg)
    if a.shape != b.shape:
        raise ValueError("hr_ppg and hr_ecg must have the same length")
    ok = np.isfinite(a) & np.isfinite(b)
    d = a[ok] - b[ok]
    n_att = int(b.size)
    within = int(np.sum(np.abs(d) <= float(tol_bpm)))
    return {"mae": float(np.mean(np.abs(d))) if d.size else float("nan"),
            "bias": float(np.mean(d)) if d.size else float("nan"),
            "within_tol_pct": float(100.0 * within / n_att) if n_att else float("nan"),
            "tol_bpm": float(tol_bpm), "n": int(ok.sum()), "n_attempted": n_att, "n_failed": int(n_att - ok.sum())}


def metrics_to_frame(d: Mapping[str, Any]) -> pd.DataFrame:
    """Flatten a metrics dict (scalars only) into a one-row DataFrame for parquet output."""
    return pd.DataFrame([{k: v for k, v in d.items() if np.isscalar(v) or v is None}])
