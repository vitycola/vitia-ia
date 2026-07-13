from typing import Literal

from pydantic import BaseModel, Field


class IdentifiedFood(BaseModel):
    name: str = Field(min_length=1)
    estimated_grams: float = Field(gt=0)
    confidence: float = Field(ge=0.0, le=1.0)


class IdentifiedFoods(BaseModel):
    items: list[IdentifiedFood] = Field(default_factory=list)


class MacrosPer100g(BaseModel):
    calories: float = Field(ge=0.0)
    protein: float = Field(ge=0.0)
    carbs: float = Field(ge=0.0)
    fat: float = Field(ge=0.0)


class MacroTotals(BaseModel):
    calories: float = Field(default=0.0, ge=0.0)
    protein: float = Field(default=0.0, ge=0.0)
    carbs: float = Field(default=0.0, ge=0.0)
    fat: float = Field(default=0.0, ge=0.0)


class MatchedFood(BaseModel):
    query_name: str
    grams: float
    source: Literal["supabase", "open_food_facts", "unmatched"]
    matched_name: str | None = None
    score: float | None = None
    macros_per_100g: MacrosPer100g | None = None
    macros_actual: MacroTotals
    low_confidence: bool = False


class MatchResult(BaseModel):
    items: list[MatchedFood] = Field(default_factory=list)
    totals: MacroTotals
    degraded: bool = False
