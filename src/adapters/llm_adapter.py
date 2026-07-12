from typing import Protocol, runtime_checkable

from src.domain.food import IdentifiedFoods


@runtime_checkable
class LLMAdapter(Protocol):
    async def analyze_image(self, image_b64: str, media_type: str) -> IdentifiedFoods: ...

    async def parse_text(self, text: str) -> IdentifiedFoods: ...
