"""Stream isolation and target-leakage checks (protocol sections 6.7, 11.1, 13; DECISIONS D-011).

A feature table holds exactly one data stream; the locked test stream never shares a table with any
other stream and is only ever written by `build.build_test_stream_features`. Column names that encode a
reference quantity (cuff BP, clinician rhythm, cuff or ECG heart rate) are flagged before they can
enter a model as inputs.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

import pandas as pd

from ._common import is_null

TEST_STREAM = "test"
KNOWN_STREAMS: tuple[str, ...] = ("pilot", "development", "model_selection", "test")

# Regexes (case-insensitive) that mark a column name as a reference or target quantity. The protocol
# names the first five (bp_target, sbp, dbp, rhythm, hr_cuff); the rest are deterministic functions of
# the cuff reference (bp_category, bp_tertile, bp_spread, bracket_flag) or the ECG reference heart rate
# (ecg_hr). `rhythm` is anchored at a name-part boundary so the CRF disease flag `flag_arrhythmia`
# stays a covariate.
TARGET_PATTERNS: tuple[str, ...] = (r"bp_target", r"(^|_)sbp(_|$)", r"(^|_)dbp(_|$)", r"(^|_)rhythm", r"hr_cuff",
                                    r"bp_category", r"bp_tertile", r"bp_spread", r"bracket_flag", r"(^|_)ecg_hr(_|$)")


class StreamIsolationError(RuntimeError):
    pass


class TargetLeakageError(ValueError):
    pass


def streams_in(df: pd.DataFrame) -> list[str]:
    """Distinct non-null stream labels in a table, sorted."""
    if "stream" not in df.columns:
        raise StreamIsolationError("table has no 'stream' column; every feature table must carry one")
    return sorted({str(s) for s in df["stream"].tolist() if not is_null(s)})


def assert_stream_isolated(df: pd.DataFrame, expected_stream: str | None = None, allow_test: bool = False) -> str:
    """Raise StreamIsolationError unless `df` holds exactly one stream and no test rows (protocol 6.7).

    Rows with a missing stream are an error too: an unlabelled row could be a test-stream row. Pass
    `allow_test=True` only from the test-stream builder, which still requires a single stream.
    Returns the stream label.
    """
    found = streams_in(df)
    n_null = int(df["stream"].isna().sum())
    if n_null:
        raise StreamIsolationError(f"{n_null} row(s) have no stream label")
    if len(found) == 0:
        raise StreamIsolationError("table has no rows with a stream label")
    if len(found) > 1:
        raise StreamIsolationError(f"table mixes streams {found}; one parquet per stream, never joined")
    stream = found[0]
    if stream == TEST_STREAM and not allow_test:
        raise StreamIsolationError("test-stream rows found in a development-side table (DECISIONS D-011)")
    if expected_stream is not None and stream != expected_stream:
        raise StreamIsolationError(f"table holds stream '{stream}', expected '{expected_stream}'")
    return stream


def assert_tables_disjoint(frames: Sequence[pd.DataFrame]) -> None:
    """Raise when two tables share a stream label or a (study_id, clip_id, camera) row key."""
    seen_streams: dict[str, int] = {}
    seen_keys: set[tuple] = set()
    for i, df in enumerate(frames):
        s = assert_stream_isolated(df, allow_test=True)
        if s in seen_streams:
            raise StreamIsolationError(f"stream '{s}' appears in tables {seen_streams[s]} and {i}")
        seen_streams[s] = i
        cols = [c for c in ("study_id", "clip_id", "camera") if c in df.columns]
        for key in df[cols].itertuples(index=False, name=None):
            if key in seen_keys:
                raise StreamIsolationError(f"row key {key} appears in more than one table")
            seen_keys.add(key)


def check_no_target_leakage(feature_cols: Iterable[str], explicit_targets: Iterable[str] = (),
                            patterns: Sequence[str] = TARGET_PATTERNS) -> list[str]:
    """Column names (case-insensitive regex search with `patterns`) that look like reference or target
    quantities and are not declared in `explicit_targets`. Empty list means clean (protocol 11, 13)."""
    targets = {str(t) for t in explicit_targets}
    pats = [re.compile(p, re.IGNORECASE) for p in patterns]
    flagged = []
    for c in feature_cols:
        name = str(c)
        if name in targets:
            continue
        if any(p.search(name) for p in pats):
            flagged.append(name)
    return flagged


def assert_no_target_leakage(feature_cols: Iterable[str], explicit_targets: Iterable[str] = (),
                             patterns: Sequence[str] = TARGET_PATTERNS) -> None:
    bad = check_no_target_leakage(feature_cols, explicit_targets, patterns)
    if bad:
        raise TargetLeakageError(f"{len(bad)} feature column(s) carry a reference quantity: {bad[:10]}")
