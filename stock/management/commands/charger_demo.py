from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from stock.models import Categorie, MouvementStock, Produit
from stock.services import enregistrer_mouvement

# (nom, code EAN fictif (clé valide), catégorie, unité, emplacement, seuil, prix, stock, DLC dans N jours)
PRODUITS = [
    ("Farine T55 1 kg", "6190000000019", "Épicerie", "paquet", "reserve", 5, "1.450", 12, None),
    ("Huile d'olive 1 L", "6190000000026", "Épicerie", "L", "reserve", 3, "18.500", 8, None),
    ("Sucre 1 kg", "6190000000033", "Épicerie", "paquet", "reserve", 4, "1.300", 2, None),
    ("Lait demi-écrémé 1 L", "6190000000040", "Frais", "L", "frigo", 6, "1.400", 10, 2),
    ("Beurre 200 g", "6190000000057", "Frais", "piece", "frigo", 4, "4.200", 3, 10),
    ("Crème fraîche 20 cl", "6190000000064", "Frais", "piece", "frigo", 4, "2.100", 6, -1),
    ("Harissa 380 g", "6190000000071", "Conserves", "boite", "reserve", 2, "2.900", 9, None),
    ("Concentré de tomate 800 g", "6190000000088", "Conserves", "boite", "reserve", 3, "4.600", 7, None),
    ("Petits pois surgelés 1 kg", "6190000000095", "Surgelés", "paquet", "congel", 2, "5.200", 4, 90),
]


class Command(BaseCommand):
    help = "Charge quelques produits de démonstration (codes-barres fictifs)."

    def handle(self, *args, **opts):
        aujourd_hui = timezone.localdate()
        for nom, code, cat, unite, empl, seuil, prix, stock, dlc in PRODUITS:
            categorie, _ = Categorie.objects.get_or_create(nom=cat)
            produit, cree = Produit.objects.get_or_create(code_barre=code, defaults=dict(
                nom=nom, categorie=categorie, unite=unite, emplacement=empl,
                seuil_alerte=seuil, prix_unitaire=Decimal(prix),
            ))
            if cree:
                enregistrer_mouvement(
                    produit, MouvementStock.Type.ENTREE, stock, note="Stock initial (démo)",
                    date_peremption=aujourd_hui + timedelta(days=dlc) if dlc is not None else None,
                )
        self.stdout.write(self.style.SUCCESS(f"{len(PRODUITS)} produits de démo prêts."))
