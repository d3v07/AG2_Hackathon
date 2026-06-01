"""Final demo smoke coverage."""
from __future__ import annotations

import os
import subprocess
import sys


def test_demo_e2e_smoke_script_proves_backend_loop(tmp_path):
    env = {
        **os.environ,
        "CONCORD_DEMO_DB": str(tmp_path / "demo-smoke.db"),
        "CONCORD_DEMO_REGRESSION_RUNNER": "local",
    }

    result = subprocess.run(
        [sys.executable, "scripts/demo_e2e_smoke.py"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert "PASS demo_e2e_smoke" in result.stdout
    assert "violations=4" in result.stdout
    assert "patches=4" in result.stdout
    assert "assertions=4" in result.stdout
    assert "validation_state=passed" in result.stdout
    assert "history_count=" in result.stdout
