from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.db import get_db
from app import models

router = APIRouter(
    prefix="/search",
    tags=["Search"],
)


def seed_categories_if_empty(db: Session) -> None:
    """Если таблица categories пустая – добавляем несколько базовых категорий."""
    count = db.query(models.Category).count()
    if count > 0:
        return

    seed_data = [
        {
            "name": "Легковые автомобили",
            "slug": "cars",
            "keywords": "авто, машина, легкова, легковая, car, авто бу",
        },
        {
            "name": "Смартфоны",
            "slug": "smartphones",
            "keywords": "телефон, смартфон, iphone, xiaomi, samsung, мобільний",
        },
        {
            "name": "Квартиры (продажа)",
            "slug": "flats_sale",
            "keywords": "квартира, продажа квартиры, купити квартиру, недвижимость",
        },
        {
            "name": "Квартиры (аренда)",
            "slug": "flats_rent",
            "keywords": "квартира, аренда, оренда, довгострокова оренда",
        },
        {
            "name": "Мебель (диваны)",
            "slug": "sofas",
            "keywords": "диван, диваны, sofa, мебель для дома",
        },
        {
            "name": "Животные (собаки)",
            "slug": "dogs",
            "keywords": "собака, собаки, щенок, щенки, пес",
        },
    ]

    for item in seed_data:
        cat = models.Category(
            name=item["name"],
            slug=item["slug"],
            keywords=item["keywords"],
            parent_id=None,
        )
        db.add(cat)

    db.commit()


@router.get(
    "/categories",
    summary="Поиск категорий по названию / ключевым словам",
)
def search_categories(
    query: str = Query(..., min_length=1, description="Поисковая строка, например: авто, iphone, квартира"),
    limit: int = Query(10, ge=1, le=50, description="Максимум результатов"),
    db: Session = Depends(get_db),
) -> List[dict]:
    """
    Ищет категории по полям name/keywords.
    Возвращает массив объектов {id, name, slug}.
    """
    # Автосидинг: если таблица пустая – создаём несколько категорий
    seed_categories_if_empty(db)

    q = f"%{query.lower()}%"

    results = (
        db.query(models.Category)
        .filter(
            or_(
                models.Category.name.ilike(q),
                models.Category.keywords.ilike(q),
            )
        )
        .order_by(models.Category.name.asc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id": c.id,
            "name": c.name,
            "slug": c.slug,
        }
        for c in results
    ]
