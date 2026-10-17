"""StrataEngine: every metric overall AND per stratum (protocol section 7, non-negotiable 11.4), with
participant-level bootstrap CIs, pooled small cells and the two mandatory baselines (non-negotiable 11.2).

Output is one long table per metric with columns
  model (only from ``metric_table_with_baselines``), metric, stratum, level, n, n_participants, point, lo, hi,
  pooled (bool), note
and the overall row first. Levels with n below ``bootstrap.min_cell_n`` are pooled into one row labelled
``"other (pooled, n<<min_cell>)"`` with ``pooled = True`` and a note naming the pooled levels. Strata named in
the config but absent from the frame are still emitted (n = 0, note ``"column absent from table"``) so a report
can never silently skip a stratum. MST is reported per band (``mst_band``), grouped (``mst_group``: 4-5, 6-7,
8-10) and by ``equity_scope``; ``bp_tertile`` is derived from reference cut points passed in.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from palmppg.core.config import Config, load_pipeline_config
from palmppg.eval.bootstrap import participant_bootstrap
from palmppg.eval.metrics import tertile_labels

MISSING_LEVEL = "missing"
OVERALL = ("overall", "all")
MANDATORY_BASELINES = ("predict_mean", "demographics_only")
TABLE_COLUMNS = ["metric", "stratum", "level", "n", "n_participants", "point", "lo", "hi", "pooled", "note"]


def pooled_label(min_cell: int) -> str:
    return f"other (pooled, n<{int(min_cell)})"


def _level_key(v: Any):
    """Sort key: numbers first in numeric order, then strings, 'missing' last."""
    if v == MISSING_LEVEL:
        return (2, 0.0, "")
    try:
        return (0, float(v), "")
    except (TypeError, ValueError):
        return (1, 0.0, str(v))


def normalise_level_column(s: pd.Series) -> pd.Series:
    """Make a stratification column groupable: lists become sorted '+'-joined strings, booleans become
    'True'/'False', floats that are whole numbers lose their '.0', missing values become 'missing'."""
    def conv(v):
        if isinstance(v, (list, tuple, set, np.ndarray)):
            items = sorted(str(x) for x in v)
            return "+".join(items) if items else MISSING_LEVEL
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return MISSING_LEVEL
        if isinstance(v, (bool, np.bool_)):
            return str(bool(v))
        if isinstance(v, (float, np.floating)) and float(v).is_integer():
            return str(int(v))
        return str(v)

    return s.map(conv).astype(object)


class StrataEngine:
    """Builds the per-stratum metric tables of section 7 from the strata list and bootstrap settings in cfg."""

    def __init__(self, cfg: Config | None = None):
        self.cfg = cfg or load_pipeline_config()
        self.strata: list[str] = list(self.cfg.get("strata"))
        self.min_cell: int = int(self.cfg.get("bootstrap.min_cell_n"))
        self.n_resamples: int = int(self.cfg.get("bootstrap.n_resamples"))
        self.ci: float = float(self.cfg.get("bootstrap.ci"))
        self.seed: int = int(self.cfg.get("study.seed"))
        self.equity_lo: int = int(self.cfg.get("crf.equity_min_band"))
        self.equity_hi: int = int(self.cfg.get("crf.equity_max_band"))

    # ----------------------------------------------------------------- derived stratification columns
    def derive_columns(self, df: pd.DataFrame, tertile_cuts: Sequence[float] | None = None,
                       reference_col: str = "bp_target_sbp") -> pd.DataFrame:
        """Add mst_group / equity_scope / mst_equity_arm from mst_band and bp_tertile from ``tertile_cuts``
        applied to ``reference_col`` when those columns are absent (section 7 MST and BP tertile strata)."""
        out = df.copy()
        if "mst_band" in out.columns:
            band = pd.to_numeric(out["mst_band"], errors="coerce")
            if "mst_group" not in out.columns:
                out["mst_group"] = np.select(
                    [band < self.equity_lo, band <= 5, band <= 7, band <= self.equity_hi],
                    ["1-3", "4-5", "6-7", "8-10"], default=None)
                out.loc[band.isna(), "mst_group"] = None
            if "equity_scope" not in out.columns:
                out["equity_scope"] = np.where(band.between(self.equity_lo, self.equity_hi), "in", "out")
                out.loc[band.isna(), "equity_scope"] = None
            if "mst_equity_arm" not in out.columns:
                out["mst_equity_arm"] = np.select([band.between(4, 6), band.between(7, 10)], ["4-6", "7-10"], default=None)
                out.loc[band.isna(), "mst_equity_arm"] = None
        if tertile_cuts is not None and "bp_tertile" not in out.columns and reference_col in out.columns:
            out["bp_tertile"] = tertile_labels(pd.to_numeric(out[reference_col], errors="coerce").to_numpy(), tertile_cuts)
        return out

    # ----------------------------------------------------------------- one cell
    def _cell(self, sub: pd.DataFrame, metric_fn: Callable[[pd.DataFrame], float], id_col: str,
              n_boot: int, salt: str, seed: int) -> tuple[float, float, float, int]:
        n_part = int(sub[id_col].nunique()) if id_col in sub.columns else len(sub)
        if len(sub) == 0:
            return float("nan"), float("nan"), float("nan"), 0
        if n_boot <= 0 or id_col not in sub.columns:
            try:
                point = float(metric_fn(sub))
            except (ValueError, ZeroDivisionError):
                point = float("nan")
            return point, float("nan"), float("nan"), n_part
        r = participant_bootstrap(sub, metric_fn, id_col=id_col, n=n_boot, ci=self.ci, seed=seed, salt=salt, cfg=self.cfg)
        return r.point, r.lo, r.hi, r.n_participants

    # ----------------------------------------------------------------- main table
    def metric_table(self, df: pd.DataFrame, metric_fn: Callable[[pd.DataFrame], float],
                     strata: Sequence[str] | None = None, min_cell: int | None = None,
                     bootstrap: int | bool | None = None, id_col: str = "study_id", metric_name: str = "metric",
                     tertile_cuts: Sequence[float] | None = None, reference_col: str = "bp_target_sbp",
                     seed: int | None = None) -> pd.DataFrame:
        """Long table of ``metric_fn`` overall (first row) and per level of every stratum (section 7).

        ``bootstrap``: None -> cfg ``bootstrap.n_resamples``; an int -> that many resamples; 0/False -> no CI.
        ``min_cell`` defaults to cfg ``bootstrap.min_cell_n``. Levels below it are pooled and flagged.
        """
        strata = list(self.strata if strata is None else strata)
        min_cell = self.min_cell if min_cell is None else int(min_cell)
        n_boot = self.n_resamples if bootstrap is None else (0 if bootstrap is False else int(bootstrap))
        seed = self.seed if seed is None else int(seed)
        data = self.derive_columns(df, tertile_cuts, reference_col)
        rows: list[dict[str, Any]] = []

        point, lo, hi, n_part = self._cell(data, metric_fn, id_col, n_boot, "overall", seed)
        rows.append({"metric": metric_name, "stratum": OVERALL[0], "level": OVERALL[1], "n": len(data),
                     "n_participants": n_part, "point": point, "lo": lo, "hi": hi, "pooled": False, "note": ""})

        for s in strata:
            if s not in data.columns:
                rows.append({"metric": metric_name, "stratum": s, "level": None, "n": 0, "n_participants": 0,
                             "point": float("nan"), "lo": float("nan"), "hi": float("nan"), "pooled": False,
                             "note": "column absent from table"})
                continue
            lev = normalise_level_column(data[s])
            counts = lev.value_counts()
            levels = sorted(counts.index.tolist(), key=_level_key)
            big = [v for v in levels if counts[v] >= min_cell]
            small = [v for v in levels if counts[v] < min_cell]
            for v in big:
                sub = data[lev == v]
                point, lo, hi, n_part = self._cell(sub, metric_fn, id_col, n_boot, f"{s}:{v}", seed)
                rows.append({"metric": metric_name, "stratum": s, "level": str(v), "n": len(sub),
                             "n_participants": n_part, "point": point, "lo": lo, "hi": hi, "pooled": False,
                             "note": "missing values" if v == MISSING_LEVEL else ""})
            if small:
                sub = data[lev.isin(small)]
                point, lo, hi, n_part = self._cell(sub, metric_fn, id_col, n_boot, f"{s}:pooled", seed)
                inside = ", ".join(f"{v} (n={int(counts[v])})" for v in small)
                note = f"pooled levels: {inside}"
                if len(sub) < min_cell:
                    note += f"; pooled cell still below n={min_cell}"
                rows.append({"metric": metric_name, "stratum": s, "level": pooled_label(min_cell), "n": len(sub),
                             "n_participants": n_part, "point": point, "lo": lo, "hi": hi, "pooled": True, "note": note})
        out = pd.DataFrame(rows, columns=TABLE_COLUMNS)
        out["pooled"] = out["pooled"].astype(bool)
        return out

    def metric_table_with_baselines(self, df: pd.DataFrame, metric_fn: Callable[[np.ndarray, np.ndarray], float],
                                    pred_cols: Mapping[str, str], y_col: str = "bp_target_sbp",
                                    abstain_cols: Mapping[str, str] | None = None, **kw) -> pd.DataFrame:
        """Same table for the model and the two mandatory baselines (non-negotiable 11.2), stacked with a
        leading ``model`` column. ``pred_cols`` must contain ``model``, ``predict_mean`` and
        ``demographics_only`` -> prediction column names; ``metric_fn(y_true, y_pred) -> float``.
        ``abstain_cols`` optionally maps a model name to a boolean abstention column; abstained rows get a NaN
        prediction so coverage-aware metrics count them as failures."""
        missing = [k for k in MANDATORY_BASELINES if k not in pred_cols]
        if missing:
            raise ValueError(f"both baselines are mandatory in every table; missing: {missing}")
        if "model" not in pred_cols:
            raise ValueError("pred_cols must name the 'model' prediction column")
        if y_col not in df.columns:
            raise KeyError(f"{y_col} not in frame")
        parts = []
        for name, col in pred_cols.items():
            if col not in df.columns:
                raise KeyError(f"prediction column {col} for {name} not in frame")
            work = df.copy()
            pred = pd.to_numeric(work[col], errors="coerce").astype(float)
            if abstain_cols and name in abstain_cols and abstain_cols[name] in work.columns:
                pred = pred.mask(work[abstain_cols[name]].astype(bool))
            work["__pred"] = pred
            t = self.metric_table(work, lambda d: metric_fn(d[y_col].to_numpy(dtype=float), d["__pred"].to_numpy(dtype=float)), **kw)
            t.insert(0, "model", name)
            parts.append(t)
        return pd.concat(parts, ignore_index=True)


# --------------------------------------------------------------------------- writers
def _fmt(v: Any, nd: int = 3) -> str:
    if v is None:
        return ""
    if isinstance(v, (bool, np.bool_)):
        return "yes" if v else "no"
    if isinstance(v, (float, np.floating)):
        return "" if not np.isfinite(v) else f"{v:.{nd}f}"
    return str(v)


def table_to_markdown(table: pd.DataFrame, title: str | None = None, columns: Sequence[str] | None = None,
                      nd: int = 3) -> str:
    """Render a strata table as a GitHub-flavoured markdown table (no external dependency)."""
    cols = list(columns) if columns else [c for c in (["model"] + TABLE_COLUMNS) if c in table.columns]
    lines = []
    if title:
        lines += [f"### {title}", ""]
    lines.append("| " + " | ".join(cols) + " |")
    lines.append("|" + "|".join(["---"] * len(cols)) + "|")
    for _, r in table.iterrows():
        lines.append("| " + " | ".join(_fmt(r[c], nd).replace("|", "/") for c in cols) + " |")
    lines.append("")
    lines.append("Cells with n below the minimum are pooled and flagged in the `pooled` column; "
                 "CIs are participant-level bootstrap percentile intervals.")
    return "\n".join(lines) + "\n"


def write_markdown(table: pd.DataFrame, path: str | Path, title: str | None = None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(table_to_markdown(table, title), encoding="utf-8")
    return path


def write_parquet(table: pd.DataFrame, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    out = table.copy()
    if "level" in out.columns:
        out["level"] = out["level"].map(lambda v: None if v is None else str(v)).astype(object)
    out.to_parquet(path, index=False)
    return path
