"""Capture documents and scripts exist and name every required setting (sections 4.5, 5); registry idempotence."""
from __future__ import annotations

import os
import re
from pathlib import Path

from palmppg.capture import CAPTURE_FEATURES, register_features
from palmppg.core.lint import scan_path, scan_text
from palmppg.core.tracks import REGISTRY

ROOT = Path(__file__).resolve().parents[1]
CAP = ROOT / "palmppg" / "capture"

PHONE_REQUIRED = [
    "Open Camera", "Camera2 API", "1920x1080", "30 fps", "H.264", "bitrate", "Constant frame rate", "2 s",
    "ISO", "shutter", "white balance", "WB lock", "focus lock", "stabilization", "OFF", "HDR", "Night", "AI", "Beauty",
    "audio", "torch", "capture_mode", "stock", "hotspot", "clock_sync.sh", "flat", "phone_flatfield.mp4",
    "clip1_meta.json", "led_block", "start_wall_ns", "sequential", "simultaneous",
]
ANDROID_REQUIRED = [
    "Open Camera", "PTS", "SENSOR_TIMESTAMP", "LED", "beep", "PalmRecorderActivity", "Gradle",
    "clip1_frames.csv", "frame_idx", "sensor_ts_ns", "wall_ns", "iso", "exposure_ns", "CONTROL_AE_LOCK", "CONTROL_AWB_LOCK",
    "variable frame rate", "offset", "drift",
    # the recorder now carries the ECG on the same clock, which is the reason it exists
    "CLOCK_BOOTTIME", "SENSOR_INFO_TIMESTAMP_SOURCE_REALTIME", "CLOCK_MONOTONIC", "MANUAL_SENSOR",
    "BleKardia", "ClockBridge", "PulseMeter", "lower envelope", "perfusion", "_ecg.atc", "not been run",
]
KOTLIN_REQUIRED = [
    "SENSOR_TIMESTAMP", "SENSOR_SENSITIVITY", "SENSOR_EXPOSURE_TIME", "CONTROL_AE_LOCK",
    "CONTROL_AWB_LOCK", "CONTROL_AF_MODE_OFF", "CONTROL_VIDEO_STABILIZATION_MODE_OFF", "LENS_OPTICAL_STABILIZATION_MODE_OFF",
    "VIDEO_W = 1920", "VIDEO_H = 1080", "FPS = 30", "setVideoSize(VIDEO_W, VIDEO_H)",
    "setVideoFrameRate(FPS)", "VideoEncoder.H264", "AudioSource.MIC",
    "frame_idx,sensor_ts_ns,wall_ns,iso,exposure_ns", "FLASH_MODE_TORCH", "CaptureCallback", "onCaptureCompleted",
    "_frames.csv", "_meta.json",
    # merged from the standalone recorder: one clock, a real ECG, and metadata read back from the file
    "ClockBridge", "BleKardia", "PulseMeter", "AtcWriter", "MediaMetadataRetriever",
    "CONTROL_AE_MODE_OFF", "SENSOR_FRAME_DURATION", "REQUEST_AVAILABLE_CAPABILITIES_MANUAL_SENSOR",
    "_sync.json", "EXTRA_ECG_SAMPLES",
]
README_REQUIRED = [
    "4.5", "metronome", "one frame", "20 ms", "tap", "sync_events.csv", "palmppg bench report", "bench_sync_report.md",
    "DECISIONS.md", "MANIFEST.sha256", "--simulate", "clock_sync.sh", "offload.sh", "capture_pi", "sync_marker",
]


def test_phone_settings_checklist_is_numbered_with_placeholders():
    text = (CAP / "phone_settings.md").read_text(encoding="utf-8")
    missing = [s for s in PHONE_REQUIRED if s.lower() not in text.lower()]
    assert not missing, missing
    steps = re.findall(r"^\s*(\d+)\.\s", text, flags=re.MULTILINE)
    assert len(steps) >= 15 and steps[0] == "1"
    assert [int(s) for s in steps] == list(range(1, len(steps) + 1))
    assert text.count("[screenshot placeholder:") >= 10
    # the stock app is excluded explicitly and stabilisation is off
    assert re.search(r"never the stock", text, flags=re.IGNORECASE)
    assert re.search(r"stabilization.*\*\*OFF\*\*", text, flags=re.IGNORECASE)


def test_android_readme_documents_both_routes():
    text = (CAP / "android" / "README.md").read_text(encoding="utf-8")
    missing = [s for s in ANDROID_REQUIRED if s.lower() not in text.lower()]
    assert not missing, missing
    assert "(a)" in text and "(b)" in text
    # the standalone recorder and the uncompiled sketch were folded into the onboarding app
    assert "SamaPalmRecorder" not in text and "PalmRecorder.kt" not in text


RECORDER = ROOT / "android" / "app" / "src" / "main" / "java" / "org" / "samahealth" / "onboarding" / "recorder"


def test_palm_recorder_source_states_status_and_logs_sensor_timestamp():
    text = (RECORDER / "PalmRecorderActivity.kt").read_text(encoding="utf-8")
    missing = [s for s in KOTLIN_REQUIRED if s not in text]
    assert not missing, missing
    head = "\n".join(text.splitlines()[:20])
    assert "bench acceptance" in head
    for name in ("ClockBridge.kt", "BleKardia.kt", "AtcWriter.kt", "PulseMeter.kt"):
        assert (RECORDER / name).exists(), name


def test_clock_bridge_converts_rather_than_assuming_one_clock():
    """A camera timestamp is only CLOCK_BOOTTIME when the sensor says so; the rest is an hours-wide bug."""
    text = (RECORDER / "ClockBridge.kt").read_text(encoding="utf-8")
    for s in ("SENSOR_INFO_TIMESTAMP_SOURCE_REALTIME", "elapsedRealtimeNanos", "nanoTime",
              "toReferenceNs", "offsetUncertaintyNs"):
        assert s in text, s


def test_atc_writer_matches_the_parser_layout():
    """The app writes ATC that palmppg/ecg/atc.py reads: crc32 over id + payload, 264 B info, <BHHBH fmt."""
    text = (RECORDER / "AtcWriter.kt").read_text(encoding="utf-8")
    for s in ("ALIVE", "CRC32", "RESOLUTION_NV", "EXACT_NV_PER_COUNT", "info", "fmt ", "ecg "):
        assert s in text, s
    widths = [32, 40, 44, 32, 32, 32, 52]
    assert sum(widths) == 264
    for w in widths:
        assert f"to {w}" in text


def test_capture_readme_bench_procedure():
    text = (CAP / "README.md").read_text(encoding="utf-8")
    missing = [s for s in README_REQUIRED if s not in text]
    assert not missing, missing
    steps = re.findall(r"^\s*(\d+)\.\s", text, flags=re.MULTILINE)
    assert len(steps) >= 10
    assert re.search(r"(Twenty|20) trials", text)


def test_scripts_exist_and_are_executable():
    for name in ("clock_sync.sh", "offload.sh"):
        p = CAP / name
        assert p.exists()
        assert os.access(p, os.X_OK)
        head = p.read_text(encoding="utf-8").splitlines()
        assert head[0].startswith("#!") and "bash" in head[0]
        assert any(line.strip() == "set -euo pipefail" for line in head)
    cs = (CAP / "clock_sync.sh").read_text(encoding="utf-8")
    for s in ("chronyc makestep", "chronyc tracking", "System time", "chronyd_makestep", "kardia_tablet",
              "date,time_utc,device,offset_ms_vs_phone,method,operator"):
        assert s in cs, s
    off = (CAP / "offload.sh").read_text(encoding="utf-8")
    for s in ("rsync -a --partial --info=progress2", "sha256sum", "MANIFEST.sha256", "COMPLETE.flag", "cp -a", "--check"):
        assert s in off, s


def test_register_features_idempotent_and_product_safe():
    names = register_features()
    names2 = register_features()
    assert names == names2 == [n for n, _, _ in CAPTURE_FEATURES]
    for n in names:
        meta = REGISTRY.get(n)
        assert meta is not None and meta.camera == "pi"
        assert meta.requires_ecg is False and meta.requires_raw is False
        assert meta.allowed_in("product_candidate") and meta.allowed_in("science")


def test_capture_tree_is_free_of_banned_vocabulary():
    hits = scan_path(CAP)
    assert not hits, hits
    for p in (ROOT / "tests").glob("test_capture_*.py"):
        assert scan_text(p.read_text(encoding="utf-8")) == [], p
