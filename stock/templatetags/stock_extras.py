from decimal import Decimal

from django import template

register = template.Library()


def format_qte(valeur) -> str:
    """10.000 → "10", 2.500 → "2.5" (évite le "1E+1" de Decimal.normalize())."""
    if valeur is None:
        return ""
    d = Decimal(valeur).normalize()
    return format(d, "f")


@register.filter
def qte(valeur):
    return format_qte(valeur)
