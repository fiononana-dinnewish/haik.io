"""Test d'intégration : génère un mini-dataset et le fait passer par le validateur."""
import csv
import subprocess
import sys
from pathlib import Path

import pytest

from src.data.valider_dataset import valider

RACINE = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def mini_dataset(tmp_path_factory):
    out = tmp_path_factory.mktemp("formes")
    subprocess.run([sys.executable, "-m", "src.data.generer_formes", "--n", "40", "--seed", "7", "--out", str(out)],
                   check=True, cwd=RACINE)
    return out


def test_structure_et_validation(mini_dataset):
    stats = valider(mini_dataset)
    assert stats["nb_erreurs"] == 0, stats["erreurs"]
    assert stats["images"] == 40
    assert stats["objets"] > 0


def test_repartition_train_val_test(mini_dataset):
    stats = valider(mini_dataset)
    assert stats["par_split"] == {"train": 32, "val": 4, "test": 4}


def test_data_yaml_portable(mini_dataset):
    txt = (mini_dataset / "data.yaml").read_text(encoding="utf-8")
    assert "path:" not in txt          # pas de chemin absolu : le dataset doit marcher sur Colab
    assert "train: images/train" in txt and "0: cercle" in txt


def test_meta_coherent_avec_labels(mini_dataset):
    with open(mini_dataset / "meta.csv", newline="", encoding="utf-8") as f:
        lignes = list(csv.DictReader(f))
    n_labels = sum(len([l for l in p.read_text().splitlines() if l.strip()]) for p in (mini_dataset / "labels").rglob("*.txt"))
    assert len(lignes) == n_labels


def test_validateur_detecte_un_label_casse(mini_dataset, tmp_path):
    """Le validateur doit vraiment échouer sur un dataset corrompu (sinon il ne sert à rien)."""
    import shutil
    copie = tmp_path / "casse"
    shutil.copytree(mini_dataset, copie)
    label = next(p for p in (copie / "labels" / "train").glob("*.txt") if p.read_text().strip())
    label.write_text("99 0.5 0.5 0.2 0.2\n", encoding="utf-8")      # classe inexistante
    assert valider(copie)["nb_erreurs"] >= 1
