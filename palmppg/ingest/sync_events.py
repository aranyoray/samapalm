"""Sync-event log (``pi/sync_events.csv``), pulse-pattern specs and pulse-sequence matching.

Serves protocol section 4.2 (hardware marker on the Pi: patterns P1/P2 logged as GPIO edges on the
reference clock) and section 2 (analysis windows adapt from the log, never from hard-coded times).

Every time returned here is ``t_ref_s``: float seconds on the Pi CLOCK_BOOTTIME clock relative to
``t0_ref_ns`` (first Pi frame, DECISIONS D-001). Wall-clock columns are carried for audit only.
"""
from __future__ import annotations

import io
import os
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pandas as pd

from palmppg.core.config import Config

SYNC_EVENT_COLUMNS = ("event_id", "kind", "pattern", "mono_ns", "wall_ns", "gpio_ok")
EDGE_KINDS = ("start", "end")
PATTERN_NAMES = ("P1", "P2")

_TRUE = {"1", "true", "t", "yes", "y", "ok", "pass"}
_FALSE = {"0", "false", "f", "no", "n", "fail", "nok", "", "nan", "none"}


def _to_bool(v: Any) -> bool:
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (int, float, np.integer, np.floating)):
        return bool(v) and not (isinstance(v, float) and np.isnan(v))
    s = str(v).strip().lower()
    if s in _TRUE:
        return True
    if s in _FALSE:
        return False
    raise ValueError(f"cannot interpret gpio_ok value {v!r} as a boolean")


# --------------------------------------------------------------------------- reading the log
def read_sync_events(csv: str | os.PathLike | io.IOBase | pd.DataFrame) -> pd.DataFrame:
    """Read ``sync_events.csv`` (CONTRACTS section 3.4) into a typed, time-sorted DataFrame.

    Columns: ``event_id`` (int), ``kind`` ('start' | 'end' = LED rising | falling edge), ``pattern``
    ('P1' | 'P2'), ``mono_ns`` (int64 reference clock), ``wall_ns`` (int64, audit only), ``gpio_ok``
    (bool self-check). Rows are sorted by ``mono_ns``. Serves protocol section 4.2.
    """
    df = csv.copy() if isinstance(csv, pd.DataFrame) else pd.read_csv(csv)
    missing = [c for c in SYNC_EVENT_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"sync_events.csv missing columns {missing}; have {list(df.columns)}")
    out = pd.DataFrame({
        "event_id": pd.to_numeric(df["event_id"], errors="coerce").astype("Int64"),
        "kind": df["kind"].astype(str).str.strip().str.lower(),
        "pattern": df["pattern"].astype(str).str.strip().str.upper(),
        "mono_ns": pd.to_numeric(df["mono_ns"], errors="coerce").astype("int64"),
        "wall_ns": pd.to_numeric(df["wall_ns"], errors="coerce").astype("int64"),
        "gpio_ok": [_to_bool(v) for v in df["gpio_ok"].tolist()],
    })
    bad_kind = sorted(set(out["kind"]) - set(EDGE_KINDS))
    if bad_kind:
        raise ValueError(f"sync_events.csv: unknown kind values {bad_kind}; expected {EDGE_KINDS}")
    out = out.sort_values("mono_ns", kind="stable").reset_index(drop=True)
    return out


def mono_ns_to_ref_s(mono_ns, t0_ref_ns: int) -> np.ndarray:
    """Reference-clock nanoseconds -> float seconds relative to the first Pi frame (D-001)."""
    return (np.asarray(mono_ns, dtype=np.int64) - np.int64(t0_ref_ns)) / 1e9


def expected_edges(df: pd.DataFrame, t0_ref_ns: int) -> dict[str, list[tuple[float, str]]]:
    """Per pattern, the logged LED edges as ``[(t_ref_s, kind), ...]`` sorted in time (section 4.2).

    These are the ground-truth edge times on the reference clock that every camera and the audio track
    are fitted against (``palmppg.ingest.led.fit_led_offset``).
    """
    out: dict[str, list[tuple[float, str]]] = {}
    for pat, sub in df.groupby("pattern", sort=True):
        sub = sub.sort_values("mono_ns")
        t = mono_ns_to_ref_s(sub["mono_ns"].to_numpy(), t0_ref_ns)
        out[str(pat)] = [(float(ti), str(k)) for ti, k in zip(t, sub["kind"].tolist())]
    return out


def pattern_onsets_from_log(df: pd.DataFrame, t0_ref_ns: int) -> dict[str, float]:
    """First rising edge of each pattern in ``t_ref_s`` (the logged P1/P2 onsets, section 4.2)."""
    out: dict[str, float] = {}
    for pat, edges in expected_edges(df, t0_ref_ns).items():
        starts = [t for t, k in edges if k == "start"]
        if starts:
            out[pat] = float(min(starts))
    return out


def gpio_ok_summary(df: pd.DataFrame) -> dict:
    """GPIO self-check summary: counts of ok/failed edges and the failing event ids (section 4.2)."""
    ok = df["gpio_ok"].to_numpy(dtype=bool)
    bad_ids = [int(e) for e in df.loc[~ok, "event_id"].dropna().tolist()]
    return {
        "n_events": len(df),
        "n_ok": int(ok.sum()),
        "n_bad": int((~ok).sum()),
        "all_ok": bool(ok.all()) if len(df) else False,
        "bad_event_ids": bad_ids,
        "patterns": sorted(set(df["pattern"].tolist())),
    }


def check_sync_events(df: pd.DataFrame, cfg: Config) -> list[str]:
    """Consistency issues in the log against the configured patterns (empty list = consistent).

    Checks edge counts per pattern (P1: pulses*2 rows, P2 likewise), alternation start/end, and the
    on/off durations against ``sync.p1``/``sync.p2`` within 10 ms (GPIO timing). Section 4.2.
    """
    issues: list[str] = []
    for name in PATTERN_NAMES:
        spec = pattern_spec(cfg, name)
        sub = df[df["pattern"] == name].sort_values("mono_ns")
        if sub.empty:
            issues.append(f"{name}: no rows in log")
            continue
        kinds = sub["kind"].tolist()
        if len(kinds) != 2 * spec["pulses"]:
            issues.append(f"{name}: {len(kinds)} edges logged, expected {2 * spec['pulses']}")
        exp_kinds = ["start", "end"] * spec["pulses"]
        if kinds != exp_kinds[: len(kinds)]:
            issues.append(f"{name}: edges do not alternate start/end: {kinds}")
            continue
        t = sub["mono_ns"].to_numpy(dtype=np.int64) / 1e9
        d = np.diff(t)
        for j, dj in enumerate(d):
            nominal = spec["on_s"] if j % 2 == 0 else spec["off_s"]
            if abs(dj - nominal) > 0.010:
                issues.append(f"{name}: interval {j} is {dj * 1e3:.1f} ms, nominal {nominal * 1e3:.0f} ms")
    if not df["gpio_ok"].all():
        issues.append(f"gpio_ok false for {int((~df['gpio_ok']).sum())} edge(s)")
    return issues


# --------------------------------------------------------------------------- clip bounds from meta
def clip_start_s(meta: Mapping, t0_ref_ns: int) -> float:
    """Clip start (``start_mono_ns`` from clip meta, CONTRACTS 3.3) in ``t_ref_s``."""
    return float(mono_ns_to_ref_s(int(meta["start_mono_ns"]), t0_ref_ns))


def clip_end_s(meta: Mapping, t0_ref_ns: int) -> float:
    """Clip end (``stop_mono_ns`` from clip meta) in ``t_ref_s``."""
    return float(mono_ns_to_ref_s(int(meta["stop_mono_ns"]), t0_ref_ns))


def clip_bounds_s(meta: Mapping, t0_ref_ns: int) -> tuple[float, float]:
    """``(clip_start_s, clip_end_s)`` in ``t_ref_s``; raises if the meta lacks the monotonic stamps."""
    for k in ("start_mono_ns", "stop_mono_ns"):
        if k not in meta or meta[k] is None:
            raise KeyError(f"clip meta lacks {k}; cannot place the clip on the reference clock")
    return clip_start_s(meta, t0_ref_ns), clip_end_s(meta, t0_ref_ns)


# --------------------------------------------------------------------------- pattern specs
def pattern_spec(cfg: Config, name: str) -> dict:
    """``{name, pulses, on_s, off_s}`` for pattern ``P1``/``P2`` from ``sync.p1``/``sync.p2`` (section 4.2).

    Durations are converted from the config's milliseconds to seconds.
    """
    key = f"sync.{name.lower()}"
    sec = cfg.section(key)
    return {
        "name": name.upper(),
        "pulses": int(sec["pulses"]),
        "on_s": float(sec["on_ms"]) / 1e3,
        "off_s": float(sec["off_ms"]) / 1e3,
    }


def pattern_specs(cfg: Config) -> dict[str, dict]:
    """Both marker patterns keyed by name."""
    return {n: pattern_spec(cfg, n) for n in PATTERN_NAMES}


def pattern_duration_s(spec: Mapping) -> float:
    """Total span of a pattern from its first rising to its last falling edge, in seconds."""
    n = int(spec["pulses"])
    return n * float(spec["on_s"]) + (n - 1) * float(spec["off_s"])


def nominal_pattern_onset_s(cfg: Config, name: str, clip_start_s: float, clip_end_s: float) -> float:
    """Where the marker script was told to fire the pattern, in ``t_ref_s`` (section 4.2 / Q14.3).

    P1 at ``clip_start + sync.p1.at_s_after_start``; P2 at ``clip_end - sync.p2.at_s_before_end`` when
    ``sync.p2.mode == before_end`` or ``clip_start + sync.p2.at_s_after_start`` when ``after_start``
    (30 s Kardia apps). Used only to centre search windows; the logged edges are the truth.
    """
    sec = cfg.section(f"sync.{name.lower()}")
    mode = str(sec.get("mode", "after_start"))
    if mode == "before_end":
        return float(clip_end_s) - float(sec["at_s_before_end"])
    return float(clip_start_s) + float(sec["at_s_after_start"])


def pattern_edges(onset_s: float, spec: Mapping) -> list[tuple[float, str]]:
    """Ideal edge times ``[(t, 'start'), (t, 'end'), ...]`` of a pattern starting at ``onset_s``."""
    out: list[tuple[float, str]] = []
    t = float(onset_s)
    for i in range(int(spec["pulses"])):
        out.append((t, "start"))
        t += float(spec["on_s"])
        out.append((t, "end"))
        if i < int(spec["pulses"]) - 1:
            t += float(spec["off_s"])
    return out


# --------------------------------------------------------------------------- pulse-sequence matching
def match_pulse_pattern(pulses: Sequence[tuple[float, float]], spec: Mapping, tol_on_s: float,
                        tol_off_s: float) -> dict | None:
    """Find the run of consecutive pulses whose on/off durations match ``spec`` within tolerance.

    ``pulses`` are ``(t_on, t_off)`` pairs sorted in time (from any detector: LED block, audio envelope).
    Returns ``{"indices": [...], "score": s, "errors_s": [...]}`` for the best match (lowest normalised
    duration error) or ``None`` when no run of ``spec['pulses']`` consecutive pulses fits. Serves the
    "match the pattern" step of section 4.2 for both cameras and the audio track.
    """
    n = int(spec["pulses"])
    if n <= 0 or len(pulses) < n:
        return None
    on_s, off_s = float(spec["on_s"]), float(spec["off_s"])
    best: dict | None = None
    for i in range(len(pulses) - n + 1):
        run = pulses[i:i + n]
        errs: list[float] = []
        norm: list[float] = []
        ok = True
        for j, (a, b) in enumerate(run):
            e_on = (b - a) - on_s
            errs.append(e_on)
            norm.append(abs(e_on) / tol_on_s)
            if abs(e_on) > tol_on_s:
                ok = False
                break
            if j < n - 1:
                e_off = (run[j + 1][0] - b) - off_s
                errs.append(e_off)
                norm.append(abs(e_off) / tol_off_s)
                if abs(e_off) > tol_off_s:
                    ok = False
                    break
        if not ok:
            continue
        score = float(np.max(norm)) if norm else 0.0
        if best is None or score < best["score"]:
            best = {"indices": list(range(i, i + n)), "score": score, "errors_s": errs}
    return best
