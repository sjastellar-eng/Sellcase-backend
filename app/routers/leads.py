# app/routers/leads.py
from app.services.notify import send_lead_to_telegram
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
    form_name: Optional[str] = None
    email: Optional[str] = None
    page: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    utm_content: Optional[str] = None
    utm_term: Optional[str] = None
    message: Optional[str] = None

@router.post("/")
def create_lead(payload: LeadCreate, db: Session = Depends(get_db)):
    lead = Lead(
        name=payload.name,
        phone=payload.phone,
        form_name=payload.form_name,
        email=payload.email,
        page=payload.page,
        utm_source=payload.utm_source,
        utm_medium=payload.utm_medium,
        utm_campaign=payload.utm_campaign,
        utm_content=payload.utm_content,
        utm_term=payload.utm_term,
        message=payload.message,
    )

    db.add(lead)
    db.commit()
    db.refresh(lead)

    # 🔔 отправляем уведомление в Telegram
    send_lead_to_telegram(lead)

    return {"status": "success", "lead_id": lead.id}

@router.get("/all")
def get_all_leads(db: Session = Depends(get_db)):
    leads = db.query(Lead).all()
    return [
        {
            "id": lead.id,
            "name": lead.name,
            "phone": lead.phone,
            "form_name": lead.form_name,
            "email": lead.email,
            "page": lead.page,
            "utm_source": lead.utm_source,
            "utm_medium": lead.utm_medium,
            "utm_campaign": lead.utm_campaign,
            "utm_content": lead.utm_content,
            "utm_term": lead.utm_term,
            "message": lead.message,
            "created_at": lead.created_at,
        }
        for lead in leads
                  ]
