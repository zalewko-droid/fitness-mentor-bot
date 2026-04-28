"""
Сервис тренировок:
  - generate_workout — генерация через Gemini → сохранение в БД
  - get_today_workout — получение тренировки на сегодня
  - mark_workout_done — отметка выполнения
  - log_exercise — логирование подхода
"""
import json
import logging
from datetime import date
from typing import Optional

from openai import AsyncOpenAI

from bot.config import settings
from bot.database import get_db
from bot.models.workout import Exercise, Workout, WorkoutLog
from bot.services.ai_service import build_context, save_memory

logger = logging.getLogger(__name__)
_openai = AsyncOpenAI(
    api_key=settings.GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
)


async def generate_workout(user_id: int) -> Optional[Workout]:
    """
    Генерирует тренировку для пользователя через GPT-4o.
    Сохраняет в таблицы workouts + exercises.
    Возвращает объект Workout или None при ошибке.
    """
    db = get_db()
    context = await build_context(user_id)
    today = date.today().isoformat()

    prompt = (
        f"Составь тренировку на сегодня ({today}) для пользователя.\n\n"
        f"{context}\n\n"
        "ВАЖНО: верни ТОЛЬКО валидный JSON без markdown-блоков:\n"
        "{\n"
        '  "name": "Название тренировки",\n'
        '  "exercises": [\n'
        "    {\n"
        '      "name": "Жим штанги лёжа",\n'
        '      "sets": 4,\n'
        '      "reps": 8,\n'
        '      "weight_kg": 80.0,\n'
        '      "muscle_group": "грудь",\n'
        '      "rest_seconds": 90,\n'
        '      "order_index": 1\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "Включи 5–7 упражнений. Делай акцент на слабых группах мышц из анализа тела."
    )

    try:
        response = await _openai.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "Ты опытный фитнес-тренер. Отвечай ТОЛЬКО JSON без markdown.",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=2000,
            temperature=0.5,
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content or "{}"
        data = json.loads(raw)

        # Сохраняем тренировку
        workout_resp = (
            db.table("workouts")
            .insert(
                {
                    "user_id": user_id,
                    "date": today,
                    "name": data.get("name", "Тренировка"),
                    "status": "planned",
                    "generated_by_ai": True,
                }
            )
            .execute()
        )

        if not workout_resp.data:
            logger.error("generate_workout: не удалось сохранить тренировку")
            return None

        workout_id = workout_resp.data[0]["id"]
        exercises: list[Exercise] = []

        for ex_data in data.get("exercises", []):
            ex_resp = (
                db.table("exercises")
                .insert(
                    {
                        "workout_id": workout_id,
                        "name": ex_data.get("name", "Упражнение"),
                        "sets": ex_data.get("sets", 3),
                        "reps": ex_data.get("reps", 10),
                        "weight_kg": float(ex_data.get("weight_kg", 0)),
                        "muscle_group": ex_data.get("muscle_group", ""),
                        "order_index": ex_data.get("order_index", 0),
                    }
                )
                .execute()
            )
            if ex_resp.data:
                exercises.append(Exercise(**ex_resp.data[0]))

        # Сохраняем в память AI
        await save_memory(
            user_id,
            "workout_generated",
            f"Тренировка '{data.get('name')}' на {today}, {len(exercises)} упражнений",
        )

        return Workout(
            id=workout_id,
            user_id=user_id,
            date=date.today(),
            name=data.get("name", "Тренировка"),
            status="planned",
            generated_by_ai=True,
            exercises=exercises,
        )

    except Exception as e:
        logger.error(f"generate_workout: ошибка: {e}")
        return None


async def get_today_workout(user_id: int) -> Optional[Workout]:
    """Возвращает тренировку на сегодня из БД или None."""
    db = get_db()
    today = date.today().isoformat()

    try:
        resp = (
            db.table("workouts")
            .select("*, exercises(*)")
            .eq("user_id", user_id)
            .eq("date", today)
            .maybe_single()
            .execute()
        )
        if not resp.data:
            return None

        w = resp.data
        exercises = [
            Exercise(**e)
            for e in sorted(w.get("exercises") or [], key=lambda x: x.get("order_index", 0))
        ]
        return Workout(
            id=w["id"],
            user_id=user_id,
            date=date.fromisoformat(w["date"]),
            name=w["name"],
            status=w["status"],
            generated_by_ai=w.get("generated_by_ai", True),
            exercises=exercises,
        )
    except Exception as e:
        logger.error(f"get_today_workout: ошибка: {e}")
        return None


async def get_workout_by_id(workout_id: int) -> Optional[Workout]:
    """Возвращает тренировку по ID с упражнениями."""
    db = get_db()
    try:
        resp = (
            db.table("workouts")
            .select("*, exercises(*)")
            .eq("id", workout_id)
            .maybe_single()
            .execute()
        )
        if not resp.data:
            return None
        w = resp.data
        exercises = [
            Exercise(**e)
            for e in sorted(w.get("exercises") or [], key=lambda x: x.get("order_index", 0))
        ]
        return Workout(
            id=w["id"],
            user_id=w["user_id"],
            date=date.fromisoformat(w["date"]),
            name=w["name"],
            status=w["status"],
            generated_by_ai=w.get("generated_by_ai", True),
            exercises=exercises,
        )
    except Exception as e:
        logger.error(f"get_workout_by_id: ошибка: {e}")
        return None


async def mark_workout_done(workout_id: int) -> bool:
    """Отмечает тренировку как выполненную."""
    db = get_db()
    try:
        db.table("workouts").update({"status": "done"}).eq("id", workout_id).execute()
        return True
    except Exception as e:
        logger.error(f"mark_workout_done: ошибка: {e}")
        return False


async def log_exercise(
    workout_id: int,
    exercise_id: int,
    actual_sets: int,
    actual_reps: int,
    actual_weight: float,
    notes: str = "",
) -> bool:
    """Логирует фактически выполненное упражнение."""
    db = get_db()
    try:
        db.table("workout_logs").insert(
            {
                "workout_id": workout_id,
                "exercise_id": exercise_id,
                "actual_sets": actual_sets,
                "actual_reps": actual_reps,
                "actual_weight": actual_weight,
                "notes": notes,
            }
        ).execute()
        return True
    except Exception as e:
        logger.error(f"log_exercise: ошибка: {e}")
        return False
