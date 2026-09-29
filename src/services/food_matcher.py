import asyncio
import logging
import unicodedata

from rapidfuzz import fuzz, process

from src.adapters.off_client import OFFFallbackClient
from src.adapters.supabase_client import GenericFoodRepository
from src.domain.food import (
    IdentifiedFood,
    IdentifiedFoods,
    MacrosPer100g,
    MacroTotals,
    MatchedFood,
    MatchResult,
)
from src.services.match_review import review_reasons

logger = logging.getLogger("vitia.match")

REPO_ERROR = "repo_error"
MATCH_ERROR = "match_error"

# Configurable threshold for fuzzy matching against Supabase candidates.
# Scores are 0–100; values below this fall through to OFF or unmatched.
FUZZY_MATCH_THRESHOLD = 70


def normalize(name: str) -> str:
    """Lowercase and strip accents (NFD decomposition, remove Mn category)."""
    nfd = unicodedata.normalize("NFD", name.lower())
    return "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")


def _compute_actuals(macros: MacrosPer100g | None, grams: float) -> MacroTotals:
    if macros is None:
        return MacroTotals()
    factor = grams / 100.0
    return MacroTotals(
        calories=macros.calories * factor,
        protein=macros.protein * factor,
        carbs=macros.carbs * factor,
        fat=macros.fat * factor,
    )


def _sum_totals(items: list[MatchedFood]) -> MacroTotals:
    return MacroTotals(
        calories=sum(i.macros_actual.calories for i in items),
        protein=sum(i.macros_actual.protein for i in items),
        carbs=sum(i.macros_actual.carbs for i in items),
        fat=sum(i.macros_actual.fat for i in items),
    )


class FoodMatcherService:
    def __init__(self, repo: GenericFoodRepository, off_client: OFFFallbackClient) -> None:
        self._repo = repo
        self._off = off_client

    async def match_all(
        self, foods: IdentifiedFoods, correlation_id: str | None = None
    ) -> MatchResult:
        raw = await asyncio.gather(
            *[self._match_one(food, correlation_id) for food in foods.items],
            return_exceptions=True,
        )
        items: list[MatchedFood] = []
        repo_failed = False
        item_failed = False
        for food, result in zip(foods.items, raw, strict=True):
            if isinstance(result, BaseException):
                item_failed = True
                logger.error(
                    "matcher_item_error",
                    exc_info=result,
                    extra={
                        "correlation_id": correlation_id,
                        "stage": "match",
                        "error_type": type(result).__name__,
                        "error_message": str(result),
                        "food_name": food.name,
                    },
                )
                item = MatchedFood(
                    query_name=food.name,
                    grams=food.estimated_grams,
                    source="unmatched",
                    matched_name=None,
                    score=None,
                    macros_per_100g=None,
                    macros_actual=MacroTotals(),
                    low_confidence=True,
                )
            else:
                item, item_repo_failed = result
                repo_failed = repo_failed or item_repo_failed
            self._apply_review(item, food, correlation_id)
            items.append(item)

        degraded_reason = REPO_ERROR if repo_failed else MATCH_ERROR if item_failed else None
        return MatchResult(
            items=items,
            totals=_sum_totals(items),
            degraded=degraded_reason is not None,
            degraded_reason=degraded_reason,
            skipped=[i.query_name for i in items if i.source == "unmatched"],
        )

    @staticmethod
    def _apply_review(item: MatchedFood, food: IdentifiedFood, correlation_id: str | None) -> None:
        """Attach advisory review flags. A failure here must never affect the item."""
        try:
            reasons = review_reasons(item, food)
        except Exception:
            return
        if not reasons:
            return
        item.review_reasons = reasons
        item.review = True
        logger.info(
            "matcher_review_flagged",
            extra={
                "correlation_id": correlation_id,
                "food_name": food.name,
                "reasons": reasons,
            },
        )

    async def _match_one(
        self, food: IdentifiedFood, correlation_id: str | None = None
    ) -> tuple[MatchedFood, bool]:
        """Return (item, repo_failed)."""
        repo_failed = False
        candidates: list[dict] = []
        try:
            candidates = await self._repo.search(normalize(food.name))
        except Exception as e:
            repo_failed = True
            logger.warning(
                "matcher_repo_error",
                exc_info=True,
                extra={
                    "correlation_id": correlation_id,
                    "stage": "supabase",
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "food_name": food.name,
                },
            )
        return await self._resolve(food, candidates, correlation_id), repo_failed

    async def _resolve(
        self, food: IdentifiedFood, candidates: list[dict], correlation_id: str | None
    ) -> MatchedFood:
        norm = normalize(food.name)

        if candidates:
            names = [c["name"] for c in candidates]
            result = process.extractOne(
                norm,
                names,
                scorer=fuzz.token_sort_ratio,
            )
            if result is not None:
                best_name, score, idx = result
                if score >= FUZZY_MATCH_THRESHOLD:
                    row = candidates[idx]
                    macros = MacrosPer100g(
                        calories=float(row.get("calories_per_100g") or 0.0),
                        protein=float(row.get("protein_per_100g") or 0.0),
                        carbs=float(row.get("carbs_per_100g") or 0.0),
                        fat=float(row.get("fat_per_100g") or 0.0),
                    )
                    return MatchedFood(
                        query_name=food.name,
                        grams=food.estimated_grams,
                        source="supabase",
                        matched_name=best_name,
                        score=float(score),
                        macros_per_100g=macros,
                        macros_actual=_compute_actuals(macros, food.estimated_grams),
                        low_confidence=False,
                    )

        # OFF fallback — treat HTTP errors as a miss, not a fatal exception
        try:
            off_macros = await self._off.search(food.name)
        except Exception as e:
            off_macros = None
            logger.warning(
                "matcher_off_error",
                exc_info=True,
                extra={
                    "correlation_id": correlation_id,
                    "stage": "off",
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "food_name": food.name,
                },
            )
        if off_macros is not None:
            return MatchedFood(
                query_name=food.name,
                grams=food.estimated_grams,
                source="open_food_facts",
                matched_name=None,
                score=None,
                macros_per_100g=off_macros,
                macros_actual=_compute_actuals(off_macros, food.estimated_grams),
                low_confidence=False,
            )

        # LLM estimate fallback — use macros the model provided at identification time
        if food.estimated_macros_per_100g is not None:
            return MatchedFood(
                query_name=food.name,
                grams=food.estimated_grams,
                source="llm_estimate",
                matched_name=None,
                score=None,
                macros_per_100g=food.estimated_macros_per_100g,
                macros_actual=_compute_actuals(
                    food.estimated_macros_per_100g, food.estimated_grams
                ),
                low_confidence=True,
            )

        # Unmatched — no data from any source
        return MatchedFood(
            query_name=food.name,
            grams=food.estimated_grams,
            source="unmatched",
            matched_name=None,
            score=None,
            macros_per_100g=None,
            macros_actual=MacroTotals(),
            low_confidence=True,
        )
