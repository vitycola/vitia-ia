"""Tests for food-parsing prompt content (R7)."""

import pytest

from src.adapters.prompts import TEXT_PROMPT, VISION_PROMPT


@pytest.mark.parametrize("prompt", [VISION_PROMPT, TEXT_PROMPT])
def test_prompt_contains_bacon_false_friend_guidance(prompt: str) -> None:
    assert "bacon" in prompt
    assert "beicon" in prompt
    assert "panceta ahumada" in prompt


@pytest.mark.parametrize("prompt", [VISION_PROMPT, TEXT_PROMPT])
def test_prompt_preserves_spanish_name_guidance(prompt: str) -> None:
    assert "the food name in Spanish (castellano)" in prompt
