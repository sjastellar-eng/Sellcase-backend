# app/services/olx_parser.py

from __future__ import annotations

import re
from typing import Optional, Dict, List

import httpx
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urlunparse
import html as html_lib


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
    """

    if not raw_url:
        return raw_url

    url = raw_url.strip()

    # 1. Всегда https
    if url.startswith("http://"):
        url = "https://" + url[len("http://") :]

    parsed = urlparse(url)

    # 2. Приводим домен к m.olx.ua
    netloc = parsed.netloc.lower()

    if "olx.ua" not in netloc:
        # вообще не OLX → возвращаем как есть (на всякий случай)
        return url

    # desktop варианты → в mobile
    if netloc in ("olx.ua", "www.olx.ua"):
        netloc = "m.olx.ua"
    elif netloc.endswith(".olx.ua"):
        # m.olx.ua, beta.olx.ua и т.п. → оставим как есть
        netloc = "m.olx.ua"

    # 3. Нормализуем path:
    # /d/uk/... → /uk/...
    path = parsed.path

    if path.startswith("/d/uk/"):
        path = path[len("/d") :]  # режем только /d → /uk/...

    # Иногда desktop даёт /uk/... — это тоже ок
    # Иногда mobile даёт уже правильный /uk/... — оставляем

    # 4. Собираем обратно
    normalized = urlunparse(
        (
            "https",          # schema
            netloc,           # m.olx.ua
            path,             # /uk/...
            parsed.params,
            parsed.query,
            parsed.fragment,
        )
    )

    return normalized

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
    Глубокий парсер объявлений OLX.
    Новый вариант: вместо HTML-парсинга используем внутренний JSON-API OLX.

    Формат результата:
    [
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
        },
        ...
    ]
    """

    # 0. Нормализуем мобильные ссылки → на www.olx.ua
    if search_url.startswith("https://m.olx.ua"):
        search_url = search_url.replace("https://m.olx.ua", "https://www.olx.ua", 1)
    elif search_url.startswith("http://m.olx.ua"):
        search_url = search_url.replace("http://m.olx.ua", "https://www.olx.ua", 1)

    results: List[Dict] = []

    async with httpx.AsyncClient(
    timeout=20.0,
    headers=HEADERS,
    follow_redirects=True,
) as client:
        # 1. Тянем HTML, чтобы в нём найти URL API
        try:
            html_resp = await client.get(search_url)
            html_resp.raise_for_status()
        except httpx.HTTPError as e:
            print(f"[OLX_API] HTML HTTP error: {e}")
            return results

        html_text = html_resp.text

        # 2. Ищем первую ссылку на /api/v1/offers в исходнике страницы
        api_match = re.search(r"https://[^\"']*/api/v1/offers[^\"']+", html_text)
        if not api_match:
            print("[OLX_API] api url not found in html")
            return results

        api_url_template = html_lib.unescape(api_match.group(0))
        print(f"[OLX_API] found api url: {api_url_template}")

        # 3. Определяем limit и offset, чтобы крутить страницы
        offset_match = re.search(r"(offset=)(\d+)", api_url_template)
        limit_match = re.search(r"(limit=)(\d+)", api_url_template)
        limit = int(limit_match.group(2)) if limit_match else 40

        for page_index in range(max_pages):
            # если в URL уже есть offset=XXX — аккуратно меняем его
            if offset_match:
                new_offset = page_index * limit
                api_url = re.sub(r"(offset=)(\d+)", rf"\1{new_offset}", api_url_template)
            else:
                # offset нет → дергаем только первую страницу
                if page_index > 0:
                    break
                api_url = api_url_template

            page_num = page_index + 1
            print(f"[OLX_API] fetch page={page_num} url={api_url}")

            try:
                api_resp = await client.get(api_url)
            except httpx.HTTPError as e:
                print(f"[OLX_API] api http error: {e}")
                break
            except Exception as e:
                print(f"[OLX_API] api error: {e}")
                break

            if api_resp.status_code != 200:
                print(f"[OLX_API] api status={api_resp.status_code}, stop")
                break

            try:
                data = api_resp.json()
            except ValueError as e:
                print(f"[OLX_API] json parse error: {e}")
                break

            # Структура может немного отличаться на разных страницах → берём максимально мягко
            items = (
                data.get("data", {}).get("items")
                or data.get("data", {}).get("ads")
                or data.get("data", [])
            )

            if not items:
                print("[OLX_API] no items in response, stop")
                break

            for idx_in_page, item in enumerate(items, start=1):
                # ID объявления
                external_id = str(
                    item.get("id")
                    or item.get("ad_id")
                    or item.get("external_id")
                    or ""
                )

                # Заголовок
                title = item.get("title") or ""

                # URL объявления
                url = item.get("url") or item.get("slug") or ""
                if url and url.startswith("/"):
                    url = "https://www.olx.ua" + url

                # Цена
                price_raw = item.get("price") or {}
                price_value = None
                currency = "UAH"

                if isinstance(price_raw, dict):
                    price_value = (
                        price_raw.get("normalized_value")
                        or price_raw.get("value")
                        or price_raw.get("amount")
                    )
                    currency = price_raw.get("currency") or currency

                # Локация
                location_obj = item.get("location") or {}
                location = (
                    location_obj.get("city")
                    or location_obj.get("label")
                    or location_obj.get("name")
                    or ""
                )

                # Продавец (если есть)
                seller_obj = item.get("seller") or {}
                seller_id = seller_obj.get("id") or seller_obj.get("user_id")
                seller_name = seller_obj.get("name") or seller_obj.get("display_name")

                results.append(
                    {
                        "external_id": external_id,
                        "title": title,
                        "url": url,
                        "price": int(price_value) if isinstance(price_value, (int, float)) else None,
                        "currency": currency,
                        "seller_id": seller_id,
                        "seller_name": seller_name,
                        "location": location,
                        "position": len(results) + 1,  # глобальная позиция в выдаче
                        "page": page_num,
                    }
                )

    return results
