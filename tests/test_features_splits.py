"""Grouped K-fold by participant: every id in exactly one test fold, no overlap, deterministic under the seed,
stratified balance, nested splits, re-shoot and augmented copies travelling with their participant, split files."""
from __future__ import annotations

import hashlib

import numpy as np
import pytest

from palmppg.features.splits import (
    SplitError,
    assert_augmented_never_in_validation,
    assert_folds_partition,
    assert_participant_disjoint,
    fold_row_masks,
    grouped_kfold,
    ids_sha256,
    nested_splits,
    participant_key,
    read_split,
    write_split,
)

IDS = [f"SWHT-PP-003-{i:04d}" for i in range(1, 48)]  # 47 participants


def test_each_participant_in_exactly_one_test_fold():
    folds = grouped_kfold(IDS, 5, seed=11)
    assert len(folds) == 5
    tested = [t for _, test in folds for t in test]
    assert sorted(tested) == sorted(IDS) and len(tested) == len(set(tested))
    sizes = sorted(len(test) for _, test in folds)
    assert sizes == [9, 9, 9, 10, 10]
    for train, test in folds:
        assert not set(train) & set(test)
        assert sorted(train + test) == sorted(IDS)
    assert_folds_partition(folds, IDS)


def test_deterministic_under_seed_and_salt():
    a = grouped_kfold(IDS, 5, seed=3)
    b = grouped_kfold(IDS, 5, seed=3)
    c = grouped_kfold(IDS, 5, seed=4)
    d = grouped_kfold(IDS, 5, seed=3, salt="inner")
    assert a == b
    assert a != c and a != d
    # order of the input never matters
    assert grouped_kfold(list(reversed(IDS)), 5, seed=3) == a


def test_duplicate_rows_and_reshoots_group_by_participant():
    rows = []
    for sid in IDS:
        rows.append(sid)
        if sid.endswith("3"):
            rows.append(f"{sid}/clip1b")
    folds = grouped_kfold(rows, 4, seed=5)
    tested = [t for _, test in folds for t in test]
    assert sorted(tested) == sorted(IDS)
    assert participant_key("SWHT-PP-003-0003/clip1b") == "SWHT-PP-003-0003"
    assert participant_key("SWHT-PP-003-0003__clip1b") == "SWHT-PP-003-0003"
    assert participant_key("SWHT-PP-003-0003:clip1") == "SWHT-PP-003-0003"
    train_mask, test_mask = fold_row_masks(rows, folds[0])
    keys = np.array([participant_key(r) for r in rows])
    assert set(keys[test_mask]) == set(folds[0][1]) and set(keys[train_mask]) == set(folds[0][0])
    assert np.all(train_mask ^ test_mask)  # every clip row on exactly one side


def test_stratified_balance():
    rng = np.random.default_rng(0)
    labels = ["T1", "T2", "T3"] * 15 + ["T1", "T2"]
    rng.shuffle(labels)
    folds = grouped_kfold(IDS, 5, seed=9, stratify_on=labels)
    lab = dict(zip(IDS, labels))
    for label in ("T1", "T2", "T3"):
        per_fold = [sum(lab[t] == label for t in test) for _, test in folds]
        assert max(per_fold) - min(per_fold) <= 1, (label, per_fold)
    assert_folds_partition(folds, IDS)


def test_errors():
    with pytest.raises(SplitError):
        grouped_kfold(IDS[:3], 5, seed=1)
    with pytest.raises(SplitError):
        grouped_kfold(IDS, 1, seed=1)
    with pytest.raises(SplitError):
        grouped_kfold(IDS, 3, seed=1, stratify_on=["a"])
    with pytest.raises(SplitError):
        assert_participant_disjoint(IDS[:5], IDS[4:8])
    assert_participant_disjoint(IDS[:5], IDS[5:8])
    with pytest.raises(SplitError):
        assert_participant_disjoint([f"{IDS[0]}/clip1b"], [IDS[0]])  # re-shoot of a test participant in train


def test_nested_splits():
    nested = nested_splits(IDS, 5, 3, seed=21)
    assert [f["outer"] for f in nested] == [0, 1, 2, 3, 4]
    outer_tests = [t for f in nested for t in f["test"]]
    assert sorted(outer_tests) == sorted(IDS)
    for f in nested:
        assert not set(f["train"]) & set(f["test"])
        assert len(f["inner"]) == 3
        vals = [v for i in f["inner"] for v in i["val"]]
        assert sorted(vals) == sorted(f["train"])  # inner folds partition the outer training set
        for i in f["inner"]:
            assert not set(i["train"]) & set(i["val"])
            assert not set(i["train"] + i["val"]) & set(f["test"])  # outer test never seen inside
            assert sorted(i["train"] + i["val"]) == sorted(f["train"])
    assert nested_splits(IDS, 5, 3, seed=21) == nested
    assert nested_splits(IDS, 5, 3, seed=22) != nested


def test_augmented_copy_rule():
    originals = IDS[:12]
    aug = {f"{sid}__aug_rot5": sid for sid in originals[:6]}
    source_map = {sid: None for sid in originals} | aug
    rows = list(source_map)
    folds = grouped_kfold(rows, 3, seed=2, source_study_ids=[source_map[r] for r in rows])
    tested = [t for _, test in folds for t in test]
    assert sorted(tested) == sorted(originals)  # augmented copies never form a group of their own
    for fold in folds:
        train_mask, test_mask = fold_row_masks(rows, fold, [source_map[r] for r in rows])
        train_rows = [r for r, m in zip(rows, train_mask) if m]
        test_rows = [r for r, m in zip(rows, test_mask) if m]
        assert not any(r in aug for r in test_rows)  # evaluation on originals only
        assert_augmented_never_in_validation((train_rows, test_rows), source_map)
    # violation 1: an augmented copy evaluated
    with pytest.raises(SplitError):
        assert_augmented_never_in_validation((originals[6:], [originals[0], f"{originals[0]}__aug_rot5"]), source_map)
    # violation 2: trained on a copy whose source is under evaluation
    with pytest.raises(SplitError):
        assert_augmented_never_in_validation((originals[6:] + [f"{originals[0]}__aug_rot5"], [originals[0]]), source_map)
    # clean: copy and its source both in training
    assert_augmented_never_in_validation((originals[:6] + list(aug), originals[6:]), source_map)


def test_split_file_roundtrip(tmp_path):
    folds = grouped_kfold(IDS, 5, seed=13)
    path = write_split("pilot_outer5", folds, seed=13, ids=IDS, splits_dir=tmp_path)
    assert path == tmp_path / "pilot_outer5.json"
    data = read_split("pilot_outer5", splits_dir=tmp_path, verify_ids=IDS)
    assert data["seed"] == 13 and data["n_splits"] == 5 and data["n_ids"] == len(IDS)
    assert data["ids_sha256"] == hashlib.sha256("\n".join(sorted(IDS)).encode()).hexdigest() == ids_sha256(IDS)
    assert data["folds"] == [(tr, te) for tr, te in folds]
    with pytest.raises(SplitError):
        read_split(path, verify_ids=IDS[:-1])
    text = path.read_text().replace(IDS[0], "SWHT-PP-003-9999")
    path.write_text(text)
    with pytest.raises(SplitError):
        read_split(path)
    nested = nested_splits(IDS, 3, 2, seed=1)
    p2 = write_split("nested", nested, seed=1, ids=IDS, splits_dir=tmp_path, kind="nested")
    back = read_split(p2)
    assert back["folds"][0]["inner"][0]["val"] == nested[0]["inner"][0]["val"]
