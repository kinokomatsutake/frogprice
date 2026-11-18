#!/usr/bin/env python3
"""Build prices.json from exact Cardmarket product-ID mappings."""
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

def records(payload, keys):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in keys:
            if isinstance(payload.get(key), list):
                return payload[key]
    raise ValueError("Unrecognized Cardmarket JSON structure; refusing to generate prices")

def main():
    mapping = json.loads((ROOT / "cardmarket-mapping.json").read_text(encoding="utf-8"))
    images = json.loads((ROOT / "images.json").read_text(encoding="utf-8"))
    catalog = records(fetch_json(CATALOG_URL), ("products", "productList", "items", "data"))
    guide_payload = fetch_json(GUIDE_URL)\n    guide = records(guide_payload, ("priceGuides", "priceGuide", "items", "data"))
    products = {str(p.get("idProduct")): p for p in catalog if p.get("idProduct") is not None}
    guides = {str(p.get("idProduct")): p for p in guide if p.get("idProduct") is not None}
    output = {}
    for path in images:
        entry = mapping.get(path, {})
        pid = str(entry.get("productId", "")) if isinstance(entry, dict) else ""
        product, values = products.get(pid), guides.get(pid)
        verified = bool(isinstance(entry, dict) and entry.get("status") == "verified" and product and values)
        if verified:
            foil = entry.get("finish") == "foil"
            average_key, low_key = ("avg-foil", "low-foil") if foil else ("avg", "low")
            average, low = values.get(average_key), values.get(low_key)
            output[path] = {
                "matched": True, "productId": int(pid),
                "name": product.get("name"), "printing": entry.get("printing", ""),
                "average": average, "low": low, "currency": "EUR",
                "guideDate": guide_payload.get("createdAt") or datetime.now(timezone.utc).isoformat()
            }
        else:
            output[path] = {"matched": False, "name": entry.get("name", "") if isinstance(entry, dict) else ""}
    (ROOT / "prices.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

if __name__ == "__main__":
    guide_payload = {}
    main()
