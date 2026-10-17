import pandas as pd
import pytest

from palmppg.core.tracks import FeatureMeta, FeatureRegistry, TrackViolation, filter_frame, feature_prefix


def test_registry_track_filtering():
    reg = FeatureRegistry()
    reg.add("pulse__phone__thenar__POS__hr_bpm", "pulse", camera="phone")
    reg.add("pulse__pi__thenar__POS__hr_bpm", "pulse", camera="pi", requires_raw=True)
    reg.add("pat__pi__thenar__mean_ms", "pat", camera="pi", requires_ecg=True)
    assert reg.columns("product_candidate") == ["pulse__phone__thenar__POS__hr_bpm"]
    assert len(reg.columns("science")) == 3
    with pytest.raises(TrackViolation):
        reg.check_columns(["pat__pi__thenar__mean_ms"], "product_candidate")
    with pytest.raises(TrackViolation):
        reg.check_columns(["not_registered"], "science")
    df = pd.DataFrame({"study_id": ["a"], "pulse__phone__thenar__POS__hr_bpm": [70.0], "pat__pi__thenar__mean_ms": [200.0]})
    out = filter_frame(df, "product_candidate", reg, keep=["study_id"])
    assert list(out.columns) == ["study_id", "pulse__phone__thenar__POS__hr_bpm"]


def test_duplicate_registration_conflict():
    reg = FeatureRegistry()
    reg.add("x", "pulse")
    reg.add("x", "pulse")
    with pytest.raises(TrackViolation):
        reg.register(FeatureMeta("x", "pulse", requires_ecg=True))


def test_feature_prefix():
    assert feature_prefix("pulse", "pi", "thenar", "POS", "hr_bpm") == "pulse__pi__thenar__POS__hr_bpm"
    assert feature_prefix("qc", "phone", None, None, "drop_pct") == "qc__phone__drop_pct"
