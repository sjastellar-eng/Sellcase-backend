# app/routers/search.py

from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db import get_db
from app.models import Category, SearchQuery, User
from app.routers.auth import get_current_user


router = APIRouter(prefix="/search", tags=["Search"])


def normalize_query(q: str) -> str:
    """Приводим запрос к нормальному виду: нижний регистр и одна пробельная полоска."""
    return " ".join(q.strip().lower().split())


@router.get("/categories")
def search_categories(
    query: str = Query(..., min_length=1, description="Поисковая строка, например: авто, iphone, квартира"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Поиск релевантных категорий по тексту.
    Используется для подбора ниши / категории под запрос.
    """
    norm = normalize_query(query)
    like = f"%{norm}%"

    # Ищем по названию, slug и keywords
    q = (
        db.query(Category)
        .filter(
            (Category.name.ilike(like)) |
            (Category.slug.ilike(like)) |
            (Category.keywords.ilike(like))
        )
        .order_by(Category.id.asc())
        .limit(limit)
    )

    categories = q.all()

    # Логируем этот поиск (для статистики и автокомплита)
    search_log = SearchQuery(
        user_id=current_user.id if current_user else None,
        query=query,
        normalized_query=norm,
        category_id=categories[0].id if categories else None,
        results_count=len(categories),
    )
    db.add(search_log)
    db.commit()

    # Отдаём аккуратный список
    return [
        {"id": c.id, "name": c.name, "slug": c.slug}
        for c in categories
    ]


@router.get("/autocomplete")
def autocomplete(
    query: str = Query(..., min_length=1, description="Часть поискового запроса"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Автокомплит:

    1) Берём подходящие категории (name / slug / keywords)
    2) Добавляем популярные запросы пользователей, которые начинаются с этого текста
    """
    norm = normalize_query(query)
    like = f"%{norm}%"
    starts = f"{norm}%"  # для поиска запросов, которые начинаются с norm

    suggestions: List[str] = []

    # 1. Подсказки из категорий
    cat_limit = max(3, limit // 2)  # минимум 3 штуки из категорий
    cat_rows = (
        db.query(Category.name)
        .filter(
            (Category.name.ilike(like)) |
            (Category.slug.ilike(like)) |
            (Category.keywords.ilike(like))
        )
        .order_by(Category.id.asc())
        .limit(cat_limit)
        .all()
    )

    for (name,) in cat_rows:
        if name not in suggestions:
            suggestions.append(name)

    # 2. Подсказки из истории запросов (SearchQuery)
    if len(suggestions) < limit:
        remaining = limit - len(suggestions)

        query_rows = (
            db.query(
                SearchQuery.normalized_query,
                func.count(SearchQuery.id).label("cnt"),
            )
            .filter(SearchQuery.normalized_query.startswith(norm))
            .group_by(SearchQuery.normalized_query)
            .order_by(func.count(SearchQuery.id).desc())
            .limit(remaining)
            .all()
        )

        for q_text, _cnt in query_rows:
            if q_text not in suggestions:
                suggestions.append(q_text)

    return suggestions
