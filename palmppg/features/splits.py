"""Participant-level splits (protocol sections 10 and 11.1) and the augmentation rule of section 8.

Every split is grouped by participant: a participant's clips (including the single permitted re-shoot,
clip1b) and every augmented copy of them (rows carrying `source_study_id`) sit on one side of every
fold boundary. Split files are written under data/splits/<name>.json with the seed and the sha256 of
the sorted id list so a split can be checked against the table it was made for.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from palmppg.core.config import REPO_ROOT, rng

from ._common import is_null

SPLITS_DIR = REPO_ROOT / "data" / "splits"
_CLIP_SUFFIX = re.compile(r"__clip\w*$")


class SplitError(ValueError):
    pass


# --------------------------------------------------------------------------- participant keys
def participant_key(study_id: Any, source_study_id: Any = None) -> str:
    """The participant an id belongs to. Augmented copies map to their `source_study_id`; composite ids
    such as `SWHT-PP-003-0001/clip1b`, `...:clip1b` or `...__clip1b` map to the participant part."""
    if not is_null(source_study_id) and str(source_study_id).strip() != "":
        return participant_key(str(source_study_id))
    s = str(study_id).strip()
    s = re.split(r"[/:|]", s, maxsplit=1)[0]
    return _CLIP_SUFFIX.sub("", s)


def participant_keys(study_ids: Iterable[Any], source_study_ids: Iterable[Any] | None = None) -> list[str]:
    ids = [str(x) for x in study_ids]
    if source_study_ids is None:
        return [participant_key(i) for i in ids]
    src = list(source_study_ids)
    if len(src) != len(ids):
        raise SplitError("source_study_ids must align with study_ids")
    return [participant_key(i, s) for i, s in zip(ids, src)]


def ids_sha256(ids: Iterable[Any]) -> str:
    """sha256 of the sorted, de-duplicated id list (one id per line)."""
    uniq = sorted({str(x) for x in ids})
    return hashlib.sha256("\n".join(uniq).encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- grouped K-fold
def grouped_kfold(study_ids: Iterable[Any], n_splits: int, seed: int, stratify_on: Iterable[Any] | None = None,
                  source_study_ids: Iterable[Any] | None = None, salt: str = "") -> list[tuple[list[str], list[str]]]:
    """Grouped K-fold by participant (protocol 10, 11.1): every participant is in exactly one test fold.

    `study_ids` may contain duplicates (one entry per clip row); `source_study_ids` (aligned, optional)
    maps augmented copies to their source so they travel with it. `stratify_on` (aligned, optional)
    gives a label per row; a participant takes the first label seen and participants are dealt to folds
    stratum by stratum so each fold receives a balanced share of every label. Deterministic under
    (seed, salt) via `palmppg.core.config.rng`. Returns [(train_participants, test_participants), ...]
    with sorted participant keys.
    """
    n_splits = int(n_splits)
    if n_splits < 2:
        raise SplitError("n_splits must be at least 2")
    ids = [str(x) for x in study_ids]
    keys = participant_keys(ids, source_study_ids)
    groups = sorted(set(keys))
    if len(groups) < n_splits:
        raise SplitError(f"{len(groups)} participant(s) cannot fill {n_splits} folds")
    label_of: dict[str, str] = {}
    if stratify_on is not None:
        labels = list(stratify_on)
        if len(labels) != len(ids):
            raise SplitError("stratify_on must align with study_ids")
        for k, lab in zip(keys, labels):
            label_of.setdefault(k, "<na>" if is_null(lab) else str(lab))
    by_stratum: dict[str, list[str]] = {}
    for k in groups:
        by_stratum.setdefault(label_of.get(k, ""), []).append(k)
    g = rng(int(seed), f"grouped_kfold:{n_splits}:{salt}")
    folds: list[list[str]] = [[] for _ in range(n_splits)]
    offset = int(g.integers(0, n_splits))
    for lab in sorted(by_stratum):
        members = by_stratum[lab]
        for j in g.permutation(len(members)):
            folds[offset % n_splits].append(members[int(j)])
            offset += 1
    out: list[tuple[list[str], list[str]]] = []
    for k in range(n_splits):
        test = sorted(folds[k])
        train = sorted(x for j in range(n_splits) if j != k for x in folds[j])
        out.append((train, test))
    return out


def nested_splits(study_ids: Iterable[Any], n_outer: int, n_inner: int, seed: int,
                  stratify_on: Iterable[Any] | None = None, source_study_ids: Iterable[Any] | None = None) -> list[dict]:
    """Nested grouped CV (protocol 10, pilot: nested 5-fold). For each outer fold the outer training
    participants are split again into `n_inner` grouped folds (salted by the outer index). Returns
    [{"outer": k, "train": [...], "test": [...], "inner": [{"train": [...], "val": [...]}, ...]}, ...]."""
    ids = [str(x) for x in study_ids]
    keys = participant_keys(ids, source_study_ids)
    label_of: dict[str, Any] = {}
    if stratify_on is not None:
        for k, lab in zip(keys, list(stratify_on)):
            label_of.setdefault(k, lab)
    outer = grouped_kfold(ids, n_outer, seed, stratify_on, source_study_ids)
    result = []
    for k, (train, test) in enumerate(outer):
        strat = [label_of.get(p) for p in train] if stratify_on is not None else None
        inner = grouped_kfold(train, n_inner, seed, strat, None, salt=f"outer{k}")
        result.append({"outer": k, "train": list(train), "test": list(test),
                       "inner": [{"train": tr, "val": va} for tr, va in inner]})
    return result


# --------------------------------------------------------------------------- row selection
def fold_row_masks(study_ids: Iterable[Any], fold: Any, source_study_ids: Iterable[Any] | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Row-level (train_mask, test_mask) for a participant-level fold. Augmented copies (non-null
    source_study_id) are training rows only, never evaluation rows (protocol 8)."""
    train_ids, test_ids = _fold_parts(fold)
    ids = [str(x) for x in study_ids]
    src = list(source_study_ids) if source_study_ids is not None else [None] * len(ids)
    keys = participant_keys(ids, src)
    train_set, test_set = set(train_ids), set(test_ids)
    is_aug = np.array([not is_null(s) and str(s).strip() != "" for s in src], dtype=bool)
    train_mask = np.array([k in train_set for k in keys], dtype=bool)
    test_mask = np.array([k in test_set for k in keys], dtype=bool) & ~is_aug
    return train_mask, test_mask


# --------------------------------------------------------------------------- assertions
def _fold_parts(fold: Any) -> tuple[list[str], list[str]]:
    if isinstance(fold, Mapping):
        train = fold.get("train")
        test = fold.get("test", fold.get("val"))
        if train is None or test is None:
            raise SplitError("fold mapping needs 'train' and 'test' (or 'val') keys")
        return [str(x) for x in train], [str(x) for x in test]
    train, test = fold
    return [str(x) for x in train], [str(x) for x in test]


def assert_participant_disjoint(train: Iterable[Any], test: Iterable[Any],
                                source_map: Mapping[str, Any] | None = None) -> None:
    """Raise SplitError when any participant has rows on both sides (protocol 11.1). Ids are reduced to
    participant keys first, so clip1b or an augmented copy of a test participant in `train` is caught."""
    sm = dict(source_map or {})
    tr = {participant_key(x, sm.get(str(x))) for x in train}
    te = {participant_key(x, sm.get(str(x))) for x in test}
    overlap = sorted(tr & te)
    if overlap:
        raise SplitError(f"{len(overlap)} participant(s) in both train and test: {overlap[:10]}")


def assert_augmented_never_in_validation(fold: Any, source_study_ids: Mapping[str, Any] | pd.Series | pd.DataFrame) -> None:
    """Protocol section 8: an augmented copy never appears in a validation fold of its source clip.

    `fold` is a row-level (train_ids, test_ids) pair or mapping; `source_study_ids` maps each id to its
    source participant (null or equal to itself for originals; a DataFrame with `study_id` and
    `source_study_id` columns is accepted). Raises SplitError when an augmented id is evaluated, or
    when an augmented id is trained on while its source participant is in the evaluation set.
    """
    if isinstance(source_study_ids, pd.DataFrame):
        src_map = dict(zip(source_study_ids["study_id"].astype(str), source_study_ids["source_study_id"].tolist()))
    elif isinstance(source_study_ids, pd.Series):
        src_map = {str(k): v for k, v in source_study_ids.items()}
    else:
        src_map = {str(k): v for k, v in dict(source_study_ids).items()}
    augmented = {k: str(v) for k, v in src_map.items() if not is_null(v) and str(v).strip() not in ("", k)}
    train, test = _fold_parts(fold)
    test_set = set(test)
    in_val = sorted(a for a in augmented if a in test_set)
    if in_val:
        raise SplitError(f"augmented copies inside the validation fold: {in_val[:10]}")
    val_participants = {participant_key(t, src_map.get(t)) for t in test}
    leak = sorted(a for a in train if a in augmented and participant_key(augmented[a]) in val_participants)
    if leak:
        raise SplitError(f"augmented copies trained on while their source is under evaluation: {leak[:10]}")


# --------------------------------------------------------------------------- split files
def split_path(name: str, splits_dir: str | Path | None = None) -> Path:
    return Path(splits_dir) / f"{name}.json" if splits_dir else SPLITS_DIR / f"{name}.json"


def _fold_payload(folds: Sequence[Any]) -> list[dict]:
    out = []
    for f in folds:
        if isinstance(f, Mapping) and "inner" in f:
            out.append({"outer": int(f.get("outer", len(out))), "train": list(map(str, f["train"])),
                        "test": list(map(str, f["test"])),
                        "inner": [{"train": list(map(str, i["train"])), "val": list(map(str, i["val"]))} for i in f["inner"]]})
        else:
            tr, te = _fold_parts(f)
            out.append({"train": tr, "test": te})
    return out


def write_split(name: str, folds: Sequence[Any], seed: int, ids: Iterable[Any],
                splits_dir: str | Path | None = None, kind: str = "grouped_kfold", extra: Mapping | None = None) -> Path:
    """Write data/splits/<name>.json: seed, sha256 of the sorted participant ids, fold membership."""
    id_list = sorted({str(x) for x in ids})
    payload = {
        "name": name, "kind": kind, "seed": int(seed), "n_splits": len(folds), "n_ids": len(id_list),
        "ids_sha256": ids_sha256(id_list), "ids": id_list,
        "created_utc": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "folds": _fold_payload(folds),
    }
    if extra:
        payload["extra"] = dict(extra)
    path = split_path(name, splits_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    return path


def read_split(name_or_path: str | Path, splits_dir: str | Path | None = None,
               verify_ids: Iterable[Any] | None = None) -> dict:
    """Read a split file and check its sha256 against the ids it lists and, if given, against `verify_ids`.
    Folds come back as (train, test) tuples under "folds"; nested files keep their dicts."""
    p = Path(name_or_path)
    if p.suffix != ".json" or not p.exists():
        p = split_path(str(name_or_path), splits_dir)
    data = json.loads(p.read_text(encoding="utf-8"))
    stored = data.get("ids_sha256")
    listed = data.get("ids")
    if listed is None:
        listed = sorted({x for f in data["folds"] for x in list(f["train"]) + list(f["test"])})
    if ids_sha256(listed) != stored:
        raise SplitError(f"{p}: id list hash does not match ids_sha256")
    if verify_ids is not None and ids_sha256(verify_ids) != stored:
        raise SplitError(f"{p}: split was made for a different id list (sha256 mismatch)")
    folds = data["folds"]
    if folds and "inner" not in folds[0]:
        data["folds"] = [(list(f["train"]), list(f["test"])) for f in folds]
    data["path"] = str(p)
    return data


def assert_folds_partition(folds: Sequence[Any], ids: Iterable[Any] | None = None) -> None:
    """Every participant in exactly one test fold, none in both sides of any fold, all covered."""
    counts: dict[str, int] = {}
    for f in folds:
        tr, te = _fold_parts(f)
        assert_participant_disjoint(tr, te)
        for t in te:
            counts[t] = counts.get(t, 0) + 1
    multi = sorted(k for k, n in counts.items() if n > 1)
    if multi:
        raise SplitError(f"participants in more than one test fold: {multi[:10]}")
    if ids is not None:
        missing = sorted({participant_key(x) for x in ids} - set(counts))
        if missing:
            raise SplitError(f"participants never tested: {missing[:10]}")
