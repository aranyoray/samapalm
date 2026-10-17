"""TrackGuard and target-leak checks (protocol 9 two tracks, 11.5)."""
import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LinearRegression

from palmppg.core.config import rng
from palmppg.core.tracks import FeatureRegistry, TrackViolation
from palmppg.models.track import TrackGuard, forbid_target_leak


@pytest.fixture
def registry():
    reg = FeatureRegistry()
    reg.add("pulse__phone__thenar__POS__hr_bpm", "pulse", camera="phone")
    reg.add("pulse__pi__thenar__POS__hr_bpm", "pulse", camera="pi", requires_raw=True)
    reg.add("pat__pi__thenar__mean_ms", "pat", camera="pi", requires_ecg=True)
    reg.add("age", "covariate")
    return reg


@pytest.fixture
def frame():
    g = rng(1, "track")
    n = 60
    hr = g.uniform(55, 95, n)
    pat = g.uniform(150, 300, n)
    return pd.DataFrame({
        "study_id": [f"SWHT-PP-003-{i:04d}" for i in range(n)],
        "pulse__phone__thenar__POS__hr_bpm": hr,
        "pulse__pi__thenar__POS__hr_bpm": hr + g.normal(0, 0.5, n),
        "pat__pi__thenar__mean_ms": pat,
        "age": g.uniform(20, 80, n),
    })


def test_requires_ecg_column_rejected_in_product_candidate(registry, frame):
    y = np.zeros(len(frame))
    guard = TrackGuard(LinearRegression(), "product_candidate", registry, keep=("study_id",))
    with pytest.raises(TrackViolation, match="forbidden in track 'product_candidate'"):
        guard.fit(frame, y)
    X = frame.drop(columns=["pat__pi__thenar__mean_ms"])
    with pytest.raises(TrackViolation):           # requires_raw column is forbidden too
        guard.fit(X, y)


def test_science_track_accepts_everything_and_records_columns(registry, frame):
    y = 2.0 * frame["pat__pi__thenar__mean_ms"].to_numpy() + 1.0
    guard = TrackGuard(LinearRegression(), "science", registry, keep=("study_id",)).fit(frame, y)
    assert guard.track == "science"
    assert guard.fitted_columns_ == [c for c in frame.columns if c != "study_id"]
    assert guard.n_features_in_ == 4
    pred = guard.predict(frame)
    assert np.allclose(pred, y, atol=1e-6)        # exact linear relation recovered
    shuffled = frame[list(reversed(frame.columns))]
    assert np.allclose(guard.predict(shuffled), pred)     # column order does not matter


def test_product_candidate_passes_on_phone_features(registry, frame):
    X = frame[["study_id", "pulse__phone__thenar__POS__hr_bpm", "age"]]
    y = X["pulse__phone__thenar__POS__hr_bpm"].to_numpy() * 0.5
    guard = TrackGuard(LinearRegression(), "product_candidate", registry, keep=("study_id",)).fit(X, y)
    assert guard.fitted_columns_ == ["pulse__phone__thenar__POS__hr_bpm", "age"]
    assert np.allclose(guard.predict(X), y, atol=1e-6)


def test_predict_checks_track_and_missing_columns(registry, frame):
    X = frame[["pulse__phone__thenar__POS__hr_bpm", "age"]]
    guard = TrackGuard(LinearRegression(), "product_candidate", registry).fit(X, np.ones(len(X)))
    with pytest.raises(TrackViolation, match="missing at predict time"):
        guard.predict(X[["age"]])
    with pytest.raises(TrackViolation):           # a forbidden column sneaking in at predict time
        guard.predict(frame[["pulse__phone__thenar__POS__hr_bpm", "age", "pat__pi__thenar__mean_ms"]])
    with pytest.raises(TrackViolation, match="unregistered"):
        guard.fit(X.assign(mystery=1.0), np.ones(len(X)))
    with pytest.raises(TrackViolation, match="before fit"):
        TrackGuard(LinearRegression(), "science", registry).predict(X)
    with pytest.raises(TypeError):
        guard.fit(X.to_numpy(), np.ones(len(X)))


def test_unknown_track_rejected(registry, frame):
    with pytest.raises(TrackViolation, match="unknown track"):
        TrackGuard(LinearRegression(), "product", registry).fit(frame[["age"]], np.ones(len(frame)))


def test_forbid_target_leak():
    g = rng(2, "leak")
    n = 50
    y = g.normal(size=n)
    X = pd.DataFrame({"a": g.normal(size=n), "b": g.normal(size=n)})
    assert forbid_target_leak(X, ["bp_target_sbp"], y) == ["a", "b"]
    with pytest.raises(TrackViolation, match="target column"):
        forbid_target_leak(X.assign(bp_target_sbp=y), ["bp_target_sbp"])
    with pytest.raises(TrackViolation, match="target-derived"):
        forbid_target_leak(X.assign(bp_category="normal"), ["sbp"])
    with pytest.raises(TrackViolation, match="copy of the target"):
        forbid_target_leak(X.assign(renamed=y * 3.0 + 1.0), ["sbp"], y)
    assert forbid_target_leak(X.assign(weak=y + 5 * g.normal(size=n)), ["sbp"], y)
