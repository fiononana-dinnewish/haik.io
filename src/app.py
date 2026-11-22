"""Serveur Haik.io : sert l'interface (static/) et expose le modèle.

    python app.py            puis ouvrir http://127.0.0.1:5000

Variables d'environnement facultatives :
    HAIK_POIDS   chemin des poids YOLO (défaut : models/formes_v1.pt)
    HAIK_CONF    seuil de confiance (défaut : 0.5)
"""
import os

import cv2
import numpy as np
from flask import Flask, jsonify, request

from src.phrase import decrire

POIDS = os.environ.get("HAIK_POIDS", "models/best_2.pt")
CONF = float(os.environ.get("HAIK_CONF", "0.5"))
SEUIL_COULEUR = 0.8       # en dessous, la couleur est jugée peu fiable (cf. reports/couleur_eval.json)

app = Flask(__name__, static_folder='static', static_url_path='')
app.config["MAX_CONTENT_LENGTH"] = 15 * 1024 * 1024      # images de 15 Mo maximum

_detecteur = None


def detecteur():
    """Chargé au premier appel (démarrage rapide, et l'interface reste servie même si les poids manquent)."""
    global _detecteur
    if _detecteur is None:
        from src.models.formes import DetecteurFormes
        _detecteur = DetecteurFormes(POIDS, conf=CONF)
    return _detecteur


@app.get('/')
def accueil():
    return app.send_static_file('index.html')


@app.post('/analyser')
def analyser():
    fichier = request.files.get('image')
    if fichier is None:
        return jsonify(erreur="champ « image » manquant"), 400
    image = cv2.imdecode(np.frombuffer(fichier.read(), np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        return jsonify(erreur="image illisible"), 400
    try:
        objets = detecteur().detecter(image)
    except FileNotFoundError:
        return jsonify(erreur=f"poids introuvables : {POIDS}"), 500
    for o in objets:
        if o.get("couleur_confiance", 1) < SEUIL_COULEUR:
            o["couleur_incertaine"] = True        # l'interface peut afficher « ? » ou atténuer la couleur
    return jsonify(objets=objets)


@app.post('/decrire')
def decrire_route():
    donnees = request.get_json(silent=True) or {}
    return jsonify(phrase=decrire(donnees.get("objets") or []))


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000)
