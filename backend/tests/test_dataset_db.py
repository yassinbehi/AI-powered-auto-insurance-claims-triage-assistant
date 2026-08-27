"""Tests de la base SQLite des jeux de donnees (src/dataset_db.py) et de son
branchement sur le jeu actif (src/dataset.py).

La base est deja detournee vers un fichier temporaire par la fixture
`base_a_l_ecart` de conftest.py : aucun test d'ici n'approche la base de
l'utilisateur.
"""

import json
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


def _enregistrer(nom="Sinistres juillet", claims=None, loaded_at="2026-08-27T10:00:00+00:00"):
    return dataset_db.save(
        nom,
        claims if claims is not None else _CLAIMS,
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


class TestNom:
    def test_les_espaces_sont_normalises(self):
        assert dataset_db.valider_nom("  Sinistres   juillet  ") == "Sinistres juillet"

    @pytest.mark.parametrize("nom", ["", "   ", "\t\n"])
    def test_un_nom_vide_est_refuse(self, nom):
        """Le nom est ce qui permet de reconnaitre un jeu dans la liste : sans
        lui, l'utilisateur choisit entre deux lignes identiques."""
        with pytest.raises(dataset_db.NomInvalide):
            dataset_db.valider_nom(nom)

    def test_un_nom_trop_long_est_refuse(self):
        with pytest.raises(dataset_db.NomInvalide):
            dataset_db.valider_nom("x" * (dataset_db.NOM_LONGUEUR_MAX + 1))

    def test_un_nom_deja_pris_est_refuse(self):
        """Refuse et non remplace : ecraser un jeu sur une collision de nom
        ferait perdre du travail sans le dire."""
        _enregistrer(nom="Juillet")
        with pytest.raises(dataset_db.NomDejaPris):
            _enregistrer(nom="Juillet")

    def test_la_casse_ne_cree_pas_deux_jeux(self):
        _enregistrer(nom="Juillet")
        with pytest.raises(dataset_db.NomDejaPris):
            _enregistrer(nom="JUILLET")

    def test_le_jeu_refuse_ne_laisse_pas_de_trace(self):
        """La transaction est annulee : ni sinistre orphelin, ni deuxieme
        ligne dans la liste."""
        _enregistrer(nom="Juillet")
        with pytest.raises(dataset_db.NomDejaPris):
            _enregistrer(nom="Juillet")
        assert len(dataset_db.liste()) == 1


class TestAllerRetour:
    def test_base_vide_ne_rend_rien(self):
        """None et non un jeu vide : l'application demarre alors sur son ecran
        de depot, comme avant l'existence de la base."""
        assert dataset_db.load() is None
        assert dataset_db.liste() == []

    def test_ce_qui_est_enregistre_est_relu_a_l_identique(self):
        _enregistrer()
        lu = dataset_db.load()

        assert lu["nom"] == "Sinistres juillet"
        assert lu["claims"] == _CLAIMS
        assert lu["policies"] == _POLICIES
        assert lu["claims_filename"] == "declarations.csv"
        assert lu["loaded_at"] == "2026-08-27T10:00:00+00:00"
        assert lu["lignes_rejetees"] == _REJETS

    def test_les_accents_survivent(self):
        dataset_db.save(
            "Été 2026",
            {"CLM-1": dict(_CLAIMS["CLM-001"], description_client="Pare-brise fissuré à Béja")},
            _POLICIES,
            claims_filename="a.csv", policies_filename="b.csv",
            loaded_at="2026-08-27T10:00:00+00:00",
        )
        lu = dataset_db.load()
        assert lu["nom"] == "Été 2026"
        assert lu["claims"]["CLM-1"]["description_client"] == "Pare-brise fissuré à Béja"

    def test_un_depot_devient_le_jeu_actif(self):
        _enregistrer(nom="Premier")
        second = _enregistrer(nom="Second", claims={"CLM-9": _CLAIMS["CLM-001"]})
        assert dataset_db.load()["id"] == second

    def test_les_jeux_ne_se_melangent_pas(self):
        """Deux jeux peuvent contenir les memes identifiants : chacun doit
        rendre les siens."""
        premier = _enregistrer(nom="Premier")
        autre = {"CLM-001": dict(_CLAIMS["CLM-001"], devis_tnd=9999)}
        second = _enregistrer(nom="Second", claims=autre)

        assert dataset_db.load(premier)["claims"]["CLM-001"]["devis_tnd"] == 2400
        assert dataset_db.load(second)["claims"]["CLM-001"]["devis_tnd"] == 9999


class TestListe:
    def test_le_plus_recent_d_abord_et_l_actif_est_marque(self):
        _enregistrer(nom="Ancien", loaded_at="2026-01-01T00:00:00+00:00")
        recent = _enregistrer(nom="Recent", loaded_at="2026-08-01T00:00:00+00:00")

        noms = [j["nom"] for j in dataset_db.liste()]
        assert noms == ["Recent", "Ancien"]

        actifs = [j["nom"] for j in dataset_db.liste() if j["actif"]]
        assert actifs == ["Recent"]
        assert dataset_db.load()["id"] == recent

    def test_les_comptes_sont_ceux_du_jeu(self):
        _enregistrer(nom="Deux", claims={"A": _CLAIMS["CLM-001"], "B": _CLAIMS["CLM-001"]})
        ligne = dataset_db.liste()[0]
        assert ligne["claims_count"] == 2
        assert ligne["policies_count"] == 1


class TestChangerDeJeu:
    def test_activer_change_le_jeu_rendu(self):
        premier = _enregistrer(nom="Premier")
        _enregistrer(nom="Second")

        assert dataset_db.activer(premier) is True
        assert dataset_db.load()["nom"] == "Premier"

    def test_activer_un_inconnu_ne_change_rien(self):
        _enregistrer(nom="Premier")
        assert dataset_db.activer(4242) is False
        assert dataset_db.load()["nom"] == "Premier"

    def test_desactiver_ne_supprime_pas(self):
        """« Changer de fichiers » ferme le jeu ; il doit rester dans la
        liste, sans quoi le nommer n'aurait servi a rien."""
        _enregistrer(nom="Premier")
        dataset_db.desactiver()

        assert dataset_db.load() is None
        assert [j["nom"] for j in dataset_db.liste()] == ["Premier"]
        assert all(j["actif"] is False for j in dataset_db.liste())


class TestSuppression:
    def test_supprimer_emporte_le_contenu(self):
        """ON DELETE CASCADE : rien de l'utilisateur ne doit rester sur le
        disque apres une suppression demandee."""
        premier = _enregistrer(nom="Premier")
        assert dataset_db.supprimer(premier) is True

        assert dataset_db.liste() == []
        conn = sqlite3.connect(dataset_db.path())
        try:
            assert next(conn.execute("SELECT COUNT(*) FROM claims"))[0] == 0
            assert next(conn.execute("SELECT COUNT(*) FROM policies"))[0] == 0
        finally:
            conn.close()

    def test_supprimer_un_inconnu(self):
        assert dataset_db.supprimer(4242) is False

    def test_supprimer_le_jeu_actif_ne_laisse_aucun_actif(self):
        premier = _enregistrer(nom="Premier")
        _enregistrer(nom="Second")
        dataset_db.activer(premier)

        dataset_db.supprimer(premier)
        assert dataset_db.load() is None
        assert [j["nom"] for j in dataset_db.liste()] == ["Second"]


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
            assert dataset_db.liste() == []
        finally:
            dataset_db.use_path(ancien)

    def test_enregistrement_sans_declaration(self):
        """Un jeu sans sinistre afficherait une file chargee que l'API
        refuserait ensuite de servir."""
        conn = sqlite3.connect(dataset_db.path())
        try:
            with conn:
                conn.execute(
                    "INSERT INTO datasets (nom, claims_filename, policies_filename, "
                    "loaded_at, lignes_rejetees) VALUES ('Vide', 'a.csv', 'b.csv', 'x', '[]')"
                )
                conn.execute(
                    "INSERT INTO actif (id, dataset_id) VALUES "
                    "(1, (SELECT id FROM datasets WHERE nom = 'Vide'))"
                )
        finally:
            conn.close()
        assert dataset_db.load() is None


class TestMigrationDepuisLAncienFormat:
    """La version precedente n'enregistrait qu'un seul jeu, sans nom. Une base
    ecrite par elle doit etre reprise, pas jetee : perdre les donnees d'un
    utilisateur parce que le format a change lui ferait perdre confiance dans
    cette base."""

    @staticmethod
    def _ecrire_ancienne_base(chemin):
        conn = sqlite3.connect(chemin)
        try:
            with conn:
                conn.executescript("""
                    CREATE TABLE dataset (
                        id INTEGER PRIMARY KEY CHECK (id = 1),
                        claims_filename TEXT NOT NULL,
                        policies_filename TEXT NOT NULL,
                        loaded_at TEXT NOT NULL,
                        lignes_rejetees TEXT NOT NULL);
                    CREATE TABLE claims (claim_id TEXT PRIMARY KEY, data TEXT NOT NULL);
                    CREATE TABLE policies (policy_id TEXT PRIMARY KEY, data TEXT NOT NULL);
                """)
                conn.execute(
                    "INSERT INTO dataset VALUES (1, 'claims_auto.csv', 'policies_auto.csv', "
                    "'2026-08-01T09:00:00+00:00', ?)",
                    (json.dumps(_REJETS),),
                )
                conn.execute(
                    "INSERT INTO claims VALUES (?, ?)",
                    ("CLM-001", json.dumps(_CLAIMS["CLM-001"])),
                )
                conn.execute(
                    "INSERT INTO policies VALUES (?, ?)",
                    ("POL-002", json.dumps(_POLICIES["POL-002"])),
                )
        finally:
            conn.close()

    def test_l_ancien_jeu_est_repris_nomme_et_actif(self, tmp_path):
        chemin = tmp_path / "ancienne.sqlite3"
        self._ecrire_ancienne_base(chemin)

        precedent = dataset_db.path()
        dataset_db.use_path(chemin)
        try:
            lu = dataset_db.load()
            assert lu is not None
            assert lu["claims"] == _CLAIMS
            assert lu["policies"] == _POLICIES
            # Nom tire du fichier, faute d'en avoir eu un.
            assert lu["nom"] == "claims_auto"
            # La date de depot d'origine est conservee.
            assert lu["loaded_at"] == "2026-08-01T09:00:00+00:00"
            assert lu["lignes_rejetees"] == _REJETS
            assert [j["actif"] for j in dataset_db.liste()] == [True]
        finally:
            dataset_db.use_path(precedent)

    def test_une_reprise_impossible_conserve_les_donnees_d_origine(self, tmp_path, capsys):
        """Le point important : une reprise ratee ne doit pas ressembler a une
        base vide. Les tables d'origine sont mises de cote sous _v1 et un
        message le dit - sans quoi un jeu disparu passerait pour un jeu jamais
        depose, et personne ne saurait qu'il y a eu un probleme."""
        chemin = tmp_path / "ancienne.sqlite3"
        self._ecrire_ancienne_base(chemin)
        # Contenu que la reprise ne saura pas relire.
        conn = sqlite3.connect(chemin)
        with conn:
            conn.execute("UPDATE claims SET data = 'ceci n est pas du JSON'")
        conn.close()

        precedent = dataset_db.path()
        dataset_db.use_path(chemin)
        try:
            assert dataset_db.load() is None
            assert "reprise de l'ancien format impossible" in capsys.readouterr().err

            conn = sqlite3.connect(chemin)
            try:
                tables = {
                    r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
                }
                assert {"dataset_v1", "claims_v1", "policies_v1"} <= tables
                assert next(conn.execute("SELECT COUNT(*) FROM claims_v1"))[0] == 1
            finally:
                conn.close()
        finally:
            dataset_db.use_path(precedent)

    def test_la_migration_ne_se_rejoue_pas(self, tmp_path):
        chemin = tmp_path / "ancienne.sqlite3"
        self._ecrire_ancienne_base(chemin)

        precedent = dataset_db.path()
        dataset_db.use_path(chemin)
        try:
            dataset_db.load()
            dataset_db.load()
            assert len(dataset_db.liste()) == 1
        finally:
            dataset_db.use_path(precedent)


class TestBranchementSurLeJeuActif:
    def test_un_depot_est_enregistre_sous_son_nom(self):
        dataset.set_active(
            _CLAIMS, _POLICIES,
            source=dataset.SOURCE_DEPOT,
            claims_filename="declarations.csv",
            policies_filename="contrats.csv",
            nom="Sinistres juillet",
        )
        assert dataset_db.load()["nom"] == "Sinistres juillet"
        assert dataset.summary()["nom"] == "Sinistres juillet"

    def test_un_jeu_lu_sur_disque_n_est_PAS_enregistre(self):
        """Point central : les evaluations, le terminal et les tests chargent
        les CSV du depot. Les enregistrer ecraserait les jeux de
        l'utilisateur, et le demarrage suivant les lui presenterait comme les
        siens."""
        dataset.set_active(
            _CLAIMS, _POLICIES,
            source=dataset.SOURCE_FICHIERS,
            claims_filename="claims_auto.csv",
            policies_filename="policies_auto.csv",
        )
        assert dataset_db.liste() == []

    def test_fermer_le_jeu_ne_le_supprime_pas(self):
        dataset.set_active(_CLAIMS, _POLICIES, source=dataset.SOURCE_DEPOT, nom="Juillet")
        dataset.clear()

        assert dataset.is_loaded() is False
        assert [j["nom"] for j in dataset.liste()] == ["Juillet"]

    def test_changer_de_jeu_remplace_tout_ce_qui_etait_en_memoire(self):
        dataset.set_active(_CLAIMS, _POLICIES, source=dataset.SOURCE_DEPOT, nom="Premier")
        premier_id = dataset.summary()["dataset_id"]

        autres = {"CLM-777": dict(_CLAIMS["CLM-001"], claim_id="CLM-777")}
        dataset.set_active(autres, _POLICIES, source=dataset.SOURCE_DEPOT, nom="Second")
        assert list(dataset.get_claims()) == ["CLM-777"]

        assert dataset.activer(premier_id) is True
        # Aucun sinistre du jeu precedent ne survit au changement.
        assert list(dataset.get_claims()) == ["CLM-001"]
        assert dataset.summary()["nom"] == "Premier"
        # L'origine reste "depot", sans quoi l'API refuserait de servir un jeu
        # que l'utilisateur a pourtant depose.
        assert dataset.source() == dataset.SOURCE_DEPOT

    def test_supprimer_le_jeu_actif_vide_l_application(self):
        dataset.set_active(_CLAIMS, _POLICIES, source=dataset.SOURCE_DEPOT, nom="Juillet")
        actif = dataset.summary()["dataset_id"]

        assert dataset.supprimer(actif) is True
        assert dataset.is_loaded() is False
        assert dataset.liste() == []

    def test_supprimer_un_autre_jeu_ne_touche_pas_a_l_actif(self):
        dataset.set_active(_CLAIMS, _POLICIES, source=dataset.SOURCE_DEPOT, nom="Premier")
        premier = dataset.summary()["dataset_id"]
        dataset.set_active(_CLAIMS, _POLICIES, source=dataset.SOURCE_DEPOT, nom="Second")

        assert dataset.supprimer(premier) is True
        assert dataset.is_loaded() is True
        assert dataset.summary()["nom"] == "Second"


class TestRestaurationAuDemarrage:
    @staticmethod
    def _simuler_un_redemarrage():
        """Vide la memoire SANS toucher a la base - ce que fait un arret du
        processus. dataset.clear() ne convient pas ici : il retire aussi le
        marqueur d'activation, donc precisement ce qu'on veut retrouver."""
        dataset._claims = None
        dataset._policies = None
        dataset._source = None
        dataset._meta = {}

    def test_le_jeu_actif_revient_apres_un_redemarrage(self):
        dataset.set_active(
            _CLAIMS, _POLICIES,
            source=dataset.SOURCE_DEPOT,
            claims_filename="declarations.csv",
            policies_filename="contrats.csv",
            rejets=_REJETS,
            nom="Sinistres juillet",
        )

        self._simuler_un_redemarrage()
        assert dataset.is_loaded() is False

        assert dataset.restore_from_db() is True
        assert dataset.get_claims() == _CLAIMS
        assert dataset.summary()["nom"] == "Sinistres juillet"
        assert dataset.summary()["lignes_rejetees"] == _REJETS

    def test_la_date_de_depot_est_celle_du_depot(self):
        """Et non celle du redemarrage : l'interface affiche cette date, et la
        voir sauter a chaque relance du serveur serait un mensonge."""
        dataset.set_active(_CLAIMS, _POLICIES, source=dataset.SOURCE_DEPOT, nom="Juillet")
        depose_le = dataset.summary()["loaded_at"]

        self._simuler_un_redemarrage()
        dataset.restore_from_db()
        assert dataset.summary()["loaded_at"] == depose_le

    def test_un_jeu_ferme_ne_revient_pas_tout_seul(self):
        """Fermer puis redemarrer doit rendre l'ecran de depot, pas le jeu
        qu'on venait de fermer - meme s'il est toujours enregistre."""
        dataset.set_active(_CLAIMS, _POLICIES, source=dataset.SOURCE_DEPOT, nom="Juillet")
        dataset.clear()

        self._simuler_un_redemarrage()
        assert dataset.restore_from_db() is False
        assert [j["nom"] for j in dataset.liste()] == ["Juillet"]

    def test_sans_rien_d_enregistre_il_ne_se_passe_rien(self):
        self._simuler_un_redemarrage()
        assert dataset.restore_from_db() is False
        assert dataset.is_loaded() is False

    def test_une_restauration_n_ecrase_pas_un_jeu_deja_actif(self):
        _enregistrer(nom="En base")
        dataset.set_active(
            {"CLM-777": _CLAIMS["CLM-001"]}, _POLICIES,
            source=dataset.SOURCE_DEPOT, nom="Depose a l'instant",
        )

        assert dataset.restore_from_db() is False
        assert list(dataset.get_claims()) == ["CLM-777"]
