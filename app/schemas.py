from pydantic import BaseModel, EmailStr
from typing import Optional, Any, Dict
from datetime import datetime

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
    message: Optional[str] = None
    raw: Optional[Dict[str, Any]] = None
# ---------- Users ----------

class UserBase(BaseModel):
    email: str
    full_name: Optional[str] = None


class UserCreate(UserBase):
    password: str


class UserOut(UserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
        
class LeadOut(LeadIn):
    id: int
    created_at: datetime
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class OlxProjectBase(BaseModel):
    name: str
    search_url: str
    notes: Optional[str] = None


class OlxProjectCreate(OlxProjectBase):
    pass


class OlxProjectOut(OlxProjectBase):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        orm_mode = True


class OlxSnapshotOut(BaseModel):
    id: int
    project_id: int
    taken_at: datetime
    items_count: int
    avg_price: Optional[float] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None

    class Config:
        # для Pydantic v2
        from_attributes = True
        # если хочешь, можно оставить и это (для совместимости)
        orm_mode = True
