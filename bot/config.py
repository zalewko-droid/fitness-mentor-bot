"""
Конфигурация через переменные окружения (pydantic-settings).
Все значения берутся из .env файла в корне проекта.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Telegram Bot Token
    BOT_TOKEN: str

    # Groq API Key (llama-3.3-70b-versatile, llama-4-scout Vision)
    # Получи на: console.groq.com/keys
    GROQ_API_KEY: str

    # Supabase
    SUPABASE_URL: str
    SUPABASE_KEY: str

    # Локальный Obsidian Sync сервер (запускается на домашнем Lenovo)
    OBSIDIAN_SYNC_URL: str = "https://your-tunnel.trycloudflare.com"

    # URL Telegram Mini App (GitHub Pages)
    TMA_URL: str = "https://yourusername.github.io/fitness-mentor-tma"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


# Глобальный singleton настроек
settings = Settings()
