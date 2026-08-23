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
import tools


@pytest.fixture(autouse=True)
def jeu_d_essai():
    """Charge les CSV de data/ comme jeu de donnees actif pour chaque test."""
    tools.load_dataset_from_files()
    yield
    dataset.clear()
