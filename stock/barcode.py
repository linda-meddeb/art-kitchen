"""Normalisation des codes lus par une douchette USB.

Une douchette USB se comporte comme un clavier : elle « tape » le code puis Entrée.
Piège classique : la douchette est configurée en QWERTY alors que le poste est en
AZERTY. Le code 3017620422003 arrive alors sous la forme  "à&é...". On remet donc
les caractères de la rangée des chiffres AZERTY en chiffres.
"""

AZERTY_VERS_CHIFFRES = str.maketrans({
    "&": "1", "é": "2", '"': "3", "'": "4", "(": "5",
    "-": "6", "è": "7", "_": "8", "ç": "9", "à": "0",
})


def normaliser_code(brut: str) -> str:
    """Nettoie un code lu par la douchette (espaces, AZERTY, caractères de contrôle)."""
    if brut is None:
        return ""
    code = "".join(c for c in str(brut) if c.isprintable()).strip()
    # Un code numérique tapé en QWERTY sur un poste AZERTY ne contient AUCUN chiffre,
    # uniquement des symboles de la rangée du haut : on ne convertit que dans ce cas
    # (un vrai code Code128 comme "AB-12" n'est donc pas touché).
    if code and all(c in "&é\"'(-è_çà" for c in code):
        code = code.translate(AZERTY_VERS_CHIFFRES)
    return code


def variantes(code: str) -> list[str]:
    """Formes équivalentes d'un même code (UPC-A 12 chiffres ⇔ EAN-13 commençant par 0)."""
    formes = [code]
    if code.isdigit():
        if len(code) == 12:
            formes.append("0" + code)
        elif len(code) == 13 and code.startswith("0"):
            formes.append(code[1:])
    return formes


def checksum_ean_valide(code: str) -> bool:
    """Vérifie la clé de contrôle d'un EAN-8 / UPC-A / EAN-13. True si format non concerné."""
    if not code.isdigit() or len(code) not in (8, 12, 13):
        return True
    chiffres = [int(c) for c in code]
    cle = chiffres.pop()
    total = sum(d * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(chiffres)))
    return (10 - total % 10) % 10 == cle
