"""Cohort builder: full study_root with every part present, under 60 s for the small profile (palmppg.synth.cohort)."""
import csv
import json
import subprocess
import sys
import time

import numpy as np
import pytest

from palmppg.core.paths import StudyLayout
from palmppg.synth import bayer_video as bv
from palmppg.synth.cohort import SMALL_PROFILE, make_cohort, participant_id, profile

def _cfg():
    from palmppg.core.config import load_pipeline_config

    return load_pipeline_config()



@pytest.fixture(scope="module")
def cohort(tmp_path_factory):
    cfg = _cfg()
    root = tmp_path_factory.mktemp("study")
    t0 = time.time()
    summary = make_cohort(root, 2, 21, cfg=cfg, small=True, overrides={"streams": ["pilot", "development"]})
    return {"root": root, "summary": summary, "elapsed": time.time() - t0}


def test_small_cohort_complete_and_fast(cohort, cfg):
    assert cohort["elapsed"] < 60.0
    layout = StudyLayout(cohort["root"])
    parts = layout.participants()
    assert [p.study_id for p in parts] == [participant_id(cfg, 1), participant_id(cfg, 2)]
    for p in parts:
        present = p.parts_present()
        assert all(present.values()), present
        assert p.clip_ids() == ["clip1"]
        truth = json.loads((p.root / "truth.json").read_text())
        assert {"latent", "crf", "clinician", "clock", "pulse", "pi", "phone", "ecg", "files"} <= set(truth)
        assert (p.root / truth["files"]["pi_truth"]).exists() and (p.root / truth["files"]["landmarks"]).exists()
        crf = json.loads(p.crf.read_text())
        assert crf["study_id"] == p.study_id
    streams = [json.loads(p.crf.read_text())["stream"] for p in parts]
    assert streams == ["pilot", "development"]
    assert (cohort["root"] / "cohort_truth.json").exists()


def test_clock_sync_log_and_unit_calibration(cohort, cfg):
    layout = StudyLayout(cohort["root"])
    with open(layout.clock_sync_log) as fh:
        rows = list(csv.DictReader(fh))
    assert list(rows[0].keys()) == ["date", "time_utc", "device", "offset_ms_vs_phone", "method", "operator"]
    assert {r["device"] for r in rows} == {"pi_unit_01", "kardia_tablet"} and len(rows) == 4
    unit = layout.unit("unit_01")
    for name in ("darkframe.raw", "flatfield.raw", "luxmap.json", "phone_flatfield.mp4"):
        assert (unit / name).exists(), name
    w, h = SMALL_PROFILE["width"], SMALL_PROFILE["height"]
    stride = bv.stride_bytes_for(w)
    flat = bv.unpack_csi2p((unit / "flatfield.raw").read_bytes(), w, h, stride).astype(float)
    dark = bv.unpack_csi2p((unit / "darkframe.raw").read_bytes(), w, h, stride).astype(float)
    assert (unit / "flatfield.raw").stat().st_size == stride * h
    centre = flat[h // 2 - 4:h // 2 + 4, w // 2 - 4:w // 2 + 4].mean()
    corner = flat[:8, :8].mean()
    assert corner < 0.8 * centre and centre < cfg.get("pi.white_level")
    assert abs(np.median(dark) - cfg.get("pi.black_level")) < 2
    lux = json.loads((unit / "luxmap.json").read_text())
    assert {"lux_grid", "rows", "cols"} <= set(lux) and len(lux["lux_grid"]) == lux["rows"]
    assert lux["lux_grid"][1][2] > lux["lux_grid"][0][0]


def test_truth_consistency_between_streams(cohort):
    layout = StudyLayout(cohort["root"])
    p = layout.participants()[0]
    pi = json.loads((p.pi / "clip1_truth.json").read_text())
    phone = json.loads((p.phone / "clip1_truth.json").read_text())
    ecg = json.loads((p.ecg / "ecg_truth.json").read_text())
    assert phone["led_schedule_ref_s"] == pi["led_schedule"]
    assert np.allclose(np.array(ecg["foot_t_ref_s"]) - np.array(ecg["r_times_ref_s"]), ecg["pat_per_beat_s"])
    assert set(ecg["foot_t_ref_s"]) <= set(pi["foot_t_ref_s"])
    assert pi["n_frames_written"] + len(pi["dropped_frame_idx"]) == pi["n_frames_nominal"]
    meta = json.loads(p.pi_meta().read_text())
    assert meta["n_frames_written"] == pi["n_frames_written"] and meta["study_id"] == p.study_id
    assert profile(load_cfg(), True)["seconds"] == SMALL_PROFILE["seconds"]


def load_cfg():
    from palmppg.core.config import load_pipeline_config

    return load_pipeline_config()


def test_cli_entry_point(tmp_path):
    root = tmp_path / "cli_root"
    cmd = [sys.executable, "-m", "palmppg.synth.cohort", "--root", str(root), "--n", "1", "--seed", "3", "--small", "--ecg-format", "pdf"]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    p = StudyLayout(root).participants()[0]
    assert all(p.parts_present().values()) and p.ecg_pdf() is not None and p.ecg_atc() is None
