# app/routers/search.py

from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.db import get_db
from app.models import Category

router = APIRouter(prefix="/search", tags=["Search"])


@router.get("/categories")
def search_categories(
    query: str = Query(..., min_length=1, description="Поисковая строка"),
    limit: int = Query(10, ge=1, le=50, description="Максимум результатов"),
    db: Session = Depends(get_db),
):
    """
    Поиск категорий по названию / слагу / ключевым словам.
    Поиск нечувствителен к регистру.
    """

    q = query.strip().lower()
    if not q:
        return []

    categories = (
        db.query(Category)
        .filter(
            or_(
                func.lower(Category.name).contains(q),
                func.lower(Category.slug).contains(q),
                func.lower(Category.keywords).contains(q),
            )
        )
        .order_by(Category.name.asc())
        .limit(limit)
        .all()
    )

    # Отдаём только то, что нужно фронту
    return [
        {
            "id": cat.id,
            "name": cat.name,
            "slug": cat.slug,
        }
        for cat in categories
    ]
