from django.contrib import admin

from .models import Categorie, MouvementStock, Produit


@admin.register(Categorie)
class CategorieAdmin(admin.ModelAdmin):
    search_fields = ["nom"]


@admin.register(Produit)
class ProduitAdmin(admin.ModelAdmin):
    list_display = ["nom", "code_barre", "categorie", "quantite", "unite", "seuil_alerte",
                    "date_peremption", "actif"]
    list_filter = ["categorie", "emplacement", "actif"]
    search_fields = ["nom", "code_barre"]
    # La quantité ne se modifie que via des mouvements, pour garder l'historique juste
    readonly_fields = ["quantite", "cree_le", "modifie_le"]


@admin.register(MouvementStock)
class MouvementStockAdmin(admin.ModelAdmin):
    list_display = ["date", "produit", "type", "quantite", "stock_avant", "stock_apres",
                    "utilisateur", "via_scan"]
    list_filter = ["type", "via_scan", "date"]
    search_fields = ["produit__nom", "produit__code_barre", "note"]
    date_hierarchy = "date"

    def has_change_permission(self, request, obj=None):
        return False  # un mouvement ne se modifie pas : on l'annule par un mouvement inverse

    def has_add_permission(self, request):
        return False  # passer par l'application pour que le stock soit mis à jour
