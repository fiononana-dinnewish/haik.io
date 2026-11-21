"""
Couleur d'un objet détecté (brique B), sans entraînement : on isole les pixels de la forme, puis on les nomme.

Pourquoi pas « la couleur dominante de la boîte » ? Une forme en contour fin est entourée de fond :
le fond dominerait toujours (« blanc »). On procède donc ainsi :
  1. on regarde l'anneau de pixels JUSTE AUTOUR de la boîte : ce sont les couleurs du fond
     (plusieurs couleurs possibles : feuille blanche + gribouillis d'une autre couleur) ;
  2. dans la boîte, les pixels qui ne ressemblent à aucune couleur de fond appartiennent à la forme ;
  3. on garde les plus contrastés (le cœur du trait, pas les bords adoucis qui se mélangent au fond) ;
  4. on nomme leur couleur médiane avec les plages de src/couleurs.py.

Usage :
    from src.models.couleur import couleur_objet
    nom, confiance = couleur_objet(image_bgr, [x, y, largeur, hauteur])
"""
import cv2
import numpy as np

from src.couleurs import NOMS, indices_couleurs

SEUIL_FOND = 40.0       # distance (en niveaux BGR) en dessous de laquelle un pixel est considéré comme « du fond »
PART_FOND = 0.03        # une couleur occupant au moins 3 % de l'anneau compte comme fond (un trait qui traverse la boîte en fait partie)
ECART = 3               # marge (px) entre la boîte et l'anneau de fond
PART_COEUR = 0.5        # on garde les pixels dont le contraste atteint au moins la moitié du contraste maximal


def _anneau(image, x0, y0, x1, y1):
    """Pixels juste autour de la boîte (ou, si la boîte touche les bords de l'image, son contour intérieur)."""
    h, w = image.shape[:2]
    m = max(6, int(0.1 * min(x1 - x0, y1 - y0))) + ECART
    ex0, ey0, ex1, ey1 = max(0, x0 - m), max(0, y0 - m), min(w, x1 + m), min(h, y1 + m)
    masque = np.ones((ey1 - ey0, ex1 - ex0), bool)       # on exclut la boîte ET une petite marge : une boîte serrée coupe parfois le trait
    masque[max(0, y0 - ECART - ey0):y1 + ECART - ey0, max(0, x0 - ECART - ex0):x1 + ECART - ex0] = False
    anneau = image[ey0:ey1, ex0:ex1][masque].astype(np.float32)
    if len(anneau) >= 30:
        return anneau
    reg = image[y0:y1, x0:x1]
    return np.concatenate([reg[:2].reshape(-1, 3), reg[-2:].reshape(-1, 3),
                           reg[:, :2].reshape(-1, 3), reg[:, -2:].reshape(-1, 3)]).astype(np.float32)


def _couleurs_de_fond(anneau):
    q = (anneau // 32).astype(np.int32)
    cle = q[:, 0] * 64 + q[:, 1] * 8 + q[:, 2]
    valeurs, nb = np.unique(cle, return_counts=True)
    fonds = [anneau[cle == v].mean(axis=0) for v, n in zip(valeurs, nb) if n >= PART_FOND * len(anneau)]
    return np.array(fonds) if fonds else np.median(anneau, axis=0, keepdims=True)    # fond en dégradé : une seule référence


def couleur_objet(image_bgr, boite) -> tuple[str, float]:
    """boite = [x, y, largeur, hauteur] en pixels. Renvoie (nom de couleur, confiance entre 0 et 1)."""
    h_img, w_img = image_bgr.shape[:2]
    x, y, w, h = (int(round(v)) for v in boite)
    x0, y0, x1, y1 = max(0, x), max(0, y), min(w_img, x + w), min(h_img, y + h)
    if x1 - x0 < 3 or y1 - y0 < 3:
        return "", 0.0

    region = image_bgr[y0:y1, x0:x1].reshape(-1, 3).astype(np.float32)
    fonds = _couleurs_de_fond(_anneau(image_bgr, x0, y0, x1, y1))
    d = np.min(np.linalg.norm(region[:, None, :] - fonds[None, :, :], axis=2), axis=1)   # écart au fond le plus proche

    ref = float(np.percentile(d, 99.5))              # le trait le plus contrasté (robuste au bruit JPEG isolé)
    coeur = d >= max(SEUIL_FOND, PART_COEUR * ref) if ref >= SEUIL_FOND else d >= 0.8 * ref
    if coeur.sum() < 3:
        coeur = d >= np.percentile(d, 99)            # forme quasi invisible : on prend le 1 % le plus différent
    pixels = region[coeur]

    mediane = np.median(pixels, axis=0)
    hsv_med = cv2.cvtColor(mediane.reshape(1, 1, 3).astype(np.uint8), cv2.COLOR_BGR2HSV).reshape(1, 3)
    choix = int(indices_couleurs(hsv_med)[0][0])
    hsv_pix = cv2.cvtColor(pixels.reshape(-1, 1, 3).astype(np.uint8), cv2.COLOR_BGR2HSV).reshape(-1, 3)
    accord = float(np.mean(indices_couleurs(hsv_pix)[0] == choix))     # part des pixels de la forme qui disent la même chose
    return NOMS[choix], round(accord, 3)
