# app/routers/search.py

from datetime import datetime, timedelta, date
from typing import List, Optional, Dict, Tuple, Any
from typing_extensions import Literal
from collections import Counter

import re

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Category, SearchQuery


def normalize_query_advanced(q: str) -> str:
    q = q.strip().lower()

    repl = {
        "айф": "айфон",
        "iphone": "айфон",
        "ifon": "айфон",

        "смартф": "смартфон",
        "тел": "телефон",

        "ноут": "ноутбук",
        "mac": "макбук",
        "macbook": "макбук",

        "квар": "квартира",
        "оренда": "аренда",
        "аренда": "аренда",

        "авто": "авто",
    }

    for key, val in repl.items():
        if q.startswith(key):
            return val

    return q

# Каноническое имя -> список синонимов/вариантов написания
BRAND_SYNONYMS = {
    "Apple": ["apple", "iphone", "айфон", "айф", "айфо", "айфончик", "ipad", "айпад", "macbook", "макбук", "mac", "мака"],
    "Samsung": ["samsung", "самсунг", "самс", "galaxy", "галакси"],
    "Xiaomi": ["xiaomi", "ксяоми", "сяоми", "mi", "redmi", "poco", "поко", "редми"],
    "Huawei": ["huawei", "хуавей", "honor", "хонор"],
    "Lenovo": ["lenovo", "леново"],
    "HP": ["hp", "hewlett", "павильон", "pavilion"],
    "Dell": ["dell", "делл"],
    "Asus": ["asus", "асус", "rog", "зенбук", "zenbook", "vivobook"],
    "Acer": ["acer", "асер"],
    "MSI": ["msi", "эмсиай", "мси"],
    "Sony": ["sony", "сони", "playstation", "ps4", "ps5", "плейстейшн"],
    "Nike": ["nike", "найк"],
    "Adidas": ["adidas", "адидас"],
    "Puma": ["puma", "пума"],
    "New Balance": ["new balance", "nb", "нью баланс", "ньюбаланс", "баланс"],
}

# Служебные слова, которые не помогают в определении бренда
STOP_TOKENS = {
    "бу", "б/у", "новый", "новая", "нове", "новий", "оригинал", "ориг", "копия",
    "купить", "продам", "цена", "доставка", "наложка", "торг",
}

def _tokens(s: str) -> list[str]:
    # normalize_query у тебя уже приводит к нижнему регистру и чистит пробелы — используем его
    s = normalize_query(s)
    # оставим буквы/цифры/пробел
    s = re.sub(r"[^0-9a-zа-яёіїєґ\s]+", " ", s, flags=re.IGNORECASE)
    parts = [p for p in s.split() if p and p not in STOP_TOKENS]
    return parts

def extract_model_from_query(normalized_query: str, brand: str) -> Optional[str]:
    if not normalized_query:
        return None

    q = normalized_query.strip().lower()
    tokens = [t for t in q.split() if t and t not in STOP_TOKENS]

    if not tokens:
        return None

    b = brand.lower()
    if tokens and tokens[0] == b:
        tokens = tokens[1:]

    if not tokens:
        return None

    model_tokens = tokens[:4]

    bad = {"телефон", "смартфон", "ноутбук", "планшет", "купить", "продам", "цена"}
    if len(model_tokens) == 1 and model_tokens[0] in bad:
        return None

    return " ".join(model_tokens)

def extract_brand(query: str) -> Tuple[Optional[str], float]:
    """
    Возвращает (brand, score). score 0..1.
    brand — каноническое имя из BRAND_SYNONYMS.
    """
    qn = normalize_query(query)
    toks = _tokens(qn)
    if not toks:
        return None, 0.0

    # Для поиска фраз типа "new balance"
    qn_spaced = f" {qn} "

    best_brand = None
    best_score = 0.0

    for brand, variants in BRAND_SYNONYMS.items():
        local_best = 0.0
        for v in variants:
            v_norm = normalize_query(v)

            # Фразовый матч (для "new balance" / "нью баланс" и т.п.)
            if " " in v_norm:
                if f" {v_norm} " in qn_spaced:
                    local_best = max(local_best, 1.0)
                continue

            # Токенный матч
            if v_norm in toks:
                local_best = max(local_best, 0.95)
                continue

            # Подстрочный матч для случаев "iphone11", "ps5" и т.п.
            if v_norm and v_norm in qn:
                local_best = max(local_best, 0.75)

        if local_best > best_score:
            best_score = local_best
            best_brand = brand

    return best_brand, best_score

# ==== СЮДА ВСТАВЬ ЭТО ====

AI_HINTS = {
    "айфон": [
        "айфон бу",
        "айфон 11",
        "айфон xr",
        "айфон 12",
        "купить айфон недорого",
    ],
    "смартфон": [
        "смартфон бу",
        "смартфон недорого",
        "смартфон samsung",
        "смартфон xiaomi",
    ],
    "ноутбук": [
        "ноутбук бу",
        "игровой ноутбук",
        "ноутбук для работы",
        "macbook бу",
    ],
    "макбук": [
        "macbook air бу",
        "macbook pro бу",
    ],
    "квартира": [
        "аренда квартир",
        "квартира долгосрочно",
        "купить квартиру",
        "1к квартира",
        "2к квартира",
    ],
    "аренда": [
        "аренда квартиры долгосрочно",
        "аренда квартиры посуточно",
    ],
    "авто": [
        "авто бу",
        "купить авто бу",
        "авто на запчасти",
    ],
}

def extract_model_from_query(normalized_query: str, brand: str) -> Optional[str]:
    if not normalized_query:
        return None

    q = normalized_query.strip().lower()
    tokens = [t for t in q.split() if t and t not in STOP_TOKENS]

    if not tokens:
        return None

    b = brand.lower()
    if tokens and tokens[0] == b:
        tokens = tokens[1:]

    if not tokens:
        return None

    model_tokens = tokens[:4]

    bad = {"телефон", "смартфон", "ноутбук", "планшет", "купить", "продам", "цена"}
    if len(model_tokens) == 1 and model_tokens[0] in bad:
        return None

    return " ".join(model_tokens)

def ai_hints(norm: str, items, limit: int):
    """
    Добавляем ручные AI-подсказки по якорному слову.
    norm — уже нормализованный запрос ('айфон', 'квартира' и т.п.).
    """
    for key, hints in AI_HINTS.items():
        if norm.startswith(key):
            for h in hints:
                if h not in items:
                    items.append(h)
    return items[:limit]

# ==== А ДАЛЬШЕ УЖЕ router = APIRouter(...) ====


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

# ===== Словари брендов и вспомогательные функции =====

# Известные бренды по категориям (можем расширять по ходу)
KNOWN_BRANDS: Dict[str, Dict[str, str]] = {
    # Телефоны и смартфоны
    "electronics_phones": {
        "iphone": "Apple",
        "айфон": "Apple",
        "apple": "Apple",
        "samsung": "Samsung",
        "самсунг": "Samsung",
        "xiaomi": "Xiaomi",
        "redmi": "Xiaomi",
        "mi ": "Xiaomi",       # пробел специально, чтобы не ловить случайные совпадения
        "oneplus": "OnePlus",
        "huawei": "Huawei",
        "honor": "Honor",
        "realme": "Realme",
        "oppo": "Oppo",
        "nokia": "Nokia",
    },
    # Ноутбуки (пока для будущего)
    "electronics_laptops": {
        "macbook": "Apple",
        "lenovo": "Lenovo",
        "dell": "Dell",
        "asus": "Asus",
        "acer": "Acer",
        "hp": "HP",
        "msi": "MSI",
    },
}

# Стоп-слова, которые не считаем брендами при эвристике
BRAND_STOP_WORDS = {
    "купить",
    "цена",
    "кредит",
    "б/у",
    "бу",
    "used",
    "olx",
    "дешево",
    "недорого",
}


def detect_brand_from_query(
    normalized_query: str,
    category_slug: Optional[str] = None,
) -> Optional[str]:
    """
    Пытаемся вытащить бренд из normalized_query.

    Стратегия (вариант C):
    1) Сначала ищем в словаре брендов по категории.
    2) Потом ищем по всем категориям (на случай, если category_slug не указан).
    3) Если не нашли — эвристика: берём первое слово из запроса как бренд,
       если это не стоп-слово, не чистое число и не слишком короткое.
    """
    q = normalized_query or ""
    q = q.strip()

    if not q:
        return None

    # 1) Сначала проверяем словарь для конкретной категории
    if category_slug and category_slug in KNOWN_BRANDS:
        for pattern, brand_name in KNOWN_BRANDS[category_slug].items():
            if pattern in q:
                return brand_name

    # 2) Если не нашли — пробегаемся по всем категориям/паттернам
    for cat_slug, patterns in KNOWN_BRANDS.items():
        # если категория передана, можем ограничиться ею
        if category_slug and cat_slug != category_slug:
            continue
        for pattern, brand_name in patterns.items():
            if pattern in q:
                return brand_name

    # 3) Эвристика: берём первое слово как «кандидата в бренд»
    tokens = q.split()
    if not tokens:
        return None

    first = tokens[0]

    # отсеиваем стоп-слова
    if first in BRAND_STOP_WORDS:
        return None

    # отсеиваем чистые числа
    if first.isdigit():
        return None

    # очень короткие куски тоже отбрасываем
    if len(first) < 3:
        return None

    return first


# ===== Pydantic-схемы ответов =====

class CategoryOut(BaseModel):
    id: int
    slug: str
    name: str
    name_ru: Optional[str] = None
    keywords: Optional[str] = None   # 👈 добавили

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

class TrainingSampleOut(BaseModel):
    id: int
    query: str
    normalized_query: str
    category_id: Optional[int]
    category_slug: Optional[str]
    category_name: Optional[str]
    results_count: int
    popularity: int
    source: str
    created_at: datetime

    class Config:
        orm_mode = True

# ==== Схемы для статистики =====

class SearchStatItem(BaseModel):
    id: int
    query: str
    normalized_query: str
    category_id: Optional[int]
    category_slug: Optional[str]
    category_name: Optional[str]
    results_count: int
    popularity: int
    source: str
    created_at: datetime

    class Config:
        orm_mode = True


class CategoryStatItem(BaseModel):
    category_id: int
    category_slug: Optional[str]
    category_name: Optional[str]
    total_searches: int

    class Config:
        orm_mode = True

    class Config:
        orm_mode = True


class EmptyQueryItem(BaseModel):
    id: int
    query: str
    normalized_query: str
    created_at: datetime

    class Config:
        orm_mode = True

class BrandStatItem(BaseModel):
    brand: str
    category_slug: Optional[str]
    total_searches: int
    total_results: int
    total_popularity: int
    first_seen: datetime
    last_seen: datetime

    class Config:
        orm_mode = True

class SearchStatsOut(BaseModel):
    top_queries: List[SearchStatItem]
    top_categories: List[CategoryStatItem]
    empty_queries: List[EmptyQueryItem]
    top_brands: List[BrandStatItem] = []

class TrendPointOut(BaseModel):
    period_start: datetime
    total_popularity: int
    total_results: int


class QueryTrendOut(BaseModel):
    normalized_query: str
    points: List[TrendPointOut]


class TrendsOut(BaseModel):
    period: Literal["week", "month"]
    queries: List[QueryTrendOut]

class BrandTrendPointOut(BaseModel):
    period_start: datetime
    total_searches: int
    total_results: int
    total_popularity: int


class BrandTrendOut(BaseModel):
    brand: str
    category_slug: Optional[str]
    points: List[BrandTrendPointOut]


class BrandTrendsOut(BaseModel):
    period: Literal["week", "month"]
    brands: List[BrandTrendOut]


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

    # Нормализуем запрос c учётом словарика типа "айф" -> "айфон"
    q_norm = normalize_query_advanced(query)
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

    # Явно мапим ORM-модели в Pydantic-схему CategoryOut,
    # чтобы в ответе гарантированно были keywords
    return [
        CategoryOut(
            id=c.id,
            slug=c.slug,
            name=c.name,
            name_ru=c.name_ru,
            keywords=c.keywords,
        )
        for c in categories
    ]


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

@router.get("/stats", response_model=SearchStatsOut)
def search_stats(
    limit: int = 20,
    db: Session = Depends(get_db),
):
    """
    Возвращает статистику поиска:
    - Топ популярных запросов (кластеризованных по normalized_query + category_id)
    - Топ категорий
    - Пустые (0 результатов) запросы
    """

    # --- Топ запросов (кластеризация по normalized_query + category_id) ---
    raw_queries = (
        db.query(SearchQuery)
        .order_by(
            SearchQuery.popularity.desc(),
            SearchQuery.created_at.desc(),
        )
        .limit(200)  # берём побольше, потом режем после агрегации
        .all()
    )

    # ключ = (normalized_query, category_id)
    clusters: Dict[tuple, dict] = {}

    for q in raw_queries:
        key = (q.normalized_query, q.category_id)

        if key not in clusters:
            clusters[key] = {
                "id": q.id,
                "query": q.query,
                "normalized_query": q.normalized_query,
                "category_id": q.category_id,
                "category": q.category,  # сам объект Category (может быть None)
                "results_count": 0,
                "popularity": 0,
                "source": q.source,
                "created_at": q.created_at,
            }

        agg = clusters[key]
        agg["results_count"] += q.results_count
        agg["popularity"] += q.popularity

        # самый свежий запрос в кластере
        if q.created_at > agg["created_at"]:
            agg["created_at"] = q.created_at
            agg["query"] = q.query
            agg["source"] = q.source

    # сортируем кластеры:
    # 1) по суммарной популярности
    # 2) по свежести (created_at)
    sorted_clusters = sorted(
        clusters.values(),
        key=lambda x: (x["popularity"], x["created_at"]),
        reverse=True,
    )

    # режем до limit
    top_clusters = sorted_clusters[:limit]

    # маппим в Pydantic-модель
    top_queries: List[SearchStatItem] = [
        SearchStatItem(
            id=cl["id"],
            query=cl["query"],
            normalized_query=cl["normalized_query"],
            category_id=cl["category_id"],
            category_slug=cl["category"].slug if cl["category"] else None,
            category_name=cl["category"].name if cl["category"] else None,
            results_count=cl["results_count"],
            popularity=cl["popularity"],
            source=cl["source"],
            created_at=cl["created_at"],
        )
        for cl in top_clusters
    ]

    # --- Топ категорий ---
    top_categories_rows = (
        db.query(
            Category.id.label("category_id"),
            Category.slug.label("category_slug"),
            Category.name.label("category_name"),
            func.count(SearchQuery.id).label("total_searches"),
        )
        .join(SearchQuery, SearchQuery.category_id == Category.id)
        .group_by(Category.id, Category.slug, Category.name)
        .order_by(func.count(SearchQuery.id).desc())
        .limit(limit)
        .all()
    )

    top_categories: List[CategoryStatItem] = [
        CategoryStatItem(
            category_id=row.category_id,
            category_slug=row.category_slug,
            category_name=row.category_name,
            total_searches=row.total_searches,
        )
        for row in top_categories_rows
    ]

    # --- Пустые запросы (0 результатов) ---
    empty_queries_rows = (
        db.query(SearchQuery)
        .filter(SearchQuery.results_count == 0)
        .order_by(SearchQuery.created_at.desc())
        .limit(limit)
        .all()
    )

    empty_queries: List[EmptyQueryItem] = [
        EmptyQueryItem(
            id=q.id,
            query=q.query,
            normalized_query=q.normalized_query,
            created_at=q.created_at,
        )
        for q in empty_queries_rows
    ]

    # ВАЖНО: всегда возвращаем объект SearchStatsOut, а не None
    return SearchStatsOut(
        top_queries=top_queries,
        top_categories=top_categories,
        empty_queries=empty_queries,
    )


    # ---- Топ категорий ----

    top_categories_query = (
        db.query(
            Category.id.label("category_id"),
            Category.slug.label("category_slug"),
            Category.name.label("category_name"),
            func.count(SearchQuery.id).label("total_searches"),
        )
        .join(SearchQuery, SearchQuery.category_id == Category.id)
    )

    if date_from_dt:
        top_categories_query = top_categories_query.filter(
            SearchQuery.created_at >= date_from_dt
        )
    if date_to_dt:
        top_categories_query = top_categories_query.filter(
            SearchQuery.created_at < date_to_dt
        )

    top_categories_orm = (
        top_categories_query
        .group_by(Category.id, Category.slug, Category.name)
        .order_by(func.count(SearchQuery.id).desc())
        .limit(limit)
        .all()
    )

    top_categories = [
        CategoryStatItem(
            category_id=row.category_id,
            category_slug=row.category_slug,
            category_name=row.category_name,
            total_searches=row.total_searches,
        )
        for row in top_categories_orm
    ]

    # ---- Пустые запросы (0 результатов) ----

    empty_queries_query = (
        db.query(SearchQuery)
        .filter(SearchQuery.results_count == 0)
    )

    if date_from_dt:
        empty_queries_query = empty_queries_query.filter(
            SearchQuery.created_at >= date_from_dt
        )
    if date_to_dt:
        empty_queries_query = empty_queries_query.filter(
            SearchQuery.created_at < date_to_dt
        )

    empty_queries_orm = (
        empty_queries_query
        .order_by(SearchQuery.created_at.desc())
        .limit(limit)
        .all()
    )

@router.get("/stats", response_model=SearchStatsOut)
def search_stats(
    limit: int = 20,
    db: Session = Depends(get_db),
):
    """
    Возвращает статистику поиска:
    - Топ популярных запросов
    - Топ категорий
    - Пустые (0 результатов) запросы
    - Топ брендов
    """

    # --- Топ запросов (кластеризация по normalized_query + category_id) ---
    raw_queries = (
        db.query(SearchQuery)
        .order_by(SearchQuery.popularity.desc(), SearchQuery.created_at.desc())
        .limit(200)
        .all()
    )

    clusters: Dict[tuple, dict] = {}

    for q in raw_queries:
        key = (q.normalized_query, q.category_id)

        if key not in clusters:
            clusters[key] = {
                "id": q.id,
                "query": q.query,
                "normalized_query": q.normalized_query,
                "category_id": q.category_id,
                "category": q.category,
                "results_count": 0,
                "popularity": 0,
                "source": q.source,
                "created_at": q.created_at,
            }

        agg = clusters[key]
        agg["results_count"] += q.results_count
        agg["popularity"] += q.popularity

        if q.created_at > agg["created_at"]:
            agg["created_at"] = q.created_at
            agg["query"] = q.query
            agg["source"] = q.source

    sorted_clusters = sorted(
        clusters.values(),
        key=lambda x: (x["popularity"], x["created_at"]),
        reverse=True,
    )

    top_clusters = sorted_clusters[:limit]

    top_queries = [
        SearchQueryOut(
            id=cl["id"],
            query=cl["query"],
            normalized_query=cl["normalized_query"],
            category_id=cl["category_id"],
            category_slug=cl["category"].slug if cl["category"] else None,
            category_name=cl["category"].name if cl["category"] else None,
            results_count=cl["results_count"],
            popularity=cl["popularity"],
            source=cl["source"],
            created_at=cl["created_at"],
        )
        for cl in top_clusters
    ]

    # --- Топ категорий ---
    top_categories_orm = (
        db.query(
            Category.id.label("category_id"),
            Category.slug.label("category_slug"),
            Category.name.label("category_name"),
            func.count(SearchQuery.id).label("total_searches"),
        )
        .join(SearchQuery, SearchQuery.category_id == Category.id)
        .group_by(Category.id, Category.slug, Category.name)
        .order_by(func.count(SearchQuery.id).desc())
        .limit(limit)
        .all()
    )

    top_categories = [
        CategoryStatItem(
            category_id=row.category_id,
            category_slug=row.category_slug,
            category_name=row.category_name,
            total_searches=row.total_searches,
        )
        for row in top_categories_orm
    ]

    # --- Пустые (0 результатов) запросы ---
    empty_queries_orm = (
        db.query(SearchQuery)
        .filter(SearchQuery.results_count == 0)
        .order_by(SearchQuery.created_at.desc())
        .limit(limit)
        .all()
    )

    empty_queries = [
        EmptyQueryItem(
            id=q.id,
            query=q.query,
            normalized_query=q.normalized_query,
            created_at=q.created_at,
        )
        for q in empty_queries_orm
    ]

    # --- Топ брендов ---
    brand_rows = (
        db.query(
            func.lower(SearchQuery.normalized_query).label("brand"),
            Category.slug.label("category_slug"),
            func.count(SearchQuery.id).label("total_searches"),
            func.sum(SearchQuery.results_count).label("total_results"),
            func.sum(SearchQuery.popularity_score).label("total_popularity"),
            func.min(SearchQuery.created_at).label("first_seen"),
            func.max(SearchQuery.created_at).label("last_seen"),
        )
        .outerjoin(Category, Category.id == SearchQuery.category_id)
        .group_by(SearchQuery.normalized_query, Category.slug)
        .order_by(
        func.count(SearchQuery.id).desc(),              # A: по числу поисков
        func.sum(SearchQuery.popularity_score).desc(),  # B: по суммарному score
        func.max(SearchQuery.created_at).desc(),        # C: по свежести
    )
    .limit(limit)
    .all()
    )

    top_brands = [
        BrandStatItem(
            brand=row.brand,
            category_slug=row.category_slug,
            total_searches=row.total_searches,
            total_results=row.total_results or 0,
            total_popularity=row.total_popularity or 0,
            first_seen=row.first_seen,
            last_seen=row.last_seen,
        )
        for row in brand_rows
    ]

    return SearchStatsOut(
        top_queries=top_queries,
        top_categories=top_categories,
        empty_queries=empty_queries,
        top_brands=top_brands,
    )

@router.get("/analytics/top-brands")
def top_brands(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(10, ge=1, le=50),
    min_score: float = Query(0.0, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """
    Топ брендов по поисковым запросам за период.
    - days: за сколько дней считать
    - limit: сколько брендов вернуть
    - min_score: если extract_brand возвращает (brand, score), можно отсечь слабые совпадения
    """

    since = datetime.utcnow() - timedelta(days=days)

    # Берём только normalized_query за период
    rows = (
        db.query(SearchQuery.normalized_query)
        .filter(SearchQuery.created_at >= since)
        .all()
    )

    brand_counter: Dict[str, int] = {}

    for (q,) in rows:
        if not q:
            continue

        # extract_brand может вернуть:
        # 1) "Apple" (строка)
        # 2) ("Apple", 0.83) (кортеж)
        res = extract_brand(q)

        brand: Optional[str] = None
        score: float = 1.0

        if isinstance(res, tuple) and len(res) >= 2:
            brand, score = res[0], float(res[1])
        else:
            brand = res

        if not brand:
            continue

        if score < min_score:
            continue

        brand_counter[brand] = brand_counter.get(brand, 0) + 1

    sorted_brands = sorted(brand_counter.items(), key=lambda x: x[1], reverse=True)

    return [{"brand": brand, "count": count} for brand, count in sorted_brands[:limit]]
    
@router.get("/brands", response_model=List[BrandStatItem])
def search_brands(
    category_slug: Optional[str] = Query(
        None,
        description="Slug категории (например, electronics_phones). Если не указан — по всем категориям.",
    ),
    limit: int = Query(
        50,
        ge=1,
        le=500,
        description="Максимальное количество брендов в ответе.",
    ),
    min_searches: int = Query(
        1,
        ge=1,
        le=500,
        description="Минимальное количество поисков по бренду, чтобы он попал в выдачу.",
    ),
    sort_by: Literal["searches", "popularity", "results", "last_seen"] = Query(
        "searches",
        description="Как сортировать бренды: searches / popularity / results / last_seen.",
    ),
    db: Session = Depends(get_db),
):
    """
    Возвращает статистику по брендам:
    - можно фильтровать по категории;
    - можно управлять сортировкой.
    """

    # Базовый запрос по брендам
    q = (
        db.query(
            func.lower(SearchQuery.normalized_query).label("brand"),
            Category.slug.label("category_slug"),
            func.count(SearchQuery.id).label("total_searches"),
            func.coalesce(func.sum(SearchQuery.results_count), 0).label("total_results"),
            func.coalesce(func.sum(SearchQuery.popularity_score), 0).label("total_popularity"),
            func.min(SearchQuery.created_at).label("first_seen"),
            func.max(SearchQuery.created_at).label("last_seen"),
        )
        # ВАЖНО: inner join — берём только запросы с категорией
        .join(Category, Category.id == SearchQuery.category_id)
    )

    # ----- A. Строгий фильтр по категории -----
    if category_slug:
        q = q.filter(Category.slug == category_slug)

    # Группируем по бренду + категории
    q = q.group_by(
        func.lower(SearchQuery.normalized_query),
        Category.slug,
    )

    # Фильтр по минимальному количеству поисков
    q = q.having(func.count(SearchQuery.id) >= min_searches)

    # ----- B. Умная сортировка -----
    if sort_by == "searches":
        # сначала по количеству поисков, затем по свежести
        q = q.order_by(
            func.count(SearchQuery.id).desc(),
            func.max(SearchQuery.created_at).desc(),
        )
    elif sort_by == "popularity":
        q = q.order_by(
            func.sum(SearchQuery.popularity_score).desc(),
            func.count(SearchQuery.id).desc(),
        )
    elif sort_by == "results":
        q = q.order_by(
            func.sum(SearchQuery.results_count).desc(),
            func.count(SearchQuery.id).desc(),
        )
    else:  # last_seen
        q = q.order_by(
            func.max(SearchQuery.created_at).desc(),
            func.count(SearchQuery.id).desc(),
        )

    rows = q.limit(limit).all()

    return [
        BrandStatItem(
            brand=row.brand,
            category_slug=row.category_slug,
            total_searches=row.total_searches,
            total_results=row.total_results,
            total_popularity=row.total_popularity,
            first_seen=row.first_seen,
            last_seen=row.last_seen,
        )
        for row in rows
    ]

# ===== /search/trends =====

@router.get("/trends", response_model=TrendsOut)
def search_trends(
    period: Literal["week", "month"] = "week",
    limit_queries: int = 10,
    periods_back: int = 4,
    db: Session = Depends(get_db),
):
    """
    Тренды поисковых запросов по периодам.

    - period: "week" или "month"
    - limit_queries: сколько топ-запросов возвращать
    - periods_back: на сколько периодов назад смотреть (недель/месяцев)
    """

    now = datetime.utcnow()

    # определяем стартовую дату с учётом periods_back
    if period == "week":
        # начинаем с начала недели N периодов назад
        start_date = now - timedelta(weeks=periods_back)
        bucket_expr = func.date_trunc("week", SearchQuery.created_at)
    else:  # "month"
        start_date = now - timedelta(days=30 * periods_back)
        bucket_expr = func.date_trunc("month", SearchQuery.created_at)

    # 1) сначала найдём топ normalized_query за период, чтобы не тащить всю базу
    top_rows = (
        db.query(
            SearchQuery.normalized_query,
            func.sum(SearchQuery.popularity).label("score"),
        )
        .filter(SearchQuery.created_at >= start_date)
        .group_by(SearchQuery.normalized_query)
        .order_by(func.sum(SearchQuery.popularity).desc())
        .limit(limit_queries)
        .all()
    )

    if not top_rows:
        # нет данных — возвращаем пустую структуру
        return TrendsOut(period=period, queries=[])

    top_normalized = [r.normalized_query for r in top_rows]

    # 2) агрегируем по периодам только для этих топ-запросов
    agg_rows = (
        db.query(
            SearchQuery.normalized_query.label("normalized_query"),
            bucket_expr.label("bucket_start"),
            func.sum(SearchQuery.popularity).label("total_popularity"),
            func.sum(SearchQuery.results_count).label("total_results"),
        )
        .filter(
            SearchQuery.created_at >= start_date,
            SearchQuery.normalized_query.in_(top_normalized),
        )
        .group_by("normalized_query", "bucket_start")
        .order_by("normalized_query", "bucket_start")
        .all()
    )

    # 3) собираем структуру normalized_query -> [points ...]
    trends_map: Dict[str, List[TrendPointOut]] = {}

    for row in agg_rows:
        nq = row.normalized_query
        if nq not in trends_map:
            trends_map[nq] = []

        trends_map[nq].append(
            TrendPointOut(
                period_start=row.bucket_start,
                total_popularity=row.total_popularity,
                total_results=row.total_results,
            )
        )

    # 4) преобразуем в список QueryTrendOut
    query_trends: List[QueryTrendOut] = []
    for nq, points in trends_map.items():
        # сортируем точки по времени на всякий случай
        points_sorted = sorted(points, key=lambda p: p.period_start)
        query_trends.append(
            QueryTrendOut(
                normalized_query=nq,
                points=points_sorted,
            )
        )

    return TrendsOut(
        period=period,
        queries=query_trends,
    )

@router.get("/brand-trends", response_model=BrandTrendsOut)
def brand_trends(
    period: Literal["week", "month"] = Query("week"),
    category_slug: Optional[str] = Query(
        None,
        description="Slug категории (например, electronics_phones). "
                    "Если не указан — считаем по всем категориям."
    ),
    limit_brands: int = Query(
        20,
        ge=1,
        le=100,
        description="Сколько брендов вернуть в топе."
    ),
    periods_back: int = Query(
        4,
        ge=1,
        le=52,
        description="Сколько периодов назад смотреть (недель или месяцев)."
    ),
    db: Session = Depends(get_db),
):
    """
    Тренды по брендам.

    Аггрегируем поиски по брендам (Apple, Samsung и т.п.) с разбивкой
    по неделям или месяцам.
    """

    # --- вспомогательная функция для начала периода ---
    def get_period_start(dt: datetime) -> datetime:
        dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        if period == "week":
            # понедельник текущей недели
            return dt - timedelta(days=dt.weekday())
        else:
            # первое число месяца
            return dt.replace(day=1)

    # --- определяем с какой даты брать данные ---
    now = datetime.utcnow()
    if period == "week":
        start_date = now - timedelta(weeks=periods_back)
    else:
        # грубо: periods_back месяцев назад
        start_date = now - timedelta(days=30 * periods_back)

    # --- базовый запрос по логам поиска ---
    query = db.query(SearchQuery)

    # фильтруем по дате
    query = query.filter(SearchQuery.created_at >= start_date)

    # фильтр по категории (если передан)
    if category_slug:
        query = (
            query
            .join(Category)
            .filter(Category.slug == category_slug)
        )
    else:
        query = query.outerjoin(Category)

    rows = query.all()

    # если логов нет — возвращаем пустой объект
    if not rows:
        return BrandTrendsOut(period=period, brands=[])

    # --- агрегация по (brand, category_slug, period_start) ---
    # ключ: (brand, category_slug)
    # значение: dict[period_start -> агрегаты]
    buckets: Dict[Tuple[str, Optional[str]], Dict[datetime, dict]] = {}

    for r in rows:
        cat_slug = r.category.slug if r.category else None

        # используем уже существующую функцию детекции бренда
        brand = detect_brand_from_query(r.query, cat_slug)
        if not brand:
            continue  # пропускаем запросы без бренда

        ps = get_period_start(r.created_at)

        key = (brand, cat_slug)
        if key not in buckets:
            buckets[key] = {}

        if ps not in buckets[key]:
            buckets[key][ps] = {
                "total_searches": 0,
                "total_results": 0,
                "total_popularity": 0,
            }

        agg = buckets[key][ps]
        agg["total_searches"] += 1
        agg["total_results"] += r.results_count
        agg["total_popularity"] += r.popularity

    if not buckets:
        return BrandTrendsOut(period=period, brands=[])

    # --- выбираем топ брендов по суммарной популярности ---
    brand_scores: List[Tuple[Tuple[str, Optional[str]], int]] = []
    for key, periods in buckets.items():
        total_popularity = sum(p["total_popularity"] for p in periods.values())
        brand_scores.append((key, total_popularity))

    brand_scores.sort(key=lambda x: x[1], reverse=True)
    top_keys = [k for k, _ in brand_scores[:limit_brands]]

    # --- формируем ответ ---
    brands_out: List[BrandTrendOut] = []

    for (brand, cat_slug) in top_keys:
        periods_dict = buckets[(brand, cat_slug)]
        # сортируем точки по дате
        sorted_points = sorted(periods_dict.items(), key=lambda x: x[0])

        points_out = [
            BrandTrendPointOut(
                period_start=ps,
                total_searches=vals["total_searches"],
                total_results=vals["total_results"],
                total_popularity=vals["total_popularity"],
            )
            for ps, vals in sorted_points
        ]

        brands_out.append(
            BrandTrendOut(
                brand=brand,
                category_slug=cat_slug,
                points=points_out,
            )
        )

    return BrandTrendsOut(
        period=period,
        brands=brands_out,
    )

class AutoKeywordsOut(BaseModel):
    updated_categories: Dict[str, int]  # slug -> сколько слов добавили


@router.get("/analytics/top-models", response_model=List[Dict])
def top_models(
    days: int = Query(30, ge=1, le=365),
    brand: Optional[str] = Query(None),
    category_slug: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=200),
    min_score: float = Query(0.5, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
):
    since = datetime.utcnow() - timedelta(days=days)

    q = db.query(SearchQuery.normalized_query, SearchQuery.category_id).filter(
        SearchQuery.created_at >= since
    )

    if category_slug is not None:
        q = q.join(Category, Category.id == SearchQuery.category_id).filter(Category.slug == category_slug)

    rows = q.all()

    counter = Counter()

    for (normalized_query, _cat_id) in rows:
        if not normalized_query:
            continue

        b, score = extract_brand(normalized_query)
        if not b or score < min_score:
            continue

        if brand is not None and b.lower() != brand.lower():
            continue

        model = extract_model_from_query(normalized_query, b)
        if not model:
            continue

        counter[(b, model)] += 1

    top = counter.most_common(limit)
    return [{"brand": b, "model": m, "count": c} for (b, m), c in top]



@router.post("/auto-keywords", response_model=AutoKeywordsOut)
def auto_keywords(
    category_slug: Optional[str] = None,
    limit_per_category: int = 50,
    min_popularity: int = 1,
    db: Session = Depends(get_db),
):
    """
    Полуавтоматическое пополнение keywords у категорий из search_queries.

    - Если category_slug указан — работаем только по одной категории.
    - Если нет — пробегаем по всем категориям, у которых есть запросы.
    """

    updated: Dict[str, int] = {}

    # Соберём список категорий, по которым есть запросы
    q = db.query(SearchQuery.category_id).filter(SearchQuery.category_id.is_not(None))
    if category_slug:
        cat = db.query(Category).filter(Category.slug == category_slug).first()
        if not cat:
            return AutoKeywordsOut(updated_categories={})
        q = q.filter(SearchQuery.category_id == cat.id)

    category_ids = {row[0] for row in q.distinct().all()}

    if category_slug and category_ids and len(category_ids) == 1:
        categories = [cat]
    else:
        categories = db.query(Category).filter(Category.id.in_(category_ids)).all()

    for cat in categories:
        # Топ запросы по категории
        top_queries = (
            db.query(SearchQuery.normalized_query, SearchQuery.popularity)
            .filter(
                SearchQuery.category_id == cat.id,
                SearchQuery.popularity >= min_popularity,
            )
            .order_by(SearchQuery.popularity.desc())
            .limit(limit_per_category)
            .all()
        )

        if not top_queries:
            continue

        # Текущие keywords
        existing = set()
        if cat.keywords:
            for part in cat.keywords.split(","):
                part = part.strip().lower()
                if part:
                    existing.add(part)

        added = 0
        for nq, pop in top_queries:
            kw = nq.strip().lower()
            if not kw or kw in existing:
                continue
            existing.add(kw)
            added += 1

        if added > 0:
            cat.keywords = ", ".join(sorted(existing))
            updated[cat.slug] = added

    if updated:
        db.commit()

    return AutoKeywordsOut(updated_categories=updated)

@router.post("", response_model=dict)
def search(
    query: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
):
    normalized = query.strip().lower()

    # TODO: здесь должен быть реальный поиск по OLX/источнику
    # results = ...
    # results_count = len(results)
    results_count = 0  # временно, пока не подключил реальный парсер/поиск

    # Ищем существующую запись по нормализованному запросу
    sq = (
        db.query(SearchQuery)
        .filter(SearchQuery.normalized_query == normalized)
        .order_by(SearchQuery.created_at.desc())
        .first()
    )

    if sq:
        sq.popularity = (sq.popularity or 0) + 1
        sq.results_count = results_count
        sq.source = "api"
        sq.query = query  # чтобы сохранить оригинальный ввод (с регистром)
    else:
        sq = SearchQuery(
            query=query,
            normalized_query=normalized,
            results_count=results_count,
            popularity=1,
            source="api",
        )
        db.add(sq)

    db.commit()
    db.refresh(sq)

    return {"query": query, "normalized": normalized, "id": sq.id, "results_count": sq.results_count, "popularity": sq.popularity}

@router.get("/suggestions")
def get_suggestions(
    query: str,
    limit: int = 5,
    db: Session = Depends(get_db),
):
    # Продвинутая нормализация (айф → айфон, ноут → ноутбук и т.д.)
    q_norm = normalize_query_advanced(query)

    items = []

    # 1. Подсказки из прошлых запросов (SearchQuery)
    prev = (
    db.query(SearchQuery)
    .filter(
        SearchQuery.normalized_query.ilike(f"{q_norm}%"),
        SearchQuery.created_at >= cutoff,
    )
    .order_by(
        SearchQuery.popularity.desc(),
        SearchQuery.results_count.desc(),
        SearchQuery.created_at.desc(),
    )
    .limit(limit)
    .all()
    )

    for p in prev:
        if p.normalized_query and p.normalized_query not in items:
            items.append(p.normalized_query)

    # 2. Подсказки из категорий (name / name_ru / slug)
    cats = (
        db.query(Category)
        .filter(
            or_(
                Category.name.ilike(f"%{query}%"),
                Category.name_ru.ilike(f"%{query}%"),
                Category.slug.ilike(f"{q_norm}%"),
                Category.keywords.ilike(f"%{q_norm}%"),
            )
        )
        .limit(limit)
        .all()
    )

    for c in cats:
        name = c.name_ru or c.name
        if name and name not in items:
            items.append(name)

    # 3. AI-подсказки на основе нормализованного ключа
    items = ai_hints(q_norm, items, limit)

    # На всякий случай ещё раз ограничим длину
    items = items[:limit]

    return {"suggestions": items}

class TrainingSample(BaseModel):
    query: str
    normalized_query: str
    category_slug: Optional[str]
    results_count: int
    popularity: int
    created_at: datetime

@router.get(
    "/training-dataset",
    response_model=List[TrainingSampleOut],
)
def training_dataset(
    db: Session = Depends(get_db),
    limit: int = Query(1000, ge=1, le=10000),
    offset: int = 0,
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    min_popularity: int = 0,
    only_with_category: bool = False,
):
    """
    Датасет для обучения ML-моделей.

    Параметры:
    - from_date / to_date — ограничение по дате created_at
    - min_popularity — минимальная популярность запроса
    - only_with_category — брать только те запросы, у которых есть категория
    - limit / offset — пагинация
    """

    q = db.query(SearchQuery)

    if from_date is not None:
        q = q.filter(SearchQuery.created_at >= from_date)

    if to_date is not None:
        q = q.filter(SearchQuery.created_at <= to_date)

    if min_popularity > 0:
        q = q.filter(SearchQuery.popularity >= min_popularity)

    if only_with_category:
        q = q.filter(SearchQuery.category_id.isnot(None))

    rows = (
        q.order_by(SearchQuery.created_at.desc())
         .offset(offset)
         .limit(limit)
         .all()
    )

    return [
        TrainingSampleOut(
            id=r.id,
            query=r.query,
            normalized_query=r.normalized_query,
            category_id=r.category_id,
            category_slug=r.category.slug if r.category else None,
            category_name=r.category.name if r.category else None,
            results_count=r.results_count,
            popularity=r.popularity,
            source=r.source,
            created_at=r.created_at,
        )
        for r in rows
        ]
