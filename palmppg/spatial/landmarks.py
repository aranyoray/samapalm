"""Hand presence, handedness, palmar check and 21 landmarks on the 8-bit preview (protocol section 6.1).

Three providers share one interface, `LandmarkProvider.detect(preview_rgb_uint8, frame_idx)`:

  MediaPipeHandsProvider     MediaPipe Hands (legacy `mediapipe.solutions.hands` when installed, else the
                             tasks-API HandLandmarker with a `.task` model file). Imported lazily.
  SyntheticLandmarkProvider  ground-truth landmarks written by the synthetic generator (JSON).
  SkinSegmentationFallback   YCrCb skin segmentation -> largest blob -> convex hull -> approximate
                             landmarks, flagged `source="skin_fallback"` with low confidence.

Every provider returns None (no hand) or a dict:
  {"source": str, "confidence": float, "is_left": bool | None, "palmar": bool | None,
   "lm": (21, 3) float array with x, y normalised to [0, 1] of the preview and z relative,
   "hand_detected": True}

Conventions (documented here because they decide "one left hand, palmar view" in QC):
  * Image coordinates: x to the right, y down, as the camera sensor reads them out (not mirrored).
  * MediaPipe reports handedness for a horizontally mirrored (selfie) image. `mirror=False` (the Pi
    looking up through the aperture, or a rear phone camera) therefore swaps the label; `mirror=True`
    keeps it. The same flag flips the palmar geometry test. Checked once on MediaPipe's own
    `thumb_up.jpg` sample (a left palm in an unmirrored photo, labelled "Right" by the model and by the
    expected-result file that ships with it): `mirror=False` gives is_left=True, palmar=True. The first
    real Pi clip must repeat this check against the CRF `imaged_hand`; if it disagrees, set
    `qc.hand_mirror: true` rather than editing code.
  * Palmar test from geometry: for a LEFT hand seen palm-on in a non-mirrored image the thumb lies to
    the RIGHT of the little finger (an observer facing the palm of a left hand, fingers up, sees the
    thumb on their right). Rotation-invariant form: the signed area of the triangle wrist (0), index
    MCP (5), little MCP (17) is negative in y-down coordinates. `palmar_convention="left_thumb_right"`
    encodes this; "left_thumb_left" is the opposite (e.g. a preview that was flipped upstream).

`run_landmarks` subsamples the preview stream by reference-clock time to `fps_target`
(configs: qc.hand_preview_fps), never by frame index, and reports the landmark jitter motion proxy.
"""
from __future__ import annotations

import contextlib
import json
import os
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

from palmppg.spatial.rois import (
    INDEX_MCP,
    LITTLE_MCP,
    N_LANDMARKS,
    WRIST,
)

LM_COLUMNS: tuple[str, ...] = tuple(f"lm{i:02d}_{ax}" for i in range(N_LANDMARKS) for ax in ("x", "y", "z"))
LANDMARK_COLUMNS: tuple[str, ...] = ("frame_idx", "t_ref_s", "source", "confidence", "is_left", "palmar") + LM_COLUMNS

PALMAR_CONVENTIONS = {"left_thumb_right": -1.0, "left_thumb_left": 1.0}

# Documented model for the MediaPipe tasks API (hand_landmarker, float16, version 1).
HAND_LANDMARKER_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
)
HAND_LANDMARKER_ENV = "PALMPPG_HAND_LANDMARKER"


def default_model_path() -> Path:
    """Where the tasks-API model is looked for: $PALMPPG_HAND_LANDMARKER, else data/models/hand_landmarker.task."""
    env = os.environ.get(HAND_LANDMARKER_ENV)
    if env:
        return Path(env)
    from palmppg.core.config import REPO_ROOT

    return REPO_ROOT / "data" / "models" / "hand_landmarker.task"


# --------------------------------------------------------------------------- geometry conventions
def handedness_from_label(label: str, mirror: bool) -> bool:
    """MediaPipe 'Left'/'Right' label -> is_left, honouring the selfie-mirror convention.

    MediaPipe assumes the image is mirrored; for a non-mirrored camera (`mirror=False`) the label is
    swapped. Section 6.1 (confirm one left hand).
    """
    lab = str(label).strip().lower()
    if lab not in ("left", "right"):
        raise ValueError(f"unknown handedness label {label!r}")
    is_left_label = lab == "left"
    return is_left_label if mirror else not is_left_label


def signed_palm_area(lm_xy: np.ndarray) -> float:
    """Cross product (5 - 0) x (17 - 0) in image coordinates (x right, y down); sign encodes thumb side."""
    a = np.asarray(lm_xy, dtype=float)
    v1 = a[INDEX_MCP, :2] - a[WRIST, :2]
    v2 = a[LITTLE_MCP, :2] - a[WRIST, :2]
    return float(v1[0] * v2[1] - v1[1] * v2[0])


def palmar_from_geometry(
    lm_xy: np.ndarray, is_left: bool | None, palmar_convention: str = "left_thumb_right",
    mirror: bool = False, assume_left: bool = True,
) -> bool | None:
    """Palmar (palm facing the camera) from landmark geometry (section 6.1, "palmar view").

    Uses the sign of the wrist / index-MCP / little-MCP triangle (see module docstring). The expected
    sign for a left palmar hand comes from `palmar_convention` and flips with `mirror`; a right hand has
    the opposite sign. `is_left=None` falls back to `assume_left` (the study images the left palm).
    Returns None when the triangle is degenerate (collinear landmarks).
    """
    if palmar_convention not in PALMAR_CONVENTIONS:
        raise ValueError(f"palmar_convention must be one of {sorted(PALMAR_CONVENTIONS)}")
    s = signed_palm_area(lm_xy)
    if abs(s) < 1e-12:
        return None
    left = assume_left if is_left is None else bool(is_left)
    expected_left = PALMAR_CONVENTIONS[palmar_convention] * (-1.0 if mirror else 1.0)
    expected = expected_left if left else -expected_left
    return bool(np.sign(s) == np.sign(expected))


# --------------------------------------------------------------------------- provider interface
class LandmarkProvider:
    """Interface: `detect(preview_rgb_uint8, frame_idx) -> dict | None` (see module docstring)."""

    source: str = "abstract"

    def detect(self, preview_rgb_uint8: np.ndarray, frame_idx: int) -> dict | None:  # pragma: no cover
        raise NotImplementedError

    def close(self) -> None:
        return None

    @staticmethod
    def _check_preview(preview: np.ndarray) -> np.ndarray:
        a = np.asarray(preview)
        if a.ndim != 3 or a.shape[2] != 3:
            raise ValueError(f"preview must be (H, W, 3) RGB, got {a.shape}")
        if a.dtype != np.uint8:
            a = np.clip(a, 0, 255).astype(np.uint8)
        return np.ascontiguousarray(a)


# --------------------------------------------------------------------------- MediaPipe
class MediaPipeHandsProvider(LandmarkProvider):
    """MediaPipe Hands on the 8-bit preview (section 6.1), legacy solutions API or tasks API.

    `mirror`: True when the preview is a selfie-style horizontally mirrored image; False (default) for the
    Pi camera looking up at the palm and for a rear phone camera. It swaps the handedness label and the
    palmar geometry sign as described in the module docstring.
    `model_path`: `.task` file for the tasks API (mediapipe >= 0.10 without `solutions`); defaults to
    `default_model_path()`; `download_model()` fetches the documented model. When neither API can be set up
    `detect` returns None and `unavailable_reason` says why, so the pipeline falls back to skin
    segmentation with a flag rather than failing.
    `confidence` in the result is MediaPipe's handedness score (the only per-hand score both APIs expose).
    Frames are processed independently (image mode): no tracking state leaks between 4 fps previews.
    """

    source = "mediapipe"

    def __init__(
        self, mirror: bool = False, palmar_convention: str = "left_thumb_right", model_path: str | os.PathLike | None = None,
        min_detection_confidence: float = 0.5, min_presence_confidence: float = 0.5, num_hands: int = 1,
        assume_left: bool = True,
    ) -> None:
        if palmar_convention not in PALMAR_CONVENTIONS:
            raise ValueError(f"palmar_convention must be one of {sorted(PALMAR_CONVENTIONS)}")
        self.mirror = bool(mirror)
        self.palmar_convention = palmar_convention
        self.model_path = Path(model_path) if model_path else None
        self.min_detection_confidence = float(min_detection_confidence)
        self.min_presence_confidence = float(min_presence_confidence)
        self.num_hands = int(num_hands)
        self.assume_left = bool(assume_left)
        self.api: str | None = None
        self.unavailable_reason: str | None = None
        self._detector = None
        self._mp = None

    # ---- setup
    def _ensure(self) -> bool:
        if self._detector is not None:
            return True
        if self.unavailable_reason is not None:
            return False
        try:
            import mediapipe as mp  # lazy, optional dependency
        except Exception as exc:  # noqa: BLE001  (a broken native build raises more than ImportError)
            self.unavailable_reason = f"mediapipe import failed: {exc}"
            return False
        self._mp = mp
        solutions = getattr(mp, "solutions", None)
        hands = getattr(solutions, "hands", None) if solutions is not None else None
        if hands is not None:
            try:
                self._detector = hands.Hands(
                    static_image_mode=True, max_num_hands=self.num_hands,
                    min_detection_confidence=self.min_detection_confidence,
                    min_tracking_confidence=self.min_presence_confidence,
                )
                self.api = "legacy"
                return True
            except Exception as exc:  # noqa: BLE001  (any setup failure means: fall back, do not crash QC)
                self.unavailable_reason = f"legacy solutions.hands setup failed: {exc}"
                return False
        path = self.model_path or default_model_path()
        if not Path(path).exists():
            self.unavailable_reason = (
                f"tasks API needs a model file; {path} not found (set {HAND_LANDMARKER_ENV} or call download_model())"
            )
            return False
        try:
            from mediapipe.tasks.python import BaseOptions, vision

            opts = vision.HandLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=str(path)),
                running_mode=vision.RunningMode.IMAGE, num_hands=self.num_hands,
                min_hand_detection_confidence=self.min_detection_confidence,
                min_hand_presence_confidence=self.min_presence_confidence,
            )
            self._detector = vision.HandLandmarker.create_from_options(opts)
            self.api = "tasks"
            return True
        except Exception as exc:  # noqa: BLE001  (any setup failure means: fall back, do not crash QC)
            self.unavailable_reason = f"tasks API setup failed: {exc}"
            return False

    @staticmethod
    def download_model(dest: str | os.PathLike | None = None, url: str = HAND_LANDMARKER_MODEL_URL) -> Path:
        """Fetch the documented hand_landmarker.task to `dest` (default `default_model_path()`)."""
        import urllib.request

        dest = Path(dest) if dest else default_model_path()
        dest.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=60) as resp, open(dest, "wb") as fh:
            fh.write(resp.read())
        return dest

    # ---- detection
    def detect(self, preview_rgb_uint8: np.ndarray, frame_idx: int) -> dict | None:
        preview = self._check_preview(preview_rgb_uint8)
        if not self._ensure():
            return None
        if self.api == "legacy":
            res = self._detector.process(preview)
            hands_lm = getattr(res, "multi_hand_landmarks", None) or []
            handed = getattr(res, "multi_handedness", None) or []
            if not hands_lm:
                return None
            lm = np.array([[p.x, p.y, p.z] for p in hands_lm[0].landmark], dtype=float)
            if handed:
                cls = handed[0].classification[0]
                label, score = cls.label, float(cls.score)
            else:
                label, score = None, 0.0
        else:
            mp = self._mp
            image = mp.Image(image_format=mp.ImageFormat.SRGB, data=preview)
            res = self._detector.detect(image)
            hands_lm = getattr(res, "hand_landmarks", None) or []
            handed = getattr(res, "handedness", None) or []
            if not hands_lm:
                return None
            lm = np.array([[p.x, p.y, p.z] for p in hands_lm[0]], dtype=float)
            if handed and handed[0]:
                label, score = handed[0][0].category_name, float(handed[0][0].score)
            else:
                label, score = None, 0.0
        if lm.shape != (N_LANDMARKS, 3):
            return None
        is_left = handedness_from_label(label, self.mirror) if label else None
        palmar = palmar_from_geometry(lm, is_left, self.palmar_convention, self.mirror, self.assume_left)
        return {
            "source": self.source, "confidence": score, "is_left": is_left, "palmar": palmar, "lm": lm,
            "hand_detected": True, "handedness_label": label, "api": self.api, "frame_idx": int(frame_idx),
        }

    def close(self) -> None:
        det, self._detector = self._detector, None
        if det is not None and hasattr(det, "close"):
            with contextlib.suppress(Exception):  # releasing a native detector must never fail the run
                det.close()


# --------------------------------------------------------------------------- synthetic ground truth
class SyntheticLandmarkProvider(LandmarkProvider):
    """Ground-truth landmarks from the synthetic generator's JSON (section 8 positive control).

    File layout: {"frames": [{"frame_idx": i, "lm": [[x, y, z] * 21], "is_left": true, "palmar": true}, ...],
    "static": [[x, y, z] * 21]}. When "frames" is absent (or empty) "static" is used for every frame.
    A frame index without an entry takes the entry with the nearest frame index (the generator may
    write landmarks at a lower cadence than the video). Per-entry `is_left`/`palmar` default to the
    top-level keys, then to True (the study images the left palm).
    """

    source = "synthetic"

    def __init__(self, path_to_landmarks_json: str | os.PathLike, confidence: float = 1.0) -> None:
        self.path = Path(path_to_landmarks_json)
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.default_is_left = bool(data.get("is_left", True))
        self.default_palmar = bool(data.get("palmar", True))
        self.confidence = float(confidence)
        static = data.get("static")
        self.static = self._as_lm(static) if static is not None else None
        frames = data.get("frames") or []
        self.frame_idx = np.array([int(f["frame_idx"]) for f in frames], dtype=np.int64)
        order = np.argsort(self.frame_idx, kind="stable")
        self.frame_idx = self.frame_idx[order]
        self.frames = [frames[i] for i in order]
        self.frame_lm = [self._as_lm(f["lm"]) for f in self.frames]
        if self.static is None and not self.frames:
            raise ValueError(f"{self.path}: needs 'frames' or 'static'")

    @staticmethod
    def _as_lm(raw) -> np.ndarray:
        lm = np.asarray(raw, dtype=float)
        if lm.shape == (N_LANDMARKS, 2):
            lm = np.hstack([lm, np.zeros((N_LANDMARKS, 1))])
        if lm.shape != (N_LANDMARKS, 3):
            raise ValueError(f"landmark array must be (21, 3), got {lm.shape}")
        return lm

    def _nearest(self, frame_idx: int) -> int:
        pos = int(np.searchsorted(self.frame_idx, frame_idx))
        if pos == 0:
            return 0
        if pos >= self.frame_idx.size:
            return self.frame_idx.size - 1
        before, after = self.frame_idx[pos - 1], self.frame_idx[pos]
        return pos - 1 if (frame_idx - before) <= (after - frame_idx) else pos

    def detect(self, preview_rgb_uint8: np.ndarray, frame_idx: int) -> dict | None:
        if self.frames:
            k = self._nearest(int(frame_idx))
            entry = self.frames[k]
            lm = self.frame_lm[k]
            is_left = bool(entry.get("is_left", self.default_is_left))
            palmar = bool(entry.get("palmar", self.default_palmar))
            if entry.get("hand_detected", True) is False:
                return None
        else:
            lm, is_left, palmar = self.static, self.default_is_left, self.default_palmar
        return {
            "source": self.source, "confidence": self.confidence, "is_left": is_left, "palmar": palmar,
            "lm": lm.copy(), "hand_detected": True, "frame_idx": int(frame_idx),
        }


# --------------------------------------------------------------------------- skin fallback
@dataclass
class SkinSegmentationFallback(LandmarkProvider):
    """Skin segmentation fallback with a flag (section 6.1, "skin segmentation fallback").

    YCrCb thresholds (Cr in `cr_range`, Cb in `cb_range`, Y above `y_min`), a morphological open/close,
    the largest connected blob, and its convex hull. The hand counts as detected only when the blob
    covers more than `min_area_frac` (5 %) of the preview. Approximate landmarks: wrist = hull vertex
    on the `wrist_side` of the image (default "bottom", the largest y); palm centre = blob centroid;
    fingertips = where rays from the centre at fixed angles about the wrist->centre axis leave the hull;
    pulled `tip_inset` of the way back toward the centre so they sit just inside the silhouette; joints
    interpolated along each ray (MCP 0.30, PIP 0.55, DIP 0.78, TIP 1.0 of centre->tip); thumb
    joints along wrist->thumb tip (0.30, 0.55, 0.78, 1.0). The thumb side is the hull's wider lateral
    side near the wrist when that is decisive, else the side implied by `assume_left`/`assume_palmar`
    under the left_thumb_right convention. Handedness and palmar view cannot be told from a skin blob,
    so `is_left` and `palmar` are None; the assumptions used are returned separately.
    `confidence` = `confidence_scale` x blob solidity (area / hull area), always low.
    """

    min_area_frac: float = 0.05
    cr_range: tuple[int, int] = (133, 173)
    cb_range: tuple[int, int] = (77, 127)
    y_min: int = 40
    wrist_side: str = "bottom"
    assume_left: bool = True
    assume_palmar: bool = True
    confidence_scale: float = 0.3
    asymmetry_min_ratio: float = 0.15
    finger_angles_deg: tuple[float, ...] = (22.0, 2.0, -16.0, -36.0)
    thumb_angle_deg: float = 70.0
    joint_fracs: tuple[float, ...] = (0.30, 0.55, 0.78, 1.0)
    tip_inset: float = 0.96
    source: str = field(default="skin_fallback", init=False)

    def skin_mask(self, preview_rgb_uint8: np.ndarray) -> np.ndarray:
        """Boolean skin mask of the preview (YCrCb box thresholds + open/close)."""
        preview = self._check_preview(preview_rgb_uint8)
        ycrcb = cv2.cvtColor(preview, cv2.COLOR_RGB2YCrCb)
        lo = np.array([self.y_min, self.cr_range[0], self.cb_range[0]], dtype=np.uint8)
        hi = np.array([255, self.cr_range[1], self.cb_range[1]], dtype=np.uint8)
        mask = cv2.inRange(ycrcb, lo, hi)
        k = max(3, (min(preview.shape[:2]) // 64) | 1)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        return mask.astype(bool)

    def largest_blob(self, mask: np.ndarray) -> tuple[np.ndarray | None, float]:
        """(mask of the largest connected component, its area fraction of the frame)."""
        n, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
        if n <= 1:
            return None, 0.0
        areas = stats[1:, cv2.CC_STAT_AREA]
        k = int(np.argmax(areas)) + 1
        blob = labels == k
        return blob, float(areas[k - 1]) / float(mask.size)

    def detect(self, preview_rgb_uint8: np.ndarray, frame_idx: int) -> dict | None:
        preview = self._check_preview(preview_rgb_uint8)
        h, w = preview.shape[:2]
        blob, area_frac = self.largest_blob(self.skin_mask(preview))
        if blob is None or area_frac <= self.min_area_frac:
            return None
        contours, _ = cv2.findContours(blob.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None
        contour = max(contours, key=cv2.contourArea)
        hull = cv2.convexHull(contour).reshape(-1, 2).astype(float)
        if hull.shape[0] < 3:
            return None
        m = cv2.moments(blob.astype(np.uint8), binaryImage=True)
        if m["m00"] <= 0:
            return None
        centre = np.array([m["m10"] / m["m00"], m["m01"] / m["m00"]])
        hull_area = max(float(cv2.contourArea(hull.astype(np.float32))), 1.0)
        solidity = min(1.0, float(m["m00"]) / hull_area)
        lm_px, thumb_from = self._landmarks_from_hull(hull, centre)
        lm = np.zeros((N_LANDMARKS, 3), dtype=float)
        lm[:, 0] = lm_px[:, 0] / w
        lm[:, 1] = lm_px[:, 1] / h
        return {
            "source": self.source, "confidence": float(self.confidence_scale * solidity), "is_left": None,
            "palmar": None, "lm": lm, "hand_detected": True, "area_frac": area_frac, "solidity": solidity,
            "is_left_assumed": self.assume_left, "palmar_assumed": self.assume_palmar,
            "thumb_side_from": thumb_from, "frame_idx": int(frame_idx),
        }

    # ---- hull -> landmarks
    def _wrist_vertex(self, hull: np.ndarray) -> np.ndarray:
        side = self.wrist_side
        if side == "bottom":
            return hull[np.argmax(hull[:, 1])]
        if side == "top":
            return hull[np.argmin(hull[:, 1])]
        if side == "left":
            return hull[np.argmin(hull[:, 0])]
        if side == "right":
            return hull[np.argmax(hull[:, 0])]
        raise ValueError("wrist_side must be bottom, top, left or right")

    @staticmethod
    def _ray_hull_exit(origin: np.ndarray, direction: np.ndarray, hull: np.ndarray, fallback_len: float) -> np.ndarray:
        best = -1.0
        n = hull.shape[0]
        for i in range(n):
            a, b = hull[i], hull[(i + 1) % n]
            e = b - a
            denom = direction[0] * e[1] - direction[1] * e[0]
            if abs(denom) < 1e-12:
                continue
            ao = a - origin
            t = (ao[0] * e[1] - ao[1] * e[0]) / denom
            u = (ao[0] * direction[1] - ao[1] * direction[0]) / denom
            if t >= 0.0 and -1e-9 <= u <= 1.0 + 1e-9:
                best = max(best, t)
        if best < 0.0:
            best = fallback_len
        return origin + best * direction

    def _landmarks_from_hull(self, hull: np.ndarray, centre: np.ndarray) -> tuple[np.ndarray, str]:
        wrist = self._wrist_vertex(hull)
        axis = centre - wrist
        length = float(np.hypot(*axis))
        axis = axis / length if length > 1e-9 else np.array([0.0, -1.0])
        lateral = np.array([-axis[1], axis[0]])            # +lateral = image right when fingers point up
        rel = hull - wrist
        proj = rel @ axis
        lat = rel @ lateral
        extent = float(np.max(proj)) if proj.size else length
        sel = (proj > 0.15 * extent) & (proj < 0.6 * extent)
        plus = float(np.max(lat[sel])) if np.any(sel & (lat > 0)) else 0.0
        minus = float(-np.min(lat[sel])) if np.any(sel & (lat < 0)) else 0.0
        width = max(plus + minus, 1e-9)
        assumed_sign = 1.0 if (self.assume_left == self.assume_palmar) else -1.0
        if abs(plus - minus) / width > self.asymmetry_min_ratio:
            sign, thumb_from = (1.0 if plus > minus else -1.0), "hull_asymmetry"
        else:
            sign, thumb_from = assumed_sign, "assumed_hand"

        def ray(angle_deg: float) -> np.ndarray:
            th = np.deg2rad(angle_deg)
            return np.cos(th) * axis + np.sin(th) * sign * lateral

        lm = np.zeros((N_LANDMARKS, 2), dtype=float)
        lm[WRIST] = wrist
        inset = float(self.tip_inset)
        exit_pt = self._ray_hull_exit(centre, ray(self.thumb_angle_deg), hull, 0.5 * extent)
        thumb_tip = centre + inset * (exit_pt - centre)
        for j, frac in zip((1, 2, 3, 4), self.joint_fracs):
            lm[j] = wrist + frac * (thumb_tip - wrist)
        for base, angle in zip((5, 9, 13, 17), self.finger_angles_deg):
            exit_pt = self._ray_hull_exit(centre, ray(angle), hull, 0.5 * extent)
            tip = centre + inset * (exit_pt - centre)
            for k, frac in enumerate(self.joint_fracs):
                lm[base + k] = centre + frac * (tip - centre)
        return lm, thumb_from


# --------------------------------------------------------------------------- the 4 fps run
def _row(frame_idx: int, t_ref_s: float, det: dict | None) -> dict:
    row: dict = {"frame_idx": int(frame_idx), "t_ref_s": float(t_ref_s)}
    if det is None:
        row.update({"source": "none", "confidence": 0.0, "is_left": None, "palmar": None})
        row.update({c: np.nan for c in LM_COLUMNS})
        return row
    row.update({
        "source": det["source"], "confidence": float(det["confidence"]),
        "is_left": None if det.get("is_left") is None else bool(det["is_left"]),
        "palmar": None if det.get("palmar") is None else bool(det["palmar"]),
    })
    lm = np.asarray(det["lm"], dtype=float)
    for i in range(N_LANDMARKS):
        row[f"lm{i:02d}_x"], row[f"lm{i:02d}_y"], row[f"lm{i:02d}_z"] = float(lm[i, 0]), float(lm[i, 1]), float(lm[i, 2])
    return row


def landmarks_frame(rows: Iterable[dict]) -> pd.DataFrame:
    """Build the landmarks.parquet DataFrame (CONTRACTS section 4) with nullable booleans."""
    df = pd.DataFrame(list(rows), columns=list(LANDMARK_COLUMNS))
    df["frame_idx"] = df["frame_idx"].astype("int64")
    df["t_ref_s"] = df["t_ref_s"].astype(float)
    df["source"] = df["source"].astype(object)
    df["confidence"] = df["confidence"].astype(float)
    for c in ("is_left", "palmar"):
        df[c] = pd.array([None if v is None or (isinstance(v, float) and np.isnan(v)) else bool(v) for v in df[c]],
                         dtype="boolean")
    for c in LM_COLUMNS:
        df[c] = df[c].astype(float)
    return df


def landmark_array(df: pd.DataFrame) -> np.ndarray:
    """(n_rows, 21, 3) float array of the lmNN_{x,y,z} columns of a landmarks DataFrame."""
    if len(df) == 0:
        return np.zeros((0, N_LANDMARKS, 3), dtype=float)
    return df[list(LM_COLUMNS)].to_numpy(dtype=float).reshape(len(df), N_LANDMARKS, 3)


def landmark_jitter_px(df: pd.DataFrame, full_res_shape: tuple[int, int]) -> float:
    """Median over consecutive detected landmark frames of the median per-landmark displacement (px).

    Displacement is measured in full-resolution pixels (normalised coordinates times the full frame
    width/height) so the value is comparable across preview sizes. NaN with fewer than two detections.
    Section 6.1 (landmark jitter as motion proxy).
    """
    det = df[df["source"] != "none"]
    if len(det) < 2:
        return float("nan")
    lm = landmark_array(det)[:, :, :2] * np.array([full_res_shape[1], full_res_shape[0]], dtype=float)
    disp = np.hypot(*(np.diff(lm, axis=0).transpose(2, 0, 1)))        # (n-1, 21)
    return float(np.median(np.median(disp, axis=1)))


def _majority(values: Iterable) -> bool | None:
    vals = [bool(v) for v in values if not (v is None or pd.isna(v))]
    if not vals:
        return None
    return bool(sum(vals) * 2 >= len(vals))


def run_landmarks(
    preview_frames_iter: Iterator[tuple[int, float, np.ndarray]],
    provider: LandmarkProvider | None,
    fps_target: float,
    fallback: LandmarkProvider | None = None,
    full_res_shape: tuple[int, int] | None = None,
    jitter_px_max: float = 3.0,
    min_detect_frac: float = 0.5,
) -> tuple[pd.DataFrame, dict]:
    """Run a landmark provider at `fps_target` over a preview stream of (frame_idx, t_ref_s, rgb_uint8).

    Frames are chosen by reference-clock time (one per 1/fps_target s, never by frame index). When the
    provider finds nothing the fallback is tried; rows with no hand carry source "none" and NaN
    landmarks. Returns (landmarks DataFrame per CONTRACTS section 4, summary) with summary keys
    hand_detected (detected in at least `min_detect_frac` of processed previews), hand_is_left and
    hand_palmar (majority vote over provider detections, None when undecidable), landmark_source
    (most frequent non-"none" source, "none" when nothing was found), landmark_jitter_px
    (`landmark_jitter_px`), motion_flag (jitter > `jitter_px_max`, configs: qc.landmark_jitter_px_max),
    plus counts. `full_res_shape` (height, width) scales the jitter; defaults to the preview size.
    Protocol section 6.1.
    """
    if fps_target <= 0:
        raise ValueError("fps_target must be positive")
    period = 1.0 / float(fps_target)
    eps = 1e-6
    next_due: float | None = None
    rows: list[dict] = []
    preview_shape: tuple[int, int] | None = None
    n_seen = 0
    sources: dict[str, int] = {}
    for frame_idx, t_ref_s, rgb in preview_frames_iter:
        n_seen += 1
        t = float(t_ref_s)
        if next_due is None:
            next_due = t
        if t + eps < next_due:
            continue
        while next_due <= t + eps:
            next_due += period
        if preview_shape is None:
            preview_shape = (int(rgb.shape[0]), int(rgb.shape[1]))
        det = provider.detect(rgb, frame_idx) if provider is not None else None
        if det is None and fallback is not None:
            det = fallback.detect(rgb, frame_idx)
        if det is not None:
            sources[det["source"]] = sources.get(det["source"], 0) + 1
        rows.append(_row(frame_idx, t, det))
    df = landmarks_frame(rows)
    shape = full_res_shape or preview_shape or (1, 1)
    n_proc = len(df)
    n_det = int((df["source"] != "none").sum()) if n_proc else 0
    detect_frac = (n_det / n_proc) if n_proc else 0.0
    det_rows = df[df["source"] != "none"]
    jitter = landmark_jitter_px(df, shape)
    source = max(sources.items(), key=lambda kv: (kv[1], kv[0]))[0] if sources else "none"
    summary = {
        "hand_detected": bool(n_proc > 0 and detect_frac >= min_detect_frac),
        "hand_is_left": _majority(det_rows["is_left"].tolist()),
        "hand_palmar": _majority(det_rows["palmar"].tolist()),
        "landmark_source": source,
        "landmark_jitter_px": jitter,
        "motion_flag": bool(np.isfinite(jitter) and jitter > jitter_px_max),
        "landmark_jitter_px_max": float(jitter_px_max),
        "n_preview_frames": int(n_seen),
        "n_landmark_frames": int(n_proc),
        "n_detected": n_det,
        "detect_frac": float(detect_frac),
        "fps_target": float(fps_target),
        "full_res_shape": [int(shape[0]), int(shape[1])],
        "sources": sources,
    }
    return df, summary
