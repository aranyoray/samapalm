"""Capture-side toolkit for the recording Pi (protocol sections 4.1, 4.2, 4.6 and 5).

Modules:
  sync_marker   LED + buzzer marker patterns P1/P2 on GPIO, logged as edges on CLOCK_BOOTTIME (section 4.2)
  capture_pi    picamera2 raw capture: preflight, fixed exposure/gain/AWB/focus, packed raw frames,
                per-frame SensorTimestamp log, clip meta, marker schedule (section 4.6)
  clock_sync.sh chronyd step at shift start/end and the clock_sync_log.csv row (section 4.1)
  offload.sh    rsync + SHA-256 manifest + completeness check (section 4.6)
  phone_settings.md, android/   OnePlus 12 operator checklist and the recorder route (section 5)

Hardware modules (picamera2, gpiozero) are imported lazily inside functions; every script has a
``--simulate`` mode that exercises the same code paths without hardware (DECISIONS D-009).
"""
from __future__ import annotations

from palmppg.core.tracks import REGISTRY

CAPTURE_FEATURES: tuple[tuple[str, str, str], ...] = (
    ("capture__pi__motion_flag", "qc", "frame-difference motion proxy above the unit threshold during capture (bool)"),
    ("capture__pi__motion_energy_dn", "qc", "median per-frame mean absolute difference of the high 8 bits (DN)"),
    ("capture__pi__live_sqi", "qc", "live SQI shown to the operator during capture (None until the live estimator ships)"),
)


def register_features() -> list[str]:
    """Register the capture-side QC columns with the process-wide registry (idempotent).

    They describe the Pi recording itself (motion proxy, live SQI placeholder), so they are camera ``pi``,
    ``requires_raw=False`` (nothing Bayer-specific is used downstream) and ``requires_ecg=False``.
    Serves CONTRACTS section 5 (every written column is registered first).
    """
    names = []
    for name, group, desc in CAPTURE_FEATURES:
        REGISTRY.add(name, group=group, camera="pi", requires_raw=False, requires_ecg=False, description=desc)
        names.append(name)
    return names
