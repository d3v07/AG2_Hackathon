import os
from dotenv import load_dotenv
from autogen.beta.config import OpenAIConfig

load_dotenv()


def get_config(model: str = "google/gemini-2.5-flash") -> OpenAIConfig:
    """Return OpenAIConfig for OpenRouter/Gemini."""
    return OpenAIConfig(
        model=model,
        streaming=True,
        api_key=os.environ["OPENROUTER_API_KEY"],
        base_url="https://openrouter.ai/api/v1",
        max_completion_tokens=1024,
    )
