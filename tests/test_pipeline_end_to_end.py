"""End-to-end pipeline on one small synthetic participant: every stage runs, outputs exist, sync and pulse are sane."""
import json

import numpy as np
import pandas as pd
import pytest

from palmppg.core.paths import StudyLayout, WorkLayout


@pytest.fixture(scope="module")
def one_run(tmp_path_factory):
    from palmppg.core.config import load_pipeline_config
    from palmppg.pipeline.run_participant import run_participant
    from palmppg.synth.cohort import make_cohort

    cfg = load_pipeline_config()
    root = tmp_path_factory.mktemp("e2e")
    make_cohort(root / "study", 1, 5, cfg, overrides={"pi_options": {"drops_pct": 0.0, "flicker_pct": 0.0, "drift_pct": 0.0, "jitter_px": 0.0}},
                small=True)
    lay, work = StudyLayout(root / "study"), WorkLayout(root / "work")
    sid = lay.participants()[0].study_id
    res = run_participant(lay, sid, work, cfg)
    return lay, work, sid, res


@pytest.mark.slow
def test_every_stage_ok_and_outputs_exist(one_run):
    lay, work, sid, res = one_run
    failed = [s["stage"] + ": " + s.get("error", "") for s in res["stages"] if s["status"] != "ok"]
    assert not failed, failed
    clip = work.root / sid / "clip1"
    for p in ("timeline.json", "sync.json", "pipeline.json", "ecg/rpeaks.parquet", "features_pi.parquet", "features_phone.parquet",
              "features_pi_proxy.parquet", "pi/beats.parquet", "pi/beat_features.json", "pi/qc.json"):
        assert (clip / p).exists(), p


@pytest.mark.slow
def test_sync_and_pulse_rate_against_truth(one_run):
    lay, work, sid, res = one_run
    clip = work.root / sid / "clip1"
    truth = json.loads((lay.participant(sid).pi / "clip1_truth.json").read_text())
    tl = json.loads((clip / "timeline.json").read_text())
    assert tl["sync_grade"] in ("fine", "coarse")
    assert tl["maps"]["ecg"]["method"] in ("artefact_lift", "thumb_contact", "wall_clock")
    bf = json.loads((clip / "pi" / "beat_features.json").read_text())
    win = tl["analysis_window"]
    hs = truth["hr_series"]
    t, h = np.asarray(hs["t_ref_s"]), np.asarray(hs["hr_bpm"])
    truth_hr = float(np.mean(h[(t >= win["start_s"]) & (t < win["end_s"])]))
    assert abs(60000.0 / bf["hrv"]["median_ibi_ms"] - truth_hr) < 3.0
    f = pd.read_parquet(clip / "features_pi.parquet")
    assert f["camera"].iloc[0] == "pi" and "bp_target_sbp" in f.columns


@pytest.mark.slow
def test_rerun_downstream_reproduces_features(one_run):
    from palmppg.core.config import load_pipeline_config
    from palmppg.pipeline.run_participant import rerun_downstream

    lay, work, sid, _ = one_run
    before = pd.read_parquet(work.root / sid / "clip1" / "features_pi.parquet")
    r = rerun_downstream(lay, sid, work, load_pipeline_config())
    assert r["ok"]
    after = pd.read_parquet(work.root / sid / "clip1" / "features_pi.parquet")
    col = "hrv__pi__median_ibi_ms"
    assert np.isclose(before[col].iloc[0], after[col].iloc[0])


def test_landmark_adapter_converts_generator_layout(tmp_path):
    from palmppg.pipeline.run_participant import provider_landmarks_json

    src = tmp_path / "lm.json"
    src.write_text(json.dumps({"is_left": True, "palmar": True, "static": True,
                               "landmarks": [{"name": f"p{i}", "x": i / 21, "y": 0.5, "z": 0.0} for i in range(21)]}))
    out = provider_landmarks_json(src, tmp_path / "out.json")
    d = json.loads(out.read_text())
    assert len(d["static"]) == 21 and d["static"][3] == [3 / 21, 0.5, 0.0]
    assert provider_landmarks_json(tmp_path / "missing.json", tmp_path / "x.json") is None
