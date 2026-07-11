from src.adapters.claude_adapter import ClaudeAdapter
from src.adapters.llm_adapter import LLMAdapter


def get_llm_adapter(settings) -> LLMAdapter:
    if settings.llm_provider == "anthropic":
        return ClaudeAdapter(
            api_key=settings.anthropic_api_key.get_secret_value(),
            model=settings.anthropic_model,
        )
    raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")
