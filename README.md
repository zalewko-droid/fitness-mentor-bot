# 💪 AI Fitness Mentor — Telegram Bot

Персональный AI-тренер в Telegram. Генерирует тренировки через GPT-4o, анализирует фото тела, ведёт дневник питания, синхронизирует с Obsidian и включает Telegram Mini App для удобного трекинга в зале.

## Возможности

| Функция | Описание |
|---|---|
| 🤖 AI-тренировки | GPT-4o генерирует программу под твои данные и слабые места |
| 📸 Анализ тела | Загрузи фото — AI определит слабые/сильные группы мышц |
| 🥗 Питание | Опиши еду текстом — AI посчитает КБЖУ |
| ⏰ Напоминания | Уведомление за час до тренировки с маршрутом в 2GIS |
| 📱 Mini App | Трекинг подходов + таймер отдыха + график прогресса |
| 📓 Obsidian Sync | Каждая тренировка записывается в твой vault |

---

## Быстрый старт

### 1. Клонируй и установи зависимости

```bash
cd fitness-mentor
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Создай `.env`

```bash
cp .env.example .env
```

Заполни файл `.env`:

```
BOT_TOKEN=          # от @BotFather
OPENAI_API_KEY=     # от platform.openai.com
SUPABASE_URL=       # из Supabase Dashboard → Settings → API
SUPABASE_KEY=       # service_role key (не anon!)
OBSIDIAN_SYNC_URL=  # URL твоего Cloudflare Tunnel
TMA_URL=            # URL GitHub Pages с TMA
```

### 3. Создай базу данных Supabase

1. Зайди на [supabase.com](https://supabase.com) → создай проект
2. Перейди в **SQL Editor**
3. Вставь содержимое `supabase/schema.sql` и нажми **Run**

### 4. Запусти бота

```bash
python -m bot.main
```

---

## Структура проекта

```
fitness-mentor/
├── bot/                      # Основной код бота (aiogram 3.x)
│   ├── main.py               # Точка входа
│   ├── config.py             # Настройки (pydantic-settings)
│   ├── database.py           # Supabase singleton
│   ├── scheduler.py          # APScheduler: уведомления, генерация тренировок
│   ├── handlers/             # Обработчики команд
│   │   ├── start.py          # /start + онбординг FSM
│   │   ├── workout.py        # /workout, /done
│   │   ├── nutrition.py      # /nutrition, /meal
│   │   ├── photo.py          # Анализ фото тела
│   │   └── profile.py        # /profile, /stats
│   ├── services/             # Бизнес-логика
│   │   ├── ai_service.py     # GPT-4o: контекст + чат
│   │   ├── workout_service.py
│   │   ├── nutrition_service.py
│   │   ├── vision_service.py # GPT-4o Vision
│   │   ├── notification_service.py
│   │   └── obsidian_service.py
│   ├── models/               # Pydantic модели
│   └── keyboards/            # Inline клавиатуры
├── obsidian_sync/            # FastAPI сервис для Lenovo
│   ├── main.py
│   ├── writer.py
│   └── requirements.txt
├── tma/                      # Telegram Mini App
│   ├── index.html
│   ├── app.js
│   └── style.css
├── supabase/
│   └── schema.sql
├── .env.example
├── requirements.txt
└── README.md
```

---

## Obsidian Sync (локальный сервер)

Запускается на домашнем компьютере (Lenovo), доступен через [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/).

```bash
cd obsidian_sync
pip install -r requirements.txt

# Создай .env в папке obsidian_sync:
echo "VAULT_PATH=C:/Users/yourname/Documents/Obsidian/MyVault" > .env
echo "FITNESS_FOLDER=Fitness/Workouts" >> .env

# Запусти сервер:
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# В другом терминале — запусти туннель:
cloudflared tunnel --url http://localhost:8000
```

Скопируй URL туннеля (вида `https://random.trycloudflare.com`) в `OBSIDIAN_SYNC_URL` в `.env` бота.

---

## Telegram Mini App

Статичный сайт из папки `tma/`. Хостится на **GitHub Pages**.

### Деплой на GitHub Pages

1. Создай репозиторий `fitness-mentor-tma` на GitHub
2. Скопируй файлы из `tma/` в корень репозитория
3. Включи GitHub Pages: Settings → Pages → Source: main branch / root
4. Получишь URL вида: `https://yourusername.github.io/fitness-mentor-tma`
5. Укажи его в `TMA_URL` в `.env`

### Регистрация Mini App в BotFather

```
/newapp → выбери своего бота → укажи TMA_URL
```

---

## Команды бота

| Команда | Описание |
|---|---|
| `/start` | Регистрация / главное меню |
| `/workout` | Тренировка на сегодня |
| `/done` | Отметить тренировку выполненной |
| `/nutrition` | Дневник питания за сегодня |
| `/meal` | Записать приём пищи |
| `/analyze` | Анализ фото тела (или просто отправь фото) |
| `/profile` | Твой профиль и ИМТ |
| `/stats` | Статистика тренировок |
| `/menu` | Главное меню |

---

## AI Memory System

Бот запоминает ключевые факты о пользователе в таблице `ai_memory`:

- Выполненные тренировки
- Результаты анализа тела (слабые/сильные мышцы)
- Важные высказывания пользователя (боли, предпочтения)

При каждом запросе к GPT-4o контекст автоматически включает:
- Профиль пользователя
- Последние 5 тренировок
- Последний анализ тела
- 10 последних записей памяти

---

## Технологии

- **Python 3.11+**
- **aiogram 3.x** — Router-паттерн, FSM
- **pydantic-settings** — конфигурация через .env
- **supabase-py** — PostgreSQL через Supabase
- **openai** — GPT-4o, GPT-4o Vision
- **APScheduler 3.x** — планировщик уведомлений
- **httpx** — async HTTP (Obsidian sync, скачивание фото)
- **FastAPI** — Obsidian sync сервис
- **Chart.js** — графики в Mini App (CDN)

---

## Автор

Проект создан как AI Fitness Mentor. Свободен для личного использования.
