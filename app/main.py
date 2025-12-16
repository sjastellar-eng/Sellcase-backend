# app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.db import Base, engine, SessionLocal
from app.routers import (
    leads,
    health,
    metrics,
    olx_projects,
    olx_reports,  # новый роутер отчётов
    auth,
)
from app.routers import search as search_router
from app.routers.analytics import router as analytics_router

app.include_router(analytics_router)

import importlib

# Загружаем модели, чтобы SQLAlchemy видел таблицы
importlib.import_module("app.models")

# Создаём таблицы (если их нет)
Base.metadata.create_all(bind=engine)

from app.services.category_seed import seed_categories

# --- Авто-миграция: добавляем колонку name_ru, если её ещё нет ---
with engine.connect() as conn:
    conn.execute(text(
    "ALTER TABLE categories "
    "ADD COLUMN IF NOT EXISTS name_ru VARCHAR(255);"
    ))
    conn.commit()

# --- Сидируем категории (если их ещё нет / нужно обновить) ---
db = SessionLocal()
try:
    seed_categories(db)
finally:
    db.close()

# --- Авто-миграция: добавляем колонку is_active, если её нет ---
try:
    with engine.connect() as conn:
        conn.execute(
            text(
                """
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;
                """
            )
        )
        conn.commit()
except Exception as e:
    print("Migration error:", e)
# ----------------------------------------------------------------

# Инициализация FastAPI
app = FastAPI(
    title="SellCase API",
    version="0.1.0",
)

# Разрешаем CORS только для твоих доменов
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://sellcase.net",
        "https://www.sellcase.net",
        "https://sellcase-backend.onrender.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем все роутеры
app.include_router(health.router)
app.include_router(leads.router)
app.include_router(metrics.router)
app.include_router(olx_projects.router)
app.include_router(olx_reports.router)  # отчёты OLX
app.include_router(auth.router)
app.include_router(search_router.router)
