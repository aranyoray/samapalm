"""One reference clock per participant and affine maps from every other stream onto it.

Reference clock: the recording Pi's CLOCK_BOOTTIME in nanoseconds (`mono_ns`, which is also what
picamera2 reports as SensorTimestamp). Every time in analysis code is a float number of seconds
on the reference clock relative to `t0_ref_ns` (the first Pi frame of the clip), so values stay
small and a clip always starts near zero.

Rules encoded here (section 4 of the protocol):
  * wall clock is for coarse alignment and audit only, never for beat alignment
    (`ClockMap.method == 'wall_clock'` can never yield sync grade 'fine');
  * every map carries a stated uncertainty and the method that produced it;
  * analysis windows come from sync events, never from hard-coded times.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Literal

import numpy as np

SyncGrade = Literal["fine", "coarse", "none"]
SYNC_GRADES: tuple[str, ...] = ("fine", "coarse", "none")

# Methods, from best to worst. Only the first group can support a 'fine' grade.
FINE_METHODS = {"led_pattern", "audio_beep", "artefact_lift", "identity"}
COARSE_METHODS = {"thumb_contact", "xcorr_hr", "wall_clock", "file_mtime"}


@dataclass
class ClockMap:
    """ref_s = native_s * (1 + drift) + offset_s  (native_s in the stream's own seconds)."""

    stream: str
    offset_s: float
    drift: float = 0.0
    uncertainty_s: float = float("inf")
    method: str = "wall_clock"
    n_anchors: int = 0
    residual_rms_s: float | None = None
    residual_max_s: float | None = None
    notes: str = ""

    def to_ref(self, t_native):
        return np.asarray(t_native, dtype=float) * (1.0 + self.drift) + self.offset_s

    def from_ref(self, t_ref):
        return (np.asarray(t_ref, dtype=float) - self.offset_s) / (1.0 + self.drift)

    @property
    def is_fine_capable(self) -> bool:
        return self.method in FINE_METHODS

    @staticmethod
    def identity(stream: str) -> "ClockMap":
        return ClockMap(stream=stream, offset_s=0.0, drift=0.0, uncertainty_s=0.0, method="identity", n_anchors=0)

    @staticmethod
    def fit(native_s: Iterable[float], ref_s: Iterable[float], stream: str, method: str,
            fit_drift: bool = True, uncertainty_s: float | None = None) -> "ClockMap":
        """Least-squares offset (+ optional drift) from paired anchors."""
        x = np.asarray(list(native_s), dtype=float)
        y = np.asarray(list(ref_s), dtype=float)
        if x.size == 0:
            raise ValueError("no anchors")
        if x.size == 1 or not fit_drift:
            drift = 0.0
            offset = float(np.mean(y - x))
        else:
            slope, intercept = np.polyfit(x, y, 1)
            drift = float(slope - 1.0)
            offset = float(intercept)
        resid = y - (x * (1.0 + drift) + offset)
        rms = float(np.sqrt(np.mean(resid**2))) if resid.size else 0.0
        mx = float(np.max(np.abs(resid))) if resid.size else 0.0
        unc = uncertainty_s if uncertainty_s is not None else max(rms, 1e-6)
        return ClockMap(stream, offset, drift, unc, method, int(x.size), rms, mx)


@dataclass
class Event:
    kind: str                 # clip_start, clip_end, p1_onset, p2_onset, thumb_contact, thumb_lift, ecg_artefact, bp1, bp2, bp3, ...
    t_ref_s: float
    uncertainty_s: float
    source: str               # e.g. 'sync_events.csv', 'pi_video', 'phone_audio', 'ecg', 'crf'
    detail: dict = field(default_factory=dict)


@dataclass
class Window:
    start_s: float
    end_s: float
    reason: str = ""

    @property
    def duration_s(self) -> float:
        return max(0.0, self.end_s - self.start_s)

    def contains(self, t) -> np.ndarray:
        t = np.asarray(t, dtype=float)
        return (t >= self.start_s) & (t < self.end_s)


@dataclass
class Timeline:
    study_id: str
    clip_id: str
    t0_ref_ns: int                                   # reference-clock origin (first Pi frame SensorTimestamp)
    ref_clock: str = "pi_mono_ns"
    maps: dict[str, ClockMap] = field(default_factory=dict)
    events: list[Event] = field(default_factory=list)
    exclusions: list[Window] = field(default_factory=list)
    analysis_window: Window | None = None
    sync_grade: str = "none"
    sync_detail: dict = field(default_factory=dict)
    capture_mode: str = "simultaneous"

    # ------------------------------------------------------------------ construction helpers
    def ns_to_s(self, mono_ns) -> np.ndarray:
        return (np.asarray(mono_ns, dtype=np.int64) - np.int64(self.t0_ref_ns)) / 1e9

    def s_to_ns(self, t_ref_s) -> np.ndarray:
        return (np.asarray(t_ref_s, dtype=float) * 1e9).astype(np.int64) + np.int64(self.t0_ref_ns)

    def set_map(self, m: ClockMap) -> None:
        self.maps[m.stream] = m

    def to_ref(self, stream: str, t_native) -> np.ndarray:
        if stream not in self.maps:
            raise KeyError(f"no clock map for stream '{stream}' (have {sorted(self.maps)})")
        return self.maps[stream].to_ref(t_native)

    def add_event(self, kind: str, t_ref_s: float, uncertainty_s: float, source: str, **detail) -> Event:
        ev = Event(kind, float(t_ref_s), float(uncertainty_s), source, dict(detail))
        self.events.append(ev)
        return ev

    def event(self, kind: str) -> Event | None:
        best = None
        for ev in self.events:
            if ev.kind == kind and (best is None or ev.uncertainty_s < best.uncertainty_s):
                best = ev
        return best

    def add_exclusion(self, start_s: float, end_s: float, reason: str) -> None:
        self.exclusions.append(Window(float(start_s), float(end_s), reason))

    def valid_mask(self, t_ref_s) -> np.ndarray:
        """True where t is inside the analysis window and outside every exclusion."""
        t = np.asarray(t_ref_s, dtype=float)
        if self.analysis_window is None:
            mask = np.ones_like(t, dtype=bool)
        else:
            mask = self.analysis_window.contains(t)
        for w in self.exclusions:
            mask &= ~w.contains(t)
        return mask

    # ------------------------------------------------------------------ protocol logic
    def derive_analysis_window(self, static_colour_s: float, tail_exclusion_s: float,
                               clip_start_s: float | None = None, clip_end_s: float | None = None) -> Window:
        """Analysis window = [clip_start + static_colour_s, P2 onset] (P2 marks the fine-anchor lift).

        Falls back to clip_end - tail_exclusion_s when P2 was not detected. Never hard-coded times:
        clip start/end and P2 come from events (sync_events.csv or detections).
        """
        start_ev = self.event("clip_start")
        end_ev = self.event("clip_end")
        p2 = self.event("p2_onset")
        cs = clip_start_s if clip_start_s is not None else (start_ev.t_ref_s if start_ev else 0.0)
        if clip_end_s is not None:
            ce = clip_end_s
        elif end_ev is not None:
            ce = end_ev.t_ref_s
        else:
            raise ValueError("clip end unknown: pass clip_end_s or add a clip_end event")
        end = p2.t_ref_s if p2 is not None else ce - tail_exclusion_s
        end = min(end, ce - tail_exclusion_s) if p2 is None else end
        self.analysis_window = Window(cs + static_colour_s, end, "protocol window (static colour head, fine-anchor tail excluded)")
        self.add_exclusion(end, ce + 1.0, "fine-anchor lift and tail")
        return self.analysis_window

    def grade(self, fine_anchor_found: bool, p1_found: bool, p2_found: bool, xcorr_agree: bool | None,
              coarse_anchor_found: bool, ecg_map_method: str | None = None, xcorr_tolerance_s: float = 0.3) -> str:
        """Section 4.4. `xcorr_agree` None means the cross-correlation could not be computed (treated as not agreeing)."""
        if fine_anchor_found and p1_found and p2_found and bool(xcorr_agree) and (ecg_map_method in FINE_METHODS or ecg_map_method is None):
            g = "fine"
        elif coarse_anchor_found or (ecg_map_method in COARSE_METHODS):
            g = "coarse"
        else:
            g = "none"
        self.sync_grade = g
        self.sync_detail.update({
            "fine_anchor_found": bool(fine_anchor_found), "p1_found": bool(p1_found), "p2_found": bool(p2_found),
            "xcorr_agree": None if xcorr_agree is None else bool(xcorr_agree),
            "coarse_anchor_found": bool(coarse_anchor_found), "ecg_map_method": ecg_map_method,
            "xcorr_tolerance_s": xcorr_tolerance_s,
        })
        return g

    @property
    def beat_level_ecg_allowed(self) -> bool:
        return self.sync_grade == "fine"

    # ------------------------------------------------------------------ serialisation
    def to_dict(self) -> dict:
        return {
            "study_id": self.study_id, "clip_id": self.clip_id, "t0_ref_ns": int(self.t0_ref_ns), "ref_clock": self.ref_clock,
            "maps": {k: asdict(v) for k, v in self.maps.items()},
            "events": [asdict(e) for e in self.events],
            "exclusions": [asdict(w) for w in self.exclusions],
            "analysis_window": asdict(self.analysis_window) if self.analysis_window else None,
            "sync_grade": self.sync_grade, "sync_detail": self.sync_detail, "capture_mode": self.capture_mode,
        }

    def save(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(self.to_dict(), indent=2, default=_json_default), encoding="utf-8")

    @classmethod
    def from_dict(cls, d: dict) -> "Timeline":
        tl = cls(d["study_id"], d["clip_id"], int(d["t0_ref_ns"]), d.get("ref_clock", "pi_mono_ns"))
        tl.maps = {k: ClockMap(**v) for k, v in d.get("maps", {}).items()}
        tl.events = [Event(**e) for e in d.get("events", [])]
        tl.exclusions = [Window(**w) for w in d.get("exclusions", [])]
        tl.analysis_window = Window(**d["analysis_window"]) if d.get("analysis_window") else None
        tl.sync_grade = d.get("sync_grade", "none")
        tl.sync_detail = d.get("sync_detail", {})
        tl.capture_mode = d.get("capture_mode", "simultaneous")
        return tl

    @classmethod
    def load(cls, path: str | Path) -> "Timeline":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)


# ---------------------------------------------------------------------- uniform grid helpers
def uniform_grid(start_s: float, end_s: float, fs: float) -> np.ndarray:
    n = int(np.floor((end_s - start_s) * fs)) + 1
    return start_s + np.arange(max(n, 0)) / fs


def detect_drops(t_s: np.ndarray, nominal_fs: float, factor: float = 1.5) -> dict:
    """Gap-based frame-drop detection on true frame times (never on frame index)."""
    t = np.asarray(t_s, dtype=float)
    if t.size < 2:
        return {"n_frames": int(t.size), "n_dropped": 0, "drop_pct": 0.0, "gaps_idx": [], "median_period_s": np.nan}
    d = np.diff(t)
    period = 1.0 / nominal_fs
    med = float(np.median(d))
    gaps = np.where(d > factor * period)[0]
    n_dropped = int(np.sum(np.round(d[gaps] / period) - 1)) if gaps.size else 0
    expected = int(round((t[-1] - t[0]) / period)) + 1
    drop_pct = 100.0 * n_dropped / max(expected, 1)
    return {"n_frames": int(t.size), "n_dropped": n_dropped, "drop_pct": float(drop_pct),
            "gaps_idx": gaps.tolist(), "median_period_s": med, "expected_frames": expected}


def resample_to_grid(t_s: np.ndarray, values: np.ndarray, grid_s: np.ndarray, max_gap_s: float | None = None) -> np.ndarray:
    """Linear resampling onto a uniform grid, NaN inside gaps wider than max_gap_s (drops stay visible)."""
    t = np.asarray(t_s, dtype=float)
    v = np.asarray(values, dtype=float)
    out = np.interp(grid_s, t, v, left=np.nan, right=np.nan)
    if max_gap_s is not None and t.size > 1:
        d = np.diff(t)
        for i in np.where(d > max_gap_s)[0]:
            out[(grid_s > t[i]) & (grid_s < t[i + 1])] = np.nan
    return out
