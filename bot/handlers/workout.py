"""
Обработчики раздела тренировок:
  /workout — карточка тренировки на сегодня
  /done — отметить тренировку выполненной
  callback: start_workout, skip_workout, generate_workout, log_ex
"""
import base64
import json
import logging
from urllib.parse import urlencode

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from bot.config import settings
from bot.database import get_db
from bot.keyboards.workout_kb import (
    get_workout_keyboard,
    get_generate_workout_keyboard,
    get_exercise_log_keyboard,
)
from bot.keyboards.main_menu import get_main_menu
from bot.services.workout_service import (
    generate_workout,
    get_today_workout,
    get_workout_by_id,
    mark_workout_done,
    log_exercise,
)
from bot.services.obsidian_service import sync_workout_to_obsidian
from bot.services.notification_service import build_map_url, build_route_url, build_2gis_url

logger = logging.getLogger(__name__)
router = Router()


def _workout_to_dict(workout) -> dict:
    """Сериализует объект Workout в dict для передачи в Mini App."""
    return {
        "workout_id": workout.id,
        "name": workout.name,
        "date": workout.date.isoformat(),
        "exercises": [
            {
                "id": e.id,
                "name": e.name,
                "sets": e.sets,
                "reps": e.reps,
                "weight_kg": e.weight_kg,
                "muscle_group": e.muscle_group,
                "rest_seconds": e.rest_seconds,
            }
            for e in workout.exercises
        ],
    }


def _build_tma_workout_url(workout) -> str:
    """Собирает WebApp URL с base64 JSON данными тренировки."""
    workout_data = _workout_to_dict(workout)
    encoded_data = base64.b64encode(json.dumps(workout_data).encode()).decode()
    query = urlencode({"startapp": encoded_data})
    separator = "&" if "?" in settings.TMA_URL else "?"
    return f"{settings.TMA_URL}{separator}{query}"


def _require_user(db, telegram_id: int) -> bool:
    """Проверяет, зарегистрирован ли пользователь."""
    try:
        resp = (
            db.table("users")
            .select("id")
            .eq("telegram_id", telegram_id)
            .maybe_single()
            .execute()
        )
        return bool(resp.data)
    except Exception:
        return False


def _get_user_gym(db, telegram_id: int) -> dict:
    """Возвращает gym_lat, gym_lon, gym_name пользователя."""
    try:
        resp = (
            db.table("users")
            .select("gym_lat, gym_lon, gym_name")
            .eq("telegram_id", telegram_id)
            .maybe_single()
            .execute()
        )
        return resp.data or {}
    except Exception:
        return {}


async def _show_workout(target: Message, user_id: int, edit: bool = False) -> None:
    """Универсальная функция вывода карточки тренировки."""
    db = get_db()
    if not _require_user(db, user_id):
        text = "⚠️ Сначала пройди регистрацию — /start"
        if edit:
            await target.edit_text(text)
        else:
            await target.answer(text)
        return

    workout = await get_today_workout(user_id)

    if not workout:
        text = "📋 На сегодня тренировка ещё не создана."
        kb = get_generate_workout_keyboard()
        if edit:
            await target.edit_text(text, reply_markup=kb)
        else:
            await target.answer(text, reply_markup=kb)
        return

    status_icon = {"done": "✅", "skipped": "⏭", "planned": "📋"}.get(workout.status, "📋")
    text = (
        f"{status_icon} <b>{workout.name}</b>\n\n"
        f"{workout.format_exercises()}\n\n"
        f"🏋️ Упражнений: {len(workout.exercises)}"
    )

    gym = _get_user_gym(db, user_id)
    gym_lat = gym.get("gym_lat")
    gym_lon = gym.get("gym_lon")

    if workout.status == "planned":
        app_url = _build_tma_workout_url(workout)
        kb = get_workout_keyboard(
            workout.id, app_url,
            gym_lat=gym_lat, gym_lon=gym_lon,
        )
    else:
        kb = get_main_menu()

    if edit:
        await target.edit_text(text, reply_markup=kb)
    else:
        await target.answer(text, reply_markup=kb)
        # Отправляем статическую карту зала при первом показе тренировки
        if workout.status == "planned" and gym_lat and gym_lon:
            try:
                caption = (
                    f"🗺 <a href='{build_route_url(gym_lat, gym_lon)}'>Маршрут до зала</a>"
                    f"  ·  "
                    f"📍 <a href='{build_2gis_url(gym_lat, gym_lon)}'>Открыть в 2ГИС</a>"
                )
                await target.answer_photo(
                    photo=build_map_url(gym_lat, gym_lon),
                    caption=caption,
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.warning(f"_show_workout: не удалось отправить карту: {e}")


# ── /workout ──────────────────────────────────────────────────────────────────
@router.message(Command("workout"))
async def cmd_workout(message: Message) -> None:
    await _show_workout(message, message.from_user.id, edit=False)


@router.callback_query(F.data == "workout")
async def cb_workout(callback: CallbackQuery) -> None:
    await callback.answer()
    await _show_workout(callback.message, callback.from_user.id, edit=True)


# ── Генерация тренировки ───────────────────────────────────────────────────────
@router.callback_query(F.data == "generate_workout")
async def cb_generate_workout(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.edit_text("🤖 Генерирую тренировку под тебя...")

    workout = await generate_workout(callback.from_user.id)

    if not workout:
        await callback.message.edit_text(
            "❌ Не удалось создать тренировку. Попробуй позже.",
            reply_markup=get_generate_workout_keyboard(),
        )
        return

    status_icon = "📋"
    text = (
        f"{status_icon} <b>{workout.name}</b>\n\n"
        f"{workout.format_exercises()}\n\n"
        f"🏋️ Упражнений: {len(workout.exercises)}"
    )
    db = get_db()
    gym = _get_user_gym(db, callback.from_user.id)
    app_url = _build_tma_workout_url(workout)
    await callback.message.edit_text(
        text,
        reply_markup=get_workout_keyboard(
            workout.id, app_url,
            gym_lat=gym.get("gym_lat"), gym_lon=gym.get("gym_lon"),
        ),
    )


# ── Начало тренировки ─────────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("start_workout:"))
async def cb_start_workout(callback: CallbackQuery) -> None:
    workout_id = int(callback.data.split(":")[1])
    await callback.answer("Тренировка начата! 💪", show_alert=False)
    await callback.message.answer(
        "🚀 <b>Тренировка началась!</b>\n\n"
        "Открой Mini App для удобного трекинга.\n"
        "После завершения напиши /done чтобы отметить выполнение."
    )


# ── Пропуск тренировки ────────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("skip_workout:"))
async def cb_skip_workout(callback: CallbackQuery) -> None:
    workout_id = int(callback.data.split(":")[1])
    db = get_db()
    try:
        db.table("workouts").update({"status": "skipped"}).eq("id", workout_id).execute()
    except Exception as e:
        logger.error(f"cb_skip_workout: ошибка: {e}")

    await callback.answer("Тренировка пропущена")
    await callback.message.edit_text(
        "⏭ Тренировка пропущена.\nОтдохни и приходи завтра! 🙏",
        reply_markup=get_main_menu(),
    )


# ── /done — завершить тренировку ──────────────────────────────────────────────
@router.message(Command("done"))
async def cmd_done(message: Message) -> None:
    """Отмечает тренировку как выполненную и синхронизирует с Obsidian."""
    user_id = message.from_user.id
    workout = await get_today_workout(user_id)

    if not workout:
        await message.answer("Нет активной тренировки на сегодня.")
        return

    if workout.status == "done":
        await message.answer("✅ Тренировка уже отмечена как выполненная!")
        return

    await mark_workout_done(workout.id)

    # Получаем имя пользователя для Obsidian
    db = get_db()
    user_name = "User"
    try:
        resp = (
            db.table("users")
            .select("name")
            .eq("telegram_id", user_id)
            .maybe_single()
            .execute()
        )
        if resp.data:
            user_name = resp.data["name"]
    except Exception:
        pass

    # Отправляем в Obsidian (non-blocking — ошибка не критична)
    obsidian_data = {
        "user_name": user_name,
        "workout_name": workout.name,
        "date": workout.date.isoformat(),
        "exercises": [
            {
                "name": e.name,
                "sets": e.sets,
                "reps": e.reps,
                "weight_kg": e.weight_kg,
                "muscle_group": e.muscle_group,
            }
            for e in workout.exercises
        ],
    }
    await sync_workout_to_obsidian(obsidian_data)

    total_volume = sum(e.sets * e.reps * e.weight_kg for e in workout.exercises)
    await message.answer(
        f"✅ <b>Тренировка выполнена!</b>\n\n"
        f"📋 {workout.name}\n"
        f"💪 {len(workout.exercises)} упражнений\n"
        f"📊 Объём: {total_volume:.0f} кг\n\n"
        "Отдыхай и восстанавливайся! 🏆",
        reply_markup=get_main_menu(),
    )


# ── Логирование упражнения ─────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("log_ex:"))
async def cb_log_exercise(callback: CallbackQuery) -> None:
    """Формат callback_data: log_ex:{workout_id}:{exercise_id}:{done|skip}"""
    parts = callback.data.split(":")
    if len(parts) < 4:
        await callback.answer("Ошибка данных")
        return

    workout_id = int(parts[1])
    exercise_id = int(parts[2])
    action = parts[3]

    if action == "done":
        # Получаем план для записи фактических данных
        workout = await get_workout_by_id(workout_id)
        exercise = next((e for e in (workout.exercises if workout else []) if e.id == exercise_id), None)
        if exercise:
            await log_exercise(
                workout_id=workout_id,
                exercise_id=exercise_id,
                actual_sets=exercise.sets,
                actual_reps=exercise.reps,
                actual_weight=exercise.weight_kg,
            )
        await callback.answer("✅ Упражнение выполнено!")
    else:
        await callback.answer("⏭ Упражнение пропущено")
