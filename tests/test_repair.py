"""Tests for zone_b/agents/repair.py — deterministic parts only."""
import asyncio
from shared.models import Violation
from zone_b.agents.repair import PRIMITIVE_MAP, _pick_primary, run_repair


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
        assert result["patches"] == []
        assert result["repair_patch"] == "no repair required"
        assert result["affected_primitive"] == ""
        assert result["confidence"] == 0.0

    def test_empty_violations_correct_keys(self):
        result = asyncio.run(run_repair([], "VerifierAgent", 3))
        assert set(result.keys()) == {
            "patches",
            "repair_patch",
            "affected_primitive",
            "patch_code",
            "expected_impact",
            "confidence",
        }


# ---------------------------------------------------------------------------
# run_repair — fallback path (LLM skipped)
# ---------------------------------------------------------------------------

class TestRunRepairFallback:
    def test_returns_one_patch_per_violation_in_input_order(self, monkeypatch):
        monkeypatch.setattr(
            "zone_b.agents.repair._ask_llm_for_patch",
            lambda v, *_: {
                "patch_code": f"# patch {v.contract_type}",
                "expected_impact": f"fixes {v.contract_type}",
            },
        )
        violations = [_v("tool"), _v("routing", "medium"), _v("schema", "medium")]
        result = asyncio.run(run_repair(violations, "VerifierAgent", 3))

        assert [p["contract_type"] for p in result["patches"]] == [
            "tool",
            "routing",
            "schema",
        ]
        assert [p["affected_primitive"] for p in result["patches"]] == [
            "OnContextCondition",
            "Handoff",
            "Guardrail",
        ]

    def test_legacy_scalar_fields_mirror_highest_severity_patch(self, monkeypatch):
        monkeypatch.setattr(
            "zone_b.agents.repair._ask_llm_for_patch",
            lambda v, *_: {
                "patch_code": f"# patch {v.contract_type}",
                "expected_impact": f"fixes {v.contract_type}",
            },
        )
        violations = [_v("routing", "medium"), _v("evidence", "high")]
        result = asyncio.run(run_repair(violations, "ReporterAgent", 4))

        assert result["patches"][1]["contract_type"] == "evidence"
        assert result["affected_primitive"] == "Guardrail"
        assert result["repair_patch"] == result["patches"][1]["repair_patch"]
        assert result["patch_code"] == "# patch evidence"

    def test_fallback_is_isolated_per_patch(self, monkeypatch):
        def fake_patch(violation, *_):
            if violation.contract_type == "tool":
                raise RuntimeError("patch failed")
            return {
                "patch_code": f"# patch {violation.contract_type}",
                "expected_impact": f"fixes {violation.contract_type}",
            }

        monkeypatch.setattr("zone_b.agents.repair._ask_llm_for_patch", fake_patch)
        result = asyncio.run(run_repair([_v("tool"), _v("approval")], "Agent", 1))

        assert result["patches"][0]["confidence"] == 0.5
        assert "tool violation" in result["patches"][0]["patch_code"]
        assert result["patches"][1]["confidence"] == 0.85
        assert result["patches"][1]["patch_code"] == "# patch approval"

    def test_fallback_uses_primitive_map(self, monkeypatch):
        monkeypatch.setattr(
            "zone_b.agents.repair._ask_llm_for_patch",
            lambda *_: (_ for _ in ()).throw(RuntimeError("LLM down"))
        )
        result = asyncio.run(run_repair([_v("approval")], "ActionAgent", 5))
        assert result["patches"][0]["affected_primitive"] == "HumanGate"
        assert result["affected_primitive"] == "HumanGate"

    def test_fallback_confidence_is_lower(self, monkeypatch):
        monkeypatch.setattr(
            "zone_b.agents.repair._ask_llm_for_patch",
            lambda *_: (_ for _ in ()).throw(RuntimeError("LLM down"))
        )
        result = asyncio.run(run_repair([_v("evidence")], "VerifierAgent", 3))
        assert result["patches"][0]["confidence"] == 0.5
        assert result["confidence"] == 0.5

    def test_fallback_repair_patch_mentions_primitive(self, monkeypatch):
        monkeypatch.setattr(
            "zone_b.agents.repair._ask_llm_for_patch",
            lambda *_: (_ for _ in ()).throw(RuntimeError("LLM down"))
        )
        result = asyncio.run(run_repair([_v("tool")], "VerifierAgent", 3))
        assert "OnContextCondition" in result["patches"][0]["repair_patch"]
        assert "OnContextCondition" in result["repair_patch"]

    def test_fallback_for_all_five_primitive_types(self, monkeypatch):
        monkeypatch.setattr(
            "zone_b.agents.repair._ask_llm_for_patch",
            lambda *_: (_ for _ in ()).throw(RuntimeError("LLM down"))
        )
        for contract_type, expected_primitive in PRIMITIVE_MAP.items():
            result = asyncio.run(run_repair([_v(contract_type)], "Agent", 1))
            assert result["patches"][0]["affected_primitive"] == expected_primitive
            assert result["affected_primitive"] == expected_primitive

    def test_unknown_type_defaults_to_guardrail(self, monkeypatch):
        monkeypatch.setattr(
            "zone_b.agents.repair._ask_llm_for_patch",
            lambda *_: (_ for _ in ()).throw(RuntimeError("LLM down"))
        )
        result = asyncio.run(run_repair([_v("unknown_type")], "Agent", 1))
        assert result["patches"][0]["affected_primitive"] == "Guardrail"
        assert result["affected_primitive"] == "Guardrail"
