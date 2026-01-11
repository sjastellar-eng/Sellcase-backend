# scripts/seed_suggestions_from_ads.py
import re
from collections import Counter
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import SessionLocal  # или твой get_db / SessionLocal
from app.models import OlxAd, SearchQuery

# Минимальный стоп-лист. Можно расширять.
STOP_WORDS = {
    "куплю", "продам", "продаю", "обмен", "торг", "терміново", "срочно",
    "новый", "нова", "нове", "б/у", "бу", "украина", "україна",
    "доставка", "olx", "олх",
    "грн", "uah", "usd", "дол", "евро", "€", "$",
}

def normalize_text(s: str) -> str:
    s = (s or "").lower().strip()
    # убрать всё кроме букв/цифр/пробелов
    s = re.sub(r"[^0-9a-zа-яёіїєґ\s]+", " ", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def tokenize(s: str) -> list[str]:
    tokens = [t for t in s.split() if t]
    cleaned = []
    for t in tokens:
        if len(t) < 2:
            continue
        if t in STOP_WORDS:
            continue
        # выкидываем чистые "мусор-цифры" (но модели типа 13/14 можно оставить)
        # оставим цифры 2-3 знака (11, 13, 256) — полезно для моделей и памяти
        if t.isdigit() and not (2 <= len(t) <= 3):
            continue
        cleaned.append(t)
    return cleaned

def extract_ngrams(tokens: list[str], max_n: int = 3) -> list[str]:
    grams = []
    L = len(tokens)
    for n in range(1, max_n + 1):
        for i in range(0, L - n + 1):
            g = " ".join(tokens[i:i+n])
            # отсекаем фразы, которые начинаются со стоп-слов (на всякий)
            if g.split()[0] in STOP_WORDS:
                continue
            grams.append(g)
    return grams

def upsert_query(db: Session, query: str, popularity_add: int, source: str = "ads_mining"):
    normalized = query  # уже нормализованный (lower + пробелы)
    sq = (
        db.query(SearchQuery)
        .filter(SearchQuery.normalized_query == normalized)
        .first()
    )
    if sq:
        sq.popularity = (sq.popularity or 0) + popularity_add
        sq.source = source
        # results_count можно не трогать или оставить как есть
    else:
        sq = SearchQuery(
            query=query,
            normalized_query=normalized,
            results_count=0,
            popularity=popularity_add,
            source=source,
        )
        db.add(sq)

def main(days: int = 180, limit_ads: int = 20000, top_phrases: int = 1500):
    db = SessionLocal()
    try:
        since = datetime.utcnow() - timedelta(days=days)

        # Берём заголовки. Если у тебя нет поля first_seen_at, возьми любое доступное
        # Здесь есть first_seen_at в OlxAd (по твоему скрину).
        titles = (
            db.query(OlxAd.title)
            .filter(OlxAd.title.isnot(None))
            .filter(OlxAd.first_seen_at >= since)
            .order_by(OlxAd.first_seen_at.desc())
            .limit(limit_ads)
            .all()
        )

        counter = Counter()

        for (title,) in titles:
            norm = normalize_text(title)
            if not norm:
                continue
            tokens = tokenize(norm)
            if not tokens:
                continue
            grams = extract_ngrams(tokens, max_n=3)
            # Можно ограничить длину фраз чтобы не было "iphone 13 pro max 256"
            grams = [g for g in grams if 2 <= len(g) <= 40]
            counter.update(grams)

        # Отсекаем слишком редкие
        items = [(q, c) for q, c in counter.items() if c >= 3]

        # Берём top
        items.sort(key=lambda x: x[1], reverse=True)
        items = items[:top_phrases]

        for q, c in items:
            upsert_query(db, q, popularity_add=c, source="ads_mining")

        db.commit()
        print(f"OK: added/updated {len(items)} suggestions from ads")
    finally:
        db.close()

if __name__ == "__main__":
    main()
