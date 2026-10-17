"""Package-level feature registration: every column the models package can emit is registered once."""
import pytest

from palmppg.core.tracks import FeatureRegistry, TrackViolation
from palmppg.models import register_features


def test_register_features_idempotent_and_track_aware():
    reg = FeatureRegistry()
    first = register_features(reg, cameras=("pi", "phone"), rois=("fused",))
    second = register_features(reg, cameras=("pi", "phone"), rois=("fused",))
    assert first == second and len(first) == len(set(first))
    groups = {reg.get(n).group for n in first}
    assert groups == {"hrv", "ecg", "embedding"}
    phone = [n for n in first if "__phone__" in n]
    pi = [n for n in first if "__pi__" in n]
    reg.check_columns(phone, "product_candidate")
    with pytest.raises(TrackViolation):
        reg.check_columns(pi[:5], "product_candidate")
    reg.check_columns(pi, "science")
    random_cols = [n for n in phone if "randominit" in n]
    assert random_cols and all("__randominit__" in n for n in random_cols)
    assert all("randominit" not in n for n in phone if "papagei_s__d" in n)
    assert sum(n.startswith("ecg__visibility__") for n in first) == 10
