"""Модели тренировки и упражнения."""
from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class Exercise(BaseModel):
    id: Optional[int] = None
    workout_id: Optional[int] = None
    name: str
    sets: int = Field(ge=1, le=20)
    reps: int = Field(ge=1, le=100)
    weight_kg: float = Field(ge=0.0)
    muscle_group: str
    order_index: int = 0
    rest_seconds: int = 60


class Workout(BaseModel):
    id: Optional[int] = None
    user_id: int
    date: date
    name: str
    # Статусы: planned / done / skipped
    status: str = "planned"
    generated_by_ai: bool = True
    created_at: Optional[datetime] = None
    exercises: List[Exercise] = []

    def format_exercises(self) -> str:
        """Форматирует список упражнений для вывода в Telegram."""
        return "\n".join(
            f"{i + 1}. <b>{e.name}</b> — {e.sets}×{e.reps} @ {e.weight_kg} кг"
            f" <i>({e.muscle_group})</i>"
            for i, e in enumerate(self.exercises)
        )


class WorkoutLog(BaseModel):
    id: Optional[int] = None
    workout_id: int
    exercise_id: int
    actual_sets: int
    actual_reps: int
    actual_weight: float
    notes: str = ""
    logged_at: Optional[datetime] = None
