import json


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
