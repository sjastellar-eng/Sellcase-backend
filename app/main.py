# app/main.py

import importlib
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.db import Base, engine, SessionLocal

# Роутеры
from app.routers import (
    leads,
    health,
    metrics,
    olx_projects,
    olx_reports,
    auth,
)

from app.routers.search import router as search_router
from app.routers.analytics import router as analytics_router


# ------------------------------
# 1) Bootstrap: таблицы + легкие миграции + сиды
# ------------------------------
def run_bootstrap():
    # ВАЖНО: чтобы SQLAlchemy увидел модели
    importlib.import_module("app.models")

    # Создаём таблицы (если их нет)
    Base.metadata.create_all(bind=engine)

    # Авто-миграции/seed (аккуратно, без падения)
    try:
        with engine.connect() as conn:
            # пример: добавить колонку name_ru, если нет (Postgres)
            # Если SQLite - эта команда может не сработать => ловим исключение ниже
            conn.execute(
                text(
                    "ALTER TABLE categories "
                    "ADD COLUMN IF NOT EXISTS name_ru VARCHAR(255);"
                )
            )
            conn.commit()
    except Exception as e:
        print("Migration warning (categories.name_ru):", e)

    # Сид категорий (если у тебя есть этот модуль)
    try:
        from app.services.category_seed import seed_categories

        db = SessionLocal()
        try:
            seed_categories(db)
        finally:
            db.close()
    except Exception as e:
        print("Seed categories warning:", e)


# ------------------------------
# 2) Создаём FastAPI app
# ------------------------------
app = FastAPI(
    title="Sellcase API",
    version="0.1.0",
)


# ------------------------------
# 3) CORS (исправлено)
# ------------------------------
# Добавь сюда ДОМЕНА фронта (Render Static / Netlify / локально)
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",

    # твой backend (не обязательно, но не мешает)
    "https://sellcase-backend.onrender.com",
    "https://case-backend.onrender.com",
]

# Если у тебя фронт на render: dashboard.onrender.com / sellcase-dashboard.onrender.com
# Лучше добавить ИХ ТОЧНО:
ALLOWED_ORIGINS += [
    "https://dashboard.onrender.com",
    "https://sellcase-dashboard.onrender.com",
]

# Если у тебя лендинг/фронт на Netlify — добавь домен Netlify:
# пример: https://sellcase.netlify.app
# ALLOWED_ORIGINS += ["https://sellcase.netlify.app", "https://<твой_домен>"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------
# 4) Подключаем роутеры
# ------------------------------
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(leads.router)
app.include_router(metrics.router)
app.include_router(olx_projects.router)
app.include_router(olx_reports.router)

app.include_router(search_router)
app.include_router(analytics_router)


# ------------------------------
# 5) Запускаем bootstrap
# ------------------------------
run_bootstrap()


# ------------------------------
# 6) Простой health-check
# ------------------------------
@app.get("/")
def root():
    return {"status": "ok"}
