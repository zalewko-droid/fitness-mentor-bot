"""
Сервис анализа тела через Gemini Vision (OpenAI-совместимый эндпоинт).
Скачивает фото, конвертирует в base64, отправляет в Vision API,
парсит JSON-ответ и сохраняет в body_photos.
"""
import base64
import json
import logging
from typing import Optional

import httpx
from openai import AsyncOpenAI

from bot.config import settings
from bot.database import get_db
from bot.services.ai_service import save_memory

logger = logging.getLogger(__name__)
_openai = AsyncOpenAI(
    api_key=settings.GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
)

ANALYSIS_PROMPT = """Проанализируй мышечный баланс и физическую форму на фото.

Верни ТОЛЬКО валидный JSON (без markdown):
{
  "weak_groups": ["группа1"],
  "strong_groups": ["группа1"],
  "symmetry_score": 7,
  "recommendations": ["совет1", "совет2", "совет3"],
  "general_assessment": "Краткое описание в 1-2 предложения"
}

Используй только эти группы мышц:
грудь, спина, плечи, бицепс, трицепс, пресс, ноги, ягодицы, икры

symmetry_score: целое число от 1 до 10."""


async def analyze_body_photo(user_id: int, photo_url: str) -> Optional[dict]:
    """
    Скачивает фото по URL, отправляет в GPT-4o Vision, сохраняет анализ.
    Возвращает dict с результатами или None при ошибке.
    """
    try:
        # Скачиваем фото
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            resp = await http_client.get(photo_url)
            resp.raise_for_status()
            photo_bytes = resp.content

        # Конвертируем в base64
        photo_b64 = base64.b64encode(photo_bytes).decode("utf-8")

        # Определяем MIME-тип по первым байтам
        if photo_bytes[:3] == b"\xff\xd8\xff":
            mime = "image/jpeg"
        elif photo_bytes[:8] == b"\x89PNG\r\n\x1a\n":
            mime = "image/png"
        else:
            mime = "image/jpeg"  # fallback

        response = await _openai.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": ANALYSIS_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime};base64,{photo_b64}",
                                "detail": "high",
                            },
                        },
                    ],
                }
            ],
            max_tokens=600,
            temperature=0.3,
        )

        raw = response.choices[0].message.content or "{}"

        # Извлекаем JSON если GPT завернул его в markdown
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()

        analysis: dict = json.loads(raw)

        # Сохраняем в БД
        db = get_db()
        db.table("body_photos").insert(
            {
                "user_id": user_id,
                "photo_url": photo_url,
                "analysis_json": analysis,
                "weak_groups": analysis.get("weak_groups", []),
                "strong_groups": analysis.get("strong_groups", []),
            }
        ).execute()

        # Сохраняем ключевые факты в память AI
        weak = ", ".join(analysis.get("weak_groups", [])) or "не определено"
        strong = ", ".join(analysis.get("strong_groups", [])) or "не определено"
        score = analysis.get("symmetry_score", "?")
        await save_memory(
            user_id,
            "body_analysis",
            f"Слабые мышцы: {weak}. Сильные: {strong}. Симметрия: {score}/10",
        )

        return analysis

    except Exception as e:
        logger.error(f"analyze_body_photo: ошибка: {e}")
        return None
