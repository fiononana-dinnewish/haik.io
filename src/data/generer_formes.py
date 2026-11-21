"""
Générateur de dataset synthétique « formes + couleurs » pour Haik.io.

Sortie (format Ultralytics / YOLO) :
    <out>/images/{train,val,test}/*.jpg
    <out>/labels/{train,val,test}/*.txt     classe = FORME  (x_centre y_centre largeur hauteur, normalisés)
    <out>/meta.csv                          une ligne par objet : forme + COULEUR + boîte (pour le modèle couleur)
    <out>/data.yaml                         fichier de config à donner à YOLO

La forme est apprise par le détecteur. La couleur est annotée à part dans meta.csv
(un petit classifieur de couleur sera entraîné sur les recadrages).

Usage :
    python -m src.data.generer_formes --n 20000 --out data/formes --seed 42
    python -m src.data.generer_formes --n 24 --out test_formes --apercu     # vérification visuelle
(à lancer depuis la racine du projet, Haik.io/)
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
    t = rng.choices(["blanc", "uni", "degrade", "bruit", "blobs"], weights=[25, 20, 15, 15, 25])[0]
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


# ----------------------------------------------------------------------------- géométrie
def rotation(pts, angle):
    c, s = math.cos(angle), math.sin(angle)
    return [(x * c - y * s, x * s + y * c) for x, y in pts]


def polygone_regulier(n, r, rot=0.0):
    return [(r * math.cos(rot + i * 2 * math.pi / n), r * math.sin(rot + i * 2 * math.pi / n)) for i in range(n)]


def sommets(forme, r, rng):
    """Sommets centrés sur (0,0), avant rotation."""
    if forme == "carre":
        return [(-r, -r), (r, -r), (r, r), (-r, r)]
    if forme == "rectangle":
        a = rng.uniform(1.35, 2.5)
        hw, hh = r * math.sqrt(a), r / math.sqrt(a)
        return [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
    if forme == "triangle":
        return polygone_regulier(3, r, -math.pi / 2)
    if forme == "losange":
        k = rng.uniform(0.55, 0.8)
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


def dessiner_objet(img, forme, couleur, cx, cy, r, rng, nprng):
    """Dessine un objet. Renvoie sa boîte (x0, y0, x1, y1) en pixels."""
    plein = rng.random() < 0.6
    epaisseur = -1 if plein else rng.randint(2, max(3, int(r * 0.3)))
    marge = 0 if plein else epaisseur / 2

    if forme == "cercle":
        a = rng.uniform(0.93, 1.07)                      # quasi-cercle (tracé à la main)
        ax, ay = int(r), int(r * a)
        cv2.ellipse(img, (int(cx), int(cy)), (ax, ay), 0, 0, 360, couleur, epaisseur, cv2.LINE_AA)
        return cx - ax - marge, cy - ay - marge, cx + ax + marge, cy + ay + marge

    pts = sommets(forme, r, rng)
    if forme in ("carre", "rectangle", "losange", "triangle") and rng.random() < 0.5:
        angle = math.radians(rng.uniform(-15, 15))       # souvent presque droit
    else:
        angle = rng.uniform(0, 2 * math.pi)
    pts = rotation(pts, angle)
    if rng.random() < 0.4:                               # tremblement de la main
        sig = r * 0.025
        pts = [(x + nprng.normal(0, sig), y + nprng.normal(0, sig)) for x, y in pts]
    pts = [(x + cx, y + cy) for x, y in pts]

    arr = np.array(pts, np.int32).reshape(-1, 1, 2)
    if plein:
        cv2.fillPoly(img, [arr], couleur, cv2.LINE_AA)
    else:
        cv2.polylines(img, [arr], True, couleur, epaisseur, cv2.LINE_AA)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs) - marge, min(ys) - marge, max(xs) + marge, max(ys) + marge


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
    mode_dessin = img.mean() > 235 and rng.random() < 0.7
    n_obj = rng.choices([0, 1, 2, 3, 4, 5], weights=[4, 33, 25, 18, 12, 8])[0]
    objets, boites = [], []

    essais = 0
    while len(objets) < n_obj and essais < 60:
        essais += 1
        forme = rng.choice(FORMES)
        nom_c = rng.choice(list(COULEURS))
        r = rng.uniform(0.06, 0.30 if n_obj <= 2 else 0.2) * H
        cx = rng.uniform(r * 1.5, W - r * 1.5)               # 1.5 > racine de 2 : un carré tourné reste dans l'image
        cy = rng.uniform(r * 1.5, H - r * 1.5)
        couleur = couleur_aleatoire(nom_c, rng)
        fond_local = img[int(cy), int(cx)]
        if distance(couleur, fond_local) < 90:           # trop peu contrasté : on repart
            continue
        if mode_dessin and nom_c == "blanc":
            continue
        copie = img.copy()
        b = dessiner_objet(copie, forme, couleur, cx, cy, r, rng, nprng)
        b = (max(0, b[0]), max(0, b[1]), min(W - 1, b[2]), min(H - 1, b[3]))
        if (b[2] - b[0]) < 12 or (b[3] - b[1]) < 12 or trop_proche(b, boites):
            continue
        img = copie
        boites.append(b)
        objets.append((forme, nom_c, b))

    # Distracteurs non annotés (traits fins) pour éviter les faux positifs
    if rng.random() < 0.15:
        for _ in range(rng.randint(1, 3)):
            pts = np.array([(rng.randint(0, W), rng.randint(0, H)) for _ in range(rng.randint(2, 5))], np.int32)
            cv2.polylines(img, [pts.reshape(-1, 1, 2)], False, tuple(rng.randint(0, 255) for _ in range(3)), 1, cv2.LINE_AA)

    # Dégradations réalistes (webcam / photo) — après annotation, les boîtes ne bougent pas
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
        meta = {}
        if lab.exists():
            for i, ligne in enumerate(lab.read_text().split("\n")):
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
