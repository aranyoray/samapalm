"""build_clip_features: every column registered, values equal the hand-written ground truth, booleans kept,
lists flattened, requires_ecg columns absent from the product_candidate selection and present for science."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from palmppg.core.crf import covariate_columns, derive
from palmppg.core.tracks import REGISTRY, TrackViolation
from palmppg.features._common import coerce_scalar, flatten, harmonise_dtypes
from palmppg.features.store import (
    DERIVED_STRATA,
    build_clip_features,
    feature_columns,
    id_columns,
    register_features,
)
from tests.test_features_fixtures import (
    BEAT_FEATURES,
    CLINICIAN,
    ECG_FEATURES,
    PAT,
    PULSE_SQI,
    QC_PI,
    SID,
    STATIC_COLOUR,
    base_crf,
    make_clip_artefacts,
)


@pytest.fixture
def clip_dir(tmp_path):
    d = tmp_path / "work" / SID / "clip1"
    make_clip_artefacts(d, "pi")
    make_clip_artefacts(d, "phone", with_embedding=False)
    return d


@pytest.fixture
def crf_derived(cfg):
    return derive(base_crf(), cfg.section("crf"))


def _row(cfg, clip_dir, crf_derived, camera="pi", **kw):
    df = build_clip_features(SID, "clip1", camera, clip_dir, crf_derived, CLINICIAN, cfg,
                             clip_meta={"start_wall_ns": "2026-10-17T10:30:00+05:30", "lux": 250.0}, **kw)
    assert len(df) == 1
    return df


def test_register_features_is_idempotent(cfg):
    n1 = register_features(cfg)
    n2 = register_features(cfg)
    assert n1 == n2 > 0
    assert "qc__phone__drop_pct" in REGISTRY and "qc__pi__reasons__n" in REGISTRY
    assert REGISTRY.get("qc__pi__drop_pct").requires_raw is True
    assert REGISTRY.get("qc__phone__drop_pct").requires_raw is False
    assert REGISTRY.get("sync__ecg_uncertainty_s").requires_ecg is True
    assert REGISTRY.get("sync__grade").requires_ecg is False
    assert REGISTRY.get("clinician__ecg_hr").requires_ecg is True
    assert REGISTRY.get("age").group == "covariate"


def test_every_column_registered_and_values_match(cfg, clip_dir, crf_derived):
    df = _row(cfg, clip_dir, crf_derived)
    unregistered = [c for c in df.columns if c not in REGISTRY]
    assert unregistered == []
    r = df.iloc[0]
    # ids
    assert (r["study_id"], r["clip_id"], r["camera"], r["stream"]) == (SID, "clip1", "pi", "pilot")
    # qc (prefix qc__pi__), numeric coercion, booleans kept, lists flattened
    assert r["qc__pi__drop_pct"] == QC_PI["drop_pct"]
    assert r["qc__pi__n_frames"] == 1800 and df["qc__pi__n_frames"].dtype == "float64"
    assert r["qc__pi__valid_clip"] is np.False_ and str(df["qc__pi__valid_clip"].dtype) == "boolean"
    assert r["qc__pi__flicker_flag"] is np.True_
    assert r["qc__pi__flicker_peaks_hz"] == "50.0;100.0" and r["qc__pi__flicker_peaks_hz__n"] == 2
    assert r["qc__pi__reasons"] == "flicker_flag" and r["qc__pi__reasons__n"] == 1
    assert r["qc__pi__landmark_source"] == "mediapipe"
    assert math.isnan(r["qc__pi__eis_warp_px"])
    assert "qc__pi__study_id" not in df.columns and "qc__pi__camera" not in df.columns
    # sync fields from timeline.json
    assert r["sync__grade"] == "fine" and r["sync_grade"] == "fine"
    assert r["sync__ecg_map_method"] == "artefact_lift"
    assert r["sync__ecg_uncertainty_s"] == pytest.approx(0.033)
    assert r["sync__p1_found"] is np.True_ and r["sync__p2_found"] is np.True_
    assert r["sync__xcorr_peak"] == pytest.approx(0.81)
    # static colour
    assert r["static_colour__pi__mean_R"] == STATIC_COLOUR["mean_R"]
    assert r["static_colour__pi__colour_space"] == "linear_raw"
    # pulse sqi per method__roi -> group__camera__roi__method__name
    assert r["pulse__pi__thenar__POS__hr_bpm"] == PULSE_SQI["POS__thenar"]["hr_bpm"]
    assert r["pulse__pi__thenar__CHROM__sqi"] == PULSE_SQI["CHROM__thenar"]["sqi"]
    assert r["pulse__pi__central_palm__2SR__snr_db"] == PULSE_SQI["2SR__central_palm"]["snr_db"]
    assert r["pulse__pi__best"] == "POS__thenar"
    assert r["pulse__pi__best__hr_bpm"] == PULSE_SQI["POS__thenar"]["hr_bpm"]
    assert r["pulse__pi__fused__sqi"] == PULSE_SQI["fused"]["sqi"]
    # beat features by group
    assert r["hrv__pi__sdnn_ms"] == BEAT_FEATURES["hrv"]["sdnn_ms"]
    assert r["morphology__pi__reflection_index"] == BEAT_FEATURES["morphology"]["reflection_index"]
    assert r["apg__pi__ageing_index"] == BEAT_FEATURES["apg"]["ageing_index"]
    assert r["perfusion__pi__thenar__G1"] == BEAT_FEATURES["perfusion"]["thenar"]["G1"]
    assert r["resp__pi__rate_bpm"] == BEAT_FEATURES["resp"]["rate_bpm"]
    assert r["beats__pi__n_beats"] == 62 and r["beats__pi__quality_mean"] == 0.77
    # pat and ecg
    assert r["pat__pi__pat_mean_ms"] == PAT["pat_mean_ms"]
    assert "pat__pi__requires_ecg" not in df.columns
    assert r["ecg__hr_bpm"] == ECG_FEATURES["hr_bpm"] and r["ecg__clinician_rhythm"] == "sinus"
    assert r["ecg_digitised"] is np.False_
    # embeddings: mean over the two rows
    assert r["embedding__pi__physnet__0"] == pytest.approx(0.2)
    assert r["embedding__pi__physnet__1"] == pytest.approx(0.6)
    assert r["embedding__pi__physnet__2"] == pytest.approx(0.0)
    # clinician and derived strata
    assert r["clinician__rhythm"] == "sinus" and r["clinician__ecg_hr"] == 72.0
    assert r["rhythm_class"] == "sinus"
    assert r["clinician__lead12_obtained"] is np.False_
    assert r["time_of_day"] == "morning" and r["lux_band"] == "200-400"
    assert r["capture_mode"] == "simultaneous"
    assert pd.isna(r["bp_tertile"])
    # covariates
    for c in covariate_columns():
        assert c in df.columns
    assert r["bp_target_sbp"] == 133.0 and r["flags"] == "hypertension" and r["acute_30m"] == "none"
    assert r["flag_hypertension"] is np.True_ and r["bracket_flag"] is np.True_
    assert r["mst_band"] == 7.0 and r["age_band"] == "40-59"


def test_registry_flags_follow_camera_and_source(cfg, clip_dir, crf_derived):
    _row(cfg, clip_dir, crf_derived, "pi")
    _row(cfg, clip_dir, crf_derived, "phone")
    assert REGISTRY.get("pulse__pi__thenar__POS__hr_bpm").requires_raw is True
    assert REGISTRY.get("pulse__phone__thenar__POS__hr_bpm").requires_raw is False
    assert REGISTRY.get("pat__pi__pat_mean_ms").requires_ecg and REGISTRY.get("pat__pi__pat_mean_ms").requires_raw
    assert REGISTRY.get("pat__phone__pat_mean_ms").requires_ecg and not REGISTRY.get("pat__phone__pat_mean_ms").requires_raw
    assert REGISTRY.get("ecg__hr_bpm").requires_ecg and REGISTRY.get("ecg__hr_bpm").camera == "any"
    assert REGISTRY.get("hrv__pi__sdnn_ms").requires_raw and not REGISTRY.get("hrv__pi__sdnn_ms").requires_ecg
    assert not REGISTRY.get("hrv__phone__sdnn_ms").requires_raw
    assert REGISTRY.get("static_colour__phone__colour_space").camera == "phone"
    assert REGISTRY.get("embedding__pi__physnet__0").group == "embedding"
    for c in DERIVED_STRATA:
        assert c in REGISTRY


def test_feature_columns_by_track(cfg, clip_dir, crf_derived):
    pi = _row(cfg, clip_dir, crf_derived, "pi")
    phone = _row(cfg, clip_dir, crf_derived, "phone")
    prod_pi = feature_columns(pi, "product_candidate")
    prod_phone = feature_columns(phone, "product_candidate")
    sci_pi = feature_columns(pi, "science")
    sci_phone = feature_columns(phone, "science")
    # nothing ECG-derived in product_candidate, for either camera
    for cols in (prod_pi, prod_phone):
        assert not any(c.startswith(("pat__", "ecg__", "clinician__")) for c in cols)
        assert "sync__ecg_uncertainty_s" not in cols and "sync__xcorr_peak" not in cols
        assert "rhythm_class" not in cols and "ecg_digitised" not in cols
    # pi (raw Bayer) columns never in product_candidate; phone columns are
    assert not any("__pi__" in c for c in prod_pi)
    assert "pulse__phone__thenar__POS__hr_bpm" in prod_phone
    assert "hrv__phone__sdnn_ms" in prod_phone and "qc__phone__drop_pct" in prod_phone
    # science keeps everything incl. pat / ecg / pi
    assert "pat__pi__pat_mean_ms" in sci_pi and "ecg__hr_bpm" in sci_pi and "pulse__pi__thenar__POS__hr_bpm" in sci_pi
    assert "pat__phone__pat_mean_ms" in sci_phone
    # identifiers and targets are never features; explicit targets can be re-admitted
    for cols in (prod_pi, prod_phone, sci_pi, sci_phone):
        assert not set(id_columns(pi)) & set(cols)
        assert "bp_target_sbp" not in cols and "bp_target_dbp" not in cols and "hr_cuff_mean" not in cols
        assert "bp_category" not in cols and "clinician__rhythm" not in cols
        assert "flag_arrhythmia" in cols  # a disease flag, not the rhythm target
    with_target = feature_columns(phone, "science", exclude_targets=False)
    assert "bp_target_sbp" in with_target and "clinician__rhythm" in with_target
    # camera filter from the config's track definition
    cams = cfg.get("tracks.product_candidate.cameras")
    assert "phone" in cams and "pi" not in cams
    assert feature_columns(pi, "science", cameras=cams) == [c for c in sci_pi if "__pi__" not in c]
    # group filter
    assert all(c.startswith("pulse__") for c in feature_columns(phone, "product_candidate", groups=["pulse"]))
    # unregistered columns are refused in strict mode
    bad = pd.concat([phone, pd.DataFrame({"rogue_feature": [1.0]})], axis=1)
    with pytest.raises(TrackViolation):
        feature_columns(bad, "science")
    assert "rogue_feature" not in feature_columns(bad, "science", strict=False)


def test_missing_files_give_null_columns_only_where_known(cfg, tmp_path, crf_derived):
    empty = tmp_path / "work" / SID / "clip1"
    empty.mkdir(parents=True)
    df = build_clip_features(SID, "clip1", "pi_proxy", empty, crf_derived, None, cfg)
    assert len(df) == 1
    r = df.iloc[0]
    assert r["camera"] == "pi_proxy" and r["study_id"] == SID
    assert pd.isna(r["sync__grade"]) and pd.isna(r["clinician__rhythm"]) and pd.isna(r["rhythm_class"])
    assert not any(c.startswith(("qc__", "pulse__", "pat__", "ecg__")) for c in df.columns)
    assert r["lux_band"] is None or pd.isna(r["lux_band"])
    assert r["time_of_day"] == "morning"  # from CRF bp2 wall_ts (09:06 local) when clip meta is absent
    assert all(c in REGISTRY for c in df.columns)


def test_pi_proxy_rows_are_product_candidate(cfg, tmp_path, crf_derived):
    d = tmp_path / "work" / SID / "clip1"
    make_clip_artefacts(d, "pi_proxy", with_ecg=False, with_embedding=False)
    df = build_clip_features(SID, "clip1", "pi_proxy", d, crf_derived, CLINICIAN, cfg)
    prod = feature_columns(df, "product_candidate")
    assert "pulse__pi_proxy__thenar__POS__hr_bpm" in prod and "hrv__pi_proxy__rmssd_ms" in prod
    assert not any(c.startswith(("pat__", "ecg__")) for c in df.columns)


def test_bad_camera_rejected(cfg, tmp_path, crf_derived):
    with pytest.raises(ValueError):
        build_clip_features(SID, "clip1", "webcam", tmp_path, crf_derived, None, cfg)


def test_flatten_and_coercion_rules():
    flat = flatten({"a": {"b": 1, "c": [1, 2]}, "d": [], "e": [{"x": 1}, {"x": 2}], "skip": 9}, skip=("skip",))
    assert flat == {"a__b": 1, "a__c": "1.0;2.0", "a__c__n": 2, "d": None, "d__n": 0, "e__0__x": 1, "e__1__x": 2}
    assert [coerce_scalar(v) for v in ["1.5", "true", "", None, 3, True, "abc", float("nan"), np.int64(4)]] == [
        1.5, True, None, None, 3.0, True, "abc", None, 4.0]
    df = harmonise_dtypes(pd.DataFrame({"b": [True, None], "n": [1, None], "s": ["x", None], "z": [None, None]}))
    assert str(df["b"].dtype) == "boolean" and df["n"].dtype == "float64" and df["z"].dtype == "float64"
    assert df["s"].tolist()[0] == "x" and pd.isna(df["s"].tolist()[1])
