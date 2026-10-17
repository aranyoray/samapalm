"""Static colour features from the first seconds of the clip (protocol section 6.2, static colour).

Computed on the ROI traces inside the static-colour window (configs: window.static_colour_s, the
first 2 s) before any pulse analysis window starts. Pi path: linear calibrated units (dark-subtracted,
flat-fielded Bayer planes; G = (G1 + G2) / 2), `colour_space = "linear_raw"`. Phone and pi_proxy paths:
inverted-sRGB "linear-ish" units in [0, 1], `colour_space = "inverted_srgb"` with
`linearised_from_srgb = True` (CONTRACTS section 0.4; true linearisation is not possible on compressed
video).

Definitions
  R, G, B                 window mean of the per-frame ROI channel means
  rg, bg                  chromaticity R/G and B/G (scale-free under a common gain)
  melanin_proxy           log(R) - log(B). Melanin absorbs short wavelengths more than long ones, so a
                          darker skin returns relatively less blue than red; the log-ratio grows with
                          melanin content and is invariant to a common illumination gain, but not to an
                          illuminant colour change. It is a proxy in the camera's own colour space, not
                          a melanin measurement, and supports no equity claim by itself.
  spatial_rg_variance     variance over the 16 x 24 whole-palm patch grid of the per-patch window-mean
                          R/G (how uneven the palm colour is; vignetting and blotching show up here)
  central_palm_pallor_index  (R/G of central_palm) / (R/G of whole_palm): below 1 the centre of the
                          palm is paler (less red) than the palm as a whole, a crude perfusion /
                          pallor contrast that is self-normalised against the person's own skin tone
  n_frames_used           grid frames inside the window with a whole-palm trace sample
"""
from __future__ import annotations

import json
import warnings
from collections.abc import Mapping, Sequence
from pathlib import Path

import numpy as np
import pandas as pd

from palmppg.core.tracks import REGISTRY, feature_prefix

GROUP = "static_colour"
COLOUR_SPACES = {"linear_raw": "pi", "inverted_srgb": "phone"}
PER_ROI_FEATURES: tuple[str, ...] = ("R_mean", "G_mean", "B_mean", "rg", "bg", "melanin_proxy")
CLIP_FEATURES: tuple[str, ...] = ("spatial_rg_variance", "central_palm_pallor_index", "n_frames_used")
CAMERAS: tuple[str, ...] = ("pi", "phone", "pi_proxy")
MELANIN_PROXY_DEFINITION = "log(R) - log(B) of the ROI window-mean channel values in the stated colour space"


def _window_rows(df: pd.DataFrame, t_window: tuple[float, float]) -> pd.DataFrame:
    t = df["t_ref_s"].to_numpy(dtype=float)
    return df[(t >= float(t_window[0])) & (t < float(t_window[1]))]


def _channel_frames(df: pd.DataFrame, roi: str, stat: str = "mean") -> dict[str, np.ndarray] | None:
    """Per-frame R, G, B for one ROI; Pi G = (G1 + G2) / 2. None when the ROI is not in the frame."""
    r = f"{roi}__R__{stat}"
    b = f"{roi}__B__{stat}"
    if r not in df.columns or b not in df.columns:
        return None
    if f"{roi}__G1__{stat}" in df.columns and f"{roi}__G2__{stat}" in df.columns:
        g = 0.5 * (df[f"{roi}__G1__{stat}"].to_numpy(dtype=float) + df[f"{roi}__G2__{stat}"].to_numpy(dtype=float))
    elif f"{roi}__G__{stat}" in df.columns:
        g = df[f"{roi}__G__{stat}"].to_numpy(dtype=float)
    else:
        return None
    return {"R": df[r].to_numpy(dtype=float), "G": g, "B": df[b].to_numpy(dtype=float)}


def _safe_ratio(a: float, b: float) -> float:
    if not (np.isfinite(a) and np.isfinite(b)) or b <= 0:
        return float("nan")
    return float(a / b)


def _safe_log_diff(a: float, b: float) -> float:
    if not (np.isfinite(a) and np.isfinite(b)) or a <= 0 or b <= 0:
        return float("nan")
    return float(np.log(a) - np.log(b))


def patch_rg(patches: np.ndarray, channels: Sequence[str]) -> np.ndarray:
    """Per-patch R/G from a (T, R, C, ch) window of patch means; G is (G1 + G2) / 2 on the Pi path."""
    p = np.asarray(patches, dtype=float)
    ch = {c: i for i, c in enumerate(channels)}
    with warnings.catch_warnings(), np.errstate(invalid="ignore", divide="ignore"):
        warnings.simplefilter("ignore", RuntimeWarning)       # all-NaN cells outside the palm
        mean_t = np.nanmean(p, axis=0) if p.shape[0] else np.full(p.shape[1:], np.nan)
    r = mean_t[..., ch["R"]]
    if "G1" in ch and "G2" in ch:
        g = 0.5 * (mean_t[..., ch["G1"]] + mean_t[..., ch["G2"]])
    else:
        g = mean_t[..., ch["G"]]
    with np.errstate(invalid="ignore", divide="ignore"):
        rg = np.where(g > 0, r / g, np.nan)
    return rg


def static_colour_features(
    traces_df: pd.DataFrame,
    t_window: tuple[float, float],
    rois: Sequence[str],
    colour_space: str,
    camera: str | None = None,
    patches: np.ndarray | None = None,
    patch_t_ref_s: np.ndarray | None = None,
    patch_channels: Sequence[str] | None = None,
) -> dict:
    """Section 6.2 static colour features over `t_window` = (start, start + window.static_colour_s).

    `traces_df` is the traces.parquet frame (uniform grid); `rois` the ROI names to report;
    `colour_space` "linear_raw" (Pi) or "inverted_srgb" (phone, pi_proxy); `camera` names the feature
    columns (defaults: pi for linear_raw, phone for inverted_srgb). `patches` (T, rows, cols, ch) with
    `patch_t_ref_s` and `patch_channels` give the spatial colour variance; without them it is NaN.
    Returns a JSON-ready dict with per-ROI values under "rois", the clip-level indices, "n_frames_used",
    and "features": {registered column name: value} ready for the feature store.
    """
    if colour_space not in COLOUR_SPACES:
        raise ValueError(f"colour_space must be one of {sorted(COLOUR_SPACES)}")
    camera = camera or COLOUR_SPACES[colour_space]
    if camera not in CAMERAS:
        raise ValueError(f"camera must be one of {CAMERAS}")
    win = _window_rows(traces_df, t_window)
    per_roi: dict[str, dict] = {}
    for roi in rois:
        ch = _channel_frames(win, roi)
        if ch is None:
            per_roi[roi] = {k: float("nan") for k in PER_ROI_FEATURES} | {"n_frames": 0}
            continue
        ok = np.isfinite(ch["R"]) & np.isfinite(ch["G"]) & np.isfinite(ch["B"])
        n = int(ok.sum())
        rm = float(np.mean(ch["R"][ok])) if n else float("nan")
        gm = float(np.mean(ch["G"][ok])) if n else float("nan")
        bm = float(np.mean(ch["B"][ok])) if n else float("nan")
        per_roi[roi] = {
            "R_mean": rm, "G_mean": gm, "B_mean": bm,
            "rg": _safe_ratio(rm, gm), "bg": _safe_ratio(bm, gm),
            "melanin_proxy": _safe_log_diff(rm, bm), "n_frames": n,
        }
    ref_roi = "whole_palm" if "whole_palm" in per_roi else (rois[0] if len(rois) else None)
    n_frames_used = int(per_roi[ref_roi]["n_frames"]) if ref_roi else 0

    spatial_var = float("nan")
    if patches is not None and patch_channels is not None:
        p = np.asarray(patches, dtype=float)
        if patch_t_ref_s is not None:
            pt = np.asarray(patch_t_ref_s, dtype=float)
            sel = (pt >= float(t_window[0])) & (pt < float(t_window[1]))
            p = p[sel]
        rg = patch_rg(p, patch_channels)
        finite = rg[np.isfinite(rg)]
        if finite.size >= 2:
            spatial_var = float(np.var(finite))

    pallor = float("nan")
    if "central_palm" in per_roi and "whole_palm" in per_roi:
        pallor = _safe_ratio(per_roi["central_palm"]["rg"], per_roi["whole_palm"]["rg"])

    features: dict[str, float] = {}
    for roi, vals in per_roi.items():
        for name in PER_ROI_FEATURES:
            features[feature_prefix(GROUP, camera, roi, None, name)] = float(vals[name])
    features[feature_prefix(GROUP, camera, None, None, "spatial_rg_variance")] = spatial_var
    features[feature_prefix(GROUP, camera, None, None, "central_palm_pallor_index")] = pallor
    features[feature_prefix(GROUP, camera, None, None, "n_frames_used")] = float(n_frames_used)

    return {
        "camera": camera,
        "colour_space": colour_space,
        "linearised_from_srgb": colour_space == "inverted_srgb",
        "t_window": [float(t_window[0]), float(t_window[1])],
        "n_frames_used": n_frames_used,
        "rois": per_roi,
        "spatial_rg_variance": spatial_var,
        "central_palm_pallor_index": pallor,
        "melanin_proxy_definition": MELANIN_PROXY_DEFINITION,
        "features": features,
    }


def nan_to_none(obj):
    """Recursively replace NaN/inf floats by None so the JSON is strict (CONTRACTS: missing = null)."""
    if isinstance(obj, Mapping):
        return {k: nan_to_none(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [nan_to_none(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return nan_to_none(obj.tolist())
    if isinstance(obj, (float, np.floating)):
        return None if not np.isfinite(obj) else float(obj)
    return obj


def write_static_colour_json(path: str | Path, payload: Mapping) -> Path:
    """Write static_colour.json (strict JSON: NaN values become null)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(nan_to_none(payload), indent=1, default=_json_default), encoding="utf-8")
    return path


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)


def register_features(cfg=None, roi_names: Sequence[str] | None = None) -> list[str]:
    """Register every static-colour column with palmppg.core.tracks.REGISTRY (idempotent).

    Group "static_colour"; one set per camera (pi, phone, pi_proxy) and per ROI from configs
    rois.names. Pi linear-raw features are `requires_raw=True` (Bayer-plane, 10-bit only); phone and
    pi_proxy inverted-sRGB features are not, so they may enter product_candidate models. Returns the
    column names registered.
    """
    if roi_names is None:
        if cfg is None:
            from palmppg.core.config import load_pipeline_config

            cfg = load_pipeline_config()
        roi_names = list(cfg.get("rois.names"))
    names: list[str] = []
    for camera in CAMERAS:
        raw = camera == "pi"
        units = "linear calibrated DN" if raw else "inverted-sRGB [0, 1]"
        for roi in roi_names:
            for name in PER_ROI_FEATURES:
                col = feature_prefix(GROUP, camera, roi, None, name)
                REGISTRY.add(col, GROUP, camera=camera, requires_raw=raw, units=units if name.endswith("_mean") else "",
                             description=f"static colour {name} of {roi} ({camera})")
                names.append(col)
        for name in CLIP_FEATURES:
            col = feature_prefix(GROUP, camera, None, None, name)
            REGISTRY.add(col, GROUP, camera=camera, requires_raw=raw, units="frames" if name == "n_frames_used" else "",
                         description=f"static colour {name} ({camera})")
            names.append(col)
    return names
