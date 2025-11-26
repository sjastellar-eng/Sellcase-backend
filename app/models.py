from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean, func
from sqlalchemy.orm import relationship
from datetime import datetime
from .db import Base

class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    message = Column(String, nullable=True)

    form_name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    page = Column(String, nullable=True)

    utm_source = Column(String, nullable=True)
    utm_medium = Column(String, nullable=True)
    utm_campaign = Column(String, nullable=True)
    utm_content = Column(String, nullable=True)
    utm_term = Column(String, nullable=True)

    raw = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    dedupe_hash = Column(String, nullable=True, unique=False)

    def __repr__(self) -> str:
        return f"<Lead id={self.id} name={self.name!r} phone={self.phone!r}>"
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"


class OlxProject(Base):
    __tablename__ = "olx_projects"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    name = Column(String, nullable=False)
    search_url = Column(String, nullable=False)  # ссылка или поисковой запрос
    notes = Column(String, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 🔗 связи
    snapshots = relationship("OlxSnapshot", back_populates="project")
    ad_snapshots = relationship("OlxAdSnapshot", back_populates="project")
    stats = relationship("OlxProjectStats", back_populates="project")

    def __repr__(self) -> str:
        return f"<OlxProject id={self.id} name={self.name!r}>"


class OlxSnapshot(Base):
    __tablename__ = "olx_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("olx_projects.id"), nullable=False, index=True)
    taken_at = Column(DateTime(timezone=True), server_default=func.now())

    items_count = Column(Integer, nullable=False, default=0)
    avg_price = Column(Float, nullable=True)
    min_price = Column(Float, nullable=True)
    max_price = Column(Float, nullable=True)

    # 🔗 обратная связь к проекту
    project = relationship("OlxProject", back_populates="snapshots")


    raw_json = Column(Text, nullable=True)  # сюда потом можно класть сырой ответ парсера

    def __repr__(self) -> str:
        return f"<OlxSnapshot id={self.id} project_id={self.project_id}>"
        
from datetime import datetime

class OlxAd(Base):
    """
    Уникальное объявление OLX.
    Хранится один раз, дальше к нему привязываем все снапшоты (цены, статусы).
    """
    __tablename__ = "olx_ads"

    id = Column(Integer, primary_key=True, index=True)
    # ID объявления в OLX (из URL вида ...-IDAbCdEF.html)
    external_id = Column(String(64), unique=True, index=True, nullable=False)

    title = Column(String(512), nullable=True)
    url = Column(String(1024), nullable=False)
    seller_id = Column(String(128), nullable=True)
    seller_name = Column(String(256), nullable=True)
    location = Column(String(256), nullable=True)
    category = Column(String(256), nullable=True)

    first_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    snapshots = relationship("OlxAdSnapshot", back_populates="ad")


class OlxAdSnapshot(Base):
    """
    Конкретный срез объявления в момент парсинга.
    Привязан и к объявлению, и к проекту.
    """
    __tablename__ = "olx_ad_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    ad_id = Column(Integer, ForeignKey("olx_ads.id"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("olx_projects.id"), nullable=False, index=True)

    price = Column(Float, nullable=True)
    currency = Column(String(8), nullable=True)

    position = Column(Integer, nullable=True)  # место на странице (опционально)
    status = Column(String(32), default="active")  # active / gone / hidden и т.д.

    collected_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    ad = relationship("OlxAd", back_populates="snapshots")
    project = relationship("OlxProject", back_populates="ad_snapshots")


class OlxProjectStats(Base):
    """
    Агрегированные метрики по проекту на момент парсинга.
    Быстрые данные для графиков и дашборда.
    """
    __tablename__ = "olx_project_stats"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("olx_projects.id"), nullable=False, index=True)

    items_count = Column(Integer, default=0)
    min_price = Column(Float, nullable=True)
    max_price = Column(Float, nullable=True)
    avg_price = Column(Float, nullable=True)
    median_price = Column(Float, nullable=True)

    new_ads_count = Column(Integer, default=0)   # новые объявления с прошлого раза
    gone_ads_count = Column(Integer, default=0)  # исчезнувшие объявления

    collected_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    project = relationship("OlxProject", back_populates="stats")
