"""Runs the Node unit tests of appscript/Code.gs (mocked Google services) when Node is installed."""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_apps_script_exporter_node_suite():
    # the reporter is pinned: Node 22 prints the "spec" format by default, which has no TAP summary line
    r = subprocess.run(["node", "--test", "--test-reporter=tap", str(ROOT / "appscript" / "test" / "code.test.js")],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]
    assert "# fail 0" in r.stdout
    assert "# pass 0" not in r.stdout, "the suite must actually run some tests"
