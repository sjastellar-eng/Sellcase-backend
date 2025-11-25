import httpx
from bs4 import BeautifulSoup
from typing import Optional, Dict


async def fetch_olx_data(search_url: str) -> Optional[Dict]:
    """
    Загружает HTML страницы OLX, парсит результаты и возвращает статистику.
    """

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(search_url)

        if response.status_code != 200:
            print("HTTP Error:", response.status_code)
            return None

        soup = BeautifulSoup(response.text, "html.parser")

        # Находим блоки объявлений
        items = soup.select("div.css-qfzx1y")  # селектор может измениться в будущем

        prices = []
        for item in items:
            price_el = item.select_one("p.css-wpfvmn-Text")
            if price_el:
                price_text = price_el.get_text(strip=True)
                price_num = extract_price(price_text)
                if price_num:
                    prices.append(price_num)

        if not prices:
            return {
                "items_count": 0,
                "avg_price": 0,
                "min_price": 0,
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
