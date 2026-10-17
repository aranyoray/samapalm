"""Generic trainer for the learned extractors (protocol 6.3, 10, 11.1, 11.6).

Fixed seeds (`rng(seed, salt)` -> torch), participant-grouped splits enforced (`SplitViolation` when
the training and validation datasets share a `study_id`), negative-Pearson or standardised-MSE loss,
Adam, optional MLflow logging behind `TrainConfig.mlflow`. torch is imported inside functions.
Validation reports the loss and the mean absolute pulse-rate error (bpm) between the spectral peaks of
the predicted and target windows (`sqi.spectral_peak`).
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass

import numpy as np

from palmppg.core.config import rng
from palmppg.pulse.learned.dataset import ClipDataset, SplitViolation, assert_participant_disjoint
from palmppg.pulse.sqi import spectral_peak


@dataclass
class TrainConfig:
    epochs: int = 2
    lr: float = 1e-3
    batch_size: int = 4
    seed: int = 0
    loss: str = "neg_pearson"          # neg_pearson | mse
    weight_decay: float = 0.0
    grad_clip: float = 1.0
    device: str = "cpu"
    num_threads: int | None = None
    mlflow: bool = False
    mlflow_experiment: str | None = None
    mlflow_run_name: str | None = None
    fs: float = 30.0
    band: tuple[float, float] = (0.5, 4.0)


def derived_seed(seed: int, salt: str) -> int:
    return int(rng(seed, salt).integers(0, 2**31 - 1))


def _to_model_input(x, layout: str):
    """Dataset video windows are (N, T, 3, H, W); 3D models want (N, 3, T, H, W). STMaps pass through."""
    if x.ndim == 5 and layout == "NCTHW":
        return x.permute(0, 2, 1, 3, 4).contiguous()
    return x


def hr_mae_bpm(pred: np.ndarray, target: np.ndarray, fs: float, band: tuple[float, float]) -> float:
    """Mean |60 f_pred - 60 f_target| over windows from the periodogram peaks in `band` (E1-style check)."""
    errs = []
    for p, t in zip(pred, target):
        fp, _ = spectral_peak(p, fs, band)
        ft, _ = spectral_peak(t, fs, band)
        if np.isfinite(fp) and np.isfinite(ft):
            errs.append(abs(60.0 * (fp - ft)))
    return float(np.mean(errs)) if errs else float("nan")


def evaluate(model, dataset: ClipDataset, config: TrainConfig) -> dict:
    """Loss and HR MAE of `model` on every window of `dataset` (no gradient)."""
    import torch

    from palmppg.pulse.learned.common import make_loss

    layout = getattr(model, "input_layout", "NTCHW")
    crit = make_loss(config.loss)
    model.eval()
    losses, preds, targets = [], [], []
    with torch.no_grad():
        for batch in dataset.loader(config.batch_size, shuffle=False, seed=config.seed):
            x = _to_model_input(batch["x"].to(config.device), layout)
            y = batch["y"].to(config.device)
            out = model(x)
            losses.append(float(crit(out, y)) * y.shape[0])
            preds.append(out.cpu().numpy())
            targets.append(y.cpu().numpy())
    n = sum(p.shape[0] for p in preds)
    if n == 0:
        return {"loss": float("nan"), "hr_mae_bpm": float("nan"), "n_windows": 0}
    pred = np.concatenate(preds)
    targ = np.concatenate(targets)
    return {"loss": float(sum(losses) / n), "hr_mae_bpm": hr_mae_bpm(pred, targ, config.fs, config.band), "n_windows": int(n)}


def train_model(model, train_ds: ClipDataset, val_ds: ClipDataset | None = None, config: TrainConfig | None = None) -> dict:
    """Train `model` on `train_ds` windows; returns a history dict.

    history = {"train_loss": [per epoch], "val_loss": [...], "val_hr_mae_bpm": [...], "epochs", "seed",
    "n_train_windows", "n_val_windows", "elapsed_s", "config"}. Raises SplitViolation when a participant is
    in both datasets (protocol 11.1). Seeds: torch and the DataLoader shuffle come from
    `rng(config.seed, ...)`; with a fixed thread count the run is repeatable on CPU. With
    `config.mlflow` the parameters and per-epoch metrics are logged to the active tracking URI.
    """
    import torch

    from palmppg.pulse.learned.common import make_loss, seed_torch

    config = config or TrainConfig()
    if val_ds is not None:
        assert_participant_disjoint(train_ds.study_ids(), val_ds.study_ids())
    if len(train_ds) == 0:
        raise ValueError("training dataset has no windows")
    if config.num_threads:
        torch.set_num_threads(int(config.num_threads))
    seed_torch(derived_seed(config.seed, "train"))
    layout = getattr(model, "input_layout", "NTCHW")
    model.to(config.device)
    crit = make_loss(config.loss)
    opt = torch.optim.Adam(model.parameters(), lr=config.lr, weight_decay=config.weight_decay)
    history = {"train_loss": [], "val_loss": [], "val_hr_mae_bpm": [], "epochs": config.epochs, "seed": config.seed,
               "n_train_windows": len(train_ds), "n_val_windows": len(val_ds) if val_ds is not None else 0,
               "config": asdict(config)}
    run = None
    if config.mlflow:
        import mlflow

        if config.mlflow_experiment:
            mlflow.set_experiment(config.mlflow_experiment)
        run = mlflow.start_run(run_name=config.mlflow_run_name)
        mlflow.log_params({k: v for k, v in asdict(config).items() if k not in ("band",)})
        mlflow.log_param("model", type(model).__name__)
    t0 = time.time()
    try:
        for epoch in range(config.epochs):
            model.train()
            total, count = 0.0, 0
            loader = train_ds.loader(config.batch_size, shuffle=True, seed=derived_seed(config.seed, f"epoch:{epoch}"))
            for batch in loader:
                x = _to_model_input(batch["x"].to(config.device), layout)
                y = batch["y"].to(config.device)
                opt.zero_grad()
                loss = crit(model(x), y)
                loss.backward()
                if config.grad_clip and config.grad_clip > 0:
                    torch.nn.utils.clip_grad_norm_(model.parameters(), config.grad_clip)
                opt.step()
                total += float(loss.detach()) * y.shape[0]
                count += int(y.shape[0])
            history["train_loss"].append(total / max(count, 1))
            if val_ds is not None and len(val_ds) > 0:
                ev = evaluate(model, val_ds, config)
                history["val_loss"].append(ev["loss"])
                history["val_hr_mae_bpm"].append(ev["hr_mae_bpm"])
            if run is not None:
                import mlflow

                mlflow.log_metric("train_loss", history["train_loss"][-1], step=epoch)
                if history["val_loss"]:
                    mlflow.log_metric("val_loss", history["val_loss"][-1], step=epoch)
                    mlflow.log_metric("val_hr_mae_bpm", history["val_hr_mae_bpm"][-1], step=epoch)
    finally:
        if run is not None:
            import mlflow

            mlflow.end_run()
    history["elapsed_s"] = time.time() - t0
    return history


__all__ = ["TrainConfig", "train_model", "evaluate", "hr_mae_bpm", "SplitViolation"]
