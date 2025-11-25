# app/services/olx_parser.py

from __future__ import annotations

import re
from typing import Optional, Dict

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
