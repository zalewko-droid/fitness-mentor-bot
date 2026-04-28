"""
Обработчики раздела питания:
  /nutrition — статистика за день
  /meal — запись приёма пищи (FSM)
  callback: nutrition
"""
import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from bot.services.nutrition_service import analyze_meal, get_today_nutrition

logger = logging.getLogger(__name__)
router = Router()


class NutritionFSM(StatesGroup):
    waiting_meal_description = State()


def _nutrition_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🍽 Записать приём пищи", callback_data="add_meal")],
            [InlineKeyboardButton(text="⬅️ Меню", callback_data="main_menu")],
        ]
    )


async def _show_nutrition(target: Message, user_id: int, edit: bool = False) -> None:
    """Показывает статистику питания за сегодня."""
    log = await get_today_nutrition(user_id)

    if log:
        text = (
            f"🥗 <b>Питание за сегодня:</b>\n\n"
            f"🔥 Калории: <b>{log.calories}</b> ккал\n"
            f"💪 Белки: <b>{log.protein_g:.1f}</b> г\n"
            f"🫒 Жиры: <b>{log.fat_g:.1f}</b> г\n"
            f"🌾 Углеводы: <b>{log.carbs_g:.1f}</b> г\n\n"
            "Нажми кнопку чтобы добавить приём пищи:"
        )
    else:
        text = (
            "🥗 <b>Питание</b>\n\n"
            "Сегодня ты ещё ничего не записал!\n\n"
            "Примеры описаний:\n"
            "• <i>Овсянка 100г с бананом и молоком</i>\n"
            "• <i>Куриная грудка 200г с рисом 150г</i>\n"
            "• <i>Два яйца и тост с маслом</i>"
        )

    kb = _nutrition_menu_kb()
    if edit:
        await target.edit_text(text, reply_markup=kb)
    else:
        await target.answer(text, reply_markup=kb)


# ── /nutrition ────────────────────────────────────────────────────────────────
@router.message(Command("nutrition"))
async def cmd_nutrition(message: Message) -> None:
    await _show_nutrition(message, message.from_user.id, edit=False)


@router.callback_query(F.data == "nutrition")
async def cb_nutrition(callback: CallbackQuery) -> None:
    await callback.answer()
    await _show_nutrition(callback.message, callback.from_user.id, edit=True)


# ── /meal — начать запись ─────────────────────────────────────────────────────
@router.message(Command("meal"))
@router.callback_query(F.data == "add_meal")
async def start_meal_logging(event: Message | CallbackQuery, state: FSMContext) -> None:
    if isinstance(event, CallbackQuery):
        await event.answer()
        await event.message.answer(
            "🍽 Опиши что ты съел:\n"
            "<i>Например: куриная грудка 200г, рис 150г, огурец</i>"
        )
    else:
        await event.answer(
            "🍽 Опиши что ты съел:\n"
            "<i>Например: куриная грудка 200г, рис 150г, огурец</i>"
        )
    await state.set_state(NutritionFSM.waiting_meal_description)


# ── Обработка описания еды ────────────────────────────────────────────────────
@router.message(NutritionFSM.waiting_meal_description)
async def process_meal(message: Message, state: FSMContext) -> None:
    meal_text = (message.text or "").strip()
    if not meal_text:
        await message.answer("Пожалуйста, опиши что ты ел:")
        return

    await message.answer("🤖 Анализирую состав блюда...")
    log = await analyze_meal(message.from_user.id, meal_text)

    if log:
        await message.answer(
            f"✅ <b>Записано!</b>\n\n"
            f"🔥 Калории: +{log.calories} ккал\n"
            f"💪 Белки: +{log.protein_g:.1f} г\n"
            f"🫒 Жиры: +{log.fat_g:.1f} г\n"
            f"🌾 Углеводы: +{log.carbs_g:.1f} г\n\n"
            "Используй /nutrition чтобы посмотреть итог за день.",
            reply_markup=_nutrition_menu_kb(),
        )
    else:
        await message.answer(
            "❌ Не удалось проанализировать. Попробуй описать подробнее:\n"
            "<i>Например: 200г куриной грудки варёной, 150г гречки</i>",
            reply_markup=_nutrition_menu_kb(),
        )

    await state.clear()
