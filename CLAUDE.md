# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Django 5.1 app (French UI, code and comments in French) for kitchen stock management with USB barcode-scanner support. SQLite database, single app `stock`, project settings in `cuisine_stock/`.

## Commands

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py charger_demo        # optional: loads 9 demo products
python manage.py runserver
python manage.py test stock          # all tests (stock/tests.py)
python manage.py test stock.tests.ServiceTests.test_xxx   # single test
```

No linter is configured. Production uses env vars `DJANGO_DEBUG=0` and `DJANGO_SECRET_KEY`.

## Architecture

- **Stock invariant**: `Produit.quantite` must never be modified directly. All changes go through `stock.services.enregistrer_mouvement()`, which locks the product (`select_for_update`) inside a transaction, computes the new quantity per movement type (entrée / sortie / perte / inventaire, where inventaire = absolute counted quantity), maintains the nearest `date_peremption`, and writes a `MouvementStock` with `stock_avant`/`stock_apres`. Insufficient stock raises `StockInsuffisant`.
- **Corrections**: mistakes are fixed by an inverse movement (see `annuler_mouvement` view) or an inventory, never by editing/deleting history (movements are read-only in admin, `PROTECT` FK on product).
- **Barcode handling** (`stock/barcode.py`): `normaliser_code` converts QWERTY-on-AZERTY scanner output back to digits and strips Enter/Tab suffixes; `variantes` makes UPC-A (12) and EAN-13 (13) match the same product; `checksum_ean_valide` is checked on product creation. Always look products up via `services.trouver_produit()` rather than raw `code_barre` queries.
- **Scan flow**: `static/stock/scan.js` + `templates/stock/scan.html` post to `POST /api/scan/` (`views.scan_api`, session + CSRF). Status codes carry meaning: 200 ok, 404 unknown code (response includes `url_creation`), 409 insufficient stock, 400 invalid request. Scans are queued client-side to be processed in order; the code input must always keep focus.
- Settings of note: `ALERTE_PEREMPTION_JOURS` (expiry alert window), language `fr`, timezone `Africa/Tunis`, prices in TND. Quantities are `Decimal` with 3 decimals; use the `format_qte` template filter/function for display.
- All views are `@login_required`; `produit_list` search redirects straight to the product page when the query is a scanned barcode.
