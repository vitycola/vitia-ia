"""Advisory review flags for matched foods. Pure, I/O-free and never raises."""

from src.domain.food import IdentifiedFood, MatchedFood

MACRO_DIVERGENCE = "macro_divergence"
PORTION_HIGH = "portion_high"

DIVERGENCE_RATIO = 0.5
MIN_KCAL_DIFF = 50.0
MIN_PROTEIN_DIFF = 10.0

# Whole-word keyword -> maximum plausible portion in grams.
PORTION_MAX_GRAMS: dict[str, float] = {
    "pan": 150.0,
    "bread": 150.0,
    "arroz": 400.0,
    "rice": 400.0,
    "aceite": 30.0,
    "oil": 30.0,
    "queso": 150.0,
    "cheese": 150.0,
    "pasta": 400.0,
}

_NO_DIVERGENCE_SOURCES = ("llm_estimate", "unmatched")


def _diverges(matched: float, per_100g_estimate: float, grams: float, min_diff: float) -> bool:
    estimate = per_100g_estimate * grams / 100.0
    if estimate <= 0:
        return False
    diff = abs(matched - estimate)
    return diff / estimate > DIVERGENCE_RATIO and diff >= min_diff


def _normalize(name: str) -> str:
    # Local import avoids a circular dependency with the matcher module.
    from src.services.food_matcher import normalize

    return normalize(name)


def _has_macro_divergence(item: MatchedFood, food: IdentifiedFood) -> bool:
    estimate = food.estimated_macros_per_100g
    if estimate is None or item.source in _NO_DIVERGENCE_SOURCES:
        return False
    grams = item.grams
    if not grams or grams <= 0:
        return False
    actual = item.macros_actual
    return _diverges(actual.calories, estimate.calories, grams, MIN_KCAL_DIFF) or _diverges(
        actual.protein, estimate.protein, grams, MIN_PROTEIN_DIFF
    )


def _has_high_portion(item: MatchedFood) -> bool:
    grams = item.grams
    if not grams or grams <= 0:
        return False
    for token in _normalize(item.query_name or "").split():
        limit = PORTION_MAX_GRAMS.get(token)
        if limit is not None and grams > limit:
            return True
    return False


def review_reasons(item: MatchedFood, food: IdentifiedFood) -> list[str]:
    """Return advisory review reasons for a matched item. Never raises."""
    reasons: list[str] = []
    try:
        if _has_macro_divergence(item, food):
            reasons.append(MACRO_DIVERGENCE)
        if _has_high_portion(item):
            reasons.append(PORTION_HIGH)
    except Exception:
        return reasons
    return reasons
