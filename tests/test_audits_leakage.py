"""Split integrity (participants, augmented copies), pulse-shuffle control summary, target-in-features check."""
from __future__ import annotations

import pandas as pd
import pytest

from palmppg.audits.leakage import pulse_shuffle_control_summary, split_integrity, target_in_features
from palmppg.core.config import rng

IDS = [f"P{i:02d}" for i in range(20)]


def _folds():
    out = []
    for k in range(4):
        test = IDS[k * 5:(k + 1) * 5]
        out.append(([i for i in IDS if i not in test], test))
    return out


def test_split_integrity_good_and_bad_folds():
    assert split_integrity(_folds())["ok"] is True
    dup = _folds()
    dup[1] = (dup[1][0], dup[1][1] + ["P00"])  # P00 in validation twice
    r = split_integrity(dup)
    assert r["ok"] is False and any("P00" in p and "folds 0 and 1" in p for p in r["problems"])
    overlap = _folds()
    overlap[2] = (overlap[2][0] + ["P10"], overlap[2][1])
    r2 = split_integrity(overlap)
    assert r2["ok"] is False and "both train and validation" in r2["problems"][0]
    assert split_integrity([{"train": IDS[5:], "test": IDS[:5]}])["ok"] is True


def test_augmented_copies_never_in_validation_nor_training_against_their_source():
    df = pd.DataFrame({"study_id": IDS + ["P03/aug1", "P12/aug1"], "augmented_from": [None] * 20 + ["P03", "P12"]})
    folds = _folds()
    # aug copies in training only where their source is also in training -> ok
    good = [(tr + [a for a in ("P03/aug1", "P12/aug1") if a.split("/")[0] in tr], te) for tr, te in folds]
    r = split_integrity(good, df)
    assert r["ok"] is True and r["n_augmented_rows"] == 2 and r["n_ids_unassigned"] == 0
    in_val = [(tr, te + ["P03/aug1"]) if "P03" in te else (tr, te) for tr, te in folds]
    r1 = split_integrity(in_val, df)
    assert r1["ok"] is False and "sits in validation" in r1["problems"][0]
    in_train = [(tr + ["P03/aug1"], te) for tr, te in folds]
    r2 = split_integrity(in_train, df)
    assert r2["ok"] is False and any("source P03 is in validation" in p for p in r2["problems"])
    with pytest.raises(KeyError):
        split_integrity(folds, df.drop(columns="study_id"))


def _long(shuffled_sd, seed=0):
    g = rng(seed, "shuffle")
    rows = []
    for i in range(120):
        sid = f"S{i:03d}"
        y = g.normal(130, 15)
        for arm, sd in (("demographics_only", 10.0), ("pulse_shuffled_control", shuffled_sd), ("temporal_only", 7.0)):
            rows.append({"study_id": sid, "arm": arm, "y": y, "pred": y + g.normal(0, sd)})
    return pd.DataFrame(rows)


def test_pulse_shuffle_control_summary_flags_a_leak_only_when_present():
    ok = pulse_shuffle_control_summary(_long(10.0), "y", "pred", n_resamples=200, seed=1)
    assert ok["leak_suspected"] is False and ok["n_participants"] == 120
    assert set(ok["table"]["arm"]) == {"demographics_only", "pulse_shuffled_control", "temporal_only"}
    assert ok["temporal_minus_shuffled_sd__temporal_only"] < 0
    leak = pulse_shuffle_control_summary(_long(4.0), "y", "pred", n_resamples=200, seed=1)
    assert leak["leak_suspected"] is True and leak["improvement_lo"] > 0 and leak["improvement_vs_demographics"] > 4
    with pytest.raises(KeyError):
        pulse_shuffle_control_summary(_long(10.0).query("arm != 'demographics_only'"), "y", "pred")


def test_target_in_features_by_name_and_by_value():
    g = rng(2, "target")
    df = pd.DataFrame({"bp_target_sbp": g.normal(130, 15, 100)})
    df["pulse__phone__thenar__POS__hr_bpm"] = g.normal(70, 8, 100)
    df["static_colour__phone__rg"] = g.normal(0, 1, 100)
    df["copy_of_target"] = 2 * df["bp_target_sbp"] + 1
    df["bp2_sbp_leak"] = g.normal(0, 1, 100)
    clean = target_in_features(df, ["pulse__phone__thenar__POS__hr_bpm", "static_colour__phone__rg"], "bp_target_sbp")
    assert clean["ok"] is True and clean["max_abs_corr"] < 0.5
    bad = target_in_features(df, ["pulse__phone__thenar__POS__hr_bpm", "copy_of_target", "bp2_sbp_leak"], "bp_target_sbp")
    assert bad["ok"] is False
    assert bad["by_name"] == ["bp2_sbp_leak"] and [c for c, _ in bad["by_value"]] == ["copy_of_target"]
    assert bad["max_abs_corr"] == pytest.approx(1.0)
    assert len(bad["problems"]) == 2
