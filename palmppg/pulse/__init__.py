"""Pulse extraction (protocol section 6.3, part of section 9).

Classical methods on ROI traces (`classical`), common preprocessing (`preprocess`), signal quality
(`sqi`), SNR-weighted multi-ROI fusion (`fusion`), instantaneous and clip-level rate (`rate`), the
per-camera runner that writes `pulse.parquet`, `pulse_morph.parquet` and `pulse_sqi.json` (`run`),
learned extractors on proxy video and STMaps (`learned`, torch) and adversarial denoising (`denoise`,
torch). The torch submodules are not imported here so `import palmppg.pulse` stays light.

Signal convention (CONTRACTS section 6): a positive deflection of every pulse signal is an increase in
blood volume, i.e. the negated skin intensity.
"""
from __future__ import annotations

from palmppg.pulse.run import register_features

__all__ = ["register_features"]
