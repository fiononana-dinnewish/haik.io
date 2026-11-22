"""Routes Flask, avec un faux détecteur (pas besoin de poids ni de GPU)."""
import cv2
import numpy as np
import pytest

import app as appli
from src.phrase import decrire


class Faux:
    def detecter(self, image):
        return [{"boite": [10, 10, 50, 50], "forme": "etoile", "couleur": "rose", "couleur_confiance": 0.5, "confiance": 0.9}]


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(appli, "_detecteur", Faux())
    return appli.app.test_client()


def _jpeg():
    return cv2.imencode(".jpg", np.full((60, 80, 3), 255, np.uint8))[1].tobytes()


def test_analyser(client):
    import io
    r = client.post("/analyser", data={"image": (io.BytesIO(_jpeg()), "i.jpg")}, content_type="multipart/form-data")
    o = r.get_json()["objets"]
    assert r.status_code == 200 and o[0]["forme"] == "etoile" and o[0]["couleur_incertaine"] is True


def test_analyser_sans_image(client):
    assert client.post("/analyser").status_code == 400


def test_decrire(client):
    r = client.post("/decrire", json={"objets": [{"forme": "cercle", "couleur": "rouge"}], "largeur": 640, "hauteur": 480})
    assert r.get_json()["phrase"] == "Je vois un cercle rouge."


def test_phrases():
    assert decrire([]) == "Je ne vois aucune forme."
    assert decrire([{"forme": "etoile", "couleur": "blanc"}]) == "Je vois une étoile blanche."
    o = [{"forme": "carre", "couleur": "bleu"}] * 2 + [{"forme": "cercle", "couleur": "vert"}]
    assert decrire(o) == "Je vois deux carrés bleus et un cercle vert."
