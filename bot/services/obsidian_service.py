"""
Сервис синхронизации с локальным Obsidian Sync сервером.
Сервер запускается на домашнем Lenovo, доступен через Cloudflare Tunnel.
"""
import logging
from typing import Any

import httpx

from bot.config import settings

logger = logging.getLogger(__name__)


async def sync_workout_to_obsidian(workout_data: dict[str, Any]) -> bool:
    """
    Отправляет данные завершённой тренировки на obsidian_sync сервер.
    При ошибке (сервер недоступен) логирует предупреждение, но не падает.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{settings.OBSIDIAN_SYNC_URL}/sync",
                json=workout_data,
                headers={"Content-Type": "application/json"},
            )
            if resp.status_code == 200:
                logger.info("Тренировка синхронизирована с Obsidian")
                return True
            else:
                logger.warning(
                    f"Obsidian sync: HTTP {resp.status_code} — {resp.text[:200]}"
                )
                return False
    except httpx.TimeoutException:
        logger.warning("Obsidian sync: таймаут соединения (сервер недоступен?)")
        return False
    except Exception as e:
        logger.error(f"Obsidian sync: ошибка: {e}")
        return False


async def check_obsidian_health() -> bool:
    """Проверяет, доступен ли obsidian_sync сервер."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.OBSIDIAN_SYNC_URL}/health")
            return resp.status_code == 200
    except Exception:
        return False
