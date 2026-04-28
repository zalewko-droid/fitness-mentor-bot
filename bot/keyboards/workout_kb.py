"""Клавиатуры для раздела тренировок."""
import base64
import json

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo


def get_workout_keyboard(
    workout_id: int,
    tma_url: str,
    workout_data: dict | None = None,
) -> InlineKeyboardMarkup:
    """
    Клавиатура для карточки тренировки:
    [▶️ Начать | ⏭ Пропустить]
    [📱 Открыть в App]

    Если передан workout_data, URL кнопки App получает base64-encoded JSON
    в параметре tgWebAppStartParam.
    """
    if workout_data:
        b64 = base64.urlsafe_b64encode(
            json.dumps(workout_data, ensure_ascii=False).encode()
        ).decode().rstrip("=")
        app_url = f"{tma_url}?tgWebAppStartParam={b64}"
    else:
        app_url = tma_url

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="▶️ Начать тренировку",
                    callback_data=f"start_workout:{workout_id}",
                ),
                InlineKeyboardButton(
                    text="⏭ Пропустить",
                    callback_data=f"skip_workout:{workout_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📱 Открыть в App",
                    web_app=WebAppInfo(url=app_url),
                ),
            ],
            [
                InlineKeyboardButton(text="⬅️ Меню", callback_data="main_menu"),
            ],
        ]
    )


def get_exercise_log_keyboard(workout_id: int, exercise_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для логирования упражнения."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Выполнено",
                    callback_data=f"log_ex:{workout_id}:{exercise_id}:done",
                ),
                InlineKeyboardButton(
                    text="⏭ Пропустить",
                    callback_data=f"log_ex:{workout_id}:{exercise_id}:skip",
                ),
            ],
        ]
    )


def get_generate_workout_keyboard() -> InlineKeyboardMarkup:
    """Кнопка генерации новой тренировки."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🤖 Сгенерировать тренировку",
                    callback_data="generate_workout",
                )
            ],
            [InlineKeyboardButton(text="⬅️ Меню", callback_data="main_menu")],
        ]
    )
