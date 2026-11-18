# frogprice

A small GitHub Pages gallery that displays Cardmarket Price Guide **Average** and **Low** values for explicitly matched Magic: The Gathering printings.

## Data model

- `images.json`: relative image paths shown in the gallery.
- `cardmarket-mapping.json`: explicit per-image Cardmarket product IDs. This is intentionally not guessed from card names.
- `prices.json`: generated daily from Cardmarket's public product catalogue and price guide downloads.

Prices are shown in EUR and labelled as guide values, not live offers. Alternate-art files can have their own product IDs when Cardmarket lists them separately. Unverified mappings remain marked as unmatched.

## Add your images

Place the 344 WebP files in `images/` and list their paths in `images.json`. The 344 image paths from the original checklist are already in `images.json`. The gallery loads the corresponding WebP assets directly from the untouched `kinokomatsutake/picture-checklist` repository, so this new repository does not duplicate or modify those image files.

## Add exact printing mappings

For each verified image, add an entry to `cardmarket-mapping.json`:

```json
{
  "images/Card Name.webp": {
    "productId": 123456,
    "printing": "Set name · collector number",
    "finish": "normal",
    "status": "verified"
  }
}
```

Use the Cardmarket product ID for the exact printing/product. Use `finish: "foil"` for foil guide fields. Do not map a card by name alone when multiple printings exist. For alternate-art assets, use a separate product ID only when that exact Cardmarket product is identified.

## Run locally

Requires Python 3.11+.

```bash
python scripts/update_prices.py
python -m http.server 8000
```

Open http://localhost:8000.

## GitHub Pages

In repository Settings → Pages, select **GitHub Actions** as the build and deployment source. The included workflow publishes the repository root and refreshes the price data daily.

## Cardmarket data

The workflow downloads Cardmarket's public Magic product catalogue and daily price guide:

- https://downloads.s3.cardmarket.com/productCatalog/productList/products_singles_1.json
- https://downloads.s3.cardmarket.com/productCatalog/priceGuide/price_guide_1.json

Public display of Cardmarket data is subject to Cardmarket's terms and any permission/consent granted by Cardmarket. Keep your written permission on file.

## Matching status

No card prices are considered verified until an exact Cardmarket product ID is entered in `cardmarket-mapping.json`. Missing mappings display as **Not matched** rather than showing a potentially incorrect price.
