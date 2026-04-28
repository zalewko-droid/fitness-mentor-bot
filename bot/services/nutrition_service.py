"""
Сервис питания:
  - analyze_meal — Gemini анализирует текстовое описание еды → КБЖУ
  - get_today_nutrition — суммарное питание за сегодня
"""
import json
import logging
from datetime import date
from typing import Optional

from openai import AsyncOpenAI

from bot.config import settings
from bot.database import get_db
from bot.models.nutrition import NutritionLog

logger = logging.getLogger(__name__)
_openai = AsyncOpenAI(
    api_key=settings.GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
)


async def analyze_meal(user_id: int, meal_description: str) -> Optional[NutritionLog]:
    """
    Анализирует описание приёма пищи через GPT-4o.
    Суммирует калории с уже записанными за сегодня.
    """
    prompt = (
        "Рассчитай КБЖУ для описанной еды. Используй типичные размеры порций.\n"
        f"Еда: {meal_description}\n\n"
        "Верни ТОЛЬКО JSON:\n"
        '{"calories": 450, "protein_g": 35.0, "fat_g": 12.0, "carbs_g": 48.0}'
    )

    try:
        response = await _openai.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "Ты нутрициолог. Возвращай только JSON, без объяснений.",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=150,
            temperature=0.2,
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content or "{}"
        data = json.loads(raw)

        calories = int(data.get("calories", 0))
        protein = float(data.get("protein_g", 0))
        fat = float(data.get("fat_g", 0))
        carbs = float(data.get("carbs_g", 0))

        today = date.today().isoformat()
        db = get_db()

        # Проверяем существующую запись за сегодня
        existing = (
            db.table("nutrition_logs")
            .select("*")
            .eq("user_id", user_id)
            .eq("date", today)
            .maybe_single()
            .execute()
        )

        if existing.data:
            # Суммируем с существующей записью
            ex = existing.data
            updated = {
                "calories": ex["calories"] + calories,
                "protein_g": round(ex["protein_g"] + protein, 1),
                "fat_g": round(ex["fat_g"] + fat, 1),
                "carbs_g": round(ex["carbs_g"] + carbs, 1),
                "meal_description": (ex.get("meal_description") or "") + f"; {meal_description}",
            }
            db.table("nutrition_logs").update(updated).eq("id", ex["id"]).execute()
            return NutritionLog(
                id=ex["id"],
                user_id=user_id,
                date=date.today(),
                **updated,
            )
        else:
            # Создаём новую запись
            new_data = {
                "user_id": user_id,
                "date": today,
                "calories": calories,
                "protein_g": protein,
                "fat_g": fat,
                "carbs_g": carbs,
                "meal_description": meal_description,
            }
            resp = db.table("nutrition_logs").insert(new_data).execute()
            row = resp.data[0]
            return NutritionLog(
                id=row["id"],
                user_id=user_id,
                date=date.today(),
                calories=calories,
                protein_g=protein,
                fat_g=fat,
                carbs_g=carbs,
                meal_description=meal_description,
            )

    except Exception as e:
        logger.error(f"analyze_meal: ошибка: {e}")
        return None


async def get_today_nutrition(user_id: int) -> Optional[NutritionLog]:
    """Возвращает суммарное питание за сегодня или None."""
    db = get_db()
    today = date.today().isoformat()

    try:
        resp = (
            db.table("nutrition_logs")
            .select("*")
            .eq("user_id", user_id)
            .eq("date", today)
            .maybe_single()
            .execute()
        )
        if not resp.data:
            return None
        n = resp.data
        return NutritionLog(
            id=n["id"],
            user_id=user_id,
            date=date.fromisoformat(n["date"]),
            calories=n["calories"],
            protein_g=n["protein_g"],
            fat_g=n["fat_g"],
            carbs_g=n["carbs_g"],
            meal_description=n.get("meal_description"),
        )
    except Exception as e:
        logger.error(f"get_today_nutrition: ошибка: {e}")
        return None
