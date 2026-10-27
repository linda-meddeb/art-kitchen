# Stock cuisine — gestion de stock avec douchette code-barres (Django)

Application web pour gérer le stock des produits d'une cuisine : entrées (livraisons),
sorties (utilisation), pertes, inventaires, alertes de stock bas et de péremption,
avec une page de **scan rapide** pensée pour une douchette USB.

## Installation

```bash
python -m venv venv
source venv/bin/activate          # Windows : venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py charger_demo     # optionnel : 9 produits de démonstration
python manage.py runserver
```

Ouvrir http://127.0.0.1:8000 et se connecter.

## Fonctionnalités

| Page | Rôle |
|---|---|
| **Tableau de bord** `/` | Nb de produits, stock bas (à commander), péremptions proches, valeur du stock, derniers mouvements |
| **Scanner** `/scan/` | Scan en continu : choisir le mode, scanner, c'est enregistré |
| **Produits** `/produits/` | Liste, recherche par nom **ou par scan** (un scan ouvre directement la fiche), filtres |
| **Fiche produit** | Stock, seuil, DLC, valeur ; ajout manuel d'un mouvement ; historique |
| **Mouvements** `/mouvements/` | Historique complet filtrable |
| **Admin** `/admin/` | Catégories, produits ; mouvements en lecture seule |

### Page de scan

- Modes : **Sortie (F1)**, **Entrée (F2)**, **Perte (F3)**, **Consulter (F4)**.
- Quantité : 1 par défaut. Pour 6 bouteilles d'un coup : taper `6`, Entrée, puis scanner.
  La quantité revient à 1 après chaque scan.
- Code inconnu → bip grave + bouton **« Créer ce produit »** (code pré-rempli, retour au scan après).
- Chaque scan peut être **annulé** depuis le journal (crée le mouvement inverse, l'historique reste juste).
- Le champ code garde toujours le focus, pour que la douchette ne « tape pas dans le vide ».
- Les scans sont traités dans l'ordre même si on scanne très vite.

## La douchette USB

Une douchette USB en mode HID se comporte comme un **clavier** : elle tape le code puis
`Entrée`. Aucun pilote n'est nécessaire. Points gérés par l'application :

- **Clavier AZERTY** : si la douchette est configurée en QWERTY sur un poste AZERTY,
  `3017620422003` arrive sous la forme `"à&è-éà'ééàà"`. Le code est automatiquement reconverti
  (voir `stock/barcode.py`). Le mieux reste de configurer la douchette en AZERTY
  (code de configuration dans son manuel).
- **Suffixe Tab** au lieu d'Entrée : accepté aussi.
- **UPC-A (12 chiffres) / EAN-13** : `036000291452` et `0036000291452` désignent le même produit.
- **Clé de contrôle EAN** vérifiée à la création d'un produit pour éviter les codes mal lus.

## Structure

```
cuisine_stock/          réglages Django (langue fr, fuseau Africa/Tunis)
stock/
  models.py             Categorie, Produit, MouvementStock
  services.py           enregistrer_mouvement() : mise à jour atomique du stock (select_for_update)
  barcode.py            normalisation des codes (AZERTY, UPC/EAN, clé de contrôle)
  views.py              pages + API JSON /api/scan/
  tests.py              18 tests
  management/commands/charger_demo.py
templates/              gabarits HTML
static/stock/           style.css, scan.js
```

Règle importante : **la quantité d'un produit ne se modifie jamais directement** — uniquement
via `enregistrer_mouvement()`. Chaque mouvement garde `stock_avant` / `stock_apres`, ce qui
donne un historique fiable. Une erreur se corrige par un mouvement inverse ou un inventaire.

## API de scan

`POST /api/scan/` (session + jeton CSRF)

```json
{"code": "6190000000019", "mode": "sortie", "quantite": "2"}
```

Réponses : `200` ok, `404` code inconnu (avec `url_creation`), `409` stock insuffisant, `400` requête invalide.

## Tests

```bash
python manage.py test stock
```

## Pistes d'évolution

- Gestion par **lots** (une DLC par livraison, sortie FIFO).
- **Fournisseurs** et bons de commande générés depuis la liste « stock bas ».
- **Recettes / fiches techniques** : une sortie de plat décrémente tous ses ingrédients.
- Impression d'**étiquettes code-barres** maison (Code128) pour les produits sans code.
- Passage à PostgreSQL et déploiement (gunicorn + nginx), `DJANGO_DEBUG=0`, `DJANGO_SECRET_KEY`.
