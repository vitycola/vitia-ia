import re
import unicodedata

MEAL_CONTEXT_MAX_LEN = 150

_WHITESPACE_CONTROLS = re.compile(r"[\r\n\t\x0b\x0c\x85\u2028\u2029]+")
_DROPPED_CATEGORIES = frozenset({"Cc", "Cf"})


def normalize_meal_context(raw: str | None) -> str | None:
    """Clean the optional written meal note; return None when nothing usable remains."""
    if raw is None:
        return None
    text = _WHITESPACE_CONTROLS.sub(" ", raw)
    text = "".join(ch for ch in text if unicodedata.category(ch) not in _DROPPED_CATEGORIES).strip()
    if not text:
        return None
    return text[:MEAL_CONTEXT_MAX_LEN].rstrip()
