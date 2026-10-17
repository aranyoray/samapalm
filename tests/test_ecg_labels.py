"""clinician.json loading: rhythm normalisation onto ecg.rhythm_classes, hard non-AF group, field coercion."""
from __future__ import annotations

import json

import pytest

from palmppg.ecg.labels import (
    is_hard_non_af,
    load_clinician,
    normalise_rhythm,
    parse_clinician,
    rhythm_classes,
)


def _write(tmp_path, record, name="clinician.json"):
    p = tmp_path / name
    p.write_text(json.dumps(record), encoding="utf-8")
    return p


def test_rhythm_synonyms_map_onto_config_classes(cfg):
    classes = rhythm_classes(cfg)
    assert classes == list(cfg.get("ecg.rhythm_classes"))
    cases = {"Atrial Fibrillation": "af", "AF": "af", "a-fib": "af", "Normal sinus rhythm": "sinus", "NSR": "sinus",
             "sinus tachycardia": "sinus", "Atrial flutter": "aflutter", "SVT": "svt", "frequent PVCs": "frequent_ectopy",
             "Paced rhythm": "paced", "unreadable": "unreadable", "AF with slow ventricular response": "af",
             "frequent_ectopy": "frequent_ectopy", "Other": "other"}
    for text, cls in cases.items():
        got, unmapped = normalise_rhythm(text, cfg)
        assert got == cls and unmapped is False, text
        assert got in classes
    assert normalise_rhythm(None, cfg) == (None, False) and normalise_rhythm("  ", cfg) == (None, False)
    got, unmapped = normalise_rhythm("junctional escape", cfg)
    assert got == "other" and unmapped is True
    got, unmapped = normalise_rhythm("AF versus flutter", cfg)          # two classes named: ambiguous
    assert got == "other" and unmapped is True


def test_hard_non_af_group(cfg):
    for cls in cfg.get("ecg.hard_non_af"):
        assert is_hard_non_af(cls, cfg) is True
    for cls in ("af", "sinus", "other", "unreadable", None):
        assert is_hard_non_af(cls, cfg) is False


def test_load_clinician_full_record(tmp_path, cfg):
    p = _write(tmp_path, {"rhythm": "Atrial flutter", "ecg_hr": "88", "lead12_obtained": "yes", "adverse_event": "",
                          "reader_id": "R1", "read_date": "2026-10-17"})
    c = load_clinician(p, cfg)
    assert c["rhythm"] == "aflutter" and c["rhythm_raw"] == "Atrial flutter" and c["rhythm_unmapped"] is False
    assert c["ecg_hr"] == 88.0 and c["lead12_obtained"] is True and c["adverse_event"] is None
    assert c["is_af"] is False and c["is_sinus"] is False and c["is_hard_non_af"] is True
    assert c["reader_id"] == "R1" and c["read_date"] == "2026-10-17" and c["problems"] == []


def test_unknown_rhythm_flagged_and_missing_fields_listed(tmp_path, cfg):
    p = _write(tmp_path, {"rhythm": "wandering atrial pacemaker"})
    c = load_clinician(p, cfg)
    assert c["rhythm"] == "other" and c["rhythm_unmapped"] is True
    assert any("not in ecg.rhythm_classes" in m for m in c["problems"])
    assert "ecg_hr missing" in c["problems"] and "lead12_obtained missing" in c["problems"]
    assert c["ecg_hr"] is None and c["lead12_obtained"] is None
    d = parse_clinician({"rhythm": "sinus", "ecg_hr": 400, "lead12_obtained": 0, "adverse_event": "syncope"}, cfg)
    assert d["lead12_obtained"] is False and d["adverse_event"] == "syncope" and d["is_sinus"] is True
    assert any("plausible range" in m for m in d["problems"])
    e = parse_clinician({}, cfg)
    assert e["rhythm"] is None and "rhythm missing" in e["problems"]
    f = parse_clinician({"rhythm": "af", "ecg_hr": float("nan"), "lead12_obtained": True}, cfg)
    assert f["ecg_hr"] is None and f["is_af"] is True


def test_missing_or_malformed_file(tmp_path, cfg):
    with pytest.raises(FileNotFoundError):
        load_clinician(tmp_path / "none.json", cfg)
    (tmp_path / "list.json").write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(TypeError):
        load_clinician(tmp_path / "list.json", cfg)
