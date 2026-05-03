import os
from dotenv import load_dotenv

load_dotenv()


def get_llm_config(model: str = "google/gemini-2.5-flash") -> dict:
    """Return llm_config dict for ConversableAgent / GroupChatManager."""
    return {
        "config_list": [{
            "model": model,
            "api_key": os.environ["OPENROUTER_API_KEY"],
            "base_url": "https://openrouter.ai/api/v1",
            "api_type": "openai",
        }],
        "temperature": 0.1,
    }
