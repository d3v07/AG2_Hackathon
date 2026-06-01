"""Static checks for in-product API key creation wiring."""
from __future__ import annotations

from pathlib import Path


def _app_source() -> str:
    return Path("public/app.jsx").read_text()


def test_landing_can_create_session_api_key():
    source = _app_source()

    assert 'const SESSION_AUTH_KEY = "concord.session_auth"' in source
    assert "window.sessionStorage.setItem(SESSION_AUTH_KEY" in source
    assert 'fetch("/api/api-keys"' in source
    assert 'fetch("/api/api-keys/status", { headers: liveHeaders() })' in source
    assert "API key required" in source
    assert "canCreateApiKey" in source
    assert "First-key bootstrap is available only from localhost or deployment shell" in source
    assert "applyBrowserAuth(body)" in source
    assert "clearBrowserAuth()" in source
    assert "setAuthVersion((version) => version + 1)" in source


def test_landing_can_load_existing_session_api_key():
    source = _app_source()

    assert "handleUseExistingApiKey" in source
    assert "Use Existing Key" in source
    assert "Existing key failed:" in source
    assert 'fetch("/api/workflows", { headers })' in source
    assert "Create another key" in source
    assert "Rotate key" not in source


def test_created_key_is_revealed_and_can_be_copied():
    source = _app_source()

    assert "Created key" in source
    assert "{createdApiKey}" in source
    assert "navigator.clipboard.writeText(createdApiKey)" in source
    assert "Clipboard unavailable" in source


def test_onboarding_documents_first_key_ui_bootstrap():
    source = Path("docs/ONBOARDING.md").read_text()

    assert "API Access" in source
    assert "session key" in source
    assert "POST /api/api-keys" in source
