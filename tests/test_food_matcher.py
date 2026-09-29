"""Unit tests for FoodMatcherService."""

import inspect
from unittest.mock import AsyncMock, MagicMock, patch

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


def _failing_repo_service(
    off_result: MacrosPer100g | None = None, off_error: Exception | None = None
) -> FoodMatcherService:
    repo = MagicMock()
    repo.search = AsyncMock(side_effect=Exception("network error"))
    off_client = MagicMock()
    if off_error is not None:
        off_client.search = AsyncMock(side_effect=off_error)
    else:
        off_client.search = AsyncMock(return_value=off_result)
    return FoodMatcherService(repo=repo, off_client=off_client)


@pytest.mark.asyncio
async def test_degraded_on_infra_error() -> None:
    """Repo raises + OFF hit: item rescued by OFF, but result is degraded (repo_error)."""
    off_macros = MacrosPer100g(calories=52.0, protein=0.3, carbs=14.0, fat=0.2)
    service = _failing_repo_service(off_result=off_macros)

    result = await service.match_all(_foods(("apple", 80.0)))

    assert result.degraded is True
    assert result.degraded_reason == "repo_error"
    assert result.items[0].source == "open_food_facts"
    assert result.skipped == []


@pytest.mark.asyncio
async def test_repo_error_falls_back_to_llm_estimate() -> None:
    service = _failing_repo_service()
    foods = IdentifiedFoods(
        items=[
            IdentifiedFood(
                name="apple",
                estimated_grams=100.0,
                confidence=0.9,
                estimated_macros_per_100g=MacrosPer100g(
                    calories=52.0, protein=0.3, carbs=14.0, fat=0.2
                ),
            )
        ]
    )
    result = await service.match_all(foods)

    assert result.items[0].source == "llm_estimate"
    assert result.degraded is True
    assert result.degraded_reason == "repo_error"


@pytest.mark.asyncio
async def test_repo_error_all_miss_is_unmatched_and_skipped() -> None:
    service = _failing_repo_service()

    result = await service.match_all(_foods(("apple", 80.0)))

    assert result.degraded is True
    assert result.items[0].source == "unmatched"
    assert result.items[0].query_name == "apple"
    assert result.totals == MacroTotals()
    assert result.skipped == ["apple"]


@pytest.mark.asyncio
async def test_repo_error_is_logged_with_correlation_id_and_food_name() -> None:
    service = _failing_repo_service()

    with patch("src.services.food_matcher.logger") as mock_logger:
        await service.match_all(_foods(("apple", 80.0)), correlation_id="abc")

    mock_logger.warning.assert_called_once()
    args, kwargs = mock_logger.warning.call_args
    assert args[0] == "matcher_repo_error"
    assert kwargs["extra"]["correlation_id"] == "abc"
    assert kwargs["extra"]["food_name"] == "apple"
    assert kwargs["exc_info"] is True


@pytest.mark.asyncio
async def test_repo_error_logged_without_correlation_id() -> None:
    service = _failing_repo_service()

    with patch("src.services.food_matcher.logger") as mock_logger:
        result = await service.match_all(_foods(("apple", 80.0)))

    mock_logger.warning.assert_called_once()
    assert mock_logger.warning.call_args.kwargs["extra"]["correlation_id"] is None
    assert result.degraded is True


@pytest.mark.asyncio
async def test_off_error_logged_flow_continues_not_degraded() -> None:
    repo = MagicMock()
    repo.search = AsyncMock(return_value=[])
    off_client = MagicMock()
    off_client.search = AsyncMock(side_effect=RuntimeError("off down"))
    service = FoodMatcherService(repo=repo, off_client=off_client)
    foods = IdentifiedFoods(
        items=[
            IdentifiedFood(
                name="apple",
                estimated_grams=100.0,
                confidence=0.9,
                estimated_macros_per_100g=MacrosPer100g(
                    calories=52.0, protein=0.3, carbs=14.0, fat=0.2
                ),
            )
        ]
    )

    with patch("src.services.food_matcher.logger") as mock_logger:
        result = await service.match_all(foods, correlation_id="cid-1")

    mock_logger.warning.assert_called_once()
    args, kwargs = mock_logger.warning.call_args
    assert args[0] == "matcher_off_error"
    assert kwargs["extra"]["correlation_id"] == "cid-1"
    assert kwargs["extra"]["food_name"] == "apple"
    assert result.items[0].source == "llm_estimate"
    assert result.degraded is False
    assert result.degraded_reason is None


@pytest.mark.asyncio
async def test_unexpected_item_error_is_match_error_and_repo_error_wins() -> None:
    service = _make_service([], off_result=None)
    original = service._match_one

    async def flaky(food, correlation_id=None):  # type: ignore[no-untyped-def]
        if food.name == "boom":
            raise ValueError("unexpected")
        return await original(food, correlation_id)

    service._match_one = flaky  # type: ignore[method-assign]

    with patch("src.services.food_matcher.logger") as mock_logger:
        result = await service.match_all(_foods(("boom", 50.0), ("ok", 50.0)))

    mock_logger.error.assert_called_once()
    assert mock_logger.error.call_args.args[0] == "matcher_item_error"
    assert result.degraded is True
    assert result.degraded_reason == "match_error"
    assert result.skipped == ["boom", "ok"]

    # repo_error takes precedence over match_error
    repo_failing = _failing_repo_service()
    orig2 = repo_failing._match_one

    async def flaky2(food, correlation_id=None):  # type: ignore[no-untyped-def]
        if food.name == "boom":
            raise ValueError("unexpected")
        return await orig2(food, correlation_id)

    repo_failing._match_one = flaky2  # type: ignore[method-assign]
    result2 = await repo_failing.match_all(_foods(("boom", 50.0), ("ok", 50.0)))
    assert result2.degraded_reason == "repo_error"


@pytest.mark.asyncio
async def test_no_errors_not_degraded_and_skipped_populated() -> None:
    service = _make_service([], off_result=None)

    result = await service.match_all(_foods(("mystery", 50.0)))

    assert result.degraded is False
    assert result.degraded_reason is None
    assert result.skipped == ["mystery"]


@pytest.mark.asyncio
async def test_high_portion_sets_review_flag() -> None:
    off_macros = MacrosPer100g(calories=250.0, protein=8.0, carbs=50.0, fat=3.0)
    service = _make_service([], off_result=off_macros)

    result = await service.match_all(_foods(("bread", 300.0)))

    item = result.items[0]
    assert item.review is True
    assert item.review_reasons == ["portion_high"]
    assert item.macros_actual.calories == pytest.approx(750.0)


@pytest.mark.asyncio
async def test_review_failure_does_not_drop_item() -> None:
    off_macros = MacrosPer100g(calories=250.0, protein=8.0, carbs=50.0, fat=3.0)
    service = _make_service([], off_result=off_macros)

    with patch("src.services.food_matcher.review_reasons", side_effect=RuntimeError("boom")):
        result = await service.match_all(_foods(("bread", 300.0)))

    assert len(result.items) == 1
    assert result.items[0].review is False
    assert result.items[0].macros_actual.calories == pytest.approx(750.0)


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
