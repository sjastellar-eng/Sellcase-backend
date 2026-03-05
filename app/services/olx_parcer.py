import httpx
import json
import re
from bs4 import BeautifulSoup


BASE_URL = "https://www.olx.ua"


async def fetch_olx_ads(search_url: str, max_pages: int = 1):

    results = []

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }

    async with httpx.AsyncClient(headers=headers, timeout=30) as client:

        for page in range(1, max_pages + 1):

            if page == 1:
                url = search_url
            else:
                if "?" in search_url:
                    url = f"{search_url}&page={page}"
                else:
                    url = f"{search_url}?page={page}"

            try:

                r = await client.get(url)

                if r.status_code != 200:
                    continue

                html = r.text

                soup = BeautifulSoup(html, "html.parser")

                script = None

                for s in soup.find_all("script"):
                    if "__PRERENDERED_STATE__" in s.text:
                        script = s.text
                        break

                if not script:
                    continue

                json_text = re.search(
                    r"__PRERENDERED_STATE__\s*=\s*(\{.*?\})\s*;",
                    script,
                    re.S
                )

                if not json_text:
                    continue

                data = json.loads(json_text.group(1))

                offers = data.get("listing", {}).get("ads", {}).get("items", [])

                for item in offers:

                    title = item.get("title")

                    price = None
                    if item.get("price"):
                        price = item.get("price", {}).get("value")

                    url = item.get("url")

                    results.append({
                        "title": title,
                        "price": price,
                        "url": BASE_URL + url if url else None
                    })

            except Exception:
                continue

    return results


async def fetch_olx_data(search_url: str):

    ads = await fetch_olx_ads(search_url, max_pages=1)

    prices = []

    for ad in ads:
        price = ad.get("price")
        if isinstance(price, (int, float)):
            prices.append(price)

    if not prices:
        return {
            "items_count": 0,
            "min_price": 0,
            "max_price": 0,
            "avg_price": 0
        }

    return {
        "items_count": len(prices),
        "min_price": min(prices),
        "max_price": max(prices),
        "avg_price": int(sum(prices) / len(prices))
                      }
