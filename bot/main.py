"""
Точка входа бота AI Fitness Mentor.
Запуск: python -m bot.main
"""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import settings
from bot.handlers import start, workout, nutrition, photo, profile
from bot.scheduler import setup_scheduler

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    """Инициализация и запуск бота."""
    # Создаём бота с HTML parse_mode по умолчанию
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # Dispatcher с хранилищем FSM в памяти
    # Для production замени MemoryStorage на RedisStorage
    dp = Dispatcher(storage=MemoryStorage())

    # Регистрируем все роутеры
    dp.include_router(start.router)
    dp.include_router(workout.router)
    dp.include_router(nutrition.router)
    dp.include_router(photo.router)
    dp.include_router(profile.router)

    # Настраиваем и запускаем APScheduler
    sched = setup_scheduler(bot)
    sched.start()
    logger.info("Планировщик APScheduler запущен")

    try:
        logger.info("Бот запущен. Ожидание обновлений...")
        # drop_pending_updates=True — игнорируем сообщения пока бот был оффлайн
        await dp.start_polling(bot, drop_pending_updates=True)
    finally:
        sched.shutdown(wait=False)
        await bot.session.close()
        logger.info("Бот остановлен")


if __name__ == "__main__":
    asyncio.run(main())
