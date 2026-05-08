"""Violation recurrence memory tests."""
from __future__ import annotations

from zone_b.memory.violation_memory import recurrence_key


def test_recurrence_key_uses_stable_violation_identity():
    key = recurrence_key(
        {
            "id": "V-001",
            "contract_type": "routing",
            "type": "ROUTING",
            "rule": "Reporter handoff must be gated",
            "title": "synthetic dashboard title",
            "failed_agent": "GroupChatManager",
            "failed_step": 10,
        }
    )

    assert key == "routing|GroupChatManager|Reporter handoff must be gated"
