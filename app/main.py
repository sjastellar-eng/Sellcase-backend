# app/main.py
from fastapi import FastAPI
from app.db import Base, engine
from app.routers import leads
# from app.routers import  watchlist

# ВАЖНО: явно подгружаем модуль с моделями,
# чтобы SQLAlchemy "увидел" их перед create_all
import importlib
importlib.import_module("app.models")

# создаём таблицы
Base.metadata.create_all(bind=engine)

app = FastAPI(title="SellCase API", version="1.0.0")

# health для проверки
@app.get("/health")
def health():
    return {"status": "ok"}

# роутеры
app.include_router(leads.router)
# app.include_router(watchlist.router)
