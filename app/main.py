# app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db import Base, engine
import importlib

# 🔹 Подгружаем модели, чтобы SQLAlchemy увидел таблицы перед create_all
importlib.import_module("app.models")

# 🔹 Создаём таблицы (если их нет)
Base.metadata.create_all(bind=engine)

# 🔹 Инициализация FastAPI приложения
app = FastAPI(title="SellCase API", version="1.0.0")

# 🔹 Разрешаем запросы с любых источников (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # позже можно ограничить, например ["https://sellcase.site"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🔹 Эндпоинт для проверки статуса
@app.get("/health")
def health():
    return {"status": "ok"}

# 🔹 Импортируем роутер с лидами
from app.routers.leads import router as leads_router

# 🔹 Подключаем роутер
app.include_router(leads_router)
