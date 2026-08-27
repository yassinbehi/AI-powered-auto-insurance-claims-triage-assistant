"""Tests de l'observation du stream et de la boucle d'outils (src/agent.py).

AUCUN APPEL API : un faux client Anthropic rejoue deux tours de boucle
(un tour d'outil, puis la reponse finale), stream compris.

Le sinistre utilise est CLM-002, choisi exprès : son texte contient un
marqueur d'injection connu, donc guard s'arrete a la couche [1] et ne
construit jamais de client pour le classifieur. Le test reste ainsi hors
ligne tout en exerçant les vrais handlers de tools.
"""

import json

import pytest

import agent
import guard
from config import MODEL


# =============================================================================
# Faux SDK
# =============================================================================

def _obj(**attrs):
    return type("Obj", (), attrs)()


def _text_block(text):
    return _obj(type="text", text=text)


def _tool_use_block(block_id, name, tool_input):
    return _obj(type="tool_use", id=block_id, name=name, input=tool_input)


def _raw_delta(text):
    """Evenement brut de l'API : c'est celui qu'agent.py doit ecouter."""
    return _obj(type="content_block_delta", delta=_obj(type="text_delta", text=text))


def _sdk_text_event(text):
    """Evenement de commodite du SDK, porteur de la MEME donnee que
    _raw_delta. agent.py doit l'ignorer, sinon chaque fragment sortirait en
    double."""
    return _obj(type="text", text=text)


class _FakeStream:
    def __init__(self, events, final_message):
        self._events = events
        self._final = final_message

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def __iter__(self):
        return iter(self._events)

    def get_final_message(self):
        return self._final


class _FakeMessages:
    def __init__(self, tours):
        self._tours = tours
        self.calls = 0

    def stream(self, **kwargs):
        tour = self._tours[self.calls]
        self.calls += 1
        return _FakeStream(tour["events"], tour["final"])


class _FakeClient:
    def __init__(self, tours):
        self.messages = _FakeMessages(tours)


_USAGE = {
    "input_tokens": 100,
    "output_tokens": 20,
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 0,
}

# Exemple valide au sens de schema.validate_full (repris de schema.py).
_SORTIE = {
    "claim_id": "CLM-002",
    "triage": "hors_garantie",
    "priorite": "normale",
    "garantie_applicable": False,
    "pieces_manquantes": [],
    "signaux_fraude": [],
    "fourchette_reparation_tnd": {"min": 800, "max": 900},
    "prochaine_action": "Informer le client que ce sinistre n'est pas couvert par sa formule.",
    "message_client": "Votre formule actuelle ne couvre pas le bris de glace.",
    "validation_humaine_requise": True,
}

_FRAGMENTS = ['{"claim_id": "CLM-002",', ' "triage": "hors_garantie",', ' ...}']


def _client_deux_tours():
    """Tour 1 : le modele appelle get_claim. Tour 2 : il rend le JSON final."""
    tour_outil = {
        "events": [],
        "final": _obj(
            content=[_tool_use_block("tu_1", "get_claim", {"claim_id": "CLM-002"})],
            usage=dict(_USAGE),
        ),
    }
    texte_final = json.dumps(_SORTIE, ensure_ascii=False)
    tour_final = {
        # Chaque fragment est emis DEUX fois par le SDK : une fois en brut,
        # une fois via l'evenement de commodite.
        "events": [e for f in _FRAGMENTS for e in (_raw_delta(f), _sdk_text_event(f))],
        "final": _obj(content=[_text_block(texte_final)], usage=dict(_USAGE)),
    }
    return _FakeClient([tour_outil, tour_final])


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def _forbidden(*args, **kwargs):
        raise AssertionError("aucun client Anthropic reel ne doit etre construit ici")

    monkeypatch.setattr(guard.anthropic, "Anthropic", _forbidden)
    guard.reset_screening_cache()
    guard.reset_guard_usage()
    yield
    guard.reset_screening_cache()
    guard.reset_guard_usage()


def _run():
    events = []
    result = agent.triage_claim("CLM-002", client=_client_deux_tours(), on_event=events.append)
    return result, events


# =============================================================================
# Le resultat ne change pas selon qu'on observe ou non
# =============================================================================

class TestNonRegression:
    def test_resultat_identique_sans_observateur(self):
        sans = agent.triage_claim("CLM-002", client=_client_deux_tours())
        guard.reset_screening_cache()
        avec, _ = _run()
        assert sans == avec

    def test_sortie_valide(self):
        result, _ = _run()
        assert result["output"] == _SORTIE
        assert result["validation_errors"] == []

    def test_usage_cumule_sur_les_deux_tours(self):
        result, _ = _run()
        assert result["usage"]["input_tokens"] == 2 * _USAGE["input_tokens"]

    def test_trace_des_tools_conservee(self):
        result, _ = _run()
        assert [t["tool"] for t in result["tool_call_trace"]] == ["get_claim"]

    def test_un_observateur_qui_plante_ne_casse_pas_le_triage(self):
        def _explose(_event):
            raise RuntimeError("observateur casse")

        result = agent.triage_claim("CLM-002", client=_client_deux_tours(), on_event=_explose)
        assert result["output"] == _SORTIE


# =============================================================================
# Sequence d'evenements
# =============================================================================

class TestEvenements:
    def test_sequence(self):
        _, events = _run()
        assert [e["type"] for e in events] == [
            "run_started",
            # Tour 1 : le modele n'emet qu'un tool_use, donc aucun delta de
            # texte, mais bien un couple tool_use / tool_result.
            "turn_started", "tool_use", "tool_result", "turn_completed",
            # Tour 2 : la reponse finale, ecrite fragment par fragment.
            "turn_started", "text_delta", "text_delta", "text_delta", "turn_completed",
            "result",
        ]

    def test_les_tours_sont_numerotes_a_partir_de_1(self):
        _, events = _run()
        assert [e["turn"] for e in events if e["type"] == "turn_started"] == [1, 2]

    def test_tool_use_precede_son_tool_result(self):
        _, events = _run()
        types = [e["type"] for e in events]
        assert types.index("tool_use") < types.index("tool_result")

        appel = next(e for e in events if e["type"] == "tool_use")
        retour = next(e for e in events if e["type"] == "tool_result")
        assert appel["tool"] == retour["tool"] == "get_claim"
        assert appel["turn"] == retour["turn"] == 1
        assert appel["input"] == {"claim_id": "CLM-002"}

    def test_le_tool_result_diffuse_est_celui_de_la_trace(self):
        result, events = _run()
        retour = next(e for e in events if e["type"] == "tool_result")
        assert retour["output"] == result["tool_call_trace"][0]["output"]

    def test_le_texte_client_reste_filtre_dans_le_flux(self):
        # Le tool_result diffuse en direct passe par le meme filtre que celui
        # transmis au modele : l'interface ne peut pas voir le texte brut.
        _, events = _run()
        retour = next(e for e in events if e["type"] == "tool_result")
        assert retour["output"]["description_client"] == guard.REDACTED_PLACEHOLDER

    def test_aucun_fragment_en_double(self):
        """Le SDK emet chaque fragment deux fois (brut + commodite) ; agent.py
        ne doit en relayer qu'un seul."""
        _, events = _run()
        fragments = [e["text"] for e in events if e["type"] == "text_delta"]
        assert fragments == _FRAGMENTS

    def test_le_resultat_final_est_diffuse(self):
        _, events = _run()
        final = events[-1]
        assert final["type"] == "result"
        assert final["output"] == _SORTIE
        assert final["validation_errors"] == []


# =============================================================================
# Cout de l'execution
# =============================================================================

class TestCoutDeLExecution:
    """`cost_usd` est ce que l'interface additionne pour afficher un cumul
    (frontend/src/lib/cumulative-cost.ts). Il doit donc etre present, exact,
    et suivre le modele reellement utilise."""

    # Deux tours de _USAGE, au tarif Haiku 4.5 (1.00 / 5.00 par MTok) :
    # 200/1e6*1.00 + 40/1e6*5.00 = 0.0004
    _COUT_HAIKU = 0.0004

    def test_le_resultat_porte_le_cout_et_le_modele(self):
        result, _ = _run()
        assert result["cost_usd"] == pytest.approx(self._COUT_HAIKU)
        assert result["model"] == MODEL

    def test_l_evenement_result_porte_le_meme_cout(self):
        result, events = _run()
        final = next(e for e in events if e["type"] == "result")
        assert final["cost_usd"] == result["cost_usd"]
        assert final["model"] == result["model"]

    def test_le_cout_suit_le_modele_choisi(self):
        """Sonnet 4.6 coute trois fois Haiku 4.5 : un cumul calcule au tarif du
        defaut serait faux des que l'utilisateur change de modele."""
        result = agent.triage_claim(
            "CLM-002", client=_client_deux_tours(), model="claude-sonnet-4-6"
        )
        assert result["cost_usd"] == pytest.approx(3 * self._COUT_HAIKU)
        assert result["model"] == "claude-sonnet-4-6"

    def test_un_triage_qui_n_aboutit_pas_est_quand_meme_facture(self):
        """Plafond de tours atteint : l'execution a consomme des appels de
        modele, et son cout doit rester visible - sinon le cumul oublie
        precisement les executions les plus cheres."""
        tours = [
            {
                "events": [],
                "final": _obj(
                    content=[_tool_use_block(f"tu_{i}", "get_claim", {"claim_id": "CLM-002"})],
                    usage=dict(_USAGE),
                ),
            }
            for i in range(agent.MAX_TOOL_TURNS)
        ]
        result = agent.triage_claim("CLM-002", client=_FakeClient(tours))

        assert "error" in result
        assert result["cost_usd"] == pytest.approx(
            agent.MAX_TOOL_TURNS / 2 * self._COUT_HAIKU
        )


# =============================================================================
# Chemins d'erreur
# =============================================================================

class TestErreurs:
    def test_json_non_parseable(self):
        client = _FakeClient([
            {"events": [_raw_delta("desole")],
             "final": _obj(content=[_text_block("desole, pas de JSON")], usage=dict(_USAGE))},
        ])
        events = []
        result = agent.triage_claim("CLM-002", client=client, on_event=events.append)

        assert "n'est pas un JSON valide" in result["error"]
        assert result["raw_output"] == "desole, pas de JSON"

        erreur = events[-1]
        assert erreur["type"] == "error"
        assert erreur["raw_output"] == "desole, pas de JSON"

    def test_plafond_de_tours_atteint(self, monkeypatch):
        monkeypatch.setattr(agent, "MAX_TOOL_TURNS", 2)
        tour = {
            "events": [],
            "final": _obj(
                content=[_tool_use_block("tu_x", "get_claim", {"claim_id": "CLM-002"})],
                usage=dict(_USAGE),
            ),
        }
        events = []
        result = agent.triage_claim(
            "CLM-002", client=_FakeClient([tour, tour]), on_event=events.append
        )

        assert "Nombre maximal de tours" in result["error"]
        assert events[-1]["type"] == "error"
