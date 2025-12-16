# app/routers/analytics.py

from datetime import datetime, timedelta, date
from typing import Optional, List, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.db import get_db
from app.models import SearchQuery  # у тебя именно так импортируется в search.py


router = APIRouter(prefix="/analytics", tags=["Analytics"])


class TopQueryItem(BaseModel):
    query: str
    count: int


class QueryPoint(BaseModel):
    bucket: str  # ISO date/datetime string
    count: int


class QueryCategoryItem(BaseModel):
    category_id: Optional[int]
    count: int


class QueryCategoryBest(BaseModel):
    query: str
    category_id: Optional[int]
    count: int


@router.get("/top-search-queries", response_model=List[TopQueryItem])
def top_search_queries(
    days: int = Query(7, ge=1, le=365),
    limit: int = Query(20, ge=1, le=200),
    user_id: Optional[int] = Query(None, ge=1),
    db: Session = Depends(get_db),
):
    since = datetime.utcnow() - timedelta(days=days)

    q = (
        db.query(
            SearchQuery.normalized_query.label("query"),
            func.count(SearchQuery.id).label("count"),
        )
        .filter(SearchQuery.created_at >= since)
    )

    if user_id is not None:
        q = q.filter(SearchQuery.user_id == user_id)

    rows = (
        q.group_by(SearchQuery.normalized_query)
        .order_by(desc(func.count(SearchQuery.id)))
        .limit(limit)
        .all()
    )

    return [{"query": r.query, "count": int(r.count)} for r in rows]


@router.get("/query-dynamics", response_model=List[QueryPoint])
def query_dynamics(
    query: str = Query(..., min_length=1),
    days: int = Query(30, ge=1, le=365),
    interval: Literal["hour", "day", "week"] = Query("day"),
    user_id: Optional[int] = Query(None, ge=1),
    db: Session = Depends(get_db),
):
    since = datetime.utcnow() - timedelta(days=days)

    bucket_expr = func.date_trunc(interval, SearchQuery.created_at).label("bucket")

    q = (
        db.query(
            bucket_expr,
            func.count(SearchQuery.id).label("count"),
        )
        .filter(SearchQuery.created_at >= since)
        .filter(SearchQuery.normalized_query == query.strip().lower())
    )

    if user_id is not None:
        q = q.filter(SearchQuery.user_id == user_id)

    rows = q.group_by(bucket_expr).order_by(bucket_expr.asc()).all()

    return [{"bucket": r.bucket.isoformat(), "count": int(r.count)} for r in rows]


@router.get("/query-to-category", response_model=List[QueryCategoryItem])
def query_to_category(
    query: str = Query(..., min_length=1),
    days: int = Query(90, ge=1, le=365),
    user_id: Optional[int] = Query(None, ge=1),
    db: Session = Depends(get_db),
):
    since = datetime.utcnow() - timedelta(days=days)

    q = (
        db.query(
            SearchQuery.category_id.label("category_id"),
            func.count(SearchQuery.id).label("count"),
        )
        .filter(SearchQuery.created_at >= since)
        .filter(SearchQuery.normalized_query == query.strip().lower())
    )

    if user_id is not None:
        q = q.filter(SearchQuery.user_id == user_id)

    rows = (
        q.group_by(SearchQuery.category_id)
        .order_by(desc(func.count(SearchQuery.id)))
        .all()
    )

    return [{"category_id": r.category_id, "count": int(r.count)} for r in rows]


@router.get("/query-to-category/best", response_model=QueryCategoryBest)
def query_to_category_best(
    query: str = Query(..., min_length=1),
    days: int = Query(90, ge=1, le=365),
    user_id: Optional[int] = Query(None, ge=1),
    db: Session = Depends(get_db),
):
    items = query_to_category(query=query, days=days, user_id=user_id, db=db)
    if not items:
        return {"query": query.strip().lower(), "category_id": None, "count": 0}
    best = items[0]
    return {"query": query.strip().lower(), "category_id": best["category_id"], "count": best["count"]}
