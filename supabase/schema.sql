-- =============================================================================
-- AI Fitness Mentor — полная схема Supabase
-- Запусти этот SQL в: Supabase Dashboard → SQL Editor → New query
-- =============================================================================

-- Расширение для UUID (уже включено в Supabase по умолчанию)
-- CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- ТАБЛИЦА: users
-- =============================================================================
CREATE TABLE IF NOT EXISTS public.users (
    id              BIGSERIAL PRIMARY KEY,
    telegram_id     BIGINT    NOT NULL UNIQUE,
    name            TEXT      NOT NULL,
    age             SMALLINT  NOT NULL CHECK (age BETWEEN 10 AND 100),
    weight          NUMERIC(5,2) NOT NULL CHECK (weight > 0),    -- кг
    height          NUMERIC(5,2) NOT NULL CHECK (height > 0),    -- см
    goal            TEXT      NOT NULL,                           -- набор массы / похудение / ...
    gym_lat         DOUBLE PRECISION,
    gym_lon         DOUBLE PRECISION,
    gym_name        TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON public.users (telegram_id);

-- =============================================================================
-- ТАБЛИЦА: workouts
-- =============================================================================
CREATE TABLE IF NOT EXISTS public.workouts (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES public.users (telegram_id) ON DELETE CASCADE,
    date            DATE   NOT NULL,
    name            TEXT   NOT NULL,
    status          TEXT   NOT NULL DEFAULT 'planned'
                        CHECK (status IN ('planned', 'done', 'skipped')),
    generated_by_ai BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, date)          -- одна тренировка на пользователя в день
);

CREATE INDEX IF NOT EXISTS idx_workouts_user_date ON public.workouts (user_id, date);

-- =============================================================================
-- ТАБЛИЦА: exercises
-- =============================================================================
CREATE TABLE IF NOT EXISTS public.exercises (
    id            BIGSERIAL PRIMARY KEY,
    workout_id    BIGINT   NOT NULL REFERENCES public.workouts (id) ON DELETE CASCADE,
    name          TEXT     NOT NULL,
    sets          SMALLINT NOT NULL CHECK (sets > 0),
    reps          SMALLINT NOT NULL CHECK (reps > 0),
    weight_kg     NUMERIC(6,2) NOT NULL DEFAULT 0 CHECK (weight_kg >= 0),
    muscle_group  TEXT,
    order_index   SMALLINT NOT NULL DEFAULT 0,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_exercises_workout_id ON public.exercises (workout_id);

-- =============================================================================
-- ТАБЛИЦА: workout_logs (фактически выполненные подходы)
-- =============================================================================
CREATE TABLE IF NOT EXISTS public.workout_logs (
    id             BIGSERIAL PRIMARY KEY,
    workout_id     BIGINT   NOT NULL REFERENCES public.workouts (id) ON DELETE CASCADE,
    exercise_id    BIGINT   NOT NULL REFERENCES public.exercises (id) ON DELETE CASCADE,
    actual_sets    SMALLINT NOT NULL CHECK (actual_sets >= 0),
    actual_reps    SMALLINT NOT NULL CHECK (actual_reps >= 0),
    actual_weight  NUMERIC(6,2) NOT NULL DEFAULT 0,
    notes          TEXT,
    logged_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_workout_logs_workout ON public.workout_logs (workout_id);

-- =============================================================================
-- ТАБЛИЦА: body_photos (анализ тела через Vision API)
-- =============================================================================
CREATE TABLE IF NOT EXISTS public.body_photos (
    id            BIGSERIAL PRIMARY KEY,
    user_id       BIGINT   NOT NULL REFERENCES public.users (telegram_id) ON DELETE CASCADE,
    photo_url     TEXT     NOT NULL,
    analysis_json JSONB,                    -- полный ответ GPT-4o Vision
    weak_groups   TEXT[]   DEFAULT '{}',    -- массив слабых групп мышц
    strong_groups TEXT[]   DEFAULT '{}',    -- массив сильных групп мышц
    taken_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_body_photos_user ON public.body_photos (user_id, taken_at DESC);

-- =============================================================================
-- ТАБЛИЦА: nutrition_logs (дневник питания)
-- =============================================================================
CREATE TABLE IF NOT EXISTS public.nutrition_logs (
    id               BIGSERIAL PRIMARY KEY,
    user_id          BIGINT   NOT NULL REFERENCES public.users (telegram_id) ON DELETE CASCADE,
    date             DATE     NOT NULL,
    calories         INTEGER  NOT NULL DEFAULT 0 CHECK (calories >= 0),
    protein_g        NUMERIC(7,2) NOT NULL DEFAULT 0,
    fat_g            NUMERIC(7,2) NOT NULL DEFAULT 0,
    carbs_g          NUMERIC(7,2) NOT NULL DEFAULT 0,
    meal_description TEXT,
    UNIQUE (user_id, date)               -- одна суммарная запись на пользователя в день
);

CREATE INDEX IF NOT EXISTS idx_nutrition_user_date ON public.nutrition_logs (user_id, date);

-- =============================================================================
-- ТАБЛИЦА: ai_memory (ключевые факты для контекста GPT-4o)
-- =============================================================================
CREATE TABLE IF NOT EXISTS public.ai_memory (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT  NOT NULL REFERENCES public.users (telegram_id) ON DELETE CASCADE,
    memory_type TEXT    NOT NULL,   -- insight / workout / body_analysis / user_feedback / etc.
    content     TEXT    NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ai_memory_user ON public.ai_memory (user_id, created_at DESC);

-- =============================================================================
-- Row Level Security (RLS) — включаем, доступ только через service_role key
-- =============================================================================
ALTER TABLE public.users          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workouts       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.exercises      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workout_logs   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.body_photos    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.nutrition_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ai_memory      ENABLE ROW LEVEL SECURITY;

-- Политики для service_role (бот использует SUPABASE_KEY = service_role key)
-- service_role обходит RLS по умолчанию — политики нужны только для anon/authenticated ролей.

-- Если используешь anon key вместо service key, раскомментируй и адаптируй:
-- CREATE POLICY "users_all" ON public.users FOR ALL TO anon USING (true) WITH CHECK (true);
-- ... и т.д. для остальных таблиц.

-- =============================================================================
-- Полезные вьюхи
-- =============================================================================

-- Тренировки с количеством упражнений
CREATE OR REPLACE VIEW public.workouts_summary AS
SELECT
    w.id,
    w.user_id,
    w.date,
    w.name,
    w.status,
    w.generated_by_ai,
    COUNT(e.id) AS exercises_count,
    COALESCE(SUM(e.sets * e.reps * e.weight_kg), 0) AS total_volume_kg
FROM public.workouts w
LEFT JOIN public.exercises e ON e.workout_id = w.id
GROUP BY w.id;

-- Статистика пользователей
CREATE OR REPLACE VIEW public.user_stats AS
SELECT
    u.telegram_id,
    u.name,
    u.goal,
    COUNT(DISTINCT w.id) FILTER (WHERE w.status = 'done')    AS workouts_done,
    COUNT(DISTINCT w.id) FILTER (WHERE w.status = 'skipped') AS workouts_skipped,
    COUNT(DISTINCT w.id)                                       AS workouts_total,
    MAX(w.date) FILTER (WHERE w.status = 'done')               AS last_workout_date
FROM public.users u
LEFT JOIN public.workouts w ON w.user_id = u.telegram_id
GROUP BY u.telegram_id, u.name, u.goal;
