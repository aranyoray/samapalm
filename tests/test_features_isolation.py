"""Stream isolation raises on mixed streams or any test row; target-leakage check flags reference names."""
from __future__ import annotations

import pandas as pd
import pytest

from palmppg.features.isolation import (
    StreamIsolationError,
    TargetLeakageError,
    assert_no_target_leakage,
    assert_stream_isolated,
    assert_tables_disjoint,
    check_no_target_leakage,
    streams_in,
)


def _tbl(streams, sid_start=1):
    return pd.DataFrame({"study_id": [f"SWHT-PP-003-{sid_start + i:04d}" for i in range(len(streams))],
                         "clip_id": ["clip1"] * len(streams), "camera": ["pi"] * len(streams), "stream": streams})


def test_single_stream_passes():
    assert assert_stream_isolated(_tbl(["pilot", "pilot"])) == "pilot"
    assert assert_stream_isolated(_tbl(["development"]), expected_stream="development") == "development"
    assert streams_in(_tbl(["pilot", "pilot"])) == ["pilot"]


def test_mixed_streams_raise():
    with pytest.raises(StreamIsolationError):
        assert_stream_isolated(_tbl(["pilot", "development"]))
    with pytest.raises(StreamIsolationError):
        assert_stream_isolated(_tbl(["pilot"]), expected_stream="development")


def test_test_rows_raise_unless_explicitly_allowed():
    with pytest.raises(StreamIsolationError):
        assert_stream_isolated(_tbl(["test"]))
    with pytest.raises(StreamIsolationError):
        assert_stream_isolated(_tbl(["pilot", "test"]), allow_test=True)
    assert assert_stream_isolated(_tbl(["test", "test"]), allow_test=True) == "test"


def test_missing_or_null_stream_raise():
    with pytest.raises(StreamIsolationError):
        assert_stream_isolated(pd.DataFrame({"study_id": ["a"]}))
    with pytest.raises(StreamIsolationError):
        assert_stream_isolated(_tbl(["pilot", None]))
    with pytest.raises(StreamIsolationError):
        assert_stream_isolated(_tbl([]))


def test_tables_disjoint():
    assert_tables_disjoint([_tbl(["pilot"], 1), _tbl(["development"], 2), _tbl(["test"], 3)])
    with pytest.raises(StreamIsolationError):
        assert_tables_disjoint([_tbl(["pilot"], 1), _tbl(["pilot"], 2)])
    with pytest.raises(StreamIsolationError):
        assert_tables_disjoint([_tbl(["pilot"], 1), _tbl(["development"], 1)])  # same row key twice


def test_target_leakage_patterns():
    cols = ["pulse__phone__thenar__POS__hr_bpm", "age", "flag_arrhythmia", "arr_type", "bp_target_sbp", "bp_target_dbp",
            "bp_target_23_sbp", "rhythm_class", "clinician__rhythm", "ecg__clinician_rhythm", "hr_cuff_mean",
            "clinician__ecg_hr", "bp_category", "bp_tertile", "bp_spread_dbp", "bracket_flag", "absorbance_sbpx"]
    flagged = check_no_target_leakage(cols)
    assert set(flagged) == {"bp_target_sbp", "bp_target_dbp", "bp_target_23_sbp", "rhythm_class", "clinician__rhythm",
                            "ecg__clinician_rhythm", "hr_cuff_mean", "clinician__ecg_hr", "bp_category", "bp_tertile",
                            "bp_spread_dbp", "bracket_flag"}
    assert "flag_arrhythmia" not in flagged and "absorbance_sbpx" not in flagged
    assert check_no_target_leakage(cols, explicit_targets=["bp_target_sbp", "bp_target_dbp"]) == [
        c for c in flagged if c not in ("bp_target_sbp", "bp_target_dbp")]
    assert check_no_target_leakage(["age", "sex", "pulse__phone__thenar__POS__hr_bpm"]) == []
    with pytest.raises(TargetLeakageError):
        assert_no_target_leakage(["age", "bp_target_sbp"])
    assert_no_target_leakage(["age", "bp_target_sbp"], explicit_targets=["bp_target_sbp"])
