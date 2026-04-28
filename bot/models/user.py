"""Модель пользователя."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class User(BaseModel):
    id: Optional[int] = None
    telegram_id: int
    name: str
    age: int = Field(ge=10, le=100)
    weight: float = Field(ge=30.0, le=300.0, description="Вес в кг")
    height: float = Field(ge=100.0, le=250.0, description="Рост в см")
    goal: str
    gym_lat: Optional[float] = None
    gym_lon: Optional[float] = None
    gym_name: Optional[str] = None
    created_at: Optional[datetime] = None

    @property
    def bmi(self) -> float:
        """Индекс массы тела."""
        h_m = self.height / 100
        return round(self.weight / (h_m ** 2), 1)
