"""
Générateur de dataset synthétique « formes + couleurs » pour Haik.io — VERSION 2.

Ce qui change par rapport à la v1 (d'après les erreurs observées sur de vrais dessins de l'interface) :
  - formes tracées comme l'OUTIL FORME de l'interface : contour toujours tracé (largeur 1-40 px, jointures
    arrondies), remplissage optionnel, rectangles/triangles/losanges étirés
  - formes dessinées au STYLO à main levée : tremblement, coins arrondis, contours ouverts ou qui dépassent,
    ellipses, traits fins (1-2 px) ou épais comme un pinceau
  - fonds avec GRIBOUILLIS de pinceau épais (les trous blancs entre les traits ne doivent plus être pris pour des formes)
  - DISTRACTEURS non annotés qui ne sont pas des formes : cœurs, blobs libres, spirales, vagues, lettres, croix

Sortie (format Ultralytics / YOLO) :
    <out>/images/{train,val,test}/*.jpg
    <out>/labels/{train,val,test}/*.txt     classe = FORME  (x_centre y_centre largeur hauteur, normalisés)
    <out>/meta.csv                          une ligne par objet : forme + COULEUR + boîte (pour le modèle couleur)
    <out>/data.yaml                         fichier de config à donner à YOLO

Usage (à lancer depuis la racine du projet, Haik.io/) :
    python -m src.data.generer_formes --n 20000 --out data/formes --seed 42
    python -m src.data.generer_formes --n 24 --out test_formes --apercu     # vérification visuelle
"""
import argparse
import csv
import math
import random
from pathlib import Path

import cv2
import numpy as np

W, H = 640, 480

FORMES = ["cercle", "carre", "rectangle", "triangle", "etoile", "losange", "pentagone", "hexagone"]

# Couleurs : plages HSV OpenCV (H 0-179, S 0-255, V 0-255). Rouge a deux plages (le rouge « boucle » sur le cercle des teintes).
COULEURS = {
    "rouge":   [((0, 6), (150, 255), (140, 255)), ((172, 179), (150, 255), (140, 255))],
    "orange":  [((8, 18), (170, 255), (190, 255))],
    "jaune":   [((22, 32), (130, 255), (190, 255))],
    "vert":    [((40, 80), (120, 255), (90, 230))],
    "cyan":    [((85, 95), (120, 255), (150, 255))],
    "bleu":    [((102, 125), (130, 255), (110, 255))],
    "violet":  [((130, 148), (90, 255), (90, 230))],
    "rose":    [((150, 168), (70, 170), (200, 255))],
    "marron":  [((8, 18), (150, 230), (55, 120))],
    "gris":    [((0, 179), (0, 20), (100, 170))],
    "noir":    [((0, 179), (0, 255), (0, 45))],
    "blanc":   [((0, 179), (0, 18), (238, 255))],
}


# ----------------------------------------------------------------------------- couleurs
def couleur_aleatoire(nom, rng):
    plages = COULEURS[nom]
    (h0, h1), (s0, s1), (v0, v1) = rng.choice(plages)
    hsv = np.uint8([[[rng.randint(h0, h1), rng.randint(s0, s1), rng.randint(v0, v1)]]])
    b, g, r = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)[0, 0]
    return int(b), int(g), int(r)


def distance(c1, c2):
    return math.sqrt(sum((int(a) - int(b)) ** 2 for a, b in zip(c1, c2)))


# ----------------------------------------------------------------------------- fonds
def fond(rng, nprng):
    t = rng.choices(["blanc", "uni", "degrade", "bruit", "blobs"], weights=[42, 14, 10, 10, 24])[0]
    if t == "blanc":                                    # canvas de dessin
        img = np.full((H, W, 3), 255, np.uint8)
        v = rng.randint(238, 255)
        img[:] = (v, v, v)
        if rng.random() < 0.2:                           # fond quadrillé léger
            for x in range(0, W, 20):
                img[:, x] = (img[:, x] * 0.93).astype(np.uint8)
            for y in range(0, H, 20):
                img[y, :] = (img[y, :] * 0.93).astype(np.uint8)
        return img
    if t == "uni":
        c = [rng.randint(20, 235) for _ in range(3)]
        return np.full((H, W, 3), c, np.uint8)
    if t == "degrade":
        c1 = np.array([rng.randint(20, 235) for _ in range(3)], np.float32)
        c2 = np.array([rng.randint(20, 235) for _ in range(3)], np.float32)
        a = np.linspace(0, 1, W if rng.random() < 0.5 else H, dtype=np.float32)
        ligne = (c1[None] * (1 - a[:, None]) + c2[None] * a[:, None])
        if len(a) == W:
            return np.tile(ligne[None], (H, 1, 1)).astype(np.uint8)
        return np.tile(ligne[:, None], (1, W, 1)).astype(np.uint8)
    if t == "bruit":
        petit = nprng.integers(40, 220, (6, 8, 3), dtype=np.uint8)
        return cv2.resize(petit, (W, H), interpolation=cv2.INTER_CUBIC)
    # blobs : décor flou qui rappelle une pièce / une table
    img = np.full((H, W, 3), [rng.randint(60, 220) for _ in range(3)], np.uint8)
    for _ in range(rng.randint(5, 14)):
        c = tuple(rng.randint(30, 230) for _ in range(3))
        cv2.circle(img, (rng.randint(0, W), rng.randint(0, H)), rng.randint(30, 160), c, -1)
    return cv2.GaussianBlur(img, (0, 0), rng.randint(15, 40))


# ----------------------------------------------------------------------------- outils géométriques
def rotation(pts, angle):
    c, s = math.cos(angle), math.sin(angle)
    return [(x * c - y * s, x * s + y * c) for x, y in pts]


def tourner(P, a):
    c, s = math.cos(a), math.sin(a)
    return np.stack([P[:, 0] * c - P[:, 1] * s, P[:, 0] * s + P[:, 1] * c], 1)


def polygone_regulier(n, r, rot=0.0):
    return [(r * math.cos(rot + i * 2 * math.pi / n), r * math.sin(rot + i * 2 * math.pi / n)) for i in range(n)]


def epaisseur_aleatoire(rng, r=None):
    """Largeur de trait entre 1,5 et 34 px (le curseur de l'interface va de 1 à 40), répartie en échelle log :
    beaucoup de traits fins, quelques gros pinceaux. Plafonnée par la taille de la forme pour qu'elle reste lisible."""
    e = math.exp(rng.uniform(math.log(1.5), math.log(34)))
    if r is not None:
        e = min(e, max(1.5, 0.32 * r))       # au-delà, un contour épais devient un anneau : la forme n'est plus reconnaissable
    return e


def sommets(forme, r, rng):
    """Sommets centrés sur (0,0), avant rotation."""
    if forme == "carre":
        return [(-r, -r), (r, -r), (r, r), (-r, r)]
    if forme == "rectangle":
        a = rng.uniform(1.25, 3.2)
        hw, hh = r * math.sqrt(a), r / math.sqrt(a)
        if rng.random() < 0.3:
            hw, hh = hh, hw                                  # rectangle vertical
        return [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
    if forme == "triangle":
        return polygone_regulier(3, r, -math.pi / 2)
    if forme == "losange":
        k = rng.uniform(0.45, 0.85)
        return [(0, -r), (r * k, 0), (0, r), (-r * k, 0)]
    if forme == "pentagone":
        return polygone_regulier(5, r, -math.pi / 2)
    if forme == "hexagone":
        return polygone_regulier(6, r, 0)
    if forme == "etoile":
        ratio = rng.uniform(0.38, 0.5)
        pts = []
        for i in range(10):
            rayon = r if i % 2 == 0 else r * ratio
            a = -math.pi / 2 + i * math.pi / 5
            pts.append((rayon * math.cos(a), rayon * math.sin(a)))
        return pts
    raise ValueError(forme)


def catmull_rom(C, par_segment=14, ferme=False):
    """Courbe lisse passant par les points de contrôle C."""
    C = np.asarray(C, np.float32)
    P = np.vstack([C[-1], C, C[0], C[1]]) if ferme else np.vstack([C[0], C, C[-1]])
    t = np.linspace(0, 1, par_segment, endpoint=False)[:, None]
    morceaux = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        morceaux.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t ** 2
                               + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    morceaux.append(P[-2][None])
    return np.vstack(morceaux)


def densifier(pts, pas=3.0, ferme=True):
    """Rééchantillonne un tracé à pas régulier."""
    pts = np.asarray(pts, np.float32)
    if ferme:
        pts = np.vstack([pts, pts[:1]])
    seg = np.diff(pts, axis=0)
    cum = np.concatenate([[0], np.cumsum(np.hypot(seg[:, 0], seg[:, 1]))])
    total = float(cum[-1])
    if total < 1e-3:
        return pts
    n = max(8, int(total / pas))
    s = np.linspace(0, total, n, endpoint=not ferme)
    return np.stack([np.interp(s, cum, pts[:, 0]), np.interp(s, cum, pts[:, 1])], 1)


def chaikin(pts, iters):
    """Arrondit les coins d'un polygone fermé (un stylo ne fait pas d'angles vifs)."""
    P = np.asarray(pts, np.float32)
    for _ in range(iters):
        Q = np.roll(P, -1, axis=0)
        P = np.stack([0.75 * P + 0.25 * Q, 0.25 * P + 0.75 * Q], 1).reshape(-1, 2)
    return P


def tremblement(P, r, rng, nprng):
    """Ondulation lente (main qui dévie) + petit bruit (souris qui accroche)."""
    n = len(P)
    u = np.linspace(0, 1, n, endpoint=False)
    amp = r * rng.uniform(0.008, 0.035)
    dx, dy = np.zeros(n), np.zeros(n)
    for f in (2, 3, 5, 7):
        a = amp / math.sqrt(f)
        dx += a * np.sin(2 * math.pi * f * u + rng.uniform(0, 6.28))
        dy += a * np.sin(2 * math.pi * f * u + rng.uniform(0, 6.28))
    return P + np.stack([dx, dy], 1) + nprng.normal(0, rng.uniform(0.2, 0.8), P.shape)


def tracer_trait(img, P, couleur, ep):
    """Trace un trait à bouts et jointures arrondis (comme le pinceau de l'interface)."""
    pts = np.round(P).astype(np.int32)
    e = max(1, int(round(ep)))
    cv2.polylines(img, [pts.reshape(-1, 1, 2)], False, couleur, e, cv2.LINE_AA)
    if e >= 4:
        pas = max(1, e // 4)
        for p in pts[::pas]:
            cv2.circle(img, (int(p[0]), int(p[1])), e // 2, couleur, -1, cv2.LINE_AA)
        cv2.circle(img, (int(pts[-1][0]), int(pts[-1][1])), e // 2, couleur, -1, cv2.LINE_AA)


# ----------------------------------------------------------------------------- les deux façons de dessiner une forme
def chemin_outil(forme, r, rng):
    """Géométrie exacte, comme l'outil forme de l'interface."""
    if forme == "cercle":
        t = np.linspace(0, 2 * math.pi, 120, endpoint=False)
        return np.stack([r * np.cos(t), r * np.sin(t)], 1)
    pts = np.array(sommets(forme, r, rng), np.float32)
    if forme in ("triangle", "losange", "rectangle") and rng.random() < 0.5:
        pts[:, 0] *= rng.uniform(0.6, 1.6)                  # forme glissée dans un cadre plus large que haut
    angle = 0.0 if rng.random() < 0.7 else rng.uniform(0, 2 * math.pi)
    P = tourner(pts, angle)
    return densifier(P, pas=3.0, ferme=True)


def chemin_main_levee(forme, r, rng, nprng):
    """Forme dessinée à la main au stylo : irrégulière, tremblante, parfois aux coins arrondis."""
    if forme == "cercle":
        k = rng.uniform(0.7, 1.35)
        t = np.linspace(0, 2 * math.pi, 80, endpoint=False)
        pts = tourner(np.stack([r * np.cos(t), r * k * np.sin(t)], 1), rng.uniform(0, math.pi))
    else:
        base = np.array(sommets(forme, r, rng), np.float32)
        # Irrégularité et arrondi limités : au-delà, un pentagone ou un hexagone devient indiscernable d'un cercle
        # et l'étiquette serait fausse. Mieux vaut peu d'exemples ambigus que des étiquettes contradictoires.
        irr = rng.uniform(0.02, 0.05) if forme == "etoile" else rng.uniform(0.03, 0.10)
        base = base + nprng.normal(0, irr * r, base.shape)
        angle = rng.uniform(0, 2 * math.pi) if rng.random() < 0.35 else math.radians(rng.uniform(-20, 20))
        pts = tourner(base, angle)
        if forme == "etoile":
            iters = 1 if rng.random() < 0.15 else 0
        elif forme in ("pentagone", "hexagone"):
            iters = rng.choices([0, 1, 2], [0.8, 0.19, 0.01])[0]
        else:
            iters = rng.choices([0, 1, 2], [0.7, 0.27, 0.03])[0]
        if iters:
            pts = chaikin(pts, iters)
    P = densifier(pts, pas=rng.uniform(2.5, 6.0), ferme=True)
    return tremblement(P, r, rng, nprng)


def appliquer_ouverture(P, rng):
    """Un tracé à main levée se ferme rarement parfaitement : fermé, ouvert (trou) ou qui dépasse le point de départ."""
    n = len(P)
    P = np.roll(P, -rng.randrange(n), axis=0)
    mode = rng.choices(["ferme", "ouvert", "depasse"], [0.45, 0.30, 0.25])[0]
    if mode == "ferme":
        return np.vstack([P, P[:1]])
    if mode == "ouvert":
        return P[: n - max(1, int(n * rng.uniform(0.03, 0.12)))]
    k = max(2, int(n * rng.uniform(0.04, 0.12)))
    return np.vstack([P, P[:k] + np.array([rng.uniform(-6, 6), rng.uniform(-6, 6)])])


def dessiner_objet(img, forme, couleur, cx, cy, r, style, rng, nprng):
    """Dessine une forme. Renvoie sa boîte (x0, y0, x1, y1) en pixels."""
    ep = epaisseur_aleatoire(rng, r)
    if style == "outil":
        P = chemin_outil(forme, r, rng) + (cx, cy)
        plein = rng.random() < 0.5
        trait = np.vstack([P, P[:1]])             # l'outil forme trace TOUJOURS le contour (remplissage + contour)
    else:
        P = chemin_main_levee(forme, r, rng, nprng) + (cx, cy)
        plein = rng.random() < 0.15
        trait = np.vstack([P, P[:1]]) if plein else appliquer_ouverture(P, rng)
    if plein:
        cv2.fillPoly(img, [np.round(P).astype(np.int32).reshape(-1, 1, 2)], couleur, cv2.LINE_AA)
    tracer_trait(img, trait, couleur, ep)
    m = ep / 2 + 1
    return trait[:, 0].min() - m, trait[:, 1].min() - m, trait[:, 0].max() + m, trait[:, 1].max() + m


# ----------------------------------------------------------------------------- éléments qui NE sont PAS des formes
def distracteur(img, rng, nprng, fin=False):
    """Dessine un élément non annoté : le modèle doit apprendre à l'ignorer. fin=True : trait fin seulement
    (utilisé par-dessus les formes, pour ne pas les cacher)."""
    t = rng.choice(["pinceau", "pinceau", "blob", "blob", "coeur", "spirale", "vague", "lettre", "croix"])
    couleur = couleur_aleatoire(rng.choice(list(COULEURS)), rng)
    ep = float(rng.choice([2, 3, 4])) if fin else epaisseur_aleatoire(rng)
    cx, cy = rng.uniform(0.15 * W, 0.85 * W), rng.uniform(0.15 * H, 0.85 * H)
    R = rng.uniform(25, 120)
    plein = (not fin) and rng.random() < 0.25

    if t == "pinceau":
        C = [(rng.uniform(0, W), rng.uniform(0, H)) for _ in range(rng.randint(3, 6))]
        tracer_trait(img, catmull_rom(C, 16), couleur, ep if fin else rng.uniform(12, 40))
        return
    if t == "lettre":
        txt = rng.choice("BCEFGHJKLMNPRSTUXYZ1234" "57")      # sans O, Q, D, 0, 6, 8, 9, A, V : trop proches d'une forme
        police = rng.choice([cv2.FONT_HERSHEY_SIMPLEX, cv2.FONT_HERSHEY_DUPLEX, cv2.FONT_HERSHEY_SCRIPT_SIMPLEX])
        cv2.putText(img, txt, (int(cx - R / 2), int(cy + R / 2)), police, R / 22, couleur,
                    min(12, max(2, int(ep / 2))), cv2.LINE_AA)
        return
    if t == "croix":
        L = R
        if rng.random() < 0.5:
            segs = [[(-L, 0), (L, 0)], [(0, -L), (0, L)]]
        else:
            segs = [[(-L, -L), (L, L)], [(-L, L), (L, -L)]]
        for s in segs:
            tracer_trait(img, np.array(s, np.float32) + (cx, cy), couleur, ep)
        return

    if t == "blob":                                  # courbe fermée irrégulière : clairement pas un cercle
        th = np.linspace(0, 2 * math.pi, 120, endpoint=False)
        rad = np.ones_like(th)
        for h in (2, 3, 4, 5):
            rad += rng.uniform(0.06, 0.3) / math.sqrt(h) * np.cos(h * th + rng.uniform(0, 6.28))
        rad = np.clip(rad, 0.35, None)
        P = tourner(np.stack([R * rad * np.cos(th), R * rng.uniform(0.6, 1.2) * rad * np.sin(th)], 1), rng.uniform(0, math.pi))
    elif t == "coeur":
        tt = np.linspace(0, 2 * math.pi, 100)
        P = np.stack([16 * np.sin(tt) ** 3, -(13 * np.cos(tt) - 5 * np.cos(2 * tt) - 2 * np.cos(3 * tt) - np.cos(4 * tt))], 1) * (R / 17)
        P = tourner(P, math.radians(rng.uniform(-25, 25)))
    elif t == "spirale":
        th = np.linspace(0, 2 * math.pi * rng.uniform(2, 4), 160)
        rr = R * th / th.max()
        P = np.stack([rr * np.cos(th), rr * np.sin(th)], 1)
        plein = False
    else:                                            # vague ou zigzag
        L = rng.uniform(100, 300)
        xs = np.linspace(-L / 2, L / 2, 80)
        f, A = rng.uniform(2, 5), rng.uniform(8, 30)
        onde = np.sin(2 * math.pi * f * xs / L)
        ys = A * onde if rng.random() < 0.6 else A * (2 / math.pi) * np.arcsin(onde)
        P = tourner(np.stack([xs, ys], 1), rng.uniform(0, math.pi))
        plein = False
    P = P + (cx, cy)
    if plein:
        cv2.fillPoly(img, [np.round(P).astype(np.int32).reshape(-1, 1, 2)], couleur, cv2.LINE_AA)
    else:
        tracer_trait(img, np.vstack([P, P[:1]]) if t in ("blob", "coeur") else P, couleur, ep)


def trop_proche(b, autres):
    for o in autres:
        ix = max(0, min(b[2], o[2]) - max(b[0], o[0]))
        iy = max(0, min(b[3], o[3]) - max(b[1], o[1]))
        inter = ix * iy
        petit = min((b[2] - b[0]) * (b[3] - b[1]), (o[2] - o[0]) * (o[3] - o[1]))
        if inter > 0.05 * petit:
            return True
    return False


# ----------------------------------------------------------------------------- une image
def generer_image(rng, nprng):
    img = fond(rng, nprng)
    blanc = img.mean() > 235

    # 1. Décor sous les formes : gribouillis de gros pinceau (comme dans les tests réels) et/ou distracteurs
    if rng.random() < 0.28:
        base = couleur_aleatoire(rng.choice(list(COULEURS)), rng)
        for _ in range(rng.randint(3, 9)):
            C = [(rng.uniform(-30, W + 30), rng.uniform(-30, H + 30)) for _ in range(rng.randint(2, 4))]
            c = base if rng.random() < 0.8 else couleur_aleatoire(rng.choice(list(COULEURS)), rng)
            tracer_trait(img, catmull_rom(C, 16), c, rng.uniform(22, 46))
        n_dis = rng.choices([0, 1, 2], [60, 30, 10])[0]
    elif blanc or rng.random() < 0.5:
        n_dis = rng.choices([0, 1, 2, 3, 4], [38, 25, 17, 13, 7])[0]
    else:
        n_dis = rng.choices([0, 1], [75, 25])[0]
    for _ in range(n_dis):
        distracteur(img, rng, nprng)

    # 2. Formes annotées
    n_obj = rng.choices([0, 1, 2, 3, 4, 5], weights=[4, 33, 25, 18, 12, 8])[0]
    objets, boites = [], []
    essais = 0
    while len(objets) < n_obj and essais < 80:
        essais += 1
        forme = rng.choice(FORMES)
        nom_c = rng.choice(list(COULEURS))
        style = "main" if rng.random() < 0.55 else "outil"
        r = rng.uniform(0.05, 0.30 if n_obj <= 2 else 0.2) * H
        cx = rng.uniform(r * 1.5, W - r * 1.5)               # 1.5 > racine de 2 : une forme tournée reste dans l'image
        cy = rng.uniform(r * 1.5, H - r * 1.5)
        couleur = couleur_aleatoire(nom_c, rng)
        copie = img.copy()
        b = dessiner_objet(copie, forme, couleur, cx, cy, r, style, rng, nprng)
        b = (max(0, b[0]), max(0, b[1]), min(W - 1, b[2]), min(H - 1, b[3]))
        if (b[2] - b[0]) < 12 or (b[3] - b[1]) < 12 or trop_proche(b, boites):
            continue
        # La forme doit être visible : contraste moyen suffisant sur les pixels qu'elle a modifiés
        x0, y0, x1, y1 = int(b[0]), int(b[1]), int(b[2]) + 1, int(b[3]) + 1
        diff = np.abs(copie[y0:y1, x0:x1].astype(np.int16) - img[y0:y1, x0:x1].astype(np.int16)).max(axis=2)
        masque = diff > 10
        if masque.sum() < 30 or diff[masque].mean() < 40:
            continue
        img = copie
        boites.append(b)
        objets.append((forme, nom_c, b))

    # 3. Traits fins parasites par-dessus (n'altèrent pas les formes)
    if rng.random() < 0.15:
        for _ in range(rng.randint(1, 2)):
            distracteur(img, rng, nprng, fin=True)

    # 4. Dégradations réalistes (webcam / photo) — après annotation, les boîtes ne bougent pas
    img = img.astype(np.float32)
    img = img * rng.uniform(0.75, 1.2) + rng.uniform(-20, 20)
    if rng.random() < 0.5:
        img += nprng.normal(0, rng.uniform(1, 8), img.shape)
    img = np.clip(img, 0, 255).astype(np.uint8)
    k = rng.choice([0, 0, 3, 5])
    if k:
        img = cv2.GaussianBlur(img, (k, k), 0)
    return img, objets


# ----------------------------------------------------------------------------- programme principal
def ecrire_yaml(out):
    noms = "\n".join(f"  {i}: {n}" for i, n in enumerate(FORMES))
    # Pas de « path: » absolu : YOLO prend alors le dossier du data.yaml, le dataset marche donc
    # aussi bien sur ton PC, sur Colab ou après un « dvc pull ».
    (out / "data.yaml").write_text(
        f"train: images/train\nval: images/val\ntest: images/test\nnames:\n{noms}\n",
        encoding="utf-8")


def apercu(out, nb=12):
    """Mosaïque avec boîtes + étiquettes, pour vérifier à l'œil."""
    fichiers = sorted((out / "images").rglob("*.jpg"))[:nb]
    tuiles = []
    for f in fichiers:
        img = cv2.imread(str(f))
        lab = out / "labels" / f.parent.name / (f.stem + ".txt")
        if lab.exists():
            for ligne in lab.read_text().split("\n"):
                if not ligne.strip():
                    continue
                c, x, y, w, h = ligne.split()
                x, y, w, h = float(x) * W, float(y) * H, float(w) * W, float(h) * H
                p1, p2 = (int(x - w / 2), int(y - h / 2)), (int(x + w / 2), int(y + h / 2))
                cv2.rectangle(img, p1, p2, (255, 0, 255), 2)
                cv2.putText(img, FORMES[int(c)], (p1[0], max(p1[1] - 5, 14)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 2)
                cv2.putText(img, FORMES[int(c)], (p1[0], max(p1[1] - 5, 14)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
        tuiles.append(cv2.resize(img, (320, 240)))
    while len(tuiles) % 4:
        tuiles.append(np.zeros_like(tuiles[0]))
    lignes = [np.hstack(tuiles[i:i + 4]) for i in range(0, len(tuiles), 4)]
    cv2.imwrite(str(out / "apercu.jpg"), np.vstack(lignes))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20000, help="nombre d'images")
    ap.add_argument("--out", default="data/formes")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--apercu", action="store_true", help="écrit apercu.jpg (mosaïque de contrôle)")
    a = ap.parse_args()

    out = Path(a.out)
    for s in ("train", "val", "test"):
        (out / "images" / s).mkdir(parents=True, exist_ok=True)
        (out / "labels" / s).mkdir(parents=True, exist_ok=True)

    with open(out / "meta.csv", "w", newline="", encoding="utf-8") as fm:
        meta = csv.writer(fm)
        meta.writerow(["image", "split", "forme", "couleur", "x", "y", "w", "h"])
        for i in range(a.n):
            rng = random.Random(a.seed * 1_000_003 + i)          # reproductible image par image
            nprng = np.random.default_rng(a.seed * 1_000_003 + i)
            split = "val" if i % 10 == 0 else "test" if i % 10 == 1 else "train"
            img, objets = generer_image(rng, nprng)
            nom = f"{i:06d}"
            cv2.imwrite(str(out / "images" / split / f"{nom}.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, rng.randint(55, 95)])
            lignes = []
            for forme, coul, (x0, y0, x1, y1) in objets:
                xc, yc, w, h = (x0 + x1) / 2 / W, (y0 + y1) / 2 / H, (x1 - x0) / W, (y1 - y0) / H
                lignes.append(f"{FORMES.index(forme)} {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}")
                meta.writerow([f"{split}/{nom}.jpg", split, forme, coul, f"{xc:.6f}", f"{yc:.6f}", f"{w:.6f}", f"{h:.6f}"])
            (out / "labels" / split / f"{nom}.txt").write_text("\n".join(lignes), encoding="utf-8")

    ecrire_yaml(out)
    if a.apercu:
        apercu(out)
    print(f"{a.n} images générées dans {out}")


if __name__ == "__main__":
    main()