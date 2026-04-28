"""Модель записи питания."""
from datetime import date
from typing import Optional
from pydantic import BaseModel, Field


class NutritionLog(BaseModel):
    id: Optional[int] = None
    user_id: int
    date: date
    calories: int = Field(ge=0)
    protein_g: float = Field(ge=0.0, description="Белки в граммах")
    fat_g: float = Field(ge=0.0, description="Жиры в граммах")
    carbs_g: float = Field(ge=0.0, description="Углеводы в граммах")
    meal_description: Optional[str] = None

    def summary(self) -> str:
        """Краткая сводка для вывода в боте."""
        return (
            f"🔥 {self.calories} ккал | "
            f"💪 Б: {self.protein_g:.0f}г | "
            f"🫒 Ж: {self.fat_g:.0f}г | "
            f"🌾 У: {self.carbs_g:.0f}г"
        )
