"""
Планировщик задач на основе APScheduler.
Отвечает за:
  - Ежедневную генерацию тренировок в 6:00
  - Утренние напоминания в 8:00 (для тренирующихся в 9:00)
  - Вечерние напоминания в 17:00 (для тренирующихся вечером)
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from bot.database import get_db
from bot.services.notification_service import (
    get_users_with_workouts_today,
    build_notification_message,
    build_map_url,
    build_route_url,
    build_2gis_url,
)

if TYPE_CHECKING:
    from aiogram import Bot

logger = logging.getLogger(__name__)

# Глобальный экземпляр планировщика
scheduler = AsyncIOScheduler(timezone="Europe/Moscow")


def setup_scheduler(bot: "Bot") -> AsyncIOScheduler:
    """Регистрирует все задачи и возвращает настроенный планировщик."""

    @scheduler.scheduled_job(CronTrigger(hour=6, minute=0))
    async def generate_daily_workouts() -> None:
        """06:00 — генерируем тренировки на день для всех пользователей."""
        logger.info("Генерация ежедневных тренировок...")
        await _generate_workouts_for_all(bot)

    @scheduler.scheduled_job(CronTrigger(hour=8, minute=0))
    async def morning_reminder() -> None:
        """08:00 — напоминание для утренних тренировок (9:00)."""
        logger.info("Отправка утренних уведомлений...")
        await _send_workout_reminders(bot)

    @scheduler.scheduled_job(CronTrigger(hour=17, minute=0))
    async def evening_reminder() -> None:
        """17:00 — напоминание для вечерних тренировок (18:00)."""
        logger.info("Отправка вечерних уведомлений...")
        await _send_workout_reminders(bot)

    return scheduler


async def _send_workout_reminders(bot: "Bot") -> None:
    """Отправляет напоминания о тренировке всем пользователям с тренировкой сегодня."""
    workouts = await get_users_with_workouts_today()

    for item in workouts:
        try:
            user_data = item.get("users") or {}
            telegram_id = user_data.get("telegram_id")
            if not telegram_id:
                continue

            msg = build_notification_message(item, user_data)
            gym_lat = user_data.get("gym_lat")
            gym_lon = user_data.get("gym_lon")

            await bot.send_message(
                chat_id=telegram_id,
                text=msg,
                parse_mode="HTML",
                disable_web_page_preview=False,
            )

            if gym_lat and gym_lon:
                try:
                    caption = (
                        f"🗺 <a href='{build_route_url(gym_lat, gym_lon)}'>Маршрут до зала</a>"
                        f"  ·  "
                        f"📍 <a href='{build_2gis_url(gym_lat, gym_lon)}'>Открыть в 2ГИС</a>"
                    )
                    await bot.send_photo(
                        chat_id=telegram_id,
                        photo=build_map_url(gym_lat, gym_lon),
                        caption=caption,
                        parse_mode="HTML",
                    )
                except Exception as map_err:
                    logger.warning(f"Не удалось отправить карту {telegram_id}: {map_err}")

            logger.info(f"Уведомление отправлено: {telegram_id}")
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления пользователю: {e}")


async def _generate_workouts_for_all(bot: "Bot") -> None:
    """Генерирует тренировки для всех зарегистрированных пользователей."""
    # Импорт здесь, чтобы избежать циклических зависимостей
    from bot.services.workout_service import get_today_workout, generate_workout

    db = get_db()
    try:
        users_resp = db.table("users").select("telegram_id, name").execute()
        for user in users_resp.data or []:
            user_id = user["telegram_id"]
            try:
                existing = await get_today_workout(user_id)
                if not existing:
                    await generate_workout(user_id)
                    logger.info(f"Тренировка сгенерирована для {user.get('name')} ({user_id})")
            except Exception as e:
                logger.error(f"Ошибка генерации для {user_id}: {e}")
    except Exception as e:
        logger.error(f"Ошибка загрузки пользователей: {e}")
