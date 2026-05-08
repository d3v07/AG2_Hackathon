"""Tests for shared/models.py — dataclass field integrity."""
from dataclasses import fields
from shared.models import (
    ToolEvent, TraceEvent, RunTrace, ContextSnapshot,
    Violation, RoleContract, EvidenceContract, RouteContract, ApprovalContract
)


class TestToolEvent:
    def test_instantiation(self):
        e = ToolEvent(
            tool_name="tavily_search", input="query", output="results",
            status="success", evidence_id="ev_001", timestamp=1.0
        )
        assert e.tool_name == "tavily_search"
        assert e.status == "success"
        assert e.timestamp == 1.0

    def test_required_fields(self):
        expected = {"tool_name", "input", "output", "status", "evidence_id", "timestamp"}
        assert {f.name for f in fields(ToolEvent)} == expected

    def test_failure_status(self):
        e = ToolEvent(tool_name="t", input=None, output=None,
                      status="failure", evidence_id="", timestamp=0.0)
        assert e.status == "failure"


class TestTraceEvent:
    def test_instantiation(self):
        e = TraceEvent(
            step=1, agent="ResearcherAgent", type="agent_turn",
            content="Found sources", tool_call_id="tc_001",
            context_delta={"retrieved_sources": ["s1"]},
            handoff_to="CriticAgent", timestamp=0.5
        )
        assert e.step == 1
        assert e.agent == "ResearcherAgent"
        assert e.tool_call_id == "tc_001"

    def test_required_fields(self):
        expected = {"step", "agent", "type", "content", "tool_call_id",
                    "context_delta", "handoff_to", "timestamp"}
        assert {f.name for f in fields(TraceEvent)} == expected

    def test_tool_call_id_can_be_none(self):
        e = TraceEvent(step=1, agent="A", type="agent_turn", content="",
                       tool_call_id=None, context_delta={}, handoff_to=None, timestamp=0.0)
        assert e.tool_call_id is None

    def test_handoff_to_can_be_none(self):
        e = TraceEvent(step=5, agent="ActionAgent", type="agent_turn", content="",
                       tool_call_id=None, context_delta={}, handoff_to=None, timestamp=0.0)
        assert e.handoff_to is None


class TestRunTrace:
    def test_instantiation(self):
        rt = RunTrace(run_id="run_001", workflow_name="TestFlow", events=[], final_output=None)
        assert rt.run_id == "run_001"
        assert rt.events == []

    def test_required_fields(self):
        expected = {"run_id", "workflow_name", "events", "final_output"}
        assert {f.name for f in fields(RunTrace)} == expected

    def test_events_list(self):
        e = TraceEvent(step=1, agent="A", type="agent_turn", content="",
                       tool_call_id=None, context_delta={}, handoff_to=None, timestamp=0.0)
        rt = RunTrace(run_id="r", workflow_name="w", events=[e], final_output=None)
        assert len(rt.events) == 1
        assert rt.events[0].agent == "A"


class TestContextSnapshot:
    def test_instantiation(self):
        snap = ContextSnapshot(
            retrieved_sources=["s1"], verified_sources_count=1,
            tool_events=[], approval_status="approved",
            failed_agent=None, failed_step=None, final_output=None
        )
        assert snap.verified_sources_count == 1
        assert snap.approval_status == "approved"

    def test_required_fields(self):
        expected = {"retrieved_sources", "verified_sources_count", "tool_events",
                    "approval_status", "failed_agent", "failed_step", "final_output"}
        assert {f.name for f in fields(ContextSnapshot)} == expected

    def test_approval_status_values(self):
        for status in ("pending", "approved", "rejected"):
            snap = ContextSnapshot(
                retrieved_sources=[], verified_sources_count=0, tool_events=[],
                approval_status=status, failed_agent=None, failed_step=None, final_output=None
            )
            assert snap.approval_status == status


class TestViolation:
    def test_instantiation(self):
        v = Violation(
            contract_type="evidence", severity="high",
            rule="verified_sources_count must be > 0",
            expected="count > 0", observed="count == 0",
            failed_agent="VerifierAgent", failed_step=3
        )
        assert v.contract_type == "evidence"
        assert v.severity == "high"
        assert v.failed_step == 3

    def test_required_fields(self):
        expected = {"contract_type", "severity", "rule", "expected",
                    "observed", "failed_agent", "failed_step", "span_id"}
        assert {f.name for f in fields(Violation)} == expected

    def test_all_contract_types(self):
        for ct in ("evidence", "tool", "routing", "approval", "schema"):
            v = Violation(contract_type=ct, severity="high", rule="r",
                          expected="e", observed="o", failed_agent="A", failed_step=1)
            assert v.contract_type == ct

    def test_all_severity_levels(self):
        for sev in ("high", "medium", "low"):
            v = Violation(contract_type="evidence", severity=sev, rule="r",
                          expected="e", observed="o", failed_agent="A", failed_step=1)
            assert v.severity == sev


class TestContractDataclasses:
    def test_role_contract(self):
        rc = RoleContract(agent_name="A", allowed_actions=["search"],
                          required_inputs=["query"], forbidden_outputs=["raw_html"])
        assert rc.agent_name == "A"
        assert "search" in rc.allowed_actions

    def test_evidence_contract(self):
        ec = EvidenceContract(claim_type="factual",
                              required_source_count=2, required_tool_event="tavily_search")
        assert ec.required_source_count == 2

    def test_route_contract(self):
        rc = RouteContract(from_agent="A", to_agent="B",
                           condition="always", forbidden_path=["C", "D"])
        assert rc.forbidden_path == ["C", "D"]

    def test_approval_contract(self):
        ac = ApprovalContract(side_effect="file_write",
                              required_approval_state="approved", human_gate="HumanGate")
        assert ac.required_approval_state == "approved"
