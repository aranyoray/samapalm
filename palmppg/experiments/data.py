"""Loading feature tables for experiments: per-camera frames, registry restoration, numeric design matrices.

Every row is one (participant, clip, camera). The test stream is never loaded here (it goes through
TestStreamGuard). Re-shot clips (clip1b) are loaded only for E14.
"""
from __future__ import annotations

import glob
from collections.abc import Iterable
from pathlib import Path

import numpy as np
import pandas as pd

from palmppg.core.config import Config
from palmppg.core.tracks import REGISTRY, FeatureRegistry

CAMERAS = ("pi", "phone", "pi_proxy")
DEFAULT_STREAMS = ("pilot", "development", "model_selection")
TEMPORAL_GROUPS = ("pulse", "hrv", "morphology", "apg", "perfusion", "resp")
STATIC_GROUPS = ("static_colour",)
EXTRA_NUMERIC_COVARIATES = {"sex_f": "1 when sex is F, else 0 (numeric encoding of the CRF sex field)"}


def restore_registry(columns: Iterable[str], camera: str | None, registry: FeatureRegistry = REGISTRY) -> None:
    """Re-register feature columns in a fresh process: producers first (their track flags win), then the feature
    store's naming rules for anything the producers do not list (D-013)."""
    from palmppg.core.config import load_pipeline_config

    cfg = load_pipeline_config()
    regs = []
    try:
        from palmppg.ingest import qc as _qc

        regs.append(_qc.register_features)
    except Exception:  # noqa: BLE001 - optional producer
        pass
    for mod, fn in (("palmppg.ingest.sync", "register_features"), ("palmppg.ecg.features", "register_features"),
                    ("palmppg.beats.run", "register_features"), ("palmppg.features.store", "register_features")):
        try:
            m = __import__(mod, fromlist=[fn])
            regs.append(getattr(m, fn))
        except Exception:  # noqa: BLE001
            continue
    import inspect

    for fn in regs:
        params = inspect.signature(fn).parameters
        try:
            fn(cfg=cfg) if "cfg" in params else fn()
        except Exception:  # noqa: BLE001 - a producer that cannot register leaves its columns to the store rules
            continue
    try:
        from palmppg.pulse.run import register_features as pulse_reg

        pulse_reg(cfg)
    except Exception:  # noqa: BLE001
        pass
    from palmppg.features.store import register_column

    for c in columns:
        if c not in registry:
            try:
                register_column(c, registry, camera)
            except Exception:  # noqa: BLE001 - an unregistrable column simply never enters a model
                continue
    for name, desc in EXTRA_NUMERIC_COVARIATES.items():
        registry.add(name, "covariate", description=desc)


def load_features(work_root: str | Path, streams: Iterable[str] = DEFAULT_STREAMS, clip_ids: Iterable[str] = ("clip1",)) -> dict[str, pd.DataFrame]:
    """{camera: frame} from work/<study_id>/<clip_id>/features_<camera>.parquet (test stream refused)."""
    streams = set(streams)
    if "test" in streams:
        raise PermissionError("the test stream is read only through TestStreamGuard (D-011)")
    out: dict[str, list[pd.DataFrame]] = {c: [] for c in CAMERAS}
    for clip_id in clip_ids:
        for cam in CAMERAS:
            for p in sorted(glob.glob(str(Path(work_root) / "*" / clip_id / f"features_{cam}.parquet"))):
                df = pd.read_parquet(p)
                if "stream" in df.columns and not df["stream"].isin(streams).all():
                    continue
                out[cam].append(df)
    frames = {}
    for cam, parts in out.items():
        if not parts:
            continue
        df = pd.concat(parts, ignore_index=True, sort=False)
        df["sex_f"] = (df.get("sex", pd.Series([None] * len(df))).astype(str).str.upper().str[0] == "F").astype(float)
        restore_registry(df.columns, cam)
        frames[cam] = df
    return frames


def numeric_matrix(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Numeric copy of `cols`: booleans to 0/1, numeric strings to numbers, everything else dropped."""
    out = {}
    for c in cols:
        s = df[c]
        if s.dtype == bool or str(s.dtype) == "boolean":
            out[c] = s.astype("float64")
            continue
        v = pd.to_numeric(s, errors="coerce")
        if v.notna().any():
            out[c] = v.astype(float)
    m = pd.DataFrame(out, index=df.index)
    keep = [c for c in m.columns if m[c].notna().sum() >= 2 and np.nanstd(m[c].to_numpy()) > 0]
    return m[keep]


def group_columns(df: pd.DataFrame, track: str, camera: str, groups: Iterable[str]) -> list[str]:
    """Registered, track-allowed, numeric columns of the given registry groups for one camera."""
    from palmppg.features.store import feature_columns

    cols = feature_columns(df, track, groups=list(groups), cameras=[camera], strict=False, numeric_only=False)
    return list(numeric_matrix(df, cols).columns)


def demographics_columns(cfg: Config) -> list[str]:
    cols = list(cfg.get("experiments.demographics_columns", ["age", "sex_f", "bmi", "mst_band"]))
    return [("sex_f" if c == "sex" else c) for c in cols]


def valid_mask(df: pd.DataFrame, camera: str) -> np.ndarray:
    col = f"qc__{camera}__valid_clip"
    if col not in df.columns:
        return np.zeros(len(df), dtype=bool)
    return df[col].fillna(False).astype(bool).to_numpy()
