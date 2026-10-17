"""Feature store (protocol sections 6.7, 10, 11): per-clip feature rows, per-stream parquet tables,
participant-level splits, stream isolation, data manifests and the data dictionary.

`register_features()` populates `palmppg.core.tracks.REGISTRY` with every column the store writes.
"""
from .store import build_clip_features, feature_columns, register_features

__all__ = ["build_clip_features", "feature_columns", "register_features"]
