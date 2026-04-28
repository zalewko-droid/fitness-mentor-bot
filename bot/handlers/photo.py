"""
Обработчик фотографий.
Любое фото отправляется в GPT-4o Vision для анализа мышечного баланса.
"""
import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from bot.config import settings
from bot.services.vision_service import analyze_body_photo

logger = logging.getLogger(__name__)
router = Router()


# ── Кнопка из главного меню ────────────────────────────────────────────────────
@router.callback_query(F.data == "photo_analysis")
async def cb_photo_analysis(callback: CallbackQuery) -> None:
    """Инструкция перед отправкой фото."""
    await callback.answer()
    await callback.message.edit_text(
        "📸 <b>Анализ тела через AI</b>\n\n"
        "Отправь фото своего тела (в полный рост, хорошее освещение, нейтральный фон).\n\n"
        "AI-тренер определит:\n"
        "• 💪 Сильные группы мышц\n"
        "• ⚠️ Слабые группы мышц\n"
        "• ⚖️ Симметрию тела (1–10)\n"
        "• 📋 Персональные рекомендации\n\n"
        "Данные учтутся при генерации следующих тренировок.\n\n"
        "<i>Просто отправь фото в этот чат ↓</i>",
    )


# ── /analyze — альтернативная команда ─────────────────────────────────────────
@router.message(Command("analyze"))
async def cmd_analyze(message: Message) -> None:
    await message.answer(
        "📸 Отправь фото своего тела для анализа мышечного баланса.\n"
        "Лучший результат: полный рост, хорошее освещение."
    )


# ── Обработчик входящих фотографий ────────────────────────────────────────────
@router.message(F.photo)
async def handle_photo(message: Message) -> None:
    """
    Скачивает фото через Telegram API, передаёт в vision_service.
    Отвечает пользователю структурированным анализом.
    """
    processing_msg = await message.answer("🔍 Анализирую фото... это займёт несколько секунд.")

    # Берём фото в максимальном разрешении (последний элемент массива)
    photo = message.photo[-1]

    try:
        # Получаем путь к файлу на серверах Telegram
        file = await message.bot.get_file(photo.file_id)
        # Прямой URL к файлу (действует 1 час)
        file_url = (
            f"https://api.telegram.org/file/bot{settings.BOT_TOKEN}/{file.file_path}"
        )

        analysis = await analyze_body_photo(message.from_user.id, file_url)

        if not analysis:
            await processing_msg.delete()
            await message.answer(
                "❌ Не удалось проанализировать фото.\n\n"
                "Попробуй снова:\n"
                "• Хорошее освещение (дневной свет)\n"
                "• Нейтральный однотонный фон\n"
                "• Фото в полный рост, тело хорошо видно"
            )
            return

        weak = ", ".join(analysis.get("weak_groups", [])) or "не определено"
        strong = ", ".join(analysis.get("strong_groups", [])) or "не определено"
        score = analysis.get("symmetry_score", "?")
        assessment = analysis.get("general_assessment", "")
        recs = "\n".join(
            f"  {i + 1}. {r}"
            for i, r in enumerate(analysis.get("recommendations", []))
        )

        await processing_msg.delete()
        await message.answer(
            f"📊 <b>Анализ тела завершён!</b>\n\n"
            f"💪 Сильные мышцы: {strong}\n"
            f"⚠️ Слабые мышцы: {weak}\n"
            f"⚖️ Симметрия: <b>{score}/10</b>\n\n"
            f"📝 {assessment}\n\n"
            f"<b>Рекомендации:</b>\n{recs}\n\n"
            f"<i>Данные сохранены и будут учтены при генерации тренировок.</i>"
        )

    except Exception as e:
        logger.error(f"handle_photo: ошибка: {e}")
        await processing_msg.delete()
        await message.answer(
            "⚠️ Произошла ошибка при обработке фото. Попробуй ещё раз."
        )
