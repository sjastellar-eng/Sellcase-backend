# app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db import Base, engine
import importlib

# 🔹 Загружаем модели, чтобы SQLAlchemy видел таблицы
importlib.import_module("app.models")

# 🔹 Создаём таблицы (если их нет)
Base.metadata.create_all(bind=engine)

# 🔹 Инициализация FastAPI
app = FastAPI(title="SellCase API", version="1.0.0")

# 🔹 Разрешаем CORS только для твоего домена
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://sellcase.net",        # твой домен
        "https://www.sellcase.net",    # вариант с www
        "https://sellcase-backend.onrender.com"  # backend-домен для тестов
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🔹 Проверка доступности
@app.get("/health")
def health():
    return {"status": "ok"}

# 🔹 Импортируем роутер для лидов
from app.routers.leads import router as leads_router

# 🔹 Подключаем роутер
app.include_router(leads_router)
