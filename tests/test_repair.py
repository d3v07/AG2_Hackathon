"""Tests for zone_b/agents/repair.py — deterministic parts only."""
import asyncio
import pytest
from shared.models import Violation
from zone_b.agents.repair import PRIMITIVE_MAP, SEVERITY_RANK, _pick_primary, run_repair


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _v(contract_type: str = "evidence", severity: str = "high",
       agent: str = "VerifierAgent", step: int = 3) -> Violation:
    return Violation(
        contract_type=contract_type, severity=severity,
        rule="test rule", expected="EXPECTED: x", observed="OBSERVED: y",
        failed_agent=agent, failed_step=step,
    )


# ---------------------------------------------------------------------------
# PRIMITIVE_MAP
# ---------------------------------------------------------------------------

class TestPrimitiveMap:
    def test_evidence_maps_to_guardrail(self):
        assert PRIMITIVE_MAP["evidence"] == "Guardrail"

    def test_tool_maps_to_on_context_condition(self):
        assert PRIMITIVE_MAP["tool"] == "OnContextCondition"

    def test_routing_maps_to_handoff(self):
        assert PRIMITIVE_MAP["routing"] == "Handoff"

    def test_approval_maps_to_human_gate(self):
        assert PRIMITIVE_MAP["approval"] == "HumanGate"

    def test_schema_maps_to_guardrail(self):
        assert PRIMITIVE_MAP["schema"] == "Guardrail"

    def test_all_five_types_covered(self):
        assert set(PRIMITIVE_MAP.keys()) == {"evidence", "tool", "routing", "approval", "schema"}


# ---------------------------------------------------------------------------
# _pick_primary
# ---------------------------------------------------------------------------

class TestPickPrimary:
    def test_picks_highest_severity(self):
        violations = [_v(severity="low"), _v(severity="high"), _v(severity="medium")]
        assert _pick_primary(violations).severity == "high"

    def test_ties_broken_by_first_occurrence(self):
        v1 = _v(severity="high", agent="AgentA")
        v2 = _v(severity="high", agent="AgentB")
        assert _pick_primary([v1, v2]).failed_agent == "AgentA"

    def test_single_violation(self):
        v = _v(severity="medium")
        assert _pick_primary([v]) is v

    def test_medium_beats_low(self):
        assert _pick_primary([_v(severity="low"), _v(severity="medium")]).severity == "medium"


# ---------------------------------------------------------------------------
# run_repair — empty violations (no LLM)
# ---------------------------------------------------------------------------

class TestRunRepairEmpty:
    def test_empty_violations_returns_no_repair(self):
        result = asyncio.run(run_repair([], "VerifierAgent", 3))
        assert result["repair_patch"] == "no repair required"
        assert result["affected_primitive"] == ""
        assert result["confidence"] == 0.0

    def test_empty_violations_correct_keys(self):
        result = asyncio.run(run_repair([], "VerifierAgent", 3))
        assert set(result.keys()) == {"repair_patch", "affected_primitive", "patch_code", "expected_impact", "confidence"}


# ---------------------------------------------------------------------------
# run_repair — fallback path (LLM skipped)
# ---------------------------------------------------------------------------

class TestRunRepairFallback:
    def test_fallback_uses_primitive_map(self, monkeypatch):
        monkeypatch.setattr(
            "zone_b.agents.repair._ask_llm_for_patch",
            lambda *_: (_ for _ in ()).throw(RuntimeError("LLM down"))
        )
        result = asyncio.run(run_repair([_v("approval")], "ActionAgent", 5))
        assert result["affected_primitive"] == "HumanGate"

    def test_fallback_confidence_is_lower(self, monkeypatch):
        monkeypatch.setattr(
            "zone_b.agents.repair._ask_llm_for_patch",
            lambda *_: (_ for _ in ()).throw(RuntimeError("LLM down"))
        )
        result = asyncio.run(run_repair([_v("evidence")], "VerifierAgent", 3))
        assert result["confidence"] == 0.5

    def test_fallback_repair_patch_mentions_primitive(self, monkeypatch):
        monkeypatch.setattr(
            "zone_b.agents.repair._ask_llm_for_patch",
            lambda *_: (_ for _ in ()).throw(RuntimeError("LLM down"))
        )
        result = asyncio.run(run_repair([_v("tool")], "VerifierAgent", 3))
        assert "OnContextCondition" in result["repair_patch"]

    def test_fallback_for_all_five_primitive_types(self, monkeypatch):
        monkeypatch.setattr(
            "zone_b.agents.repair._ask_llm_for_patch",
            lambda *_: (_ for _ in ()).throw(RuntimeError("LLM down"))
        )
        for contract_type, expected_primitive in PRIMITIVE_MAP.items():
            result = asyncio.run(run_repair([_v(contract_type)], "Agent", 1))
            assert result["affected_primitive"] == expected_primitive

    def test_unknown_type_defaults_to_guardrail(self, monkeypatch):
        monkeypatch.setattr(
            "zone_b.agents.repair._ask_llm_for_patch",
            lambda *_: (_ for _ in ()).throw(RuntimeError("LLM down"))
        )
        result = asyncio.run(run_repair([_v("unknown_type")], "Agent", 1))
        assert result["affected_primitive"] == "Guardrail"
