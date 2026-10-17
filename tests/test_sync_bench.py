"""Bench self-test (section 4.5): 20/20 synthetic trials pass and the markdown is labelled synthetic."""
import re

import pytest

from palmppg.core.lint import scan_text
from palmppg.ingest.bench import bench_trials_report, evaluate_trial, synthetic_bench_selftest


@pytest.fixture(scope="module")
def selftest(tmp_path_factory):
    out = tmp_path_factory.mktemp("bench") / "bench_sync_report.md"
    from palmppg.core.config import load_pipeline_config
    return synthetic_bench_selftest(n_trials=20, seed=20261017, cfg=load_pipeline_config(), out_path=out), out


def test_selftest_passes_20_of_20(selftest):
    res, out = selftest
    assert res["n_trials"] == 20 and res["n_pass"] == 20
    for r in res["results"]:
        c = r["criteria"]
        assert c["pi_video"]["residual_max_frames"] < 1.0 and c["pi_video"]["n_matched"] == 10
        assert c["phone_video"]["residual_max_frames"] < 1.0 and c["phone_video"]["offset_error_frames"] < 1.0
        assert c["phone_video"]["drift_error"] * 12.0 < 1 / 30.0   # drift error accumulates to < 1 frame over the clip
        assert c["audio"]["residual_max_ms"] < 20.0 and c["audio"]["offset_error_ms"] < 20.0
        assert c["artefact"]["error_frames"] < 1.0 and c["artefact"]["n_pairs"] == 2
    assert out.exists()


def test_markdown_labelled_synthetic_and_clean(selftest):
    res, out = selftest
    md = out.read_text()
    assert md == res["markdown"]
    assert "SYNTHETIC SELF-TEST" in md and "no camera, buzzer or GPIO was involved" in md
    assert "hardware acceptance still outstanding" in md
    assert "20/20 trials pass every criterion" in md
    assert md.count("| pass |") >= 20
    assert scan_text(md) == []
    assert re.search(r"within 1\.0 frame period", md)


def test_hardware_label_and_failure_listing(selftest):
    res, _ = selftest
    trials = [dict(t) for t in res["trials"][:3]]
    trials[1] = dict(trials[1], audio_edges=None)                     # no beeps recorded
    trials[2] = dict(trials[2], artefact={"pairs": trials[2]["artefact"]["pairs"][:1], "true_offset_s": None})
    md = bench_trials_report(trials, hardware=True, out_path=None)
    assert "HARDWARE CAPTURES" in md and "SYNTHETIC" not in md
    assert "trial 2, audio: no beeps detected" in md
    assert "NOT ACCEPTED" in md
    ev = evaluate_trial(trials[2], __import__("palmppg.core.config", fromlist=["x"]).load_pipeline_config())
    assert ev["criteria"]["artefact"]["pass"] is None and ev["pass"] is False
    assert scan_text(md) == []
