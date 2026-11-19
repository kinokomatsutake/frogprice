#!/usr/bin/env python3
"""Refresh Scryfall frog-art printings and exact Cardmarket daily guide matches."""
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
    product_data = get_json(PRODUCTS_URL)
    guide_data = get_json(GUIDE_URL)
    products = product_data.get("products", [])
    guides = {str(x.get("idProduct")): x for x in guide_data.get("priceGuides", []) if x.get("idProduct") is not None}
    # Match using Cardmarket's own product IDs. First try exact normalized
    # name + expansion + collector number; then name + collector number,
    # which often resolves Cardmarket expansion-name spelling differences.
    # When several reprints share a number, compare expansion names and only
    # accept a clear, high-confidence winner. Never assign a guessed ID.
    from difflib import SequenceMatcher

    def number_key(value):
        value = str(value or "").strip().casefold()
        # Cardmarket sometimes formats collector numbers as "123/280".
        value = re.sub(r"/\\d+$", "", value)
        return re.sub(r"[^a-z0-9]+", "", value)

    exact_index, number_index, name_index = {}, {}, {}
    for product in products:
        pname = norm(product.get("name") or product.get("enName"))
        pnum = number_key(product.get("number"))
        pset = norm(product.get("expansionName") or product.get("expansion"))
        if pname:
            name_index.setdefault(pname, []).append(product)
        if pname and pnum:
            number_index.setdefault((pname, pnum), []).append(product)
        if pname and pnum and pset:
            exact_index.setdefault((pname, pset, pnum), []).append(product)

    prices = {}
    for card in cards:
        cname = norm(card["name"])
        cnum = number_key(card["collector_number"])
        cset = norm(card["set_name"])
        exact = exact_index.get((cname, cset, cnum), [])
        candidates = exact if len(exact) == 1 else number_index.get((cname, cnum), [])
        method = "exact name + expansion + collector number"

        if len(candidates) > 1:
            scored = []
            for product in candidates:
                expansion = product.get("expansionName") or product.get("expansion") or ""
                score = SequenceMatcher(None, cset, norm(expansion)).ratio()
                scored.append((score, product))
            scored.sort(key=lambda item: item[0], reverse=True)
            if scored[0][0] >= 0.72 and scored[0][0] - scored[1][0] >= 0.10:
                candidates = [scored[0][1]]
                method = "card name + collector number + clear expansion match"
            else:
                candidates = []

        if len(candidates) != 1 and not exact:
            # A unique catalogue product name is safe only when there is
            # exactly one product for that card in the entire catalogue.
            name_candidates = name_index.get(cname, [])
            if len(name_candidates) == 1:
                candidates = name_candidates
                method = "unique Cardmarket product name"

        if len(candidates) != 1:
            prices[card["id"]] = {
                "matched": False,
                "reason": "no Cardmarket product" if not number_index.get((cname, cnum)) and not name_index.get(cname) else "multiple printings; no unambiguous product ID",
            }
            continue

        product = candidates[0]
        product_id = str(product.get("idProduct", ""))
        guide = guides.get(product_id)
        if not guide:
            prices[card["id"]] = {"matched": False, "reason": "no Cardmarket guide data"}
            continue
        normal = {"trend": price_value(guide, "trend"), "low": price_value(guide, "low")}
        foil = {"trend": price_value(guide, "trend-holo", "trend-foil"), "low": price_value(guide, "low-holo", "low-foil")}
        expansion = product.get("expansionName") or product.get("expansion") or ""
        prices[card["id"]] = {
            "matched": True, "product_id": product_id,
            "match_method": method,
            "printing": str(expansion or "Cardmarket product") + ((" · " + str(product.get("number"))) if product.get("number") else ""),
            "normal": normal, "foil": foil,
            "cardmarket_url": "https://www.cardmarket.com/en/Magic/Products?idProduct=" + product_id,
        }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "price_guide_date": guide_data.get("createdAt", product_data.get("createdAt", "unknown")),
        "currency": "EUR", "prices": prices,
        "source": GUIDE_URL,
    }


def main():
    cards = fetch_scryfall()
    (ROOT / "cards.json").write_text(json.dumps({
        "query": QUERY, "generated_at": datetime.now(timezone.utc).isoformat(), "cards": cards
    }, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    prices = build_prices(cards)
    (ROOT / "prices.json").write_text(json.dumps(prices, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    matched = sum(1 for item in prices["prices"].values() if item.get("matched"))
    print(f"Updated {len(cards)} Scryfall printings; {matched} exact Cardmarket matches.")


if __name__ == "__main__":
    main()
