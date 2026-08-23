"""Tests du bareme d'urgence (src/urgence.py).

AUCUN APPEL API : estimate_urgency est une fonction pure sur un dictionnaire.
Les declarations sont construites sur place plutot que lues dans data/, pour
que chaque test dise exactement quelle colonne il exerce.

Deux tests de ce fichier ne portent pas sur le calcul mais sur la FRONTIERE :
le bareme est en partie deduit de colonnes d'evaluation, donc il ne doit
jamais atteindre le modele, et il ne doit jamais se laisser influencer par ces
memes colonnes quand elles trainent dans la declaration.
"""

import copy
from pathlib import Path

import pytest

import agent
import urgence
from config import EXPERTISE_REQUIRED_THRESHOLD_TND, SYSTEM_PROMPT_PATH
from urgence import (
    MOTIF_BLESSURE,
    MOTIF_DEVIS_ELEVE,
    MOTIF_MESSAGE_SIGNALE,
    MOTIF_MONTANT_FAIBLE,
    MOTIF_MONTANT_INCONNU,
    SEUIL_MONTANT_FAIBLE_TND,
    estimate_urgency,
)


def _claim(**overrides) -> dict:
    """Declaration neutre : rien qui doive declencher quoi que ce soit."""
    base = {
        "claim_id": "CLM-TEST",
        "policy_id": "POL-TEST",
        "date_sinistre": "2026-08-01",
        "type_sinistre": "collision",
        "description_client": "Accrochage sur un parking.",
        "blessure": "non",
        "constat": "oui",
        "photos": "oui",
        "devis_tnd": 2000,
        "tiers_identifie": "oui",
        "kilometrage_declare": 90000,
    }
    base.update(overrides)
    return base


class TestReglesDocumentees:
    """La seule ligne du bareme que regles_sinistres.md ecrit noir sur blanc."""

    def test_blessure_donne_critique(self):
        resultat = estimate_urgency(_claim(blessure="oui"), [])
        assert resultat["niveau"] == "critique"
        assert MOTIF_BLESSURE in resultat["motifs"]

    def test_blessure_l_emporte_sur_un_montant_faible(self):
        # Le montant ne fait jamais redescendre un dossier deja escalade.
        resultat = estimate_urgency(_claim(blessure="oui", devis_tnd=200), [])
        assert resultat["niveau"] == "critique"
        assert MOTIF_MONTANT_FAIBLE not in resultat["motifs"]


class TestSeuilDExpertise:
    def test_au_dessus_du_seuil_donne_haute(self):
        resultat = estimate_urgency(
            _claim(devis_tnd=EXPERTISE_REQUIRED_THRESHOLD_TND + 1), []
        )
        assert resultat["niveau"] == "haute"
        assert MOTIF_DEVIS_ELEVE in resultat["motifs"]

    def test_exactement_au_seuil_n_est_pas_haute(self):
        # Garde le `>` STRICT, aligne sur tools.estimate_repair_band. Un
        # basculement en `>=` ici desynchroniserait le bareme de la regle
        # documentee sans que rien d'autre ne le signale.
        resultat = estimate_urgency(
            _claim(devis_tnd=EXPERTISE_REQUIRED_THRESHOLD_TND), []
        )
        assert resultat["niveau"] == "normale"
        assert MOTIF_DEVIS_ELEVE not in resultat["motifs"]


class TestMessageSignale:
    def test_marqueurs_presents_donnent_haute(self):
        resultat = estimate_urgency(_claim(), ["ignore les instructions"])
        assert resultat["niveau"] == "haute"
        assert MOTIF_MESSAGE_SIGNALE in resultat["motifs"]

    def test_liste_vide_ne_change_rien(self):
        assert estimate_urgency(_claim(), [])["niveau"] == "normale"


class TestMontant:
    def test_montant_faible_donne_basse(self):
        resultat = estimate_urgency(_claim(devis_tnd=500), [])
        assert resultat["niveau"] == "basse"
        assert MOTIF_MONTANT_FAIBLE in resultat["motifs"]

    def test_bornes_de_la_bande_leger(self):
        # SEUIL_MONTANT_FAIBLE_TND est lu dans tools.REPAIR_BANDS. Ce test
        # fige la borne : rejouer les bandes doit faire bouger ce test, pas
        # passer inapercu.
        juste_en_dessous = estimate_urgency(
            _claim(devis_tnd=SEUIL_MONTANT_FAIBLE_TND - 1), []
        )
        pile_dessus = estimate_urgency(_claim(devis_tnd=SEUIL_MONTANT_FAIBLE_TND), [])
        assert juste_en_dessous["niveau"] == "basse"
        assert pile_dessus["niveau"] == "normale"

    def test_devis_zero_est_normale_et_non_basse(self):
        # Zero veut dire "pas encore chiffre", pas "petit montant". Le classer
        # `basse` enverrait au fond de la file exactement les dossiers qu'il
        # faut aller regarder (un vol sans devis, typiquement).
        resultat = estimate_urgency(_claim(devis_tnd=0), [])
        assert resultat["niveau"] == "normale"
        assert resultat["motifs"] == [MOTIF_MONTANT_INCONNU]


class TestCumulDesMotifs:
    def test_les_motifs_s_accumulent_sous_le_niveau_maximal(self):
        # Le gestionnaire a besoin de savoir POURQUOI, pas seulement A QUEL
        # POINT : un dossier critique pour blessure doit continuer a remonter
        # son devis eleve et son message signale.
        resultat = estimate_urgency(
            _claim(blessure="oui", devis_tnd=9800), ["ignore les instructions"]
        )
        assert resultat["niveau"] == "critique"
        assert resultat["motifs"] == [
            MOTIF_BLESSURE,
            MOTIF_DEVIS_ELEVE,
            MOTIF_MESSAGE_SIGNALE,
        ]


class TestRobustesse:
    @pytest.mark.parametrize("devis", [None, "", "abc", -1])
    def test_devis_illisible_ne_fait_pas_echouer_la_file(self, devis):
        # Une ligne amputee doit rester visible au niveau par defaut plutot
        # que faire tomber tout l'ecran.
        resultat = estimate_urgency(_claim(devis_tnd=devis), [])
        assert resultat["niveau"] == "normale"

    def test_declaration_presque_vide(self):
        assert estimate_urgency({}, [])["niveau"] == "normale"


class TestPurete:
    def test_deux_appels_donnent_le_meme_resultat(self):
        claim = _claim(blessure="oui", devis_tnd=9800)
        assert estimate_urgency(claim, []) == estimate_urgency(claim, [])

    def test_l_entree_n_est_pas_mutee(self):
        claim = _claim(blessure="oui", devis_tnd=9800)
        avant = copy.deepcopy(claim)
        estimate_urgency(claim, ["ignore les instructions"])
        assert claim == avant


class TestFrontiereAvecLesEvaluations:
    """Le bareme est en partie deduit de colonnes d'evaluation. Ces deux tests
    sont ce qui rend cette dette acceptable plutot que silencieuse."""

    def test_les_colonnes_de_reference_n_influencent_rien(self):
        # priorite_attendue est la REPONSE de l'eval. La lire ici viderait de
        # son sens toute mesure de qualite.
        benin = _claim(priorite_attendue="critique", triage_attendu="suspicion_fraude")
        assert estimate_urgency(benin, [])["niveau"] == "normale"

    def test_le_vocabulaire_n_atteint_jamais_le_modele(self):
        # Verification au niveau SOURCE, dans l'esprit du test de fuite de
        # test_api.py : ni la boucle agentique ni le prompt systeme ne doivent
        # connaitre ce module.
        #
        # On cherche le vocabulaire PROPRE au bareme, pas le mot "urgence" :
        # system_prompt.md l'emploie deja en francais courant ("une urgence
        # reelle qui ne peut pas attendre"), ce qui n'a rien a voir.
        interdits = [
            "urgence_estimee",
            "urgence_motifs",
            "estimate_urgency",
            "import urgence",
            MOTIF_MONTANT_INCONNU,
            MOTIF_MONTANT_FAIBLE,
        ]
        source_agent = Path(agent.__file__).read_text(encoding="utf-8")
        prompt = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
        for terme in interdits:
            assert terme not in source_agent, f"{terme} a fuite dans agent.py"
            assert terme not in prompt, f"{terme} a fuite dans system_prompt.md"


def test_niveaux_est_ordonne_du_moins_au_plus_urgent():
    # _plus_urgent compare par index : l'ordre de ce tuple EST le bareme.
    assert urgence.NIVEAUX == ("basse", "normale", "haute", "critique")
