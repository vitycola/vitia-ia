import pytest
from pydantic import ValidationError

from src.domain.food import MacrosPer100g, MacroTotals, MatchedFood, MatchResult


def test_macros_per_100g_valid() -> None:
    m = MacrosPer100g(calories=100.0, protein=5.0, carbs=20.0, fat=3.0)
    assert m.calories == 100.0
    assert m.protein == 5.0
    assert m.carbs == 20.0
    assert m.fat == 3.0


def test_macro_totals_defaults_zero() -> None:
    t = MacroTotals()
    assert t.calories == 0.0
    assert t.protein == 0.0
    assert t.carbs == 0.0
    assert t.fat == 0.0


def test_macros_per_100g_rejects_negative_calories() -> None:
    with pytest.raises(ValidationError):
        MacrosPer100g(calories=-1.0, protein=0.0, carbs=0.0, fat=0.0)


def test_macros_per_100g_rejects_negative_protein() -> None:
    with pytest.raises(ValidationError):
        MacrosPer100g(calories=0.0, protein=-0.1, carbs=0.0, fat=0.0)


def test_macro_totals_rejects_negative() -> None:
    with pytest.raises(ValidationError):
        MacroTotals(calories=-5.0)


def test_matched_food_shape() -> None:
    mf = MatchedFood(
        query_name="chicken",
        grams=150.0,
        source="supabase",
        matched_name="Chicken breast",
        score=95.0,
        macros_per_100g=MacrosPer100g(calories=165.0, protein=31.0, carbs=0.0, fat=3.6),
        macros_actual=MacroTotals(calories=247.5, protein=46.5, carbs=0.0, fat=5.4),
        low_confidence=False,
    )
    assert mf.source == "supabase"
    assert mf.low_confidence is False


def test_match_result_shape() -> None:
    result = MatchResult(
        items=[],
        totals=MacroTotals(),
        degraded=False,
    )
    assert result.degraded is False
    assert result.items == []
