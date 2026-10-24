"""On-site quality grades for phone clips and ECGs (design contract docs/onboarding_v2_design.md section 4).

`onsite` is the numpy-only reference of the Kotlin module android/quality-core (package org.samahealth.quality);
both implement the same rules and are pinned by the shared fixtures in configs/quality_fixtures/.
"""
from palmppg.quality.onsite import (
    EcgQualityConfig,
    EcgTrace,
    Grade,
    RhythmSummary,
    RoiSeries,
    VideoQualityConfig,
    detect_qrs,
    parse_ecg_csv,
    parse_frames_csv,
    parse_roi_csv,
    read_atc,
    read_kardia_pdf,
    score_ecg,
    score_video,
    summarise_ecg,
)

__all__ = [
    "EcgQualityConfig", "EcgTrace", "Grade", "RhythmSummary", "RoiSeries", "VideoQualityConfig", "detect_qrs",
    "parse_ecg_csv", "parse_frames_csv", "parse_roi_csv", "read_atc", "read_kardia_pdf", "score_ecg",
    "score_video", "summarise_ecg",
]
