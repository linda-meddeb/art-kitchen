import json
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import F, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import MouvementForm, ProduitForm
from .models import Categorie, MouvementStock, Produit
from .services import StockInsuffisant, enregistrer_mouvement, trouver_produit
from .templatetags.stock_extras import format_qte


@login_required
def dashboard(request):
    actifs = Produit.objects.filter(actif=True)
    limite = timezone.localdate() + timedelta(days=settings.ALERTE_PEREMPTION_JOURS)
    valeur = actifs.filter(prix_unitaire__isnull=False).aggregate(
        total=Sum(F("quantite") * F("prix_unitaire"))
    )["total"]
    contexte = {
        "nb_produits": actifs.count(),
        "alertes": actifs.filter(quantite__lte=F("seuil_alerte")).select_related("categorie")[:20],
        "peremptions": actifs.filter(date_peremption__lte=limite, quantite__gt=0)
                             .order_by("date_peremption")[:20],
        "derniers": MouvementStock.objects.select_related("produit", "utilisateur")[:10],
        "valeur_stock": valeur,
    }
    return render(request, "stock/dashboard.html", contexte)


@login_required
def produit_list(request):
    qs = Produit.objects.select_related("categorie")
    q = request.GET.get("q", "").strip()
    if q:
        produit, code = trouver_produit(q)
        if produit:  # scan direct dans la recherche → fiche produit
            return redirect(produit)
        qs = qs.filter(Q(nom__icontains=q) | Q(code_barre__icontains=code))
    categorie = request.GET.get("categorie")
    if categorie:
        qs = qs.filter(categorie_id=categorie)
    if request.GET.get("alerte"):
        qs = qs.filter(quantite__lte=F("seuil_alerte"))
    if not request.GET.get("inactifs"):
        qs = qs.filter(actif=True)
    page = Paginator(qs, 50).get_page(request.GET.get("page"))
    return render(request, "stock/produit_list.html", {
        "page": page, "q": q, "categories": Categorie.objects.all(),
        "categorie": categorie,
    })


@login_required
def produit_create(request):
    initial = {}
    if request.GET.get("code"):
        initial["code_barre"] = request.GET["code"]
    form = ProduitForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        produit = form.save()
        messages.success(request, f"Produit « {produit} » créé.")
        retour = request.POST.get("retour")
        if retour == "scan":
            return redirect("stock:scan")
        return redirect(produit)
    return render(request, "stock/produit_form.html", {
        "form": form, "titre": "Nouveau produit", "retour": request.GET.get("retour", ""),
    })


@login_required
def produit_update(request, pk):
    produit = get_object_or_404(Produit, pk=pk)
    form = ProduitForm(request.POST or None, instance=produit)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Produit mis à jour.")
        return redirect(produit)
    return render(request, "stock/produit_form.html", {
        "form": form, "titre": f"Modifier « {produit} »", "produit": produit,
    })


@login_required
def produit_detail(request, pk):
    produit = get_object_or_404(Produit.objects.select_related("categorie"), pk=pk)
    form = MouvementForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            enregistrer_mouvement(
                produit, form.cleaned_data["type"], form.cleaned_data["quantite"],
                utilisateur=request.user, note=form.cleaned_data["note"],
                date_peremption=form.cleaned_data["date_peremption"],
            )
            messages.success(request, "Mouvement enregistré.")
            return redirect(produit)
        except (StockInsuffisant, ValueError) as e:
            form.add_error("quantite", str(e))
    mouvements = produit.mouvements.select_related("utilisateur")[:50]
    return render(request, "stock/produit_detail.html", {
        "produit": produit, "form": form, "mouvements": mouvements,
    })


@login_required
def mouvement_list(request):
    qs = MouvementStock.objects.select_related("produit", "utilisateur")
    type_ = request.GET.get("type")
    if type_:
        qs = qs.filter(type=type_)
    page = Paginator(qs, 50).get_page(request.GET.get("page"))
    return render(request, "stock/mouvement_list.html", {
        "page": page, "types": MouvementStock.Type.choices, "type": type_,
    })


@login_required
def scan(request):
    return render(request, "stock/scan.html", {"types": MouvementStock.Type.choices})


def _produit_json(produit):
    return {
        "id": produit.pk,
        "nom": produit.nom,
        "code_barre": produit.code_barre,
        "quantite": format_qte(produit.quantite),
        "unite": produit.get_unite_display(),
        "en_alerte": produit.en_alerte,
        "date_peremption": produit.date_peremption.isoformat() if produit.date_peremption else None,
        "url": produit.get_absolute_url(),
    }


@login_required
@require_POST
def scan_api(request):
    """Reçoit un scan : {"code": "...", "mode": "entree|sortie|perte|consulter", "quantite": "1"}."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "erreur": "Requête invalide."}, status=400)

    produit, code = trouver_produit(data.get("code", ""))
    if not code:
        return JsonResponse({"ok": False, "erreur": "Code vide."}, status=400)
    if produit is None:
        return JsonResponse({
            "ok": False, "inconnu": True, "code": code,
            "erreur": f"Code {code} inconnu.",
            "url_creation": reverse("stock:produit_create") + f"?code={code}&retour=scan",
        }, status=404)

    mode = data.get("mode", "consulter")
    if mode == "consulter":
        return JsonResponse({"ok": True, "mode": mode, "produit": _produit_json(produit)})

    if mode not in (MouvementStock.Type.ENTREE, MouvementStock.Type.SORTIE, MouvementStock.Type.PERTE):
        return JsonResponse({"ok": False, "erreur": "Mode inconnu."}, status=400)
    try:
        quantite = Decimal(str(data.get("quantite", "1")).replace(",", "."))
    except InvalidOperation:
        return JsonResponse({"ok": False, "erreur": "Quantité invalide."}, status=400)

    try:
        mouvement = enregistrer_mouvement(
            produit, mode, quantite, utilisateur=request.user, via_scan=True,
        )
    except StockInsuffisant as e:
        return JsonResponse({"ok": False, "erreur": str(e), "produit": _produit_json(produit)}, status=409)
    except ValueError as e:
        return JsonResponse({"ok": False, "erreur": str(e)}, status=400)

    return JsonResponse({
        "ok": True, "mode": mode, "mouvement_id": mouvement.pk,
        "quantite": format_qte(quantite),
        "produit": _produit_json(mouvement.produit),
    })


@login_required
@require_POST
def annuler_mouvement(request, pk):
    """Annule un mouvement fait par scan (erreur de manip) en créant le mouvement inverse."""
    m = get_object_or_404(MouvementStock, pk=pk)
    inverse = {
        MouvementStock.Type.ENTREE: MouvementStock.Type.SORTIE,
        MouvementStock.Type.SORTIE: MouvementStock.Type.ENTREE,
        MouvementStock.Type.PERTE: MouvementStock.Type.ENTREE,
    }.get(m.type)
    if inverse is None:
        return JsonResponse({"ok": False, "erreur": "Un inventaire ne s'annule pas."}, status=400)
    try:
        enregistrer_mouvement(
            m.produit, inverse, m.quantite, utilisateur=request.user,
            note=f"Annulation du mouvement #{m.pk}",
        )
    except StockInsuffisant as e:
        return JsonResponse({"ok": False, "erreur": str(e)}, status=409)
    m.produit.refresh_from_db()
    return JsonResponse({"ok": True, "produit": _produit_json(m.produit)})
