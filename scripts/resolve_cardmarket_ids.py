#!/usr/bin/env python3
"""OCR gallery cards and resolve exact printings from all pages of Scryfall frog-art search."""
import difflib
import io
import json
import re
import unicodedata
import urllib.parse
import urllib.request
import time
from pathlib import Path

from PIL import Image
import pytesseract

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL_REPO = "https://raw.githubusercontent.com/kinokomatsutake/picture-checklist/main/"
SCRYFALL_SEARCH_URL = "https://api.scryfall.com/cards/search"
SCRYFALL_QUERY = "art:frog ++ @@ -is:alchemy"

def fetch_bytes(url, timeout=90):
    req = urllib.request.Request(url, headers={
        "User-Agent": "frogprice/1.0 (+https://github.com/kinokomatsutake/frogprice)",
        "Accept": "application/json;q=0.9,*/*;q=0.8"
    })
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()

def fetch_json(url, timeout=300):
    return json.loads(fetch_bytes(url, timeout).decode("utf-8"))

def normalize(value):
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(c for c in value if not unicodedata.combining(c))
    return " ".join(re.findall(r"[a-z0-9]+", value.lower()))

def read_card_text(image_bytes):
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    title_crop = image.crop((20, 20, 468, 105)).resize((896, 170))
    footer_crop = image.crop((0, 630, 488, 680)).resize((1464, 150))
    title = pytesseract.image_to_string(title_crop, config="--psm 6")
    footer = pytesseract.image_to_string(footer_crop, config="--psm 6")
    return title, footer

def extract_set_and_number(footer):
    text = (footer or "").upper()
    set_match = re.search(r"\b([A-Z0-9]{3})\s*[*+X-]*\s*(?:EN|JP)\b", text)
    if not set_match:
        return None, None
    prefix = text[:set_match.start()]
    tokens = re.findall(r"(?<![A-Z0-9])([0-9OS]{1,4}[A-Z]?)(?![A-Z0-9])", prefix)
    for token in tokens:
        token = token.replace("O", "0").replace("S", "5")
        digits = re.match(r"([0-9]{1,4})", token)
        if not digits:
            continue
        number = digits.group(1)
        if len(number) == 4 and 1990 <= int(number) <= 2099:
            continue
        suffix = token[len(number):].lower()
        return set_match.group(1), number + suffix
    return set_match.group(1), None

def name_score(card, title_ocr, filename):
    names = [card.get("name", "")]
    names.extend(face.get("name", "") for face in card.get("card_faces", []))
    observed = [normalize(title_ocr), normalize(Path(filename).stem)]
    best = 0.0
    for name in names:
        target = normalize(name)
        if not target:
            continue
        target_tokens = set(target.split())
        for text in observed:
            if not text:
                continue
            text_tokens = set(text.split())
            coverage = len(target_tokens & text_tokens) / len(target_tokens)
            ratio = difflib.SequenceMatcher(None, target, text).ratio()
            best = max(best, coverage, ratio)
    return best

def main():
    images = json.loads((ROOT / "images.json").read_text(encoding="utf-8"))
    mapping_path = ROOT / "cardmarket-mapping.json"
    mapping = json.loads(mapping_path.read_text(encoding="utf-8")) if mapping_path.exists() else {}

    # Search every Scryfall page for the user's exact frog-art query.
    # unique=prints is essential: each set/collector-number printing must remain distinct.
    params = urllib.parse.urlencode({"q": SCRYFALL_QUERY, "unique": "prints", "order": "name"})
    next_url = SCRYFALL_SEARCH_URL + "?" + params
    index = {}
    page_count = 0
    total_cards = None
    while next_url:
        page = fetch_json(next_url, timeout=180)
        page_count += 1
        if total_cards is None:
            total_cards = page.get("total_cards", 0)
        for card in page.get("data", []):
            key = (str(card.get("set", "")).lower(), str(card.get("collector_number", "")).lower())
            index.setdefault(key, []).append(card)
        next_url = page.get("next_page") if page.get("has_more") else None
        if next_url:
            time.sleep(0.12)  # stay comfortably below Scryfall's API rate limit
    print(f"Loaded {sum(map(len, index.values()))} printing records across {page_count} pages (Scryfall total: {total_cards})")

    newly_verified = 0
    unresolved = 0
    for image_path in images:
        if Path(image_path).stem.lower().startswith("zz"):
            unresolved += 1
            continue
        existing = mapping.get(image_path)
        if isinstance(existing, dict) and existing.get("status") == "verified" and existing.get("productId"):
            continue

        encoded_path = urllib.parse.quote(image_path, safe="/")
        try:
            image_bytes = fetch_bytes(ORIGINAL_REPO + encoded_path)
            title_ocr, footer_ocr = read_card_text(image_bytes)
        except Exception as exc:
            print(f"Could not read {image_path}: {exc}")
            unresolved += 1
            continue

        set_code, collector_number = extract_set_and_number(footer_ocr)
        if not set_code or not collector_number:
            unresolved += 1
            continue

        candidates = index.get((set_code.lower(), collector_number.lower()), [])
        ranked = [(name_score(card, title_ocr, image_path), card) for card in candidates]
        ranked = [(score, card) for score, card in ranked if score >= 0.88 and card.get("cardmarket_id")]
        if not ranked:
            unresolved += 1
            continue

        best_score = max(score for score, _ in ranked)
        best_cards = [card for score, card in ranked if score == best_score]
        product_ids = {str(card["cardmarket_id"]) for card in best_cards}
        if len(product_ids) != 1:
            unresolved += 1
            continue

        card = best_cards[0]
        # Only record a standard nonfoil product. Foil-only or etched-only matches stay blank.
        if "nonfoil" not in card.get("finishes", []):
            unresolved += 1
            continue

        product_id = next(iter(product_ids))
        mapping[image_path] = {
            "productId": product_id,
            "status": "verified",
            "finish": "nonfoil",
            "name": card.get("name", ""),
            "expansionName": card.get("set_name", ""),
            "number": card.get("collector_number", ""),
            "printing": f'{card.get("set_name", "")} ({card.get("set", "").upper()}) {card.get("collector_number", "")}'
        }
        newly_verified += 1

    mapping_path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    verified_total = sum(
        1 for value in mapping.values()
        if isinstance(value, dict) and value.get("status") == "verified" and value.get("productId")
    )
    print(f"Newly verified: {newly_verified}; verified total: {verified_total}; left blank: {len(images) - verified_total}")

if __name__ == "__main__":
    main()
