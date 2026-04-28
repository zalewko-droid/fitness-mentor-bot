"""
Обработчик /start и онбординг (FSM).
Сценарий: имя → возраст → вес → рост → цель → зал (гео или текст) → дни → время.
"""
import logging

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)

from bot.database import get_db
from bot.keyboards.main_menu import get_main_menu

logger = logging.getLogger(__name__)
router = Router()


# ── FSM состояния онбординга ────────────────────────────────────────────────
class OnboardingFSM(StatesGroup):
    waiting_name = State()
    waiting_age = State()
    waiting_weight = State()
    waiting_height = State()
    waiting_goal = State()
    waiting_gym = State()       # гео или текст
    waiting_gym_name = State()  # если выбрал «ввести вручную»
    waiting_workout_days = State()
    waiting_workout_time = State()


# ── Статические клавиатуры ──────────────────────────────────────────────────
GOALS_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💪 Набор массы"), KeyboardButton(text="🔥 Похудение")],
        [KeyboardButton(text="⚡ Поддержание формы"), KeyboardButton(text="🏃 Выносливость")],
    ],
    resize_keyboard=True,
    one_time_keyboard=True,
)

GEO_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📍 Поделиться геолокацией", request_location=True)],
        [KeyboardButton(text="✍️ Ввести название зала")],
    ],
    resize_keyboard=True,
    one_time_keyboard=True,
)


# ── /start ───────────────────────────────────────────────────────────────────
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    """Приветствие или запуск онбординга."""
    db = get_db()
    try:
        resp = (
            db.table("users")
            .select("name")
            .eq("telegram_id", message.from_user.id)
            .maybe_single()
            .execute()
        )
        if resp.data:
            await message.answer(
                f"С возвращением, <b>{resp.data['name']}</b>! 💪",
                reply_markup=get_main_menu(),
            )
            return
    except Exception as e:
        logger.error(f"cmd_start: ошибка проверки пользователя: {e}")

    await message.answer(
        "👋 Привет! Я твой персональный <b>AI-тренер</b>.\n\n"
        "Давай познакомимся. Как тебя зовут?",
        reply_markup=ReplyKeyboardRemove(),
    )
    await state.set_state(OnboardingFSM.waiting_name)


# ── Имя ───────────────────────────────────────────────────────────────────────
@router.message(OnboardingFSM.waiting_name)
async def process_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if len(name) < 2:
        await message.answer("Пожалуйста, введи своё имя (минимум 2 символа):")
        return
    await state.update_data(name=name)
    await message.answer(f"Приятно познакомиться, <b>{name}</b>! 🎉\n\nСколько тебе лет?")
    await state.set_state(OnboardingFSM.waiting_age)


# ── Возраст ───────────────────────────────────────────────────────────────────
@router.message(OnboardingFSM.waiting_age)
async def process_age(message: Message, state: FSMContext) -> None:
    try:
        age = int((message.text or "").strip())
        if not (10 <= age <= 100):
            raise ValueError
    except ValueError:
        await message.answer("Введи возраст числом от 10 до 100:")
        return
    await state.update_data(age=age)
    await message.answer("Какой у тебя вес? (в кг, например: <code>75.5</code>)")
    await state.set_state(OnboardingFSM.waiting_weight)


# ── Вес ───────────────────────────────────────────────────────────────────────
@router.message(OnboardingFSM.waiting_weight)
async def process_weight(message: Message, state: FSMContext) -> None:
    try:
        weight = float((message.text or "").strip().replace(",", "."))
        if not (30 <= weight <= 300):
            raise ValueError
    except ValueError:
        await message.answer("Введи корректный вес в кг (например: <code>75.5</code>):")
        return
    await state.update_data(weight=weight)
    await message.answer("Какой твой рост? (в см, например: <code>178</code>)")
    await state.set_state(OnboardingFSM.waiting_height)


# ── Рост ───────────────────────────────────────────────────────────────────────
@router.message(OnboardingFSM.waiting_height)
async def process_height(message: Message, state: FSMContext) -> None:
    try:
        height = float((message.text or "").strip().replace(",", "."))
        if not (100 <= height <= 250):
            raise ValueError
    except ValueError:
        await message.answer("Введи корректный рост в см (например: <code>178</code>):")
        return
    await state.update_data(height=height)
    await message.answer("Какова твоя основная цель? 🎯", reply_markup=GOALS_KB)
    await state.set_state(OnboardingFSM.waiting_goal)


# ── Цель ───────────────────────────────────────────────────────────────────────
@router.message(OnboardingFSM.waiting_goal)
async def process_goal(message: Message, state: FSMContext) -> None:
    goal = (message.text or "").strip()
    if not goal:
        await message.answer("Выбери цель или напиши свою:")
        return
    await state.update_data(goal=goal)
    await message.answer(
        "Где ты тренируешься?\n"
        "Поделись геолокацией или введи название зала:",
        reply_markup=GEO_KB,
    )
    await state.set_state(OnboardingFSM.waiting_gym)


# ── Зал: геолокация ──────────────────────────────────────────────────────────
@router.message(OnboardingFSM.waiting_gym, F.location)
async def process_gym_geo(message: Message, state: FSMContext) -> None:
    lat = message.location.latitude
    lon = message.location.longitude
    await state.update_data(gym_lat=lat, gym_lon=lon, gym_name="Мой зал")
    await _ask_workout_days(message, state)


# ── Зал: кнопка «ввести вручную» ─────────────────────────────────────────────
@router.message(OnboardingFSM.waiting_gym, F.text == "✍️ Ввести название зала")
async def process_gym_manual_btn(message: Message, state: FSMContext) -> None:
    await message.answer(
        "Введи название зала:", reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(OnboardingFSM.waiting_gym_name)


# ── Зал: текстовое название ───────────────────────────────────────────────────
@router.message(OnboardingFSM.waiting_gym)
async def process_gym_text(message: Message, state: FSMContext) -> None:
    """Любой текст в состоянии waiting_gym — это название зала."""
    gym_name = (message.text or "").strip()
    await state.update_data(gym_name=gym_name, gym_lat=None, gym_lon=None)
    await _ask_workout_days(message, state)


@router.message(OnboardingFSM.waiting_gym_name)
async def process_gym_name(message: Message, state: FSMContext) -> None:
    gym_name = (message.text or "").strip()
    await state.update_data(gym_name=gym_name, gym_lat=None, gym_lon=None)
    await _ask_workout_days(message, state)


# ── Вспомогательная функция ───────────────────────────────────────────────────
async def _ask_workout_days(message: Message, state: FSMContext) -> None:
    await message.answer(
        "В какие дни ты обычно тренируешься?\n"
        "Например: <i>Пн, Ср, Пт</i>",
        reply_markup=ReplyKeyboardRemove(),
    )
    await state.set_state(OnboardingFSM.waiting_workout_days)


# ── Дни тренировок ────────────────────────────────────────────────────────────
@router.message(OnboardingFSM.waiting_workout_days)
async def process_workout_days(message: Message, state: FSMContext) -> None:
    await state.update_data(workout_days=(message.text or "").strip())
    await message.answer(
        "В какое время предпочитаешь тренироваться?\n"
        "Например: <i>19:00</i> или <i>утром около 8</i>"
    )
    await state.set_state(OnboardingFSM.waiting_workout_time)


# ── Время тренировок → сохранение в БД ───────────────────────────────────────
@router.message(OnboardingFSM.waiting_workout_time)
async def process_workout_time(message: Message, state: FSMContext) -> None:
    await state.update_data(workout_time=(message.text or "").strip())
    data = await state.get_data()

    db = get_db()
    try:
        db.table("users").insert(
            {
                "telegram_id": message.from_user.id,
                "name": data.get("name"),
                "age": data.get("age"),
                "weight": data.get("weight"),
                "height": data.get("height"),
                "goal": data.get("goal"),
                "gym_lat": data.get("gym_lat"),
                "gym_lon": data.get("gym_lon"),
                "gym_name": data.get("gym_name"),
            }
        ).execute()

        await message.answer(
            f"✅ <b>Профиль создан!</b> Добро пожаловать, {data.get('name')}!\n\n"
            f"🎯 Цель: {data.get('goal')}\n"
            f"🏋️ Зал: {data.get('gym_name', 'не указан')}\n"
            f"📅 Дни: {data.get('workout_days')}\n"
            f"🕐 Время: {data.get('workout_time')}\n\n"
            "Я готов помочь тебе достичь результата! 💪\n"
            "Используй /workout чтобы получить тренировку на сегодня.",
            reply_markup=get_main_menu(),
        )
    except Exception as e:
        logger.error(f"process_workout_time: ошибка сохранения: {e}")
        await message.answer(
            "⚠️ Ошибка при сохранении профиля. Попробуй снова /start"
        )

    await state.clear()


# ── Обработчик кнопки «Спросить тренера» из главного меню ────────────────────
@router.callback_query(F.data == "ask_ai")
async def ask_ai_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await callback.message.answer(
        "💬 Напиши свой вопрос тренеру — отвечу с учётом твоих данных:"
    )


# ── Обработчик главного меню ──────────────────────────────────────────────────
@router.callback_query(F.data == "main_menu")
async def show_main_menu(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.edit_text(
        "Главное меню:", reply_markup=get_main_menu()
    )


# ── Fallback: любое текстовое сообщение вне FSM → AI-ответ ───────────────────
@router.message(F.text)
async def fallback_ai_chat(message: Message, state: FSMContext) -> None:
    """Любое текстовое сообщение вне FSM отправляется AI-тренеру."""
    current_state = await state.get_state()
    if current_state is not None:
        return  # Не перехватываем FSM-диалоги

    from bot.services.ai_service import chat_with_ai

    db = get_db()
    try:
        resp = (
            db.table("users")
            .select("id")
            .eq("telegram_id", message.from_user.id)
            .maybe_single()
            .execute()
        )
        if not resp.data:
            await message.answer(
                "Сначала зарегистрируйся — нажми /start"
            )
            return
    except Exception:
        pass

    await message.answer("🤔 Думаю...")
    reply = await chat_with_ai(message.from_user.id, message.text)
    await message.answer(reply)
