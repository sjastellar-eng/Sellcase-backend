# app/main.py
from fastapi import FastAPI
from app.db import Base, engine

# Явно подгружаем модели, чтобы create_all их увидел
import importlib
importlib.import_module("app.models")

# Создаём таблицы
Base.metadata.create_all(bind=engine)

app = FastAPI(title="SellCase API", version="1.0.0")

@app.get("/health")
def health():
    return {"status": "ok"}

# Роутеры — импортируем напрямую модуль и берём router
from app.routers.leads import router as leads_router
app.include_router(leads_router)

# watchlist пока отключён (когда будет готов — раскомментируешь)
# from app.routers.watchlist import router as watchlist_router
# app.include_router(watchlist_router)
