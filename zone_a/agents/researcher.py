"""
ResearcherAgent — searches Tavily and asks the LLM to format structured sources.

Intentional Zone A behaviour (feeds Contract violations for Zone B):
  - tool_call_id is always "tc_001" (hard-coded, deterministic for the demo)
  - verified_sources_count is NOT set here (left at 0 by design)
"""

import json
import os
import time
from typing import Any

from autogen import ConversableAgent
from dotenv import load_dotenv
from tavily import TavilyClient

from zone_a.config import get_llm_config
from zone_a.agents._utils import make_proxy, strip_json_fences

load_dotenv()


_SYSTEM_MESSAGE = """\
You are ResearcherAgent in a Literature Review Assistant workflow.

You will receive raw search results from Tavily. Your job is to return a JSON object
with this exact structure — no extra text, no markdown fences:

{
  "retrieved_sources": [
    {
      "title": "<title>",
      "url": "<url>",
      "snippet": "<short relevant excerpt>"
    }
  ],
  "summary": "<2-3 sentence synthesis of what the sources collectively say>"
}

Include at most 3 sources. Use only the information provided to you.
"""


def run_researcher(task: str, research_question: str) -> dict[str, Any]:
    """Search Tavily, format results with the LLM, return structured output."""
    tavily_api_key = os.environ.get("TAVILY_API_KEY", "")
    if not tavily_api_key:
        raise EnvironmentError(
            "TAVILY_API_KEY is not set. Add it to your .env file."
        )

    client = TavilyClient(api_key=tavily_api_key)
    raw_results = client.search(
        query=research_question,
        max_results=3,
        search_depth="basic",
    )
    results_str = json.dumps(raw_results.get("results", []), indent=2)

    agent = ConversableAgent(
        name="ResearcherAgent",
        llm_config=get_llm_config(),
        system_message=_SYSTEM_MESSAGE,
        human_input_mode="NEVER",
        max_consecutive_auto_reply=1,
        code_execution_config=False,
    )

    proxy = make_proxy("ResearcherProxy")

    message = (
        f"Task: {task}\n\n"
        f"Research question: {research_question}\n\n"
        f"Tavily search results:\n{results_str}\n\n"
        "Return the JSON object as specified."
    )

    result = proxy.initiate_chat(agent, message=message, max_turns=1)
    parsed = json.loads(strip_json_fences(result.chat_history[-1]["content"]))

    return {
        "step": 1,
        "agent": "ResearcherAgent",
        "type": "agent_turn",
        "content": parsed["summary"],
        "tool_call_id": "tc_001",
        "context_delta": {
            "retrieved_sources": parsed["retrieved_sources"],
            "tool_events": [{
                "tool_name": "tavily_search",
                "input": research_question,
                "output": f"{len(parsed['retrieved_sources'])} results",
                "status": "success",
                "evidence_id": "ev_001",
                "timestamp": time.time(),
            }],
        },
        "handoff_to": "CriticAgent",
        "timestamp": time.time(),
    }


if __name__ == "__main__":
    import json as _json
    import pathlib

    fixture = _json.loads(
        (pathlib.Path(__file__).parent.parent / "fixtures" / "task.json").read_text()
    )
    output = run_researcher(
        task=fixture["task"],
        research_question=fixture["research_question"],
    )
    print(_json.dumps(output, indent=2))
