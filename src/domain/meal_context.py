import re
import unicodedata

MEAL_CONTEXT_MAX_LEN = 150

_WHITESPACE_CONTROLS = re.compile(r"[\r\n\t\x0b\x0c]+")


def normalize_meal_context(raw: str | None) -> str | None:
    """Clean the optional written meal note; return None when nothing usable remains."""
    if raw is None:
        return None
    text = _WHITESPACE_CONTROLS.sub(" ", raw)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Cc").strip()
    if not text:
        return None
    text = text[:MEAL_CONTEXT_MAX_LEN].rstrip()
    return text or None
