from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
from fastapi import APIRouter, Depends

from src.adapters.off_client import OFFFallbackClient
from src.adapters.supabase_client import GenericFoodRepository
from src.config import get_settings
from src.domain.food import IdentifiedFoods, MatchResult
from src.services.food_matcher import FoodMatcherService

router = APIRouter(prefix="/food", tags=["food"])


@asynccontextmanager
async def _lifespan_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient() as client:
        yield client


async def get_food_matcher_service() -> AsyncGenerator[FoodMatcherService, None]:
    settings = get_settings()
    async with httpx.AsyncClient() as client:
        repo = GenericFoodRepository(
            client=client,
            base_url=settings.supabase_url,
            anon_key=settings.supabase_anon_key.get_secret_value(),
        )
        off_client = OFFFallbackClient(client=client)
        yield FoodMatcherService(repo=repo, off_client=off_client)


@router.post("/match", response_model=MatchResult)
async def match_foods(
    body: IdentifiedFoods,
    service: FoodMatcherService = Depends(get_food_matcher_service),  # noqa: B008
) -> MatchResult:
    return await service.match_all(body)
