import logging
import time
import uuid
from collections.abc import AsyncGenerator

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.adapters.factory import get_llm_adapter
from src.adapters.off_client import OFFFallbackClient
from src.adapters.supabase_client import GenericFoodRepository
from src.auth.dependencies import get_current_user
from src.auth.models import CurrentUser
from src.config import get_settings
from src.domain.food import MatchResult
from src.services.errors import LLMError, LLMTimeoutError
from src.services.food_matcher import FoodMatcherService
from src.services.text_parsing import TextParsingService

router = APIRouter(prefix="/api", tags=["parse"])

logger = logging.getLogger("vitia.parse")


class ParseRequest(BaseModel):
    text: str


async def get_text_parsing_service() -> AsyncGenerator[TextParsingService, None]:
    settings = get_settings()
    llm = get_llm_adapter(settings)
    async with httpx.AsyncClient() as client:
        repo = GenericFoodRepository(
            client=client,
            base_url=settings.supabase_url,
            anon_key=settings.supabase_anon_key.get_secret_value(),
        )
        off_client = OFFFallbackClient(client=client)
        matcher = FoodMatcherService(repo=repo, off_client=off_client)
        yield TextParsingService(llm=llm, matcher=matcher)


@router.post("/parse", response_model=MatchResult)
async def parse_text(
    body: ParseRequest,
    service: TextParsingService = Depends(get_text_parsing_service),  # noqa: B008
    _user: CurrentUser = Depends(get_current_user),  # noqa: B008
) -> MatchResult:
    if body.text.strip() == "":
        raise HTTPException(status_code=422, detail="text must not be empty")

    t_start = time.monotonic()
    correlation_id = str(uuid.uuid4())

    logger.info(
        "parse_request",
        extra={
            "correlation_id": correlation_id,
            "text_length": len(body.text),
        },
    )

    try:
        result = await service.parse(body.text, correlation_id)
    except LLMTimeoutError as exc:
        raise HTTPException(
            status_code=504, detail="LLM request timed out. Please try again."
        ) from exc
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=f"LLM error: {exc}") from exc

    logger.info(
        "parse_response_sent",
        extra={
            "correlation_id": correlation_id,
            "total_duration_ms": int((time.monotonic() - t_start) * 1000),
            "status_code": 200,
        },
    )

    return result
