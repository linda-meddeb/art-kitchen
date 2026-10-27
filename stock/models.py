from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone


class Categorie(models.Model):
    nom = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["nom"]
        verbose_name = "catégorie"

    def __str__(self):
        return self.nom


class Produit(models.Model):
    class Unite(models.TextChoices):
        PIECE = "piece", "pièce"
        KG = "kg", "kg"
        G = "g", "g"
        L = "L", "L"
        ML = "mL", "mL"
        BOITE = "boite", "boîte"
        PAQUET = "paquet", "paquet"

    class Emplacement(models.TextChoices):
        RESERVE = "reserve", "Réserve sèche"
        FRIGO = "frigo", "Chambre froide / frigo"
        CONGEL = "congel", "Congélateur"
        AUTRE = "autre", "Autre"

    nom = models.CharField(max_length=200)
    code_barre = models.CharField(
        "code-barres", max_length=64, unique=True, null=True, blank=True,
        help_text="Scannez le produit avec la douchette pour remplir ce champ.",
    )
    categorie = models.ForeignKey(
        Categorie, on_delete=models.SET_NULL, null=True, blank=True, related_name="produits",
        verbose_name="catégorie",
    )
    unite = models.CharField("unité", max_length=10, choices=Unite.choices, default=Unite.PIECE)
    emplacement = models.CharField(max_length=10, choices=Emplacement.choices, default=Emplacement.RESERVE)
    quantite = models.DecimalField("quantité en stock", max_digits=12, decimal_places=3, default=Decimal("0"))
    seuil_alerte = models.DecimalField(
        "seuil d'alerte", max_digits=12, decimal_places=3, default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Alerte quand le stock est inférieur ou égal à cette valeur.",
    )
    prix_unitaire = models.DecimalField(
        "prix unitaire (TND)", max_digits=10, decimal_places=3, null=True, blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    date_peremption = models.DateField("prochaine péremption", null=True, blank=True)
    actif = models.BooleanField(default=True)
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nom"]
        indexes = [models.Index(fields=["nom"], name="produit_nom_idx")]

    def __str__(self):
        return self.nom

    def get_absolute_url(self):
        return reverse("stock:produit_detail", args=[self.pk])

    @property
    def en_alerte(self):
        return self.quantite <= self.seuil_alerte

    @property
    def perime(self):
        return bool(self.date_peremption and self.date_peremption < timezone.localdate())

    @property
    def bientot_perime(self):
        if not self.date_peremption:
            return False
        limite = timezone.localdate() + timedelta(days=settings.ALERTE_PEREMPTION_JOURS)
        return self.date_peremption <= limite

    @property
    def valeur_stock(self):
        if self.prix_unitaire is None:
            return None
        return self.quantite * self.prix_unitaire


class MouvementStock(models.Model):
    class Type(models.TextChoices):
        ENTREE = "entree", "Entrée (livraison)"
        SORTIE = "sortie", "Sortie (utilisation)"
        PERTE = "perte", "Perte / casse / périmé"
        INVENTAIRE = "inventaire", "Inventaire (comptage)"

    produit = models.ForeignKey(Produit, on_delete=models.PROTECT, related_name="mouvements")
    type = models.CharField(max_length=12, choices=Type.choices)
    quantite = models.DecimalField(
        "quantité", max_digits=12, decimal_places=3,
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Pour un inventaire : la quantité réellement comptée.",
    )
    stock_avant = models.DecimalField(max_digits=12, decimal_places=3)
    stock_apres = models.DecimalField(max_digits=12, decimal_places=3)
    date_peremption = models.DateField("date de péremption", null=True, blank=True)
    note = models.CharField(max_length=255, blank=True)
    via_scan = models.BooleanField(default=False)
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    date = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-date", "-id"]
        verbose_name = "mouvement de stock"
        verbose_name_plural = "mouvements de stock"

    def __str__(self):
        return f"{self.get_type_display()} {self.quantite} {self.produit}"

    @property
    def variation(self):
        return self.stock_apres - self.stock_avant
