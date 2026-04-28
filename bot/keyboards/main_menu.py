"""Главное меню бота (inline keyboard)."""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_main_menu() -> InlineKeyboardMarkup:
    """Возвращает главное меню с 4 кнопками."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💪 Тренировка", callback_data="workout"),
                InlineKeyboardButton(text="🥗 Питание", callback_data="nutrition"),
            ],
            [
                InlineKeyboardButton(text="📸 Анализ тела", callback_data="photo_analysis"),
                InlineKeyboardButton(text="👤 Профиль", callback_data="profile"),
            ],
            [
                InlineKeyboardButton(text="💬 Спросить тренера", callback_data="ask_ai"),
            ],
        ]
    )


def get_back_to_menu() -> InlineKeyboardMarkup:
    """Кнопка возврата в главное меню."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Главное меню", callback_data="main_menu")]
        ]
    )
