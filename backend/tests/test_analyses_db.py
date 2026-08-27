"""Tests de l'historique des analyses (src/analyses_db.py).

La base est deja detournee vers un fichier temporaire par la fixture
`base_a_l_ecart` de conftest.py.
"""

import sqlite3

import pytest

import analyses_db
import dataset
import dataset_db


_SORTIE = {
    "claim_id": "CLM-001",
    "triage": "traitement_standard",
    "priorite": "normale",
    "garantie_applicable": True,
    "pieces_manquantes": [],
    "signaux_fraude": [],
    "fourchette_reparation_tnd": {"min": 1800, "max": 2600},
    "prochaine_action": "Ouvrir le dossier et missionner un reparateur agree.",
    "message_client": "Votre sinistre est pris en charge.",
    "validation_humaine_requise": False,
}

_REUSSITE = {
    "claim_id": "CLM-001",
    "output": _SORTIE,
    "validation_errors": [],
    "tool_call_trace": [{"tool": "get_claim", "input": {}, "output": {}}],
    "usage": {"input_tokens": 3243, "output_tokens": 538},
    "model": "claude-haiku-4-5-20251001",
    "cost_usd": 0.0177,
}

_ECHEC = {
    "claim_id": "CLM-002",
    "error": "La reponse finale du modele n'est pas un JSON valide.",
    "raw_output": "{ pas du json",
    "tool_call_trace": [],
    "usage": {"input_tokens": 900, "output_tokens": 100},
    "model": "claude-sonnet-4-6",
    "cost_usd": 0.0042,
}


@pytest.fixture(autouse=True)
def base_vide():
    dataset_db.clear()
    analyses_db.vider()
    yield
    analyses_db.vider()
    dataset_db.clear()


class TestEnregistrement:
    def test_une_analyse_reussie_est_conservee(self):
        analyses_db.enregistrer(_REUSSITE, dataset_id=None, dataset_nom="Sinistres juillet")

        ligne = analyses_db.liste()[0]
        assert ligne["claim_id"] == "CLM-001"
        assert ligne["triage"] == "traitement_standard"
        assert ligne["priorite"] == "normale"
        assert ligne["model"] == "claude-haiku-4-5-20251001"
        assert ligne["cost_usd"] == pytest.approx(0.0177)
        assert ligne["dataset_nom"] == "Sinistres juillet"
        assert ligne["erreur"] is None

    def test_un_echec_est_conserve_lui_aussi(self):
        """Une analyse interrompue a ete facturee : un historique qui ne
        montrerait que les reussites donnerait une image fausse de la
        depense."""
        analyses_db.enregistrer(_ECHEC, dataset_nom="Sinistres juillet")

        ligne = analyses_db.liste()[0]
        assert ligne["triage"] is None
        assert ligne["erreur"].startswith("La reponse finale")
        assert ligne["cost_usd"] == pytest.approx(0.0042)

    def test_le_contrat_de_sortie_est_relu_a_l_identique(self):
        identifiant = analyses_db.enregistrer(_REUSSITE, dataset_nom="Juillet")
        assert analyses_db.get(identifiant)["output"] == _SORTIE

    def test_la_liste_ne_transporte_pas_le_contrat(self):
        """Un tableau n'a pas besoin de cinquante contrats complets pour
        afficher cinquante lignes."""
        analyses_db.enregistrer(_REUSSITE, dataset_nom="Juillet")
        assert "output" not in analyses_db.liste()[0]

    def test_les_ecarts_de_schema_sont_conserves(self):
        resultat = dict(_REUSSITE, validation_errors=["priorite absente"])
        identifiant = analyses_db.enregistrer(resultat, dataset_nom="Juillet")
        assert analyses_db.get(identifiant)["validation_errors"] == ["priorite absente"]

    def test_la_plus_recente_d_abord(self):
        analyses_db.enregistrer(dict(_REUSSITE, claim_id="CLM-001"), dataset_nom="J")
        analyses_db.enregistrer(dict(_REUSSITE, claim_id="CLM-002"), dataset_nom="J")
        assert [a["claim_id"] for a in analyses_db.liste()] == ["CLM-002", "CLM-001"]

    def test_une_analyse_inconnue(self):
        assert analyses_db.get(4242) is None


class TestEcritureImpossible:
    def test_un_historique_qui_ne_s_ecrit_pas_ne_casse_pas_l_analyse(self, tmp_path, capsys):
        """L'analyse vient d'etre payee et affichee : elle ne doit pas echouer
        parce que l'archivage a echoue. L'incident part sur stderr."""
        faux = tmp_path / "pas-une-base.sqlite3"
        faux.write_bytes(b"ceci n'est pas du SQLite")
        precedent = dataset_db.path()
        dataset_db.use_path(faux)
        try:
            assert analyses_db.enregistrer(_REUSSITE, dataset_nom="Juillet") is None
            assert "historique non ecrit" in capsys.readouterr().err
        finally:
            dataset_db.use_path(precedent)


class TestSuppression:
    def test_supprimer_une_analyse(self):
        identifiant = analyses_db.enregistrer(_REUSSITE, dataset_nom="Juillet")
        assert analyses_db.supprimer(identifiant) is True
        assert analyses_db.liste() == []

    def test_supprimer_une_analyse_inconnue(self):
        assert analyses_db.supprimer(4242) is False


class TestLienAvecLeJeuDeDonnees:
    def test_supprimer_le_jeu_ne_supprime_pas_l_historique(self):
        """Le point important : une analyse a eu lieu et a coute de l'argent.
        Supprimer les fichiers d'origine ne doit pas effacer la trace de ce
        qui a ete fait."""
        dataset.set_active(
            {"CLM-001": {"claim_id": "CLM-001"}},
            {"POL-001": {"policy_id": "POL-001"}},
            source=dataset.SOURCE_DEPOT,
            nom="Sinistres juillet",
        )
        jeu = dataset.summary()["dataset_id"]
        analyses_db.enregistrer(_REUSSITE, dataset_id=jeu, dataset_nom="Sinistres juillet")

        dataset.supprimer(jeu)

        ligne = analyses_db.liste()[0]
        assert ligne["dataset_id"] is None       # ON DELETE SET NULL
        assert ligne["dataset_nom"] == "Sinistres juillet"  # recopie, donc lisible
        assert ligne["cost_usd"] == pytest.approx(0.0177)


class TestArchivageParLApi:
    """api._archiver est le point de couture entre le triage et l'historique :
    c'est lui qui tourne a la fin des DEUX chemins de triage (bloquant et
    SSE). Le tester vaut mieux que payer une analyse pour s'en assurer."""

    def test_le_jeu_actif_est_attache_a_l_analyse(self):
        import api

        dataset.set_active(
            {"CLM-001": {"claim_id": "CLM-001"}},
            {"POL-001": {"policy_id": "POL-001"}},
            source=dataset.SOURCE_DEPOT,
            nom="Sinistres juillet",
        )
        api._archiver(_REUSSITE)

        ligne = analyses_db.liste()[0]
        assert ligne["claim_id"] == "CLM-001"
        assert ligne["dataset_nom"] == "Sinistres juillet"
        assert ligne["dataset_id"] == dataset.summary()["dataset_id"]
        assert ligne["cost_usd"] == pytest.approx(0.0177)

    def test_sans_jeu_actif_l_analyse_est_quand_meme_conservee(self):
        """Cas limite : le jeu a ete ferme entre le lancement et la fin de
        l'analyse. Le resultat a ete paye, il doit rester."""
        import api

        dataset.clear()
        api._archiver(_REUSSITE)

        ligne = analyses_db.liste()[0]
        assert ligne["dataset_id"] is None
        assert ligne["dataset_nom"] == ""


class TestTotalDuCout:
    def test_somme_des_couts(self):
        analyses_db.enregistrer(_REUSSITE, dataset_nom="J")
        analyses_db.enregistrer(_ECHEC, dataset_nom="J")
        assert analyses_db.total_cout_usd() == pytest.approx(0.0177 + 0.0042)

    def test_sans_analyse(self):
        assert analyses_db.total_cout_usd() == 0.0
