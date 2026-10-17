"""Ingest layer (protocol sections 3, 5, 6.1): raw formats in, calibrated planes and QC out.

Modules owned by WP1:
  bayer        10-bit packed CSI-2 Bayer unpack/pack, plane split, streaming clip reader, preview, proxy zarr
  calibration  per-unit dark frame / flat field, vignetting residual
  timestamps   true frame times from sensor timestamps or PTS, drops, uniform grid, clock-sync log
  phone        ffprobe PTS, PyAV decode, sRGB inversion, audio, EIS residual detector, phone flat field
  pi_proxy     Pi frames -> 8-bit sRGB H.264 "pi_proxy" camera stream (DECISIONS D-006)
  qc           saturation, flicker, lighting drift, qc.json builder, qc_table upsert
  run          ingest_pi / ingest_phone orchestrators

Sync, LED/audio marker detection, anchors and the bench report live in sibling modules owned by WP2 and
are never imported from here. Heavy decoders (PyAV, OpenCV) are imported by the modules that need them.
"""
from __future__ import annotations

from palmppg.ingest import bayer, calibration, qc, timestamps

__all__ = ["bayer", "calibration", "qc", "timestamps"]
