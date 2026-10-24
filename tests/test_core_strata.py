"""Recruitment targets and priority (design section 3): hand-computed cases, validation, fixtures, and that every
target key is one the CRF engine's strata derivations can produce."""
import copy
import json
from pathlib import Path

import pytest

from palmppg.core.strata import TargetsError, cell_table, load_targets, most_needed, priority, validate_targets

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "configs" / "crf_schema.json").read_text())
FIXTURES = json.loads((ROOT / "configs" / "crf_fixtures" / "strata_golden.json").read_text())

SMALL = {"version": "t", "levels": {"high": 0.5, "medium": 0.2}, "groups": [
    {"id": "sex", "label": "Sex", "weight": 1.0, "cells": [{"key": "sex:F", "label": "Female", "target": 100},
                                                           {"key": "sex:M", "label": "Male", "target": 100}]},
    {"id": "x", "label": "Cross", "weight": 0.5, "cells": [{"key": "sex_mst:F:8", "label": "F8", "target": 10},
                                                           {"key": "sex_mst:F:9", "label": "F9", "target": 10}]},
    {"id": "scan", "label": "Scan", "weight": 0.0, "cells": [{"key": "rhythm:af", "label": "AF", "target": 10}]},
]}


def test_no_matching_cell_is_none():
    assert priority(["mstgrp:dark", "dm:no_known"], {}, SMALL) == {"score": 0.0, "level": "none", "reasons": []}
    assert priority([], {"sex:F": 3}, SMALL)["level"] == "none"


def test_all_full_is_met_even_when_over_target():
    p = priority(["sex:F", "sex_mst:F:8"], {"sex:F": 100, "sex_mst:F:8": 12}, SMALL)
    assert p["level"] == "met" and p["score"] == 0.0
    assert [r["key"] for r in p["reasons"]] == ["sex:F", "sex_mst:F:8"]   # tie at 0 broken by key


def test_weighting_and_levels():
    # sex:F 80/100 -> deficit 0.2, contribution 0.2; sex_mst:F:8 0/10 -> 1.0 * weight 0.5 = 0.5 -> high
    p = priority(["sex:F", "sex_mst:F:8"], {"sex:F": 80}, SMALL)
    assert p["score"] == 0.5 and p["level"] == "high"
    assert [(r["key"], r["contribution"]) for r in p["reasons"]] == [("sex_mst:F:8", 0.5), ("sex:F", 0.2)]
    # sex_mst:F:8 6/10 -> 0.4 * 0.5 = 0.2 = medium threshold; sex:F 90/100 -> 0.1
    p = priority(["sex:F", "sex_mst:F:8"], {"sex:F": 90, "sex_mst:F:8": 6}, SMALL)
    assert p["score"] == 0.2 and p["level"] == "medium"   # 0.5 * (1 - 0.6) is exactly 0.2 in binary: >= holds
    p = priority(["sex:F"], {"sex:F": 80}, SMALL)            # 1 - 0.8 = 0.19999999999999996 < 0.2
    assert p["level"] == "low"
    p = priority(["sex:M"], {"sex:M": 95}, SMALL)
    assert p["level"] == "low" and p["score"] == pytest.approx(0.05)
    # a weight-0 cell matches (not "none") but never raises the score
    p = priority(["rhythm:af"], {}, SMALL)
    assert p == {"score": 0.0, "level": "low", "reasons": [{"key": "rhythm:af", "label": "AF", "group": "scan", "n": 0,
                                                             "target": 10, "contribution": 0.0}]}


def test_tie_ordering_by_key_missing_counts_and_reason_cap():
    p = priority(["sex_mst:F:9", "sex_mst:F:8", "sex:F", "sex:M"], {"sex:F": 50, "sex:M": 50}, SMALL)
    # sex:F and sex:M 0.5; F8 and F9 0.5 * 1.0 = 0.5: four-way tie, ordered by key, capped at 3
    assert [r["key"] for r in p["reasons"]] == ["sex:F", "sex:M", "sex_mst:F:8"]
    assert all(r["n"] == 0 for r in p["reasons"] if r["key"].startswith("sex_mst"))
    assert p["reasons"][0] == {"key": "sex:F", "label": "Female", "group": "sex", "n": 50, "target": 100, "contribution": 0.5}


def test_contribution_rounding():
    t = copy.deepcopy(SMALL)
    t["groups"][0]["cells"][0]["target"] = 3
    p = priority(["sex:F"], {"sex:F": 1}, t)                 # 1 - 1/3 = 0.6666...
    assert p["reasons"][0]["contribution"] == 0.667 and p["score"] == pytest.approx(2 / 3)
    p = priority(["sex:F"], {"sex:F": 2}, t)                 # 1/3 -> 0.333
    assert p["reasons"][0]["contribution"] == 0.333 and p["level"] == "medium"


def test_cell_table_and_most_needed():
    rows = cell_table({"sex:F": 150, "sex_mst:F:9": 5}, SMALL)
    assert [(r["key"], r["n"], r["fill"]) for r in rows] == [("sex:F", 150, 1.0), ("sex:M", 0, 0.0), ("sex_mst:F:8", 0, 0.0),
                                                             ("sex_mst:F:9", 5, 0.5), ("rhythm:af", 0, 0.0)]
    assert rows[0]["group"] == "sex" and rows[0]["target"] == 100 and rows[0]["label"] == "Female"
    mn = most_needed({"sex:F": 150, "sex_mst:F:9": 5}, SMALL, k=5)
    # sex:M 1.0, F8 0.5, F9 0.25; sex:F full and rhythm:af weight 0 are left out
    assert [(r["key"], r["contribution"]) for r in mn] == [("sex:M", 1.0), ("sex_mst:F:8", 0.5), ("sex_mst:F:9", 0.25)]
    assert [r["key"] for r in most_needed({}, SMALL, k=2)] == ["sex:F", "sex:M"]


def test_validation_errors_are_clear(tmp_path):
    bad = copy.deepcopy(SMALL)
    bad["groups"][1]["cells"][1]["key"] = "sex:F"
    bad["groups"][1]["weight"] = 1.5
    bad["groups"][0]["cells"][1]["target"] = 0
    bad["groups"][2]["cells"][0]["target"] = 2.5
    probs = validate_targets(bad)
    assert "group x: duplicate cell key sex:F" in probs
    assert "group x: weight must be a number in [0, 1], got 1.5" in probs
    assert "group sex: cell sex:M: target must be a whole number > 0, got 0" in probs
    assert "group scan: cell rhythm:af: target must be a whole number > 0, got 2.5" in probs
    assert validate_targets({"levels": {"high": 0.1, "medium": 0.4}, "groups": []}) == \
        ["levels must satisfy 0 <= medium <= high <= 1", "groups must be a non-empty list"]
    p = tmp_path / "t.json"
    p.write_text(json.dumps(bad))
    with pytest.raises(TargetsError, match="duplicate cell key sex:F"):
        load_targets(p)


def test_real_targets_file_defaults():
    t = load_targets()
    assert validate_targets(t) == [] and "confirm" in t["note"]
    cells = {c["key"]: (g["id"], g["weight"], c["target"]) for g in t["groups"] for c in g["cells"]}
    assert cells["sex:F"] == ("sex", 1.0, 1000) and cells["mst:10"] == ("mst", 1.0, 200)
    assert cells["haem:thal_disease"] == ("condition", 1.0, 60) and cells["sex_mst:M:4"] == ("sex_mst", 0.7, 100)
    assert cells["cond_mstgrp:af:dark"] == ("condition_dark", 0.7, 120) and cells["rhythm:nsr"] == ("scan", 0.0, 500)
    assert len(cells) == 2 + 7 + 10 + 14 + 5 + 2
    assert t["levels"] == {"high": 0.5, "medium": 0.2}


def _values(name):
    return [c["value"] for c in SCHEMA["choices"].get(name, [])]


def test_every_target_key_can_be_produced_by_the_engine():
    if not _values("conditions") or not _values("kardia"):
        pytest.skip("configs/crf_schema.json has no v2 conditions/kardia choice lists yet")
    sexes, conds, kardia = _values("sex"), _values("conditions"), _values("kardia")
    bands = [str(b) for b in range(1, 11)]
    groups = ["light", "medium", "dark"]
    haem = ["thal_disease", "thal_trait", "thal_unspecified", "ida", "anaemia_other", "non_anaemic"]
    dm = ["documented_hba1c", "documented", "hba1c_only", "no_known"]
    producible = {"preg:yes", "scan:done"}
    producible |= {f"sex:{s}" for s in sexes} | {f"mst:{b}" for b in bands} | {f"mstgrp:{g}" for g in groups}
    producible |= {f"cond:{c}" for c in conds} | {f"haem:{h}" for h in haem} | {f"dm:{d}" for d in dm}
    producible |= {f"sex_mst:{s}:{b}" for s in sexes for b in bands}
    producible |= {f"cond_mstgrp:{c}:{g}" for c in conds if c != "none" for g in groups}
    producible |= {f"haem_mstgrp:{h}:{g}" for h in haem for g in groups} | {f"rhythm:{k}" for k in kardia}
    keys = [c["key"] for g in load_targets()["groups"] for c in g["cells"]]
    assert [k for k in keys if k not in producible] == []


def test_engine_strata_hit_the_expected_cells():
    from palmppg.core.crf_schema import CrfEngine, load_schema, parse_ts
    golden = {c["name"]: c for c in json.loads((ROOT / "configs" / "crf_fixtures" / "golden.json").read_text())["cases"]}
    c = golden["strata_order_and_cross_keys"]
    keys = CrfEngine(load_schema(), c["settings"]).evaluate(c["answers"], parse_ts(c["now"])).derived["strata"]
    p = priority(keys, {}, load_targets())
    # empty counts: every matched weight-1 cell has contribution 1.0; ties by key put cond:af first
    assert p["level"] == "high" and p["score"] == 1.0
    assert [r["key"] for r in p["reasons"]] == ["cond:af", "cond:diabetes", "cond:htn"]


@pytest.mark.parametrize("case", FIXTURES["cases"], ids=[c["name"] for c in FIXTURES["cases"]])
def test_fixture_cases_reproduce(case):
    assert priority(case["keys"], case["counts"], load_targets()) == case["expected"]


def test_fixture_tables_reproduce_and_are_current():
    t = load_targets()
    assert FIXTURES["targets_version"] == t["version"] and len(FIXTURES["cases"]) >= 12
    for tab in FIXTURES["tables"]:
        assert cell_table(tab["counts"], t) == tab["cell_table"]
        assert most_needed(tab["counts"], t, tab["k"]) == tab["most_needed"]
