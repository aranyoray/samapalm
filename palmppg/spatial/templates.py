"""A hand-shaped 21-landmark template in normalised image coordinates (sections 6.1, 6.2 fixtures).

The template is a LEFT hand seen palm-on (palmar) in a non-mirrored image with the fingers pointing
up: wrist near the bottom centre, four fingers above the palm, thumb to the image RIGHT (the
left_thumb_right convention of `palmppg.spatial.landmarks`). It gives synthetic generators and tests a
plausible landmark set; `transform_landmarks` turns it into other hands, poses and jitters.
"""
from __future__ import annotations

import numpy as np

from palmppg.spatial.rois import N_LANDMARKS

_LEFT_PALMAR_FINGERS_UP: tuple[tuple[float, float], ...] = (
    (0.50, 0.90),                                                     # 0 wrist
    (0.60, 0.82), (0.68, 0.72), (0.74, 0.64), (0.79, 0.57),           # 1-4 thumb CMC, MCP, IP, TIP
    (0.60, 0.55), (0.62, 0.42), (0.63, 0.33), (0.64, 0.25),           # 5-8 index
    (0.51, 0.53), (0.51, 0.39), (0.51, 0.29), (0.51, 0.20),           # 9-12 middle
    (0.42, 0.55), (0.41, 0.42), (0.40, 0.33), (0.39, 0.26),           # 13-16 ring
    (0.34, 0.60), (0.32, 0.50), (0.31, 0.43), (0.30, 0.37),           # 17-20 little
)


def hand_template_landmarks(is_left: bool = True, palmar: bool = True, mirror: bool = False) -> np.ndarray:
    """(21, 3) normalised landmarks of a hand with the fingers up; z = 0.

    `is_left=False` or `palmar=False` flips the thumb to the other side (a right palmar hand and a left
    dorsal hand look alike in 2D); `mirror=True` flips horizontally once more to emulate a selfie preview.
    """
    lm = np.zeros((N_LANDMARKS, 3), dtype=float)
    lm[:, :2] = np.asarray(_LEFT_PALMAR_FINGERS_UP, dtype=float)
    flips = int(not is_left) + int(not palmar) + int(mirror)
    if flips % 2 == 1:
        lm[:, 0] = 1.0 - lm[:, 0]
    return lm


def transform_landmarks(
    lm: np.ndarray, rotate_deg: float = 0.0, scale: float = 1.0, shift: tuple[float, float] = (0.0, 0.0),
    centre: tuple[float, float] | None = None,
) -> np.ndarray:
    """Rotate (about `centre`, default the wrist), scale and shift normalised landmarks; z untouched."""
    a = np.asarray(lm, dtype=float).copy()
    c = np.asarray(centre if centre is not None else a[0, :2], dtype=float)
    th = np.deg2rad(rotate_deg)
    rot = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
    a[:, :2] = (a[:, :2] - c) @ rot.T * float(scale) + c + np.asarray(shift, dtype=float)
    return a
