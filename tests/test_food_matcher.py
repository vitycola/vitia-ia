"""Unit tests for FoodMatcherService."""

import inspect
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.food import IdentifiedFood, IdentifiedFoods, MacrosPer100g, MacroTotals
from src.services.food_matcher import FoodMatcherService, normalize

# ---------------------------------------------------------------------------
# normalize() helper
# ---------------------------------------------------------------------------


def test_normalize_lowercases() -> None:
    assert normalize("Banana") == "banana"


def test_normalize_strips_accents() -> None:
    assert normalize("Açaí") == "acai"


def test_normalize_combined() -> None:
    assert normalize("Pollo Asado") == "pollo asado"


# ---------------------------------------------------------------------------
# FUZZY_MATCH_THRESHOLD constant — must be referenced, not inlined
# ---------------------------------------------------------------------------


def test_threshold_constant_referenced_not_inlined() -> None:
    import src.services.food_matcher as mod

    source = inspect.getsource(mod)
    # The constant must appear as a reference in comparisons, not as bare "70"
    assert "FUZZY_MATCH_THRESHOLD" in source
    # Ensure 70 only appears in the constant definition line, not scattered
    lines_with_70 = [
        ln for ln in source.splitlines() if "70" in ln and "FUZZY_MATCH_THRESHOLD" not in ln
    ]
    assert lines_with_70 == [], f"Bare 70 found outside constant definition: {lines_with_70}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_food(name: str = "chicken", grams: float = 100.0) -> IdentifiedFood:
    return IdentifiedFood(name=name, estimated_grams=grams, confidence=0.9)


def _foods(*names_grams: tuple[str, float]) -> IdentifiedFoods:
    return IdentifiedFoods(
        items=[IdentifiedFood(name=n, estimated_grams=g, confidence=0.9) for n, g in names_grams]
    )


def _make_service(candidates: list[dict], off_result: MacrosPer100g | None) -> FoodMatcherService:
    repo = MagicMock()
    repo.search = AsyncMock(return_value=candidates)
    off_client = MagicMock()
    off_client.search = AsyncMock(return_value=off_result)
    return FoodMatcherService(repo=repo, off_client=off_client)


# ---------------------------------------------------------------------------
# Supabase hit above threshold
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_supabase_hit_above_threshold() -> None:
    candidates = [
        {
            "name": "chicken breast",
            "calories_per_100g": 165.0,
            "protein_per_100g": 31.0,
            "carbs_per_100g": 0.0,
            "fat_per_100g": 3.6,
        }
    ]
    service = _make_service(candidates, off_result=None)
    result = await service.match_all(_foods(("chicken breast", 200.0)))

    assert result.degraded is False
    assert len(result.items) == 1
    item = result.items[0]
    assert item.source == "supabase"
    assert item.low_confidence is False
    assert item.macros_actual.calories == pytest.approx(330.0)
    assert item.macros_actual.protein == pytest.approx(62.0)


# ---------------------------------------------------------------------------
# Supabase miss (score < 70), OFF hit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_supabase_miss_off_hit() -> None:
    # Return a candidate that won't fuzzy-match well
    candidates = [
        {
            "name": "zzzunrelated",
            "calories_per_100g": 50.0,
            "protein_per_100g": 1.0,
            "carbs_per_100g": 10.0,
            "fat_per_100g": 0.5,
        }
    ]
    off_macros = MacrosPer100g(calories=250.0, protein=10.0, carbs=30.0, fat=8.0)
    service = _make_service(candidates, off_result=off_macros)
    result = await service.match_all(_foods(("quinoa", 100.0)))

    assert result.degraded is False
    item = result.items[0]
    assert item.source == "open_food_facts"
    assert item.low_confidence is False
    assert item.macros_actual.calories == pytest.approx(250.0)


# ---------------------------------------------------------------------------
# Both miss → unmatched
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_both_miss_unmatched() -> None:
    service = _make_service([], off_result=None)
    result = await service.match_all(_foods(("mystery food xyz", 100.0)))

    item = result.items[0]
    assert item.source == "unmatched"
    assert item.low_confidence is True
    assert item.macros_per_100g is None
    assert item.macros_actual == MacroTotals()


# ---------------------------------------------------------------------------
# Degraded mode on infra error
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_degraded_on_infra_error() -> None:
    """Infra error on one item: becomes unmatched; degraded=True; other items unaffected."""
    repo = MagicMock()
    repo.search = AsyncMock(side_effect=Exception("network error"))
    off_client = MagicMock()
    off_client.search = AsyncMock(return_value=None)
    service = FoodMatcherService(repo=repo, off_client=off_client)

    result = await service.match_all(_foods(("apple", 80.0)))

    assert result.degraded is True
    assert len(result.items) == 1
    assert result.items[0].source == "unmatched"
    assert result.items[0].query_name == "apple"
    assert result.totals == MacroTotals()


# ---------------------------------------------------------------------------
# Totals aggregation includes unmatched (zeroed)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_totals_include_unmatched_items() -> None:
    """One matched item + one unmatched: totals reflect only matched actuals."""
    supabase_row = {
        "name": "banana",
        "calories_per_100g": 89.0,
        "protein_per_100g": 1.1,
        "carbs_per_100g": 23.0,
        "fat_per_100g": 0.3,
    }

    call_count = 0

    async def search_side_effect(name: str) -> list[dict]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return [supabase_row]
        return []

    repo = MagicMock()
    repo.search = AsyncMock(side_effect=search_side_effect)
    off_client = MagicMock()
    off_client.search = AsyncMock(return_value=None)
    service = FoodMatcherService(repo=repo, off_client=off_client)

    result = await service.match_all(_foods(("banana", 100.0), ("mystery xyz", 100.0)))

    assert len(result.items) == 2
    assert result.items[0].source == "supabase"
    assert result.items[1].source == "unmatched"
    # totals = banana actuals + zeros
    assert result.totals.calories == pytest.approx(89.0)


# ---------------------------------------------------------------------------
# OFF energy field resolution (unit-level via _extract_macros)
# ---------------------------------------------------------------------------


def test_off_kcal_field_used_directly() -> None:
    from src.adapters.off_client import OFFFallbackClient

    product = {
        "energy-kcal_100g": 250,
        "proteins_100g": 5.0,
        "carbohydrates_100g": 30.0,
        "fat_100g": 8.0,
    }
    result = OFFFallbackClient._extract_macros(product)
    assert result is not None
    assert result.calories == pytest.approx(250.0)


def test_off_kj_fallback() -> None:
    from src.adapters.off_client import OFFFallbackClient

    product = {
        "energy_100g": 1046.0,
        "proteins_100g": 5.0,
        "carbohydrates_100g": 30.0,
        "fat_100g": 8.0,
    }
    result = OFFFallbackClient._extract_macros(product)
    assert result is not None
    assert result.calories == pytest.approx(1046.0 / 4.184, rel=1e-3)


def test_off_neither_energy_field_zero() -> None:
    from src.adapters.off_client import OFFFallbackClient

    product = {
        "proteins_100g": 5.0,
        "carbohydrates_100g": 30.0,
        "fat_100g": 8.0,
    }
    result = OFFFallbackClient._extract_macros(product)
    assert result is not None
    assert result.calories == pytest.approx(0.0)
