from django.urls import path

from . import views

app_name = "stock"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("produits/", views.produit_list, name="produit_list"),
    path("produits/nouveau/", views.produit_create, name="produit_create"),
    path("produits/<int:pk>/", views.produit_detail, name="produit_detail"),
    path("produits/<int:pk>/modifier/", views.produit_update, name="produit_update"),
    path("mouvements/", views.mouvement_list, name="mouvement_list"),
    path("mouvements/<int:pk>/annuler/", views.annuler_mouvement, name="annuler_mouvement"),
    path("scan/", views.scan, name="scan"),
    path("api/scan/", views.scan_api, name="scan_api"),
]
