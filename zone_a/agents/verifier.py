import json
from autogen import ConversableAgent, UserProxyAgent
from zone_a.config import get_llm_config


def run_verifier(retrieved_sources: list, critique_notes: list) -> dict:
    agent = ConversableAgent(
        name="VerifierAgent",
        llm_config=get_llm_config(),
        system_message=(
            "You are a source verifier. Given retrieved sources and critique notes, "
            "assess whether the sources are credible and sufficient. "
            "Respond with a short verification narrative."
        ),
        human_input_mode="NEVER",
        max_consecutive_auto_reply=1,
        code_execution_config=False,
    )
    proxy = UserProxyAgent(
        name="Proxy",
        llm_config=False,
        human_input_mode="NEVER",
        is_termination_msg=lambda x: True,
        max_consecutive_auto_reply=0,
        code_execution_config=False,
    )

    message = (
        f"Sources to verify: {json.dumps(retrieved_sources)}\n"
        f"Critique notes: {json.dumps(critique_notes)}"
    )
    result = proxy.initiate_chat(agent, message=message, max_turns=1)
    narrative = result.chat_history[-1]["content"]

    # intentional failures: tool_call_id=None, verified_sources_count=0
    return {
        "verified": bool(narrative),
        "tool_call_id": None,
        "verified_sources_count": 0,
        "step": 3,
        "agent": "VerifierAgent",
        "handoff_to": "ReporterAgent",
    }


if __name__ == "__main__":
    sources = [{"title": "Paper A", "url": "https://example.com/a"}]
    notes = ["Methodology seems sound"]
    out = run_verifier(sources, notes)
    print(out)
