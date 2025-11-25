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


async def fetch_olx_data(search_url: str) -> Optional[Dict[str, int]]:
    """
    Забирает страницу поиска OLX и пытается вытащить цены всех объявлений.
    Возвращает словарь с items_count / min / max / avg или None, если ничего
    не удалось распарсить.
    """

    # 1. HTTP-запрос
    try:
        async with httpx.AsyncClient(timeout=20.0, headers=HEADERS) as client:
            resp = await client.get(search_url)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        # в логах Render увидим причину
        print(f"[OLX] HTTP error: {e}")
        return None

    html = resp.text
    soup = BeautifulSoup(html, "html.parser")

    # 2. Находим карточки объявлений
    # На OLX чаще всего карточки имеют data-cy="l-card"
    cards = soup.select('div[data-cy="l-card"]')

    # запасной вариант — вдруг разметка другая
    if not cards:
        cards = soup.select('div[data-testid="l-card"]')

    if not cards:
        print("[OLX] No cards found on page")
        return None

    prices: list[int] = []

    for card in cards:
        # 3. Пытаемся достать элемент с ценой
        price_el = (
            card.select_one('[data-testid="ad-price"]')
            or card.select_one("p[data-testid='ad-price']")
            or card.select_one("span[data-testid='ad-price']")
        )

        text = ""
        if price_el:
            text = price_el.get_text(" ", strip=True)
        else:
            # fallback: смотрим весь текст карточки
            text = card.get_text(" ", strip=True)

        # 4. Вытаскиваем первое «число с пробелами», например "12 500"
        match = re.search(r"\d[\d\s]{1,15}", text)
        if not match:
            continue

        number_str = match.group(0).replace(" ", "").replace("\u00a0", "")
        try:
            value = int(number_str)
        except ValueError:
            continue

        prices.append(value)

    if not prices:
        print("[OLX] No prices parsed from cards")
        return None

    items_count = len(prices)
    min_price = min(prices)
    max_price = max(prices)
    avg_price = sum(prices) // items_count

    return {
        "items_count": items_count,
        "min_price": min_price,
        "max_price": max_price,
        "avg_price": avg_price,
    }                "min_price": 0,
                "max_price": 0,
            }

        return {
            "items_count": len(prices),
            "avg_price": round(sum(prices) / len(prices), 2),
            "min_price": min(prices),
            "max_price": max(prices),
        }

    except Exception as e:
        print("Parse error:", e)
        return None


def extract_price(text: str) -> Optional[int]:
    """
    Извлекает число из строки вида '1 200 грн'.
    """
    digits = "".join(ch for ch in text if ch.isdigit())
    return int(digits) if digits else None
