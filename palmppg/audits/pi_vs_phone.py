"""Pi-versus-phone transfer table (protocol section 9 E16, section 7 per-band gaps).

Input: long results with one row per (arm, stratum, level) carrying the metric point estimate (and optional
lo/hi/n). Arms are either given in an ``arm`` column (E16 names: pi_proxy_to_pi_proxy, pi_proxy_to_phone,
phone_to_phone, pi_proxy_aug_to_phone) or derived from ``camera_train``, ``camera_test`` and ``augmented``.
Output: one row per (stratum, level) with a column per arm and the gaps
  gap_pi_to_phone      = pi_to_phone - pi_to_pi          (what is lost by moving the test camera)
  gap_vs_phone_native  = pi_to_phone - phone_to_phone    (transfer versus training on phone data)
  aug_gain             = pi_aug_to_phone - pi_to_phone   (what compression augmentation changes)
Signs are plain differences; with an error metric (lower is better) a negative gap is an improvement.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ARMS: tuple[str, ...] = ("pi_to_pi", "pi_to_phone", "phone_to_phone", "pi_aug_to_phone")
ARM_ALIASES: dict[str, str] = {
    "pi_to_pi": "pi_to_pi", "pi_proxy_to_pi_proxy": "pi_to_pi", "pi_proxy_to_pi": "pi_to_pi",
    "pi_to_phone": "pi_to_phone", "pi_proxy_to_phone": "pi_to_phone",
    "phone_to_phone": "phone_to_phone",
    "pi_aug_to_phone": "pi_aug_to_phone", "pi_proxy_aug_to_phone": "pi_aug_to_phone",
}
GAPS: dict[str, tuple[str, str]] = {"gap_pi_to_phone": ("pi_to_phone", "pi_to_pi"),
                                    "gap_vs_phone_native": ("pi_to_phone", "phone_to_phone"),
                                    "aug_gain": ("pi_aug_to_phone", "pi_to_phone")}


def derive_arm(camera_train: Any, camera_test: Any, augmented: Any = False) -> str | None:
    """Canonical arm from the train/test cameras (pi and pi_proxy both count as Pi) and the augmentation flag."""
    tr = "pi" if str(camera_train) in ("pi", "pi_proxy") else str(camera_train)
    te = "pi" if str(camera_test) in ("pi", "pi_proxy") else str(camera_test)
    aug = bool(augmented) if augmented is not None and not (isinstance(augmented, float) and np.isnan(augmented)) else False
    if tr == "pi" and te == "pi":
        return "pi_to_pi"
    if tr == "pi" and te == "phone":
        return "pi_aug_to_phone" if aug else "pi_to_phone"
    if tr == "phone" and te == "phone":
        return "phone_to_phone"
    return None


def transfer_table(results: pd.DataFrame, metric_col: str = "point", stratum_col: str = "stratum", level_col: str = "level",
                   n_col: str | None = "n", lower_is_better: bool = True) -> pd.DataFrame:
    """Wide per-(stratum, level) table of the E16 arms and their gaps; the overall row comes first."""
    df = results.copy()
    if "arm" in df.columns:
        df["__arm"] = df["arm"].astype(str).map(ARM_ALIASES)
    elif {"camera_train", "camera_test"} <= set(df.columns):
        aug = df["augmented"] if "augmented" in df.columns else pd.Series(False, index=df.index)
        df["__arm"] = [derive_arm(a, b, c) for a, b, c in zip(df["camera_train"], df["camera_test"], aug)]
    else:
        raise KeyError("results need an 'arm' column or camera_train/camera_test")
    unknown = df[df["__arm"].isna()]
    if len(unknown):
        raise ValueError(f"{len(unknown)} row(s) with an arm outside {ARMS}")
    for c in (metric_col, stratum_col, level_col):
        if c not in df.columns:
            raise KeyError(f"{c} not in results")
    df[level_col] = df[level_col].astype(str)
    keys = df[[stratum_col, level_col]].drop_duplicates()
    order = [(s, lv) for s, lv in zip(keys[stratum_col], keys[level_col])]
    order.sort(key=lambda k: (0 if k[0] == "overall" else 1))  # stable: keeps input order within groups
    wide = df.pivot_table(index=[stratum_col, level_col], columns="__arm", values=metric_col, aggfunc="first")
    out = pd.DataFrame(index=pd.MultiIndex.from_tuples(order, names=[stratum_col, level_col]))
    for arm in ARMS:
        out[arm] = wide[arm].reindex(out.index) if arm in wide.columns else np.nan
    if n_col and n_col in df.columns:
        nw = df.pivot_table(index=[stratum_col, level_col], columns="__arm", values=n_col, aggfunc="first")
        for arm in ARMS:
            out[f"n_{arm}"] = nw[arm].reindex(out.index) if arm in nw.columns else np.nan
    for gap, (a, b) in GAPS.items():
        out[gap] = out[a] - out[b]
    out = out.reset_index()
    out.attrs["lower_is_better"] = bool(lower_is_better)
    out.attrs["metric"] = metric_col
    return out


def transfer_markdown(table: pd.DataFrame, metric_label: str | None = None, lower_is_better: bool | None = None) -> str:
    lib = table.attrs.get("lower_is_better", True) if lower_is_better is None else lower_is_better
    cols = ["stratum", "level"] + [a for a in ARMS if a in table.columns] + list(GAPS)
    lines = [f"## Pi versus phone transfer (E16): {metric_label or table.attrs.get('metric', 'metric')}", "",
             "| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, r in table.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            cells.append(f"{v:.3f}" if isinstance(v, (float, np.floating)) and np.isfinite(v) else ("" if isinstance(v, float) else str(v)))
        lines.append("| " + " | ".join(cells) + " |")
    lines += ["", "gap_pi_to_phone = pi_to_phone - pi_to_pi; gap_vs_phone_native = pi_to_phone - phone_to_phone; "
                  "aug_gain = pi_aug_to_phone - pi_to_phone. " + ("Lower is better: a negative gap is an improvement."
                                                                   if lib else "Higher is better: a positive gap is an improvement.")]
    return "\n".join(lines) + "\n"


def write_transfer_markdown(table: pd.DataFrame, path: str | Path, metric_label: str | None = None) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(transfer_markdown(table, metric_label), encoding="utf-8")
    return p
