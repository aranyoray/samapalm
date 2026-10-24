"""ECGFounder single-lead (lead I) offline runner: vendored Net1D, preprocessing, window rule, folder runner.

Design contract section 9: the research model runs offline on the analysis laptop (`palmppg ecg founder`) and is
compared with the clinician read (hypothesis H6). Outputs are research annotations for the study clinician and
that comparison. They are never returned to participants unless the ethics committee approves it and a clinician
has over-read the strip. No published evaluation on Indian or South-Asian ECGs exists.

Model: ECGFounder (Li et al., NEJM AI 2025), https://github.com/PKUDigitalHealth/ECGFounder. The classes
`MyConv1dPadSame` .. `Net1D` below are a faithful port of master/net1d.py (Shenda Hong, 2020); only unused
imports and the dataset/verbose helpers were dropped. Upstream licence:

    MIT License

    Copyright (c) 2025 PKUDigitalHealth

    Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
    documentation files (the "Software"), to deal in the Software without restriction, including without
    limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the
    Software, and to permit persons to whom the Software is furnished to do so, subject to the following
    conditions:

    The above copyright notice and this permission notice shall be included in all copies or substantial
    portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED
    TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
    THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
    CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
    DEALINGS IN THE SOFTWARE.

Weights: huggingface PKUDigitalHealth/ECGFounder, 1_lead_ECGFounder.pth (terms of the weights and of the HEEDB
training data to be confirmed with the authors; see docs/ecg_model.md). Labels: configs/ecgfounder_tasks.txt,
a copy of master/tasks.txt (line i is output i - 1).

Input: (N, 1, 5000) = 10 s at 500 Hz, z-scored per window. `filtered=True` (default) also applies
util.filter_bandpass as dataset.py does (50 Hz notch Q=30, 4th-order Butterworth 0.67-40 Hz filtfilt, minus a
0.4 s running median); `filtered=False` is z-score only, as ptbxl_eval.py. The choice is recorded in every
output. A Kardia strip (lead I, 300 Hz, 30 s) is resampled with resample_poly(x, 5, 3), cut into 10 s windows
and the window probabilities are combined by a rule fixed in advance (`combine_windows`).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from scipy.signal import butter, filtfilt, find_peaks, iirnotch, medfilt, resample_poly
from torch import nn

log = logging.getLogger(__name__)

from palmppg.ecg.founder_prep import (  # noqa: F401  (re-exported: the public API is unchanged)
    FILTER_DESC,
    FS_MODEL,
    MAX_RULE_LABELS,
    N_CLASSES,
    OUTPUT_SUFFIX,
    POLARITY_MIN_BEATS,
    POLARITY_NEG_FRAC,
    RHYTHM_LABELS,
    SOURCE_URL,
    TASKS_PATH,
    USE_NOTE,
    WEIGHTS_URL,
    WIN,
    WIN_S,
    ZSCORE_EPS,
    Windows,
    combine_rule,
    combine_windows,
    filter_bandpass,
    load_tasks,
    polarity_check,
    preprocess,
    resample_to_model,
    z_score,
)

# --------------------------------------------------------------------------- vendored net1d.py (MIT)
class MyConv1dPadSame(nn.Module):
    """
    extend nn.Conv1d to support SAME padding

    input: (n_sample, in_channels, n_length)
    output: (n_sample, out_channels, (n_length+stride-1)//stride)
    """
    def __init__(self, in_channels, out_channels, kernel_size, stride, groups=1):
        super().__init__()
        self.in_channels = in_channels
        self.out_channels = out_channels
        self.kernel_size = kernel_size
        self.stride = stride
        self.groups = groups
        self.conv = torch.nn.Conv1d(
            in_channels=self.in_channels,
            out_channels=self.out_channels,
            kernel_size=self.kernel_size,
            stride=self.stride,
            groups=self.groups)

    def forward(self, x):
        net = x
        # compute pad shape
        in_dim = net.shape[-1]
        out_dim = (in_dim + self.stride - 1) // self.stride
        p = max(0, (out_dim - 1) * self.stride + self.kernel_size - in_dim)
        pad_left = p // 2
        pad_right = p - pad_left
        net = F.pad(net, (pad_left, pad_right), "constant", 0)
        net = self.conv(net)
        return net


class MyMaxPool1dPadSame(nn.Module):
    """
    extend nn.MaxPool1d to support SAME padding

    params:
        kernel_size: kernel size
        stride: the stride of the window. Default value is kernel_size

    input: (n_sample, n_channel, n_length)
    """
    def __init__(self, kernel_size):
        super().__init__()
        self.kernel_size = kernel_size
        self.max_pool = torch.nn.MaxPool1d(kernel_size=self.kernel_size)

    def forward(self, x):
        net = x
        # compute pad shape
        p = max(0, self.kernel_size - 1)
        pad_left = p // 2
        pad_right = p - pad_left
        net = F.pad(net, (pad_left, pad_right), "constant", 0)
        net = self.max_pool(net)
        return net


class Swish(nn.Module):
    def forward(self, x):
        return x * torch.sigmoid(x)


class BasicBlock(nn.Module):
    """
    Basic Block:
        conv1 -> convk -> conv1

    params:
        in_channels: number of input channels
        out_channels: number of output channels
        ratio: ratio of channels to out_channels
        kernel_size: kernel window length
        stride: kernel step size
        groups: number of groups in convk
        downsample: whether downsample length
        use_bn: whether use batch_norm
        use_do: whether use dropout

    input: (n_sample, in_channels, n_length)
    output: (n_sample, out_channels, (n_length+stride-1)//stride)
    """
    def __init__(self, in_channels, out_channels, ratio, kernel_size, stride, groups, downsample,
                 is_first_block=False, use_bn=True, use_do=True):
        super().__init__()

        self.in_channels = in_channels
        self.out_channels = out_channels
        self.ratio = ratio
        self.kernel_size = kernel_size
        self.groups = groups
        self.downsample = downsample
        self.stride = stride if self.downsample else 1
        self.is_first_block = is_first_block
        self.use_bn = use_bn
        self.use_do = use_do

        self.middle_channels = int(self.out_channels * self.ratio)

        # the first conv, conv1
        self.bn1 = nn.BatchNorm1d(in_channels)
        self.activation1 = Swish()
        self.do1 = nn.Dropout(p=0.5)
        self.conv1 = MyConv1dPadSame(
            in_channels=self.in_channels,
            out_channels=self.middle_channels,
            kernel_size=1,
            stride=1,
            groups=1)

        # the second conv, convk
        self.bn2 = nn.BatchNorm1d(self.middle_channels)
        self.activation2 = Swish()
        self.do2 = nn.Dropout(p=0.5)
        self.conv2 = MyConv1dPadSame(
            in_channels=self.middle_channels,
            out_channels=self.middle_channels,
            kernel_size=self.kernel_size,
            stride=self.stride,
            groups=self.groups)

        # the third conv, conv1
        self.bn3 = nn.BatchNorm1d(self.middle_channels)
        self.activation3 = Swish()
        self.do3 = nn.Dropout(p=0.5)
        self.conv3 = MyConv1dPadSame(
            in_channels=self.middle_channels,
            out_channels=self.out_channels,
            kernel_size=1,
            stride=1,
            groups=1)

        # Squeeze-and-Excitation
        r = 2
        self.se_fc1 = nn.Linear(self.out_channels, self.out_channels // r)
        self.se_fc2 = nn.Linear(self.out_channels // r, self.out_channels)
        self.se_activation = Swish()

        if self.downsample:
            self.max_pool = MyMaxPool1dPadSame(kernel_size=self.stride)

    def forward(self, x):
        identity = x

        out = x
        # the first conv, conv1
        if not self.is_first_block:
            if self.use_bn:
                out = self.bn1(out)
            out = self.activation1(out)
            if self.use_do:
                out = self.do1(out)
        out = self.conv1(out)

        # the second conv, convk
        if self.use_bn:
            out = self.bn2(out)
        out = self.activation2(out)
        if self.use_do:
            out = self.do2(out)
        out = self.conv2(out)

        # the third conv, conv1
        if self.use_bn:
            out = self.bn3(out)
        out = self.activation3(out)
        if self.use_do:
            out = self.do3(out)
        out = self.conv3(out)  # (n_sample, n_channel, n_length)

        # Squeeze-and-Excitation
        se = out.mean(-1)  # (n_sample, n_channel)
        se = self.se_fc1(se)
        se = self.se_activation(se)
        se = self.se_fc2(se)
        se = torch.sigmoid(se)  # (n_sample, n_channel)
        out = torch.einsum('abc,ab->abc', out, se)

        # if downsample, also downsample identity
        if self.downsample:
            identity = self.max_pool(identity)

        # if expand channel, also pad zeros to identity
        if self.out_channels != self.in_channels:
            identity = identity.transpose(-1, -2)
            ch1 = (self.out_channels - self.in_channels) // 2
            ch2 = self.out_channels - self.in_channels - ch1
            identity = F.pad(identity, (ch1, ch2), "constant", 0)
            identity = identity.transpose(-1, -2)

        # shortcut
        out += identity

        return out


class BasicStage(nn.Module):
    """
    Basic Stage:
        block_1 -> block_2 -> ... -> block_M
    """
    def __init__(self, in_channels, out_channels, ratio, kernel_size, stride, groups, i_stage, m_blocks,
                 use_bn=True, use_do=True, verbose=False):
        super().__init__()

        self.in_channels = in_channels
        self.out_channels = out_channels
        self.ratio = ratio
        self.kernel_size = kernel_size
        self.groups = groups
        self.i_stage = i_stage
        self.m_blocks = m_blocks
        self.use_bn = use_bn
        self.use_do = use_do
        self.verbose = verbose

        self.block_list = nn.ModuleList()
        for i_block in range(self.m_blocks):

            # first block
            if self.i_stage == 0 and i_block == 0:
                self.is_first_block = True
            else:
                self.is_first_block = False
            # downsample, stride, input
            if i_block == 0:
                self.downsample = True
                self.stride = stride
                self.tmp_in_channels = self.in_channels
            else:
                self.downsample = False
                self.stride = 1
                self.tmp_in_channels = self.out_channels

            # build block
            tmp_block = BasicBlock(
                in_channels=self.tmp_in_channels,
                out_channels=self.out_channels,
                ratio=self.ratio,
                kernel_size=self.kernel_size,
                stride=self.stride,
                groups=self.groups,
                downsample=self.downsample,
                is_first_block=self.is_first_block,
                use_bn=self.use_bn,
                use_do=self.use_do)
            self.block_list.append(tmp_block)

    def forward(self, x):
        out = x
        for i_block in range(self.m_blocks):
            net = self.block_list[i_block]
            out = net(out)
        return out


class Net1D(nn.Module):
    """
    Input:
        X: (n_samples, n_channel, n_length)
        Y: (n_samples)

    Output:
        out: (n_samples)

    params:
        in_channels
        base_filters
        filter_list: list, filters for each stage
        m_blocks_list: list, number of blocks of each stage
        kernel_size
        stride
        groups_width
        n_stages
        n_classes
        use_bn
        use_do
    """

    def __init__(self, in_channels, base_filters, ratio, filter_list, m_blocks_list, kernel_size, stride,
                 groups_width, n_classes, use_bn=True, use_do=True, return_features=False, verbose=False):
        super().__init__()

        self.in_channels = in_channels
        self.base_filters = base_filters
        self.ratio = ratio
        self.filter_list = filter_list
        self.m_blocks_list = m_blocks_list
        self.kernel_size = kernel_size
        self.stride = stride
        self.groups_width = groups_width
        self.n_stages = len(filter_list)
        self.n_classes = n_classes
        self.use_bn = use_bn
        self.use_do = use_do
        self.return_features = return_features
        self.verbose = verbose

        # first conv
        self.first_conv = MyConv1dPadSame(
            in_channels=in_channels,
            out_channels=self.base_filters,
            kernel_size=self.kernel_size,
            stride=2)
        self.first_bn = nn.BatchNorm1d(base_filters)
        self.first_activation = Swish()

        # stages
        self.stage_list = nn.ModuleList()
        in_channels = self.base_filters
        for i_stage in range(self.n_stages):

            out_channels = self.filter_list[i_stage]
            m_blocks = self.m_blocks_list[i_stage]
            tmp_stage = BasicStage(
                in_channels=in_channels,
                out_channels=out_channels,
                ratio=self.ratio,
                kernel_size=self.kernel_size,
                stride=self.stride,
                groups=out_channels // self.groups_width,
                i_stage=i_stage,
                m_blocks=m_blocks,
                use_bn=self.use_bn,
                use_do=self.use_do,
                verbose=self.verbose)
            self.stage_list.append(tmp_stage)
            in_channels = out_channels

        # final prediction
        self.dense = nn.Linear(in_channels, n_classes)

    def forward(self, x):
        out = x

        # first conv
        out = self.first_conv(out)
        if self.use_bn:
            out = self.first_bn(out)
        out = self.first_activation(out)

        # stages
        for i_stage in range(self.n_stages):
            net = self.stage_list[i_stage]
            out = net(out)

        # final prediction
        deep_features = out.mean(-1)
        out = self.dense(deep_features)

        if self.return_features:
            return out, deep_features
        else:
            return out


# --------------------------------------------------------------------------- model construction and loading
NET_KW = {"in_channels": 1, "base_filters": 64, "ratio": 1, "filter_list": [64, 160, 160, 400, 400, 1024, 1024],
          "m_blocks_list": [2, 2, 2, 3, 3, 4, 4], "kernel_size": 16, "stride": 2, "groups_width": 16,
          "verbose": False, "use_bn": False, "use_do": False, "n_classes": N_CLASSES}


def build_model() -> Net1D:
    """The 1-lead ECGFounder Net1D (about 30.8 M parameters), randomly initialised, eval mode."""
    return Net1D(**NET_KW).eval()


def sha256_file(path: str | Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def _numpy_safe_globals() -> list:
    """numpy types the official checkpoint stores next to the weights (a metric as a numpy scalar)."""
    try:
        from numpy._core.multiarray import scalar
        name = "numpy._core.multiarray.scalar"
    except ImportError:                                   # numpy < 2
        from numpy.core.multiarray import scalar
        name = "numpy.core.multiarray.scalar"
    return [scalar, (scalar, name), (scalar, "numpy.core.multiarray.scalar"), np.dtype,
            *(type(np.dtype(t)) for t in ("float64", "float32", "int64"))]


def load_model(weights_path: str | Path, trust_pickle: bool = False) -> Net1D:
    """Net1D with the 1-lead checkpoint loaded; `model.weights_sha256` and `model.weights_path` are set.

    The checkpoint holds `{'state_dict': ...}` plus optimiser state. It is read with torch's weights-only
    unpickler (numpy scalar types allowed); `trust_pickle=True` falls back to a full unpickle
    (`weights_only=False`, as upstream does), which runs code from the file: use it only for a file whose
    sha256 you have checked. Every model weight must be present (upstream loads with strict=False).
    """
    path = Path(weights_path)
    digest = sha256_file(path)
    if trust_pickle:
        ckpt = torch.load(path, map_location="cpu", weights_only=False)
    else:
        try:
            with torch.serialization.safe_globals(_numpy_safe_globals()):
                ckpt = torch.load(path, map_location="cpu", weights_only=True)
        except Exception as e:   # pickle.UnpicklingError and friends
            raise RuntimeError(f"{path}: weights-only load failed ({e}); if this is the official checkpoint "
                               f"(sha256 {digest}), retry with trust_pickle=True / --trust-pickle") from e
    state = ckpt.get("state_dict", ckpt) if isinstance(ckpt, dict) else ckpt
    state = {k.removeprefix("module."): v for k, v in state.items()}
    model = build_model()
    missing, unexpected = model.load_state_dict(state, strict=False)
    assert not missing, f"{path}: checkpoint lacks {len(missing)} model weights, e.g. {missing[:3]}"
    if unexpected:
        log.warning("%s: ignored %d extra checkpoint keys, e.g. %s", path.name, len(unexpected), unexpected[:3])
    model.eval()
    model.weights_sha256 = digest
    model.weights_path = str(path)
    model.unexpected_keys = list(unexpected)
    return model


class onnx_export_mode:
    """Context manager: Net1D pad layers in a form ONNX Runtime optimises correctly (fixed input length).

    net1d.py zero-pads and then max-pools. After constant folding ONNX Runtime fuses that Pad into MaxPool's
    own `pads`, which pad with -inf, not 0: from the first odd length on, the last pooled value differs when
    it is negative (logit errors up to 0.8). Here the max-pool pad is a Concat of zeros (not fusable) and the
    conv pads are frozen as constants. The maths is unchanged. Approach from the OpenHolter wrapper
    (ai/ecgfounder/export_onnx.py).
    """

    def __enter__(self):
        def conv_forward(m, x):
            n = int(x.shape[-1])
            out = (n + m.stride - 1) // m.stride
            p = max(0, (out - 1) * m.stride + m.kernel_size - n)
            return m.conv(F.pad(x, (p // 2, p - p // 2), "constant", 0))

        def pool_forward(m, x):
            p = max(0, m.kernel_size - 1)
            z = x[..., :1] * 0
            x = torch.cat([z] * (p // 2) + [x] + [z] * (p - p // 2), dim=-1)
            return m.max_pool(x)

        self.saved = (MyConv1dPadSame.forward, MyMaxPool1dPadSame.forward)
        MyConv1dPadSame.forward, MyMaxPool1dPadSame.forward = conv_forward, pool_forward
        return self

    def __exit__(self, *exc):
        MyConv1dPadSame.forward, MyMaxPool1dPadSame.forward = self.saved
        return False


class _WithProbs(nn.Module):
    def __init__(self, net: nn.Module):
        super().__init__()
        self.net = net

    def forward(self, x):
        logits = self.net(x)
        return logits, torch.sigmoid(logits)


ONNX_INPUT, ONNX_OUTPUTS, ONNX_OPSET = "ecg", ("logits", "probs"), 17


def export_onnx(model: nn.Module, path: str | Path, opset: int = ONNX_OPSET) -> Path:
    """fp32 ONNX: input `ecg` (batch, 1, 5000) float32, outputs `logits` and `probs` (batch, 150).

    Length fixed at 5000, batch dynamic, standard ops only, pads exported via `onnx_export_mode`. The graph holds
    the network only: resampling, filtering and z-scoring stay outside (see docs/ecg_model.md).
    """
    import warnings

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    wrapped = _WithProbs(model).eval()
    x = torch.randn(2, 1, WIN)
    kw = {"input_names": [ONNX_INPUT], "output_names": list(ONNX_OUTPUTS), "opset_version": opset,
          "dynamic_axes": {ONNX_INPUT: {0: "batch"}, **{k: {0: "batch"} for k in ONNX_OUTPUTS}}}
    with onnx_export_mode(), warnings.catch_warnings(), torch.inference_mode():
        warnings.simplefilter("ignore")      # tracer warnings: int(x.shape[-1]) is intended (fixed length)
        try:
            torch.onnx.export(wrapped, (x,), str(path), dynamo=False, **kw)
        except TypeError:                    # torch without the dynamo switch
            torch.onnx.export(wrapped, (x,), str(path), **kw)
    return path


# --------------------------------------------------------------------------- preprocessing
# --------------------------------------------------------------------------- inference
def window_probabilities(model: nn.Module, x: np.ndarray, batch: int = 16) -> np.ndarray:
    """(n, 1, 5000) float32 -> (n, 150) sigmoid probabilities."""
    if len(x) == 0:
        return np.zeros((0, N_CLASSES))
    out = []
    model.eval()
    with torch.inference_mode():
        for i in range(0, len(x), batch):
            out.append(torch.sigmoid(model(torch.from_numpy(np.ascontiguousarray(x[i:i + batch])))).numpy())
    return np.concatenate(out).astype(np.float64)


def _r(v: float, nd: int = 6):
    return None if v is None or not np.isfinite(v) else round(float(v), nd)


def predict(model: nn.Module, x_mv, fs: float, filtered: bool = True, step_s: float = WIN_S,
            polarity: str = "auto", tasks: list[str] | None = None) -> dict:
    """Per-label probabilities (combined over windows), per-window probabilities and metadata, JSON-ready.

    Keys: `labels` (rhythm subset: index, name, rule, prob, window_probs), `all_labels` (150 names -> combined
    prob), `window_probs` (n x 150), `n_windows`, `window_starts_s`, `filtered`, `filter`, `polarity_flipped`,
    `weights_sha256`, ... plus `use` (the ethics position). With no 10 s window the probabilities are null.
    """
    tasks = tasks or load_tasks()
    w = preprocess(x_mv, fs, filtered=filtered, step_s=step_s, polarity=polarity)
    wp = window_probabilities(model, w.x)
    comb = combine_windows(wp) if len(wp) else np.full(N_CLASSES, np.nan)
    labels = {}
    for i, name in RHYTHM_LABELS.items():
        labels[name] = {"index": i, "rule": combine_rule(i), "prob": _r(comb[i]),
                        "window_probs": [_r(v) for v in wp[:, i]]}
    return {
        "model": "ECGFounder 1-lead (Net1D, 150 labels)", "source": SOURCE_URL,
        "weights_sha256": getattr(model, "weights_sha256", None), "weights_path": getattr(model, "weights_path", None),
        "filtered": bool(filtered), "filter": FILTER_DESC[bool(filtered)],
        "fs_in": float(fs), "fs_model": FS_MODEL, "resample_up_down": list(w.resample_up_down),
        "duration_s": _r(w.duration_s, 3), "step_s": w.step_s, "n_windows": len(w.starts_s),
        "window_starts_s": w.starts_s,
        "polarity_flipped": w.polarity_flipped, "polarity_negative_fraction": _r(w.polarity_negative_fraction, 3),
        "polarity_beats": w.polarity_beats, "polarity_mode": polarity,
        "combine": {"max": sorted(MAX_RULE_LABELS), "mean": "all other labels"},
        "labels": labels,
        "all_labels": {name: _r(comb[i]) for i, name in enumerate(tasks)},
        "window_probs": [[_r(v) for v in row] for row in wp],
        "notes": w.notes, "use": USE_NOTE,
        "torch_version": torch.__version__,
        "created_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
    }


# --------------------------------------------------------------------------- inputs and folder runner
def read_ecg_samples_csv(path: str | Path) -> tuple[np.ndarray, float, dict]:
    """BLE `<clip>_ecg_samples.csv` (t_ref_ns, ..., lead1_mv) -> (mV, fs, info).

    fs comes from the t_ref_ns span; within 1 percent of a whole number it is rounded (the Kardia samples at a
    fixed device rate, the phone timestamps jitter). The measured value is kept in `info`.
    """
    import pandas as pd

    df = pd.read_csv(path)
    if "lead1_mv" not in df.columns or "t_ref_ns" not in df.columns:
        raise ValueError(f"{path}: needs t_ref_ns and lead1_mv columns, has {list(df.columns)}")
    mv = df["lead1_mv"].to_numpy(dtype=np.float64)
    t = df["t_ref_ns"].to_numpy(dtype=np.float64)
    if mv.size < 2 or t[-1] <= t[0]:
        raise ValueError(f"{path}: too few samples or no time span")
    fs_meas = (mv.size - 1) / ((t[-1] - t[0]) * 1e-9)
    fs = float(round(fs_meas)) if abs(fs_meas - round(fs_meas)) <= 0.01 * fs_meas else float(fs_meas)
    return mv, fs, {"fs_measured": round(fs_meas, 4)}


def read_atc(path: str | Path) -> tuple[np.ndarray, float, dict]:
    from palmppg.ecg.atc import parse_atc

    r = parse_atc(path)
    return r["samples_mv"].astype(np.float64), float(r["fs"]), {"atc_problems": r["problems"],
                                                                 "clipped_frac": r["clipped_frac"]}


_CLIP_PATTERNS = (  # (regex on the file name, kind); earlier wins for the same clip
    (re.compile(r"^(?P<clip>.+)_ecg_samples\.csv$"), "ble_csv"),
    (re.compile(r"^(?P<clip>.+)_ecg\.atc$"), "ble_atc"),
    (re.compile(r"^(?P<clip>.+)_kardia\.atc$"), "kardia_atc"),
    (re.compile(r"^(?P<clip>kardia_.+)\.atc$"), "kardia_atc"),
)


def find_clips(participant_dir: str | Path) -> list[tuple[str, str, Path]]:
    """(clip, kind, path) per clip under one participant folder; the BLE CSV wins over that clip's ATC."""
    found: dict[tuple[str, str], tuple[int, str, Path]] = {}
    for p in sorted(Path(participant_dir).rglob("*")):
        if not p.is_file():
            continue
        for rank, (rx, kind) in enumerate(_CLIP_PATTERNS):
            m = rx.match(p.name)
            if m:
                key = (str(p.parent), m.group("clip"))
                if key not in found or rank < found[key][0]:
                    found[key] = (rank, kind, p)
                break
    return [(clip, kind, path) for (_, clip), (_, kind, path) in sorted(found.items())]


def run_file(model: nn.Module, path: str | Path, kind: str | None = None, filtered: bool = True,
             out_path: str | Path | None = None, pid: str | None = None, clip: str | None = None,
             step_s: float = WIN_S, out_dir: str | Path | None = None) -> dict:
    """Run one ECG file (ATC or BLE samples CSV) and write `<clip>_ecg_founder.json`.

    Written to `out_path`, else `out_dir/<clip>_ecg_founder.json`, else next to the input.
    """
    path = Path(path)
    kind = kind or ("ble_csv" if path.suffix.lower() == ".csv" else "atc")
    mv, fs, info = read_ecg_samples_csv(path) if kind == "ble_csv" else read_atc(path)
    res = predict(model, mv, fs, filtered=filtered, step_s=step_s)
    clip = clip or path.name.removesuffix("_ecg_samples.csv").removesuffix(".atc").removesuffix("_ecg")
    res = {"pid": pid, "clip": clip, "input": str(path), "input_kind": kind, **info, **res}
    out = Path(out_path) if out_path else (Path(out_dir) if out_dir else path.parent) / f"{clip}{OUTPUT_SUFFIX}"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=1), encoding="utf-8")
    res["output"] = str(out)
    return res


def iter_participants(root: str | Path) -> Iterator[Path]:
    """Participant folders: each sub-folder of `root` (a study root's participants/ is used when present)."""
    root = Path(root)
    base = root / "participants" if (root / "participants").is_dir() else root
    yield from (p for p in sorted(base.iterdir()) if p.is_dir())


def run_participants(model: nn.Module, root: str | Path, filtered: bool = True, out_root: str | Path | None = None,
                     step_s: float = WIN_S) -> list[dict]:
    """Every clip of every participant under `root`; one summary row per clip (errors are rows, not raises)."""
    rows = []
    for pdir in iter_participants(root):
        for clip, kind, path in find_clips(pdir):
            out = Path(out_root) / pdir.name / f"{clip}{OUTPUT_SUFFIX}" if out_root else None
            try:
                r = run_file(model, path, kind=kind, filtered=filtered, out_path=out, pid=pdir.name, clip=clip,
                             step_s=step_s)
                probs = {k: v["prob"] for k, v in r["labels"].items() if v["prob"] is not None}
                rows.append({"pid": pdir.name, "clip": clip, "kind": kind, "output": r["output"],
                             "n_windows": r["n_windows"], "polarity_flipped": r["polarity_flipped"],
                             "top": max(probs, key=probs.get) if probs else None, "error": None})
            except Exception as e:   # one bad file must not stop the cohort
                log.exception("%s failed", path)
                rows.append({"pid": pdir.name, "clip": clip, "kind": kind, "output": None, "n_windows": 0,
                             "polarity_flipped": None, "top": None, "error": f"{type(e).__name__}: {e}"})
    return rows
