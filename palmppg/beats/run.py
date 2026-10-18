"""Per-camera beat runner (protocol 6.5, 6.6): beats.parquet, beat_features.json and, for sync grade fine, pat.json.

Inputs (real producer shapes):
  <camera_dir>/pulse_morph.parquet  t_ref_s + <method>__<roi> (band 0.4-8 Hz, z-scored, NaN outside the window)
  <camera_dir>/pulse_sqi.json       {"<method>__<roi>": {sqi, snr_db, hr_bpm, ...}, "best": "<method>__<roi>", ...}
  <camera_dir>/traces.parquet       raw ROI traces on the uniform grid (perfusion needs AC/DC, not z-scores)
  timeline                          palmppg.core.timeline.Timeline (analysis window, exclusions, sync grade)
  ecg_rpeaks_t_ref_s                R-peak times on the reference clock (only used when the grade is fine)

Beats are detected on the best-SQI morphology signal (the protocol's "best-SQI signal"), inside the analysis window.
Everything in pat.json is requires_ecg = True and never enters a product_candidate model.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from palmppg.beats import apg as apg_mod
from palmppg.beats import hrv as hrv_mod
from palmppg.beats import morphology as morph_mod
from palmppg.beats import pat as pat_mod
from palmppg.beats import perfusion as perf_mod
from palmppg.beats import quality as quality_mod
from palmppg.beats import resp as resp_mod
from palmppg.beats.segmentation import detect_beats
from palmppg.core.config import Config
from palmppg.core.tracks import REGISTRY, FeatureRegistry, feature_prefix

CAMERAS = ("pi", "phone", "pi_proxy")
HRV_KEYS = ("sdnn_ms", "rmssd_ms", "pnn50", "sampen", "ibi_hist_entropy", "sd1_ms", "sd2_ms", "sd1_sd2_ratio", "tpr",
            "n_beats", "mean_hr_bpm", "hr_cv")
APG_KEYS = ("a", "b", "c", "d", "e", "b_a", "c_a", "d_a", "e_a", "ageing_index")
RESP_KEYS = ("resp_rate_bpm", "resp_power_ratio", "resp_rate_am_bpm", "resp_rate_ibi_bpm")
PAT_KEYS = ("pairing_rate", "pat_mean_ms", "pat_sd_ms", "pat_median_ms", "n_pairs", "n_rpeaks", "ectopic_capture_fraction",
            "n_ectopic_ecg", "n_ectopic_captured", "ibi_diff_mean_ms", "ibi_diff_sd_ms", "ibi_corr")


def register_features(cfg: Config | None = None, registry: FeatureRegistry = REGISTRY) -> list[str]:
    """Register the clip-level beat columns for every camera (idempotent). Pi columns are requires_raw (they come
    from the raw Bayer path); pat__* columns are requires_ecg for every camera."""
    names: list[str] = []
    keys = {"hrv": HRV_KEYS, "morphology": tuple(morph_mod.MORPH_KEYS) + tuple(f"{k}_sd" for k in morph_mod.MORPH_KEYS if k != "dicrotic_notch_present")
            + ("notch_fraction", "n_beats_used", "n_beats_total"), "apg": APG_KEYS, "resp": RESP_KEYS}
    for cam in CAMERAS:
        raw = cam == "pi"
        for group, ks in keys.items():
            for k in ks:
                n = feature_prefix(group, cam, None, None, k)
                registry.add(n, group, camera=cam, requires_raw=raw)
                names.append(n)
        for k in PAT_KEYS:
            n = feature_prefix("pat", cam, None, None, k)
            registry.add(n, "pat", camera=cam, requires_raw=raw, requires_ecg=True)
            names.append(n)
    return names


def _load_json(p: Path) -> dict | None:
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _jsonable(o: Any):
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (float, np.floating)):
        f = float(o)
        return None if not np.isfinite(f) else f
    if isinstance(o, np.ndarray):
        return _jsonable(o.tolist())
    if isinstance(o, pd.DataFrame):
        return None
    return o


def best_signal(camera_dir: Path) -> tuple[str | None, pd.DataFrame | None]:
    """Name of the best-SQI `<method>__<roi>` signal and the morphology-band frame (None when unavailable)."""
    sqi = _load_json(camera_dir / "pulse_sqi.json")
    p = camera_dir / "pulse_morph.parquet"
    if not sqi or not p.exists():
        return None, None
    df = pd.read_parquet(p)
    best = sqi.get("best")
    if best not in df.columns:
        ranked = sorted(((v.get("sqi") or -1, k) for k, v in sqi.items() if isinstance(v, dict) and k in df.columns), reverse=True)
        best = ranked[0][1] if ranked else None
    return best, df


def run_beats(camera_dir, camera: str, cfg: Config, timeline, ecg_rpeaks_t_ref_s=None, write: bool = True) -> dict:
    """Segment beats on the best-SQI morphology signal and write beats.parquet / beat_features.json / pat.json."""
    camera_dir = Path(camera_dir)
    if camera not in CAMERAS:
        raise ValueError(f"camera must be one of {CAMERAS}")
    register_features(cfg)
    best, df = best_signal(camera_dir)
    if best is None:
        raise FileNotFoundError(f"{camera_dir}: no pulse_morph.parquet / pulse_sqi.json best signal")
    t = df["t_ref_s"].to_numpy(dtype=float)
    x = df[best].to_numpy(dtype=float)
    mask = timeline.valid_mask(t) if timeline is not None else np.isfinite(x)
    x = np.where(mask, x, np.nan)
    fs = float(cfg.get("grid.fs"))
    lo_i = int(np.argmax(np.isfinite(x))) if np.isfinite(x).any() else 0
    hi_i = len(x) - int(np.argmax(np.isfinite(x[::-1]))) if np.isfinite(x).any() else 0
    xs, t0 = x[lo_i:hi_i], float(t[lo_i]) if len(t) else 0.0
    ibi_bounds = tuple(cfg.get("beats.ibi_bounds_s"))
    beats = detect_beats(xs, fs, ibi_bounds, foot_method=str(cfg.get("beats.foot_method")),
                         matched_filter=bool(cfg.get("beats.matched_filter")), t0=t0)
    qmin = float(cfg.get("beats.quality_min"))
    q = quality_mod.beat_quality(beats, xs, fs, t0=t0) if len(beats) else pd.DataFrame({"quality": []})
    per_beat = morph_mod.beat_morphology(beats, xs, fs, t0=t0) if len(beats) else pd.DataFrame(columns=list(morph_mod.MORPH_KEYS))
    quality = q["quality"].to_numpy(dtype=float) if "quality" in q else np.zeros(0)

    good_ibi = beats["ibi_s"].to_numpy(dtype=float) if len(beats) else np.zeros(0)
    if quality.size:
        good_ibi = np.where(quality >= qmin, good_ibi, np.nan)
    hrv = hrv_mod.hrv_features(good_ibi[np.isfinite(good_ibi)], ibi_bounds)
    ens = morph_mod.ensemble_morphology(per_beat, quality, qmin) if len(beats) else {}
    try:
        apg = apg_mod.ensemble_apg(beats, xs, fs, quality, qmin, notch_tau_s=ens.get("notch_time_s"), t0=t0) if len(beats) >= 3 else {}
    except Exception as exc:  # noqa: BLE001 - an APG failure on a poor clip is recorded, not fatal
        apg = {"error": f"{type(exc).__name__}: {exc}"}
    resp = resp_mod.respiratory_proxy(xs, fs, tuple(cfg.get("beats.resp_band")),
                                      foot_t=beats["foot_t"].to_numpy(float) if len(beats) else None,
                                      amplitude=beats["amplitude"].to_numpy(float) if len(beats) else None,
                                      ibi_s=beats["ibi_s"].to_numpy(float) if len(beats) else None, t0=t0)
    perfusion: dict = {}
    tp = camera_dir / "traces.parquet"
    if tp.exists():
        tr = pd.read_parquet(tp)
        vm = timeline.valid_mask(tr["t_ref_s"].to_numpy(float)) if timeline is not None else None
        perfusion = perf_mod.perfusion_table(tr, tuple(cfg.get("pulse.band_rate")), fs, valid_mask=vm,
                                             rois=list(cfg.get("rois.names")), exclude=list(cfg.get("rois.excluded")))

    table = pd.concat([beats.reset_index(drop=True), per_beat.reset_index(drop=True).add_prefix("m_"),
                       q.reset_index(drop=True)], axis=1) if len(beats) else beats
    if len(table):
        table = table.loc[:, ~table.columns.duplicated()]
    features = {"camera": camera, "signal": best, "fs": fs, "window": [float(t[lo_i]) if len(t) else None, float(t[hi_i - 1]) if hi_i else None],
                "hrv": hrv, "morphology": ens, "apg": {k: apg.get(k) for k in APG_KEYS} if "error" not in apg else apg,
                "apg_detail": {k: v for k, v in apg.items() if k not in APG_KEYS},
                "perfusion": {roi: {ch: (v.get("pi_pct") if isinstance(v, dict) else v) for ch, v in chans.items()} for roi, chans in perfusion.items()},
                "resp": {k: resp.get(k) for k in RESP_KEYS}, "resp_detail": {k: v for k, v in resp.items() if k not in RESP_KEYS},
                "quality": quality_mod.quality_summary(quality, qmin), "segmentation": {k: v for k, v in beats.attrs.items() if k != "template"},
                "requires_ecg": False}

    pat_out = None
    grade = getattr(timeline, "sync_grade", "none")
    if ecg_rpeaks_t_ref_s is not None and grade == "fine" and len(beats):
        r = np.asarray(ecg_rpeaks_t_ref_s, dtype=float)
        if timeline is not None:
            r = r[timeline.valid_mask(r)]
        feet = beats["foot_t"].to_numpy(float)
        pairs = pat_mod.pair_r_to_foot(r, feet, tuple(cfg.get("sync.pat_window_ms")), timeline)
        summ = pat_mod.pat_summary(pairs, timeline)
        cmp_ = pat_mod.compare_ibis(r, feet, pairs, timeline)
        pat_out = {"requires_ecg": True, "sync_grade": grade, **summ,
                   **{k: cmp_.get(k) for k in ("n_compared", "ibi_diff_mean_ms", "ibi_diff_sd_ms", "ibi_diff_mad_ms", "ibi_corr",
                                               "n_ectopic_ecg", "n_ectopic_captured", "ectopic_capture_fraction")}}
        if write:
            pairs.to_parquet(camera_dir / "pat_pairs.parquet", index=False)
    elif ecg_rpeaks_t_ref_s is not None:
        pat_out = {"requires_ecg": True, "sync_grade": grade, "skipped": f"sync grade {grade}: beat-level ECG pairing needs 'fine'"}

    if write:
        table.to_parquet(camera_dir / "beats.parquet", index=False)
        (camera_dir / "beat_features.json").write_text(json.dumps(_jsonable(features), indent=1), encoding="utf-8")
        if pat_out is not None:
            (camera_dir / "pat.json").write_text(json.dumps(_jsonable(pat_out), indent=1), encoding="utf-8")
    return {"beats": table, "features": features, "pat": pat_out}
