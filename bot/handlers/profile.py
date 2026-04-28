"""
Обработчики профиля пользователя:
  /profile — показать профиль
  /menu — главное меню
  /stats — статистика тренировок
"""
import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from bot.database import get_db
from bot.keyboards.main_menu import get_main_menu

logger = logging.getLogger(__name__)
router = Router()


def _profile_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")],
            [InlineKeyboardButton(text="⬅️ Меню", callback_data="main_menu")],
        ]
    )


async def _get_user_data(telegram_id: int) -> dict | None:
    """Загружает профиль из БД."""
    db = get_db()
    try:
        resp = (
            db.table("users")
            .select("*")
            .eq("telegram_id", telegram_id)
            .maybe_single()
            .execute()
        )
        return resp.data
    except Exception as e:
        logger.error(f"_get_user_data: ошибка: {e}")
        return None


async def _show_profile(target: Message, user_id: int, edit: bool = False) -> None:
    """Универсальный вывод профиля."""
    user = await _get_user_data(user_id)

    if not user:
        text = "⚠️ Профиль не найден. Используй /start для регистрации."
        if edit:
            await target.edit_text(text)
        else:
            await target.answer(text)
        return

    h_m = user["height"] / 100
    bmi = round(user["weight"] / (h_m ** 2), 1)

    # Описание ИМТ
    if bmi < 18.5:
        bmi_label = "дефицит массы"
    elif bmi < 25:
        bmi_label = "норма"
    elif bmi < 30:
        bmi_label = "избыток массы"
    else:
        bmi_label = "ожирение"

    text = (
        f"👤 <b>Профиль</b>\n\n"
        f"Имя: <b>{user['name']}</b>\n"
        f"Возраст: {user['age']} лет\n"
        f"Вес: {user['weight']} кг\n"
        f"Рост: {user['height']} см\n"
        f"ИМТ: {bmi} <i>({bmi_label})</i>\n\n"
        f"🎯 Цель: {user['goal']}\n"
        f"🏋️ Зал: {user.get('gym_name') or 'не указан'}\n"
    )

    kb = _profile_kb()
    if edit:
        await target.edit_text(text, reply_markup=kb)
    else:
        await target.answer(text, reply_markup=kb)


# ── /profile ──────────────────────────────────────────────────────────────────
@router.message(Command("profile"))
async def cmd_profile(message: Message) -> None:
    await _show_profile(message, message.from_user.id, edit=False)


@router.callback_query(F.data == "profile")
async def cb_profile(callback: CallbackQuery) -> None:
    await callback.answer()
    await _show_profile(callback.message, callback.from_user.id, edit=True)


# ── /menu ─────────────────────────────────────────────────────────────────────
@router.message(Command("menu"))
async def cmd_menu(message: Message) -> None:
    await message.answer("Главное меню:", reply_markup=get_main_menu())


# ── /stats — статистика тренировок ────────────────────────────────────────────
@router.message(Command("stats"))
@router.callback_query(F.data == "stats")
async def cmd_stats(event: Message | CallbackQuery) -> None:
    """Показывает статистику: всего тренировок, пропущено, последние 7 дней."""
    if isinstance(event, CallbackQuery):
        message = event.message
        user_id = event.from_user.id
        await event.answer()
        edit = True
    else:
        message = event
        user_id = event.from_user.id
        edit = False

    db = get_db()
    try:
        resp = (
            db.table("workouts")
            .select("status, date")
            .eq("user_id", user_id)
            .order("date", desc=True)
            .limit(30)
            .execute()
        )
        workouts = resp.data or []
    except Exception as e:
        logger.error(f"cmd_stats: ошибка: {e}")
        workouts = []

    total = len(workouts)
    done = sum(1 for w in workouts if w["status"] == "done")
    skipped = sum(1 for w in workouts if w["status"] == "skipped")
    planned = sum(1 for w in workouts if w["status"] == "planned")

    # Процент выполнения
    if done + skipped > 0:
        rate = round(done / (done + skipped) * 100)
    else:
        rate = 0

    # Последние 7 тренировок
    recent = workouts[:7]
    recent_str = "\n".join(
        f"  {'✅' if w['status'] == 'done' else '⏭' if w['status'] == 'skipped' else '📋'} "
        f"{w['date']}"
        for w in recent
    )

    text = (
        f"📊 <b>Статистика тренировок</b>\n\n"
        f"Всего запланировано: {total}\n"
        f"✅ Выполнено: {done}\n"
        f"⏭ Пропущено: {skipped}\n"
        f"📋 Запланировано: {planned}\n"
        f"🎯 Процент выполнения: {rate}%\n\n"
        f"<b>Последние:</b>\n{recent_str or 'нет данных'}"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ Профиль", callback_data="profile")]]
    )

    if edit:
        await message.edit_text(text, reply_markup=kb)
    else:
        await message.answer(text, reply_markup=kb)
