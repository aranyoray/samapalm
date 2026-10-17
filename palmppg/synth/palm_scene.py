"""Synthetic left palm, palmar view, over the dark box aperture (protocol sections 3, 4.2, 6.2, 8).

What the scene provides
  * a static linear-RGB reflectance image of a left palm (palm ellipse, four fingers, thumb) with the thumb
    lying on a pale Kardia card at the bottom-left, over a dark background;
  * the box illumination (cos^4 aperture vignetting plus a mild side gradient);
  * the LED block in the top-left corner (section 4.2: "a frame corner that never overlaps skin"), asserted;
  * a perfusion (AC amplitude) map: finger pads and thenar high, wrist low, thumb present but excluded
    downstream (section 6.2 ROI list, cfg `rois.excluded`);
  * 21 ground-truth landmarks in MediaPipe order, normalised to the half-resolution preview, and the ROI
    ground-truth masks for every name in cfg `rois.names` plus `thumb`;
  * an optional melanin level: multiplicative per-channel darkening of the skin, B attenuated most and R
    least. Any scene with melanin > 0 is labelled "synthetic tone shift" (section 8: supports no equity claim);
  * Bayer RGGB sampling with per-channel sensor responsivity, black level from cfg `pi.black_level`, 10-bit
    range from cfg `pi.white_level`, Poisson shot noise at a configurable full-well scale and Gaussian read noise.

Geometry is defined in "H units" (x and y divided by the image height, fingers pointing up, thumb to the
left) so that circles stay circular at any aspect ratio; landmarks are then normalised by width and height.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

LANDMARK_NAMES = (
    "WRIST", "THUMB_CMC", "THUMB_MCP", "THUMB_IP", "THUMB_TIP",
    "INDEX_FINGER_MCP", "INDEX_FINGER_PIP", "INDEX_FINGER_DIP", "INDEX_FINGER_TIP",
    "MIDDLE_FINGER_MCP", "MIDDLE_FINGER_PIP", "MIDDLE_FINGER_DIP", "MIDDLE_FINGER_TIP",
    "RING_FINGER_MCP", "RING_FINGER_PIP", "RING_FINGER_DIP", "RING_FINGER_TIP",
    "PINKY_MCP", "PINKY_PIP", "PINKY_DIP", "PINKY_TIP",
)
FINGERS = ("index", "middle", "ring", "little")
TONE_LABEL = "synthetic tone shift"

# linear-RGB reflectances (not protocol quantities; scene design)
SKIN_REFLECTANCE = (0.60, 0.40, 0.32)
CARD_REFLECTANCE = (0.62, 0.60, 0.57)        # pale card, kept below sensor saturation at skin exposure
BACKGROUND_REFLECTANCE = (0.025, 0.025, 0.03)
MELANIN_ABSORPTION = (0.6, 1.1, 1.6)         # per channel R, G, B: B attenuated most, R least
PERFUSION_WEIGHTS = {                          # relative AC amplitude per region (thenar = 1 after normalisation)
    "skin": 0.6, "forearm": 0.3, "volar_wrist": 0.3, "central_palm": 0.8, "hypothenar": 0.9, "thenar": 1.0,
    "prox": 0.9, "mid_phalanges": 1.0, "pad": 1.2, "thumb": 0.9,
}
REFERENCE_GEOMETRY_WH = (1536, 864)           # geometry the cfg pixel blocks are expressed in

# hand geometry in H units: fingers up, wrist at the bottom, thumb pointing down-left onto the card
HAND_GEOMETRY = {
    "palm_center": (0.95, 0.69), "palm_axes": (0.235, 0.245),
    "wrist": (0.97, 0.93), "forearm_end": (0.99, 1.12), "forearm_radius": 0.17,
    "mcp": {"index": (0.77, 0.47), "middle": (0.89, 0.45), "ring": (1.01, 0.47), "little": (1.12, 0.52)},
    "finger_dir": {"index": (-0.12, -1.0), "middle": (0.0, -1.0), "ring": (0.10, -1.0), "little": (0.25, -1.0)},
    "finger_len": {"index": 0.36, "middle": 0.40, "ring": 0.37, "little": 0.28},
    "finger_radius": {"index": 0.046, "middle": 0.048, "ring": 0.045, "little": 0.040},
    "segments": (0.45, 0.30, 0.25),            # MCP->PIP, PIP->DIP, DIP->TIP fractions of finger length
    "thumb": ((0.76, 0.76), (0.60, 0.82), (0.44, 0.87), (0.28, 0.91)),   # CMC, MCP, IP, TIP
    "thumb_radius": 0.052, "thumb_lift_shift": (-0.05, -0.23),   # lifted thumb rises beside the palm, clear of the thenar
    "thenar": ((0.80, 0.70), (0.10, 0.13)), "hypothenar": ((1.11, 0.74), (0.08, 0.14)),
    "central_palm": ((0.95, 0.62), (0.09, 0.10)),
    "card": (0.02, 0.80, 0.60, 0.995),         # x0, y0, x1, y1
}


# ----------------------------------------------------------------------------- small raster helpers
def _grid(width: int, height: int) -> tuple[np.ndarray, np.ndarray]:
    ys, xs = np.mgrid[0:height, 0:width]
    return (xs + 0.5) / height, (ys + 0.5) / height


def _ellipse(X, Y, c, axes) -> np.ndarray:
    return ((X - c[0]) / axes[0]) ** 2 + ((Y - c[1]) / axes[1]) ** 2 <= 1.0


def _capsule(X, Y, p0, p1, r) -> np.ndarray:
    px, py = p1[0] - p0[0], p1[1] - p0[1]
    L2 = px * px + py * py
    if L2 < 1e-12:
        return (X - p0[0]) ** 2 + (Y - p0[1]) ** 2 <= r * r
    t = np.clip(((X - p0[0]) * px + (Y - p0[1]) * py) / L2, 0.0, 1.0)
    dx = X - (p0[0] + t * px)
    dy = Y - (p0[1] + t * py)
    return dx * dx + dy * dy <= r * r


def _rect(X, Y, x0, y0, x1, y1) -> np.ndarray:
    return (X >= x0) & (X < x1) & (Y >= y0) & (Y < y1)


def _blur(img: np.ndarray, sigma_px: float) -> np.ndarray:
    if sigma_px <= 0:
        return img
    import cv2

    k = int(2 * round(3 * sigma_px) + 1)
    return cv2.GaussianBlur(img.astype(np.float32), (k, k), sigma_px, borderType=cv2.BORDER_REPLICATE)


def _similarity(points, scale: float, angle_deg: float, shift, pivot) -> list[tuple[float, float]]:
    a = math.radians(angle_deg)
    ca, sa = math.cos(a), math.sin(a)
    out = []
    for x, y in points:
        dx, dy = (x - pivot[0]) * scale, (y - pivot[1]) * scale
        out.append((pivot[0] + ca * dx - sa * dy + shift[0], pivot[1] + sa * dx + ca * dy + shift[1]))
    return out


def scale_block(block: dict, width: int, height: int, ref_wh: tuple[int, int] = REFERENCE_GEOMETRY_WH,
                min_px: int = 8) -> dict:
    """Scale a cfg pixel block (full-resolution reference geometry) to a synthetic frame size; coordinates are
    kept even so the block holds whole Bayer cells, and at least `min_px` wide/high."""
    sx, sy = width / ref_wh[0], height / ref_wh[1]
    x = 2 * int(round(block["x"] * sx / 2))
    y = 2 * int(round(block["y"] * sy / 2))
    w = max(min_px, 2 * int(round(block["w"] * sx / 2)))
    h = max(min_px, 2 * int(round(block["h"] * sy / 2)))
    x = max(0, min(x, width - w))
    y = max(0, min(y, height - h))
    return {"x": x, "y": y, "w": w, "h": h}


def block_slice(block: dict) -> tuple[slice, slice]:
    return slice(block["y"], block["y"] + block["h"]), slice(block["x"], block["x"] + block["w"])


# ----------------------------------------------------------------------------- the scene
@dataclass
class PalmScene:
    """Static scene with ground truth. Arrays are full-resolution Bayer geometry (height, width)."""

    width: int
    height: int
    reflectance: np.ndarray                 # (H, W, 3) linear RGB, thumb on the card
    reflectance_thumb_up: np.ndarray        # (H, W, 3) thumb lifted off the card
    illumination: np.ndarray                # (H, W), 1.0 at the frame centre
    ac_map: np.ndarray                      # (H, W) perfusion weights, thumb down (thenar mean = 1)
    ac_map_thumb_up: np.ndarray
    skin_mask: np.ndarray                   # (H, W) bool, thumb down
    skin_mask_thumb_up: np.ndarray          # (H, W) bool, thumb lifted
    region_masks: dict[str, np.ndarray]     # name -> (H, W) bool, cfg rois.names + thumb
    landmarks: np.ndarray                   # (21, 2) normalised (x, y) of the half-res preview
    led_block: dict
    thumb_block: dict
    card_rect: dict
    melanin: float
    sensor: dict
    geometry: dict = field(default_factory=dict)

    @property
    def tone_label(self) -> str | None:
        return TONE_LABEL if self.melanin > 0 else None

    def region_ac_means(self) -> dict[str, float]:
        """Mean perfusion weight per ROI (what the injected AC/DC in that ROI is relative to the G target)."""
        return {k: float(self.ac_map[m].mean()) if m.any() else float("nan") for k, m in self.region_masks.items()}

    def summary(self) -> dict:
        return {
            "width": self.width, "height": self.height, "led_block": self.led_block, "thumb_block": self.thumb_block,
            "card_rect": self.card_rect, "melanin": self.melanin, "tone_label": self.tone_label,
            "sensor": self.sensor, "region_ac_means": self.region_ac_means(),
            "region_pixels": {k: int(m.sum()) for k, m in self.region_masks.items()},
            "landmarks": {LANDMARK_NAMES[i]: [float(self.landmarks[i, 0]), float(self.landmarks[i, 1])] for i in range(21)},
            "geometry": self.geometry,
        }


def make_palm_scene(width: int, height: int, cfg, rng: np.random.Generator, melanin: float = 0.0,
                    hand_jitter: float = 0.0, led_block: dict | None = None, thumb_block: dict | None = None,
                    target_skin_g_dn: float = 450.0, full_well_e: float = 8000.0, read_noise_dn: float = 2.0,
                    responsivity: tuple[float, float, float] = (0.63, 1.0, 0.71), texture: float = 0.05) -> PalmScene:
    """Build the synthetic palm scene for a frame of `width` x `height` (full-resolution Bayer geometry).

    cfg supplies `sync.led_block.pi`, `sync.thumb_block.pi`, `pi.black_level`, `pi.white_level`, `rois.names`,
    `rois.excluded`. `melanin` in [0, 1] darkens the skin per channel (synthetic tone shift). `hand_jitter`
    (0..1) adds a per-participant similarity perturbation of the hand pose. `target_skin_g_dn` sets the
    exposure so that the central-palm G signal lands at that many DN above black (section 6.1 exposure).
    """
    if width % 4 or height % 2:
        raise ValueError("width must be a multiple of 4 and height even for CSI2P packing")
    g = HAND_GEOMETRY
    X, Y = _grid(width, height)
    black = float(cfg.get("pi.black_level"))
    white = float(cfg.get("pi.white_level"))
    led_block = led_block or scale_block(cfg.get("sync.led_block.pi"), width, height)
    thumb_block = thumb_block or scale_block(cfg.get("sync.thumb_block.pi"), width, height)

    # ---- per-participant pose jitter (similarity transform about the palm centre), thumb tip kept in its block
    pivot = g["palm_center"]
    for attempt in range(6):
        j = hand_jitter * (0.5 ** attempt)
        scale = float(1.0 + rng.uniform(-0.04, 0.04) * j)
        angle = float(rng.uniform(-5.0, 5.0) * j)
        shift = (float(rng.uniform(-0.03, 0.03) * j), float(rng.uniform(-0.02, 0.02) * j))
        tip = _similarity([g["thumb"][3]], scale, angle, shift, pivot)[0]
        u, v = tip[0] * height / width, tip[1]
        tb = thumb_block
        if tb["x"] / width + 0.02 <= u <= (tb["x"] + tb["w"]) / width - 0.02 and tb["y"] / height + 0.02 <= v <= (tb["y"] + tb["h"]) / height - 0.02:
            break
    else:  # pragma: no cover - fallback to the canonical pose
        scale, angle, shift = 1.0, 0.0, (0.0, 0.0)

    def T(points):
        return _similarity(points, scale, angle, shift, pivot)

    def T1(p):
        return T([p])[0]

    palm_c = T1(g["palm_center"])
    axes = (g["palm_axes"][0] * scale, g["palm_axes"][1] * scale)
    wrist = T1(g["wrist"])
    fore_end = T1(g["forearm_end"])
    mcp = {f: T1(g["mcp"][f]) for f in FINGERS}
    joints: dict[str, list[tuple[float, float]]] = {}
    a_rad = math.radians(angle)
    for f in FINGERS:
        dx, dy = g["finger_dir"][f]
        n = math.hypot(dx, dy)
        dx, dy = dx / n, dy / n
        dxr, dyr = math.cos(a_rad) * dx - math.sin(a_rad) * dy, math.sin(a_rad) * dx + math.cos(a_rad) * dy
        L = g["finger_len"][f] * scale
        pts = [mcp[f]]
        acc = 0.0
        for frac in g["segments"]:
            acc += frac
            pts.append((mcp[f][0] + dxr * L * acc, mcp[f][1] + dyr * L * acc))
        joints[f] = pts                      # MCP, PIP, DIP, TIP
    thumb = T(list(g["thumb"]))
    lift = g["thumb_lift_shift"]
    thumb_up = [(x + lift[0] * scale, y + lift[1] * scale) for x, y in thumb]
    r_f = {f: g["finger_radius"][f] * scale for f in FINGERS}
    r_t = g["thumb_radius"] * scale

    # ---- masks
    palm = _ellipse(X, Y, palm_c, axes)
    forearm = _capsule(X, Y, wrist, fore_end, g["forearm_radius"] * scale)
    fingers = {f: _capsule(X, Y, joints[f][0], (joints[f][3][0] - 0.0, joints[f][3][1]), r_f[f]) for f in FINGERS}
    # finger tips: shorten the capsule so the rounded end is the TIP landmark
    for f in FINGERS:
        p0, p3 = joints[f][0], joints[f][3]
        vx, vy = p3[0] - p0[0], p3[1] - p0[1]
        n = math.hypot(vx, vy)
        p_end = (p3[0] - vx / n * r_f[f], p3[1] - vy / n * r_f[f])
        fingers[f] = _capsule(X, Y, p0, p_end, r_f[f])
        joints[f] = [p0, joints[f][1], joints[f][2], p3]
    thumb_mask = np.zeros_like(palm)
    thumb_up_mask = np.zeros_like(palm)
    for pts, dst in ((thumb, thumb_mask), (thumb_up, thumb_up_mask)):
        for i in range(3):
            p1 = pts[i + 1]
            if i == 2:
                vx, vy = p1[0] - pts[i][0], p1[1] - pts[i][1]
                n = math.hypot(vx, vy)
                p1 = (p1[0] - vx / n * r_t, p1[1] - vy / n * r_t)
            dst |= _capsule(X, Y, pts[i], p1, r_t)
    hand_core = palm | forearm
    for f in FINGERS:
        hand_core |= fingers[f]
    skin_down = hand_core | thumb_mask
    skin_up = hand_core | thumb_up_mask
    card = _rect(X, Y, *g["card"])

    # ---- ROI ground truth (thumb-down pose)
    regions: dict[str, np.ndarray] = {}
    regions["thenar"] = _ellipse(X, Y, T1(g["thenar"][0]), (g["thenar"][1][0] * scale, g["thenar"][1][1] * scale)) & palm & ~thumb_mask
    regions["hypothenar"] = _ellipse(X, Y, T1(g["hypothenar"][0]), (g["hypothenar"][1][0] * scale, g["hypothenar"][1][1] * scale)) & palm
    regions["central_palm"] = _ellipse(X, Y, T1(g["central_palm"][0]), (g["central_palm"][1][0] * scale, g["central_palm"][1][1] * scale)) & palm
    mid = np.zeros_like(palm)
    for f in FINGERS:
        p0, p1, p2, p3 = joints[f]
        regions[f"prox_{f}"] = _capsule(X, Y, p0, p1, r_f[f]) & fingers[f]
        mid |= _capsule(X, Y, p1, p2, r_f[f]) & fingers[f]
        regions[f"pad_{f}"] = _capsule(X, Y, p2, p3, r_f[f]) & fingers[f]
    regions["mid_phalanges"] = mid
    wrist_band = _rect(X, Y, wrist[0] - 0.16 * scale, wrist[1] - 0.012, wrist[0] + 0.16 * scale, wrist[1] + 0.07 * scale)
    regions["volar_wrist"] = wrist_band & (palm | forearm) & ~thumb_mask
    whole = palm.copy()
    for f in FINGERS:
        whole |= fingers[f]
    regions["whole_palm"] = whole & ~thumb_mask
    regions["thumb"] = thumb_mask.copy()
    wanted = list(cfg.get("rois.names")) + list(cfg.get("rois.excluded"))
    missing = [n for n in wanted if n not in regions]
    if missing:
        raise RuntimeError(f"scene lacks ROI masks for {missing}")
    regions = {k: regions[k] for k in wanted}

    # ---- reflectance (linear RGB) with mild static texture, melanin darkening of skin only
    mel = np.exp(-float(melanin) * np.asarray(MELANIN_ABSORPTION))
    skin_rgb = np.asarray(SKIN_REFLECTANCE) * mel
    sigma_tex = max(1.0, 0.02 * height)
    tex = 1.0 + texture * (_blur(rng.standard_normal((height, width)).astype(np.float32), sigma_tex) * (sigma_tex * 1.8))
    tex = np.clip(tex, 0.8, 1.2).astype(np.float32)
    pad_boost = np.ones((height, width), np.float32)
    for f in FINGERS:
        pad_boost[regions[f"pad_{f}"]] = 1.06

    def compose(skin_mask, thumb_m):
        img = np.empty((height, width, 3), np.float32)
        img[:] = np.asarray(BACKGROUND_REFLECTANCE, np.float32)
        img[card] = np.asarray(CARD_REFLECTANCE, np.float32) * (0.97 + 0.06 * (X[card] - g["card"][0]) / 0.6)[:, None]
        sm = skin_mask
        img[sm] = (skin_rgb[None, :] * (tex[sm] * pad_boost[sm])[:, None]).astype(np.float32)
        img[thumb_m] = (skin_rgb[None, :] * 0.98 * tex[thumb_m][:, None]).astype(np.float32)
        return img

    refl_down = compose(skin_down, thumb_mask)
    refl_up = compose(skin_up, thumb_up_mask)

    # ---- LED block must never overlap skin (either pose)
    ys, xs = block_slice(led_block)
    if skin_down[ys, xs].any() or skin_up[ys, xs].any() or card[ys, xs].any():
        raise RuntimeError("LED block overlaps skin or card; move the hand or the block")

    # ---- illumination: cos^4 aperture vignetting about the frame centre + mild side gradient
    f_len = 1.9
    illum = aperture_illumination(width, height, f_len)

    # ---- perfusion map (AC amplitude weights), thenar mean normalised to 1
    def perfusion(skin_mask, thumb_m):
        w = np.zeros((height, width), np.float32)
        w[skin_mask] = PERFUSION_WEIGHTS["skin"]
        w[forearm & ~palm] = PERFUSION_WEIGHTS["forearm"]
        w[regions["volar_wrist"]] = PERFUSION_WEIGHTS["volar_wrist"]
        w[regions["central_palm"]] = PERFUSION_WEIGHTS["central_palm"]
        w[regions["hypothenar"]] = PERFUSION_WEIGHTS["hypothenar"]
        w[regions["thenar"]] = PERFUSION_WEIGHTS["thenar"]
        for f in FINGERS:
            w[regions[f"prox_{f}"]] = PERFUSION_WEIGHTS["prox"]
        w[regions["mid_phalanges"]] = PERFUSION_WEIGHTS["mid_phalanges"]
        for f in FINGERS:
            w[regions[f"pad_{f}"]] = PERFUSION_WEIGHTS["pad"]
        w[thumb_m] = PERFUSION_WEIGHTS["thumb"]
        w = _blur(w, max(1.0, 0.012 * height))
        w[~skin_mask] = 0.0
        return w

    ac_down = perfusion(skin_down, thumb_mask)
    ac_up = perfusion(skin_up, thumb_up_mask)
    th = regions["thenar"]
    norm = float(ac_down[th].mean())
    ac_down = (ac_down / norm).astype(np.float32)
    ac_up = (ac_up / norm).astype(np.float32)

    # ---- sensor model: exposure so that central-palm G reaches target_skin_g_dn above black
    cp = regions["central_palm"]
    g_centre = float((refl_down[..., 1] * illum)[cp].mean())
    exposure_scale = target_skin_g_dn / max(g_centre * responsivity[1], 1e-6)
    sensor = {
        "responsivity": [float(v) for v in responsivity], "black_level": black, "white_level": white,
        "full_well_e": float(full_well_e), "read_noise_dn": float(read_noise_dn), "exposure_scale": float(exposure_scale),
        "target_skin_g_dn": float(target_skin_g_dn), "e_per_dn": float(full_well_e / (white - black)),
    }

    # ---- landmarks (MediaPipe order) normalised to the preview: u = x_h * H / W, v = y_h
    lm = [wrist] + thumb
    for f in FINGERS:
        lm += joints[f]
    lmn = np.array([[x * height / width, y] for x, y in lm], dtype=float)

    geometry = {
        "scale": scale, "angle_deg": angle, "shift": list(shift), "palm_center": list(palm_c), "palm_axes": list(axes),
        "wrist": list(wrist), "thumb": [list(p) for p in thumb], "thumb_up": [list(p) for p in thumb_up],
        "joints": {f: [list(p) for p in joints[f]] for f in FINGERS}, "finger_radius": r_f, "thumb_radius": r_t,
        "card": list(g["card"]), "units": "x/H, y/H (H = frame height)", "vignette_f": f_len,
    }
    card_rect = {"x": int(g["card"][0] * height), "y": int(g["card"][1] * height),
                 "w": int((g["card"][2] - g["card"][0]) * height), "h": int((g["card"][3] - g["card"][1]) * height)}
    return PalmScene(width, height, refl_down, refl_up, illum, ac_down, ac_up, skin_down, skin_up, regions, lmn,
                     dict(led_block), dict(thumb_block), card_rect, float(melanin), sensor, geometry)


# ----------------------------------------------------------------------------- rendering and sampling
def bayer_channel_index(pattern: str = "RGGB") -> np.ndarray:
    """(2, 2) array of RGB channel indices for the Bayer pattern (0 = R, 1 = G, 2 = B)."""
    pattern = pattern.upper()
    if len(pattern) != 4 or set(pattern) - set("RGB"):
        raise ValueError(f"bad Bayer pattern {pattern}")
    idx = {"R": 0, "G": 1, "B": 2}
    return np.array([[idx[pattern[0]], idx[pattern[1]]], [idx[pattern[2]], idx[pattern[3]]]])


def mosaic_from_rgb(rgb: np.ndarray, pattern: str = "RGGB") -> np.ndarray:
    """Sample one channel per pixel from a full-resolution RGB image (section 6.1: planes stay separate)."""
    ci = bayer_channel_index(pattern)
    out = np.empty(rgb.shape[:2], dtype=rgb.dtype)
    for r in (0, 1):
        for c in (0, 1):
            out[r::2, c::2] = rgb[r::2, c::2, ci[r, c]]
    return out


def channel_mosaic(values: tuple[float, float, float] | np.ndarray, height: int, width: int, pattern: str = "RGGB") -> np.ndarray:
    """(H, W) array holding the per-channel value (R, G, B) at each Bayer position."""
    ci = bayer_channel_index(pattern)
    v = np.asarray(values, dtype=np.float32)
    out = np.empty((height, width), np.float32)
    for r in (0, 1):
        for c in (0, 1):
            out[r::2, c::2] = v[ci[r, c]]
    return out


def planes_from_mosaic(mosaic: np.ndarray, pattern: str = "RGGB") -> dict[str, np.ndarray]:
    """Split a mosaic into the four half-resolution planes named R, G1, G2, B (CONTRACTS section 3.1)."""
    names = {"RGGB": ("R", "G1", "G2", "B"), "BGGR": ("B", "G1", "G2", "R"), "GRBG": ("G1", "R", "B", "G2"),
             "GBRG": ("G1", "B", "R", "G2")}[pattern.upper()]
    quads = (mosaic[0::2, 0::2], mosaic[0::2, 1::2], mosaic[1::2, 0::2], mosaic[1::2, 1::2])
    return dict(zip(names, quads))


def linear_radiance(scene: PalmScene, thumb_up: bool = False) -> np.ndarray:
    """Reflectance x illumination (H, W, 3), linear, 1.0 = white card under the central illumination."""
    refl = scene.reflectance_thumb_up if thumb_up else scene.reflectance
    return refl * scene.illumination[..., None]


def bayer_dc_ac(scene: PalmScene, ac_dc_g: float, ac_ratios: dict | tuple, thumb_up: bool = False,
                pattern: str = "RGGB") -> tuple[np.ndarray, np.ndarray]:
    """DC image (DN above black) in the Bayer domain and the AC image such that frame = DC - AC * W(t).

    `ac_dc_g` is the peak-to-peak AC/DC at the thenar reference in the G planes; `ac_ratios` gives R:G:B
    relative amplitudes (G = 1), e.g. {"R": 0.5, "G": 1.0, "B": 0.6}.
    """
    rgb = linear_radiance(scene, thumb_up)
    resp = np.asarray(scene.sensor["responsivity"], np.float32) * scene.sensor["exposure_scale"]
    dc = mosaic_from_rgb((rgb * resp[None, None, :]).astype(np.float32), pattern)
    ratios = _ratio_tuple(ac_ratios)
    ac_map = scene.ac_map_thumb_up if thumb_up else scene.ac_map
    ac = dc * channel_mosaic(ratios, scene.height, scene.width, pattern) * (ac_dc_g * ac_map)
    return dc.astype(np.float32), ac.astype(np.float32)


def _ratio_tuple(ac_ratios) -> tuple[float, float, float]:
    if isinstance(ac_ratios, dict):
        return (float(ac_ratios.get("R", 0.5)), float(ac_ratios.get("G", 1.0)), float(ac_ratios.get("B", 0.6)))
    r = tuple(float(v) for v in ac_ratios)
    if len(r) != 3:
        raise ValueError("ac_ratios needs three values R, G, B")
    return r


def shot_read_noise(signal: np.ndarray, scale_e: float, read_sigma: float, rng: np.random.Generator) -> np.ndarray:
    """Add shot noise (variance signal / scale_e, i.e. Poisson at `scale_e` electrons per signal unit) and read
    noise (sigma `read_sigma`, signal units) with one Gaussian draw per pixel. The Gaussian approximation of the
    Poisson law is used because every rendered pixel carries more than about a hundred electrons."""
    sig = np.asarray(signal, dtype=np.float32)
    sigma = np.sqrt(np.maximum(sig, 0.0) / float(scale_e) + float(read_sigma) ** 2)
    return sig + sigma * rng.standard_normal(sig.shape, dtype=np.float32)


def add_sensor_noise(dn_above_black: np.ndarray, sensor: dict, rng: np.random.Generator, light_factor: float = 1.0) -> np.ndarray:
    """Shot noise at the full-well scale (lower `light_factor` = fewer electrons per DN = more noise), read noise,
    black level, 10-bit clip. Returns uint16 DN (section 6.1 sensor model)."""
    gain = float(sensor["e_per_dn"]) * float(light_factor)
    noisy = shot_read_noise(dn_above_black, gain, float(sensor["read_noise_dn"]), rng) + float(sensor["black_level"])
    return np.clip(np.rint(noisy), 0, float(sensor["white_level"])).astype(np.uint16)


def aperture_illumination(width: int, height: int, f_len: float = 1.9, side_gradient: float = 0.05) -> np.ndarray:
    """cos^4 vignetting about the frame centre (focal length `f_len` in H units) with a mild side gradient, 1 at
    the centre. Shared by the palm scene and the unit flat field."""
    X, Y = _grid(width, height)
    cx, cy = 0.5 * width / height, 0.5
    r2 = (X - cx) ** 2 + (Y - cy) ** 2
    illum = (1.0 / (1.0 + r2 / (f_len * f_len))) ** 2 * (1.0 + side_gradient * (X - cx))
    return (illum / illum[height // 2, width // 2]).astype(np.float32)


def preview_rgb(scene: PalmScene, thumb_up: bool = False) -> np.ndarray:
    """Half-resolution 8-bit sRGB preview (what the hand-landmark stage looks at), white balanced."""
    rgb = linear_radiance(scene, thumb_up)
    h, w = scene.height // 2, scene.width // 2
    small = rgb.reshape(h, 2, w, 2, 3).mean(axis=(1, 3))
    small = small / max(float(np.percentile(small, 99.5)), 1e-6)
    return (srgb_oetf(np.clip(small, 0, 1)) * 255.0 + 0.5).astype(np.uint8)


def srgb_oetf(lin: np.ndarray) -> np.ndarray:
    """sRGB opto-electronic transfer (linear -> encoded, both in 0..1)."""
    lin = np.asarray(lin, dtype=np.float32)
    return np.where(lin <= 0.0031308, 12.92 * lin, 1.055 * np.power(np.maximum(lin, 0.0031308), 1 / 2.4) - 0.055)


def srgb_eotf(enc: np.ndarray) -> np.ndarray:
    """Inverse sRGB transfer (encoded 0..1 -> linear-ish 0..1)."""
    enc = np.asarray(enc, dtype=np.float32)
    return np.where(enc <= 0.04045, enc / 12.92, np.power((np.maximum(enc, 0.04045) + 0.055) / 1.055, 2.4))


# ----------------------------------------------------------------------------- ground-truth files
def landmarks_record(scene: PalmScene, clip_id: str, frame_idx: int = 0, t_ref_s: float = 0.0) -> dict:
    """Landmark ground truth in the shape of CONTRACTS section 4 `landmarks.parquet` rows (lm00_x..lm20_z,
    normalised preview coordinates, z = 0) plus a named list; `source` = "synthetic_truth"."""
    rec = {"clip_id": clip_id, "source": "synthetic_truth", "order": "mediapipe", "normalised": True,
           "image_size": [scene.width // 2, scene.height // 2], "frame_idx": int(frame_idx), "t_ref_s": float(t_ref_s),
           "confidence": 1.0, "is_left": True, "palmar": True, "static": True,
           "landmarks": [{"name": LANDMARK_NAMES[i], "x": float(scene.landmarks[i, 0]), "y": float(scene.landmarks[i, 1]), "z": 0.0}
                         for i in range(21)]}
    for i in range(21):
        rec[f"lm{i:02d}_x"] = float(scene.landmarks[i, 0])
        rec[f"lm{i:02d}_y"] = float(scene.landmarks[i, 1])
        rec[f"lm{i:02d}_z"] = 0.0
    return rec


def write_landmarks(path: str | Path, scene: PalmScene, clip_id: str) -> Path:
    path = Path(path)
    path.write_text(json.dumps(landmarks_record(scene, clip_id), indent=1), encoding="utf-8")
    return path


def write_roi_masks(path: str | Path, scene: PalmScene) -> Path:
    """ROI ground-truth masks as a compressed npz (full-resolution Bayer geometry, bool), plus the thumb-up
    variants `thumb_up__skin` for the lift and `ac_map`."""
    path = Path(path)
    arrays = {k: v.astype(bool) for k, v in scene.region_masks.items()}
    arrays["skin"] = scene.skin_mask.astype(bool)
    arrays["ac_map"] = scene.ac_map.astype(np.float32)
    arrays["thumb_up__skin"] = scene.skin_mask_thumb_up.astype(bool)
    np.savez_compressed(path, **arrays)
    return path
