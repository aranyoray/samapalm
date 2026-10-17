"""Configuration loading, seeding and frozen-config integrity.

All thresholds live in YAML under configs/. Nothing in code hard-codes a window length,
a go/no-go margin or an SQI threshold; code reads them from the config object and the
frozen config carries a sha256 signature that must match its content before any pilot
experiment runs (see `verify_frozen`).
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "configs"


class ConfigError(RuntimeError):
    pass


def _deep_merge(base: dict, override: Mapping) -> dict:
    out = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, Mapping) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


@dataclass
class Config:
    """Dict-backed config with dotted access: cfg.get('qc.drop_pct_max')."""

    data: dict = field(default_factory=dict)
    sources: list[str] = field(default_factory=list)

    def get(self, dotted: str, default: Any = ...) -> Any:
        node: Any = self.data
        for part in dotted.split("."):
            if isinstance(node, Mapping) and part in node:
                node = node[part]
            else:
                if default is ...:
                    raise ConfigError(f"missing config key: {dotted} (sources={self.sources})")
                return default
        return node

    def __getitem__(self, dotted: str) -> Any:
        return self.get(dotted)

    def section(self, dotted: str) -> dict:
        node = self.get(dotted, {})
        if not isinstance(node, Mapping):
            raise ConfigError(f"config key {dotted} is not a section")
        return dict(node)

    def with_overrides(self, overrides: Mapping | None) -> "Config":
        if not overrides:
            return self
        return Config(_deep_merge(self.data, overrides), self.sources + ["<overrides>"])

    def sha256(self) -> str:
        return hashlib.sha256(json.dumps(self.data, sort_keys=True, default=str).encode()).hexdigest()

    def to_dict(self) -> dict:
        return copy.deepcopy(self.data)


def load_yaml(path: str | os.PathLike) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: top level must be a mapping")
    return data


def load_config(*paths: str | os.PathLike, overrides: Mapping | None = None) -> Config:
    """Load one or more YAML files; later files override earlier ones (deep merge)."""
    if not paths:
        paths = (CONFIG_DIR / "pipeline.yaml",)
    data: dict = {}
    sources: list[str] = []
    for p in paths:
        p = Path(p)
        data = _deep_merge(data, load_yaml(p))
        sources.append(str(p))
    cfg = Config(data, sources)
    return cfg.with_overrides(overrides)


def load_pipeline_config(overrides: Mapping | None = None) -> Config:
    return load_config(CONFIG_DIR / "pipeline.yaml", overrides=overrides)


def load_frozen_config() -> Config:
    return load_config(CONFIG_DIR / "frozen_config.yaml")


# --------------------------------------------------------------------------- frozen config
def frozen_payload_hash(frozen: Mapping) -> str:
    """Hash of everything in the frozen config except the signature block itself."""
    payload = {k: v for k, v in frozen.items() if k != "signature"}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def sign_frozen_config(path: str | os.PathLike, signed_by: str, date: str) -> str:
    """Write the signature block into frozen_config.yaml. Returns the sha256."""
    data = load_yaml(path)
    digest = frozen_payload_hash(data)
    data["signature"] = {"sha256": digest, "signed_by": signed_by, "date": date}
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, sort_keys=False)
    return digest


def verify_frozen(path: str | os.PathLike | None = None) -> dict:
    """Raise ConfigError unless the frozen config's signature matches its content."""
    path = Path(path) if path else CONFIG_DIR / "frozen_config.yaml"
    data = load_yaml(path)
    sig = data.get("signature") or {}
    expected = frozen_payload_hash(data)
    if sig.get("sha256") != expected:
        raise ConfigError(
            f"frozen config {path} signature mismatch: thresholds were edited after signing "
            f"(have {sig.get('sha256')}, content hashes to {expected}). Re-sign only with a dated DECISIONS entry."
        )
    return data


# --------------------------------------------------------------------------- seeding
def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    try:  # torch optional
        import torch

        torch.manual_seed(seed)
        torch.use_deterministic_algorithms(False)
    except Exception:  # pragma: no cover
        pass


def rng(seed: int | None, salt: str = "") -> np.random.Generator:
    """Deterministic generator derived from (seed, salt) so parallel workers never share streams."""
    if seed is None:
        seed = 0
    h = hashlib.sha256(f"{seed}:{salt}".encode()).digest()
    return np.random.default_rng(int.from_bytes(h[:8], "little"))
