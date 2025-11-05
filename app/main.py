# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db import Base, engine
import importlib

# Загружаем модели, чтобы SQLAlchemy видел таблицы
importlib.import_module("app.models")

# Создаём таблицы (если их нет)
Base.metadata.create_all(bind=engine)

# Инициализация FastAPI
app = FastAPI(title="SellCase API", version="1.0.0")

# Разрешаем CORS только для твоего домена
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://sellcase.net",
        "https://www.sellcase.net",
        "https://sellcase-backend.onrender.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Импортируем и подключаем роутеры
from app.routers import leads, health

app.include_router(health.router)
app.include_router(leads.router)
