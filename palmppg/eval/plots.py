"""Headless matplotlib figures for the evaluation reports (protocol sections 7, 8 and 10; E6, E16).

Every function returns a ``matplotlib.figure.Figure`` and, when ``path`` is given, writes both ``<path>.png``
and ``<path>.svg`` (the suffix of ``path`` is replaced). The Agg backend is selected at import so the module
works on a machine with no display. Colours follow one fixed categorical order (never cycled), one y-axis per
figure, thin marks and recessive grid lines; a legend is drawn whenever two or more series share an axis.
"""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.figure import Figure

from palmppg.eval.metrics import limits_of_agreement

# Fixed categorical order (blue, orange, aqua, yellow, magenta, green, violet, red): a series keeps its colour
# whatever is filtered out, and a ninth series folds into "other".
SERIES_COLOURS: tuple[str, ...] = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948")
INK = "#0b0b0b"
MUTED = "#52514e"
GRID = "#d8d7d2"


def _style(ax) -> None:
    ax.grid(True, color=GRID, linewidth=0.6, alpha=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(colors=MUTED, labelsize=8)


def save_figure(fig: Figure, path: str | Path | None) -> tuple[Path, Path] | None:
    """Write PNG and SVG next to each other; returns the two paths or None when ``path`` is None."""
    if path is None:
        return None
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    png, svg = p.with_suffix(".png"), p.with_suffix(".svg")
    fig.savefig(png, dpi=150, bbox_inches="tight")
    fig.savefig(svg, bbox_inches="tight")
    return png, svg


def _colour(i: int) -> str:
    return SERIES_COLOURS[i % len(SERIES_COLOURS)]


def bland_altman(ax, y, pred, title: str | None = None, units: str = "mmHg", ci: float = 0.95,
                 path: str | Path | None = None) -> Figure:
    """Bland-Altman plot of (pred - y) against the mean of the two, with bias and the limits of agreement
    (section 10). ``ax`` may be None to create a new figure."""
    y = np.asarray(y, dtype=float).ravel()
    p = np.asarray(pred, dtype=float).ravel()
    ok = np.isfinite(y) & np.isfinite(p)
    y, p = y[ok], p[ok]
    if ax is None:
        fig, ax = plt.subplots(figsize=(5.5, 4))
    else:
        fig = ax.figure
    diff = p - y
    mean = (p + y) / 2.0
    bias, _sd, lo, hi = limits_of_agreement(diff, ci)
    ax.scatter(mean, diff, s=12, color=_colour(0), alpha=0.6, linewidths=0)
    for v, lab, ls in ((bias, f"bias {bias:.1f}", "-"), (lo, f"LoA {lo:.1f}", "--"), (hi, f"LoA {hi:.1f}", "--")):
        if np.isfinite(v):
            ax.axhline(v, color=INK, linewidth=1.0, linestyle=ls)
            ax.text(ax.get_xlim()[1] if mean.size else 0, v, " " + lab, va="center", fontsize=8, color=MUTED)
    ax.set_xlabel(f"mean of reference and prediction ({units})", fontsize=9)
    ax.set_ylabel(f"prediction - reference ({units})", fontsize=9)
    ax.set_title(title or f"Bland-Altman (n={y.size})", fontsize=10, color=INK)
    _style(ax)
    save_figure(fig, path)
    return fig


def degradation_curves(df: pd.DataFrame, metric_col: str, severity_col: str = "severity", series_col: str = "method",
                       facet_col: str | None = "camera", path: str | Path | None = None,
                       ylabel: str | None = None) -> Figure:
    """Metric versus corruption severity, one line per ``series_col``, one panel per ``facet_col`` sharing the
    y-axis (section 8 outputs). Series keep a fixed colour across panels."""
    facets = list(pd.unique(df[facet_col])) if facet_col and facet_col in df.columns else [None]
    series = list(pd.unique(df[series_col]))
    fig, axes = plt.subplots(1, len(facets), figsize=(4.2 * len(facets), 3.6), sharey=True, squeeze=False)
    for ax, fac in zip(axes[0], facets):
        sub = df if fac is None else df[df[facet_col] == fac]
        for i, s in enumerate(series):
            ss = sub[sub[series_col] == s].sort_values(severity_col)
            if ss.empty:
                continue
            ax.plot(ss[severity_col].to_numpy(), ss[metric_col].to_numpy(), marker="o", markersize=4, linewidth=1.6,
                    color=_colour(i), label=str(s))
        ax.set_title(str(fac) if fac is not None else "", fontsize=10, color=INK)
        ax.set_xlabel(severity_col, fontsize=9)
        _style(ax)
    axes[0][0].set_ylabel(ylabel or metric_col, fontsize=9)
    if len(series) > 1:
        axes[0][-1].legend(fontsize=8, frameon=False, title=series_col, title_fontsize=8)
    fig.tight_layout()
    save_figure(fig, path)
    return fig


def strata_forest(table: pd.DataFrame, path: str | Path | None = None, metric_label: str | None = None,
                  max_rows: int | None = None) -> Figure:
    """Forest plot of a StrataEngine table: one marker per (stratum, level) with its bootstrap interval; the
    overall row is drawn first and as a vertical reference, pooled rows use hollow markers (section 7)."""
    t = table[table["level"].notna()].copy()
    if "model" in t.columns and t["model"].nunique() > 1:
        t = t[t["model"] == t["model"].iloc[0]]
    if max_rows:
        t = t.head(max_rows)
    labels = [f"{s}: {lv} (n={int(n)})" for s, lv, n in zip(t["stratum"], t["level"], t["n"])]
    ypos = np.arange(len(t))[::-1]
    fig, ax = plt.subplots(figsize=(6.5, max(3.0, 0.24 * len(t) + 1.0)))
    pts = t["point"].to_numpy(dtype=float)
    lo = t["lo"].to_numpy(dtype=float)
    hi = t["hi"].to_numpy(dtype=float)
    pooled = t["pooled"].to_numpy(dtype=bool)
    for yy, pt, l_, h_, pl in zip(ypos, pts, lo, hi, pooled):
        if np.isfinite(l_) and np.isfinite(h_):
            ax.plot([l_, h_], [yy, yy], color=_colour(0), linewidth=1.2)
        ax.plot([pt], [yy], marker="o", markersize=5, color=_colour(0), markerfacecolor="white" if pl else _colour(0))
    if len(pts) and np.isfinite(pts[0]):
        ax.axvline(pts[0], color=MUTED, linewidth=0.8, linestyle=":")
    ax.set_yticks(ypos)
    ax.set_yticklabels(labels, fontsize=7)
    ax.set_xlabel(metric_label or str(t["metric"].iloc[0] if len(t) else "metric"), fontsize=9)
    ax.set_title("per-stratum estimates with participant bootstrap CI (hollow = pooled cell)", fontsize=9, color=INK)
    _style(ax)
    fig.tight_layout()
    save_figure(fig, path)
    return fig


def calibration_plot(reliability: pd.DataFrame, path: str | Path | None = None, title: str | None = None) -> Figure:
    """Reliability diagram from ``palmppg.eval.calibration.reliability_table``: observed fraction against mean
    predicted probability per bin, with the identity line and bin counts as marker size (section 10)."""
    t = reliability[reliability["n"] > 0]
    fig, ax = plt.subplots(figsize=(4.5, 4.5))
    ax.plot([0, 1], [0, 1], color=MUTED, linewidth=0.8, linestyle="--", label="ideal")
    sizes = 20 + 80 * t["n"].to_numpy(dtype=float) / max(float(t["n"].max()), 1.0) if len(t) else []
    ax.plot(t["mean_pred"], t["frac_pos"], color=_colour(0), linewidth=1.4, label="model")
    ax.scatter(t["mean_pred"], t["frac_pos"], s=sizes, color=_colour(0), zorder=3, linewidths=0)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel("mean predicted probability", fontsize=9)
    ax.set_ylabel("observed fraction", fontsize=9)
    ax.set_title(title or "reliability", fontsize=10, color=INK)
    ax.legend(fontsize=8, frameon=False)
    _style(ax)
    fig.tight_layout()
    save_figure(fig, path)
    return fig


def decision_curve_plot(dc: pd.DataFrame, path: str | Path | None = None, title: str | None = None) -> Figure:
    """Net benefit against threshold probability for the model, treat-all and treat-none (section 10)."""
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.plot(dc["threshold"], dc["net_benefit_model"], color=_colour(0), linewidth=1.8, label="model")
    ax.plot(dc["threshold"], dc["net_benefit_all"], color=_colour(1), linewidth=1.2, label="treat all")
    ax.plot(dc["threshold"], dc["net_benefit_none"], color=MUTED, linewidth=1.0, linestyle="--", label="treat none")
    nb = dc[["net_benefit_model", "net_benefit_all"]].to_numpy(dtype=float)
    nb = nb[np.isfinite(nb)]
    if nb.size:
        ax.set_ylim(max(-0.05, float(nb.min()) - 0.02), float(nb.max()) + 0.02)
    ax.set_xlabel("threshold probability", fontsize=9)
    ax.set_ylabel("net benefit", fontsize=9)
    ax.set_title(title or "decision curve", fontsize=10, color=INK)
    ax.legend(fontsize=8, frameon=False)
    _style(ax)
    fig.tight_layout()
    save_figure(fig, path)
    return fig


def pi_vs_phone_bars(transfer: pd.DataFrame, arms: Sequence[str] | None = None, path: str | Path | None = None,
                     metric_label: str | None = None) -> Figure:
    """Grouped bars of the transfer metric per (stratum, level) with one bar per arm (E16, section 9)."""
    if arms is None:
        arms = [c for c in transfer.columns if c in ("pi_to_pi", "pi_to_phone", "phone_to_phone", "pi_aug_to_phone")]
    levels = [f"{s}: {lv}" for s, lv in zip(transfer["stratum"], transfer["level"])]
    x = np.arange(len(levels))
    w = 0.8 / max(len(arms), 1)
    fig, ax = plt.subplots(figsize=(max(5.0, 0.9 * len(levels) + 2), 3.8))
    for i, arm in enumerate(arms):
        vals = transfer[arm].to_numpy(dtype=float) if arm in transfer.columns else np.full(len(levels), np.nan)
        ax.bar(x + (i - (len(arms) - 1) / 2) * w, vals, width=w * 0.92, color=_colour(i), label=arm, linewidth=0)
    ax.set_xticks(x)
    ax.set_xticklabels(levels, fontsize=8, rotation=20, ha="right")
    ax.set_ylabel(metric_label or "metric", fontsize=9)
    ax.set_title("Pi versus phone transfer", fontsize=10, color=INK)
    if len(arms) > 1:
        ax.legend(fontsize=8, frameon=False)
    _style(ax)
    fig.tight_layout()
    save_figure(fig, path)
    return fig
