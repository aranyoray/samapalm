"""tools/ecgfounder_public_eval.py: the parts that decide the numbers, checked without torch or data."""
import numpy as np
import pytest

import tools.ecgfounder_public_eval as ev


def _labels(n_per_class=(60, 20, 30, 10)):
    out, k = {}, 0
    for c, n in enumerate(n_per_class):
        for _ in range(n):
            out[f"A{k:05d}"] = c
            k += 1
    return out


def test_split_is_deterministic_stratified_and_disjoint():
    lab = _labels()
    a, b = ev.cinc_split(lab, seed=0), ev.cinc_split(lab, seed=0)
    assert a == b
    assert ev.cinc_split(lab, seed=1) != a
    for s, frac in (("train", 0.70), ("val", 0.15), ("test", 0.15)):
        recs = [r for r, v in a.items() if v == s]
        assert abs(len(recs) / len(lab) - frac) < 0.02
        # every class appears in every split, in roughly its overall share
        for c in range(4):
            share = sum(lab[r] == c for r in recs) / len(recs)
            overall = sum(v == c for v in lab.values()) / len(lab)
            assert abs(share - overall) < 0.05
    assert set(a) == set(lab)


def test_per_strip_mean_and_missing_strips():
    vals = np.array([[0.2], [0.4], [0.9]])
    owner = np.array([0, 0, 2])
    got = ev.per_strip(vals, owner, 4)
    assert got[0, 0] == pytest.approx(0.3) and got[2, 0] == pytest.approx(0.9)
    assert np.isnan(got[1, 0]) and np.isnan(got[3, 0])     # strips with no 10 s window stay NaN


def test_youden_and_binary_summary_on_a_separable_case():
    y = np.array([0, 0, 0, 0, 1, 1, 1])
    s = np.array([0.1, 0.2, 0.3, 0.35, 0.6, 0.7, 0.9])
    thr = ev.youden_threshold(y, s)
    assert 0.35 < thr <= 0.6
    r = ev.binary_summary(y, s, thr, n_boot=50)
    assert r["auroc"] == pytest.approx(1.0)
    assert r["sensitivity"] == 1.0 and r["specificity"] == 1.0
    assert r["tp_fn_tn_fp"] == [3, 0, 4, 0]
    assert r["n"] == 7 and r["positives"] == 3


def test_challenge_score_is_mean_f1_of_normal_af_other_only():
    y = np.array([0, 1, 2, 3])
    prob = np.eye(4)[[0, 1, 2, 0]]                      # the noisy strip is called normal
    r = ev.challenge_summary(y, prob)
    assert r["F1"]["~"] == 0.0
    assert r["challenge_F1_NAO"] == pytest.approx(np.mean([r["F1"]["N"], r["F1"]["A"], r["F1"]["O"]]))
    assert r["confusion_rows_true_cols_pred"][3][0] == 1
