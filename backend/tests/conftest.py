"""Configuration commune des tests.

Depuis que le repli automatique sur data/ a ete retire (voir
tools._load_claims), plus rien ne lit ces fichiers sans qu'on le demande. Les
tests qui exercent les tools deterministes doivent donc charger le jeu
d'essai eux-memes - c'est fait ici, une fois pour toutes.

Les tests qui verifient l'absence de donnees appellent dataset.clear() de
leur cote ; la fixture est reappliquee au test suivant.
"""

import pytest

import dataset
import dataset_db
import tools


@pytest.fixture(autouse=True, scope="session")
def base_a_l_ecart(tmp_path_factory):
    """AUCUN test n'ecrit dans la base de l'utilisateur.

    dataset.set_active() enregistre desormais tout jeu depose dans
    backend/dataset.sqlite3, et dataset.clear() l'efface. Sans ce
    detournement vers un fichier temporaire, lancer la suite de tests
    supprimerait les dossiers que l'utilisateur a deposes dans
    l'application. Portee `session` : la redirection est en place avant
    la premiere fixture de test."""
    dataset_db.use_path(tmp_path_factory.mktemp("dataset-db") / "test.sqlite3")
    yield


@pytest.fixture(autouse=True)
def jeu_d_essai():
    """Charge les CSV de data/ comme jeu de donnees actif pour chaque test."""
    tools.load_dataset_from_files()
    yield
    dataset.clear()
