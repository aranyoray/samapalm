"""time_of_day cut at 13:00 local, lux band edges, BP tertile cut points from the development set only."""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

import numpy as np
import pytest

from palmppg.features.covariates import (
    apply_tertiles,
    bp_tertile,
    bp_tertile_by_stream,
    covariate_settings,
    derived_strata,
    lux_band,
    lux_band_labels,
    tertile_cuts,
    time_of_day,
)

IST = ZoneInfo("Asia/Kolkata")


def _ns(h, m=0, s=0):
    return int(dt.datetime(2026, 10, 17, h, m, s, tzinfo=IST).timestamp() * 1e9)


def test_time_of_day_cut_at_13_local():
    assert time_of_day(_ns(12, 59, 59)) == "morning"
    assert time_of_day(_ns(13, 0, 0)) == "afternoon"
    assert time_of_day(_ns(0, 0, 0)) == "morning"
    assert time_of_day(_ns(23, 59, 59)) == "afternoon"
    # ISO strings with offset, UTC and naive (taken as local)
    assert time_of_day("2026-10-17T12:59:00+05:30") == "morning"
    assert time_of_day("2026-10-17T07:29:59Z") == "morning"        # 12:59:59 IST
    assert time_of_day("2026-10-17T07:30:00Z") == "afternoon"      # 13:00:00 IST exactly
    assert time_of_day("2026-10-17T07:30:00+00:00") == "afternoon"
    assert time_of_day("2026-10-17T13:00:00") == "afternoon"
    assert time_of_day(dt.datetime(2026, 10, 17, 10, 0, tzinfo=dt.UTC)) == "afternoon"  # 15:30 IST
    # another zone and another cut hour
    assert time_of_day(_ns(13, 0, 0), tz="UTC") == "morning"  # 07:30 UTC
    assert time_of_day(_ns(12, 0, 0), cut_hour=12) == "afternoon"
    # epoch seconds are accepted too (magnitude below 1e12)
    assert time_of_day(_ns(9) / 1e9) == "morning"
    assert time_of_day(None) is None and time_of_day(float("nan")) is None and time_of_day("not a date") is None


def test_lux_band_edges():
    assert [lux_band(x) for x in (0, 199.99, 200, 300, 400, 400.01, 10_000)] == [
        "<200", "<200", "200-400", "200-400", "200-400", ">400", ">400"]
    assert lux_band(None) is None and lux_band(float("nan")) is None and lux_band("dark") is None
    assert lux_band("250") == "200-400"
    assert lux_band_labels((100, 300)) == ("<100", "100-300", ">300")
    assert lux_band(150, edges=(100, 300)) == "100-300"


def test_tertile_cuts_from_development_only():
    dev = list(range(1, 10))  # 1..9 -> cuts at 3.667 and 6.333
    c1, c2 = tertile_cuts(dev)
    assert c1 == pytest.approx(np.percentile(dev, 100 / 3)) == pytest.approx(3.6667, abs=1e-3)
    assert c2 == pytest.approx(6.3333, abs=1e-3)
    # values exactly on a cut point belong to the lower tertile (v <= cut)
    labels, cuts = bp_tertile([2, c1, c1 + 1e-9, c2, c2 + 1e-9, 9, None, float("nan")], fit_values=dev)
    assert labels == ["T1", "T1", "T2", "T2", "T3", "T3", None, None]
    assert cuts == (c1, c2)
    # explicit cuts win and are returned unchanged
    labels2, cuts2 = bp_tertile([120, 130, 140], cuts=(125.0, 135.0))
    assert labels2 == ["T1", "T2", "T3"] and cuts2 == (125.0, 135.0)
    # the pilot rows do not move the cut points
    pilot = [100, 101, 102, 103, 104]
    lab_mixed, cuts_mixed, info = bp_tertile_by_stream(dev + pilot, ["development"] * 9 + ["pilot"] * 5)
    assert cuts_mixed == (c1, c2) and info == {"fit_stream": "development", "n_fit": 9}
    assert lab_mixed[-5:] == ["T3"] * 5
    assert apply_tertiles([1, 5, 9], (c1, c2), labels=("low", "mid", "high")) == ["low", "mid", "high"]
    with pytest.raises(ValueError):
        tertile_cuts([1, 2])


def test_settings_and_derived_strata(cfg):
    s = covariate_settings(cfg)
    assert s["cut_hour"] == 13 and s["lux_edges"] == (200.0, 400.0) and s["tz"] == "Asia/Kolkata"
    over = cfg.with_overrides({"features": {"time_of_day_cut_hour": 12, "lux_band_edges": [100, 300]}})
    s2 = covariate_settings(over)
    assert s2["cut_hour"] == 12 and s2["lux_edges"] == (100.0, 300.0)
    assert derived_strata(_ns(12, 30), 250.0, s) == {"time_of_day": "morning", "lux_band": "200-400"}
    assert derived_strata(_ns(12, 30), 250.0, s2) == {"time_of_day": "afternoon", "lux_band": "100-300"}
    assert derived_strata(None, None) == {"time_of_day": None, "lux_band": None}
