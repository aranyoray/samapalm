"""Two model tracks, enforced by code rather than by convention.

  product_candidate : features a consumer phone can produce with no ECG and no box
                      (phone camera, or Pi features restricted to an 8-bit sRGB compressed proxy).
  science           : Pi raw Bayer features, ECG-aligned features, pulse arrival time.

Every feature column is registered with FeatureMeta. `requires_ecg=True` columns can never enter a
product_candidate model; `requires_raw=True` columns (Bayer-plane, 10-bit, uncompressed) cannot either.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Iterable

import pandas as pd

TRACKS = ("product_candidate", "science")
CAMERAS = ("pi", "phone", "pi_proxy")  # pi_proxy = Pi frames pushed through an 8-bit sRGB + H.264 proxy chain


class TrackViolation(RuntimeError):
    pass


@dataclass(frozen=True)
class FeatureMeta:
    name: str
    group: str                       # qc, sync, static_colour, pulse, hrv, morphology, apg, perfusion, embedding, ecg, pat, covariate
    requires_ecg: bool = False
    requires_raw: bool = False
    camera: str = "any"              # pi | phone | pi_proxy | any
    description: str = ""
    units: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)

    def allowed_in(self, track: str) -> bool:
        if track not in TRACKS:
            raise ValueError(f"unknown track {track}")
        if track == "science":
            return True
        return not (self.requires_ecg or self.requires_raw)


class FeatureRegistry:
    """Process-wide registry of feature column metadata (one entry per column name)."""

    def __init__(self) -> None:
        self._items: dict[str, FeatureMeta] = {}

    def register(self, meta: FeatureMeta) -> FeatureMeta:
        prev = self._items.get(meta.name)
        if prev is not None and prev != meta:
            raise TrackViolation(f"feature {meta.name} registered twice with different metadata")
        self._items[meta.name] = meta
        return meta

    def add(self, name: str, group: str, **kw) -> FeatureMeta:
        return self.register(FeatureMeta(name, group, **kw))

    def get(self, name: str) -> FeatureMeta | None:
        return self._items.get(name)

    def __contains__(self, name: str) -> bool:
        return name in self._items

    def columns(self, track: str, camera: str | None = None, groups: Iterable[str] | None = None) -> list[str]:
        gs = set(groups) if groups else None
        out = []
        for m in self._items.values():
            if not m.allowed_in(track):
                continue
            if camera is not None and m.camera not in ("any", camera):
                continue
            if gs is not None and m.group not in gs:
                continue
            out.append(m.name)
        return out

    def table(self) -> pd.DataFrame:
        return pd.DataFrame([asdict(m) for m in self._items.values()])

    def check_columns(self, columns: Iterable[str], track: str, strict_unknown: bool = True) -> list[str]:
        """Raise TrackViolation if any column is forbidden in `track`; return the allowed list."""
        bad, unknown, ok = [], [], []
        for c in columns:
            m = self._items.get(c)
            if m is None:
                unknown.append(c)
                continue
            (ok if m.allowed_in(track) else bad).append(c)
        if bad:
            raise TrackViolation(f"{len(bad)} column(s) forbidden in track '{track}': {bad[:10]}")
        if unknown and strict_unknown:
            raise TrackViolation(f"{len(unknown)} unregistered column(s) cannot enter a model: {unknown[:10]}")
        return ok


REGISTRY = FeatureRegistry()


def filter_frame(df: pd.DataFrame, track: str, registry: FeatureRegistry = REGISTRY, keep: Iterable[str] = ()) -> pd.DataFrame:
    """Return only the columns of df allowed in `track` (plus `keep`, e.g. ids and targets)."""
    keep = set(keep)
    cols = [c for c in df.columns if c in keep or (c in registry and registry.get(c).allowed_in(track))]
    return df[cols]


def assert_product_candidate_clean(columns: Iterable[str], registry: FeatureRegistry = REGISTRY) -> None:
    registry.check_columns(columns, "product_candidate", strict_unknown=True)


def feature_prefix(group: str, camera: str, roi: str | None, method: str | None, name: str) -> str:
    """Canonical column naming: group__camera__roi__method__name (missing parts omitted)."""
    parts = [group, camera] + [p for p in (roi, method) if p] + [name]
    return "__".join(parts)
