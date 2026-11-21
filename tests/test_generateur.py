"""Tests unitaires du générateur : ce sont les « garde-fous » qui empêchent un dataset faux de partir à l'entraînement."""
import random

import cv2
import numpy as np
import pytest

from src.data import generer_formes as g


def une_image(seed):
    return g.generer_image(random.Random(seed), np.random.default_rng(seed))


def test_reproductible():
    img1, obj1 = une_image(123)
    img2, obj2 = une_image(123)
    assert np.array_equal(img1, img2)
    assert obj1 == obj2


def test_graines_differentes_donnent_des_images_differentes():
    assert not np.array_equal(une_image(1)[0], une_image(2)[0])


def test_taille_image():
    img, _ = une_image(5)
    assert img.shape == (g.H, g.W, 3) and img.dtype == np.uint8


@pytest.mark.parametrize("seed", range(40))
def test_boites_valides(seed):
    _, objets = une_image(seed)
    for forme, couleur, (x0, y0, x1, y1) in objets:
        assert forme in g.FORMES
        assert couleur in g.COULEURS
        assert 0 <= x0 < x1 <= g.W and 0 <= y0 < y1 <= g.H
        assert (x1 - x0) >= 12 and (y1 - y0) >= 12


def test_toutes_les_formes_et_couleurs_apparaissent():
    formes, couleurs = set(), set()
    for seed in range(300):
        for f, c, _ in une_image(seed)[1]:
            formes.add(f)
            couleurs.add(c)
    assert formes == set(g.FORMES)
    assert couleurs == set(g.COULEURS)


def _dans_plage(hsv, nom):
    h, s, v = hsv
    return any(h0 <= h <= h1 and s0 <= s <= s1 and v0 <= v <= v1 for (h0, h1), (s0, s1), (v0, v1) in g.COULEURS[nom])


@pytest.mark.parametrize("nom", list(g.COULEURS))
def test_couleurs_non_ambigues(nom):
    """Une couleur générée pour « nom » ne doit appartenir à aucune autre plage : sinon les étiquettes seraient contradictoires."""
    rng = random.Random(0)
    for _ in range(300):
        b, gg, r = g.couleur_aleatoire(nom, rng)
        hsv = tuple(int(x) for x in cv2.cvtColor(np.uint8([[[b, gg, r]]]), cv2.COLOR_BGR2HSV)[0, 0])
        autres = [n for n in g.COULEURS if n != nom and _dans_plage(hsv, n)]
        assert not autres, f"{nom} {hsv} ressemble aussi à {autres}"
