"""Tests for zone_b/agents/human_gate.py."""
import asyncio
import pytest
from zone_b.agents.human_gate import run_human_gate


def _report(**overrides) -> dict:
    base = {
        "failed_agent": "VerifierAgent",
        "affected_primitive": "Guardrail",
        "repair_patch": "Add Guardrail before ReporterAgent",
        "repair_confidence": 0.85,
    }
    return {**base, **overrides}


class TestRunHumanGate:
    def test_returns_approved(self):
        result = asyncio.run(run_human_gate(_report()))
        assert result["approval_status"] == "approved"

    def test_returns_comments(self):
        result = asyncio.run(run_human_gate(_report()))
        assert "comments" in result
        assert isinstance(result["comments"], str)
        assert result["comments"] != ""

    def test_correct_keys(self):
        result = asyncio.run(run_human_gate(_report()))
        assert set(result.keys()) == {"approval_status", "comments"}

    def test_always_approves_regardless_of_confidence(self):
        result = asyncio.run(run_human_gate(_report(repair_confidence=0.1)))
        assert result["approval_status"] == "approved"

    def test_handles_empty_report(self):
        result = asyncio.run(run_human_gate({}))
        assert result["approval_status"] == "approved"

    def test_approval_status_is_string(self):
        result = asyncio.run(run_human_gate(_report()))
        assert isinstance(result["approval_status"], str)
