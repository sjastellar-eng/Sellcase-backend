from sqlalchemy import Column, Integer, String, DateTime, Text
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
