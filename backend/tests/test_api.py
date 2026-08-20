"""Tests de la couche HTTP (src/api.py).

AUCUN APPEL API. Deux mecanismes garantissent que ces tests restent hors
ligne :

  - une fixture autouse remplace anthropic.Anthropic par un objet qui leve
    des l'instanciation : toute tentative de contacter le modele echoue
    bruyamment au lieu de partir sur le reseau ;
  - les endpoints payants sont testes avec agent.triage_claim et
    guard.classify_client_text remplaces par des doublures.

Les endpoints gratuits, eux, sont exerces pour de vrai contre les CSV de
data/ : c'est justement ce qui doit fonctionner sans cle API.
"""

import json

import pytest
from fastapi.testclient import TestClient

import agent
import api
import guard
from api import app
from tools import list_claim_ids

client = TestClient(app)


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Filet de securite : aucun test de ce fichier ne doit pouvoir construire
    un vrai client Anthropic."""

    def _forbidden(*args, **kwargs):
        raise AssertionError(
            "Un test de test_api.py a tente de creer un client Anthropic : "
            "un appel de modele s'est glisse dans un chemin cense etre gratuit."
        )

    monkeypatch.setattr(guard.anthropic, "Anthropic", _forbidden)
    guard.reset_screening_cache()
    guard.reset_guard_usage()
    yield
    guard.reset_screening_cache()
    guard.reset_guard_usage()


def _parse_sse(text: str) -> list:
    """Decoupe une reponse text/event-stream en couples (evenement, donnees).
    Les commentaires de heartbeat (`: ping`) sont ignores."""
    frames = []
    for block in text.split("\n\n"):
        block = block.strip()
        if not block or block.startswith(":"):
            continue
        event = None
        data = None
        for line in block.split("\n"):
            if line.startswith("event: "):
                event = line[len("event: "):]
            elif line.startswith("data: "):
                data = json.loads(line[len("data: "):])
        frames.append((event, data))
    return frames


# =============================================================================
# Endpoints gratuits
# =============================================================================

class TestEndpointsGratuits:
    def test_health(self):
        body = client.get("/api/health").json()
        assert body["status"] == "ok"
        assert body["model"]

    def test_file_d_attente_liste_tous_les_sinistres(self):
        response = client.get("/api/claims")
        assert response.status_code == 200
        assert len(response.json()) == len(list_claim_ids())

    def test_file_d_attente_joint_la_police(self):
        row = next(c for c in client.get("/api/claims").json() if c["claim_id"] == "CLM-001")
        assert row["assure"], "la file doit etre lisible sans ouvrir le dossier"
        assert row["formule"]

    def test_fiche_dossier_complete(self):
        body = client.get("/api/claims/CLM-001").json()
        assert set(body) == {
            "claim", "policy", "coverage", "repair_band", "fraud_signals", "screening",
        }
        assert body["claim"]["claim_id"] == "CLM-001"
        assert body["policy"]["policy_id"] == body["claim"]["policy_id"]

    def test_fiche_dossier_ne_declenche_aucun_appel_de_modele(self, monkeypatch):
        # Complete la fixture _no_network : ici c'est la couche [2] elle-meme
        # qui doit rester intouchee, meme si un client existait deja.
        def _forbidden(*args, **kwargs):
            raise AssertionError("la couche [2] ne doit pas etre appelee ici")

        monkeypatch.setattr(guard, "_call_classifier", _forbidden)
        for claim_id in list_claim_ids():
            assert client.get(f"/api/claims/{claim_id}").status_code == 200

    def test_police_seule(self):
        assert client.get("/api/policies/POL-002").json()["formule"] == "tous_risques"

    def test_regles_servies_telles_quelles(self):
        documents = client.get("/api/rules").json()["documents"]
        noms = {d["name"] for d in documents}
        assert noms == {"regles_sinistres.md", "contrat_sortie.md"}
        assert all(d["content"].strip() for d in documents)

    def test_sinistre_inconnu(self):
        assert client.get("/api/claims/CLM-999").status_code == 404

    def test_police_inconnue(self):
        assert client.get("/api/policies/POL-999").status_code == 404


# =============================================================================
# Point de vigilance 1 : les colonnes de reference ne sortent jamais
# =============================================================================

class TestFuiteDesReponsesAttendues:
    """claims_auto.csv contient priorite_attendue et triage_attendu, qui sont
    les reponses attendues des evals. Les exposer par HTTP rendrait toute
    mesure de qualite sans valeur."""

    INTERDIT = ("priorite_attendue", "triage_attendu")

    def _assert_propre(self, payload):
        brut = json.dumps(payload, ensure_ascii=False)
        for colonne in self.INTERDIT:
            assert colonne not in brut, f"{colonne} ne doit jamais sortir par HTTP"

    def test_file_d_attente(self):
        self._assert_propre(client.get("/api/claims").json())

    def test_chaque_fiche_dossier(self):
        for claim_id in list_claim_ids():
            self._assert_propre(client.get(f"/api/claims/{claim_id}").json())

    def test_le_module_api_n_importe_pas_le_lecteur_de_labels(self):
        # get_claim_eval_labels est la seule fonction qui lit ces colonnes.
        assert not hasattr(api, "get_claim_eval_labels")


# =============================================================================
# Filtre anti-injection expose par l'API
# =============================================================================

class TestScreeningExpose:
    def test_absence_de_verdict_sur_la_fiche_gratuite(self):
        # CLM-001 : aucun marqueur connu. Sans la couche [2], il n'y a pas de
        # verdict - et surtout pas un SAFE fabrique.
        screening = client.get("/api/claims/CLM-001").json()["screening"]
        assert screening["verdict"] is None
        assert screening["classifier_called"] is False
        assert screening["redacted"] is False

    def test_injection_detectee_sans_appel_de_modele(self):
        # CLM-002 contient "approuver le paiement" / "sans verifier" : la
        # couche [1] tranche seule, gratuitement.
        screening = client.get("/api/claims/CLM-002").json()["screening"]
        assert screening["verdict"] == "INJECTION"
        assert screening["markers_found"]
        assert screening["classifier_called"] is False
        assert screening["redacted"] is True

    def test_texte_injecte_ne_sort_pas_de_l_api(self):
        """Le texte redige par le client ne franchit pas la frontiere HTTP.

        A ne pas confondre avec `markers_found`, qui sort bien : ses entrees
        proviennent de guard.INJECTION_MARKERS, un vocabulaire fixe du depot,
        et non de ce que le client a ecrit. C'est la trace du filtre, et
        l'interface a besoin de l'afficher.
        """
        body = client.get("/api/claims/CLM-002").json()
        brut = json.dumps(body, ensure_ascii=False)

        # Phrases propres a CLM-002 dans claims_auto.csv.
        assert "Pare-brise fissure sur autoroute" not in brut
        assert "sans verifier la police" not in brut
        assert "original_text" not in brut

        # Ce qui reste visible : le placeholder et le vocabulaire du filtre.
        assert body["screening"]["text_for_model"] == guard.REDACTED_PLACEHOLDER
        assert set(body["screening"]["markers_found"]) <= set(guard.INJECTION_MARKERS)

    def test_marqueurs_signales_dans_la_file(self):
        rows = {c["claim_id"]: c for c in client.get("/api/claims").json()}
        assert rows["CLM-002"]["injection_markers_found"]
        assert rows["CLM-006"]["injection_markers_found"]
        assert rows["CLM-001"]["injection_markers_found"] == []

    def test_consultation_gratuite_ne_pollue_pas_le_memo(self, monkeypatch):
        """Une fiche consultee sans classifieur ne doit pas empecher le triage
        suivant d'executer la couche [2] sur le meme sinistre."""
        assert client.get("/api/claims/CLM-001").status_code == 200

        appels = []

        def _doublure(text, client=None, use_classifier=True):
            appels.append(use_classifier)
            return {
                "verdict": "SAFE",
                "markers_found": [],
                "classifier_available": True,
                "classifier_called": True,
                "text_for_model": guard.wrap_untrusted(text),
                "original_text": text,
            }

        monkeypatch.setattr(guard, "classify_client_text", _doublure)

        body = client.post("/api/claims/CLM-001/screen").json()
        assert body["verdict"] == "SAFE"
        assert appels == [True], "la couche [2] doit bien avoir ete sollicitee"


# =============================================================================
# Point de vigilance 2 : serialisation du travail payant
# =============================================================================

class TestVerrou:
    def test_second_triage_refuse(self):
        api._RUN_LOCK.acquire()
        try:
            assert client.post("/api/triage/CLM-001").status_code == 409
            assert client.post("/api/claims/CLM-001/screen").status_code == 409
        finally:
            api._RUN_LOCK.release()

    def test_verrou_libere_apres_un_triage(self, monkeypatch):
        monkeypatch.setattr(
            agent, "triage_claim",
            lambda claim_id, client=None, on_event=None: {"claim_id": claim_id, "output": {}},
        )
        assert client.post("/api/triage/CLM-001").status_code == 200
        assert not api._RUN_LOCK.locked(), "le verrou doit etre rendu"

    def test_sinistre_inconnu_ne_prend_pas_le_verrou(self):
        assert client.post("/api/triage/CLM-999").status_code == 404
        assert not api._RUN_LOCK.locked()


# =============================================================================
# Point de vigilance 3 : un GET ne declenche pas un triage par accident
# =============================================================================

class TestGardeFouSSE:
    def test_confirm_obligatoire(self):
        assert client.get("/api/triage/CLM-001/stream").status_code == 400
        assert client.get("/api/triage/CLM-001/stream?confirm=0").status_code == 400

    def test_confirm_refuse_ne_prend_pas_le_verrou(self):
        client.get("/api/triage/CLM-001/stream")
        assert not api._RUN_LOCK.locked()

    def test_sinistre_inconnu_avant_tout_lancement(self):
        assert client.get("/api/triage/CLM-999/stream?confirm=1").status_code == 404


# =============================================================================
# Forme des trames SSE
# =============================================================================

def _triage_scripte(claim_id, client=None, on_event=None):
    """Doublure de agent.triage_claim : rejoue une sequence d'evenements
    representative d'un triage reel, sans appel de modele."""
    resultat = {
        "claim_id": claim_id,
        "output": {"claim_id": claim_id, "triage": "traitement_standard"},
        "validation_errors": [],
        "tool_call_trace": [],
        "usage": {"input_tokens": 10, "output_tokens": 2},
    }
    on_event({"type": "run_started", "claim_id": claim_id, "model": "doublure"})
    on_event({"type": "turn_started", "turn": 1})
    on_event({"type": "tool_use", "turn": 1, "tool": "get_claim", "input": {"claim_id": claim_id}})
    on_event({"type": "tool_result", "turn": 1, "tool": "get_claim", "output": {"claim_id": claim_id}})
    on_event({"type": "turn_completed", "turn": 1, "usage": {"input_tokens": 10}})
    on_event({"type": "turn_started", "turn": 2})
    # Un JSON contenant un retour a la ligne : il ne doit pas couper la trame.
    on_event({"type": "text_delta", "text": '{\n  "claim_id"'})
    on_event({"type": "result", **resultat})
    return resultat


class TestFluxSSE:
    def _frames(self, monkeypatch, claim_id="CLM-001"):
        monkeypatch.setattr(agent, "triage_claim", _triage_scripte)
        response = client.get(f"/api/triage/{claim_id}/stream?confirm=1")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        return _parse_sse(response.text)

    def test_sequence_complete(self, monkeypatch):
        noms = [nom for nom, _ in self._frames(monkeypatch)]
        assert noms == [
            "stream_open", "run_started", "turn_started", "tool_use", "tool_result",
            "turn_completed", "turn_started", "text_delta", "result", "done",
        ]

    def test_le_resultat_transporte_le_contrat_de_sortie(self, monkeypatch):
        frames = dict(self._frames(monkeypatch))
        assert frames["result"]["output"]["triage"] == "traitement_standard"
        assert frames["result"]["validation_errors"] == []

    def test_un_retour_a_la_ligne_ne_coupe_pas_la_trame(self, monkeypatch):
        frames = dict(self._frames(monkeypatch))
        assert frames["text_delta"]["text"] == '{\n  "claim_id"'

    def test_le_type_n_est_pas_duplique_dans_les_donnees(self, monkeypatch):
        # Le type est porte par la ligne `event:` ; le repeter dans `data:`
        # obligerait le frontend a choisir entre deux sources.
        for _, data in self._frames(monkeypatch):
            assert "type" not in data

    def test_verrou_libere_en_fin_de_flux(self, monkeypatch):
        self._frames(monkeypatch)
        assert not api._RUN_LOCK.locked()

    def test_une_exception_du_triage_est_remontee_puis_le_flux_se_ferme(self, monkeypatch):
        def _explose(claim_id, client=None, on_event=None):
            raise RuntimeError("panne simulee")

        monkeypatch.setattr(agent, "triage_claim", _explose)
        frames = _parse_sse(client.get("/api/triage/CLM-001/stream?confirm=1").text)
        noms = [nom for nom, _ in frames]
        # "run_error" et non "error" : voir _EVENT_NAME_OVERRIDES (collision
        # avec l'evenement de transport d'EventSource cote navigateur).
        assert noms == ["stream_open", "run_error", "done"]
        assert "panne simulee" in dict(frames)["run_error"]["message"]
        assert not api._RUN_LOCK.locked(), "meme en cas d'echec, le verrou est rendu"

    def test_l_evenement_error_de_l_agent_est_renomme(self, monkeypatch):
        def _sans_json(claim_id, client=None, on_event=None):
            on_event({"type": "error", "message": "pas un JSON", "raw_output": "desole"})
            return {"claim_id": claim_id, "error": "pas un JSON"}

        monkeypatch.setattr(agent, "triage_claim", _sans_json)
        frames = _parse_sse(client.get("/api/triage/CLM-001/stream?confirm=1").text)
        noms = [nom for nom, _ in frames]
        assert "run_error" in noms
        assert "error" not in noms
        assert dict(frames)["run_error"]["raw_output"] == "desole"
