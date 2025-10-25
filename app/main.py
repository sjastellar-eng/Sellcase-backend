from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db import Base, engine

# подгружаем модели, чтобы create_all увидел таблицы
import importlib
importlib.import_module("app.models")

# создаём таблицы
Base.metadata.create_all(bind=engine)

app = FastAPI(title="SellCase API", version="1.0.0")

# ✅ Разрешаем запросы с лендинга (временно можно "*" для теста)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # потом заменишь на свой домен, напр. https://sellcase.site
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}

# ✅ импортируем РОУТЕР из файла leads.py
from app.routers.leads import router as leads_router
app.include_router(leads_router)
