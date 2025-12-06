# seed_categories.py

from sqlalchemy.orm import Session

from app.models import Category

CATEGORY_DATA = [
    # === Транспорт ===
    {
        "slug": "transport",
        "name": "Транспорт",
        "name_ru": "Транспорт",
        "keywords": "транспорт,машины,авто,автомобили,car,cars",
        "parent_slug": None,
    },
    {
        "slug": "transport_cars",
        "name": "Легкові автомобілі",
        "name_ru": "Легковые автомобили",
        "keywords": "авто,легковое авто,машина,sedan,хетчбек,кросовер,suv,авто бу",
        "parent_slug": "transport",
    },
    {
        "slug": "transport_moto",
        "name": "Мотоцикли та мототехніка",
        "name_ru": "Мотоциклы и мототехника",
        "keywords": "мото,мотоцикл,скутер,байк,motorcycle",
        "parent_slug": "transport",
    },
    {
        "slug": "transport_parts",
        "name": "Автозапчастини та аксесуари",
        "name_ru": "Автозапчасти и аксессуары",
        "keywords": "запчасти,автозапчасти,шини,диски,масло для авто,акумулятор,автоаксесуари",
        "parent_slug": "transport",
    },

    # === Нерухомість ===
    {
        "slug": "real_estate",
        "name": "Нерухомість",
        "name_ru": "Недвижимость",
        "keywords": "квартира,квартиры,дом,дача,оренда,аренда,купити квартиру,купить квартиру",
        "parent_slug": None,
    },
    {
        "slug": "real_estate_flats",
        "name": "Квартири",
        "name_ru": "Квартиры",
        "keywords": "квартира,квартири,1к,2к,3к,новобудова,вторичка,оренда квартири",
        "parent_slug": "real_estate",
    },
    {
        "slug": "real_estate_houses",
        "name": "Будинки та дачі",
        "name_ru": "Дома и дачи",
        "keywords": "будинок,дом,дача,котедж,таунхаус,садовий будинок",
        "parent_slug": "real_estate",
    },

    # === Електроніка ===
    {
        "slug": "electronics",
        "name": "Електроніка",
        "name_ru": "Электроника",
        "keywords": "електроніка,электроника,gadgets,гаджеты",
        "parent_slug": None,
    },
    {
        "slug": "electronics_phones",
        "name": "Телефони та смартфони",
        "name_ru": "Телефоны и смартфоны",
        "keywords": "телефон,телефони,смартфон,смартфоны,iphone,айфон,samsung,xiaomi,redmi,oneplus",
        "parent_slug": "electronics",
    },
    {
        "slug": "electronics_laptops",
        "name": "Ноутбуки та компʼютери",
        "name_ru": "Ноутбуки и компьютеры",
        "keywords": "ноутбук,ноутбуки,компʼютер,пк,macbook,imac,ігровий ноутбук",
        "parent_slug": "electronics",
    },

    # === Дім та сад ===
    {
        "slug": "home_garden",
        "name": "Дім та сад",
        "name_ru": "Дом и сад",
        "keywords": "дом,сад,дача,інтерʼєр,дизайн,садові товари",
        "parent_slug": None,
    },
    {
        "slug": "home_garden_furniture",
        "name": "Меблі",
        "name_ru": "Мебель",
        "keywords": "диван,кровать,шафа,стіл,стіл обідній,стул,кухонний гарнітур",
        "parent_slug": "home_garden",
    },

    # === Одяг та взуття ===
    {
        "slug": "fashion",
        "name": "Одяг та взуття",
        "name_ru": "Одежда и обувь",
        "keywords": "одяг,одежда,обувь,взуття,куртка,джинси,кросівки,кроссовки",
        "parent_slug": None,
    },
    {
        "slug": "fashion_men",
        "name": "Чоловічий одяг",
        "name_ru": "Мужская одежда",
        "keywords": "чоловічий одяг,мужская одежда,чоловіча куртка,штани,кофта,свитшот",
        "parent_slug": "fashion",
    },
    {
        "slug": "fashion_women",
        "name": "Жіночий одяг",
        "name_ru": "Женская одежда",
        "keywords": "жіночий одяг,женская одежда,плаття,платье,спідниця,юбка,блузка",
        "parent_slug": "fashion",
    },

    # === Спорт ===
    {
        "slug": "sport",
        "name": "Спорт та відпочинок",
        "name_ru": "Спорт и отдых",
        "keywords": "спорт,спорттовари,туризм,кемпінг,спортзал",
        "parent_slug": None,
    },
    {
        "slug": "sport_fitness",
        "name": "Фітнес та тренажери",
        "name_ru": "Фитнес и тренажёры",
        "keywords": "гантелі,гантели,штанга,тренажер,фітнес резинки,коврик для йоги",
        "parent_slug": "sport",
    },

    # === Послуги ===
    {
        "slug": "services",
        "name": "Послуги",
        "name_ru": "Услуги",
        "keywords": "послуги,услуги,ремонт,доставка,будівельні послуги,сервис",
        "parent_slug": None,
    },
    {
        "slug": "services_repair",
        "name": "Ремонт та будівництво",
        "name_ru": "Ремонт и строительство",
        "keywords": "ремонт квартир,ремонт дома,строительство,отделка,майстер",
        "parent_slug": "services",
    },
]


def seed_categories(db: Session) -> None:
    """Создаёт категории, если их ещё нет."""
    existing = {c.slug: c for c in db.query(Category).all()}

    # сначала создаём / обновляем сами категории
    for item in CATEGORY_DATA:
        slug = item["slug"]
        cat = existing.get(slug)

        if not cat:
            cat = Category(slug=slug)
            db.add(cat)
            existing[slug] = cat

        cat.name = item["name"]
        cat.name_ru = item.get("name_ru")
        cat.keywords = item.get("keywords") or ""

    db.flush()  # чтобы у новых категорий появились id

    # второй проход — расставляем parent_id
    by_slug = existing
    for item in CATEGORY_DATA:
        slug = item["slug"]
        parent_slug = item.get("parent_slug")
        if not parent_slug:
            continue

        cat = by_slug.get(slug)
        parent = by_slug.get(parent_slug)
        if cat and parent:
            cat.parent_id = parent.id

    db.commit()
