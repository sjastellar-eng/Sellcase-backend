# app/services/olx_parser.py

from __future__ import annotations

import re
from typing import Optional, Dict, List

import httpx
from bs4 import BeautifulSoup


HEADERS = {
    # маскируемся под обычный браузер
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    ),
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
    cards = soup.select('div[data-cy="l-card"]')

    # запасной вариант — вдруг разметка другая
    if not cards:
        cards = soup.select('div[data-testid="l-card"]')

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
    Формат:
    [
      {
        "external_id": "...",
        "title": "...",
        "url": "...",
        "price": 12345,
        "currency": "UAH",
        "seller_id": "...",
        "seller_name": "...",
        "location": "Київ"
      },
      ...
    ]
    """
    results: List[Dict] = []

    async with httpx.AsyncClient(timeout=20.0, headers=HEADERS) as client:
        for page in range(1, max_pages + 1):
            # аккуратно добавляем &page=, чтобы не ломать существующие параметры
            if "?" in search_url:
                page_url = f"{search_url}&page={page}"
            else:
                page_url = f"{search_url}?page={page}"

            resp = await client.get(page_url)
            if resp.status_code != 200:
                # если на первой странице ошибка — выходим сразу
                if page == 1:
                    return results
                break

            html = resp.text
            soup = BeautifulSoup(html, "html.parser")

        # --- карточки объявлений (как в рабочем fetch_olx_data) ---
        cards = soup.select("div[data-cy='l-card']")
        if not cards:
            cards = soup.select("div[data-testid='l-card']")

        # если и так не нашли — дальше смысла нет
        if not cards:
            # для дебага оставим лог
            print(f"[OLX_ADS] no cards on page={page} url={page_url}")
            if page == 1:
                # на первой странице пусто — просто вернём то, что уже есть
                return results
            break

            for idx, card in enumerate(cards, start=1):
                # --- URL + title ---
                link_el = (
                    card.select_one("[data-cy='ad-card-title'] a")
                    or card.select_one("a")
                )
                if not link_el or not link_el.get("href"):
                    continue

                href = link_el["href"]
                title = link_el.get_text(" ", strip=True)

                # нормализуем абсолютный URL
                if href.startswith("//"):
                    url = "https:" + href
                elif href.startswith("/"):
                    url = "https://www.olx.ua" + href
                else:
                    url = href

                # --- external_id из URL: ищем кусок вида -IDabc123.html ---
                m = re.search(r"-ID([A-Za-z0-9]+)\.html", url)
                if m:
                    external_id = m.group(1)
                else:
                    # fallback: используем сам URL как ID (хуже, но работает)
                    external_id = url

                # --- location ---
                loc_el = card.select_one("[data-testid='location-date']")
                location = None
                if loc_el:
                    loc_text = loc_el.get_text(" ", strip=True)
                    # обычно формат "Київ - Сьогодні 12:34"
                    location = loc_text.split("-")[0].strip()

                # --- seller (если удастся) ---
                seller_id = None
                seller_name = None
                # Можно позже доработать, пока оставим пустым.

                # --- price ---
                price_el = card.select_one("[data-testid='ad-price']")
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
                        "currency": "UAH",  # пока фиксировано, позже можно парсить
                        "seller_id": seller_id,
                        "seller_name": seller_name,
                        "location": location,
                        "position": idx,  # позиция в выдаче на этой странице
                        "page": page,
                    }
                )

    return results
