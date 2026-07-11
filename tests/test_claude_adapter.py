from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.adapters.claude_adapter import ClaudeAdapter
from src.adapters.prompts import TEXT_PROMPT, VISION_PROMPT
from src.domain.food import IdentifiedFoods

APPLE_ITEM = {"name": "Apple", "estimated_grams": 180.0, "confidence": 0.9}
RICE_ITEM = {"name": "Rice", "estimated_grams": 200.0, "confidence": 0.85}


def make_tool_use_block(items: list) -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", input={"items": items})


def make_mock_client(items: list) -> AsyncMock:
    block = make_tool_use_block(items)
    response = SimpleNamespace(content=[block])
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=response)
    return mock_client


@pytest.fixture
def apple_client() -> AsyncMock:
    return make_mock_client([APPLE_ITEM])


@pytest.fixture
def rice_client() -> AsyncMock:
    return make_mock_client([RICE_ITEM])


async def test_analyze_image_returns_identified_foods(apple_client: AsyncMock) -> None:
    adapter = ClaudeAdapter(api_key="dummy", model="claude-test", client=apple_client)
    result = await adapter.analyze_image("abc123", "image/jpeg")

    assert isinstance(result, IdentifiedFoods)
    assert result.items[0].name == "Apple"
    assert result.items[0].estimated_grams == 180.0
    assert result.items[0].confidence == 0.9


async def test_analyze_image_sends_base64_block(apple_client: AsyncMock) -> None:
    adapter = ClaudeAdapter(api_key="dummy", model="claude-test", client=apple_client)
    await adapter.analyze_image("abc123", "image/jpeg")

    call_kwargs = apple_client.messages.create.call_args.kwargs
    content = call_kwargs["messages"][0]["content"]

    image_blocks = [b for b in content if b.get("type") == "image"]
    assert len(image_blocks) == 1
    source = image_blocks[0]["source"]
    assert source["type"] == "base64"
    assert source["data"] == "abc123"
    assert source["media_type"] == "image/jpeg"


async def test_analyze_image_includes_vision_prompt(apple_client: AsyncMock) -> None:
    adapter = ClaudeAdapter(api_key="dummy", model="claude-test", client=apple_client)
    await adapter.analyze_image("abc123", "image/jpeg")

    call_kwargs = apple_client.messages.create.call_args.kwargs
    content = call_kwargs["messages"][0]["content"]
    text_blocks = [b for b in content if b.get("type") == "text"]

    assert any(VISION_PROMPT in b["text"] for b in text_blocks)


async def test_parse_text_returns_identified_foods(rice_client: AsyncMock) -> None:
    adapter = ClaudeAdapter(api_key="dummy", model="claude-test", client=rice_client)
    result = await adapter.parse_text("200g white rice")

    assert isinstance(result, IdentifiedFoods)
    assert result.items[0].name == "Rice"
    assert result.items[0].estimated_grams == 200.0
    assert result.items[0].confidence == 0.85


async def test_parse_text_includes_text_prompt_and_user_text(rice_client: AsyncMock) -> None:
    adapter = ClaudeAdapter(api_key="dummy", model="claude-test", client=rice_client)
    await adapter.parse_text("200g white rice")

    call_kwargs = rice_client.messages.create.call_args.kwargs
    content = call_kwargs["messages"][0]["content"]
    text_blocks = [b for b in content if b.get("type") == "text"]

    combined = " ".join(b["text"] for b in text_blocks)
    assert TEXT_PROMPT in combined
    assert "200g white rice" in combined


async def test_tool_choice_is_forced(apple_client: AsyncMock) -> None:
    adapter = ClaudeAdapter(api_key="dummy", model="claude-test", client=apple_client)
    await adapter.analyze_image("abc123", "image/jpeg")

    call_kwargs = apple_client.messages.create.call_args.kwargs
    assert call_kwargs["tool_choice"] == {"type": "tool", "name": "record_identified_foods"}
