"""
Mesure la précision du classifieur de couleur sur des images synthétiques (avec les VRAIES boîtes, pour isoler la couleur
de la détection). Écrit un JSON de résultats et une mosaïque des erreurs pour comprendre où ça se trompe.

    python -m src.models.evaluer_couleur --n 1500 --seed 123 --out reports/couleur_eval.json
"""
import argparse
import json
import random
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

from src.data.generer_formes import generer_image
from src.models.couleur import couleur_objet


def evaluer(n: int, seed: int):
    vrais, preds, confs, erreurs = [], [], [], []
    for i in range(n):
        rng, nprng = random.Random(seed * 1_000_003 + i), np.random.default_rng(seed * 1_000_003 + i)
        img, objets = generer_image(rng, nprng)
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, rng.randint(55, 95)])     # même compression que le dataset
        img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        for forme, vrai, (x0, y0, x1, y1) in objets:
            pred, conf = couleur_objet(img, [x0, y0, x1 - x0, y1 - y0])
            vrais.append(vrai); preds.append(pred); confs.append(conf)
            if pred != vrai:
                erreurs.append((img, (int(x0), int(y0), int(x1), int(y1)), vrai, pred, forme))
    return vrais, preds, confs, erreurs


def mosaique_erreurs(erreurs, chemin, nb=24, taille=200):
    tuiles = []
    for img, (x0, y0, x1, y1), vrai, pred, forme in erreurs[:nb]:
        m = 15
        crop = img[max(0, y0 - m):y1 + m, max(0, x0 - m):x1 + m]
        crop = cv2.resize(crop, (taille, taille))
        cv2.putText(crop, f"{vrai}->{pred}", (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 3)
        cv2.putText(crop, f"{vrai}->{pred}", (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        tuiles.append(crop)
    if not tuiles:
        return
    while len(tuiles) % 6:
        tuiles.append(np.zeros_like(tuiles[0]))
    cv2.imwrite(str(chemin), np.vstack([np.hstack(tuiles[i:i + 6]) for i in range(0, len(tuiles), 6)]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1500, help="nombre d'images à générer")
    ap.add_argument("--seed", type=int, default=123, help="graine différente de celle du dataset d'entraînement")
    ap.add_argument("--out", default="reports/couleur_eval.json")
    a = ap.parse_args()

    vrais, preds, confs, erreurs = evaluer(a.n, a.seed)
    total = len(vrais)
    ok = sum(v == p for v, p in zip(vrais, preds))
    par_couleur = {}
    for c in sorted(set(vrais)):
        idx = [i for i, v in enumerate(vrais) if v == c]
        par_couleur[c] = round(sum(preds[i] == c for i in idx) / len(idx), 3)
    confusions = Counter((v, p) for v, p in zip(vrais, preds) if v != p).most_common(10)
    # La confiance est-elle utile ? précision quand elle est élevée vs faible
    hauts = [v == p for v, p, c in zip(vrais, preds, confs) if c >= 0.8]
    bas = [v == p for v, p, c in zip(vrais, preds, confs) if c < 0.8]

    res = {
        "objets": total, "precision": round(ok / total, 4), "par_couleur": par_couleur,
        "confusions_frequentes": [{"vrai": v, "predit": p, "nb": n} for (v, p), n in confusions],
        "precision_si_confiance_>=0.8": round(sum(hauts) / max(1, len(hauts)), 4), "part_confiance_>=0.8": round(len(hauts) / total, 3),
        "precision_si_confiance_<0.8": round(sum(bas) / max(1, len(bas)), 4),
    }
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    mosaique_erreurs(erreurs, out.with_name("couleur_erreurs.jpg"))
    print(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
