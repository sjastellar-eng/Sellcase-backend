# app/main.py

import importlib

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.db import Base, engine, SessionLocal
from app.routers import (
    leads,
    health,
    metrics,
    olx_projects,
    olx_reports,  # отчёты OLX
    auth,
)

# Если у тебя в этих файлах router = APIRouter(...)
from app.routers.search import router as search_router
from app.routers.analytics import router as analytics_router


# ----------------------------
# 1) Загружаем модели и создаём таблицы (если их нет)
# ----------------------------
importlib.import_module("app.models")
Base.metadata.create_all(bind=engine)


# ----------------------------
# 2) Авто-миграции / seed (как у тебя было)
#    (позже перенесём в Alembic, но сейчас оставим, чтобы не ломать прод)
# ----------------------------
def run_bootstrap():
    # --- Авто-миграция: добавляем колонку name_ru в categories, если её ещё нет ---
    with engine.connect() as conn:
        conn.execute(
            text(
                "ALTER TABLE categories "
                "ADD COLUMN IF NOT EXISTS name_ru VARCHAR(255);"
            )
        )
        conn.commit()

    # --- Сидируем категории (если их ещё нет / нужно обновить) ---
    try:
        from app.services.category_seed import seed_categories

        db = SessionLocal()
        try:
            seed_categories(db)
        finally:
            db.close()
    except Exception as e:
        print("Seed categories error:", e)

    # --- Авто-миграция: добавляем колонку is_active в users, если её нет ---
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


run_bootstrap()


# ----------------------------
# 3) Инициализация FastAPI
# ----------------------------
app = FastAPI(
    title="Sellcase API",
    version="0.1.0",
)


# ----------------------------
# 4) CORS
#    Сейчас оставил список доменов, как у тебя на скрине (можешь расширять)
# ----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://sellcase.net",
        "https://www.sellcase.net",
        "https://sellcase-backend.onrender.com",
        # на выходных добавим сюда домен фронта (например, Vercel)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----------------------------
# 5) Подключаем роутеры (ОДИН РАЗ)
# ----------------------------
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(leads.router)
app.include_router(metrics.router)
app.include_router(olx_projects.router)
app.include_router(olx_reports.router)

app.include_router(search_router)
app.include_router(analytics_router)
