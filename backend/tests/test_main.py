"""Tests de la commande de triage (src/main.py).

AUCUN APPEL API : agent.triage_claim est remplace par une doublure, et une
fixture interdit la construction d'un vrai client Anthropic.

L'objet de ces tests est une regle simple : aucun triage ne doit partir sans
qu'un sinistre ait ete nomme. La commande traitait auparavant les 8 sinistres
du CSV quand on l'appelait sans argument, soit 8 appels de modele sur une
faute de frappe.
"""

import sys

import pytest

import agent
import anthropic
import main


class _ClientInerte:
    """Remplace le client Anthropic. Le CONSTRUIRE ne declenche aucun reseau -
    c'est l'utiliser qui en declenche. La construction est donc autorisee (le
    code de main.py en cree un legitimement), mais tout acces a un attribut
    fait echouer le test bruyamment."""

    def __getattr__(self, name):
        raise AssertionError(
            f"appel API tente dans test_main.py (client.{name}) : ces tests "
            "doivent rester hors ligne."
        )


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    monkeypatch.setattr(anthropic, "Anthropic", lambda *args, **kwargs: _ClientInerte())


@pytest.fixture
def triages(monkeypatch):
    """Enregistre les sinistres reellement soumis a l'agent."""
    appels = []

    def _doublure(claim_id, client=None, on_event=None):
        appels.append(claim_id)
        return {"claim_id": claim_id, "output": {}, "usage": {}}

    monkeypatch.setattr(agent, "triage_claim", _doublure)
    return appels


class TestAucuneAnalyseAutomatique:
    def test_run_refuse_une_liste_vide(self, triages):
        with pytest.raises(ValueError):
            main.run([])
        assert triages == [], "aucun sinistre ne doit avoir ete traite"

    def test_run_refuse_none(self, triages):
        with pytest.raises(ValueError):
            main.run(None)  # type: ignore[arg-type]
        assert triages == []

    def test_ligne_de_commande_sans_argument_ne_lance_rien(self, monkeypatch, triages):
        # argparse sort avec le code 2 et affiche l'aide, avant tout appel.
        monkeypatch.setattr(sys, "argv", ["main.py"])
        with pytest.raises(SystemExit) as sortie:
            main.main()
        assert sortie.value.code == 2
        assert triages == []

    def test_le_fichier_complet_n_est_jamais_parcouru_par_defaut(self, triages):
        """Garde-fou explicite : main.py ne doit plus connaitre de chemin qui
        enumere tous les sinistres du CSV."""
        assert not hasattr(main, "list_claim_ids"), (
            "main.py ne doit plus importer list_claim_ids : c'est ce qui "
            "permettait de traiter tout le fichier sans argument."
        )


class TestTraitementNomme:
    def test_un_seul_sinistre(self, triages):
        resultats = main.run(["CLM-001"], client=object())
        assert triages == ["CLM-001"]
        assert [r["claim_id"] for r in resultats] == ["CLM-001"]

    def test_plusieurs_sinistres_dans_l_ordre_donne(self, triages):
        main.run(["CLM-003", "CLM-001"], client=object())
        assert triages == ["CLM-003", "CLM-001"]

    def test_ligne_de_commande_avec_arguments(self, monkeypatch, triages, capsys):
        monkeypatch.setattr(sys, "argv", ["main.py", "CLM-001", "CLM-002"])
        main.main()
        assert triages == ["CLM-001", "CLM-002"]

        # stdout doit rester du JSON pur : le cout part sur stderr.
        capture = capsys.readouterr()
        import json

        assert [r["claim_id"] for r in json.loads(capture.out)] == ["CLM-001", "CLM-002"]
        assert "[cost]" in capture.err
