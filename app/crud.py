from sqlalchemy.orm import Session
from . import models
from .schemas import LeadIn

def create_lead(db: Session, payload: LeadIn) -> models.Lead:
    lead = models.Lead(**payload.model_dump(exclude_unset=True))
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead

def list_leads(db: Session, limit: int = 100):
    return db.query(models.Lead).order_by(models.Lead.id.desc()).limit(limit).all()
