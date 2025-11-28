# app/services/olx_parser.py

from __future__ import annotations

import re
from typing import Optional, Dict, List

import httpx
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "uk-UA,uk;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _empty_stats(reason: str) -> Dict[str, int]:
    # На будущее: reason будет видно в логах
    print(f"[OLX] return empty stats, reason={reason}")
    return {
        "items_count": 0,
        "avg_price": 0,
        "min_price": 0,
        "max_price": 0,
    }


def extract_price(text: str) -> Optional[int]:
    """
    Извлекает адекватную цену из текста карточки OLX.
    """

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
    В ЛЮБОМ случае возвращает словарь (даже если ничего не распарсили).
    """
    # 1. HTTP-запрос
    try:
        async with httpx.AsyncClient(timeout=20.0, headers=HEADERS) as client:
            resp = await client.get(search_url)
            resp.raise_for_status()
    except httpx.HTTPError as e:
        print(f"[OLX] HTTP error: {e}")
        return _empty_stats("http-error")

    html = resp.text
    soup = BeautifulSoup(html, "html.parser")

    # 2. Находим карточки объявлений
    # Чаще всего: data-cy="l-card"
    cards = soup.select("div[data-cy='l-card']")
    # запасной вариант — вдруг разметка другая
    if not cards:
        cards = soup.select("div[data-testid='l-card']")

    if not cards:
        print("[OLX] No cards found on page")
        return _empty_stats("no-cards")

    prices: list[int] = []

    # 3. Пытаемся достать цену из карточки
    for card in cards:
        # Берём весь текст карточки и вытаскиваем из него число
        text = card.get_text(" ", strip=True)
        value = extract_price(text)
        if value is not None:
            prices.append(value)

    if not prices:
        print("[OLX] No prices parsed from cards")
        return _empty_stats("no-prices")

    # 4. Считаем статистику
    items_count = len(prices)
    min_price = min(prices)
    max_price = max(prices)
    avg_price = round(sum(prices) / items_count, 2)

    return {
        "items_count": items_count,
        "avg_price": avg_price,
        "min_price": min_price,
        "max_price": max_price,
    }

async def fetch_olx_ads(search_url: str, max_pages: int = 3) -> List[Dict]:
    """
    Глубокий парсер: обходит несколько страниц OLX и возвращает список объявлений.
    Формат элемента списка:
    {
        "external_id": "...",
        "title": "...",
        "url": "...",
        "price": 12345,
        "currency": "UAH",
        "seller_id": "...",
        "seller_name": "...",
        "location": "Київ",
        "position": 1,
        "page": 1,
    }
    """
    # нормализуем: мобильная версия всегда редиректит → ломает парсер
    if search_url.startswith("https://m.olx.ua"):
        search_url = search_url.replace("https://m.olx.ua", "https://www.olx.ua")
    results: List[Dict] = []
async with httpx.AsyncClient(
    timeout=20.0,
    headers=HEADERS,
    follow_redirects=False,
) as client:
        for page in range(1, max_pages + 1):
            # --- формируем URL с параметром page ---
            if "page=" in search_url:
                # если в URL уже есть page=, то аккуратно его заменим
                base, _, tail = search_url.partition("page=")
                tail_parts = tail.split("&", 1)
                if len(tail_parts) == 2:
                    # page=<старое>&остальное
                    _, rest = tail_parts
                    page_url = f"{base}page={page}&{rest}"
                else:
                    page_url = f"{base}page={page}"
            else:
                sep = "&" if "?" in search_url else "?"
                page_url = f"{search_url}{sep}page={page}"

            print(f"[OLX_ADS] fetch page={page} url={page_url}")

            # --- HTTP-запрос ---
            try:
                resp = await client.get(page_url)
                resp.raise_for_status()
            except httpx.HTTPError as e:
                print(f"[OLX_ADS] HTTP error on page={page}: {e}")
                # если первая страница упала — просто возвращаем то, что есть
                if page == 1:
                    return results
                break

            html = resp.text
            soup = BeautifulSoup(html, "html.parser")

            # --- карточки объявлений ---

            # 1) основной вариант (по твоим скринам)
            cards = soup.select('div[data-testid="l-card"]')

            # 2) запасной вариант (старый data-cy)
            if not cards:
                cards = soup.select('div[data-cy="l-card"]')

            # 3) ещё один запасной (на случай другой разметки)
            if not cards:
                cards = soup.select(
                    '[data-testid="ad-card"], '
                    '[data-testid="ad-card-container"], '
                    'article[data-testid="listing-grid-item"]'
                )

            if not cards:
                print(f"[OLX_ADS] no cards on page={page} url={page_url}")
                # если на первой странице нет карточек — значит, что-то сильно не так
                if page == 1:
                    return results
                # дальше идти смысла нет
                break

            print(f"[OLX_ADS] cards on page={page}: {len(cards)}")

            for idx, card in enumerate(cards, start=1):
                # --- URL + title ---
                link_el = (
                    card.select_one('[data-cy="ad-card-title"] a')
                    or card.select_one('a[data-testid="ad-title"]')
                    or card.select_one('a[data-testid="title-link"]')
                    or card.select_one("a[href]")
                )

                if not link_el or not link_el.get("href"):
                    continue

                href = link_el.get("href", "")
                title = link_el.get_text(" ", strip=True)

                # нормализуем абсолютный URL
                if href.startswith("//"):
                    url = "https:" + href
                elif href.startswith("/"):
                    url = "https://www.olx.ua" + href
                else:
                    url = href

                # --- external_id из URL ---
                m = re.search(r"-ID([A-Za-z0-9]+)\.html", url)
                if m:
                    external_id = m.group(1)
                else:
                    # fallback: используем сам URL как ID
                    external_id = url

                # --- location ---
                loc_el = (
                    card.select_one('[data-testid="location-date"]')
                    or card.select_one('[data-cy="location-date"]')
                )
                location = None
                if loc_el:
                    loc_text = loc_el.get_text(" ", strip=True)
                    # обычно формат "Київ - Сегодня 12:34"
                    location = loc_text.split("-")[0].strip()

                # --- seller (пока пусто, при желании доработаем позже) ---
                seller_id = None
                seller_name = None

                # --- price ---
                price_el = (
                    card.select_one('span[data-testid="ad-price"]')
                    or card.select_one('[data-testid="ad-price"]')
                    or card.select_one('[data-cy="ad-price"]')
                )
                if price_el:
                    price_text = price_el.get_text(" ", strip=True)
                else:
                    price_text = card.get_text(" ", strip=True)

                price = extract_price(price_text)

                results.append(
                    {
                        "external_id": external_id,
                        "title": title,
                        "url": url,
                        "price": price,
                        "currency": "UAH",
                        "seller_id": seller_id,
                        "seller_name": seller_name,
                        "location": location,
                        "position": idx,  # позиция в выдаче на этой странице
                        "page": page,
                    }
                )

    return results
