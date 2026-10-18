"""palmppg.beats: beat segmentation and beat-level features of the palm pulse (protocol 6.5, 6.6).

  segmentation  systolic peaks, feet (intersecting tangents), dicrotic notches, matched-filter second pass, IBIs
  quality       per-beat quality index in [0, 1] (template correlation, IBI plausibility, amplitude consistency)
  hrv           SDNN, RMSSD, pNN50, sample entropy, IBI-histogram entropy, SD1/SD2, turning-point ratio
  morphology    per-beat and ensemble (quality-gated median and SD) pulse-wave morphology
  apg           acceleration plethysmogram a, b, c, d, e waves and the ageing index of the ensemble beat
  perfusion     perfusion index (AC/DC in percent) per ROI and channel from the raw traces
  resp          respiratory proxy from the amplitude modulation of the pulse and from the IBI series
  pat           pulse arrival time and ECG-versus-pulse IBI comparison, sync grade "fine" only, requires_ecg
  run           run_beats(): per-camera runner writing beats.parquet, beat_features.json and pat.json

Every time is float seconds on the reference clock; nothing here is aligned by wall clock or frame index.
"""
from palmppg.beats.run import register_features, run_beats

__all__ = ["register_features", "run_beats"]
