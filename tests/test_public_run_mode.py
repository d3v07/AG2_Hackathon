"""Static checks for public run-mode exposure."""
from __future__ import annotations

from pathlib import Path


def test_submit_form_posts_live_mode_without_public_mode_radio():
    source = Path("public/app.jsx").read_text()

    assert 'mode: "live"' in source
    assert 'fetch("/api/public/runs"' in source
    assert 'name="mode"' not in source
    assert 'value="stub"' not in source
    assert "deterministic, no LLM credentials needed" not in source


def test_fixture_demo_affordance_remains_available():
    source = Path("public/app.jsx").read_text()

    assert "View demo fixture run" in source
    assert "Open fixture demo" in source
