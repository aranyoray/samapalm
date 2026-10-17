"""Every plot function returns a Figure and writes PNG and SVG on a headless backend."""
from __future__ import annotations

import matplotlib
import numpy as np
import pandas as pd
import pytest

from palmppg.core.config import rng
from palmppg.eval import plots
from palmppg.eval.calibration import decision_curve, reliability_table


def _check(fig, base):
    assert fig.__class__.__name__ == "Figure"
    assert base.with_suffix(".png").stat().st_size > 0 and base.with_suffix(".svg").stat().st_size > 0
    matplotlib.pyplot.close(fig)


def test_backend_is_headless():
    assert matplotlib.get_backend().lower() == "agg"


def test_bland_altman(tmp_path):
    g = rng(1, "plots")
    y = g.normal(130, 15, 80)
    fig = plots.bland_altman(None, y, y + g.normal(1, 8, 80), path=tmp_path / "ba")
    _check(fig, tmp_path / "ba")
    fig2, ax = matplotlib.pyplot.subplots()
    assert plots.bland_altman(ax, y, y + 1.0) is fig2
    matplotlib.pyplot.close(fig2)


def test_degradation_strata_calibration_decision_and_transfer(tmp_path):
    g = rng(2, "plots")
    deg = pd.DataFrame([{"camera": cam, "method": m, "severity": s, "hr_mae": s * (1 + i) + g.normal(0, 0.1)}
                        for cam in ("pi", "phone") for i, m in enumerate(("POS", "CHROM")) for s in (0, 1, 2, 3)])
    _check(plots.degradation_curves(deg, "hr_mae", path=tmp_path / "deg"), tmp_path / "deg")
    strata = pd.DataFrame({"metric": "error_sd", "stratum": ["overall", "sex", "sex", "mst_band"],
                           "level": ["all", "F", "M", "other (pooled, n<20)"], "n": [100, 50, 50, 10],
                           "n_participants": [100, 50, 50, 10], "point": [8.0, 7.5, 8.5, 9.0],
                           "lo": [7.0, 6.5, 7.5, np.nan], "hi": [9.0, 8.5, 9.5, np.nan],
                           "pooled": [False, False, False, True], "note": ""})
    _check(plots.strata_forest(strata, path=tmp_path / "forest"), tmp_path / "forest")
    p = g.uniform(size=500)
    y = (g.uniform(size=500) < p).astype(int)
    _check(plots.calibration_plot(reliability_table(y, p, 10), path=tmp_path / "cal"), tmp_path / "cal")
    _check(plots.decision_curve_plot(decision_curve(y, p, np.linspace(0.05, 0.95, 19)), path=tmp_path / "dc"), tmp_path / "dc")
    transfer = pd.DataFrame({"stratum": ["overall", "mst_group"], "level": ["all", "4-5"], "pi_to_pi": [7.0, 6.5],
                             "pi_to_phone": [9.0, 8.0], "phone_to_phone": [8.0, 7.5], "pi_aug_to_phone": [8.5, 7.8]})
    _check(plots.pi_vs_phone_bars(transfer, path=tmp_path / "tr"), tmp_path / "tr")
    assert plots.save_figure(matplotlib.pyplot.figure(), None) is None
    matplotlib.pyplot.close("all")


@pytest.mark.parametrize("n", [0, 1])
def test_bland_altman_handles_tiny_inputs(tmp_path, n):
    fig = plots.bland_altman(None, np.arange(n, dtype=float), np.arange(n, dtype=float), path=tmp_path / f"ba{n}")
    _check(fig, tmp_path / f"ba{n}")
