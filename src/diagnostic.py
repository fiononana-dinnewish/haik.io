"""Vérifie que la couleur est bien branchée.   python -m src.diagnostic --poids models/best_2.pt --image reel/une_image.png"""
import argparse
import inspect
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--poids", default="models/best_2.pt")
    ap.add_argument("--image", required=True)
    a = ap.parse_args()

    import cv2
    from src.models import formes
    from src.models.formes import DetecteurFormes
    print("formes.py utilisé :", Path(formes.__file__).resolve())
    print("  gère la couleur :", "couleur_objet" in inspect.getsource(formes))
    try:
        from src.models.couleur import couleur_objet
        img = cv2.imread(a.image)
        print("module couleur OK ; image entière ->", couleur_objet(img, [0, 0, img.shape[1], img.shape[0]]))
    except Exception as e:
        print("MODULE COULEUR EN ERREUR :", repr(e))
        return
    for o in DetecteurFormes(a.poids).detecter(img):
        print(o)


if __name__ == "__main__":
    main()
