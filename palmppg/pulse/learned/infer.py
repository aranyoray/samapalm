"""Window -> pulse -> rate inference for the learned extractors (protocol 6.3, E1, E4).

`predict_pulse` streams fixed windows of a (n, H, W, 3) uint8 proxy video (array or zarr) or of a
(n, P, ch) STMap source through a model, z-scores each window's prediction and overlap-averages them
into one (n,) pulse signal (NaN where no window reached). `infer_clip` adds the clip rate from the
spectral peak and the median beat interval (`rate.clip_hr`). torch is imported inside functions.
"""
from __future__ import annotations

import numpy as np

from palmppg.pulse.learned.dataset import ClipDataset, ClipRecord
from palmppg.pulse.learned.train import _to_model_input
from palmppg.pulse.rate import clip_hr


def predict_pulse(model, source, window_frames: int, step_frames: int | None = None, mode: str = "video",
                  batch_size: int = 4, device: str = "cpu") -> np.ndarray:
    """(n,) pulse prediction over the whole source by overlap-averaging z-scored window predictions."""
    import torch

    rec = ClipRecord("inference", video=source if mode == "video" else None, stmap=source if mode == "stmap" else None)
    ds = ClipDataset([rec], window_frames, step_frames or window_frames // 2, mode=mode, require_target=False)
    n = rec.n_frames(mode)
    acc = np.zeros(n)
    cnt = np.zeros(n)
    layout = getattr(model, "input_layout", "NTCHW")
    model.eval()
    with torch.no_grad():
        for batch in ds.loader(batch_size, shuffle=False):
            x = _to_model_input(batch["x"].to(device), layout)
            out = model(x).cpu().numpy()
            for row, start in zip(out, batch["start"]):
                sd = row.std()
                z = (row - row.mean()) / sd if sd > 1e-8 else np.zeros_like(row)
                acc[start:start + window_frames] += z
                cnt[start:start + window_frames] += 1
    pulse = np.where(cnt > 0, acc / np.maximum(cnt, 1), np.nan)
    ok = np.isfinite(pulse)
    if ok.sum() > 1 and pulse[ok].std() > 1e-8:
        pulse[ok] = (pulse[ok] - pulse[ok].mean()) / pulse[ok].std()
    return pulse


def infer_clip(model, source, fs: float, band: tuple[float, float], window_frames: int, step_frames: int | None = None,
               mode: str = "video", ibi_bounds_s: tuple[float, float] = (0.33, 2.0), device: str = "cpu") -> dict:
    """{"pulse": (n,), "hr_bpm": spectral-peak rate, "hr_ibi_bpm", "n_beats"} for one clip source."""
    pulse = predict_pulse(model, source, window_frames, step_frames, mode=mode, device=device)
    hr = clip_hr(pulse, fs, band, ibi_bounds_s)
    return {"pulse": pulse, "hr_bpm": hr["hr_spectral_bpm"], "hr_ibi_bpm": hr["hr_ibi_median_bpm"], "n_beats": hr["n_beats"]}
