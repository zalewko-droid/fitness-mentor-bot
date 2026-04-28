"""
AI-сервис: интеграция с Gemini через OpenAI-совместимый эндпоинт.
Основные функции:
  - build_context(user_id) — собирает полный контекст пользователя для system prompt
  - chat_with_ai(user_id, message) — отвечает с учётом контекста
  - save_memory(user_id, type, content) — сохраняет инсайты в ai_memory
"""
import json
import logging
from typing import Optional

from openai import AsyncOpenAI

from bot.config import settings
from bot.database import get_db

logger = logging.getLogger(__name__)

# Клиент openai, перенаправленный на Groq OpenAI-совместимый эндпоинт
_openai = AsyncOpenAI(
    api_key=settings.GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
)


async def build_context(user_id: int) -> str:
    """
    Строит строку контекста для системного промпта GPT-4o.
    Включает: профиль, последние 5 тренировок, последний анализ тела, записи памяти.
    """
    db = get_db()
    parts: list[str] = []

    # --- Профиль пользователя ---
    try:
        resp = (
            db.table("users")
            .select("*")
            .eq("telegram_id", user_id)
            .maybe_single()
            .execute()
        )
        if resp.data:
            u = resp.data
            bmi = round(u["weight"] / ((u["height"] / 100) ** 2), 1)
            parts.append(
                f"=== ПРОФИЛЬ ===\n"
                f"Имя: {u['name']}, Возраст: {u['age']} лет\n"
                f"Вес: {u['weight']} кг, Рост: {u['height']} см, ИМТ: {bmi}\n"
                f"Цель: {u['goal']}\n"
                f"Зал: {u.get('gym_name', 'не указан')}\n"
            )
    except Exception as e:
        logger.error(f"build_context: ошибка профиля: {e}")

    # --- Последние 5 тренировок ---
    try:
        resp = (
            db.table("workouts")
            .select("*, exercises(*)")
            .eq("user_id", user_id)
            .order("date", desc=True)
            .limit(5)
            .execute()
        )
        if resp.data:
            lines = ["=== ПОСЛЕДНИЕ ТРЕНИРОВКИ ==="]
            for w in resp.data:
                exs = ", ".join(
                    f"{e['name']} {e['sets']}×{e['reps']}@{e['weight_kg']}кг"
                    for e in (w.get("exercises") or [])
                )
                lines.append(f"  {w['date']} | {w['name']} ({w['status']}): {exs}")
            parts.append("\n".join(lines))
    except Exception as e:
        logger.error(f"build_context: ошибка тренировок: {e}")

    # --- Последний анализ тела ---
    try:
        resp = (
            db.table("body_photos")
            .select("analysis_json, taken_at")
            .eq("user_id", user_id)
            .order("taken_at", desc=True)
            .limit(1)
            .execute()
        )
        if resp.data:
            raw = resp.data[0].get("analysis_json") or {}
            if isinstance(raw, str):
                raw = json.loads(raw)
            weak = ", ".join(raw.get("weak_groups", [])) or "нет данных"
            strong = ", ".join(raw.get("strong_groups", [])) or "нет данных"
            parts.append(
                f"=== АНАЛИЗ ТЕЛА ===\n"
                f"Слабые группы: {weak}\n"
                f"Сильные группы: {strong}\n"
                f"Симметрия: {raw.get('symmetry_score', '?')}/10\n"
            )
    except Exception as e:
        logger.error(f"build_context: ошибка анализа тела: {e}")

    # --- Ключевые факты из памяти ---
    try:
        resp = (
            db.table("ai_memory")
            .select("memory_type, content, created_at")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(10)
            .execute()
        )
        if resp.data:
            lines = ["=== ПАМЯТЬ ==="]
            for m in resp.data:
                lines.append(f"  [{m['memory_type']}] {m['content']}")
            parts.append("\n".join(lines))
    except Exception as e:
        logger.error(f"build_context: ошибка памяти: {e}")

    return "\n\n".join(parts) if parts else "Данных о пользователе пока нет."


async def save_memory(user_id: int, memory_type: str, content: str) -> None:
    """Сохраняет ключевой факт в таблицу ai_memory."""
    db = get_db()
    try:
        db.table("ai_memory").insert(
            {
                "user_id": user_id,
                "memory_type": memory_type,
                "content": content[:500],  # обрезаем длинные строки
            }
        ).execute()
    except Exception as e:
        logger.error(f"save_memory: ошибка: {e}")


async def chat_with_ai(user_id: int, user_message: str) -> str:
    """
    Отправляет сообщение пользователя в GPT-4o вместе с полным контекстом.
    Возвращает ответ тренера.
    """
    context = await build_context(user_id)

    system_prompt = (
        "Ты персональный AI-тренер по фитнесу. Отвечай на русском языке.\n"
        "Давай конкретные, персонализированные советы на основе данных пользователя.\n"
        "Будь кратким, мотивирующим, используй эмодзи.\n\n"
        f"Данные о пользователе:\n{context}"
    )

    try:
        response = await _openai.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            max_tokens=800,
            temperature=0.7,
        )
        answer = response.choices[0].message.content or ""

        # Сохраняем важные высказывания пользователя в память
        trigger_words = ["болит", "проблема", "не могу", "люблю", "ненавижу", "устал", "травм"]
        if any(w in user_message.lower() for w in trigger_words):
            await save_memory(user_id, "user_feedback", user_message[:200])

        return answer
    except Exception as e:
        logger.error(f"chat_with_ai: ошибка Gemini: {e}")
        return "⚠️ AI-помощник временно недоступен. Попробуй позже."
