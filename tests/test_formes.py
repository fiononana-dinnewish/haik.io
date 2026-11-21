"""Test de la conversion YOLO -> format de l'interface (ne nécessite ni poids ni GPU)."""
from src.models.formes import convertir


def test_convertir_format_interface():
    o = convertir([100.4, 50.6, 220.4, 150.6], 0.93456, 4, {4: "etoile"})
    assert o == {"boite": [100, 51, 120, 100], "forme": "etoile", "couleur": "", "confiance": 0.9346}


def test_boite_est_x_y_largeur_hauteur():
    x, y, w, h = convertir([10, 20, 60, 90], 0.5, 0, {0: "cercle"})["boite"]
    assert (x, y, w, h) == (10, 20, 50, 70)
