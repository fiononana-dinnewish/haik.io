"""La palette de l'interface doit être reconnue correctement : sinon une pastille « jaune » serait étiquetée autrement."""
import pytest

from src.couleurs import COULEURS, NOMS, PALETTE_INTERFACE, bgr_vers_hsv, hex_vers_bgr, nommer_couleur


def _plages_contenant(hsv):
    h, s, v = hsv
    return [n for n, plages in COULEURS.items()
            if any(a <= h <= b and c <= s <= d and e <= v <= f for (a, b), (c, d), (e, f) in plages)]


@pytest.mark.parametrize("hexa,attendu", PALETTE_INTERFACE)
def test_pastille_dans_la_bonne_plage_et_seulement_celle_la(hexa, attendu):
    hsv = bgr_vers_hsv(hex_vers_bgr(hexa))
    assert _plages_contenant(hsv) == [attendu], f"{hexa} -> HSV {hsv}"


@pytest.mark.parametrize("hexa,attendu", PALETTE_INTERFACE)
def test_nommer_couleur_palette(hexa, attendu):
    assert nommer_couleur(hex_vers_bgr(hexa)) == attendu


def test_toutes_les_couleurs_ont_une_pastille():
    assert {n for _, n in PALETTE_INTERFACE} == set(NOMS)


@pytest.mark.parametrize("hexa,attendu", [
    ("#ff0000", "rouge"), ("#0000ff", "bleu"), ("#00ff00", "vert"), ("#ffff00", "jaune"),
    ("#000000", "noir"), ("#808080", "gris"), ("#ff8000", "orange"), ("#8b4513", "marron"),
])
def test_couleurs_pures_du_color_picker(hexa, attendu):
    """L'utilisateur peut aussi choisir une couleur libre avec le sélecteur : les couleurs « évidentes » doivent marcher."""
    assert nommer_couleur(hex_vers_bgr(hexa)) == attendu


def _img(fond, dessin):
    import cv2
    import numpy as np
    img = np.full((240, 320, 3), fond, np.uint8)
    dessin(img, cv2)
    return img


@pytest.mark.parametrize("hexa,attendu", PALETTE_INTERFACE[:11])
def test_forme_pleine_et_contour_sur_fond_blanc(hexa, attendu):
    from src.models.couleur import couleur_objet
    bgr = hex_vers_bgr(hexa)
    plein = _img((255, 255, 255), lambda i, cv: cv.circle(i, (160, 120), 50, bgr, -1))
    contour = _img((255, 255, 255), lambda i, cv: cv.rectangle(i, (100, 70), (220, 170), bgr, 6))
    assert couleur_objet(plein, [110, 70, 100, 100])[0] == attendu
    assert couleur_objet(contour, [97, 67, 126, 106])[0] == attendu


def test_forme_blanche_sur_fond_sombre():
    from src.models.couleur import couleur_objet
    img = _img((60, 40, 30), lambda i, cv: cv.circle(i, (160, 120), 50, (255, 255, 255), -1))
    assert couleur_objet(img, [110, 70, 100, 100])[0] == "blanc"
