import json
import time
from autogen import ConversableAgent
from zone_a.config import get_llm_config
from zone_a.agents._utils import make_proxy, strip_json_fences


def run_reporter(verified_sources_count: int, retrieved_sources: list, critique_notes: list) -> dict:
    # runs even when verified_sources_count=0 — downstream consequence of VerifierAgent breakage
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
    proxy = make_proxy("ReporterProxy")

    message = (
        f"Verified sources count: {verified_sources_count}\n"
        f"Sources: {json.dumps(retrieved_sources)}\n"
        f"Critique notes: {json.dumps(critique_notes)}"
    )
    result = proxy.initiate_chat(agent, message=message, max_turns=1)
    raw = strip_json_fences(result.chat_history[-1]["content"])

    try:
        final_output = json.loads(raw)
    except json.JSONDecodeError:
        final_output = {"summary": raw, "claims": [], "citations": [], "risks": [], "next_steps": []}

    return {
        "step": 4,
        "agent": "ReporterAgent",
        "type": "agent_turn",
        "content": final_output.get("summary", ""),
        "tool_call_id": None,
        "context_delta": {"final_output": final_output},
        "handoff_to": "ActionAgent",
        "timestamp": time.time(),
    }


if __name__ == "__main__":
    sources = [{"title": "Paper A", "url": "https://example.com/a"}]
    notes = ["Methodology seems sound"]
    out = run_reporter(0, sources, notes)
    print(out)
