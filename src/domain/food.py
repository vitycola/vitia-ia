from pydantic import BaseModel, Field


class IdentifiedFood(BaseModel):
    name: str = Field(min_length=1)
    estimated_grams: float = Field(gt=0)
    confidence: float = Field(ge=0.0, le=1.0)


class IdentifiedFoods(BaseModel):
    items: list[IdentifiedFood] = Field(default_factory=list)
