"""ECG anchors on the video side (protocol section 4.3): thumb contact (coarse), thumb lift (fine),
wall-clock cross-check, and the ClockMaps they produce.

* Coarse: the frame the left thumb lands on the Kardia card = ECG t0, uncertainty about 1 s (app latency).
* Wall clock: ``kardia_meta.start_wall_ts`` corrected by the day's clock offsets; disagreement with the
  coarse anchor above ``clock.wall_vs_meta_disagreement_s`` is a data-entry error flag.
* Fine: the thumb-lift transient at P2 in the thumb pixel block paired with the ECG baseline artefact
  onset (detected by the ECG package); uncertainty one frame period.

All inputs are block traces (per-frame mean of the thumb block, any plane) with their frame times; no
frames are held here.
"""
from __future__ import annotations

import datetime as dt
from collections.abc import Mapping

import numpy as np
from scipy.ndimage import median_filter

from palmppg.core.timeline import ClockMap

DEFAULTS = {
    "sync.thumb.min_segment_s": 0.5,      # shortest segment on either side of the contact step
    "sync.thumb.min_r2": 0.2,             # fraction of trace variance the single step must explain
    "sync.thumb.min_snr": 4.0,            # step height over residual sigma
    "sync.lift.search_s": [-1.0, 4.0],    # thumb-lift search window relative to the P2 onset
    "sync.lift.median_frames": 3,         # median filter before the first difference
    "sync.lift.first_fraction": 0.5,      # earliest |diff| >= fraction * max is the lift (not the put-back)
    "clock.kardia_tz_offset_h": 0.0,      # applied to a naive (no tz) Kardia start_wall_ts
}


def _median_period(t: np.ndarray) -> float:
    d = np.diff(t)
    d = d[np.isfinite(d) & (d > 0)]
    return float(np.median(d)) if d.size else 1.0 / 30.0


# --------------------------------------------------------------------------- coarse anchor
def thumb_contact_frame(t_s, intensity, frame_idx=None, uncertainty_s: float = 1.0,
                        min_segment_s: float | None = None, min_r2: float | None = None,
                        min_snr: float | None = None, search_window: tuple[float, float] | None = None) -> dict:
    """Frame where the thumb lands on the card: the largest sustained level shift of the thumb block
    (section 4.3, coarse anchor).

    Single change-point least squares (the CUSUM statistic maximised over the split index): the split
    ``k`` minimising SSE(left) + SSE(right) with at least ``min_segment_s`` on each side. Returns
    ``{t_s, frame_idx, confidence (R^2 of the step), shift, snr, found, uncertainty_s}``; ``t_s`` is the time
    of the first frame after the step, ``found`` requires R^2 >= min_r2 and snr >= min_snr. When nothing
    anchors, ``found`` is False and the caller falls back to the wall clock.
    """
    min_segment_s = DEFAULTS["sync.thumb.min_segment_s"] if min_segment_s is None else float(min_segment_s)
    min_r2 = DEFAULTS["sync.thumb.min_r2"] if min_r2 is None else float(min_r2)
    min_snr = DEFAULTS["sync.thumb.min_snr"] if min_snr is None else float(min_snr)
    t = np.asarray(t_s, dtype=float)
    y = np.asarray(intensity, dtype=float)
    fidx = np.arange(t.size, dtype=np.int64) if frame_idx is None else np.asarray(frame_idx, dtype=np.int64)
    keep = np.isfinite(t) & np.isfinite(y)
    if search_window is not None:
        keep &= (t >= search_window[0]) & (t <= search_window[1])
    t, y, fidx = t[keep], y[keep], fidx[keep]
    empty = {"t_s": None, "frame_idx": None, "confidence": 0.0, "shift": 0.0, "snr": 0.0, "found": False,
             "uncertainty_s": float(uncertainty_s), "r2": 0.0}
    n = y.size
    period = _median_period(t)
    m = max(2, round(min_segment_s / period))
    if n < 2 * m + 1:
        return empty
    cs = np.concatenate([[0.0], np.cumsum(y)])
    cs2 = np.concatenate([[0.0], np.cumsum(y * y)])
    k = np.arange(m, n - m + 1)                     # split: left = y[:k], right = y[k:]
    sl, sl2 = cs[k], cs2[k]
    sr, sr2 = cs[n] - cs[k], cs2[n] - cs2[k]
    sse = (sl2 - sl**2 / k) + (sr2 - sr**2 / (n - k))
    j = int(np.argmin(sse))
    kb = int(k[j])
    sst = float(cs2[n] - cs[n] ** 2 / n)
    r2 = float(1.0 - sse[j] / sst) if sst > 0 else 0.0
    shift = float(sr[j] / (n - kb) - sl[j] / kb)
    sigma = float(np.sqrt(max(sse[j], 1e-18) / max(n - 2, 1)))
    snr = abs(shift) / max(sigma, 1e-12)
    found = bool(r2 >= min_r2 and snr >= min_snr)
    return {"t_s": float(t[kb]), "frame_idx": int(fidx[kb]), "confidence": float(np.clip(r2, 0.0, 1.0)),
            "shift": shift, "snr": float(snr), "found": found, "uncertainty_s": float(uncertainty_s), "r2": r2,
            "t_before_s": float(t[kb - 1])}


def coarse_ecg_map(thumb_contact_t_ref_s: float, ecg_native_t0: float = 0.0,
                   uncertainty_s: float = 1.0) -> ClockMap:
    """ECG native time -> reference clock from the thumb-contact frame (section 4.3, coarse anchor):
    ECG sample at ``ecg_native_t0`` is placed at the thumb-contact time; no drift; uncertainty
    ``sync.coarse_anchor_uncertainty_s`` (app start latency)."""
    return ClockMap(stream="ecg", offset_s=float(thumb_contact_t_ref_s) - float(ecg_native_t0), drift=0.0,
                    uncertainty_s=float(uncertainty_s), method="thumb_contact", n_anchors=1,
                    notes="ECG t0 at the thumb-contact frame")


# --------------------------------------------------------------------------- wall clock cross-check
def parse_wall_ts_ns(ts, naive_tz_offset_h: float = 0.0) -> int:
    """ISO8601 string (or epoch seconds / ns) -> epoch nanoseconds. A naive timestamp is interpreted as
    UTC shifted by ``naive_tz_offset_h`` (the Kardia device clock convention, see decisions)."""
    if isinstance(ts, (int, np.integer)):
        return int(ts)
    if isinstance(ts, (float, np.floating)):
        return round(ts * 1e9) if ts < 1e12 else int(ts)
    s = str(ts).strip().replace("Z", "+00:00")
    d = dt.datetime.fromisoformat(s)
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone(dt.timedelta(hours=float(naive_tz_offset_h))))
    epoch = dt.datetime(1970, 1, 1, tzinfo=dt.UTC)
    delta = d - epoch
    return int(delta.days * 86_400_000_000_000 + delta.seconds * 1_000_000_000 + delta.microseconds * 1000)


def wall_clock_ecg_map(kardia_start_wall_ts, pi_meta: Mapping, t0_ref_ns: int,
                       day_offsets_ms: Mapping[str, float] | None = None, uncertainty_s: float = 1.0,
                       naive_tz_offset_h: float | None = None, pi_device: str | None = None,
                       kardia_device: str = "kardia_tablet") -> ClockMap:
    """ECG native time -> reference clock via wall clocks only (section 4.3 cross-check; audit grade).

    ``day_offsets_ms`` are the day's ``clock_sync_log.csv`` offsets ``offset_ms_vs_phone`` (device clock
    minus phone clock) keyed by device; the Kardia wall time is moved onto the Pi wall clock
    (``kardia - off_kardia + off_pi``), then onto the Pi monotonic clock with the clip meta pair
    ``start_wall_ns``/``start_mono_ns``. Method ``wall_clock`` can never support grade ``fine`` (D-004).
    """
    naive = DEFAULTS["clock.kardia_tz_offset_h"] if naive_tz_offset_h is None else float(naive_tz_offset_h)
    k_wall = parse_wall_ts_ns(kardia_start_wall_ts, naive)
    offs = dict(day_offsets_ms or {})
    pi_device = pi_device or pi_meta.get("unit_id") or "pi"
    off_k = float(offs.get(kardia_device, 0.0))
    off_pi = float(offs.get(pi_device, offs.get(f"pi_{pi_device}", 0.0)))
    pi_wall_ns = k_wall - round(off_k * 1e6) + round(off_pi * 1e6)
    wall_minus_mono = int(pi_meta["start_wall_ns"]) - int(pi_meta["start_mono_ns"])
    mono_ns = pi_wall_ns - wall_minus_mono
    offset_s = (mono_ns - int(t0_ref_ns)) / 1e9
    return ClockMap(stream="ecg", offset_s=float(offset_s), drift=0.0, uncertainty_s=float(uncertainty_s),
                    method="wall_clock", n_anchors=1,
                    notes=f"kardia start_wall_ts via day offsets (kardia {off_k:+.0f} ms, pi {off_pi:+.0f} ms)")


def compare_anchors(coarse: ClockMap | None, wall: ClockMap | None, threshold_s: float) -> dict:
    """``{disagreement_s, flag}``: |coarse offset - wall offset|, flagged above
    ``clock.wall_vs_meta_disagreement_s`` (a data-entry error, section 4.3)."""
    if coarse is None or wall is None:
        return {"disagreement_s": None, "flag": False, "threshold_s": float(threshold_s), "comparable": False}
    d = float(abs(coarse.offset_s - wall.offset_s))
    return {"disagreement_s": d, "flag": bool(d > threshold_s), "threshold_s": float(threshold_s), "comparable": True}


# --------------------------------------------------------------------------- fine anchor
def thumb_lift_event(t_s, intensity, search_window: tuple[float, float], frame_idx=None,
                     median_frames: int | None = None, first_fraction: float | None = None,
                     k_mad: float = 8.0) -> dict:
    """Thumb-lift transient near P2: largest absolute first difference of the (median-filtered) thumb block
    inside ``search_window`` (section 4.3, fine anchor, video side).

    The lift and the put-back both produce a jump; the earliest jump of at least ``first_fraction`` of
    the largest one is taken so the lift (which the ECG artefact detector also sees first) is chosen.
    Returns ``{t_s, frame_idx, confidence, z, found}`` with ``t_s`` midway between the last frame before and
    the first frame after the jump, and ``found`` = z >= k_mad (``sync.artefact.k_mad``).
    """
    median_frames = DEFAULTS["sync.lift.median_frames"] if median_frames is None else int(median_frames)
    first_fraction = DEFAULTS["sync.lift.first_fraction"] if first_fraction is None else float(first_fraction)
    t = np.asarray(t_s, dtype=float)
    y = np.asarray(intensity, dtype=float)
    fidx = np.arange(t.size, dtype=np.int64) if frame_idx is None else np.asarray(frame_idx, dtype=np.int64)
    keep = np.isfinite(t) & np.isfinite(y) & (t >= search_window[0]) & (t <= search_window[1])
    t, y, fidx = t[keep], y[keep], fidx[keep]
    empty = {"t_s": None, "frame_idx": None, "confidence": 0.0, "z": 0.0, "found": False, "jump": 0.0}
    if y.size < 4:
        return empty
    if median_frames >= 3:
        y = median_filter(y, size=int(median_frames) | 1, mode="nearest")
    d = np.diff(y)
    mag = np.abs(d)
    sigma = max(float(1.4826 * np.median(np.abs(d - np.median(d)))), 1e-12)
    peak = float(mag.max())
    cands = np.where(mag >= first_fraction * peak)[0]
    i = int(cands[0]) if cands.size else int(np.argmax(mag))
    z = float(mag[i] / sigma)
    found = bool(z >= k_mad)
    return {"t_s": float(0.5 * (t[i] + t[i + 1])), "frame_idx": int(fidx[i + 1]), "frame_before": int(fidx[i]),
            "confidence": float(1.0 - np.exp(-z / max(k_mad, 1e-9))), "z": z, "found": found, "jump": float(d[i]),
            "period_s": float(t[i + 1] - t[i])}


def fine_ecg_map(video_lift_t_ref_s: float, ecg_artefact_t_ecg_s: float, uncertainty_s: float) -> ClockMap:
    """ECG native -> reference clock from the fine anchor: offset = video lift time minus ECG artefact
    onset (section 4.3); uncertainty one frame period (``sync.fine_anchor_uncertainty_s``); no drift
    (a 60 s clip cannot resolve ECG clock drift)."""
    return ClockMap(stream="ecg", offset_s=float(video_lift_t_ref_s) - float(ecg_artefact_t_ecg_s), drift=0.0,
                    uncertainty_s=float(uncertainty_s), method="artefact_lift", n_anchors=1,
                    notes="thumb-lift frame paired with ECG baseline artefact onset")
