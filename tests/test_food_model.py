import pytest
from pydantic import ValidationError

from src.domain.food import IdentifiedFood, IdentifiedFoods


def test_valid_identified_food() -> None:
    food = IdentifiedFood(name="Banana", estimated_grams=120.0, confidence=0.95)
    assert food.name == "Banana"
    assert food.estimated_grams == 120.0
    assert food.confidence == 0.95


def test_confidence_above_one_rejected() -> None:
    with pytest.raises(ValidationError):
        IdentifiedFood(name="X", estimated_grams=50.0, confidence=1.1)


def test_confidence_below_zero_rejected() -> None:
    with pytest.raises(ValidationError):
        IdentifiedFood(name="X", estimated_grams=50.0, confidence=-0.1)


def test_estimated_grams_zero_rejected() -> None:
    with pytest.raises(ValidationError):
        IdentifiedFood(name="X", estimated_grams=0.0, confidence=0.5)


def test_estimated_grams_negative_rejected() -> None:
    with pytest.raises(ValidationError):
        IdentifiedFood(name="X", estimated_grams=-10.0, confidence=0.5)


def test_empty_items_list_is_valid() -> None:
    foods = IdentifiedFoods(items=[])
    assert foods.items == []


def test_identified_foods_default_empty() -> None:
    foods = IdentifiedFoods()
    assert foods.items == []
