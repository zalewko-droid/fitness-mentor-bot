"""
Сервис уведомлений.
Формирует тексты напоминаний о тренировках с 2GIS deep-link.
"""
import logging
from datetime import date

from bot.database import get_db

logger = logging.getLogger(__name__)


async def get_users_with_workouts_today() -> list[dict]:
    """
    Возвращает список записей workouts (со вложенным users)
    для тренировок со статусом 'planned' на сегодня.
    """
    db = get_db()
    today = date.today().isoformat()

    try:
        resp = (
            db.table("workouts")
            .select("*, users(*)")
            .eq("date", today)
            .eq("status", "planned")
            .execute()
        )
        return resp.data or []
    except Exception as e:
        logger.error(f"get_users_with_workouts_today: ошибка: {e}")
        return []


def build_notification_message(workout: dict, user: dict) -> str:
    """
    Формирует HTML-сообщение напоминания о тренировке.
    Формат: имя тренировки + снаряжение + маршрут до зала (2GIS).
    """
    workout_name = workout.get("name", "Тренировка")
    gym_name = user.get("gym_name") or "твой зал"
    gym_lat = user.get("gym_lat")
    gym_lon = user.get("gym_lon")

    # Оборудование определяем эвристически по названию тренировки
    name_lower = workout_name.lower()
    if "грудь" in name_lower or "жим" in name_lower:
        equipment = "штанга/гантели, скамья, полотенце, бутылка воды"
    elif "спина" in name_lower or "тяга" in name_lower:
        equipment = "штанга, турник, ремни, полотенце, бутылка воды"
    elif "ног" in name_lower or "присед" in name_lower:
        equipment = "штанга, пояс, наколенники, полотенце, бутылка воды"
    else:
        equipment = "спортивная форма, полотенце, бутылка воды"

    msg = (
        f"💪 <b>Через час тренировка!</b>\n\n"
        f"📋 Сегодня: <b>{workout_name}</b>\n"
        f"🎒 Возьми: {equipment}\n"
        f"🏋️ Твой зал: {gym_name}\n"
    )

    # Добавляем 2GIS deep-link если есть координаты
    if gym_lat and gym_lon:
        gis_url = f"https://2gis.ru/routeSearch/to/{gym_lon},{gym_lat}/from/my_location"
        msg += f"\n📍 <a href='{gis_url}'>Маршрут в 2GIS</a>"

    msg += "\n\n💪 Ты справишься!"
    return msg
