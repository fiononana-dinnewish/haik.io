"""
Définition UNIQUE des couleurs de Haik.io (utilisée par le générateur de dataset ET par le classifieur de couleur).

Chaque couleur = une ou plusieurs plages HSV OpenCV (H 0-179, S 0-255, V 0-255).
Ces plages couvrent la palette de l'interface (PALETTE_INTERFACE) : le test tests/test_couleurs.py vérifie que
chaque pastille de la palette tombe dans la bonne couleur, et dans celle-là seulement.
"""
import cv2
import numpy as np

COULEURS = {
    "rouge":   [((0, 6), (150, 255), (140, 255)), ((172, 179), (150, 255), (140, 255))],   # le rouge « boucle » sur le cercle des teintes
    "orange":  [((8, 17), (170, 255), (190, 255))],
    "jaune":   [((19, 33), (130, 255), (190, 255))],
    "vert":    [((40, 80), (120, 255), (90, 230))],
    "cyan":    [((85, 95), (120, 255), (150, 255))],
    "bleu":    [((100, 121), (130, 255), (110, 255))],
    "violet":  [((124, 148), (90, 255), (90, 255))],
    "rose":    [((150, 168), (70, 170), (200, 255))],
    "marron":  [((8, 18), (150, 230), (75, 135))],
    "gris":    [((0, 179), (0, 50), (95, 205))],        # le gris de l'interface est légèrement bleuté (S ≈ 43)
    "noir":    [((0, 179), (0, 255), (0, 62))],         # le « noir » de l'interface est un bleu nuit très sombre (V ≈ 61)
    "blanc":   [((0, 179), (0, 25), (215, 255))]       # un blanc un peu assombri par la lumière reste blanc,
}

NOMS = list(COULEURS)

# Pastilles de la palette de l'interface (src/static/index.js), dans l'ordre -> couleur attendue
PALETTE_INTERFACE = [
    ("#e5484d", "rouge"), ("#ff8a3d", "orange"), ("#ffc83d", "jaune"), ("#3ecf8e", "vert"),
    ("#00bcd4", "cyan"), ("#2f6bff", "bleu"), ("#7c4dff", "violet"), ("#ff6bb5", "rose"),
    ("#7a4b2a", "marron"), ("#8a94a6", "gris"), ("#14213d", "noir"), ("#ffffff", "blanc"),
]

# (indice de couleur, h0, h1, s0, s1, v0, v1) pour chaque plage
_BOITES = [(i, h0, h1, s0, s1, v0, v1)
           for i, nom in enumerate(NOMS) for (h0, h1), (s0, s1), (v0, v1) in COULEURS[nom]]


def _dist_lineaire(x, a, b):
    return np.maximum(0, np.maximum(a - x, x - b))


def _dist_teinte(h, a, b):
    """Distance à l'intervalle [a, b] sur le cercle des teintes (0-179)."""
    d1 = np.minimum(np.abs(h - a), 180 - np.abs(h - a))
    d2 = np.minimum(np.abs(h - b), 180 - np.abs(h - b))
    return np.where((h >= a) & (h <= b), 0, np.minimum(d1, d2))


def indices_couleurs(hsv):
    """hsv : tableau (N, 3). Renvoie (indice de la couleur la plus proche, distance à sa plage).
    Une teinte hors de toutes les plages (zone de transition) est rattachée à la plus proche."""
    hsv = np.asarray(hsv, np.float32).reshape(-1, 3)
    h, s, v = hsv[:, 0], hsv[:, 1], hsv[:, 2]
    meilleure = np.full(len(hsv), np.inf, np.float32)
    indice = np.zeros(len(hsv), np.int32)
    for i, h0, h1, s0, s1, v0, v1 in _BOITES:
        d = np.sqrt((2.5 * _dist_teinte(h, h0, h1)) ** 2 + (0.3 * _dist_lineaire(s, s0, s1)) ** 2
                    + (0.3 * _dist_lineaire(v, v0, v1)) ** 2)
        mieux = d < meilleure
        meilleure = np.where(mieux, d, meilleure)
        indice = np.where(mieux, i, indice)
    return indice, meilleure


def bgr_vers_hsv(bgr):
    """(B, G, R) -> (H, S, V) OpenCV."""
    return tuple(int(x) for x in cv2.cvtColor(np.uint8([[list(bgr)]]), cv2.COLOR_BGR2HSV)[0, 0])


def nommer_couleur(bgr) -> str:
    """Nom de la couleur d'un pixel (B, G, R)."""
    return NOMS[int(indices_couleurs(bgr_vers_hsv(bgr))[0][0])]


def hex_vers_bgr(hexa: str):
    return tuple(int(hexa[i:i + 2], 16) for i in (5, 3, 1))
