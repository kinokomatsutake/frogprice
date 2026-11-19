#!/usr/bin/env python3
"""Refresh Scryfall frog-art printings and exact Cardmarket daily guide matches."""
import gzip
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUERY = "art:frog @@ -is:alchemy"
SCRYFALL = "https://api.scryfall.com/cards/search"
PRODUCTS_URL = "https://downloads.s3.cardmarket.com/productCatalog/productList/products_singles_1.json"
GUIDE_URL = "https://downloads.s3.cardmarket.com/productCatalog/priceGuide/price_guide_1.json"
MTGJSON_IDENTIFIERS_URL = "https://mtgjson.com/api/v5/AllIdentifiers.json.gz"
HEADERS = {"User-Agent": "frogprice/2.0 (Scryfall frog-art checklist)", "Accept": "application/json"}


def get_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=90) as response:
                return json.load(response)
        except Exception:
            if attempt == 4:
                raise
            time.sleep(2 ** attempt)


def get_gzip_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=180) as response:
                with gzip.GzipFile(fileobj=response) as stream:
                    return json.load(stream)
        except Exception:
            if attempt == 4:
                raise
            time.sleep(2 ** attempt)


def norm(value):
    value = str(value or "").casefold()
    value = value.replace("’", "'").replace("‘", "'")
    return re.sub(r"[^a-z0-9]+", "", value)


def fetch_scryfall():
    cards, url = [], None
    while True:
        if url is None:
            params = urllib.parse.urlencode({"q": QUERY, "unique": "prints", "order": "name", "dir": "asc"})
            url = SCRYFALL + "?" + params
        payload = get_json(url)
        cards.extend(payload.get("data", []))
        if not payload.get("has_more"):
            break
        url = payload.get("next_page")
        time.sleep(0.12)
    result = []
    for card in cards:
        image = card.get("image_uris", {}).get("normal")
        if not image and card.get("card_faces"):
            image = next((face.get("image_uris", {}).get("normal") for face in card["card_faces"] if face.get("image_uris")), None)
        result.append({
            "id": card["id"], "name": card["name"], "set": card.get("set", ""),
            "set_name": card.get("set_name", ""), "collector_number": card.get("collector_number", ""),
            "rarity": card.get("rarity", ""), "released_at": card.get("released_at", ""),
            "finishes": card.get("finishes", []), "image": image,
            "scryfall_uri": card.get("scryfall_uri", ""),
        })
    return result


def price_value(row, *keys):
    for key in keys:
        value = row.get(key)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                pass
    return None


def build_prices(cards):
    # MTGJSON cross-references the exact Scryfall printing UUID to Cardmarket idProduct.
    # Card names and images remain sourced from Scryfall; all prices come from Cardmarket.
    identifier_data = get_gzip_json(MTGJSON_IDENTIFIERS_URL)
    cardmarket_ids = {}
    for record in identifier_data.get("data", {}).values():
        identifiers = record.get("identifiers") or {}
        scryfall_id = identifiers.get("scryfallId")
        mcm_id = identifiers.get("mcmId")
        if scryfall_id and mcm_id:
            cardmarket_ids[str(scryfall_id)] = str(mcm_id)

    guide_data = get_json(GUIDE_URL)
    guides = {
        str(row.get("idProduct")): row
        for row in guide_data.get("priceGuides", [])
        if row.get("idProduct") is not None
    }

    prices = {}
    for card in cards:
        product_id = cardmarket_ids.get(str(card["id"]))
        if not product_id:
            prices[card["id"]] = {
                "matched": False,
                "reason": "no Cardmarket product ID cross-reference for this Scryfall printing",
            }
            continue

        guide = guides.get(product_id)
        if not guide:
            prices[card["id"]] = {
                "matched": False,
                "reason": "Cardmarket product ID found, but no row in the current price guide",
                "product_id": product_id,
                "cardmarket_url": "https://www.cardmarket.com/en/Magic/Products?idProduct=" + product_id,
            }
            continue

        normal = {"trend": price_value(guide, "trend"), "low": price_value(guide, "low")}
        foil = {
            "trend": price_value(guide, "trend-holo", "trend-foil"),
            "low": price_value(guide, "low-holo", "low-foil"),
        }
        prices[card["id"]] = {
            "matched": True,
            "product_id": product_id,
            "match_method": "Scryfall printing UUID to Cardmarket product ID",
            "normal": normal,
            "foil": foil,
            "cardmarket_url": "https://www.cardmarket.com/en/Magic/Products?idProduct=" + product_id,
        }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "price_guide_date": guide_data.get("createdAt", "unknown"),
        "currency": "EUR",
        "prices": prices,
        "source": GUIDE_URL,
        "id_cross_reference": MTGJSON_IDENTIFIERS_URL,
    }


def main():
    cards = fetch_scryfall()
    (ROOT / "cards.json").write_text(json.dumps({
        "query": QUERY, "generated_at": datetime.now(timezone.utc).isoformat(), "cards": cards
    }, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    prices = build_prices(cards)
    (ROOT / "prices.json").write_text(json.dumps(prices, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    matched = sum(1 for item in prices["prices"].values() if item.get("matched"))
    print(f"Updated {len(cards)} Scryfall printings; {matched} Cardmarket product-ID matches.")


if __name__ == "__main__":
    main()
