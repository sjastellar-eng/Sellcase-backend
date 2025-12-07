# app/routers/search.py

from datetime import datetime
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


class SearchLogRequest(BaseModel):
    """
    Тело запроса для логирования поиска.
    Фронт может отправлять:
    - query: что ввёл пользователь
    - category_slug: выбранная категория (если есть)
    - results_count: сколько объявлений нашли
    - source: откуда запрос (по умолчанию 'frontend')
    - user_id: id пользователя в твоей системе (если нужно)
    """
    query: str
    category_slug: Optional[str] = None
    results_count: int
    source: str = "frontend"
    user_id: Optional[int] = None


class SearchLogResponse(BaseModel):
    id: int
    query: str
    normalized_query: str
    category_id: Optional[int] = None
    results_count: int
    popularity: int
    source: str

    class Config:
        orm_mode = True


# ==== Схемы для статистики =====

class TopQueryOut(BaseModel):
    id: int
    query: str
    normalized_query: str
    category_id: Optional[int] = None
    category_slug: Optional[str] = None
    category_name: Optional[str] = None
    results_count: int
    popularity: int
    source: str
    created_at: datetime

    class Config:
        orm_mode = True


class TopCategoryOut(BaseModel):
    category_id: int
    slug: str
    name: str
    name_ru: Optional[str] = None
    total_popularity: int
    avg_results: float


class SearchStatsOut(BaseModel):
    top_queries: List[TopQueryOut]
    top_categories: List[TopCategoryOut]
    empty_queries: List[TopQueryOut]


# ===== Внутренняя функция логирования =====

def log_search_query(
    db: Session,
    *,
    query: str,
    results_count: int,
    source: str = "frontend",
    category: Optional[Category] = None,
    user_id: Optional[int] = None,
) -> SearchQuery:
    """
    Пишем запрос в таблицу search_queries.

    Логика:
    - нормализуем запрос;
    - ищем запись с таким же normalized_query + category_id;
    - если есть — увеличиваем popularity;
    - если нет — создаём новую.
    """

    normalized = normalize_query(query)
    category_id = category.id if category else None

    existing = (
        db.query(SearchQuery)
        .filter(
            SearchQuery.normalized_query == normalized,
            SearchQuery.category_id.is_(category_id)
            if category_id is None
            else SearchQuery.category_id == category_id,
        )
        .first()
    )

    if existing:
        existing.popularity += 1
        existing.results_count = results_count
        existing.source = source
        if user_id is not None:
            existing.user_id = user_id
        db.commit()
        db.refresh(existing)
        return existing

    new_q = SearchQuery(
        query=query,
        normalized_query=normalized,
        category_id=category_id,
        results_count=results_count,
        popularity=1,
        source=source,
        user_id=user_id,
    )
    db.add(new_q)
    db.commit()
    db.refresh(new_q)
    return new_q


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


# ===== /search/log =====

@router.post("/log", response_model=SearchLogResponse)
def log_search_endpoint(
    payload: SearchLogRequest,
    db: Session = Depends(get_db),
):
    """
    Эндпоинт для логирования поисковых запросов.

    Идея:
    - фронт делает основной поиск (по OLX/отчётам) как сейчас;
    - после получения результата фронт отправляет сюда:
        query, category_slug (если выбрана), results_count;
    - мы пишем / обновляем запись в search_queries.
    """

    category: Optional[Category] = None
    if payload.category_slug:
        category = (
            db.query(Category)
            .filter(Category.slug == payload.category_slug)
            .first()
        )

    sq = log_search_query(
        db,
        query=payload.query,
        results_count=payload.results_count,
        source=payload.source,
        category=category,
        user_id=payload.user_id,
    )

    return sq


# ===== /search/stats =====

@router.get("/stats")
def search_stats(limit: int = 20, db: Session = Depends(get_db)):
    """
    Возвращает статистику поиска:
    - Топ популярных запросов
    - Топ категорий
    - Пустые (0 результатов) запросы
    """

    # --- Топ запросов ---
    top_queries_orm = (
        db.query(SearchQuery)
        .order_by(SearchQuery.popularity.desc(), SearchQuery.created_at.desc())
        .limit(limit)
        .all()
    )

    top_queries = [
        SearchQueryOut(
            id=q.id,
            query=q.query,
            normalized_query=q.normalized_query,
            category_id=q.category_id,
            category_slug=q.category.slug if q.category else None,
            category_name=q.category.name if q.category else None,
            results_count=q.results_count,
            popularity=q.popularity,
            source=q.source,
            created_at=q.created_at,
        )
        for q in top_queries_orm
    ]

    # --- Топ категорий ---
    top_categories = (
        db.query(
            Category.id,
            Category.slug,
            Category.name,
            func.count(SearchQuery.id).label("query_count")
        )
        .join(SearchQuery, SearchQuery.category_id == Category.id)
        .group_by(Category.id)
        .order_by(func.count(SearchQuery.id).desc())
        .limit(limit)
        .all()
    )

    # --- Пустые запросы ---
    empty_queries_orm = (
        db.query(SearchQuery)
        .filter(SearchQuery.results_count == 0)
        .order_by(SearchQuery.created_at.desc())
        .limit(limit)
        .all()
    )

    empty_queries = [
        SearchQueryOut(
            id=q.id,
            query=q.query,
            normalized_query=q.normalized_query,
            category_id=q.category_id,
            category_slug=q.category.slug if q.category else None,
            category_name=q.category.name if q.category else None,
            results_count=q.results_count,
            popularity=q.popularity,
            source=q.source,
            created_at=q.created_at,
        )
        for q in empty_queries_orm
    ]

    return SearchStatsOut(
        top_queries=top_queries,
        top_categories=top_categories,
        empty_queries=empty_queries,
    )

@router.get("/suggestions")
def get_suggestions(
    query: str,
    limit: int = 5,
    db: Session = Depends(get_db),
):
    """
    Умные подсказки:
    1) Похожие прошлые запросы (SearchQuery) по префиксу.
    2) Если мало — добавляем названия категорий по name / name_ru / keywords.
    """

    normalized = query.strip().lower()
    prefix = f"{normalized}%"

    suggestions: list[str] = []
    seen: set[str] = set()

    # 1. Подсказки из прошлых запросов
    prev_queries = (
        db.query(SearchQuery)
        .filter(SearchQuery.normalized_query.ilike(prefix))
        .order_by(
            SearchQuery.popularity.desc(),
            SearchQuery.results_count.desc(),
            SearchQuery.created_at.desc(),
        )
        .limit(limit)
        .all()
    )

    for q in prev_queries:
        value = q.normalized_query
        if value and value not in seen:
            suggestions.append(value)
            seen.add(value)

    # 2. Если подсказок мало — добавляем категории
    if len(suggestions) < limit:
        # Берём первое слово из запроса для поиска по keywords
        main_term = normalized.split()[0] if normalized else ""
        if main_term:
            like_pattern = f"%{main_term}%"

            categories = (
                db.query(Category)
                .filter(
                    or_(
                        Category.name.ilike(like_pattern),
                        Category.name_ru.ilike(like_pattern),
                        Category.keywords.ilike(like_pattern),
                    )
                )
                .limit(limit)
                .all()
            )

            for c in categories:
                label = c.name_ru or c.name
                if not label:
                    continue
                low = label.lower()
                if low not in seen:
                    suggestions.append(label)
                    seen.add(low)
                if len(suggestions) >= limit:
                    break

    return {"suggestions": suggestions}
