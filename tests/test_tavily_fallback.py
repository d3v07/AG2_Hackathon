"""Sprint 14 #71 — Tavily failure fallback + structured logging tests.

Asserts that every Tavily failure path (missing key, network error, rate
limit, bad response shape) falls back to the committed offline fixture
AND emits a structured JSON log line with key context fields.
"""
from __future__ import annotations

import io
import json
import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from shared.logging import get_logger
from zone_a.swarm import _build_initial_message, _load_tavily_fallback


_FALLBACK_FIXTURE = Path(__file__).parent.parent / "zone_a" / "fixtures" / "tavily_fallback.json"


@pytest.fixture
def captured_logs():
    """Attach a capture handler to the zone_a.swarm logger and return its stream."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    # Match the JSON formatter so captured records are parseable
    from shared.logging import _JsonFormatter

    handler.setFormatter(_JsonFormatter())
    logger = get_logger("zone_a.swarm")
    logger.addHandler(handler)
    yield stream
    logger.removeHandler(handler)


def _parsed(stream: io.StringIO) -> list[dict]:
    return [json.loads(line) for line in stream.getvalue().splitlines() if line.strip()]


# ─── fixture file is committed and parseable ───────────────────────────────────


def test_tavily_fallback_fixture_exists():
    assert _FALLBACK_FIXTURE.exists(), (
        f"Tavily fallback fixture missing: {_FALLBACK_FIXTURE}"
    )


def test_tavily_fallback_fixture_has_three_sources():
    data = json.loads(_FALLBACK_FIXTURE.read_text())
    results = data.get("results", [])
    assert len(results) == 3
    for src in results:
        assert "title" in src
        assert "url" in src
        assert "content" in src


def test_load_tavily_fallback_returns_three_sources():
    sources = _load_tavily_fallback()
    assert len(sources) == 3


# ─── missing key path ──────────────────────────────────────────────────────────


def test_missing_key_uses_fallback_and_logs(monkeypatch, captured_logs):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    msg = _build_initial_message("task", "research question")
    assert "fallback:no_key" in msg
    assert "Multi-agent reliability patterns" in msg or "Survey" in msg

    logs = _parsed(captured_logs)
    assert any(log.get("event") == "zone_a.tavily.missing_key" for log in logs), (
        f"Expected zone_a.tavily.missing_key log; got events: {[log.get('event') for log in logs]}"
    )
    missing = next(log for log in logs if log.get("event") == "zone_a.tavily.missing_key")
    assert missing.get("level") == "warning"
    assert missing.get("using_fallback") is True


def test_missing_key_does_not_construct_tavily_client(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    with patch("tavily.TavilyClient") as mock_cls:
        _build_initial_message("t", "rq")
    mock_cls.assert_not_called()


# ─── network/error path ────────────────────────────────────────────────────────


def test_network_error_uses_fallback_and_logs(monkeypatch, captured_logs):
    monkeypatch.setenv("TAVILY_API_KEY", "fake-key-for-test")
    with patch("tavily.TavilyClient") as mock_cls:
        mock_client = mock_cls.return_value
        mock_client.search.side_effect = ConnectionError("network down")
        msg = _build_initial_message("task", "rq")

    assert "fallback:ConnectionError" in msg
    logs = _parsed(captured_logs)
    err_log = next((log for log in logs if log.get("event") == "zone_a.tavily.error"), None)
    assert err_log is not None
    assert err_log.get("level") == "warning"
    assert err_log.get("error_type") == "ConnectionError"
    assert err_log.get("using_fallback") is True


def test_rate_limit_uses_fallback(monkeypatch, captured_logs):
    monkeypatch.setenv("TAVILY_API_KEY", "fake-key-for-test")
    with patch("tavily.TavilyClient") as mock_cls:
        mock_client = mock_cls.return_value
        mock_client.search.side_effect = Exception("429 rate limited")
        msg = _build_initial_message("task", "rq")

    assert "fallback:Exception" in msg
    logs = _parsed(captured_logs)
    err_log = next((log for log in logs if log.get("event") == "zone_a.tavily.error"), None)
    assert err_log is not None
    assert "429" in err_log.get("error_message", "")


# ─── bad response shape ────────────────────────────────────────────────────────


def test_bad_response_shape_uses_fallback_and_logs(monkeypatch, captured_logs):
    monkeypatch.setenv("TAVILY_API_KEY", "fake-key-for-test")
    with patch("tavily.TavilyClient") as mock_cls:
        mock_client = mock_cls.return_value
        mock_client.search.return_value = {"results": "not-a-list"}
        msg = _build_initial_message("task", "rq")

    assert "fallback:bad_shape" in msg
    logs = _parsed(captured_logs)
    bad_log = next(
        (log for log in logs if log.get("event") == "zone_a.tavily.bad_response_shape"), None
    )
    assert bad_log is not None
    assert bad_log.get("using_fallback") is True


# ─── happy path ────────────────────────────────────────────────────────────────


def test_successful_search_logs_success(monkeypatch, captured_logs):
    monkeypatch.setenv("TAVILY_API_KEY", "fake-key-for-test")
    with patch("tavily.TavilyClient") as mock_cls:
        mock_client = mock_cls.return_value
        mock_client.search.return_value = {
            "results": [
                {"title": "Real Result", "url": "https://example.com", "content": "..."},
            ]
        }
        msg = _build_initial_message("task", "what is X?")

    assert "source=tavily" in msg
    assert "Real Result" in msg

    logs = _parsed(captured_logs)
    ok_log = next((log for log in logs if log.get("event") == "zone_a.tavily.search"), None)
    assert ok_log is not None
    assert ok_log.get("status") == "success"
    assert ok_log.get("source_count") == 1
    assert ok_log.get("query") == "what is X?"
    assert isinstance(ok_log.get("latency_ms"), int)
    assert ok_log["latency_ms"] >= 0


# ─── log shape sanity ─────────────────────────────────────────────────────────


def test_every_log_line_has_base_fields(monkeypatch, captured_logs):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    _build_initial_message("t", "rq")

    logs = _parsed(captured_logs)
    assert logs, "expected at least one log line"
    for log in logs:
        for field in ("timestamp", "level", "event", "service"):
            assert field in log, f"log missing required base field {field!r}: {log}"
