# app/services/olx_parser.py

from __future__ import annotations

import re
from typing import Optional, Dict, List

import httpx
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
import html as html_lib

import logging

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "DNT": "1",
    "Referer": "https://www.google.com/",
}


def normalize_olx_url(raw_url: str) -> str:
    """
    Принимает ЛЮБУЮ olx-ссылку (desktop/mobile) и возвращает
    нормализованный mobile-URL вида:
    https://m.olx.ua/uk/...

    Правила:
    - http -> https
    - домен -> m.olx.ua
    - /d/uk/... -> /uk/...
    - чистим query: убираем page и utm_*
    """
    if not raw_url:
        return raw_url

    url = raw_url.strip()

    # 1) Всегда https
    if url.startswith("http://"):
        url = "https://" + url[len("http://") :]

    parsed = urlparse(url)
    netloc = (parsed.netloc or "").lower()

    # если вообще не olx — вернём как есть
    if "olx.ua" not in netloc:
        return url

    # 2) Домены -> m.olx.ua
    if netloc in ("olx.ua", "www.olx.ua"):
        netloc = "m.olx.ua"
    elif netloc.endswith(".olx.ua"):
        # beta.olx.ua, m.olx.ua и т.п.
        netloc = "m.olx.ua"
    else:
        netloc = "m.olx.ua"

    # 3) Нормализуем path
    path = parsed.path or "/"
    if path.startswith("/d/uk/"):
        path = path[len("/d") :]  # /d/uk/... -> /uk/...

    # 3.5) Чистим query: выкидываем page и utm_*
    q = []
    for k, v in parse_qsl(parsed.query or "", keep_blank_values=True):
        lk = k.lower()
        if lk == "page":
            continue
        if lk.startswith("utm_"):
            continue
        q.append((k, v))
    clean_query = urlencode(q)

    # 4) Собираем обратно
    return urlunparse(
        (
            "https",
            netloc,
            path,
            parsed.params,
            clean_query,
            parsed.fragment,
        )
    )


def _empty_stats(reason: str) -> Dict[str, int]:
    print(f"[OLX] return empty stats, reason={reason}")
    return {
        "items_count": 0,
        "avg_price": 0,
        "min_price": 0,
        "max_price": 0,
        "median_price": 0,
        "p25_price": 0,
        "p75_price": 0,
    }

def _percentile(sorted_vals: List[int], p: float) -> int:
    """
    p: 0..1 (например 0.25, 0.5, 0.75)
    sorted_vals: уже отсортированный список
    """
    if not sorted_vals:
        return 0
    if len(sorted_vals) == 1:
        return sorted_vals[0]

    # линейная интерполяция
    k = (len(sorted_vals) - 1) * p
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    d0 = sorted_vals[f] * (c - k)
    d1 = sorted_vals[c] * (k - f)
    return int(round(d0 + d1))

def _calc_price_stats(prices: List[int]) -> Dict[str, int]:
    """
    Возвращает расширенную статистику.
    """
    if not prices:
        return {
            "items_count": 0,
            "min_price": 0,
            "max_price": 0,
            "avg_price": 0,
            "median_price": 0,
            "p25_price": 0,
            "p75_price": 0,
        }

    s = sorted(prices)
    items_count = len(s)
    min_price = s[0]
    max_price = s[-1]
    avg_price = int(round(sum(s) / items_count))

    p25 = _percentile(s, 0.25)
    median = _percentile(s, 0.50)
    p75 = _percentile(s, 0.75)

    return {
        "items_count": items_count,
        "min_price": min_price,
        "max_price": max_price,
        "avg_price": avg_price,
        "median_price": median,
        "p25_price": p25,
        "p75_price": p75,
    }

def extract_price(text: str) -> Optional[int]:
    """
    Извлекает адекватную цену из текста карточки OLX.
    """
    if not text:
        return None

    # 1. Ищем число рядом с гривной
    match = re.search(
        r"(\d{1,3}(?:[\s\u00a0]\d{3}){0,3})\s*(?:грн|₴|uah)",
        text,
        flags=re.IGNORECASE,
    )

    if not match:
        # 2. fallback — любое нормальное число (2–7 цифр)
        match = re.search(r"\d{2,7}", text)

    if not match:
        return None

    number_str = match.group(1 if match.lastindex else 0)
    number_str = number_str.replace(" ", "").replace("\u00a0", "")

    try:
        value = int(number_str)
    except ValueError:
        return None

    # 3. фильтруем невозможные значения
    if value < 10 or value > 10_000_000:
        return None

    return value


async def fetch_olx_data(search_url: str) -> Dict[str, int]:
    """
    Забирает страницу поиска OLX и пытается вытащить цены всех объявлений.
    Возвращает словарь с items_count / min / max / avg.
    В ЛЮБОМ случае возвращает словарь (даже если ничего не распарсилось).
    """
    # Нормализуем URL
    search_url = normalize_olx_url(search_url)

    try:
        async with httpx.AsyncClient(
            timeout=20.0,
            headers=HEADERS,
            follow_redirects=True,
        ) as client:
            resp = await client.get(search_url)
            resp.raise_for_status()
    except httpx.HTTPError as e:
        print(f"[OLX] HTTP error: {e}")
        return _empty_stats("http-error")

    html = resp.text
    soup = BeautifulSoup(html, "html.parser")

    # Ищем карточки объявлений
    cards = soup.select('div[data-cy="l-card"]')
    if not cards:
        cards = soup.select('div[data-testid="l-card"]')

    if not cards:
        print("[OLX] No cards found on page")
        return _empty_stats("no-cards")

    prices: List[int] = []

    for card in cards:
        text = card.get_text(" ", strip=True)
        value = extract_price(text)
        if value is not None:
            prices.append(value)

    if not prices:
        print("[OLX] No prices parsed from cards")
        return _empty_stats("no-prices")

    return _calc_price_stats(prices)

# ===== ГЛУБОКИЙ ПАРСЕР ОБЪЯВЛЕНИЙ (для /debug/parse и будущих фич) =====

def _build_page_url(base_search_url: str, page: int) -> str:
    """
    Аккуратно добавляет / заменяет параметр ?page= в URL.
    """
    parsed = urlparse(base_search_url)
    query_list = parse_qsl(parsed.query, keep_blank_values=True)
    query_dict = dict(query_list)

    query_dict["page"] = str(page)

    new_query = urlencode(query_dict)

    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            parsed.fragment,
        )
    )


async def fetch_olx_ads(search_url: str, max_pages: int = 3) -> List[Dict]:
    """
    Глубокий парсер объявлений OLX.

    HTML-вариант: обходит несколько страниц поиска и возвращает список
    объявлений со структурой:

    {
        "external_id": "...",
        "title": "...",
        "url": "...",
        "price": 12345,
        "currency": "UAH",
        "seller_id": "...",
        "seller_name": "...",
        "location": "Київ",
        "position": 1,      # порядковый номер в общем списке
        "page": 1,          # номер страницы
    }
    """
    # 0. Нормализуем ссылку → всегда работаем через mobile-формат
    search_url = normalize_olx_url(search_url)

    results: List[Dict] = []

    async with httpx.AsyncClient(
        timeout=20.0,
        headers=HEADERS,
        follow_redirects=True,
    ) as client:
        for page in range(1, max_pages + 1):
            page_url = _build_page_url(search_url, page)
            print(f"[OLX_ADS_HTML] fetch page={page} url={page_url}")

            # --- грузим HTML ---
            try:
                resp = await client.get(page_url)
                resp.raise_for_status()
            except httpx.HTTPError as e:
                print(f"[OLX_ADS_HTML] http error on page={page}: {e}")
                break

            html = resp.text
            soup = BeautifulSoup(html, "html.parser")

            # --- ищем карточки объявлений ---
            cards = soup.select('div[data-cy="l-card"]')
            if not cards:
                cards = soup.select('div[data-testid="l-card"]')

            if not cards:
                print(f"[OLX_ADS_HTML] no cards on page={page}")
                break

            for card in cards:
                # --- Заголовок / ссылка ---
                link_tag = card.select_one("a[href]")
                title = ""

                # 1) Пытаемся через атрибуты
                title_tag = card.select_one('[data-cy="ad-title"], [data-testid="ad-title"]')
                if title_tag:
                    title = title_tag.get_text(" ", strip=True)

                # 2) Фолбэк: h6/h4/h3
                if not title:
                    h = card.select_one("h6, h4, h3")
                    if h:
                        title = h.get_text(" ", strip=True)

                # 3) Фолбэк: текст ссылки
                if not title and link_tag:
                    title = link_tag.get_text(" ", strip=True)

                # --- URL и external_id ---
                url = ""
                external_id = ""

                if link_tag:
                    href = link_tag.get("href", "")
                    if href.startswith("/"):
                        url = "https://www.olx.ua" + href
                    elif href.startswith("http"):
                        url = href
                    else:
                        url = "https://www.olx.ua/" + href.lstrip("/")

                    m = re.search(r"ID([0-9A-Za-z]+)\.html", href)
                    if not m:
                        m = re.search(r"(\d+)", href)
                    if m:
                        external_id = m.group(1)

    # дальше уже твоя цена/локация и append результата
                # Цена
                price_tag = card.select_one(
                    '[data-testid="ad-price"], [data-cy="ad-price"]'
                )
                if price_tag:
                    price_text = price_tag.get_text(" ", strip=True)
                else:
                    # запасной вариант – весь текст карточки
                    price_text = card.get_text(" ", strip=True)

                price_value = extract_price(price_text) or 0
                currency = "UAH"  # OLX UA

                # Локация
                location_tag = card.select_one(
                    '[data-testid="location-date"], [data-cy="location-date"]'
                )
                location = (
                    location_tag.get_text(" ", strip=True)
                    if location_tag
                    else ""
                )

                # Продавец (пока пустые, можно будет доработать)
                seller_id = ""
                seller_name = ""

                results.append(
                    {
                        "external_id": external_id,
                        "title": title,
                        "url": url,
                        "price": price_value,
                        "currency": currency,
                        "seller_id": seller_id,
                        "seller_name": seller_name,
                        "location": location,
                        "position": len(results) + 1,
                        "page": page,
                    }
                )

    return results
