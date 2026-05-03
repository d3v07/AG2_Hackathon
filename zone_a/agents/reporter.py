import json
from autogen import ConversableAgent, UserProxyAgent
from zone_a.config import get_llm_config


def run_reporter(verified_sources_count: int, retrieved_sources: list, critique_notes: list) -> dict:
    # intentional failure: no guard on verified_sources_count — runs even when count is 0
    agent = ConversableAgent(
        name="ReporterAgent",
        llm_config=get_llm_config(),
        system_message=(
            "You are a research reporter. Given sources and critique notes, produce a structured report. "
            "Respond with JSON containing: summary (str), claims (list of str), "
            "citations (list of str), risks (list of str), next_steps (list of str)."
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
        f"Verified sources count: {verified_sources_count}\n"
        f"Sources: {json.dumps(retrieved_sources)}\n"
        f"Critique notes: {json.dumps(critique_notes)}"
    )
    result = proxy.initiate_chat(agent, message=message, max_turns=1)
    raw = result.chat_history[-1]["content"]

    try:
        start = raw.index("{")
        end = raw.rindex("}") + 1
        final_output = json.loads(raw[start:end])
    except (ValueError, json.JSONDecodeError):
        final_output = {
            "summary": raw,
            "claims": [],
            "citations": [],
            "risks": [],
            "next_steps": [],
        }

    return {
        "final_output": final_output,
        "step": 4,
        "agent": "ReporterAgent",
        "handoff_to": "ActionAgent",
    }


if __name__ == "__main__":
    sources = [{"title": "Paper A", "url": "https://example.com/a"}]
    notes = ["Methodology seems sound"]
    out = run_reporter(0, sources, notes)
    print(out)
