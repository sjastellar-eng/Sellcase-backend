import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# 1) Берём URL из переменной окружения (для Render/Docker)
# 2) Фолбэк — локальный SQLite (как у тебя сейчас), чтобы ничего не сломалось
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sellcase.db")

# Для SQLite нужен спец-параметр; для Postgres — нет
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)
Base = declarative_base()

# Зависимость для роутов FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
