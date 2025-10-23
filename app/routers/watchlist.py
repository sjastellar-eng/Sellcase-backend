from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, HttpUrl
from typing import List, Optional
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import WatchItem

router = APIRouter(prefix="/watchlist", tags=["Watchlist"])

# ----- Pydantic-схемы -----
class WatchCreate(BaseModel):
    url: HttpUrl
    note: Optional[str] = None

class WatchOut(BaseModel):
    id: int
    url: str
    note: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True  # SQLAlchemy -> Pydantic v2

# ----- Эндпоинты -----
@router.get("/", response_model=List[WatchOut])
def get_watchlist(db: Session = Depends(get_db)):
    rows = db.query(models.WatchItem).order_by(models.WatchItem.id.desc()).all()
    return rows

@router.post("/", response_model=WatchOut, status_code=201)
def add_item(payload: WatchCreate, db: Session = Depends(get_db)):
    item = models.WatchItem(url=str(payload.url), note=payload.note)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

@router.delete("/{item_id}", status_code=204)
def delete_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(models.WatchItem).get(item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    db.delete(item)
    db.commit()
