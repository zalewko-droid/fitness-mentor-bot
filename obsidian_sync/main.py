"""
Obsidian Sync — локальный FastAPI сервер для записи тренировок в Obsidian vault.
Запускается на домашнем Lenovo, доступен снаружи через Cloudflare Tunnel.

Запуск:
  uvicorn main:app --host 0.0.0.0 --port 8000 --reload

Настройка туннеля:
  cloudflared tunnel --url http://localhost:8000
"""
import logging
import os
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Загружаем .env из той же директории
load_dotenv()

# Импортируем writer из той же папки
from writer import write_workout_note  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Obsidian Fitness Sync",
    description="Синхронизация тренировок из Telegram-бота в Obsidian vault",
    version="1.0.0",
)


# ── Схемы запросов ──────────────────────────────────────────────────────────
class ExerciseItem(BaseModel):
    name: str
    sets: int
    reps: int
    weight_kg: float
    muscle_group: str = ""


class WorkoutSyncRequest(BaseModel):
    user_name: str
    workout_name: str
    date: str  # YYYY-MM-DD
    duration_minutes: Optional[int] = None
    exercises: list[ExerciseItem] = []
    notes: Optional[str] = None


# ── Эндпоинты ────────────────────────────────────────────────────────────────
@app.post("/sync")
async def sync_workout(data: WorkoutSyncRequest) -> dict:
    """
    Принимает данные тренировки и записывает .md файл в Obsidian vault.
    Возвращает путь к созданному файлу.
    """
    try:
        file_path = write_workout_note(data.model_dump())
        logger.info(f"Записана заметка: {file_path}")
        return {"status": "ok", "file": file_path, "message": "Заметка создана"}
    except FileNotFoundError as e:
        logger.error(f"/sync: путь не найден: {e}")
        raise HTTPException(status_code=500, detail=f"Vault path not found: {e}")
    except Exception as e:
        logger.error(f"/sync: ошибка: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health() -> dict:
    """Проверка работоспособности сервиса и доступности vault."""
    vault_path = os.getenv("VAULT_PATH", "")
    vault_exists = os.path.isdir(vault_path) if vault_path else False

    return {
        "status": "ok",
        "vault_path": vault_path,
        "vault_accessible": vault_exists,
        "timestamp": datetime.now().isoformat(),
    }
