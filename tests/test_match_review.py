"""Unit tests for match_review.review_reasons (R8-R10)."""

from src.domain.food import IdentifiedFood, MacrosPer100g, MacroTotals, MatchedFood
from src.services.match_review import MACRO_DIVERGENCE, PORTION_HIGH, review_reasons


def _item(
    name: str = "chicken",
    grams: float = 100.0,
    kcal: float = 0.0,
    protein: float = 0.0,
    source: str = "supabase",
) -> MatchedFood:
    return MatchedFood(
        query_name=name,
        grams=grams,
        source=source,  # type: ignore[arg-type]
        macros_actual=MacroTotals(calories=kcal, protein=protein),
    )


def _food(
    name: str = "chicken",
    grams: float = 100.0,
    kcal: float | None = None,
    protein: float = 0.0,
) -> IdentifiedFood:
    est = None if kcal is None else MacrosPer100g(calories=kcal, protein=protein, carbs=0, fat=0)
    return IdentifiedFood(
        name=name, estimated_grams=grams, confidence=0.9, estimated_macros_per_100g=est
    )


def test_kcal_divergence_flagged() -> None:
    assert review_reasons(_item(kcal=400), _food(kcal=200)) == [MACRO_DIVERGENCE]


def test_below_absolute_floor_not_flagged() -> None:
    assert review_reasons(_item(kcal=60), _food(kcal=30)) == []


def test_ratio_below_threshold_not_flagged() -> None:
    assert review_reasons(_item(kcal=140), _food(kcal=100)) == []


def test_ratio_exactly_half_not_flagged() -> None:
    assert review_reasons(_item(kcal=150), _food(kcal=100)) == []


def test_protein_divergence_flagged() -> None:
    assert review_reasons(_item(protein=30), _food(kcal=0, protein=10)) == [MACRO_DIVERGENCE]


def test_protein_below_floor_not_flagged() -> None:
    assert review_reasons(_item(protein=8), _food(kcal=0, protein=4)) == []


def test_missing_estimate_skipped() -> None:
    assert review_reasons(_item(kcal=400), _food(kcal=None)) == []


def test_all_zero_estimate_skipped() -> None:
    assert review_reasons(_item(kcal=400, protein=30), _food(kcal=0, protein=0)) == []


def test_single_metric_zero_estimate_no_zero_division() -> None:
    assert review_reasons(_item(kcal=400, protein=0), _food(kcal=200, protein=0)) == [
        MACRO_DIVERGENCE
    ]
    assert review_reasons(_item(kcal=100, protein=50), _food(kcal=100, protein=0)) == []


def test_llm_estimate_and_unmatched_skipped() -> None:
    for source in ("llm_estimate", "unmatched"):
        assert review_reasons(_item(kcal=400, source=source), _food(kcal=200)) == []


def test_pan_300g_flagged() -> None:
    assert review_reasons(_item("pan", 300), _food("pan", 300)) == [PORTION_HIGH]


def test_panceta_not_flagged_whole_word() -> None:
    assert review_reasons(_item("panceta", 300), _food("panceta", 300)) == []


def test_bread_at_max_not_flagged() -> None:
    assert review_reasons(_item("bread", 150), _food("bread", 150)) == []


def test_aceite_de_oliva_45g_flagged() -> None:
    assert review_reasons(_item("aceite de oliva", 45), _food("aceite de oliva", 45)) == [
        PORTION_HIGH
    ]


def test_manzana_not_flagged() -> None:
    assert review_reasons(_item("manzana", 500), _food("manzana", 500)) == []


def test_zero_grams_not_flagged() -> None:
    assert review_reasons(_item("pan", 0), _food("pan")) == []


def test_portion_applies_to_llm_estimate_source() -> None:
    assert review_reasons(_item("pan", 300, source="llm_estimate"), _food("pan", 300)) == [
        PORTION_HIGH
    ]


def test_both_reasons_coexist_without_duplicates() -> None:
    reasons = review_reasons(_item("bread", 300, kcal=400), _food("bread", 300, kcal=50))
    assert reasons == [MACRO_DIVERGENCE, PORTION_HIGH]
