from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# База лежит рядом с backend/run_server.py как sellcase.db
SQLALCHEMY_DATABASE_URL = "sqlite:///./sellcase.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}  # обязательно для SQLite + FastAPI
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# зависимость для роутов
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
