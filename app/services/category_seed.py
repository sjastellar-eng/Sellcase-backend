from app.models import Category
from sqlalchemy.orm import Session


DEFAULT_CATEGORIES = [
    {"name": "Авто", "slug": "auto", "keywords": "авто,машина,автомобиль,car"},
    {"name": "Телефоны", "slug": "phones", "keywords": "iphone,телефон,apple,samsung,смартфон"},
    {"name": "Квартиры", "slug": "apartments", "keywords": "квартира,аренда,комната,жилье"},
    {"name": "Ноутбуки", "slug": "laptops", "keywords": "ноутбук,laptop,macbook,ultrabook,пк"},
    {"name": "Телевизоры", "slug": "tv", "keywords": "телевизор,tv,smart tv,жк тв"},
]


def seed_categories(db: Session):
    count = db.query(Category).count()
    if count > 0:
        return  # Уже заполнено

    for item in DEFAULT_CATEGORIES:
        db.add(Category(**item))

    db.commit()
