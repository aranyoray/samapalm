"""Synthetic participant generator, augmentation library and positive-control helpers (WP8).

Protocol sections served: 3 (data layout), 4.2-4.3 (what the marker, LED, buzzer and thumb-lift
streams look like), 8 (augmentation transforms and the positive control), 12 run-order step 1
(synthetic data and positive control pass before any real clip).

Modules
  pulse_wave        beat schedule with RSA-like modulation and ectopic beats; per-beat PPG template
  palm_scene        synthetic left palm over the dark aperture, ground-truth landmarks and ROI masks,
                    linear-RGB rendering and Bayer RGGB sampling with a sensor noise model
  bayer_video       packed 10-bit CSI2P Pi clip writer with pts csv, meta, sync_events and truth json
  phone_video       phone proxy clip (H.264 + AAC beeps) with clock offset, drift and optional VFR
  ecg_synth         single-lead ECG from the same beats (R before foot by a per-participant PAT), ATC writer
  crf_synth         CRF / clinician sampling with a documented latent BP model
  cohort            study_root builder (clock_sync_log, unit calibration, participants) and CLI
  augment           every section 8 transform as a class, a registry and apply_chain with a parameter log
  positive_control  inject_known_pulse and score_recovery

Every truth quantity written by this package is registered in palmppg.core.tracks.REGISTRY by
`register_features()` with requires_ecg=True and requires_raw=True: generator ground truth is for scoring
only and can never enter a product_candidate model.
"""
from __future__ import annotations

from palmppg.core.tracks import REGISTRY

TRUTH_COLUMNS: dict[str, tuple[str, str]] = {
    "synth__truth__hr_bpm": ("mean pulse rate of the generated beat schedule", "bpm"),
    "synth__truth__ibi_sd_s": ("standard deviation of the generated inter-beat intervals", "s"),
    "synth__truth__n_ectopic": ("number of injected ectopic beats", "count"),
    "synth__truth__ac_dc_g": ("injected peak-to-peak AC/DC modulation in the G planes", "fraction"),
    "synth__truth__pat_s": ("generated pulse arrival time (R-peak to PPG foot)", "s"),
    "synth__truth__sbp_mmhg": ("latent systolic pressure of the synthetic participant", "mmHg"),
    "synth__truth__dbp_mmhg": ("latent diastolic pressure of the synthetic participant", "mmHg"),
    "synth__truth__upstroke_s": ("measured foot-to-peak time of the beat template", "s"),
    "synth__truth__systolic_width_s": ("measured full width at half maximum of the beat template", "s"),
    "synth__truth__notch_time_s": ("measured foot-to-dicrotic-notch time of the beat template", "s"),
    "synth__truth__notch_depth": ("measured notch depth below the dicrotic peak, unit-peak units", "fraction"),
    "synth__truth__reflection_index": ("measured dicrotic peak over systolic peak", "fraction"),
    "synth__truth__decay_tau_s": ("measured diastolic decay time constant", "s"),
    "synth__truth__melanin": ("synthetic melanin level of the rendered skin (synthetic tone shift)", "a.u."),
    "synth__truth__rhythm": ("rhythm class used to generate the beats", "category"),
    "synth__augment__chain": ("augmentation chain applied to the clip, as logged by apply_chain", "json"),
    "synth__augment__severity_index": ("severity index of the last transform in the chain", "index"),
}


def register_features() -> list[str]:
    """Register every synthetic-truth column with REGISTRY (idempotent). Protocol section 8 / 12 step 1."""
    names = []
    for name, (desc, units) in TRUTH_COLUMNS.items():
        REGISTRY.add(name, group="synth_truth", requires_ecg=True, requires_raw=True, camera="any",
                     description=desc, units=units, tags=("synthetic", "truth", "never_a_model_input"))
        names.append(name)
    return names


register_features()
