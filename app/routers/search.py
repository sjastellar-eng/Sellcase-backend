# app/routers/search.py

from typing import List, Literal, Optional

import re

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Category, SearchQuery

router = APIRouter(
    prefix="/search",
    tags=["search"],
)


# ===== Вспомогательная функция нормализации запроса =====

def normalize_query(q: str) -> str:
    """
    Приводим запрос к нижнему регистру, убираем лишние пробелы.
    На этом потом можно строить ИИ-классификацию.
    """
    q = q.strip().lower()
    q = re.sub(r"\s+", " ", q)
    return q


# ===== Pydantic-схемы ответов =====

class CategoryOut(BaseModel):
    id: int
    slug: str
    name: str
    name_ru: Optional[str] = None

    class Config:
        orm_mode = True


class AutocompleteItem(BaseModel):
    type: Literal["query", "category"]
    value: str
    category_id: Optional[int] = None
    slug: Optional[str] = None

    class Config:
        orm_mode = True


# ===== /search/categories =====

@router.get("/categories", response_model=List[CategoryOut])
def search_categories(
    query: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
):
    """
    Поиск категорий по названию (UA, RU) и keywords.
    Используется для подсказок категорий на фронте.
    """
    q_norm = normalize_query(query)
    pattern = f"%{q_norm}%"

    categories = (
        db.query(Category)
        .filter(
            or_(
                func.lower(Category.name).ilike(pattern),
                func.lower(Category.name_ru).ilike(pattern),
                func.lower(Category.keywords).ilike(pattern),
            )
        )
        .order_by(Category.name.asc())
        .limit(20)
        .all()
    )

    return categories


# ===== /search/autocomplete =====

@router.get("/autocomplete", response_model=List[AutocompleteItem])
def autocomplete(
    query: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
):
    """
    Автокомплит:
    1) Сначала ищем похожие прошлые запросы (SearchQuery) по префиксу.
    2) Если мало — добавляем подсказки категорий.
    """
    q_norm = normalize_query(query)
    prefix = f"{q_norm}%"

    suggestions: list[AutocompleteItem] = []

    # 1. Подсказки из прошлых запросов
    prev_queries = (
        db.query(SearchQuery)
        .filter(SearchQuery.normalized_query.ilike(prefix))
        .order_by(
            SearchQuery.popularity.desc(),
            SearchQuery.results_count.desc(),
            SearchQuery.created_at.desc(),
        )
        .limit(10)
        .all()
    )

    for q in prev_queries:
        suggestions.append(
            AutocompleteItem(
                type="query",
                value=q.query,
                category_id=q.category_id,
                slug=q.category.slug if q.category else None,
            )
        )

    # 2. Если подсказок меньше 10 — добиваем категориями
    if len(suggestions) < 10:
        pattern = f"%{q_norm}%"
        categories = (
            db.query(Category)
            .filter(
                or_(
                    func.lower(Category.name).ilike(pattern),
                    func.lower(Category.name_ru).ilike(pattern),
                    func.lower(Category.keywords).ilike(pattern),
                )
            )
            .order_by(Category.name.asc())
            .limit(10 - len(suggestions))
            .all()
        )

        for cat in categories:
            suggestions.append(
                AutocompleteItem(
                    type="category",
                    value=cat.name,
                    category_id=cat.id,
                    slug=cat.slug,
                )
            )

    return suggestions
