"""Data manifest: sha256 per raw file, parquet round trip, verify reports changed / missing / new."""
from __future__ import annotations

import hashlib

import pandas as pd
import pytest

from palmppg.core.paths import StudyLayout
from palmppg.features.manifest import (
    MANIFEST_COLUMNS,
    assert_manifest_ok,
    data_manifest,
    manifest_path,
    manifest_summary,
    read_manifest,
    verify_manifest,
    write_manifest,
)
from tests.test_features_fixtures import make_study_tree

P1, P2 = "SWHT-PP-003-0001", "SWHT-PP-003-0002"


@pytest.fixture
def layout(tmp_path):
    root = tmp_path / "study"
    make_study_tree(root, {P1: "pilot", P2: "pilot"}, clips={P1: ["clip1", "clip1b"]})
    (root / "participants" / P1 / "pi" / "clip1.raw").write_bytes(bytes(range(256)) * 40)
    (root / "participants" / P1 / "ecg").mkdir()
    (root / "participants" / P1 / "ecg" / "kardia_0001.atc").write_bytes(b"ALIVE\x01\x00\x00" + b"\x00" * 100)
    return StudyLayout(root)


def test_manifest_rows_and_hashes(layout):
    df = data_manifest(layout)
    assert list(df.columns) == MANIFEST_COLUMNS
    paths = set(df["path"])
    assert f"participants/{P1}/pi/clip1.raw" in paths and f"participants/{P1}/crf.json" in paths
    assert "clock_sync_log.csv" in paths and "units/unit_01/luxmap.json" in paths
    raw = df[df["path"] == f"participants/{P1}/pi/clip1.raw"].iloc[0]
    expected = hashlib.sha256(bytes(range(256)) * 40).hexdigest()
    assert raw["sha256"] == expected and raw["bytes"] == 256 * 40 and raw["study_id"] == P1 and raw["part"] == "pi"
    parts = df.set_index("path")["part"]
    assert parts[f"participants/{P1}/crf.json"] == "crf" and parts[f"participants/{P1}/clinician.json"] == "clinician"
    assert parts[f"participants/{P1}/ecg/kardia_0001.atc"] == "ecg" and parts["clock_sync_log.csv"] == "clock_sync_log"
    assert parts["units/unit_01/luxmap.json"] == "units"
    assert df[df["part"] == "units"]["study_id"].isna().all()
    # P1 has 2 clips x (pi meta + phone meta) + crf + clinician + raw + atc = 8; P2 has 4; plus 2 root files
    assert df["study_id"].value_counts().to_dict() == {P1: 8, P2: 4}
    assert len(df) == 14
    assert df["mtime"].gt(0).all()
    assert data_manifest(layout, parts=("crf",))["part"].unique().tolist() == ["crf"]


def test_write_read_verify_roundtrip(layout, tmp_path):
    df = data_manifest(layout)
    path = write_manifest(df, date="2026-10-17", manifests_dir=tmp_path / "manifests")
    assert path == manifest_path("2026-10-17", tmp_path / "manifests") and path.name == "2026-10-17.parquet"
    back = read_manifest(path)
    for col in ("path", "sha256", "bytes", "part"):
        assert back[col].tolist() == df[col].tolist()
    assert back["study_id"].fillna("").tolist() == df["study_id"].fillna("").tolist()
    status = verify_manifest(layout, path)
    assert set(status["status"]) == {"ok"} and len(status) == len(df)
    assert manifest_summary(status) == {"ok": 14, "changed": 0, "missing": 0, "new": 0}
    assert assert_manifest_ok(layout, path)["ok"] == 14
    # mutate, delete, add
    (layout.root / "participants" / P1 / "pi" / "clip1.raw").write_bytes(b"corrupted")
    (layout.root / "participants" / P2 / "clinician.json").unlink()
    (layout.root / "participants" / P2 / "phone" / "clip1.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42")
    status = verify_manifest(layout, back).set_index("path")["status"]
    assert status[f"participants/{P1}/pi/clip1.raw"] == "changed"
    assert status[f"participants/{P2}/clinician.json"] == "missing"
    assert status[f"participants/{P2}/phone/clip1.mp4"] == "new"
    assert manifest_summary(status.reset_index()) == {"ok": 12, "changed": 1, "missing": 1, "new": 1}
    with pytest.raises(RuntimeError):
        assert_manifest_ok(layout, back)


def test_read_manifest_requires_all_columns(tmp_path):
    bad = tmp_path / "bad.parquet"
    pd.DataFrame({"path": ["a"], "sha256": ["0" * 64]}).to_parquet(bad, index=False)
    with pytest.raises(ValueError):
        read_manifest(bad)
