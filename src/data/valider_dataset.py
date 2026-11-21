"""
Contrôle qualité d'un dataset YOLO généré par generer_formes.py.

Vérifie : image lisible, label présent, 5 champs par ligne, classe valide, boîte dans l'image,
cohérence labels <-> meta.csv. Écrit des statistiques (JSON) suivies par DVC comme « metrics ».
Code de sortie 1 s'il y a au moins une erreur (pour bloquer le pipeline).

Usage :
    python -m src.data.valider_dataset --dataset data/formes --out reports/dataset_stats.json
(à lancer depuis la racine du projet, Haik.io/)
"""
import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

import cv2

from src.data.generer_formes import FORMES

SPLITS = ("train", "val", "test")


def valider(dataset: Path) -> dict:
    erreurs = []
    par_classe, par_couleur = Counter(), Counter()
    n_images = n_objets = n_vides = 0
    par_split = {}

    for split in SPLITS:
        images = sorted((dataset / "images" / split).glob("*.jpg"))
        par_split[split] = len(images)
        for img in images:
            n_images += 1
            if cv2.imread(str(img)) is None:
                erreurs.append(f"image illisible : {img.name}")
            lab = dataset / "labels" / split / (img.stem + ".txt")
            if not lab.exists():
                erreurs.append(f"label manquant : {img.name}")
                continue
            lignes = [l for l in lab.read_text(encoding="utf-8").splitlines() if l.strip()]
            if not lignes:
                n_vides += 1
            for l in lignes:
                champs = l.split()
                if len(champs) != 5:
                    erreurs.append(f"{lab.name} : ligne invalide « {l} »")
                    continue
                c = int(float(champs[0]))
                x, y, w, h = map(float, champs[1:])
                if not 0 <= c < len(FORMES):
                    erreurs.append(f"{lab.name} : classe {c} hors limites")
                    continue
                if min(w, h) <= 0 or x - w / 2 < -1e-6 or y - h / 2 < -1e-6 or x + w / 2 > 1 + 1e-6 or y + h / 2 > 1 + 1e-6:
                    erreurs.append(f"{lab.name} : boîte hors de l'image « {l} »")
                    continue
                n_objets += 1
                par_classe[FORMES[c]] += 1

    meta = dataset / "meta.csv"
    n_meta = 0
    if meta.exists():
        with open(meta, newline="", encoding="utf-8") as f:
            for ligne in csv.DictReader(f):
                n_meta += 1
                par_couleur[ligne["couleur"]] += 1
    if n_meta != n_objets:
        erreurs.append(f"meta.csv ({n_meta} lignes) ≠ labels ({n_objets} objets)")

    effectifs = list(par_classe.values())
    return {
        "images": n_images,
        "images_sans_objet": n_vides,
        "objets": n_objets,
        "par_split": par_split,
        "par_classe": dict(par_classe),
        "par_couleur": dict(par_couleur),
        # 1.0 = parfaitement équilibré ; plus c'est grand, plus une classe domine
        "desequilibre_classes": round(max(effectifs) / min(effectifs), 3) if effectifs else None,
        "nb_erreurs": len(erreurs),
        "erreurs": erreurs[:50],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="data/formes")
    ap.add_argument("--out", default="reports/dataset_stats.json")
    a = ap.parse_args()

    stats = valider(Path(a.dataset))
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"{stats['images']} images, {stats['objets']} objets, {stats['nb_erreurs']} erreur(s)")
    if stats["nb_erreurs"]:
        for e in stats["erreurs"][:10]:
            print(" -", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
