from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey, Float
from sqlalchemy.sql import func
from app.db import Base

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
    search_url = Column(String, nullable=False)  # ссылка или поисковой URL OLX
    notes = Column(String, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

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

    raw_json = Column(Text, nullable=True)  # сюда потом можно класть сырой ответ парсера

    def __repr__(self) -> str:
        return f"<OlxSnapshot id={self.id} project_id={self.project_id}>"
