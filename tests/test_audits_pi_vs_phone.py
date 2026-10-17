"""Pi-versus-phone transfer table shape, arm derivation, gap arithmetic and markdown."""
from __future__ import annotations

import pandas as pd
import pytest

from palmppg.audits.pi_vs_phone import derive_arm, transfer_markdown, transfer_table, write_transfer_markdown

ARMS = {"pi_proxy_to_pi_proxy": 7.0, "pi_proxy_to_phone": 9.0, "phone_to_phone": 8.0, "pi_proxy_aug_to_phone": 8.5}
LEVELS = [("overall", "all", 0.0), ("mst_group", "4-5", -0.5), ("mst_group", "6-7", 0.0), ("mst_group", "8-10", 1.0)]


def _results():
    rows = []
    for s, lv, shift in LEVELS:
        for arm, v in ARMS.items():
            rows.append({"arm": arm, "stratum": s, "level": lv, "point": v + shift, "n": 50})
    return pd.DataFrame(rows)


def test_table_shape_and_gaps():
    t = transfer_table(_results(), metric_col="point")
    assert len(t) == 4 and (t.loc[0, "stratum"], t.loc[0, "level"]) == ("overall", "all")
    assert t["level"].tolist() == ["all", "4-5", "6-7", "8-10"]
    for arm in ("pi_to_pi", "pi_to_phone", "phone_to_phone", "pi_aug_to_phone"):
        assert arm in t.columns and f"n_{arm}" in t.columns and (t[f"n_{arm}"] == 50).all()
    assert t["gap_pi_to_phone"].tolist() == pytest.approx([2.0] * 4)
    assert t["gap_vs_phone_native"].tolist() == pytest.approx([1.0] * 4)
    assert t["aug_gain"].tolist() == pytest.approx([-0.5] * 4)
    assert t.loc[3, "pi_to_pi"] == pytest.approx(8.0)
    assert t.attrs["lower_is_better"] is True


def test_arm_derivation_from_cameras_and_errors():
    assert derive_arm("pi_proxy", "phone", False) == "pi_to_phone"
    assert derive_arm("pi", "phone", True) == "pi_aug_to_phone"
    assert derive_arm("phone", "phone") == "phone_to_phone"
    assert derive_arm("pi", "pi_proxy") == "pi_to_pi"
    assert derive_arm("phone", "pi") is None
    r = _results().drop(columns="arm")
    cams = {"pi_proxy_to_pi_proxy": ("pi_proxy", "pi_proxy", False), "pi_proxy_to_phone": ("pi_proxy", "phone", False),
            "phone_to_phone": ("phone", "phone", False), "pi_proxy_aug_to_phone": ("pi_proxy", "phone", True)}
    full = _results()
    r["camera_train"] = [cams[a][0] for a in full["arm"]]
    r["camera_test"] = [cams[a][1] for a in full["arm"]]
    r["augmented"] = [cams[a][2] for a in full["arm"]]
    t = transfer_table(r)
    pd.testing.assert_frame_equal(t, transfer_table(_results()))
    bad = _results()
    bad.loc[0, "arm"] = "phone_to_pi"
    with pytest.raises(ValueError):
        transfer_table(bad)
    with pytest.raises(KeyError):
        transfer_table(_results().drop(columns=["arm"]))
    partial = _results()[lambda d: d["arm"] != "pi_proxy_aug_to_phone"]
    tp = transfer_table(partial)
    assert tp["pi_aug_to_phone"].isna().all() and tp["aug_gain"].isna().all() and tp["gap_pi_to_phone"].notna().all()


def test_markdown(tmp_path):
    t = transfer_table(_results())
    md = transfer_markdown(t, metric_label="SBP error SD (mmHg)")
    assert "## Pi versus phone transfer (E16): SBP error SD (mmHg)" in md
    assert "| overall | all | 7.000 | 9.000 | 8.000 | 8.500 | 2.000 | 1.000 | -0.500 |" in md
    assert "Lower is better" in md
    p = write_transfer_markdown(t, tmp_path / "e16.md")
    assert p.read_text() == transfer_markdown(t)
    assert "Higher is better" in transfer_markdown(t, lower_is_better=False)
