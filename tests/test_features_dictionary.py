"""The data dictionary lists every registered column with group, camera, track flags, units, description."""
from __future__ import annotations

import pandas as pd

from palmppg.core.crf import derive
from palmppg.core.lint import scan_text
from palmppg.core.tracks import REGISTRY, FeatureRegistry
from palmppg.features._common import describe_column
from palmppg.features.dictionary import (
    DICTIONARY_COLUMNS,
    data_dictionary_frame,
    data_dictionary_markdown,
    write_data_dictionary,
)
from palmppg.features.store import build_clip_features, register_features
from tests.test_features_fixtures import CLINICIAN, SID, base_crf, make_clip_artefacts


def test_dictionary_contains_every_registered_column(cfg, tmp_path):
    register_features(cfg)
    d = tmp_path / "work" / SID / "clip1"
    make_clip_artefacts(d, "pi")
    make_clip_artefacts(d, "phone", with_embedding=False)
    crf = derive(base_crf(), cfg.section("crf"))
    df = build_clip_features(SID, "clip1", "pi", d, crf, CLINICIAN, cfg)
    df_phone = build_clip_features(SID, "clip1", "phone", d, crf, CLINICIAN, cfg)
    md = data_dictionary_markdown()
    names = set(REGISTRY.table()["name"])
    for name in names:
        assert f"| {name} |" in md, name
    for col in list(df.columns) + list(df_phone.columns):
        assert f"| {col} |" in md
    frame = data_dictionary_frame()
    assert list(frame.columns) == DICTIONARY_COLUMNS and len(frame) == len(names)
    assert frame["name"].is_unique
    row = frame.set_index("name").loc["pat__pi__pat_mean_ms"]
    assert row["requires_ecg"] and row["requires_raw"] and row["camera"] == "pi" and row["units"] == "ms"
    row = frame.set_index("name").loc["pulse__phone__thenar__POS__hr_bpm"]
    assert row["units"] == "bpm" and not row["requires_ecg"] and not row["requires_raw"] and row["group"] == "pulse"
    assert frame.set_index("name").loc["age", "units"] == "years"
    assert "| pat__pi__pat_mean_ms | pat | pi | yes | yes | ms |" in md
    assert scan_text(md) == []  # no banned vocabulary anywhere in the generated report


def test_extra_entries_and_overrides(tmp_path):
    reg = FeatureRegistry()
    reg.add("pulse__phone__thenar__POS__hr_bpm", "pulse", camera="phone")
    reg.add("qc__pi__drop_pct", "qc", camera="pi", requires_raw=True, units="%", description="custom | text")
    md = data_dictionary_markdown(reg, extra={"fold": {"group": "split", "description": "outer fold index"},
                                              "qc__pi__drop_pct": {"description": "overridden"}})
    assert "| fold | split | any | no | no |" in md
    assert "overridden" in md and "custom \\| text" not in md
    assert "2 groups" not in md and "3 columns" in md
    path = write_data_dictionary(tmp_path / "reports" / "data_dictionary.md", reg)
    assert path.exists() and path.read_text().startswith("# Data dictionary")
    frame = data_dictionary_frame(reg)
    assert frame["group"].tolist() == ["pulse", "qc"]  # sorted by group then name
    assert isinstance(frame, pd.DataFrame)


def test_describe_column_is_deterministic():
    assert describe_column("pulse__pi__thenar__POS__hr_bpm") == describe_column("pulse__pi__thenar__POS__hr_bpm")
    units, desc = describe_column("hrv__phone__sdnn_ms")
    assert units == "ms" and "6.5" in desc
    assert describe_column("embedding__phone__physnet__3")[0] == "a.u."
    assert describe_column("sync__ecg_uncertainty_s")[0] == "s"
    assert describe_column("qc__pi__drop_pct")[0] == "%"
    assert describe_column("mst_band") == ("band", "Monk Skin Tone band, self-selected 1..10")
