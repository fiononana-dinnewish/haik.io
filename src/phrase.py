"""Construit la phrase française affichée par l'interface à partir des objets détectés (POST /decrire)."""

_FEMININ = {"etoile"}                       # tous les autres noms de formes sont masculins
_AFFICHAGE = {"carre": "carré", "etoile": "étoile", "losange": "losange", "pentagone": "pentagone", "hexagone": "hexagone"}
# accord de la couleur avec le genre : « une étoile rose », « un cercle rose » ; invariables : orange, marron, rose
_COULEUR_FEM = {"blanc": "blanche", "noir": "noire", "vert": "verte", "violet": "violette", "gris": "grise",
                "bleu": "bleue", "jaune": "jaune", "rouge": "rouge", "cyan": "cyan", "orange": "orange",
                "marron": "marron", "rose": "rose"}
_NOMBRES = {2: "deux", 3: "trois", 4: "quatre", 5: "cinq", 6: "six", 7: "sept", 8: "huit", 9: "neuf", 10: "dix"}


def _un(forme, couleur):
    nom = _AFFICHAGE.get(forme, forme)
    fem = forme in _FEMININ
    adj = _COULEUR_FEM.get(couleur, couleur) if fem else couleur
    return ("une " if fem else "un ") + nom + (f" {adj}" if adj else "")


def decrire(objets) -> str:
    if not objets:
        return "Je ne vois aucune forme."
    groupes = {}
    for o in objets:
        groupes.setdefault((o.get("forme", ""), o.get("couleur", "")), 0)
        groupes[(o.get("forme", ""), o.get("couleur", ""))] += 1
    morceaux = []
    for (forme, couleur), n in groupes.items():
        if n == 1:
            morceaux.append(_un(forme, couleur))
        else:
            nom = _AFFICHAGE.get(forme, forme)
            pluriel = nom if nom.endswith(("s", "x")) else nom + "s"
            fem = forme in _FEMININ
            adj = _COULEUR_FEM.get(couleur, couleur) if fem else couleur
            if adj and adj not in ("orange", "marron", "rose", "cyan") and not adj.endswith(("s", "x")):
                adj += "s"
            morceaux.append(f"{_NOMBRES.get(n, n)} {pluriel}" + (f" {adj}" if adj else ""))
    texte = morceaux[0] if len(morceaux) == 1 else ", ".join(morceaux[:-1]) + " et " + morceaux[-1]
    return ("Je vois " + texte + ".")
