#!/usr/bin/env python3
"""Build prices.json from explicit Cardmarket product-ID mappings."""
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG_URL = "https://downloads.s3.cardmarket.com/productCatalog/productList/products_singles_1.json"
GUIDE_URL = "https://downloads.s3.cardmarket.com/productCatalog/priceGuide/price_guide_1.json"

def fetch_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": "frogprice/1.0"})
    with urllib.request.urlopen(request, timeout=90) as response:
        return json.load(response)

def records(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("products", "priceGuides", "priceGuide", "items", "data"):
            if isinstance(payload.get(key), list):
                return payload[key]
    raise ValueError("Unrecognized Cardmarket JSON structure; refusing to generate prices")

def main():
    mapping = json.loads((ROOT / "cardmarket-mapping.json").read_text(encoding="utf-8"))
    images = json.loads((ROOT / "images.json").read_text(encoding="utf-8"))
    catalog = records(fetch_json(CATALOG_URL))
    guide = records(fetch_json(GUIDE_URL))
    products = {str(p.get("idProduct")): p for p in catalog if p.get("idProduct") is not None}
    guides = {str(p.get("idProduct")): p for p in guide if p.get("idProduct") is not None}
    output = {}
    for path in images:
        entry = mapping.get(path, {})
        pid = str(entry.get("productId", "")) if isinstance(entry, dict) else ""
        product, values = products.get(pid), guides.get(pid)
        verified = bool(entry.get("status") == "verified" and product and values) if isinstance(entry, dict) else False
        if verified:
            foil = entry.get("finish") == "foil"
            average_key, low_key = ("trendFoil", "lowFoil") if foil else ("avg", "low")
            average = values.get(average_key)
            low = values.get(low_key)
            output[path] = {
                "matched": True,
                "productId": int(pid),
                "name": product.get("name"),
                "printing": entry.get("printing", ""),
                "average": average,
                "low": low,
                "currency": "EUR",
                "updatedAt": datetime.now(timezone.utc).isoformat()
            }
        else:
            output[path] = {"matched": False, "name": entry.get("name", "") if isinstance(entry, dict) else ""}
    (ROOT / "prices.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

if __name__ == "__main__":
    main()
