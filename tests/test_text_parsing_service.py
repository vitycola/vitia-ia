"""Tests for TextParsingService."""

from unittest.mock import AsyncMock

import pytest

from src.domain.food import (
    IdentifiedFood,
    IdentifiedFoods,
    MacrosPer100g,
    MacroTotals,
    MatchedFood,
    MatchResult,
)
from src.services.errors import LLMError, LLMTimeoutError
from src.services.text_parsing import TextParsingService


def _matched_food(
    query_name: str,
    source: str = "supabase",
    calories: float = 100.0,
) -> MatchedFood:
    return MatchedFood(
        query_name=query_name,
        grams=100.0,
        source=source,  # type: ignore[arg-type]
        matched_name=query_name if source != "unmatched" else None,
        macros_per_100g=MacrosPer100g(calories=calories, protein=5.0, carbs=10.0, fat=2.0)
        if source != "unmatched"
        else None,
        macros_actual=MacroTotals(calories=calories, protein=5.0, carbs=10.0, fat=2.0)
        if source != "unmatched"
        else MacroTotals(),
    )


def _make_service(
    llm_result: IdentifiedFoods | None = None,
    matcher_result: MatchResult | None = None,
    llm_side_effect=None,
) -> TextParsingService:
    llm = AsyncMock()
    if llm_side_effect is not None:
        llm.parse_text = AsyncMock(side_effect=llm_side_effect)
    else:
        foods = llm_result if llm_result is not None else IdentifiedFoods(items=[])
        llm.parse_text = AsyncMock(return_value=foods)

    matcher = AsyncMock()
    result = (
        matcher_result
        if matcher_result is not None
        else MatchResult(items=[], totals=MacroTotals(), degraded=False)
    )
    matcher.match_all = AsyncMock(return_value=result)

    return TextParsingService(llm=llm, matcher=matcher)


@pytest.mark.asyncio
async def test_parse_simple_match_returns_items():
    food_item = _matched_food("pollo", source="supabase", calories=200.0)
    llm_result = IdentifiedFoods(
        items=[IdentifiedFood(name="pollo", estimated_grams=100.0, confidence=0.9)]
    )
    matcher_result = MatchResult(
        items=[food_item],
        totals=MacroTotals(calories=200.0, protein=5.0, carbs=10.0, fat=2.0),
        degraded=False,
    )
    service = _make_service(llm_result=llm_result, matcher_result=matcher_result)

    result = await service.parse("pollo a la plancha", "corr-1")

    assert len(result.items) == 1
    assert result.items[0].query_name == "pollo"
    assert result.skipped == []
    assert result.totals.calories == 200.0


@pytest.mark.asyncio
async def test_parse_compound_multiple_matched_items():
    foods = [
        _matched_food("arroz", source="supabase", calories=150.0),
        _matched_food("pollo", source="supabase", calories=200.0),
    ]
    llm_result = IdentifiedFoods(
        items=[
            IdentifiedFood(name="arroz", estimated_grams=100.0, confidence=0.9),
            IdentifiedFood(name="pollo", estimated_grams=100.0, confidence=0.9),
        ]
    )
    matcher_result = MatchResult(
        items=foods,
        totals=MacroTotals(calories=350.0, protein=10.0, carbs=20.0, fat=4.0),
        degraded=False,
    )
    service = _make_service(llm_result=llm_result, matcher_result=matcher_result)

    result = await service.parse("arroz con pollo", "corr-2")

    assert len(result.items) == 2
    assert result.skipped == []
    assert result.totals.calories == 350.0


@pytest.mark.asyncio
async def test_parse_colloquial_quantity_resolved_by_llm():
    food_item = _matched_food("yogur", source="supabase", calories=80.0)
    llm_result = IdentifiedFoods(
        items=[IdentifiedFood(name="yogur", estimated_grams=125.0, confidence=0.85)]
    )
    matcher_result = MatchResult(
        items=[food_item],
        totals=MacroTotals(calories=80.0, protein=5.0, carbs=8.0, fat=2.0),
        degraded=False,
    )
    service = _make_service(llm_result=llm_result, matcher_result=matcher_result)

    result = await service.parse("un yogur de postre", "corr-3")

    assert len(result.items) == 1
    assert result.skipped == []
    llm_call_args = service.llm.parse_text.call_args
    assert llm_call_args.args[0] == "un yogur de postre"


@pytest.mark.asyncio
async def test_parse_partial_match_populates_skipped():
    matched = _matched_food("pollo", source="supabase", calories=200.0)
    unmatched = _matched_food("unicornio", source="unmatched")
    llm_result = IdentifiedFoods(
        items=[
            IdentifiedFood(name="pollo", estimated_grams=100.0, confidence=0.9),
            IdentifiedFood(name="unicornio", estimated_grams=50.0, confidence=0.5),
        ]
    )
    matcher_result = MatchResult(
        items=[matched, unmatched],
        totals=MacroTotals(calories=200.0, protein=5.0, carbs=10.0, fat=2.0),
        degraded=False,
    )
    service = _make_service(llm_result=llm_result, matcher_result=matcher_result)

    result = await service.parse("pollo y unicornio a la plancha", "corr-4")

    assert len(result.items) == 1
    assert result.items[0].query_name == "pollo"
    assert result.skipped == ["unicornio"]
    assert result.totals.calories == 200.0


@pytest.mark.asyncio
async def test_parse_all_unmatched_empty_items_populated_skipped():
    u1 = _matched_food("xyzfood", source="unmatched")
    u2 = _matched_food("blargh", source="unmatched")
    llm_result = IdentifiedFoods(
        items=[
            IdentifiedFood(name="xyzfood", estimated_grams=30.0, confidence=0.3),
            IdentifiedFood(name="blargh", estimated_grams=30.0, confidence=0.3),
        ]
    )
    matcher_result = MatchResult(
        items=[u1, u2],
        totals=MacroTotals(),
        degraded=False,
    )
    service = _make_service(llm_result=llm_result, matcher_result=matcher_result)

    result = await service.parse("xyzfood and blargh", "corr-5")

    assert result.items == []
    assert set(result.skipped) == {"xyzfood", "blargh"}
    assert result.totals.calories == 0.0


@pytest.mark.asyncio
async def test_parse_empty_llm_result_returns_degraded():
    service = _make_service(
        llm_result=IdentifiedFoods(items=[]),
        matcher_result=MatchResult(items=[], totals=MacroTotals(), degraded=False),
    )

    result = await service.parse("nothing here", "corr-6")

    assert result.degraded is True
    assert result.items == []
    assert result.skipped == []


@pytest.mark.asyncio
async def test_parse_degraded_propagates_from_matcher():
    food_item = _matched_food("arroz", source="supabase", calories=150.0)
    llm_result = IdentifiedFoods(
        items=[IdentifiedFood(name="arroz", estimated_grams=100.0, confidence=0.9)]
    )
    matcher_result = MatchResult(
        items=[food_item],
        totals=MacroTotals(calories=150.0, protein=3.0, carbs=30.0, fat=1.0),
        degraded=True,
    )
    service = _make_service(llm_result=llm_result, matcher_result=matcher_result)

    result = await service.parse("arroz", "corr-7")

    assert result.degraded is True


@pytest.mark.asyncio
async def test_parse_llm_timeout_raises():
    service = _make_service(llm_side_effect=TimeoutError())

    with pytest.raises(LLMTimeoutError):
        await service.parse("some food", "corr-8")


@pytest.mark.asyncio
async def test_parse_llm_error_raises():
    service = _make_service(llm_side_effect=RuntimeError("network error"))

    with pytest.raises(LLMError):
        await service.parse("some food", "corr-9")
