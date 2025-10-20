from sqlalchemy import Column, Integer, String, DateTime, func
from app.db import Base

# Пример уже существующей модели
class Watchlist(Base):
    __tablename__ = "watchlist"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String(255), nullable=False)
    note = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ✅ Новая модель Lead — добавляем в конце
class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    phone = Column(String(50), nullable=False)
    utm_source = Column(String(100))
    utm_medium = Column(String(100))
    utm_campaign = Column(String(100))
    message = Column(String(500))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
