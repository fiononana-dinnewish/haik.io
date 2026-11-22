"""
Détection des formes (brique A) avec le modèle YOLO entraîné.

Renvoie les objets au format attendu par l'interface :
    {"boite": [x, y, largeur, hauteur] (pixels), "forme": "etoile", "couleur": "", "confiance": 0.93}
La couleur est laissée vide ici : elle sera remplie par la brique B.

Usage en ligne de commande (test sur des dessins réels) :
    python -m src.models.formes --poids models/formes_v1.pt --source reel --conf 0.25
Usage dans Flask :
    from src.models.formes import DetecteurFormes
    detecteur = DetecteurFormes("models/formes_v1.pt")      # une seule fois, au démarrage du serveur
    objets = detecteur.detecter(image_bgr)                    # image_bgr : tableau OpenCV (cv2.imdecode)
"""
import argparse
import json
from pathlib import Path


def convertir(xyxy, confiance, classe, noms) -> dict:
    """Convertit une détection YOLO (x1, y1, x2, y2) vers le format de l'interface (x, y, largeur, hauteur)."""
    x1, y1, x2, y2 = (float(v) for v in xyxy)
    return {
        "boite": [round(x1), round(y1), round(x2 - x1), round(y2 - y1)],
        "forme": noms[int(classe)],
        "couleur": "",
        "confiance": round(float(confiance), 4),
    }


class DetecteurFormes:
    def __init__(self, poids: str, conf: float = 0.5, imgsz: int = 640):
        from ultralytics import YOLO       # import ici : les tests de conversion n'ont pas besoin d'ultralytics
        self.modele = YOLO(poids)
        self.conf = conf
        self.imgsz = imgsz

    def detecter(self, image, conf: float | None = None) -> list[dict]:
        # agnostic_nms : une même zone ne peut recevoir qu'UNE forme (sinon « pentagone 44 % » et « hexagone 93 % » coexistent)
        res = self.modele.predict(image, conf=self.conf if conf is None else conf,
                                  imgsz=self.imgsz, agnostic_nms=True, verbose=False)[0]
        noms = res.names
        objets = [convertir(b.xyxy[0].tolist(), b.conf[0], b.cls[0], noms) for b in res.boxes]
        from src.models.couleur import couleur_objet
        for o in objets:
            o["couleur"], o["couleur_confiance"] = couleur_objet(image, o["boite"])
        return sorted(objets, key=lambda o: (o["boite"][1], o["boite"][0]))   # lecture haut-gauche -> bas-droite


def main():
    import cv2

    ap = argparse.ArgumentParser(description="Teste le modèle de formes sur une image ou un dossier d'images")
    ap.add_argument("--poids", default="models/formes_v1.pt")
    ap.add_argument("--source", required=True, help="image ou dossier d'images")
    ap.add_argument("--conf", type=float, default=0.5, help="seuil de confiance (0.5 par défaut ; plus bas = plus de faux positifs)")
    ap.add_argument("--out", default="reports/predictions", help="dossier des images annotées")
    a = ap.parse_args()

    det = DetecteurFormes(a.poids, conf=a.conf)
    src = Path(a.source)
    fichiers = sorted(p for p in ([src] if src.is_file() else src.iterdir())
                      if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"})
    if not fichiers:
        raise SystemExit(f"Aucune image trouvée dans {src}")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    for f in fichiers:
        img = cv2.imread(str(f))
        if img is None:
            print(f"{f.name} : illisible")
            continue
        objets = det.detecter(img)
        print(f"{f.name} : " + (", ".join(f"{o['forme']} ({o['confiance']:.0%})" for o in objets) or "aucune forme détectée"))
        for o in objets:
            x, y, w, h = o["boite"]
            cv2.rectangle(img, (x, y), (x + w, y + h), (255, 0, 255), 2)
            txt = f"{o['forme']} {o['confiance']:.0%}"
            cv2.putText(img, txt, (x, max(y - 6, 14)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 3)
            cv2.putText(img, txt, (x, max(y - 6, 14)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        cv2.imwrite(str(out / f"{f.stem}_pred.jpg"), img)
        (out / f"{f.stem}.json").write_text(json.dumps(objets, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nImages annotées dans {out}/")


if __name__ == "__main__":
    main()