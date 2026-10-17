import pytest

from palmppg.core.config import ConfigError, load_frozen_config, load_pipeline_config, rng, verify_frozen


def test_pipeline_config_keys():
    cfg = load_pipeline_config()
    assert cfg.get("sync.p1.pulses") == 3
    assert cfg.get("window.tail_exclusion_s") == 5.0
    assert cfg.get("missing.key", None) is None
    with pytest.raises(ConfigError):
        cfg.get("missing.key")
    assert cfg.with_overrides({"sync": {"p1": {"pulses": 2}}}).get("sync.p1.pulses") == 2
    assert cfg.get("sync.p1.on_ms") == 100


def test_frozen_signature_verifies():
    d = verify_frozen()
    assert d["go_no_go"]["coverage_min_pct"] == 90.0
    assert load_frozen_config().get("equity.error_sd_ratio_margin") == 1.15


def test_rng_is_deterministic_and_salted():
    a, b, c = rng(1, "x"), rng(1, "x"), rng(1, "y")
    assert a.random() == b.random() != c.random()
