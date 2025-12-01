import csv
import io
from typing import List, Dict, Any

CSV_FIELDS = [
    "external_id", "title", "url", "price", "currency",
    "seller_id", "seller_name", "location", "position", "page"
]

def rows_to_csv(rows: List[Dict[str, Any]]) -> bytes:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    return buf.getvalue().encode("utf-8-sig")  # с BOM для Excel
