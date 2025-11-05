from pydantic import BaseModel, EmailStr
from typing import Optional, Any, Dict

class LeadIn(BaseModel):
    form_name: Optional[str] = None
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    utm_content: Optional[str] = None
    utm_term: Optional[str] = None
    page: Optional[str] = None
    raw: Optional[Dict[str, Any]] = None
