WORKFLOW_CONTRACT = {
    "workflow": "LiteratureReviewAssistant",
    "run_id": "run_041",
    "rules": [
        {
            "id": "C1",
            "type": "evidence",
            "rule": "Reporter may only write final_output when verified_sources_count > 0",
            "severity": "high",
        },
        {
            "id": "C2",
            "type": "tool",
            "rule": (
                "Any agent whose content contains 'verified', 'searched', or 'checked' "
                "must have a non-null tool_call_id"
            ),
            "severity": "high",
        },
        {
            "id": "C3",
            "type": "routing",
            "rule": (
                "ReporterAgent must run after VerifierAgent has a successful tool event; "
                "ActionAgent requires HumanGateAgent first"
            ),
            "severity": "medium",
        },
        {
            "id": "C4",
            "type": "approval",
            "rule": "ActionAgent requires approval_status == 'approved'",
            "severity": "high",
        },
        {
            "id": "C5",
            "type": "schema",
            "rule": (
                "final_output must include keys: summary, claims[], citations[], "
                "risks[], next_steps[]"
            ),
            "severity": "medium",
        },
    ],
}
