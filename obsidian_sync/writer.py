"""
Модуль записи тренировочных заметок в Obsidian vault.
Формат файла: YAML frontmatter + Markdown тело.
Папка назначения: {VAULT_PATH}/{FITNESS_FOLDER}/YYYY-MM-DD-название.md
"""
import os
from datetime import datetime
from typing import Any

# Конфигурация из переменных окружения
VAULT_PATH: str = os.getenv("VAULT_PATH", "/path/to/obsidian/vault")
FITNESS_FOLDER: str = os.getenv("FITNESS_FOLDER", "Fitness/Workouts")


def write_workout_note(data: dict[str, Any]) -> str:
    """
    Создаёт Markdown-файл тренировки в Obsidian vault.

    Args:
        data: словарь с полями workout_name, date, user_name,
              duration_minutes, exercises (list), notes

    Returns:
        Абсолютный путь к созданному файлу.

    Raises:
        FileNotFoundError: если VAULT_PATH не существует.
    """
    if not os.path.isdir(VAULT_PATH):
        raise FileNotFoundError(
            f"Obsidian vault не найден: {VAULT_PATH}. "
            "Проверь переменную VAULT_PATH в .env"
        )

    date_str: str = data.get("date") or datetime.now().strftime("%Y-%m-%d")
    workout_name: str = data.get("workout_name", "Тренировка")
    user_name: str = data.get("user_name", "User")
    duration: int | None = data.get("duration_minutes")
    exercises: list[dict] = data.get("exercises") or []
    notes: str = data.get("notes") or ""

    # Считаем суммарный объём (сеты × повторения × вес)
    total_volume: float = sum(
        (e.get("sets") or 0) * (e.get("reps") or 0) * (e.get("weight_kg") or 0.0)
        for e in exercises
    )

    # Группы мышц через запятую
    muscle_groups = list(
        dict.fromkeys(e.get("muscle_group", "") for e in exercises if e.get("muscle_group"))
    )

    # ── YAML Frontmatter ─────────────────────────────────────────────────────
    frontmatter = (
        "---\n"
        f"date: {date_str}\n"
        f"workout: \"{workout_name}\"\n"
        f"athlete: \"{user_name}\"\n"
        f"duration: {duration or 'null'}\n"
        f"volume: {total_volume:.0f}\n"
        f"exercises_count: {len(exercises)}\n"
        f"muscle_groups: [{', '.join(muscle_groups)}]\n"
        "tags: [fitness, workout, ai-generated]\n"
        "---\n\n"
    )

    # ── Заголовок ────────────────────────────────────────────────────────────
    body = f"# {workout_name} — {date_str}\n\n"

    # ── Статистика ───────────────────────────────────────────────────────────
    body += "## 📊 Статистика\n\n"
    body += f"| Параметр | Значение |\n"
    body += f"|---|---|\n"
    body += f"| Дата | {date_str} |\n"
    body += f"| Атлет | {user_name} |\n"
    body += f"| Продолжительность | {duration or 'N/A'} мин |\n"
    body += f"| Общий объём | {total_volume:.0f} кг |\n"
    body += f"| Упражнений | {len(exercises)} |\n\n"

    # ── Список упражнений ────────────────────────────────────────────────────
    body += "## 💪 Упражнения\n\n"
    if exercises:
        for e in exercises:
            name = e.get("name", "?")
            sets = e.get("sets", 0)
            reps = e.get("reps", 0)
            weight = e.get("weight_kg", 0.0)
            group = e.get("muscle_group", "")
            vol = sets * reps * weight
            body += f"- [ ] **{name}** — {sets}×{reps} @ {weight} кг"
            if group:
                body += f" _({group})_"
            body += f" · объём: {vol:.0f} кг\n"
    else:
        body += "_упражнения не указаны_\n"

    body += "\n"

    # ── Заметки ──────────────────────────────────────────────────────────────
    body += "## 📝 Заметки\n\n"
    body += (notes if notes else "_нет заметок_") + "\n\n"

    # ── Подпись ──────────────────────────────────────────────────────────────
    body += "---\n_Синхронизировано AI Fitness Bot_\n"

    content = frontmatter + body

    # ── Создаём директорию и записываем файл ─────────────────────────────────
    folder = os.path.join(VAULT_PATH, FITNESS_FOLDER)
    os.makedirs(folder, exist_ok=True)

    # Транслитерация пробелов в тире, нижний регистр
    safe_name = workout_name.lower().replace(" ", "-").replace("/", "-")
    filename = f"{date_str}-{safe_name}.md"
    file_path = os.path.join(folder, filename)

    with open(file_path, "w", encoding="utf-8") as fh:
        fh.write(content)

    return file_path
