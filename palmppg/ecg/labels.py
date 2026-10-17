"""Clinician ECG read (`clinician.json`): the rhythm label for the rhythm endpoints (protocol 6.4, E7).

The clinician label is ground truth; the Kardia app label is a covariate only (handled in `run`).
Rhythm text is normalised onto `ecg.rhythm_classes`; text that maps to none of them becomes "other"
with `rhythm_unmapped=True` so the mapping is auditable. `ecg.hard_non_af` defines the hard non-AF
comparison group.
"""
from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from pathlib import Path

from palmppg.core.config import Config

# Clinician free text (lower case, punctuation stripped) -> class in ecg.rhythm_classes.
SYNONYMS: dict[str, tuple[str, ...]] = {
    "sinus": ("sinus", "sinus rhythm", "normal sinus rhythm", "nsr", "sr", "normal", "regular sinus",
              "sinus bradycardia", "sinus tachycardia", "sinus arrhythmia"),
    "af": ("af", "afib", "a fib", "atrial fibrillation", "fibrillation", "possible atrial fibrillation"),
    "aflutter": ("aflutter", "afl", "atrial flutter", "flutter", "a flutter"),
    "svt": ("svt", "psvt", "supraventricular tachycardia", "avnrt", "avrt", "narrow complex tachycardia"),
    "frequent_ectopy": ("frequent ectopy", "ectopy", "frequent pvcs", "frequent pacs", "pvcs", "pacs",
                        "premature beats", "bigeminy", "trigeminy", "frequent ventricular ectopy",
                        "frequent atrial ectopy"),
    "paced": ("paced", "paced rhythm", "pacemaker", "pacemaker rhythm", "pacing", "ventricular paced"),
    "other": ("other",),
    "unreadable": ("unreadable", "uninterpretable", "noise", "too noisy", "no analysis", "artifact only",
                   "artefact only"),
}
# Phrases safe to recognise inside a longer free-text read ("AF with slow ventricular response"). Bare
# words such as "pacemaker" or "fibrillation" are deliberately absent: "wandering atrial pacemaker" is not
# a paced rhythm, "ventricular fibrillation" is not AF.
STRONG_KEYWORDS: dict[str, tuple[str, ...]] = {
    "sinus": ("sinus rhythm", "normal sinus rhythm", "sinus bradycardia", "sinus tachycardia", "sinus arrhythmia", "nsr"),
    "af": ("atrial fibrillation", "afib", "a fib", "af"),
    "aflutter": ("atrial flutter", "flutter", "afl"),
    "svt": ("supraventricular tachycardia", "svt", "psvt", "avnrt", "avrt"),
    "frequent_ectopy": ("frequent ectopy", "frequent pvcs", "frequent pacs", "bigeminy", "trigeminy",
                        "frequent ventricular ectopy", "frequent atrial ectopy"),
    "paced": ("paced rhythm", "ventricular paced", "paced"),
}
TRUE_WORDS = ("true", "yes", "y", "1", "obtained", "done")
FALSE_WORDS = ("false", "no", "n", "0", "not obtained", "none", "not done")
NULL_WORDS = ("", "none", "null", "nil", "na", "n/a", "nan")


def _cfg(cfg: Config | None) -> Config:
    if cfg is None:
        from palmppg.core.config import load_pipeline_config

        cfg = load_pipeline_config()
    return cfg


def rhythm_classes(cfg: Config | None = None) -> list[str]:
    """The rhythm label vocabulary, `ecg.rhythm_classes` from the pipeline config (protocol 6.4, E7)."""
    return [str(c) for c in _cfg(cfg).get("ecg.rhythm_classes")]


def _norm_text(s: str) -> str:
    s = str(s).strip().lower().replace("_", " ").replace("-", " ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def normalise_rhythm(text, cfg: Config | None = None) -> tuple[str | None, bool]:
    """Map clinician rhythm text onto `ecg.rhythm_classes`. Returns (class | None, unmapped).

    None (with unmapped=False) when the text is empty; "other" with unmapped=True when the text matches
    neither a class name nor a known synonym.
    """
    classes = rhythm_classes(cfg)
    if text is None:
        return None, False
    raw = _norm_text(text)
    if raw in NULL_WORDS:
        return None, False
    by_class = {_norm_text(c): c for c in classes}
    if raw in by_class:
        return by_class[raw], False
    for cls, words in SYNONYMS.items():
        if cls in classes and raw in words:
            return cls, False
    # a longer free-text read that contains exactly one class phrase ("AF with slow ventricular response")
    hits = []
    for cls, words in STRONG_KEYWORDS.items():
        if cls not in classes:
            continue
        for w in sorted(words, key=len, reverse=True):
            if re.search(rf"\b{re.escape(w)}\b", raw):
                hits.append(cls)
                break
    if len(set(hits)) == 1:
        return hits[0], False
    return ("other" if "other" in classes else classes[-1]), True


def _to_bool(v) -> bool | None:
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    s = _norm_text(v)
    if s in TRUE_WORDS:
        return True
    if s in FALSE_WORDS:
        return False
    return None


def _to_float(v) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def is_hard_non_af(rhythm: str | None, cfg: Config | None = None) -> bool:
    """True when the rhythm class is one of `ecg.hard_non_af` (the hard non-AF comparison group, E7)."""
    if rhythm is None:
        return False
    return str(rhythm) in {str(c) for c in _cfg(cfg).get("ecg.hard_non_af")}


def parse_clinician(record: Mapping, cfg: Config | None = None) -> dict:
    """Normalise a clinician record (CONTRACTS 3.6 `clinician.json`) -> dict with
    rhythm, rhythm_raw, rhythm_unmapped, ecg_hr (bpm | None), lead12_obtained (bool | None),
    adverse_event (str | None), reader_id, read_date, is_af, is_sinus, is_hard_non_af, problems."""
    c = _cfg(cfg)
    problems: list[str] = []
    raw = record.get("rhythm")
    rhythm, unmapped = normalise_rhythm(raw, c)
    if rhythm is None:
        problems.append("rhythm missing")
    elif unmapped:
        problems.append(f"rhythm {raw!r} not in ecg.rhythm_classes; recorded as 'other'")
    hr = _to_float(record.get("ecg_hr"))
    if hr is None:
        problems.append("ecg_hr missing")
    elif not (20.0 <= hr <= 300.0):
        problems.append(f"ecg_hr {hr} outside a plausible range")
    lead12 = _to_bool(record.get("lead12_obtained"))
    if lead12 is None:
        problems.append("lead12_obtained missing")
    adverse = record.get("adverse_event")
    if adverse is not None and _norm_text(adverse) in NULL_WORDS:
        adverse = None
    return {
        "rhythm": rhythm, "rhythm_raw": None if raw is None else str(raw), "rhythm_unmapped": bool(unmapped),
        "ecg_hr": hr, "lead12_obtained": lead12, "adverse_event": None if adverse is None else str(adverse),
        "reader_id": record.get("reader_id"), "read_date": record.get("read_date"),
        "is_af": rhythm == "af", "is_sinus": rhythm == "sinus", "is_hard_non_af": is_hard_non_af(rhythm, c),
        "problems": problems,
    }


def load_clinician(path: str | Path, cfg: Config | None = None) -> dict:
    """Read `clinician.json` and normalise it (see `parse_clinician`). Raises FileNotFoundError when absent."""
    with open(path, "r", encoding="utf-8") as fh:
        record = json.load(fh)
    if not isinstance(record, Mapping):
        raise TypeError(f"{path}: clinician.json must hold an object")
    return parse_clinician(record, cfg)
