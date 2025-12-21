# app/routers/analytics.py

from datetime import datetime, timedelta, date
from typing import Dict, Optional, List, Literal, Any
import re

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.db import get_db
from app.models import SearchQuery, Category  # у тебя именно так импортируется в search.py


router = APIRouter(prefix="/analytics", tags=["Analytics"])

def _norm_text(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^0-9a-zа-яёіїє\s]+", " ", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _tokens(s: str) -> List[str]:
    s = _norm_text(s)
    toks = [t for t in s.split(" ") if t]
    # можно выкинуть супер-частые слова, если захочешь
    return toks

def _split_keywords(raw: Any) -> List[str]:
    """
    Поддерживаем разные форматы:
    - None
    - строка "iphone, айфон, ios"
    - список ["iphone","айфон"]
    """
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    s = str(raw).strip()
    if not s:
        return []
    # делим по запятым/точкам с запятой/переносам
    parts = re.split(r"[,\n;]+", s)
    return [p.strip() for p in parts if p.strip()]

def _category_terms(cat) -> List[str]:
    """
    Пытаемся достать термины из Category, не зная точно полей.
    Поддержим name, name_ru, keywords, synonyms, etc.
    """
    terms: List[str] = []

    for field in ["name", "name_ru", "title", "title_ru"]:
        if hasattr(cat, field):
            val = getattr(cat, field)
            if val:
                terms.append(str(val))

    # keywords/synonyms могут быть строкой или списком
    for field in ["keywords", "synonyms", "aliases", "tags"]:
        if hasattr(cat, field):
            terms += _split_keywords(getattr(cat, field))

    # нормализуем, убираем пустые
    out = []
    for t in terms:
        nt = _norm_text(t)
        if nt:
            out.append(nt)
    return list(dict.fromkeys(out))  # unique preserving order

def _score_category(query_norm: str, query_toks: List[str], cat_terms: List[str]) -> Dict[str, Any]:
    """
    Возвращает score и matched tokens/phrases.
    Логика:
    - сильный бонус за точное вхождение фразы термина в запрос
    - бонус за совпадение токенов
    """
    score = 0.0
    matched: List[str] = []

    q = query_norm

    # phrase match (самое сильное)
    for term in cat_terms:
        if not term:
            continue
        if len(term) >= 3 and term in q:
            score += 5.0
            matched.append(term)

    # token overlap
    term_toks = set()
    for term in cat_terms:
        term_toks.update(_tokens(term))

    for t in query_toks:
        if t in term_toks:
            score += 1.0
            matched.append(t)

    # небольшой бонус за количество совпадений (чтобы “iphone 11” сильнее тянуло в смартфоны)
    uniq = set(matched)
    score += min(len(uniq), 5) * 0.2

    return {"score": score, "matched": list(dict.fromkeys(matched))}

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

class CategoryGuess(BaseModel):
    id: Optional[int] = None
    name: Optional[str] = None
    confidence: float = 0.0
    source: str  # "logged" | "auto" | "none"
    matched: List[str] = []


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
    interval: Literal["day", "week"] = Query("day"),
    user_id: Optional[int] = Query(None, ge=1),
    db: Session = Depends(get_db),
):
    q_norm = query.strip().lower()

    now = datetime.utcnow()
    since = now - timedelta(days=days)

    bucket_expr = func.date_trunc(interval, SearchQuery.created_at).label("bucket")

    base = (
        db.query(bucket_expr, func.count(SearchQuery.id).label("count"))
        .filter(SearchQuery.created_at >= since)
        .filter(SearchQuery.normalized_query == q_norm)
    )
    if user_id is not None:
        base = base.filter(SearchQuery.user_id == user_id)

    rows = base.group_by(bucket_expr).order_by(bucket_expr.asc()).all()

    # Сводим в dict: дата -> count
    counts = {}
    for r in rows:
        # date_trunc возвращает datetime
        d = r.bucket.date()
        counts[d] = int(r.count)

    # Генерим сетку дат и заполняем нулями
    points: List[dict] = []
    cur = since.date()
    end = now.date()

    step_days = 1 if interval == "day" else 7
    while cur <= end:
        points.append({"bucket": cur.isoformat(), "count": counts.get(cur, 0)})
        cur = cur + timedelta(days=step_days)

    return points

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


@router.get(
    "/query-to-category/best-plus",
    response_model=QueryCategoryBest,
)
def query_to_category_best_plus(
    query: str = Query(..., min_length=1),
    days: int = Query(90, ge=1, le=365),
    user_id: Optional[int] = Query(None, ge=1),
    db: Session = Depends(get_db),
):
    """
    Лучшее определение категории для запроса:
    1) пробуем по логам (если category_id есть)
    2) если NULL — угадываем по terms категорий
    """

    q_norm = query.strip().lower()
    since = datetime.utcnow() - timedelta(days=days)

    # --- 1) Пробуем взять из логов (если category_id не null) ---
    base_query = (
        db.query(
            SearchQuery.category_id,
            func.count(SearchQuery.id).label("cnt"),
        )
        .filter(SearchQuery.normalized_query == q_norm)
        .filter(SearchQuery.created_at >= since)
    )

    if user_id is not None:
        base_query = base_query.filter(SearchQuery.user_id == user_id)

    rows = (
        base_query
        .group_by(SearchQuery.category_id)
        .order_by(func.count(SearchQuery.id).desc())
        .all()
    )

    # Если есть явная категория в логах — возвращаем 1.0 (logged)
    for category_id, cnt in rows:
        if category_id is not None:
            cat = db.query(Category).filter(Category.id == category_id).first()
            if cat:
                name = getattr(cat, "name", None) or getattr(cat, "name_ru", None)
                return {
                    "id": cat.id,
                    "name": name,
                    "confidence": 1.0,
                    "source": "logged",
                    "matched": [],
                }

    # --- 2) Если в логах NULL → auto-match по категориям ---
    cats = db.query(Category).all()
    if not cats:
        return {
            "id": None,
            "name": None,
            "confidence": 0.0,
            "source": "auto",
            "matched": [],
        }

    q_tokens = _tokens(q_norm)

    scored = []
    for c in cats:
        terms = _category_terms(c)
        res = _score_category(q_norm, q_tokens, terms)
        scored.append((c, float(res.get("score", 0.0)), res.get("matched", [])))

    scored.sort(key=lambda x: x[1], reverse=True)

    top_cat, top_score, top_matched = scored[0]
    second_score = scored[1][1] if len(scored) > 1 else 0.0

    if top_score <= 0:
        return {
            "id": None,
            "name": None,
            "confidence": 0.0,
            "source": "auto",
            "matched": [],
        }

    # --- CONFIDENCE (устойчивый, MVP-friendly, НЕ всегда 1) ---
    # 1) База: сила совпадений (масштабируем, чтобы 1 слово не давало 1.0)
    confidence = min(1.0, top_score / 10.0)

    # 2) Небольшой бонус за “сильные” совпадения (длинные токены / фразы)
    if any(len(m) >= 5 for m in top_matched):
        confidence = min(1.0, confidence + 0.10)

    # 3) Бонус за отрыв от второго места (если есть конкуренция)
    gap = top_score - second_score
    if gap >= 2:
        confidence = min(1.0, confidence + 0.10)

    confidence = round(confidence, 3)

    name = getattr(top_cat, "name", None) or getattr(top_cat, "name_ru", None)

    return {
        "id": top_cat.id,
        "name": name,
        "confidence": confidence,
        "source": "auto",
        "matched": top_matched[:12],
    }
