from decimal import Decimal

import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Categorie",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nom", models.CharField(max_length=100, unique=True)),
            ],
            options={"verbose_name": "catégorie", "ordering": ["nom"]},
        ),
        migrations.CreateModel(
            name="Produit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nom", models.CharField(max_length=200)),
                ("code_barre", models.CharField(
                    blank=True, help_text="Scannez le produit avec la douchette pour remplir ce champ.",
                    max_length=64, null=True, unique=True, verbose_name="code-barres")),
                ("unite", models.CharField(
                    choices=[("piece", "pièce"), ("kg", "kg"), ("g", "g"), ("L", "L"), ("mL", "mL"),
                             ("boite", "boîte"), ("paquet", "paquet")],
                    default="piece", max_length=10, verbose_name="unité")),
                ("emplacement", models.CharField(
                    choices=[("reserve", "Réserve sèche"), ("frigo", "Chambre froide / frigo"),
                             ("congel", "Congélateur"), ("autre", "Autre")],
                    default="reserve", max_length=10)),
                ("quantite", models.DecimalField(decimal_places=3, default=Decimal("0"), max_digits=12,
                                                 verbose_name="quantité en stock")),
                ("seuil_alerte", models.DecimalField(
                    decimal_places=3, default=Decimal("0"),
                    help_text="Alerte quand le stock est inférieur ou égal à cette valeur.", max_digits=12,
                    validators=[django.core.validators.MinValueValidator(Decimal("0"))],
                    verbose_name="seuil d'alerte")),
                ("prix_unitaire", models.DecimalField(
                    blank=True, decimal_places=3, max_digits=10, null=True,
                    validators=[django.core.validators.MinValueValidator(Decimal("0"))],
                    verbose_name="prix unitaire (TND)")),
                ("date_peremption", models.DateField(blank=True, null=True, verbose_name="prochaine péremption")),
                ("actif", models.BooleanField(default=True)),
                ("cree_le", models.DateTimeField(auto_now_add=True)),
                ("modifie_le", models.DateTimeField(auto_now=True)),
                ("categorie", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="produits", to="stock.categorie", verbose_name="catégorie")),
            ],
            options={
                "ordering": ["nom"],
                "indexes": [models.Index(fields=["nom"], name="produit_nom_idx")],
            },
        ),
        migrations.CreateModel(
            name="MouvementStock",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("type", models.CharField(
                    choices=[("entree", "Entrée (livraison)"), ("sortie", "Sortie (utilisation)"),
                             ("perte", "Perte / casse / périmé"), ("inventaire", "Inventaire (comptage)")],
                    max_length=12)),
                ("quantite", models.DecimalField(
                    decimal_places=3, help_text="Pour un inventaire : la quantité réellement comptée.",
                    max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal("0"))],
                    verbose_name="quantité")),
                ("stock_avant", models.DecimalField(decimal_places=3, max_digits=12)),
                ("stock_apres", models.DecimalField(decimal_places=3, max_digits=12)),
                ("date_peremption", models.DateField(blank=True, null=True, verbose_name="date de péremption")),
                ("note", models.CharField(blank=True, max_length=255)),
                ("via_scan", models.BooleanField(default=False)),
                ("date", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("produit", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT, related_name="mouvements", to="stock.produit")),
                ("utilisateur", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "mouvement de stock",
                "verbose_name_plural": "mouvements de stock",
                "ordering": ["-date", "-id"],
            },
        ),
    ]
