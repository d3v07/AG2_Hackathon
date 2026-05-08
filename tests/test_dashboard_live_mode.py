"""Static dashboard live-mode wiring tests."""
from __future__ import annotations

from pathlib import Path


def test_public_dashboard_defaults_to_fixture_and_can_open_live_sse():
    html = Path("public/index.html").read_text()

    assert "FIXTURE_DATA" in html
    assert "source-toggle" in html
    assert "EventSource(" in html
    assert "/api/runs/${liveRunId}/events/token" in html
    assert "stream_token=" in html
    assert "X-Concord-API-Key" in html


def test_public_dashboard_lifts_concord_data_into_react_state():
    html = Path("public/index.html").read_text()

    assert "useState(FIXTURE_DATA)" in html
    assert "setData(normalizeDashboardData(liveData, { fallbackFixture: false }))" in html
    assert "D = data;" in html


def test_public_dashboard_uses_dynamic_live_shapes():
    html = Path("public/index.html").read_text()

    assert "buildAgentStepMap(agents, trace)" in html
    assert "topologyNodes" in html
    assert "payload.sequence" in html
    assert "reconnectTimer = setTimeout(openLiveRun, 1000)" in html
    assert "if (!playing && step < totalSteps) setStep(totalSteps)" in html


def test_public_dashboard_renders_recurring_dag_badges():
    html = Path("public/index.html").read_text()

    assert "recurrence-badge" in html
    assert "RECURRING" in html
    assert "recurrenceTitle(" in html
    assert "recurrenceForEdge(" in html
    assert "recurrenceForNode(" in html
    assert "item.edge.from === edge.from" in html
    assert "item.edge.to === edge.to" in html
    assert "CONTRACT_ID_BY_TYPE" not in html
    assert ".dag-svg { min-width: 1240px; }" in html
