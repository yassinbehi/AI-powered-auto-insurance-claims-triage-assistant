"""Tests du validateur de contrat de sortie (schema.py). Pas d'appel API :
schema.py ne fait que verifier une sortie deja produite, jamais en generer
une.
"""

from schema import (
    check_no_payment_promise,
    expected_validation_humaine_requise,
    validate_business_rules,
    validate_full,
    validate_schema,
)


def _valid_output(**overrides):
    base = {
        "claim_id": "CLM-001",
        "triage": "traitement_standard",
        "priorite": "normale",
        "garantie_applicable": True,
        "pieces_manquantes": [],
        "signaux_fraude": [],
        "fourchette_reparation_tnd": {"min": 100, "max": 500},
        "prochaine_action": "Aucune action requise.",
        "message_client": "Votre dossier est en cours de traitement.",
        "validation_humaine_requise": False,
    }
    base.update(overrides)
    return base


class TestValidateSchema:
    def test_valid_output_has_no_errors(self):
        assert validate_schema(_valid_output()) == []

    def test_missing_field_detected(self):
        output = _valid_output()
        del output["signaux_fraude"]
        errors = validate_schema(output)
        assert any("signaux_fraude" in e for e in errors)

    def test_invalid_triage_value_detected(self):
        errors = validate_schema(_valid_output(triage="pas_une_valeur_valide"))
        assert any("triage invalide" in e for e in errors)

    def test_invalid_priorite_value_detected(self):
        errors = validate_schema(_valid_output(priorite="pas_une_valeur_valide"))
        assert any("priorite invalide" in e for e in errors)

    def test_fourchette_min_greater_than_max_detected(self):
        output = _valid_output(fourchette_reparation_tnd={"min": 900, "max": 100})
        errors = validate_schema(output)
        assert any("min ne peut pas etre superieur" in e for e in errors)

    def test_non_dict_output_rejected(self):
        assert validate_schema("not a dict") != []


class TestPaymentPromise:
    def test_no_warning_for_neutral_message(self):
        assert check_no_payment_promise("Votre dossier est en cours de traitement.") == []

    def test_warns_on_reimbursement_promise(self):
        warnings = check_no_payment_promise("Vous serez rembourse sous 48h.")
        assert len(warnings) == 1


class TestExpectedValidationHumaineRequise:
    def test_true_for_suspicion_fraude(self):
        result = expected_validation_humaine_requise("suspicion_fraude", {"min": 0, "max": 100}, blessure=False)
        assert result is True

    def test_true_for_hors_garantie(self):
        result = expected_validation_humaine_requise("hors_garantie", {"min": 0, "max": 100}, blessure=False)
        assert result is True

    def test_true_when_amount_over_threshold(self):
        result = expected_validation_humaine_requise("traitement_standard", {"min": 0, "max": 5001}, blessure=False)
        assert result is True

    def test_false_when_amount_at_threshold(self):
        result = expected_validation_humaine_requise("traitement_standard", {"min": 0, "max": 5000}, blessure=False)
        assert result is False

    def test_true_when_blessure(self):
        result = expected_validation_humaine_requise("traitement_standard", {"min": 0, "max": 100}, blessure=True)
        assert result is True

    def test_false_otherwise(self):
        result = expected_validation_humaine_requise("traitement_standard", {"min": 0, "max": 100}, blessure=False)
        assert result is False


class TestValidateBusinessRules:
    def test_flags_missing_validation_humaine_requise(self):
        output = _valid_output(triage="hors_garantie", validation_humaine_requise=False)
        errors = validate_business_rules(output, blessure=False)
        assert any("validation_humaine_requise doit etre true" in e for e in errors)

    def test_ok_when_validation_humaine_requise_correctly_true(self):
        output = _valid_output(triage="hors_garantie", validation_humaine_requise=True)
        assert validate_business_rules(output, blessure=False) == []

    def test_flags_payment_promise_in_message(self):
        output = _valid_output(message_client="Vous serez rembourse sous 48h.")
        errors = validate_business_rules(output, blessure=False)
        assert len(errors) == 1


def test_validate_full_combines_schema_and_business_rules():
    output = _valid_output(
        triage="hors_garantie",
        validation_humaine_requise=False,
        message_client="Vous serez rembourse.",
    )
    errors = validate_full(output, blessure=False)
    assert len(errors) == 2
