from django import forms

from .barcode import checksum_ean_valide, normaliser_code
from .models import MouvementStock, Produit


class DateInput(forms.DateInput):
    input_type = "date"


class ProduitForm(forms.ModelForm):
    class Meta:
        model = Produit
        fields = [
            "code_barre", "nom", "categorie", "unite", "emplacement",
            "seuil_alerte", "prix_unitaire", "actif",
        ]
        widgets = {
            "code_barre": forms.TextInput(attrs={
                "autofocus": True, "autocomplete": "off", "class": "champ-scan",
                "placeholder": "Scannez ou tapez le code…",
            }),
        }

    def clean_code_barre(self):
        code = normaliser_code(self.cleaned_data.get("code_barre"))
        if not code:
            return None  # unique=True accepte plusieurs NULL
        if not checksum_ean_valide(code):
            raise forms.ValidationError(
                "Clé de contrôle EAN invalide : le code a probablement été mal lu, rescannez-le."
            )
        return code


class MouvementForm(forms.ModelForm):
    class Meta:
        model = MouvementStock
        fields = ["type", "quantite", "date_peremption", "note"]
        widgets = {"date_peremption": DateInput()}

    def clean(self):
        donnees = super().clean()
        if donnees.get("type") != MouvementStock.Type.ENTREE:
            donnees["date_peremption"] = None
        return donnees
