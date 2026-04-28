"""
Singleton клиент Supabase.
Создаётся один раз при первом вызове get_db() и переиспользуется.
"""
import logging
from supabase import create_client, Client
from bot.config import settings

logger = logging.getLogger(__name__)

_client: Client | None = None


def get_db() -> Client:
    """Возвращает singleton клиент Supabase."""
    global _client
    if _client is None:
        try:
            _client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
            logger.info("Подключение к Supabase установлено")
        except Exception as e:
            logger.error(f"Ошибка подключения к Supabase: {e}")
            raise
    return _client
