"""Clip windows for the learned extractors, with participant-level splits (protocol 6.3, 10, 11.1).

`ClipRecord` points at one clip of one camera: a proxy video (`proxy_128x72.zarr`, (n, 72, 128, 3)
uint8, CONTRACTS section 4) and/or an STMap source (`patches.zarr`, (n, rows, cols, ch)), plus the
target pulse (a column of `pulse.parquet`, the `best` entry of `pulse_sqi.json`, or an in-memory
synthetic ground truth). `ClipDataset` cuts fixed windows (`window_frames`, `step_frames`) and reads
only the frames of one window per `__getitem__` (never a whole clip, CONTRACTS section 0.6).
`participant_folds` / `split_records` make grouped folds by `study_id`; the trainer refuses any
train / validation pair that shares a participant. torch is imported lazily (collate / loader).
"""
from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from palmppg.core.config import rng
from palmppg.core.timeline import resample_to_grid

MODES = ("video", "stmap")


class SplitViolation(RuntimeError):
    """Raised when training and validation data share a participant (protocol 11.1)."""


# --------------------------------------------------------------------------- records
@dataclass
class ClipRecord:
    study_id: str
    clip_id: str = "clip1"
    camera: str = "phone"
    video: object = None          # (n, H, W, 3) uint8 array or path to proxy zarr
    stmap: object = None          # (n, P, ch) / (n, rows, cols, ch) float array or path to patches.zarr
    target: object = None         # (n,) float array, or path to pulse.parquet
    target_column: str | None = None
    t_ref_s: np.ndarray | None = None
    valid: np.ndarray | None = None
    meta: dict = field(default_factory=dict)

    # --- lazy accessors (zarr arrays stay on disk) ---
    def _open(self, src):
        if isinstance(src, (str, Path)):
            import zarr

            return zarr.open_array(str(src), mode="r")
        return src

    def n_frames(self, mode: str = "video") -> int:
        src = self.video if mode == "video" else self.stmap
        if src is None:
            raise ValueError(f"record {self.study_id}/{self.clip_id} has no {mode} source")
        return int(self._open(src).shape[0])

    def frame_times(self, mode: str = "video") -> np.ndarray | None:
        if self.t_ref_s is not None:
            return np.asarray(self.t_ref_s, dtype=float)
        src = self.video if mode == "video" else self.stmap
        if isinstance(src, (str, Path)):
            attrs = dict(self._open(src).attrs.asdict())
            if "t_ref_s" in attrs:
                return np.asarray(attrs["t_ref_s"], dtype=float)
        return None

    def read(self, mode: str, start: int, stop: int) -> np.ndarray:
        src = self.video if mode == "video" else self.stmap
        return np.asarray(self._open(src)[start:stop])

    def load_target(self, mode: str = "video") -> np.ndarray:
        """(n,) float target aligned to the frames: an array as given; a pulse.parquet column resampled by
        `t_ref_s` onto the frame times (nearest grid sample, NaN beyond 1.5 grid periods)."""
        n = self.n_frames(mode)
        if self.target is None:
            return np.full(n, np.nan)
        if not isinstance(self.target, (str, Path)):
            y = np.asarray(self.target, dtype=float)
            if y.size != n:
                raise ValueError(f"target has {y.size} samples for {n} frames")
            return y
        path = Path(self.target)
        df = pd.read_parquet(path)
        col = self.target_column
        if col in (None, "best"):
            sqi_path = path.parent / "pulse_sqi.json"
            if sqi_path.exists():
                col = json.loads(sqi_path.read_text(encoding="utf-8")).get("best")
            if col is None:
                col = next(c for c in df.columns if c != "t_ref_s")
        tt = df["t_ref_s"].to_numpy(dtype=float)
        yy = df[col].to_numpy(dtype=float)
        ft = self.frame_times(mode)
        if ft is None or ft.size != n:
            if yy.size != n:
                raise ValueError("pulse.parquet is not on the frame grid and the record has no frame times")
            return yy
        ok = np.isfinite(yy)
        if ok.sum() < 2:
            return np.full(n, np.nan)
        period = float(np.median(np.diff(tt))) if tt.size > 1 else 1.0
        return resample_to_grid(tt[ok], yy[ok], ft, max_gap_s=1.5 * period)


# --------------------------------------------------------------------------- splits
def participant_folds(study_ids: Iterable[str], n_folds: int, seed: int) -> list[tuple[set[str], set[str]]]:
    """Grouped K-fold over unique participants: a deterministic permutation (`rng(seed, 'folds')`) dealt
    round-robin into `n_folds` validation sets. Returns [(train_ids, val_ids), ...]; every participant is
    in exactly one validation set."""
    ids = sorted(set(study_ids))
    if len(ids) < n_folds:
        raise ValueError(f"{len(ids)} participants cannot make {n_folds} folds")
    perm = rng(seed, "folds").permutation(len(ids))
    folds: list[set[str]] = [set() for _ in range(n_folds)]
    for k, p in enumerate(perm):
        folds[k % n_folds].add(ids[p])
    out = []
    for k in range(n_folds):
        val = folds[k]
        train = set(ids) - val
        out.append((train, val))
    return out


def split_records(records: Sequence[ClipRecord], val_ids: Iterable[str]) -> tuple[list[ClipRecord], list[ClipRecord]]:
    val_ids = set(val_ids)
    train = [r for r in records if r.study_id not in val_ids]
    val = [r for r in records if r.study_id in val_ids]
    return train, val


def assert_participant_disjoint(train_ids: Iterable[str], val_ids: Iterable[str]) -> None:
    shared = set(train_ids) & set(val_ids)
    if shared:
        raise SplitViolation(f"{len(shared)} participant(s) in both train and validation: {sorted(shared)[:5]}")


# --------------------------------------------------------------------------- dataset
def _stmap_window(x: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    """(T, P, ch) or (T, R, C, ch) patch window -> (ch, P, T) float32 image, per-patch z-scored over time;
    NaN (dropped frames, cells off the palm) bridged along time or set to zero."""
    x = np.asarray(x, dtype=np.float32)
    if x.ndim == 4:
        x = x.reshape(x.shape[0], -1, x.shape[3])
    t, p, ch = x.shape
    img = np.transpose(x, (2, 1, 0)).astype(np.float64)       # (ch, P, T)
    idx = np.arange(t)
    for c in range(ch):
        for i in range(p):
            tr = img[c, i]
            ok = np.isfinite(tr)
            if ok.all():
                continue
            img[c, i] = np.interp(idx, idx[ok], tr[ok]) if ok.sum() >= 2 else 0.0
    mu = img.mean(axis=2, keepdims=True)
    sd = img.std(axis=2, keepdims=True)
    img = np.where(sd > eps, (img - mu) / np.maximum(sd, eps), 0.0)
    return img.astype(np.float32)


class ClipDataset:
    """Fixed-length windows over clip records; `__getitem__` returns numpy arrays, `collate` / `loader` torch.

    mode "video": x is (T, 3, H, W) float32 in [0, 1] from the uint8 proxy frames; mode "stmap": x is
    (ch, P, T) float32 (per-patch z-scored). y is the (T,) target pulse, z-scored per window (zeros when
    the target is missing); windows whose target has NaN or whose `valid` mask is False anywhere are
    skipped when `require_target` is True. Keys of each item: x, y, study_id, clip_id, camera, start.
    """

    def __init__(self, records: Sequence[ClipRecord], window_frames: int, step_frames: int | None = None,
                 mode: str = "video", require_target: bool = True, max_windows_per_clip: int | None = None) -> None:
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")
        self.records = list(records)
        self.window = int(window_frames)
        self.step = int(step_frames) if step_frames else int(window_frames)
        self.mode = mode
        self.require_target = bool(require_target)
        self._targets: list[np.ndarray] = []
        self.index: list[tuple[int, int]] = []
        for ri, rec in enumerate(self.records):
            n = rec.n_frames(mode)
            y = rec.load_target(mode)
            self._targets.append(y)
            valid = np.ones(n, dtype=bool) if rec.valid is None else np.asarray(rec.valid, dtype=bool)
            count = 0
            for start in range(0, n - self.window + 1, self.step):
                stop = start + self.window
                if self.require_target and (not np.isfinite(y[start:stop]).all() or not valid[start:stop].all()):
                    continue
                self.index.append((ri, start))
                count += 1
                if max_windows_per_clip is not None and count >= max_windows_per_clip:
                    break

    def __len__(self) -> int:
        return len(self.index)

    def study_ids(self) -> set[str]:
        return {r.study_id for r in self.records}

    def __getitem__(self, i: int) -> dict:
        ri, start = self.index[i]
        rec = self.records[ri]
        stop = start + self.window
        raw = rec.read(self.mode, start, stop)
        if self.mode == "video":
            x = np.transpose(raw.astype(np.float32) / 255.0, (0, 3, 1, 2))
        else:
            x = _stmap_window(raw)
        y = self._targets[ri][start:stop].astype(np.float32)
        if np.isfinite(y).all() and y.std() > 1e-8:
            y = (y - y.mean()) / y.std()
        else:
            y = np.zeros_like(y)
        return {"x": x, "y": y, "study_id": rec.study_id, "clip_id": rec.clip_id, "camera": rec.camera, "start": start}

    @staticmethod
    def collate(items: list[dict]) -> dict:
        import torch

        return {
            "x": torch.from_numpy(np.stack([it["x"] for it in items])),
            "y": torch.from_numpy(np.stack([it["y"] for it in items])),
            "study_id": [it["study_id"] for it in items], "clip_id": [it["clip_id"] for it in items],
            "camera": [it["camera"] for it in items], "start": [it["start"] for it in items],
        }

    def loader(self, batch_size: int, shuffle: bool, seed: int = 0):
        import torch

        g = torch.Generator()
        g.manual_seed(int(seed))
        return torch.utils.data.DataLoader(self, batch_size=int(batch_size), shuffle=shuffle, collate_fn=self.collate,
                                           num_workers=0, generator=g, drop_last=False)


# --------------------------------------------------------------------------- synthetic ground truth
def synthetic_video_clip(n_frames: int, fs: float, hr_bpm: float, seed: int, size: tuple[int, int] = (72, 128),
                         ac: float = 0.02, noise: float = 0.01, hrv: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
    """A proxy-sized uint8 video with a known pulse: a palm-coloured ellipse whose brightness drops in
    proportion to the blood-volume pulse (green most, red least), on a static dark background, plus
    pixel noise. Returns (video (n, H, W, 3) uint8, pulse (n,) in volume polarity). Used for the learned
    model tests and the positive control of section 8."""
    g = rng(seed, "synthetic_video")
    h, w = size
    t = np.arange(n_frames) / fs
    f = hr_bpm / 60.0 * (1 + hrv * np.sin(2 * np.pi * 0.25 * t))
    phase = np.cumsum(f) / fs
    ph = phase % 1.0
    pulse = np.exp(-((ph - 0.3) ** 2) / (2 * 0.08**2)) + 0.35 * np.exp(-((ph - 0.62) ** 2) / (2 * 0.12**2))
    pulse = (pulse - pulse.mean()) / pulse.std()
    yy, xx = np.mgrid[0:h, 0:w]
    mask = (((yy - h / 2) / (0.4 * h)) ** 2 + ((xx - w / 2) / (0.4 * w)) ** 2) <= 1.0
    base = np.where(mask[:, :, None], np.array([190.0, 140.0, 120.0]), np.array([20.0, 20.0, 20.0]))
    base = base * (1 + 0.1 * g.uniform(-1, 1, (h, w, 1)))
    ratios = np.array([0.5, 1.0, 0.6]) * ac
    frames = np.empty((n_frames, h, w, 3), dtype=np.uint8)
    for i in range(n_frames):
        fr = base * (1 - mask[:, :, None] * ratios * pulse[i]) + g.normal(0, noise * 255.0, (h, w, 3))
        frames[i] = np.clip(np.round(fr), 0, 255).astype(np.uint8)
    return frames, pulse
