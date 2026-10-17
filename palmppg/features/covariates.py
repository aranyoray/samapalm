"""Derived stratification covariates that are not CRF fields: time of day, lux band, BP tertile.

Protocol section 7 lists "time of day (morning, afternoon)", "lux band" and "bp tertile" among the strata
every metric table is cut by; section 10 says reference tertiles are a reporting cut. The cut hour, the
lux edges and the time zone are read through `covariate_settings(cfg)` (config section `features`, with
the protocol defaults when the section is absent) so no caller hard-codes them.
"""
from __future__ import annotations

import datetime as dt
import math
from collections.abc import Iterable, Mapping, Sequence
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np

from ._common import is_null

DEFAULT_TZ = "Asia/Kolkata"
DEFAULT_CUT_HOUR = 13
DEFAULT_LUX_EDGES = (200.0, 400.0)
TERTILE_LABELS = ("T1", "T2", "T3")


def covariate_settings(cfg: Any = None) -> dict:
    """Settings for the derived covariates: `features.tz`, `features.time_of_day_cut_hour`,
    `features.lux_band_edges`, `features.tertile_labels`, with protocol defaults when missing."""
    get = cfg.get if cfg is not None and hasattr(cfg, "get") else (lambda k, d=None: d)
    edges = get("features.lux_band_edges", list(DEFAULT_LUX_EDGES))
    return {
        "tz": str(get("features.tz", DEFAULT_TZ)),
        "cut_hour": int(get("features.time_of_day_cut_hour", DEFAULT_CUT_HOUR)),
        "lux_edges": (float(edges[0]), float(edges[1])),
        "tertile_labels": tuple(get("features.tertile_labels", list(TERTILE_LABELS))),
    }


# --------------------------------------------------------------------------- time of day
def _to_local(ts: Any, tz: str) -> dt.datetime | None:
    zone = ZoneInfo(tz)
    if is_null(ts):
        return None
    if isinstance(ts, dt.datetime):
        d = ts if ts.tzinfo is not None else ts.replace(tzinfo=zone)
        return d.astimezone(zone)
    if isinstance(ts, (int, float, np.integer, np.floating)):
        ns = float(ts)
        if not math.isfinite(ns):
            return None
        # Wall-clock nanoseconds since the epoch (the `*_wall_ns` convention); seconds are also accepted
        # when the magnitude says so (anything below 1e12 cannot be ns in this century).
        seconds = ns / 1e9 if abs(ns) >= 1e12 else ns
        return dt.datetime.fromtimestamp(seconds, tz=dt.UTC).astimezone(zone)
    if isinstance(ts, str):
        s = ts.strip()
        if not s:
            return None
        if s.lstrip("+-").replace(".", "", 1).isdigit():
            return _to_local(float(s), tz)
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        try:
            d = dt.datetime.fromisoformat(s)
        except ValueError:
            return None
        return _to_local(d, tz)
    return None


def time_of_day(start_wall_ns: Any, tz: str = DEFAULT_TZ, cut_hour: int = DEFAULT_CUT_HOUR) -> str | None:
    """"morning" when the clip started before `cut_hour`:00 local time (default 13:00 in Asia/Kolkata),
    "afternoon" otherwise; None when the timestamp is missing or unparseable. Protocol section 7 stratum.

    Accepts wall-clock nanoseconds since the epoch (`start_wall_ns` from the Pi meta, audit use only),
    an ISO-8601 string (naive strings are taken as local time in `tz`), or a datetime.
    """
    local = _to_local(start_wall_ns, tz)
    if local is None:
        return None
    return "morning" if local.hour < int(cut_hour) else "afternoon"


# --------------------------------------------------------------------------- lux band
def lux_band_labels(edges: Sequence[float] = DEFAULT_LUX_EDGES) -> tuple[str, str, str]:
    lo, hi = float(edges[0]), float(edges[1])
    return (f"<{lo:g}", f"{lo:g}-{hi:g}", f">{hi:g}")


def lux_band(lux: Any, edges: Sequence[float] = DEFAULT_LUX_EDGES) -> str | None:
    """Ambient-light band for stratification (protocol section 7): "<200" when lux < 200,
    "200-400" when 200 <= lux <= 400 (both edges inclusive in the middle band), ">400" when lux > 400;
    None when lux is missing. Units: lux as logged by the capture unit."""
    if is_null(lux):
        return None
    try:
        x = float(lux)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(x):
        return None
    lo, hi = float(edges[0]), float(edges[1])
    labels = lux_band_labels(edges)
    if x < lo:
        return labels[0]
    if x <= hi:
        return labels[1]
    return labels[2]


# --------------------------------------------------------------------------- BP tertiles
def tertile_cuts(fit_values: Iterable[Any]) -> tuple[float, float]:
    """Cut points at the 1/3 and 2/3 quantiles (linear interpolation, NaN ignored) of the fitting set.
    The fitting set must be the development set only (protocol section 10): cut points chosen on the
    rows they are applied to would leak the reference distribution into the evaluation."""
    arr = np.asarray([np.nan if is_null(v) else float(v) for v in fit_values], dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size < 3:
        raise ValueError(f"need at least 3 finite values to place tertile cut points, got {arr.size}")
    c1, c2 = np.percentile(arr, [100.0 / 3.0, 200.0 / 3.0])
    return float(c1), float(c2)


def apply_tertiles(values: Iterable[Any], cuts: Sequence[float], labels: Sequence[str] = TERTILE_LABELS) -> list[str | None]:
    """Label each value: labels[0] when v <= cut1, labels[1] when cut1 < v <= cut2, labels[2] when v > cut2."""
    c1, c2 = float(cuts[0]), float(cuts[1])
    out: list[str | None] = []
    for v in values:
        if is_null(v):
            out.append(None)
            continue
        x = float(v)
        if not math.isfinite(x):
            out.append(None)
        elif x <= c1:
            out.append(str(labels[0]))
        elif x <= c2:
            out.append(str(labels[1]))
        else:
            out.append(str(labels[2]))
    return out


def bp_tertile(values: Iterable[Any], fit_values: Iterable[Any] | None = None,
               cuts: Sequence[float] | None = None, labels: Sequence[str] = TERTILE_LABELS) -> tuple[list[str | None], tuple[float, float]]:
    """Reference-BP tertile labels (protocol sections 7 and 10) and the cut points used.

    `cuts` wins when given; otherwise cut points are computed on `fit_values`, which must be the
    development-set references; when neither is given the cuts are computed on `values` themselves
    (acceptable only for a table that is entirely development data). Returns (labels, (cut1, cut2)), in mmHg.
    """
    vals = list(values)
    if cuts is None:
        cuts = tertile_cuts(list(fit_values) if fit_values is not None else vals)
    cuts_t = (float(cuts[0]), float(cuts[1]))
    return apply_tertiles(vals, cuts_t, labels), cuts_t


def bp_tertile_by_stream(values: Iterable[Any], streams: Iterable[Any], fit_stream: str = "development",
                         labels: Sequence[str] = TERTILE_LABELS) -> tuple[list[str | None], tuple[float, float], dict]:
    """Tertile labels for a mixed table: cut points from the rows whose stream equals `fit_stream`,
    applied to every row. Returns (labels, cuts, {"fit_stream", "n_fit"})."""
    vals = list(values)
    strs = list(streams)
    if len(vals) != len(strs):
        raise ValueError("values and streams must have the same length")
    fit = [v for v, s in zip(vals, strs) if s == fit_stream]
    lab, cuts = bp_tertile(vals, fit_values=fit, labels=labels)
    return lab, cuts, {"fit_stream": fit_stream, "n_fit": len([v for v in fit if not is_null(v)])}


def derived_strata(start_wall_ns: Any, lux: Any, settings: Mapping | None = None) -> dict[str, str | None]:
    """time_of_day and lux_band for one clip, using `covariate_settings`."""
    s = dict(settings or covariate_settings(None))
    return {
        "time_of_day": time_of_day(start_wall_ns, s["tz"], s["cut_hour"]),
        "lux_band": lux_band(lux, s["lux_edges"]),
    }
