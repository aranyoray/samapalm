import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")
os.environ.setdefault("OMP_NUM_THREADS", "2")


@pytest.fixture
def cfg():
    from palmppg.core.config import load_pipeline_config

    return load_pipeline_config()


@pytest.fixture
def tmp_work(tmp_path):
    from palmppg.core.paths import WorkLayout

    return WorkLayout(tmp_path / "work")
