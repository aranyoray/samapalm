"""Landmark providers, conventions, the 4 fps run and the jitter motion proxy (section 6.1)."""
import json

import cv2
import numpy as np
import pandas as pd
import pytest

from palmppg.spatial.landmarks import (
    LANDMARK_COLUMNS,
    LandmarkProvider,
    MediaPipeHandsProvider,
    SkinSegmentationFallback,
    SyntheticLandmarkProvider,
    handedness_from_label,
    landmark_jitter_px,
    landmarks_frame,
    palmar_from_geometry,
    run_landmarks,
)
from palmppg.spatial.templates import hand_template_landmarks, transform_landmarks

FULL = (1080, 1920)
SKIN = (205, 150, 125)
DARK = (20, 18, 22)


class _Stub(LandmarkProvider):
    """Provider returning a template shifted by a known full-res pixel step per call."""

    source = "stub"

    def __init__(self, step_px=0.0, is_left=True, palmar=True, fail=False):
        self.step_px, self.is_left, self.palmar, self.fail = step_px, is_left, palmar, fail
        self.calls = 0

    def detect(self, preview, frame_idx):
        self.calls += 1
        if self.fail:
            return None
        lm = hand_template_landmarks()
        lm[:, 0] += self.step_px * (self.calls - 1) / FULL[1]
        return {"source": self.source, "confidence": 0.9, "is_left": self.is_left, "palmar": self.palmar, "lm": lm}


def _preview_stream(n=90, fps=30.0, shape=(54, 96)):
    img = np.zeros((shape[0], shape[1], 3), np.uint8)
    for i in range(n):
        yield i, i / fps, img


# ---------------------------------------------------------------- conventions
def test_handedness_label_is_swapped_for_non_mirrored_images():
    assert handedness_from_label("Left", mirror=True) is True
    assert handedness_from_label("Left", mirror=False) is False
    assert handedness_from_label("Right", mirror=False) is True
    with pytest.raises(ValueError):
        handedness_from_label("Both", False)


def test_palmar_geometry_follows_thumb_side_and_is_rotation_invariant():
    left_palmar = hand_template_landmarks()
    assert palmar_from_geometry(left_palmar, True) is True
    assert palmar_from_geometry(left_palmar, False) is False          # a right hand with the thumb on the right is dorsal
    assert palmar_from_geometry(hand_template_landmarks(is_left=False), False) is True
    assert palmar_from_geometry(hand_template_landmarks(palmar=False), True) is False
    for deg in (37.0, 90.0, 180.0, 270.0):
        assert palmar_from_geometry(transform_landmarks(left_palmar, rotate_deg=deg), True) is True
    mirrored = hand_template_landmarks(mirror=True)
    assert palmar_from_geometry(mirrored, True, mirror=True) is True
    assert palmar_from_geometry(mirrored, True, mirror=False) is False
    assert palmar_from_geometry(mirrored, True, palmar_convention="left_thumb_left") is True
    assert palmar_from_geometry(left_palmar, None, assume_left=True) is True
    collinear = np.zeros((21, 3))
    collinear[:, 0] = np.linspace(0, 1, 21)
    assert palmar_from_geometry(collinear, True) is None


# ---------------------------------------------------------------- synthetic provider
def test_synthetic_provider_reads_frames_and_static(tmp_path):
    lm = hand_template_landmarks()
    frames = []
    for k, idx in enumerate((0, 8, 16)):
        frames.append({"frame_idx": idx, "lm": (lm + np.array([0.01 * k, 0.0, 0.0])).tolist(), "is_left": True, "palmar": True})
    path = tmp_path / "landmarks.json"
    path.write_text(json.dumps({"frames": frames, "static": lm.tolist()}))
    prov = SyntheticLandmarkProvider(path)
    d0 = prov.detect(None, 0)
    assert d0["source"] == "synthetic" and d0["lm"].shape == (21, 3) and d0["is_left"] is True and d0["palmar"] is True
    assert np.allclose(d0["lm"], lm)
    assert np.allclose(prov.detect(None, 3)["lm"], lm)                       # nearest: frame 0
    assert np.allclose(prov.detect(None, 5)["lm"], lm + [0.01, 0, 0])        # nearest: frame 8
    assert np.allclose(prov.detect(None, 999)["lm"], lm + [0.02, 0, 0])      # beyond the last: frame 16
    static_only = tmp_path / "static.json"
    static_only.write_text(json.dumps({"static": lm.tolist(), "is_left": False, "palmar": True}))
    prov2 = SyntheticLandmarkProvider(static_only)
    for idx in (0, 7, 500):
        d = prov2.detect(None, idx)
        assert np.allclose(d["lm"], lm) and d["is_left"] is False
    (tmp_path / "bad.json").write_text(json.dumps({"frames": []}))
    with pytest.raises(ValueError):
        SyntheticLandmarkProvider(tmp_path / "bad.json")


# ---------------------------------------------------------------- skin fallback
def _ellipse_image(h=270, w=480, centre=(240, 150), axes=(90, 110)):
    img = np.full((h, w, 3), DARK, np.uint8)
    cv2.ellipse(img, centre, axes, 0, 0, 360, SKIN, -1)
    return img


def test_skin_fallback_finds_skin_ellipse_and_flags_source():
    img = _ellipse_image()
    fb = SkinSegmentationFallback()
    det = fb.detect(img, 3)
    assert det is not None and det["source"] == "skin_fallback" and det["hand_detected"] is True
    assert det["is_left"] is None and det["palmar"] is None
    assert 0.0 < det["confidence"] <= fb.confidence_scale
    expected_area = np.pi * 90 * 110 / (270 * 480)
    assert det["area_frac"] == pytest.approx(expected_area, rel=0.05)
    lm = det["lm"]
    assert lm.shape == (21, 3) and (lm[:, :2] >= 0).all() and (lm[:, :2] <= 1).all()
    px = lm[:, :2] * [480, 270]
    assert px[0, 1] == pytest.approx(260.0, abs=2.0)                 # wrist = lowest hull point (y = 150 + 110)
    assert px[0, 1] == px[:, 1].max()
    skin = cv2.dilate(fb.skin_mask(img).astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    for x, y in px:
        assert skin[min(round(y), 269), min(round(x), 479)], (x, y)
    tips = px[[4, 8, 12, 16, 20]]
    assert (tips[:, 1] < px[0, 1]).all()                              # all tips above the wrist
    assert tips[1:, 1].max() < 150                                    # finger tips in the upper half
    assert det["thumb_side_from"] == "assumed_hand" and tips[0, 0] > tips[4, 0]  # left palmar: thumb right of pinky


def test_skin_fallback_rejects_small_blob_and_dark_frames():
    fb = SkinSegmentationFallback(min_area_frac=0.05)
    assert fb.detect(_ellipse_image(axes=(20, 25)), 0) is None
    assert fb.detect(np.full((100, 100, 3), DARK, np.uint8), 0) is None


def test_skin_fallback_uses_hull_asymmetry_for_the_thumb_side():
    img = _ellipse_image()
    cv2.ellipse(img, (350, 190), (45, 22), -30, 0, 360, SKIN, -1)   # a thumb-like bump on the right, near the wrist
    det = SkinSegmentationFallback(assume_left=False).detect(img, 0)  # the assumption says thumb-left; geometry wins
    assert det["thumb_side_from"] == "hull_asymmetry"
    px = det["lm"][:, :2] * [480, 270]
    assert px[4, 0] > px[20, 0]


# ---------------------------------------------------------------- run_landmarks
def test_run_landmarks_subsamples_by_reference_time_not_index():
    stub = _Stub()
    df, s = run_landmarks(_preview_stream(90), stub, 4.0, None, full_res_shape=FULL)
    assert len(df) == 12 and stub.calls == 12
    assert np.all(np.diff(df["t_ref_s"].to_numpy()) >= 0.25 - 1 / 30 - 1e-9)
    assert list(df.columns) == list(LANDMARK_COLUMNS)
    assert s["hand_detected"] is True and s["landmark_source"] == "stub"
    assert s["hand_is_left"] is True and s["hand_palmar"] is True
    assert s["n_preview_frames"] == 90 and s["n_landmark_frames"] == 12

    def gapped():
        for i in range(90):
            t = i / 30.0 + (10.0 if i >= 45 else 0.0)                 # 10 s hole in the middle, same indices
            yield i, t, np.zeros((54, 96, 3), np.uint8)

    df2, _ = run_landmarks(gapped(), _Stub(), 4.0, None, full_res_shape=FULL)
    assert len(df2) == 12
    assert (df2["t_ref_s"] >= 10.0).sum() == 6


def test_run_landmarks_jitter_and_motion_flag():
    df, s = run_landmarks(_preview_stream(90), _Stub(step_px=2.0), 4.0, None, full_res_shape=FULL, jitter_px_max=3.0)
    assert s["landmark_jitter_px"] == pytest.approx(2.0, abs=1e-6)
    assert s["motion_flag"] is False
    assert landmark_jitter_px(df, FULL) == pytest.approx(2.0, abs=1e-6)
    _, s2 = run_landmarks(_preview_stream(90), _Stub(step_px=4.0), 4.0, None, full_res_shape=FULL, jitter_px_max=3.0)
    assert s2["landmark_jitter_px"] == pytest.approx(4.0, abs=1e-6) and s2["motion_flag"] is True
    _, s3 = run_landmarks(_preview_stream(90), _Stub(step_px=4.0), 4.0, None, full_res_shape=(540, 960))
    assert s3["landmark_jitter_px"] == pytest.approx(2.0, abs=1e-6)  # measured in full-res px of the stated frame


def test_run_landmarks_falls_back_and_reports_none_when_nothing_found():
    class _Fallback(LandmarkProvider):
        source = "skin_fallback"

        def detect(self, preview, frame_idx):
            return {"source": "skin_fallback", "confidence": 0.1, "is_left": None, "palmar": None,
                    "lm": hand_template_landmarks()}

    df, s = run_landmarks(_preview_stream(60), _Stub(fail=True), 4.0, _Fallback(), full_res_shape=FULL)
    assert s["landmark_source"] == "skin_fallback" and s["hand_detected"] is True
    assert s["hand_is_left"] is None and s["hand_palmar"] is None
    assert (df["source"] == "skin_fallback").all() and df["is_left"].isna().all()
    df2, s2 = run_landmarks(_preview_stream(60), _Stub(fail=True), 4.0, None, full_res_shape=FULL)
    assert s2["hand_detected"] is False and s2["landmark_source"] == "none"
    assert np.isnan(s2["landmark_jitter_px"]) and s2["motion_flag"] is False
    assert (df2["source"] == "none").all() and df2["lm00_x"].isna().all()
    df3, s3 = run_landmarks(iter(()), _Stub(), 4.0, None)
    assert len(df3) == 0 and s3["hand_detected"] is False


def test_landmarks_frame_matches_contract_and_survives_parquet(tmp_path):
    df, _ = run_landmarks(_preview_stream(30), _Stub(), 4.0, None, full_res_shape=FULL)
    assert str(df["is_left"].dtype) == "boolean" and df["frame_idx"].dtype == np.int64
    assert df.filter(regex=r"^lm\d\d_[xyz]$").shape[1] == 63
    df.to_parquet(tmp_path / "landmarks.parquet", index=False)
    back = pd.read_parquet(tmp_path / "landmarks.parquet")
    assert list(back.columns) == list(LANDMARK_COLUMNS)
    assert back["palmar"].tolist() == [True] * len(back)
    assert landmarks_frame([]).shape == (0, len(LANDMARK_COLUMNS))


# ---------------------------------------------------------------- MediaPipe smoke
@pytest.mark.hands
def test_mediapipe_provider_smoke_on_rendered_hand():
    pytest.importorskip("mediapipe")
    h, w = 480, 480
    img = np.full((h, w, 3), DARK, np.uint8)
    cv2.ellipse(img, (240, 300), (85, 95), 0, 0, 360, SKIN, -1)
    for (x0, y0, x1, y1) in [(175, 250, 150, 120), (215, 220, 205, 80), (255, 215, 255, 75), (295, 225, 300, 95), (330, 255, 345, 160)]:
        cv2.line(img, (x0, y0), (x1, y1), SKIN, 34)
    cv2.line(img, (300, 350), (380, 300), SKIN, 40)
    prov = MediaPipeHandsProvider(mirror=False, min_detection_confidence=0.2, min_presence_confidence=0.2)
    try:
        det = prov.detect(img, 0)
    finally:
        prov.close()
    if det is None:
        # allowed: no hand found on a cartoon, or no usable API / model on this machine (reason recorded)
        assert prov.api in (None, "legacy", "tasks")
        assert prov.api is not None or isinstance(prov.unavailable_reason, str)
    else:
        assert det["source"] == "mediapipe" and det["lm"].shape == (21, 3)
        assert det["is_left"] in (True, False, None) and det["palmar"] in (True, False, None)
    missing = MediaPipeHandsProvider(model_path="/nonexistent/hand_landmarker.task")
    if missing._ensure() and missing.api == "legacy":
        missing.close()
    else:
        assert missing.detect(img, 0) is None and missing.unavailable_reason
