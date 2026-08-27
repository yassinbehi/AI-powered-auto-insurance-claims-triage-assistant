"""Tests de la base SQLite du jeu de donnees (src/dataset_db.py) et de son
branchement sur le jeu actif (src/dataset.py).

La base est deja detournee vers un fichier temporaire par la fixture
`base_a_l_ecart` de conftest.py : aucun test d'ici n'approche la base de
l'utilisateur.
"""

import sqlite3

import pytest

import dataset
import dataset_db


_CLAIMS = {
    "CLM-001": {
        "claim_id": "CLM-001",
        "policy_id": "POL-002",
        "date_sinistre": "2026-07-18",
        "type_sinistre": "collision",
        "description_client": "Choc arriere a un feu rouge.",
        "blessure": "non",
        "constat": "oui",
        "photos": "oui",
        "devis_tnd": 2400,
        "tiers_identifie": "oui",
        "kilometrage_declare": 48200,
    }
}

_POLICIES = {
    "POL-002": {
        "policy_id": "POL-002",
        "assure": "Youssef Trabelsi",
        "vehicule": "Renault Clio",
        "formule": "tous_risques",
        "date_debut": "2026-01-01",
        "date_fin": "2026-12-31",
        "franchise_tnd": 300,
        # Listes : c'est ce que le stockage en JSON preserve sans effort, la ou
        # une colonne SQL par champ aurait demande un encodage a part.
        "garanties": ["collision", "vol", "bris_glace"],
        "exclusions": ["conduite sans permis"],
    }
}

_REJETS = [
    {"fichier": "declarations", "ligne": 4, "identifiant": "CLM-009", "raison": "devis_tnd illisible"}
]


def _enregistrer(loaded_at="2026-08-27T10:00:00+00:00"):
    dataset_db.save(
        _CLAIMS,
        _POLICIES,
        claims_filename="declarations.csv",
        policies_filename="contrats.csv",
        loaded_at=loaded_at,
        lignes_rejetees=_REJETS,
    )


@pytest.fixture(autouse=True)
def base_vide():
    """Chaque test part d'une base vierge : la fixture de conftest partage un
    seul fichier pour toute la session."""
    dataset_db.clear()
    yield
    dataset_db.clear()


class TestAllerRetour:
    def test_base_vide_ne_rend_rien(self):
        """None et non un jeu vide : l'application doit alors demarrer sur son
        ecran de depot, comme avant l'existence de la base."""
        assert dataset_db.load() is None

    def test_ce_qui_est_enregistre_est_relu_a_l_identique(self):
        _enregistrer()
        lu = dataset_db.load()

        assert lu["claims"] == _CLAIMS
        assert lu["policies"] == _POLICIES
        assert lu["claims_filename"] == "declarations.csv"
        assert lu["policies_filename"] == "contrats.csv"
        assert lu["loaded_at"] == "2026-08-27T10:00:00+00:00"
        assert lu["lignes_rejetees"] == _REJETS

    def test_les_accents_survivent(self):
        """ensure_ascii=False a l'ecriture, et SQLite stocke de l'UTF-8 : un
        nom accentue doit revenir tel quel."""
        claims = {"CLM-1": dict(_CLAIMS["CLM-001"], description_client="Pare-brise fissuré à Béja")}
        dataset_db.save(
            claims, _POLICIES,
            claims_filename="a.csv", policies_filename="b.csv",
            loaded_at="2026-08-27T10:00:00+00:00",
        )
        assert dataset_db.load()["claims"]["CLM-1"]["description_client"] == "Pare-brise fissuré à Béja"

    def test_un_depot_remplace_le_precedent(self):
        """Les deux fichiers vont ensemble et sont remplaces d'un bloc : aucun
        sinistre du jeu precedent ne doit survivre au suivant."""
        _enregistrer()
        autres = {"CLM-999": dict(_CLAIMS["CLM-001"], claim_id="CLM-999")}
        dataset_db.save(
            autres, _POLICIES,
            claims_filename="autre.csv", policies_filename="contrats.csv",
            loaded_at="2026-08-28T10:00:00+00:00",
        )
        assert list(dataset_db.load()["claims"]) == ["CLM-999"]

    def test_clear_efface_reellement(self):
        _enregistrer()
        dataset_db.clear()
        assert dataset_db.load() is None


class TestBaseAbimee:
    """Une base illisible ne doit pas empecher l'application de demarrer :
    l'utilisateur redepose ses fichiers, il ne debugge pas un cache."""

    def test_fichier_qui_n_est_pas_une_base(self, tmp_path):
        faux = tmp_path / "pas-une-base.sqlite3"
        faux.write_bytes(b"ceci n'est pas du SQLite")
        ancien = dataset_db.path()
        dataset_db.use_path(faux)
        try:
            assert dataset_db.load() is None
        finally:
            dataset_db.use_path(ancien)

    def test_enregistrement_sans_declaration(self):
        """Un jeu sans sinistre afficherait une file chargee que l'API
        refuserait ensuite de servir."""
        conn = sqlite3.connect(dataset_db.path())
        with conn:
            conn.executescript(dataset_db._SCHEMA)
            conn.execute(
                "INSERT INTO dataset (id, claims_filename, policies_filename, "
                "loaded_at, lignes_rejetees) VALUES (1, 'a.csv', 'b.csv', 'x', '[]')"
            )
        conn.close()
        assert dataset_db.load() is None


class TestBranchementSurLeJeuActif:
    def test_un_depot_est_enregistre(self):
        dataset.set_active(
            _CLAIMS, _POLICIES,
            source=dataset.SOURCE_DEPOT,
            claims_filename="declarations.csv",
            policies_filename="contrats.csv",
        )
        assert dataset_db.load()["claims"] == _CLAIMS

    def test_un_jeu_lu_sur_disque_n_est_PAS_enregistre(self):
        """Point central : les evaluations, le terminal et les tests chargent
        les CSV du depot. Les enregistrer ecraserait les dossiers de
        l'utilisateur, et le demarrage suivant les lui presenterait comme les
        siens."""
        dataset.set_active(
            _CLAIMS, _POLICIES,
            source=dataset.SOURCE_FICHIERS,
            claims_filename="claims_auto.csv",
            policies_filename="policies_auto.csv",
        )
        assert dataset_db.load() is None

    def test_retirer_le_jeu_efface_la_base(self):
        """DELETE /api/dataset passe par la : les donnees ne doivent pas
        rester sur le disque en attendant le prochain demarrage."""
        dataset.set_active(_CLAIMS, _POLICIES, source=dataset.SOURCE_DEPOT)
        dataset.clear()
        assert dataset_db.load() is None


class TestRestaurationAuDemarrage:
    @staticmethod
    def _simuler_un_redemarrage():
        """Vide la memoire SANS toucher a la base - ce que fait un arret du
        processus. dataset.clear() ne convient pas ici : il efface aussi la
        base, donc precisement ce qu'on veut retrouver."""
        dataset._claims = None
        dataset._policies = None
        dataset._source = None
        dataset._meta = {}

    def test_le_jeu_depose_revient_apres_un_redemarrage(self):
        dataset.set_active(
            _CLAIMS, _POLICIES,
            source=dataset.SOURCE_DEPOT,
            claims_filename="declarations.csv",
            policies_filename="contrats.csv",
            rejets=_REJETS,
        )
        depose_le = dataset.summary()["loaded_at"]

        self._simuler_un_redemarrage()
        assert dataset.is_loaded() is False

        assert dataset.restore_from_db() is True
        assert dataset.get_claims() == _CLAIMS
        assert dataset.get_policies() == _POLICIES
        # L'origine retrouvee doit rester "depot", sans quoi l'API web
        # refuserait de servir un jeu que l'utilisateur a pourtant depose.
        assert dataset.source() == dataset.SOURCE_DEPOT
        assert dataset.summary()["lignes_rejetees"] == _REJETS

    def test_la_date_de_depot_est_celle_du_depot(self):
        """Et non celle du redemarrage : l'interface affiche cette date, et la
        voir sauter a chaque relance du serveur serait un mensonge."""
        dataset.set_active(_CLAIMS, _POLICIES, source=dataset.SOURCE_DEPOT)
        depose_le = dataset.summary()["loaded_at"]

        self._simuler_un_redemarrage()
        dataset.restore_from_db()
        assert dataset.summary()["loaded_at"] == depose_le

    def test_sans_rien_d_enregistre_il_ne_se_passe_rien(self):
        self._simuler_un_redemarrage()
        assert dataset.restore_from_db() is False
        assert dataset.is_loaded() is False

    def test_une_restauration_n_ecrase_pas_un_jeu_deja_actif(self):
        """Le depot de l'utilisateur passe avant tout ce qui traine en base."""
        _enregistrer()
        actuel = {"CLM-777": dict(_CLAIMS["CLM-001"], claim_id="CLM-777")}
        dataset.set_active(actuel, _POLICIES, source=dataset.SOURCE_DEPOT)

        assert dataset.restore_from_db() is False
        assert list(dataset.get_claims()) == ["CLM-777"]
