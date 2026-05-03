"""
CriticAgent — reviews retrieved sources and flags weak evidence, missing citations,
and unsupported claims.

Receives output from ResearcherAgent, hands off to VerifierAgent.
"""

import json
from typing import Any

from autogen import ConversableAgent, UserProxyAgent

from zone_a.config import get_llm_config


_SYSTEM_MESSAGE = """\
You are CriticAgent in a Literature Review Assistant workflow.

You will receive a list of research sources and a task description. Your job is to
critically evaluate the evidence and return a JSON object with this exact structure
— no extra text, no markdown fences:

{
  "critique_notes": [
    "<specific concern about a source or claim>"
  ],
  "risk_flags": [
    "<risk: unsupported claim | weak evidence | missing citation | contradiction>"
  ],
  "summary": "<2-3 sentence overall critique assessment>"
}

Be specific. Reference titles or snippets where relevant. Include at least 2 critique
notes and 1 risk flag.
"""


def run_critic(retrieved_sources: list, task: str) -> dict[str, Any]:
    """Critique the retrieved sources with the LLM, return structured notes."""
    agent = ConversableAgent(
        name="CriticAgent",
        llm_config=get_llm_config(),
        system_message=_SYSTEM_MESSAGE,
        human_input_mode="NEVER",
        max_consecutive_auto_reply=1,
        code_execution_config=False,
    )

    proxy = UserProxyAgent(
        name="CriticProxy",
        llm_config=False,
        human_input_mode="NEVER",
        is_termination_msg=lambda x: True,
        max_consecutive_auto_reply=0,
        code_execution_config=False,
    )

    sources_str = json.dumps(retrieved_sources, indent=2)
    message = (
        f"Task: {task}\n\n"
        f"Retrieved sources to critique:\n{sources_str}\n\n"
        "Return the JSON object as specified."
    )

    result = proxy.initiate_chat(agent, message=message, max_turns=1)
    raw_content = result.chat_history[-1]["content"]

    content = raw_content.strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()

    parsed = json.loads(content)

    return {
        "step": 2,
        "agent": "CriticAgent",
        "type": "agent_turn",
        "critique_notes": parsed["critique_notes"],
        "risk_flags": parsed["risk_flags"],
        "summary": parsed["summary"],
        "tool_call_id": None,
        "handoff_to": "VerifierAgent",
    }


if __name__ == "__main__":
    import json as _json

    # Fixture input — mirrors what ResearcherAgent would produce
    fixture_sources = [
        {
            "title": "Multi-Agent Systems in Scientific Research",
            "url": "https://example.com/mas-research",
            "snippet": (
                "Studies suggest multi-agent systems can distribute verification tasks, "
                "potentially reducing single-agent error rates."
            ),
        },
        {
            "title": "Reliability in Automated Research Pipelines",
            "url": "https://example.com/reliability",
            "snippet": (
                "Automated pipelines with multiple agents show improved error detection "
                "in citation verification compared to single-agent baselines."
            ),
        },
        {
            "title": "Challenges in Agent Coordination",
            "url": "https://example.com/challenges",
            "snippet": (
                "Without clear handoff protocols, multi-agent systems can amplify "
                "hallucinations rather than reduce them."
            ),
        },
    ]

    output = run_critic(
        retrieved_sources=fixture_sources,
        task=(
            "Create a literature review memo on whether multi-agent systems improve "
            "reliability in research workflows."
        ),
    )
    print(_json.dumps(output, indent=2))
