"""CRF / clinician sampling and the latent BP model (palmppg.synth.crf_synth)."""
import numpy as np

from palmppg.core.config import rng
from palmppg.core.crf import DEPT_TAGS, derive, validate_crf
from palmppg.synth import crf_synth as cs


def sample(cfg, n, seed=11):
    return [cs.sample_crf(f"SWHT-PP-003-{i + 1:04d}", rng(seed, f"p{i}"), cfg) for i in range(n)]


def test_every_crf_and_clinician_is_usable(cfg):
    rows = sample(cfg, 150)
    classes = set(cfg.get("ecg.rhythm_classes"))
    for crf, clin, lat in rows:
        assert validate_crf(crf) == []
        d = derive(crf, cfg.section("crf"))
        assert d["bp_target_sbp"] is not None and d["bmi"] > 10
        assert crf["dept"] in DEPT_TAGS and crf["stream"] == "pilot"
        assert clin["rhythm"] in classes and clin["rhythm"] == lat["rhythm"]
        assert abs(clin["ecg_hr"] - lat["hr_bpm"]) < 3.5
        assert set(clin) == {"rhythm", "ecg_hr", "lead12_obtained", "adverse_event", "reader_id", "read_date"}
        if crf["pregnant"]:
            assert crf["sex"] == "F"
        if "arrhythmia" not in crf["flags"]:
            assert crf["arr_type"] is None
        for k in ("bp1", "bp2", "bp3"):
            assert set(crf[k]) == {"sbp", "dbp", "hr", "wall_ts"}


def test_population_priors(cfg):
    rows = sample(cfg, 400, seed=5)
    mst = np.array([c["mst_band"] for c, _, _ in rows])
    assert ((mst >= 4) & (mst <= 10)).mean() > 0.9 and (mst <= 3).any()
    hba1c = np.mean([c["hba1c"] is not None for c, _, _ in rows])
    hb = np.mean([c["hb_gdl"] is not None for c, _, _ in rows])
    assert 0.3 < hba1c < 0.6 and 0.3 < hb < 0.6
    rhythms = [cl["rhythm"] for _, cl, _ in rows]
    af = np.mean([r == "af" for r in rhythms])
    hard = np.mean([r in cfg.get("ecg.hard_non_af") for r in rhythms])
    assert 0.04 < af < 0.14 and 0.015 < hard < 0.11
    assert np.mean([r == "sinus" for r in rhythms]) > 0.75
    ages = np.array([c["age"] for c, _, _ in rows])
    assert ages.min() >= 18 and ages.max() <= 85 and 40 < ages.mean() < 55
    outlier = np.mean([derive(c, cfg.section("crf"))["bp_target_rule_sbp"] == "mean_bp2_bp3_bp1_outlier" for c, _, _ in rows])
    assert 0.02 < outlier < 0.25
    assert len({c["dept"] for c, _, _ in rows}) >= 8


def test_latent_bp_relationship_is_recoverable(cfg):
    rows = sample(cfg, 400, seed=9)
    pat = np.array([lat["pat_s"] for _, _, lat in rows])
    sbp = np.array([lat["sbp_true"] for _, _, lat in rows])
    age = np.array([lat["age"] for _, _, lat in rows])
    bmi = np.array([lat["bmi"] for _, _, lat in rows])
    htn = np.array([lat["htn"] for _, _, lat in rows], float)
    X = np.c_[np.ones_like(pat), pat, age, bmi, htn]
    beta = np.linalg.lstsq(X, sbp, rcond=None)[0]
    m = cs.BP_MODEL["sbp"]
    assert beta[1] < 0 and abs(beta[1] - m["pat_s"]) < 0.4 * abs(m["pat_s"])
    assert abs(beta[2] - m["age"]) < 0.3 and abs(beta[4] - m["htn"]) < 6
    cuff = np.array([(c["bp2"]["sbp"] + c["bp3"]["sbp"]) / 2 for c, _, _ in rows])
    assert abs(np.mean(cuff - sbp)) < 1.5 and np.std(cuff - sbp) < 5
    assert all(lat["dbp_true"] < lat["sbp_true"] - 20 for _, _, lat in rows)


def test_rhythm_overrides_and_anaemia_lower_ac(cfg):
    crf, clin, lat = cs.sample_crf("SWHT-PP-003-0001", rng(1, "x"), cfg, stream="development", overrides={"rhythm": "af", "mst_band": 9})
    assert clin["rhythm"] == "af" and crf["mst_band"] == 9 and crf["stream"] == "development"
    assert lat["hrv_sd_s"] > 0.1 and lat["resp_amp"] == 0.0 and lat["melanin"] > 0.4
    sinus = cs.sample_crf("SWHT-PP-003-0002", rng(1, "y"), cfg, overrides={"rhythm": "sinus"})[2]
    assert sinus["hrv_sd_s"] < 0.06
