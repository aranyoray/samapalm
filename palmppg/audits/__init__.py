"""Audits for SWHT-PP-003 (protocol sections 7, 10 and 11; experiments E6, E11, E16).

Modules
  shortcut      nuisance-variable shortcut audit (predict operator, unit, dept, ... from features; residual association)
  equity        coverage and error-SD non-inferiority across MST arms, error-on-MST regression, MST leakage probe
  leakage       split integrity, pulse-shuffle control summary, target-in-features check
  partition     standardised mean differences and chi-square balance between folds or streams
  pi_vs_phone   Pi-to-phone transfer table with per-stratum gaps

No feature column is created by this package; ``register_features`` is a no-op returning an empty list.
"""
from __future__ import annotations

from palmppg.core.tracks import REGISTRY, FeatureRegistry


def register_features(registry: FeatureRegistry = REGISTRY) -> list[str]:
    """Idempotent registry hook (COMMON rules): audits create no feature columns, so nothing is registered."""
    return []


__all__ = ["register_features"]
