import json
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .barcode import checksum_ean_valide, normaliser_code, variantes
from .models import MouvementStock, Produit
from .services import StockInsuffisant, enregistrer_mouvement, trouver_produit
from .templatetags.stock_extras import format_qte


class BarcodeTests(TestCase):
    def test_azerty(self):
        # 3017620422003 tapé par une douchette QWERTY sur un poste AZERTY
        self.assertEqual(normaliser_code("\"à&è-éà'ééàà\""), "3017620422003")

    def test_code_alphanumerique_non_modifie(self):
        self.assertEqual(normaliser_code("AB-12"), "AB-12")
        self.assertEqual(normaliser_code("  123\r\n"), "123")

    def test_variantes_upc_ean(self):
        self.assertIn("0036000291452", variantes("036000291452"))
        self.assertIn("036000291452", variantes("0036000291452"))

    def test_checksum(self):
        self.assertTrue(checksum_ean_valide("3017620422003"))
        self.assertFalse(checksum_ean_valide("3017620422004"))
        self.assertTrue(checksum_ean_valide("ABC"))

    def test_format_qte(self):
        self.assertEqual(format_qte(Decimal("10.000")), "10")
        self.assertEqual(format_qte(Decimal("2.500")), "2.5")


class ServiceTests(TestCase):
    def setUp(self):
        self.p = Produit.objects.create(nom="Farine", code_barre="3017620422003", seuil_alerte=2)

    def test_entree_sortie(self):
        enregistrer_mouvement(self.p, MouvementStock.Type.ENTREE, 10)
        m = enregistrer_mouvement(self.p, MouvementStock.Type.SORTIE, Decimal("2.5"))
        self.p.refresh_from_db()
        self.assertEqual(self.p.quantite, Decimal("7.5"))
        self.assertEqual((m.stock_avant, m.stock_apres), (Decimal("10"), Decimal("7.5")))

    def test_sortie_trop_grande(self):
        enregistrer_mouvement(self.p, MouvementStock.Type.ENTREE, 1)
        with self.assertRaises(StockInsuffisant):
            enregistrer_mouvement(self.p, MouvementStock.Type.SORTIE, 2)
        self.p.refresh_from_db()
        self.assertEqual(self.p.quantite, 1)

    def test_inventaire(self):
        enregistrer_mouvement(self.p, MouvementStock.Type.ENTREE, 10)
        enregistrer_mouvement(self.p, MouvementStock.Type.INVENTAIRE, 8)
        self.p.refresh_from_db()
        self.assertEqual(self.p.quantite, 8)

    def test_peremption_la_plus_proche(self):
        loin, proche = date.today() + timedelta(days=30), date.today() + timedelta(days=5)
        enregistrer_mouvement(self.p, MouvementStock.Type.ENTREE, 5, date_peremption=loin)
        enregistrer_mouvement(self.p, MouvementStock.Type.ENTREE, 5, date_peremption=proche)
        self.p.refresh_from_db()
        self.assertEqual(self.p.date_peremption, proche)
        enregistrer_mouvement(self.p, MouvementStock.Type.SORTIE, 10)
        self.p.refresh_from_db()
        self.assertIsNone(self.p.date_peremption)

    def test_trouver_produit_azerty(self):
        produit, code = trouver_produit("\"à&è-éà'ééàà\"")
        self.assertEqual(produit, self.p)


class ScanApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("chef", password="motdepasse123")
        self.client.force_login(self.user)
        self.p = Produit.objects.create(nom="Lait", code_barre="3017620422003")
        self.url = reverse("stock:scan_api")

    def post(self, **data):
        return self.client.post(self.url, json.dumps(data), content_type="application/json")

    def test_entree_puis_sortie(self):
        r = self.post(code="3017620422003", mode="entree", quantite="6")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["produit"]["quantite"], "6")
        r = self.post(code="3017620422003", mode="sortie", quantite="1")
        self.assertEqual(r.json()["produit"]["quantite"], "5")
        self.assertTrue(MouvementStock.objects.filter(via_scan=True).count() == 2)

    def test_code_inconnu(self):
        r = self.post(code="999", mode="sortie")
        self.assertEqual(r.status_code, 404)
        self.assertTrue(r.json()["inconnu"])
        self.assertIn("code=999", r.json()["url_creation"])

    def test_stock_insuffisant(self):
        r = self.post(code="3017620422003", mode="sortie", quantite="1")
        self.assertEqual(r.status_code, 409)

    def test_annulation(self):
        r = self.post(code="3017620422003", mode="entree", quantite="3")
        mid = r.json()["mouvement_id"]
        r = self.client.post(reverse("stock:annuler_mouvement", args=[mid]))
        self.assertEqual(r.json()["produit"]["quantite"], "0")

    def test_connexion_requise(self):
        self.client.logout()
        r = self.post(code="3017620422003", mode="consulter")
        self.assertEqual(r.status_code, 302)


class PagesTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_user("chef", password="motdepasse123"))
        self.p = Produit.objects.create(nom="Sucre", code_barre="3017620422003")
        enregistrer_mouvement(self.p, MouvementStock.Type.ENTREE, 4)

    def test_pages_s_affichent(self):
        for nom, args in [("dashboard", []), ("produit_list", []), ("produit_create", []),
                          ("produit_detail", [self.p.pk]), ("produit_update", [self.p.pk]),
                          ("mouvement_list", []), ("scan", [])]:
            r = self.client.get(reverse(f"stock:{nom}", args=args))
            self.assertEqual(r.status_code, 200, nom)

    def test_recherche_par_scan_redirige(self):
        r = self.client.get(reverse("stock:produit_list"), {"q": "3017620422003"})
        self.assertRedirects(r, self.p.get_absolute_url())

    def test_creation_code_invalide(self):
        r = self.client.post(reverse("stock:produit_create"), {
            "code_barre": "3017620422004", "nom": "X", "unite": "piece",
            "emplacement": "reserve", "seuil_alerte": "0", "actif": "on",
        })
        self.assertContains(r, "Clé de contrôle EAN invalide")
