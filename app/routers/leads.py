# app/routers/leads.py
from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import Lead

router = APIRouter(prefix="/leads", tags=["Leads"])

# Модель входящего запроса
class LeadCreate(BaseModel):
    name: str
    phone: str
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    message: Optional[str] = None

@router.post("/")
def create_lead(payload: LeadCreate, db: Session = Depends(get_db)):
    lead = Lead(
        name=payload.name,
        phone=payload.phone,
        utm_source=payload.utm_source,
        utm_medium=payload.utm_medium,
        utm_campaign=payload.utm_campaign,
        message=payload.message
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return {"status": "success", "lead_id": lead.id}
# Получение всех лидов
@router.get("/all")
def get_all_leads(db: Session = Depends(get_db)):
    leads = db.query(Lead).all()
    return [
        {
            "id": lead.id,
            "name": lead.name,
            "phone": lead.phone,
            "utm_source": lead.utm_source,
            "utm_medium": lead.utm_medium,
            "utm_campaign": lead.utm_campaign,
            "message": lead.message
        }
        for lead in leads
    ]
