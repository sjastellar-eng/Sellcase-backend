# app/routers/search.py

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.db import get_db
from app.models import Category, SearchQuery

router = APIRouter(
    prefix="/search",
    tags=["Search"],
)


def _normalize_query(text: str) -> str:
    """
    Нормализация строки запроса:
    - trim пробелов
    - приводим к нижнему регистру
    - схлопываем множественные пробелы
    """
    return " ".join(text.strip().lower().split())


@router.get("/categories")
def search_categories(
    query: str,
    limit: int = 10,
    db: Session = Depends(get_db),
):
    """
    Поиск категорий по запросу пользователя + логирование запроса.

    Возвращаем простой список:
    [
      { "id": 1, "name": "...", "slug": "..." },
      ...
    ]
    """

    normalized = _normalize_query(query)

    # --- 1. Ищем подходящие категории ---
    categories: List[Category] = (
        db.query(Category)
        .filter(
            or_(
                Category.name.ilike(f"%{normalized}%"),
                Category.slug.ilike(f"%{normalized}%"),
                Category.keywords.ilike(f"%{normalized}%"),
            )
        )
        .order_by(Category.name.asc())
        .limit(limit)
        .all()
    )

    results_count = len(categories)

    # Если нашли ровно одну категорию — считаем её "основной"
    main_category_id = categories[0].id if results_count == 1 else None

    # --- 2. Логируем поисковый запрос ---
    try:
        search_row = SearchQuery(
            user_id=None,                # позже сюда подцепим текущего пользователя
            query=query,                 # как ввёл пользователь
            normalized_query=normalized, # нормализованная строка
            category_id=main_category_id,
            results_count=results_count,
        )
        db.add(search_row)
        db.commit()
    except Exception:
        # если логирование сломалось — откатываем БД, но поиск не ломаем
        db.rollback()

    # --- 3. Формируем ответ ---
    return [
        {
            "id": c.id,
            "name": c.name,
            "slug": c.slug,
        }
        for c in categories
    ]
