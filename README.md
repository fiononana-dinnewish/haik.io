# Haik.io

Détection de **formes** et de **couleurs** (dessin), et d'**objets** (webcam / photos), avec une interface web Flask.

## Architecture des modèles

| Brique | Rôle | Données | Entraînement |
|---|---|---|---|
| **A. Formes** | 8 formes avec boîtes | dataset synthétique (`src/data/generer_formes.py`) | YOLO11 sur Google Colab |
| **B. Couleur** | 12 couleurs par boîte | recadrages issus de A (`meta.csv`) | petit CNN ou règles HSV |
| **C. Objets** | personne, tableau, plats… | COCO / Open Images (pré-entraîné, affiné si besoin) | YOLO pré-entraîné |

## Structure du projet

```
Haik.io/
├── .venv/                      environnement Python (ignoré par Git)
├── .gitignore
├── .env                        secrets locaux (ignoré) — ne jamais commiter
├── README.md
├── requirements.txt            dépendances de l'application
├── requirements-dev.txt        + données, tests, DVC
├── pytest.ini
├── params.yaml                 paramètres suivis par DVC
├── dvc.yaml                    pipeline : génération -> validation du dataset
├── dvc.lock                    (généré) empreintes exactes — à commiter
├── .dvc/                       (généré par « dvc init »)
├── data/                       datasets — gérés par DVC, pas par Git
│   ├── formes/                 (généré) images/ labels/ meta.csv data.yaml
│   └── objets/                 (plus tard) sous-ensemble COCO / Open Images
├── models/                     poids entraînés (.pt) — gérés par DVC
├── reports/                    dataset_stats.json, métriques d'entraînement
├── notebooks/                  notebooks Colab (entraînement)
├── src/
│   ├── __init__.py
│   ├── static/                 ton interface : index.html, index.css, index.js
│   ├── data/
│   │   ├── __init__.py
│   │   ├── generer_formes.py   générateur du dataset de formes
│   │   └── valider_dataset.py  contrôle qualité + statistiques
│   ├── models/                 (plus tard) chargement des modèles A, B, C
│   └── app.py                  (ton serveur Flask : /analyser, /decrire)
└── tests/
    ├── __init__.py
    ├── test_generateur.py
    └── test_dataset.py
```

Attention : `data/` à la racine contient les **données** ; `src/data/` contient le **code** qui les fabrique.

## Étape 1 — Environnement

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
```

Après installation, fige les versions exactes : `pip freeze > requirements.lock.txt`.

## Étape 2 — Dataset de formes

Depuis la racine du projet :

```powershell
python -m src.data.generer_formes --n 24 --out test_formes --apercu
```

Ouvre `test_formes/apercu.jpg` : chaque forme doit avoir sa boîte et son étiquette. Quand c'est bon, supprime `test_formes/` et passe à DVC (étape 4) : `dvc repro` génère le vrai dataset (20 000 images) avec les paramètres de `params.yaml`.

## Étape 3 — Tests

```powershell
pytest -q
```

Ils vérifient que le générateur est reproductible, que les boîtes restent dans l'image, que chaque couleur est non ambiguë, et que le validateur détecte bien un dataset cassé. À relancer à chaque modification du générateur.

## Étape 4 — DVC et Git

```powershell
git init                      # si ce n'est pas déjà fait
dvc init
git add .dvc .dvcignore .gitignore dvc.yaml params.yaml
git commit -m "Initialise DVC"

dvc repro                     # génère data/formes puis le valide
git add dvc.lock reports/dataset_stats.json
git commit -m "Dataset formes v1 (20000 images, seed 42)"
git tag dataset-formes-v1
```

Le dataset formes est **entièrement reproductible** (même seed = mêmes images). Sur Colab, il suffit donc de cloner le dépôt et de lancer `dvc repro` : aucun stockage distant n'est nécessaire pour lui.

Un stockage distant sert pour ce qui n'est **pas** reproductible : les poids entraînés (`models/`) et les datasets réels téléchargés (`data/objets/`). Pour un dossier Google Drive :

```powershell
dvc remote add --default stockage gdrive://<ID_DU_DOSSIER_DRIVE>/haik
dvc push
```

Le premier `dvc push` ouvre le navigateur pour te connecter. En cas d'erreur « This app is blocked », crée ton propre projet Google Cloud (API Drive + identifiant OAuth « Application de bureau »), puis :

```powershell
dvc remote modify stockage gdrive_client_id "<id>"
dvc remote modify --local stockage gdrive_client_secret "<secret>"
```

Pour faire évoluer le dataset : modifie `params.yaml` (ou le générateur), relance `dvc repro`, commite `dvc.lock`, puis crée un nouveau tag (`dataset-formes-v2`).

## Datasets pour la brique C (objets réels)

- **COCO** : 80 classes dont personne, parapluie, écran, ordinateur, et 10 aliments (banane, pomme, sandwich, orange, brocoli, carotte, hot-dog, pizza, donut, gâteau). **Pas de classe « tableau blanc ».** Les poids YOLO11 pré-entraînés sur COCO sont fournis par Ultralytics : https://docs.ultralytics.com/models/yolo11/
- **Open Images V7** : 601 classes, beaucoup plus d'aliments et d'objets. Le dataset complet fait environ 561 Go, donc ne le télécharge pas en entier : utilise les poids pré-entraînés `yolov8n-oiv7.pt` … `yolov8x-oiv7.pt`, ou télécharge seulement quelques classes avec FiftyOne : https://docs.ultralytics.com/datasets/detect/open-images-v7 et https://docs.voxel51.com/dataset_zoo/datasets/open_images_v7.html
- **Tes propres images** (webcam, plats, tableau blanc) : une centaine suffit pour affiner. À annoter avec Roboflow, CVAT ou Label Studio.
