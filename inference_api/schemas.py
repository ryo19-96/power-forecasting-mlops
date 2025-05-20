from typing import List

from pydantic import BaseModel, Field


class PredictRequest(BaseModel):
    date: str = Field(example="2023-01-01")
    max_temp: float = Field(example=28.0)
    min_temp: float = Field(example=10.5)
    weather: str = Field(example="曇り")


# {'predictions': [3722.7302187905166]}で返ってくる
class PredictResponse(BaseModel):
    predictions: List[float]
