from anthropic import AsyncAnthropic
from anthropic.types import ToolParam

from src.adapters.prompts import TEXT_PROMPT, VISION_PROMPT
from src.domain.food import IdentifiedFoods

TOOL: ToolParam = {
    "name": "record_identified_foods",
    "description": "Record the food items identified with weight and confidence.",
    "input_schema": {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "estimated_grams": {"type": "number"},
                        "confidence": {"type": "number"},
                    },
                    "required": ["name", "estimated_grams", "confidence"],
                },
            }
        },
        "required": ["items"],
    },
}


class ClaudeAdapter:
    def __init__(self, api_key: str, model: str, client: AsyncAnthropic | None = None) -> None:
        self._model = model
        self._client = client or AsyncAnthropic(api_key=api_key)

    async def _call(self, content: list) -> IdentifiedFoods:
        resp = await self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            tools=[TOOL],
            tool_choice={"type": "tool", "name": "record_identified_foods"},
            messages=[{"role": "user", "content": content}],
        )
        block = next(b for b in resp.content if b.type == "tool_use")
        return IdentifiedFoods.model_validate(block.input)

    async def analyze_image(self, image_b64: str, media_type: str, context: str | None = None) -> IdentifiedFoods:
        prompt = VISION_PROMPT
        if context:
            prompt = f"{VISION_PROMPT}\n\nUser context: {context}"
        content = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": image_b64,
                },
            },
            {"type": "text", "text": prompt},
        ]
        return await self._call(content)

    async def parse_text(self, text: str) -> IdentifiedFoods:
        content = [{"type": "text", "text": f"{TEXT_PROMPT}\n\n{text}"}]
        return await self._call(content)
