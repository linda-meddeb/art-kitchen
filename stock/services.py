from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .barcode import normaliser_code, variantes
from .models import MouvementStock, Produit
from .templatetags.stock_extras import format_qte


class StockInsuffisant(Exception):
    def __init__(self, produit, demande):
        self.produit = produit
        self.demande = demande
        super().__init__(
            f"Stock insuffisant pour « {produit} » : {format_qte(produit.quantite)} "
            f"{produit.get_unite_display()} disponible(s), {format_qte(demande)} demandé(s)."
        )


def trouver_produit(code_brut: str):
    """Retrouve un produit à partir d'un code scanné. Renvoie (produit|None, code_normalisé)."""
    code = normaliser_code(code_brut)
    if not code:
        return None, code
    produit = Produit.objects.filter(code_barre__in=variantes(code)).first()
    return produit, code


@transaction.atomic
def enregistrer_mouvement(produit, type_mouvement, quantite, utilisateur=None,
                          note="", date_peremption=None, via_scan=False):
    """Crée un mouvement et met à jour le stock de façon atomique.

    Le produit est verrouillé (select_for_update) pour éviter que deux scans
    simultanés n'écrasent mutuellement le stock.
    """
    quantite = Decimal(str(quantite))
    if quantite < 0:
        raise ValueError("La quantité doit être positive.")
    if quantite == 0 and type_mouvement != MouvementStock.Type.INVENTAIRE:
        raise ValueError("La quantité doit être supérieure à zéro.")

    produit = Produit.objects.select_for_update().get(pk=produit.pk)
    avant = produit.quantite

    if type_mouvement == MouvementStock.Type.ENTREE:
        apres = avant + quantite
    elif type_mouvement in (MouvementStock.Type.SORTIE, MouvementStock.Type.PERTE):
        if quantite > avant:
            raise StockInsuffisant(produit, quantite)
        apres = avant - quantite
    elif type_mouvement == MouvementStock.Type.INVENTAIRE:
        apres = quantite
    else:
        raise ValueError(f"Type de mouvement inconnu : {type_mouvement}")

    # Garder la péremption la plus proche ; repartir de zéro si le stock était vide
    if type_mouvement == MouvementStock.Type.ENTREE and date_peremption:
        if avant <= 0 or not produit.date_peremption or date_peremption < produit.date_peremption:
            produit.date_peremption = date_peremption
    if apres <= 0:
        produit.date_peremption = None

    produit.quantite = apres
    produit.save(update_fields=["quantite", "date_peremption", "modifie_le"])

    return MouvementStock.objects.create(
        produit=produit,
        type=type_mouvement,
        quantite=quantite,
        stock_avant=avant,
        stock_apres=apres,
        date_peremption=date_peremption,
        note=note,
        via_scan=via_scan,
        utilisateur=utilisateur,
        date=timezone.now(),
    )
