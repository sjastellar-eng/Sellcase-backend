from fastapi import FastAPI
from app.db import Base, engine

# подгружаем модели, чтобы create_all увидел таблицы
import importlib
importlib.import_module("app.models")

# создаём таблицы
Base.metadata.create_all(bind=engine)

app = FastAPI(title="SellCase API", version="1.0.0")

@app.get("/health")
def health():
    return {"status": "ok"}

# ✅ импортируем РОУТЕР из файла leads.py, без импорта пакета routers
from app.routers.leads import router as leads_router
app.include_router(leads_router)
