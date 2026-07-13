import asyncio
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

    async def match_all(self, foods: IdentifiedFoods) -> MatchResult:
        try:
            results = await asyncio.gather(
                *[self._match_one(food) for food in foods.items],
                return_exceptions=True,
            )
            # If any coroutine raised, treat the whole batch as degraded.
            for result in results:
                if isinstance(result, BaseException):
                    raise result
            items: list[MatchedFood] = list(results)  # type: ignore[arg-type]
        except Exception:
            return MatchResult(
                items=[],
                totals=MacroTotals(),
                degraded=True,
            )

        return MatchResult(items=items, totals=_sum_totals(items), degraded=False)

    async def _match_one(self, food: IdentifiedFood) -> MatchedFood:
        norm = normalize(food.name)
        candidates = await self._repo.search(norm)

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

        # OFF fallback
        off_macros = await self._off.search(food.name)
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

        # Unmatched
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
