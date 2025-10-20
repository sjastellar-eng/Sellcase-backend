from fastapi import FastAPI

from app.db import Base, engine
from app import models  # важно, чтобы модели были импортированы
from app.routers import health, watchlist, leads  # ← импорт роутеров (один раз)

# создаём таблицы, если их ещё нет
Base.metadata.create_all(bind=engine)

# приложение FastAPI
app = FastAPI(
    title="SellCase API",
    description="Backend для сервиса аналитики SellCase",
    version="1.0.0",
)

# подключаем роутеры (по одному разу)
app.include_router(health.router)
app.include_router(watchlist.router)
app.include_router(leads.router)

# корневой эндпоинт
@app.get("/")
def root():
    return {"message": "SellCase API is running 🚀"}
    
