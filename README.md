# frogprice 🐸

A frog-art Magic: The Gathering checklist powered by the Scryfall search query `art:frog @@ -is:alchemy`. It uses Scryfall card images and printings only; it does not depend on the old ZIP, the old 344-image list, or the picture-checklist image repository.

## Features

- Pulls every matching printing from Scryfall (`unique=prints`), including separate printings and available foil finishes.
- Card images, card names, set, collector number, rarity and Scryfall links come from Scryfall.
- Greyed-out checklist state with strikethrough when collected. Progress is saved in this browser's local storage.
- Search, collected/missing filters, and sorting by name, set, Cardmarket trend or low price.
- Displays Cardmarket Trend and Low in EUR, with foil guide values shown separately where available.
- Daily GitHub Actions refresh for Scryfall results and Cardmarket's public daily price guide.

## Pricing and matching

The updater joins Scryfall printings to Cardmarket's Magic singles catalogue only when normalized **card name + expansion name + collector number** match exactly and uniquely. It will not guess from card name alone. Unmatched or ambiguous printings display no price.

Cardmarket's downloadable Price Guide is updated daily. Its Trend and Low fields are guide statistics, not a real-time seller-offer feed. The page labels the source date and links to the matched Cardmarket product.

Sources:
- Scryfall search: https://scryfall.com/search?dir=asc&q=art%3Afrog+%40%40+-is%3Aalchemy
- Scryfall API: https://api.scryfall.com
- Cardmarket Magic singles catalogue: https://downloads.s3.cardmarket.com/productCatalog/productList/products_singles_1.json
- Cardmarket Magic daily price guide: https://downloads.s3.cardmarket.com/productCatalog/priceGuide/price_guide_1.json

**Cardmarket terms:** before publicly displaying or redistributing Cardmarket price-guide data, confirm that your intended use complies with Cardmarket's current terms and any permission requirements. Public accessibility of the daily download does not itself establish permission for every reuse.

## Run locally

Requires Python 3.11+.

```bash
python scripts/update_data.py
python -m http.server 8000
```

Open http://localhost:8000.

## GitHub Pages

The workflow refreshes data daily at 06:17 UTC and deploys the static site. In repository Settings → Pages, choose **GitHub Actions** as the build and deployment source. You can also run the workflow manually from the Actions tab.
