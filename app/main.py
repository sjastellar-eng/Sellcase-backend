# app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db import Base, engine
import importlib

# 🔹 Загружаем модели, чтобы SQLAlchemy видел таблицы
importlib.import_module("app.models")

# 🔹 Создаём таблицы
Base.metadata.create_all(bind=engine)

# 🔹 Инициализация FastAPI
app = FastAPI(title="SellCase API", version="1.0.0")

# 🔹 Разрешаем CORS до подключения роутеров
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # можно заменить на домен лендинга позже
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
