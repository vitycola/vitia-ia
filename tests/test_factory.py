import pytest

from src.adapters.claude_adapter import ClaudeAdapter
from src.adapters.factory import get_llm_adapter
from src.config import Settings, get_settings


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_get_llm_adapter_returns_claude_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    settings = Settings()
    adapter = get_llm_adapter(settings)
    assert isinstance(adapter, ClaudeAdapter)


def test_get_llm_adapter_unknown_provider_raises_value_error() -> None:
    # Build a minimal stub that mimics enough of Settings for factory to branch
    class FakeSettings:
        llm_provider = "openai"

    with pytest.raises(ValueError, match="openai"):
        get_llm_adapter(FakeSettings())


def test_settings_default_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    settings = Settings()
    assert settings.llm_provider == "anthropic"


def test_settings_api_key_is_secret_str(monkeypatch: pytest.MonkeyPatch) -> None:
    from pydantic import SecretStr

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    settings = Settings()
    assert isinstance(settings.anthropic_api_key, SecretStr)
    assert "sk-ant-test" not in str(settings.anthropic_api_key)


def test_settings_missing_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    from pydantic import ValidationError

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    with pytest.raises(ValidationError):
        Settings()
