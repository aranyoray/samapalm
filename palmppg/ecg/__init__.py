"""ECG processing for SWHT-PP-003 (protocol sections 3, 4.3 and 6.4).

Modules:
  atc            AliveCor ATC v1 chunk files: parse, describe, write (CONTRACTS section 3.6)
  pdf_digitiser  Kardia PDF strip fallback: synthetic renderer and the digitiser (ecg_digitised = True)
  clean          zero-phase band-pass plus mains notch, all bands from configs/pipeline.yaml ecg.*
  rpeaks         NeuroKit2 R-peak detection with a two-detector agreement check; IBI series with bounds
  features       heart rate, IBI statistics and rhythm features; instantaneous rate for the sync xcorr
  artefact       adaptive first-difference artefact onset detector for the fine anchor (section 4.3)
  labels         clinician.json loader; the clinician rhythm is the label, the app label a covariate
  run            per-participant orchestrator writing ecg/*.parquet and ecg/*.json (CONTRACTS section 4)

Everything derived from ECG timing is registered `requires_ecg=True` (group "ecg") and lives on the
science track only.
"""
from palmppg.ecg.features import register_features

__all__ = ["register_features"]
