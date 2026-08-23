"""Tests des 5 tools deterministes (aucun appel API, aucune dependance a un
modele). Utilise soit des fixtures synthetiques (policy/claim en dur) pour
tester les cas limites, soit les CSV reels (data/claims_auto.csv,
data/policies_auto.csv) pour verifier l'integration bout en bout des
lookups.
"""

import pytest

from tools import (
    ClaimNotFound,
    PolicyNotFound,
    check_coverage,
    detect_fraud_signals,
    estimate_repair_band,
    get_claim,
    get_policy,
    list_claim_ids,
)


def _policy(**overrides):
    base = {
        "policy_id": "POL-TEST",
        "assure": "Test Assure",
        "vehicule": "Test Vehicule",
        "formule": "tous_risques",
        "date_debut": "2025-01-01",
        "date_fin": "2027-01-01",
        "franchise_tnd": 500,
        "garanties": ["rc", "collision", "vol", "incendie", "bris_glace"],
        "exclusions": [],
    }
    base.update(overrides)
    return base


def _claim(**overrides):
    base = {
        "claim_id": "CLM-TEST",
        "policy_id": "POL-TEST",
        "date_sinistre": "2026-06-01",
        "type_sinistre": "collision",
        "description_client": "Test.",
        "blessure": "non",
        "constat": "oui",
        "photos": "oui",
        "devis_tnd": 1000,
        "tiers_identifie": "oui",
        "kilometrage_declare": 50000,
    }
    base.update(overrides)
    return base


class TestCheckCoverage:
    def test_covered_when_garantie_present_and_not_excluded(self):
        result = check_coverage(_policy(), _claim())
        assert result["garantie_applicable"] is True

    def test_not_covered_when_garantie_missing(self):
        result = check_coverage(_policy(garanties=["rc"]), _claim(type_sinistre="vol"))
        assert result["garantie_applicable"] is False

    def test_not_covered_when_explicitly_excluded(self):
        policy = _policy(exclusions=["bris_glace"])
        result = check_coverage(policy, _claim(type_sinistre="bris_glace"))
        assert result["garantie_applicable"] is False

    def test_rc_simple_does_not_cover_collision(self):
        policy = _policy(formule="rc_simple", garanties=["rc"])
        result = check_coverage(policy, _claim(type_sinistre="collision"))
        assert result["garantie_applicable"] is False

    def test_rc_simple_covers_rc_tiers(self):
        policy = _policy(formule="rc_simple", garanties=["rc"])
        result = check_coverage(policy, _claim(type_sinistre="rc_tiers"))
        assert result["garantie_applicable"] is True

    def test_flotte_pro_flags_human_review_on_driver_exclusion(self):
        policy = _policy(formule="flotte_pro", exclusions=["conducteur_non_habilite"])
        result = check_coverage(policy, _claim())
        assert result["verification_humaine_recommandee"] is True

    def test_never_flags_human_review_outside_flotte_pro(self):
        policy = _policy(formule="tous_risques", exclusions=["conducteur_non_habilite"])
        result = check_coverage(policy, _claim())
        assert result["verification_humaine_recommandee"] is False


class TestEstimateRepairBand:
    @pytest.mark.parametrize(
        "devis_tnd,expected_bande",
        [(0, "leger"), (999, "leger"), (1000, "modere"), (2999, "modere"),
         (3000, "important"), (4999, "important"), (5000, "majeur"), (5001, "majeur")],
    )
    def test_band_boundaries(self, devis_tnd, expected_bande):
        assert estimate_repair_band(devis_tnd)["bande"] == expected_bande

    def test_expertise_obligatoire_only_strictly_above_5000(self):
        assert estimate_repair_band(5000)["expertise_obligatoire"] is False
        assert estimate_repair_band(5001)["expertise_obligatoire"] is True

    def test_negative_devis_raises(self):
        with pytest.raises(ValueError):
            estimate_repair_band(-1)


class TestDetectFraudSignals:
    def test_flags_montant_eleve_above_threshold(self):
        result = detect_fraud_signals(_claim(devis_tnd=6000), _policy())
        assert "montant_eleve" in result["signaux_fraude"]

    def test_no_montant_eleve_below_threshold(self):
        result = detect_fraud_signals(_claim(devis_tnd=1000), _policy())
        assert "montant_eleve" not in result["signaux_fraude"]

    def test_flags_claim_shortly_after_policy_start(self):
        claim = _claim(date_sinistre="2025-01-10")
        policy = _policy(date_debut="2025-01-01")
        result = detect_fraud_signals(claim, policy)
        assert "sinistre_juste_apres_ouverture_police" in result["signaux_fraude"]

    def test_flags_vol_recent_for_theft_shortly_after_start(self):
        claim = _claim(type_sinistre="vol", date_sinistre="2025-01-10")
        policy = _policy(date_debut="2025-01-01")
        result = detect_fraud_signals(claim, policy)
        assert "vol_recent" in result["signaux_fraude"]

    def test_flags_date_outside_coverage_period(self):
        claim = _claim(date_sinistre="2028-01-01")
        policy = _policy(date_debut="2025-01-01", date_fin="2027-01-01")
        result = detect_fraud_signals(claim, policy)
        assert "incoherence_police_date_hors_couverture" in result["signaux_fraude"]

    def test_clean_claim_has_no_signals(self):
        claim = _claim(devis_tnd=1000, date_sinistre="2026-06-01")
        policy = _policy(date_debut="2025-01-01", date_fin="2027-01-01")
        result = detect_fraud_signals(claim, policy)
        assert result["signaux_fraude"] == []


class TestGetPolicyAndGetClaim:
    def test_get_policy_known_id(self):
        policy = get_policy("POL-001")
        assert policy["policy_id"] == "POL-001"

    def test_get_policy_unknown_id_raises(self):
        with pytest.raises(PolicyNotFound):
            get_policy("POL-DOES-NOT-EXIST")

    def test_get_claim_known_id(self):
        claim = get_claim("CLM-001")
        assert claim["claim_id"] == "CLM-001"

    def test_get_claim_unknown_id_raises(self):
        with pytest.raises(ClaimNotFound):
            get_claim("CLM-DOES-NOT-EXIST")

    def test_get_claim_does_not_expose_reference_only_columns(self):
        # priorite_attendue/triage_attendu sont des colonnes de reference
        # dans claims_auto.csv, jamais des attributs de sinistre reels : elles
        # ne doivent pas apparaitre dans ce que get_claim renvoie (ni au
        # modele, ni ailleurs).
        claim = get_claim("CLM-001")
        assert "priorite_attendue" not in claim
        assert "triage_attendu" not in claim


def test_list_claim_ids_returns_all_claims_sorted():
    ids = list_claim_ids()
    assert ids == sorted(ids)
    assert "CLM-001" in ids
    assert len(ids) == 8


# =============================================================================
# Absence de repli sur data/
# =============================================================================

class TestAucunRepliSurLeDepot:
    """Les CSV de data/ sont les jeux d'essai des evaluations, pas la source
    de l'application. Rien ne doit les lire sans qu'on le demande."""

    def test_lecture_refusee_sans_jeu_de_donnees(self):
        import dataset
        import tools as tools_module
        from tools import NoDatasetLoaded

        dataset.clear()
        # Les fichiers existent : si une lecture aboutissait, c'est qu'elle
        # s'y serait rabattue.
        assert tools_module.DEFAULT_CLAIMS_PATH.exists()
        with pytest.raises(NoDatasetLoaded):
            get_claim("CLM-001")
        with pytest.raises(NoDatasetLoaded):
            get_policy("POL-002")
        with pytest.raises(NoDatasetLoaded):
            list_claim_ids()

    def test_chargement_explicite_puis_lecture(self):
        import dataset
        import tools as tools_module

        dataset.clear()
        tools_module.load_dataset_from_files()
        assert get_claim("CLM-001")["claim_id"] == "CLM-001"
