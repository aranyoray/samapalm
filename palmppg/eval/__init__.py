"""Evaluation layer for SWHT-PP-003 (protocol sections 7, 10 and 11).

Modules
  metrics          BP agreement, rhythm and pulse-rate metrics with coverage that counts abstentions as failures
  bootstrap        participant-level (cluster) bootstrap confidence intervals
  noninferiority   one-sided non-inferiority tests for coverage and error-SD ratio (equity, section 7)
  calibration      reliability tables, expected calibration error, decision curves, regression calibration
  strata           StrataEngine: every metric overall and per stratum with pooled small cells and both baselines
  baselines        predict-the-mean, demographics-only ridge, pulse-shuffled leakage control
  gonogo           frozen pilot go/no-go evaluation (refuses to run on a tampered frozen config)
  multiplicity     fixed-sequence hierarchy for primary and key secondary endpoints
  plots            headless matplotlib figures (PNG + SVG)

No feature column is created by this package: ``register_features`` exists for uniformity with the other
packages and is a no-op that returns the (empty) list of columns it owns.
"""
from __future__ import annotations

from palmppg.core.tracks import REGISTRY, FeatureRegistry


def register_features(registry: FeatureRegistry = REGISTRY) -> list[str]:
    """Idempotent registry hook (COMMON rules). The evaluation layer writes prediction and metric tables,
    never feature columns, so nothing is registered and an empty list is returned."""
    return []


__all__ = ["register_features"]
