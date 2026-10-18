"""Per-camera pulse extraction runner (protocol section 6.3; outputs of CONTRACTS section 4).

`run_pulse(camera_dir, camera, cfg, timeline)` reads `<camera_dir>/traces.parquet` (and `patches.zarr`
for 2SR when present), runs every classical method of `pulse.methods` on every ROI inside the
timeline's analysis window and valid mask, and writes
  * `pulse.parquet`        t_ref_s + `<method>__<roi>` (and `<method>__fused`) columns, band `pulse.band_rate`,
                           z-scored, NaN outside the valid mask;
  * `pulse_morph.parquet`  the same columns in `pulse.band_morph`;
  * `pulse_sqi.json`       {"<method>__<roi>": {sqi, snr_db, hr_bpm, ...}, "best": key, "fused": {...}};
  * `pulse_rate.parquet`   t_ref_s + instantaneous rate (bpm) of the best signal at `sync.xcorr.rate_fs`
                           (peaks and stft), for the section 4.3 cross-correlation and E1;
  * `pulse_run.json`       run details (fs, bands, lambda, window, fusion weights, per-window SQIs).
Pi traces are R, G1, G2, B Bayer-plane means (never demosaiced); the green planes are averaged,
(G1 + G2) / 2, before extraction. `register_features()` registers every
`pulse__<camera>__<roi>__<method>__{hr_bpm, sqi, snr_db}` column (Pi raw-based ones `requires_raw`).
"""
from __future__ import annotations

import json
import time
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pandas as pd

from palmppg.core.config import Config
from palmppg.core.tracks import REGISTRY, CAMERAS, FeatureRegistry, TrackViolation
from palmppg.pulse.classical import canonical_name, run_method
from palmppg.pulse.fusion import snr_weighted_fusion
from palmppg.pulse.rate import instantaneous_rate
from palmppg.pulse.sqi import snr_band_sqi

SEP = "__"
PULSE_STATS = ("hr_bpm", "sqi", "snr_db")
PI_CHANNELS = ("R", "G1", "G2", "B")
RGB_CHANNELS = ("R", "G", "B")
SSR_LABELS = {"patches": "whole_palm", "roi_means": "roi_set"}
TRACE_TARGET_STAT = "mean"


# --------------------------------------------------------------------------- registry
def _requires_raw(camera: str) -> bool:
    return camera == "pi"


def _register(name: str, camera: str, registry: FeatureRegistry, units: str = "", description: str = "") -> None:
    req_raw = _requires_raw(camera)
    existing = registry.get(name)
    if existing is not None:
        if req_raw and not existing.requires_raw:
            raise TrackViolation(f"{name} is registered without requires_raw but the Pi raw path produces it")
        return
    registry.add(name, group="pulse", camera=camera, requires_raw=req_raw, units=units, description=description)


def register_features(cfg: Config | None = None, registry: FeatureRegistry = REGISTRY,
                      rois: Sequence[str] | None = None, methods: Sequence[str] | None = None) -> int:
    """Register `pulse__<camera>__<roi>__<method>__{hr_bpm, sqi, snr_db}` for every camera, ROI (config
    `rois.names` plus the fusion and 2SR labels) and method (`pulse.methods`), plus `pulse__<camera>__best`
    and the `pulse__<camera>__{best, fused}__<stat>` summaries. Pi (raw Bayer) columns are `requires_raw`;
    phone and pi_proxy are not. Idempotent: existing entries are kept (an existing Pi entry that is not
    `requires_raw` raises). Returns the number of columns registered or confirmed. CONTRACTS section 5.
    """
    if cfg is None and (rois is None or methods is None):
        from palmppg.core.config import load_pipeline_config

        cfg = load_pipeline_config()
    roi_list = list(rois) if rois is not None else list(cfg.get("rois.names"))
    roi_list = roi_list + [v for v in SSR_LABELS.values() if v not in roi_list] + ["fused"]
    method_list = [canonical_name(m) for m in (methods if methods is not None else cfg.get("pulse.methods"))]
    n = 0
    for cam in CAMERAS:
        for roi in roi_list:
            for m in method_list:
                for stat in PULSE_STATS:
                    _register(f"pulse{SEP}{cam}{SEP}{roi}{SEP}{m}{SEP}{stat}", cam, registry,
                              units="bpm" if stat == "hr_bpm" else ("dB" if stat == "snr_db" else ""),
                              description=f"{m} on {roi}: {stat} (section 6.3)")
                    n += 1
        _register(f"pulse{SEP}{cam}{SEP}best", cam, registry, description="best method__roi by SQI")
        n += 1
        for key in ("best", "fused"):
            for stat in PULSE_STATS:
                _register(f"pulse{SEP}{cam}{SEP}{key}{SEP}{stat}", cam, registry,
                          units="bpm" if stat == "hr_bpm" else ("dB" if stat == "snr_db" else ""))
                n += 1
    return n


# --------------------------------------------------------------------------- trace reading
def trace_channels(columns: Sequence[str]) -> tuple[str, ...]:
    """Channel set of a traces.parquet column list: Pi Bayer planes (R, G1, G2, B) or RGB."""
    cols = set(columns)
    if any(c.endswith(f"{SEP}G1{SEP}{TRACE_TARGET_STAT}") for c in cols):
        return PI_CHANNELS
    return RGB_CHANNELS


def trace_rois(columns: Sequence[str], channels: Sequence[str], order: Sequence[str] | None = None,
               exclude: Sequence[str] = ()) -> list[str]:
    """ROI names that have a `<roi>__<ch>__mean` column for every channel, in `order` first, then the rest."""
    found = []
    suffix = f"{SEP}{channels[0]}{SEP}{TRACE_TARGET_STAT}"
    for c in columns:
        if c.endswith(suffix):
            roi = c[: -len(suffix)]
            if all(f"{roi}{SEP}{ch}{SEP}{TRACE_TARGET_STAT}" in columns for ch in channels) and roi not in exclude:
                found.append(roi)
    ordered = [r for r in (order or []) if r in found] + [r for r in found if r not in (order or [])]
    return ordered


def roi_rgb(traces: pd.DataFrame, roi: str, channels: Sequence[str]) -> np.ndarray:
    """(T, 3) R, G, B trace of one ROI; Pi planes give G = (G1 + G2) / 2 (no demosaicing)."""
    get = lambda ch: traces[f"{roi}{SEP}{ch}{SEP}{TRACE_TARGET_STAT}"].to_numpy(dtype=float)  # noqa: E731 (local accessor)
    if tuple(channels) == PI_CHANNELS:
        return np.column_stack([get("R"), 0.5 * (get("G1") + get("G2")), get("B")])
    return np.column_stack([get("R"), get("G"), get("B")])


def patches_to_pixels(patches: np.ndarray, channels: Sequence[str]) -> np.ndarray:
    """(T, R, C, ch) patch means -> (T, R*C, 3) RGB pixels for 2SR (Pi greens averaged)."""
    p = np.asarray(patches, dtype=float)
    t, r, c, n_ch = p.shape
    flat = p.reshape(t, r * c, n_ch)
    chans = list(channels)
    if "G1" in chans and "G2" in chans:
        g = 0.5 * (flat[:, :, chans.index("G1")] + flat[:, :, chans.index("G2")])
        return np.stack([flat[:, :, chans.index("R")], g, flat[:, :, chans.index("B")]], axis=2)
    return np.stack([flat[:, :, chans.index(ch)] for ch in ("R", "G", "B")], axis=2)


def _load_patches(path: Path, lo: int, hi: int) -> tuple[np.ndarray, list[str]] | None:
    if not path.exists():
        return None
    import zarr

    z = zarr.open_array(str(path), mode="r")
    attrs = dict(z.attrs.asdict())
    arr = np.asarray(z[lo:hi], dtype=np.float32)
    return arr, list(attrs.get("channels", []))


def _grid_fs(t: np.ndarray, cfg: Config) -> float:
    nominal = float(cfg.get("grid.fs"))
    if t.size > 1:
        measured = 1.0 / float(np.median(np.diff(t)))
        if np.isfinite(measured) and abs(measured - nominal) / nominal > 0.05:
            return measured
    return nominal


def _sqi_summary(d: dict) -> dict:
    return {k: (None if (isinstance(v, float) and not np.isfinite(v)) else v)
            for k, v in d.items() if k in ("sqi", "snr_db", "hr_bpm", "template_corr", "skewness", "kurtosis", "n_windows")}


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, float) and not np.isfinite(o):
        return None
    return str(o)


def _dump_json(obj: dict, path: Path) -> None:
    def clean(v):
        if isinstance(v, dict):
            return {k: clean(x) for k, x in v.items()}
        if isinstance(v, (list, tuple)):
            return [clean(x) for x in v]
        if isinstance(v, float) and not np.isfinite(v):
            return None
        return v

    path.write_text(json.dumps(clean(obj), indent=2, default=_json_default), encoding="utf-8")


# --------------------------------------------------------------------------- runner
def select_best(sqi: dict, cfg: Config) -> tuple[str | None, dict]:
    """Choose the signal beats are segmented on (protocol 6.5 "best-SQI signal"), D-023.

    Candidates are pre-specified, not the full method x ROI grid: the ROI labels in cfg `pulse.best_candidates`
    (default whole_palm and the SNR-weighted multi-ROI `fused` signal of each method). Taking the maximum SQI over
    every method x ROI pair selects noise (on a clip without a pulse, the best of about 130 candidates still scores
    high), so each candidate's SQI is multiplied by its cross-method agreement: the fraction of candidates whose rate
    lies within cfg `pulse.consensus_tol_bpm` of its rate. With `pulse.best_selection: max_sqi` the plain maximum over
    the same candidates is used. Returns (best key, selection detail).
    """
    rois = list(cfg.get("pulse.best_candidates", ["whole_palm", "fused"]))
    mode = str(cfg.get("pulse.best_selection", "consensus_sqi"))
    tol = float(cfg.get("pulse.consensus_tol_bpm", 5.0))
    cands = [k for k, v in sqi.items() if isinstance(v, dict) and SEP in k and k.split(SEP, 1)[1] in rois
             and v.get("sqi") is not None and v.get("hr_bpm") is not None and np.isfinite(v["hr_bpm"])]
    if not cands:
        cands = [k for k, v in sqi.items() if isinstance(v, dict) and SEP in k and v.get("sqi") is not None]
        if not cands:
            return None, {"mode": mode, "n_candidates": 0}
        b = max(cands, key=lambda k: sqi[k]["sqi"] or 0.0)
        return b, {"mode": "fallback_max_sqi", "n_candidates": len(cands)}
    hr = np.array([sqi[k]["hr_bpm"] for k in cands], float)
    raw = np.array([sqi[k]["sqi"] or 0.0 for k in cands], float)
    agree = np.array([np.mean(np.abs(hr - h) <= tol) for h in hr])
    score = raw * agree if mode == "consensus_sqi" else raw
    i = int(np.argmax(score))
    return cands[i], {"mode": mode, "n_candidates": len(cands), "agreement": float(agree[i]), "score": float(score[i]),
                      "consensus_hr_bpm": float(np.median(hr[agree >= agree.max() - 1e-9])), "raw_sqi": float(raw[i])}


def run_pulse(camera_dir, camera: str, cfg: Config, timeline, patches_path=None, write: bool = True) -> dict:
    """Run every classical method on every ROI of `<camera_dir>/traces.parquet` (section 6.3).

    `camera` in {pi, phone, pi_proxy}. Only samples inside `timeline.valid_mask` (analysis window minus
    exclusions: first 2 s and the fine-anchor tail, section 6.3) are used; outputs are NaN elsewhere.
    2SR runs on `patches.zarr` (`patches_path` overrides) labelled roi `whole_palm`, or, without patches,
    on the stack of ROI means labelled `roi_set`. SQI per `<method>__<roi>` uses `pulse.window_s` /
    `pulse.step_s`; `best` is the highest SQI (ties: config order); `<method>__fused` is the SNR-weighted
    multi-ROI fusion per method and the `fused` summary is the fusion of the best method. Returns a dict
    with the pulse frames, the SQI dict and the run details; files are written when `write` is True.
    """
    t_start = time.time()
    camera_dir = Path(camera_dir)
    if camera not in CAMERAS:
        raise ValueError(f"camera must be one of {CAMERAS}")
    traces = pd.read_parquet(camera_dir / "traces.parquet")
    t = traces["t_ref_s"].to_numpy(dtype=float)
    n = t.size
    fs = _grid_fs(t, cfg)
    channels = trace_channels(list(traces.columns))
    rois = trace_rois(list(traces.columns), channels, order=cfg.get("rois.names", []), exclude=cfg.get("rois.excluded", []))
    if not rois:
        raise ValueError("traces.parquet holds no ROI mean columns")
    band_rate = tuple(float(v) for v in cfg.get("pulse.band_rate"))
    band_morph = tuple(float(v) for v in cfg.get("pulse.band_morph"))
    window_s = float(cfg.get("pulse.window_s"))
    step_s = float(cfg.get("pulse.step_s"))
    ibi_bounds = tuple(float(v) for v in cfg.get("beats.ibi_bounds_s", (0.33, 2.0)))
    rate_fs = float(cfg.get("sync.xcorr.rate_fs", 4.0))
    methods = [canonical_name(m) for m in cfg.get("pulse.methods")]
    valid = timeline.valid_mask(t) if timeline is not None else np.ones(n, dtype=bool)
    idx = np.flatnonzero(valid)
    out_rate: dict[str, np.ndarray] = {}
    out_morph: dict[str, np.ndarray] = {}
    sqi: dict = {}
    details: dict = {
        "camera": camera, "fs": fs, "channels": list(channels), "rois": rois, "methods": methods,
        "band_rate": list(band_rate), "band_morph": list(band_morph), "detrend_lambda": cfg.get("pulse.detrend_lambda", None),
        "n_samples": int(n), "n_valid": int(idx.size), "polarity": "positive = blood volume increase (negated intensity)",
        "green_merge": "G = (G1 + G2) / 2" if tuple(channels) == PI_CHANNELS else "G as decoded",
        "ssr_input": None, "fusion_weights": {}, "sqi_windows": {},
    }
    if idx.size == 0:
        lo, hi = 0, 0
    else:
        lo, hi = int(idx[0]), int(idx[-1]) + 1
    inside = valid[lo:hi]

    def masked(rgb: np.ndarray) -> np.ndarray:
        rgb = np.array(rgb[lo:hi], dtype=float, copy=True)
        rgb[~inside] = np.nan
        return rgb

    def place(sig: np.ndarray) -> np.ndarray:
        full = np.full(n, np.nan)
        full[lo:hi] = sig
        full[~valid] = np.nan
        return full

    per_roi_rgb = {roi: masked(roi_rgb(traces, roi, channels)) for roi in rois}
    enough = hi - lo >= max(int(2 * fs), 8)
    for m in methods:
        if m == "2SR":
            continue
        for roi in rois:
            key = f"{m}{SEP}{roi}"
            if not enough or np.isnan(per_roi_rgb[roi]).all():
                out_rate[key] = np.full(n, np.nan)
                out_morph[key] = np.full(n, np.nan)
                continue
            out_rate[key] = place(run_method(m, per_roi_rgb[roi], fs, cfg, band=band_rate))
            out_morph[key] = place(run_method(m, per_roi_rgb[roi], fs, cfg, band=band_morph))
    if "2SR" in methods and enough:
        loaded = _load_patches(Path(patches_path) if patches_path else camera_dir / "patches.zarr", lo, hi)
        if loaded is not None and loaded[0].shape[0] == hi - lo:
            pix = patches_to_pixels(loaded[0], loaded[1] or list(channels))
            pix[~inside] = np.nan
            details["ssr_input"] = "patches"
        else:
            pix = np.stack([per_roi_rgb[r] for r in rois], axis=1)
            details["ssr_input"] = "roi_means"
        key = f"2SR{SEP}{SSR_LABELS[details['ssr_input']]}"
        try:
            out_rate[key] = place(run_method("2SR", pix, fs, cfg, band=band_rate))
            out_morph[key] = place(run_method("2SR", pix, fs, cfg, band=band_morph))
        except ValueError as exc:                      # fewer than three usable pixels
            details["ssr_error"] = str(exc)
            out_rate[key] = np.full(n, np.nan)
            out_morph[key] = np.full(n, np.nan)
    # SQI per method__roi
    for key, sig in out_rate.items():
        res = snr_band_sqi(sig[lo:hi] if enough else sig, fs, band_rate, window_s, step_s, ibi_bounds_s=ibi_bounds)
        sqi[key] = _sqi_summary(res)
        details["sqi_windows"][key] = {k: res[k] for k in ("snr_db_windows", "hr_bpm_windows", "window_start_s")}
    # fusion per method across ROIs
    fused_by_method: dict[str, str] = {}
    for m in methods:
        keys = [k for k in out_rate if k.split(SEP, 1)[0] == m and k.split(SEP, 1)[1] != "fused"]
        if not keys or all(sqi[k]["sqi"] in (None, 0.0) for k in keys):
            continue
        sig_r = {k.split(SEP, 1)[1]: out_rate[k] for k in keys}
        sig_m = {k.split(SEP, 1)[1]: out_morph[k] for k in keys}
        q = {k.split(SEP, 1)[1]: sqi[k] for k in keys}
        fused_r, w = snr_weighted_fusion(sig_r, q)
        fused_m, _ = snr_weighted_fusion(sig_m, q)
        fkey = f"{m}{SEP}fused"
        out_rate[fkey] = fused_r
        out_morph[fkey] = fused_m
        details["fusion_weights"][m] = w
        res = snr_band_sqi(fused_r[lo:hi] if enough else fused_r, fs, band_rate, window_s, step_s, ibi_bounds_s=ibi_bounds)
        sqi[fkey] = _sqi_summary(res)
        fused_by_method[m] = fkey
    # best and fused summary (D-023: pre-specified large-area candidates, consensus-weighted SQI)
    best, selection = select_best(sqi, cfg)
    sqi["best"] = best
    sqi["selection"] = selection
    if best is not None and best.split(SEP, 1)[0] in fused_by_method:
        fkey = fused_by_method[best.split(SEP, 1)[0]]
        sqi["fused"] = {"sqi": sqi[fkey]["sqi"], "snr_db": sqi[fkey]["snr_db"], "hr_bpm": sqi[fkey]["hr_bpm"],
                        "method": best.split(SEP, 1)[0]}
    else:
        sqi["fused"] = {"sqi": None, "snr_db": None, "hr_bpm": None, "method": None}
    sqi.update({"camera": camera, "requires_raw": _requires_raw(camera), "ssr_input": details["ssr_input"]})
    if timeline is not None:
        sqi["study_id"] = timeline.study_id
        sqi["clip_id"] = timeline.clip_id
    # rate series of the best signal
    rate_df = pd.DataFrame({"t_ref_s": np.zeros(0), "bpm_peaks": np.zeros(0), "bpm_stft": np.zeros(0)})
    if best is not None and enough:
        sig = out_rate[best][lo:hi]
        tg, bpm_p = instantaneous_rate(sig, fs, "peaks", rate_fs, t0=float(t[lo]), band=band_rate, ibi_bounds_s=ibi_bounds)
        _, bpm_s = instantaneous_rate(sig, fs, "stft", rate_fs, t0=float(t[lo]), band=band_rate, ibi_bounds_s=ibi_bounds)
        rate_df = pd.DataFrame({"t_ref_s": tg, "bpm_peaks": bpm_p, "bpm_stft": bpm_s})
    pulse_df = pd.DataFrame({"t_ref_s": t, **out_rate})
    morph_df = pd.DataFrame({"t_ref_s": t, **out_morph})
    details["elapsed_s"] = time.time() - t_start
    details["best"] = best
    if write:
        camera_dir.mkdir(parents=True, exist_ok=True)
        pulse_df.to_parquet(camera_dir / "pulse.parquet", index=False)
        morph_df.to_parquet(camera_dir / "pulse_morph.parquet", index=False)
        rate_df.to_parquet(camera_dir / "pulse_rate.parquet", index=False)
        _dump_json(sqi, camera_dir / "pulse_sqi.json")
        _dump_json(details, camera_dir / "pulse_run.json")
    return {"pulse": pulse_df, "pulse_morph": morph_df, "pulse_rate": rate_df, "sqi": sqi, "details": details}
