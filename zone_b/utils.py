import json
from autogen import UserProxyAgent


def make_proxy(name: str) -> UserProxyAgent:
    return UserProxyAgent(
        name=name,
        llm_config=False,
        human_input_mode="NEVER",
        is_termination_msg=lambda x: True,
        max_consecutive_auto_reply=0,
        code_execution_config=False,
    )


def parse_json_body(body: str) -> dict:
    """Strip ```json fences and parse. Raises ValueError on failure."""
    body = body.strip()
    if body.startswith("```"):
        body = body.split("```")[1]
        if body.startswith("json"):
            body = body[4:]
    try:
        return json.loads(body)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON from LLM response: {e}") from e
