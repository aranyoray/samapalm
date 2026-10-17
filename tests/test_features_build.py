"""build_feature_store: one parquet per stream, test stream never built here, qc_table aggregation,
re-shoot clips as rows of the same participant, and the guarded test-stream builder."""
from __future__ import annotations

import json

import pandas as pd
import pytest

from palmppg.core import paths as core_paths
from palmppg.core.paths import StudyLayout
from palmppg.features.build import (
    build_feature_store,
    build_test_stream_features,
    clip_dirs,
    read_feature_table,
    tables_for_streams,
)
from palmppg.features.isolation import StreamIsolationError, assert_stream_isolated
from palmppg.features.store import feature_columns
from tests.test_features_fixtures import PULSE_SQI, QC_PI, make_clip_artefacts, make_study_tree

P1, P2, P3, PT = "SWHT-PP-003-0001", "SWHT-PP-003-0002", "SWHT-PP-003-0003", "SWHT-PP-003-9001"


@pytest.fixture
def study(tmp_path):
    root = tmp_path / "study"
    make_study_tree(root, {P1: "pilot", P2: "pilot", P3: "development", PT: "test"}, clips={P1: ["clip1", "clip1b"]})
    work = tmp_path / "work"
    make_clip_artefacts(work / P1 / "clip1", "pi")
    make_clip_artefacts(work / P1 / "clip1", "phone", with_embedding=False, with_ecg=False)
    make_clip_artefacts(work / P1 / "clip1b", "pi", grade="coarse")
    make_clip_artefacts(work / P2 / "clip1", "pi", with_embedding=False)
    make_clip_artefacts(work / P2 / "clip1", "pi_proxy", with_ecg=False, with_embedding=False)
    make_clip_artefacts(work / P3 / "clip1", "phone", with_ecg=False, with_embedding=False, grade="none")
    make_clip_artefacts(work / PT / "clip1", "pi")  # must never reach a development-side table
    return StudyLayout(root), work


def test_clip_dirs_union_of_work_and_layout(study):
    _layout, work = study
    assert [c for c, _ in clip_dirs(work, P1, ["clip1"])] == ["clip1", "clip1b"]
    assert [c for c, _ in clip_dirs(work, "nobody", ["clip1"])] == ["clip1"]


def test_build_feature_store_one_table_per_stream(cfg, study):
    layout, work = study
    out = build_feature_store(work, layout, cfg)
    assert set(out["tables"]) == {"pilot", "development"}
    # pi and phone rows exist wherever the raw clip meta exists (all-null when nothing was derived);
    # pi_proxy rows exist only where the proxy chain ran
    assert out["n_rows"] == {"pilot": 7, "development": 2, "model_selection": 0}
    assert out["skipped"] == {"test": 1}
    assert not (work / "tables" / "features_test.parquet").exists()
    assert not (work / "tables" / "features_model_selection.parquet").exists()

    pilot = read_feature_table(out["tables"]["pilot"], expected_stream="pilot")
    assert assert_stream_isolated(pilot) == "pilot"
    keys = sorted(zip(pilot["study_id"], pilot["clip_id"], pilot["camera"]))
    assert keys == [(P1, "clip1", "phone"), (P1, "clip1", "pi"), (P1, "clip1b", "phone"), (P1, "clip1b", "pi"),
                    (P2, "clip1", "phone"), (P2, "clip1", "pi"), (P2, "clip1", "pi_proxy")]
    assert PT not in set(pilot["study_id"])
    # numbers survive the parquet round trip
    pi_row = pilot[(pilot.study_id == P1) & (pilot.clip_id == "clip1") & (pilot.camera == "pi")].iloc[0]
    assert pi_row["pulse__pi__thenar__POS__hr_bpm"] == PULSE_SQI["POS__thenar"]["hr_bpm"]
    assert pi_row["qc__pi__drop_pct"] == QC_PI["drop_pct"]
    assert pi_row["sync_grade"] == "fine" and pi_row["time_of_day"] == "morning" and pi_row["lux_band"] == "200-400"
    assert bool(pi_row["qc__pi__hand_detected"]) is True and str(pilot["qc__pi__hand_detected"].dtype) == "boolean"
    b_row = pilot[(pilot.study_id == P1) & (pilot.clip_id == "clip1b") & (pilot.camera == "pi")].iloc[0]
    assert b_row["sync_grade"] == "coarse" and b_row["sync__ecg_map_method"] == "thumb_contact"
    # the phone row of clip1b has no artefacts (raw phone meta exists) -> all-null feature columns, ids present
    pb = pilot[(pilot.study_id == P1) & (pilot.clip_id == "clip1b") & (pilot.camera == "phone")]
    assert len(pb) == 1 and pd.isna(pb.iloc[0]["pulse__phone__thenar__POS__hr_bpm"])
    # product_candidate selection on the mixed-camera table never includes a pi or ECG column
    prod = feature_columns(pilot, "product_candidate")
    assert prod and not any("__pi__" in c or c.startswith(("pat__", "ecg__", "clinician__")) for c in prod)
    assert "pulse__pi_proxy__thenar__POS__hr_bpm" in prod and "pulse__phone__thenar__POS__hr_bpm" in prod

    dev = read_feature_table(out["tables"]["development"], expected_stream="development")
    assert dev["study_id"].tolist() == [P3, P3] and dev["camera"].tolist() == ["phone", "pi"]
    assert dev.iloc[0]["sync_grade"] == "none"
    # the pi row exists (raw pi meta present) but nothing was derived: no pi columns at all in this table,
    # and every non-identifier, non-covariate column of that row is null
    assert "pulse__pi__thenar__POS__hr_bpm" not in dev.columns
    pi_null = dev.iloc[1]
    assert pd.isna(pi_null["pulse__phone__thenar__POS__hr_bpm"]) and pd.isna(pi_null["static_colour__phone__mean_R"])
    assert pi_null["sync_grade"] == "none"  # the timeline is per clip, so every camera row carries its grade
    assert pi_null["age"] == 52.0 and pi_null["time_of_day"] == "morning"
    with pytest.raises(StreamIsolationError):
        assert_stream_isolated(pd.concat([pilot, dev], ignore_index=True))

    qc = pd.read_parquet(out["qc_table"])  # only clips with a qc.json: 5 pilot + 1 development
    assert len(qc) == 6 and set(qc["stream"]) == {"pilot", "development"}
    assert list(qc.columns[:4]) == ["study_id", "clip_id", "camera", "stream"]
    assert qc.set_index(["study_id", "clip_id", "camera"]).loc[(P1, "clip1b", "pi"), "sync_grade"] == "coarse"
    assert qc["drop_pct"].tolist() == [QC_PI["drop_pct"]] * 6
    manifest = json.loads(out["manifest"].read_text())
    assert manifest["n_rows"]["pilot"] == 7 and manifest["skipped"] == {"test": 1}
    assert tables_for_streams(work, ["pilot", "development", "model_selection"]).keys() == {"pilot", "development"}
    with pytest.raises(StreamIsolationError):
        tables_for_streams(work, ["test"])


def test_build_feature_store_refuses_test_stream(cfg, study):
    layout, work = study
    with pytest.raises(StreamIsolationError):
        build_feature_store(work, layout, cfg, streams=("pilot", "test"))


def test_test_stream_goes_through_guard(cfg, tmp_path):
    test_root = tmp_path / "test_stream"
    make_study_tree(test_root, {PT: "test"})
    work = tmp_path / "work_test"
    make_clip_artefacts(work / PT / "clip1", "pi")
    make_clip_artefacts(work / PT / "clip1", "phone", with_ecg=False, with_embedding=False)
    guard = core_paths.TestStreamGuard(test_root, log_path=tmp_path / "ACCESS_LOG.jsonl")
    out = build_test_stream_features(guard, work, cfg, reason="final evaluation", operator="pi", frozen_config_sha="abc")
    assert out["n_rows"] == 2 and out["table"].parent.name == "tables_test_stream"
    df = pd.read_parquet(out["table"])
    assert assert_stream_isolated(df, expected_stream="test", allow_test=True) == "test"
    with pytest.raises(StreamIsolationError):
        assert_stream_isolated(df)  # a development-side reader must refuse it
    assert df.iloc[0]["study_id"] == PT
    log = [json.loads(line) for line in (tmp_path / "ACCESS_LOG.jsonl").read_text().splitlines()]
    assert [e["action"] for e in log] == ["read"] and log[0]["frozen_config_sha"] == "abc"
    # read once: the second build is refused and logged as denied
    with pytest.raises(core_paths.TestStreamAccessDenied):
        build_test_stream_features(guard, work, cfg, reason="again", operator="pi", frozen_config_sha="abc")
    assert guard.reads_so_far() == 1


def test_test_stream_builder_rejects_foreign_participants(cfg, tmp_path):
    test_root = tmp_path / "test_stream"
    make_study_tree(test_root, {PT: "test", P1: "pilot"})
    guard = core_paths.TestStreamGuard(test_root, log_path=tmp_path / "log.jsonl")
    with pytest.raises(StreamIsolationError):
        build_test_stream_features(guard, tmp_path / "w", cfg, reason="x", operator="o", frozen_config_sha="s")
