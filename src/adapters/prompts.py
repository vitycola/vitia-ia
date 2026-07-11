VISION_PROMPT = (
    "Identify every food item visible in this image. "
    "For each item, call the record_identified_foods tool with the following fields: "
    "name (string — the food name), "
    "estimated_grams (float greater than 0 — the estimated portion weight in grams), "
    "confidence (float between 0.0 and 1.0 — how confident you are in the identification). "
    "If no food items are present, call the tool with an empty items list."
)

TEXT_PROMPT = (
    "Identify every food item described in the text below. "
    "For each item, call the record_identified_foods tool with the following fields: "
    "name (string — the food name), "
    "estimated_grams (float greater than 0 — the estimated portion weight in grams), "
    "confidence (float between 0.0 and 1.0 — how confident you are in the identification). "
    "If no food items are described, call the tool with an empty items list."
)
