
from __future__ import annotations

import re
import json
from typing import List, Dict
import httpx
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9,uk;q=0.8",
}

def extract_price(text: str):
    if not text:
        return 0
    m = re.search(r"(\d[\d\s]{1,8})\s*(грн|₴|uah)?", text.lower())
    if not m:
        return 0
    n = m.group(1).replace(" ", "")
    try:
        return int(n)
    except:
        return 0


async def fetch_olx_ads(search_url: str, max_pages: int = 1) -> List[Dict]:
    results = []

    async with httpx.AsyncClient(headers=HEADERS, timeout=20) as client:
        for page in range(1, max_pages + 1):

            url = search_url
            if page > 1:
                if "?" in url:
                    url += f"&page={page}"
                else:
                    url += f"?page={page}"

            r = await client.get(url)
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

            # Navigate JSON safely
            offers = []
            try:
                offers = data["listing"]["items"]
            except:
                pass

            for item in offers:

                title = item.get("title", "")
                url = item.get("url", "")
                price = 0

                price_obj = item.get("price", {})
                if isinstance(price_obj, dict):
                    price = price_obj.get("value", 0)

                location = ""
                loc = item.get("location", {})
                if isinstance(loc, dict):
                    location = loc.get("cityName", "")

                external_id = str(item.get("id", ""))

                results.append({
                    "external_id": external_id,
                    "title": title,
                    "url": url,
                    "price": price,
                    "currency": "UAH",
                    "location": location,
                    "position": len(results) + 1,
                    "page": page
                })

    return results
