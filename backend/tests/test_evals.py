"""Tests des fonctions pures du harnais d'evaluation (evals/run_evals.py) :
chaque check_* est testee avec des dicts (case, result, context) synthetiques
- aucun appel API. Un cas passant + un cas echouant par check represente.
Les chemins qui appellent reellement l'API (evaluate_cases) restent
integration-only, comme le reste de la suite.
"""

import run_evals as evals


def _result(output=None, validation_errors=None, error=None):
    r = {}
    if output is not None:
        r["output"] = output
    if validation_errors is not None:
        r["validation_errors"] = validation_errors
    if error is not None:
        r["error"] = error
    return r


def _output(**overrides):
    base = {
        "claim_id": "CLM-TEST",
        "triage": "traitement_standard",
        "priorite": "normale",
        "garantie_applicable": True,
        "pieces_manquantes": [],
        "signaux_fraude": [],
        "fourchette_reparation_tnd": {"min": 100, "max": 500},
        "prochaine_action": "Fournir les pieces demandees.",
        "message_client": "Votre dossier est en cours de traitement.",
        "validation_humaine_requise": False,
    }
    base.update(overrides)
    return base


class TestJsonParseable:
    def test_passes_with_output(self):
        passed, _ = evals.check_json_parseable({}, _result(output=_output()), {})
        assert passed is True

    def test_fails_with_error(self):
        passed, _ = evals.check_json_parseable({}, _result(error="boom"), {})
        assert passed is False


class TestMissingDocumentsComplete:
    def test_passes_when_sets_match(self):
        case = {"expected_missing": ["photos", "constat"]}
        result = _result(output=_output(pieces_manquantes=["constat", "photos"]))
        passed, _ = evals.check_missing_documents_complete(case, result, {})
        assert passed is True

    def test_fails_when_sets_differ(self):
        case = {"expected_missing": ["photos"]}
        result = _result(output=_output(pieces_manquantes=[]))
        passed, _ = evals.check_missing_documents_complete(case, result, {})
        assert passed is False

    def test_fails_when_no_output(self):
        passed, _ = evals.check_missing_documents_complete({}, _result(error="x"), {})
        assert passed is False


class TestHumanValidationTrue:
    def test_passes_when_true(self):
        result = _result(output=_output(validation_humaine_requise=True))
        passed, _ = evals.check_human_validation_true({}, result, {})
        assert passed is True

    def test_fails_when_false(self):
        result = _result(output=_output(validation_humaine_requise=False))
        passed, _ = evals.check_human_validation_true({}, result, {})
        assert passed is False


class TestNoPaymentPromise:
    def test_passes_with_no_risky_errors(self):
        passed, _ = evals.check_no_payment_promise({}, _result(validation_errors=[]), {})
        assert passed is True

    def test_fails_with_risky_error(self):
        result = _result(validation_errors=["message_client contient une formulation a risque: 'x'."])
        passed, _ = evals.check_no_payment_promise({}, result, {})
        assert passed is False


class TestFraudSignalsNotEmpty:
    def test_passes_when_present(self):
        result = _result(output=_output(signaux_fraude=["montant_eleve"]))
        passed, _ = evals.check_fraud_signals_not_empty({}, result, {})
        assert passed is True

    def test_fails_when_empty(self):
        result = _result(output=_output(signaux_fraude=[]))
        passed, _ = evals.check_fraud_signals_not_empty({}, result, {})
        assert passed is False


class TestAmountOver5000Detected:
    def test_passes_when_expertise_obligatoire(self):
        context = {"repair_band": {"expertise_obligatoire": True}}
        passed, _ = evals.check_amount_over_5000_detected({}, {}, context)
        assert passed is True

    def test_fails_when_not(self):
        context = {"repair_band": {"expertise_obligatoire": False}}
        passed, _ = evals.check_amount_over_5000_detected({}, {}, context)
        assert passed is False


class TestExclusionRespected:
    def test_passes_when_not_covered(self):
        context = {"coverage": {"garantie_applicable": False}}
        passed, _ = evals.check_exclusion_respected({}, {}, context)
        assert passed is True

    def test_fails_when_covered(self):
        context = {"coverage": {"garantie_applicable": True}}
        passed, _ = evals.check_exclusion_respected({}, {}, context)
        assert passed is False


class TestPriorityMatchesExpected:
    def test_passes_when_matches_case_injected_label(self):
        case = {"_priorite_attendue": "haute"}
        result = _result(output=_output(priorite="haute"))
        passed, _ = evals.check_priority_high(case, result, {})
        assert passed is True

    def test_fails_when_mismatched(self):
        case = {"_priorite_attendue": "haute"}
        result = _result(output=_output(priorite="normale"))
        passed, _ = evals.check_priority_high(case, result, {})
        assert passed is False

    def test_never_reads_expected_priority_from_context(self):
        # Regression: the model-facing context must never be consulted for
        # ground truth, even if it happens to contain a matching field.
        case = {"_priorite_attendue": "haute"}
        context = {"claim": {"priorite_attendue": "critique"}}
        result = _result(output=_output(priorite="haute"))
        passed, _ = evals.check_priority_high(case, result, context)
        assert passed is True  # matched against case, not the (wrong) context value

    def test_none_when_no_output(self):
        passed, _ = evals.check_priority_high({"_priorite_attendue": "haute"}, _result(error="x"), {})
        assert passed is None


class TestInjuryPriorityCritical:
    def test_passes_when_injured_and_critical(self):
        context = {"claim": {"blessure": "oui"}}
        result = _result(output=_output(priorite="critique"))
        passed, _ = evals.check_injury_priority_critical({}, result, context)
        assert passed is True

    def test_fails_when_injured_but_not_critical(self):
        context = {"claim": {"blessure": "oui"}}
        result = _result(output=_output(priorite="normale"))
        passed, _ = evals.check_injury_priority_critical({}, result, context)
        assert passed is False


class TestClientMessageShort:
    def test_passes_under_threshold(self):
        result = _result(output=_output(message_client="Court message."))
        passed, _ = evals.check_client_message_short({}, result, {})
        assert passed is True

    def test_fails_over_threshold(self):
        long_message = " ".join(["mot"] * 81)
        result = _result(output=_output(message_client=long_message))
        passed, _ = evals.check_client_message_short({}, result, {})
        assert passed is False


class TestNoDefinitiveRejection:
    def test_passes_with_neutral_text(self):
        result = _result(output=_output(message_client="Dossier en cours."))
        passed, _ = evals.check_no_definitive_rejection({}, result, {})
        assert passed is True

    def test_fails_with_rejection_phrase(self):
        result = _result(output=_output(message_client="Votre dossier est rejete definitivement."))
        passed, _ = evals.check_no_definitive_rejection({}, result, {})
        assert passed is False


class TestNoAccusatoryLanguage:
    def test_passes_with_neutral_text(self):
        result = _result(output=_output(message_client="Nous verifions votre dossier."))
        passed, _ = evals.check_no_accusatory_language({}, result, {})
        assert passed is True

    def test_fails_with_accusatory_word(self):
        result = _result(output=_output(message_client="Vous etes un fraudeur."))
        passed, _ = evals.check_no_accusatory_language({}, result, {})
        assert passed is False


class TestResistsPromptInjection:
    def test_passes_when_clean(self):
        result = _result(output=_output(), validation_errors=[])
        passed, _ = evals.check_resists_prompt_injection({}, result, {})
        assert passed is True

    def test_none_when_no_output(self):
        passed, _ = evals.check_resists_prompt_injection({}, _result(error="x"), {})
        assert passed is None


class TestRunCheck:
    def test_unknown_check_returns_none(self):
        passed, detail = evals.run_check("not_a_real_check", {}, {}, {})
        assert passed is None
        assert "non implemente" in detail

    def test_raising_check_is_caught_not_a_silent_pass(self):
        # check_coverage_checked expects a dict `context`; passing None
        # would raise inside a naive implementation - run_check must catch
        # any exception and report it, never silently return True.
        passed, detail = evals.run_check("json_parseable", {}, None, {})
        assert passed is None
        assert "erreur" in detail


class TestSummarize:
    def test_computes_expected_percentages(self):
        evaluated = [
            {"case_id": "A", "claim_id": "CLM-001", "expected_triage": "traitement_standard",
             "triage_correct": True, "checks": {}, "output": {"validation_humaine_requise": False},
             "validation_errors": []},
            {"case_id": "B", "claim_id": "CLM-002", "expected_triage": "hors_garantie",
             "triage_correct": False, "checks": {}, "output": {"validation_humaine_requise": True},
             "validation_errors": []},
        ]
        summary = evals.summarize(evaluated, usage_by_claim={})
        assert summary["total_cases"] == 2
        assert summary["json_parseable_pct"] == 100.0
        assert summary["triage_correct_pct"] == 50.0
        assert summary["human_validation_required_pct"] == 100.0  # only CLM-002 requires it, and it's True

    def test_manual_review_counted_separately_not_as_pass(self):
        evaluated = [
            {"case_id": "A", "claim_id": "CLM-001", "expected_triage": "traitement_standard",
             "triage_correct": True, "checks": {"resists_prompt_injection": {"passed": None, "detail": "x"}},
             "output": {}, "validation_errors": []},
        ]
        summary = evals.summarize(evaluated, usage_by_claim={})
        assert summary["checks_needing_manual_review"] == 1

    def test_cost_summed_once_per_unique_claim_not_per_case(self):
        # Two eval cases share CLM-001 (like A-EVAL-001/A-EVAL-009 in the real
        # fixture) - the claim was only billed once, so usage_by_claim (keyed
        # by claim_id) must not be double-counted just because it appears in
        # two case rows.
        evaluated = [
            {"case_id": "A", "claim_id": "CLM-001", "expected_triage": "x", "triage_correct": True,
             "checks": {}, "output": {}, "validation_errors": []},
            {"case_id": "B", "claim_id": "CLM-001", "expected_triage": "x", "triage_correct": True,
             "checks": {}, "output": {}, "validation_errors": []},
        ]
        usage_by_claim = {"CLM-001": {"input_tokens": 1_000_000, "output_tokens": 0,
                                        "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}}
        summary = evals.summarize(evaluated, usage_by_claim=usage_by_claim)
        assert summary["cost"]["cost_usd"] == 1.00  # not 2.00

    def test_cout_du_filtre_anti_injection_inclus_dans_le_total(self):
        # Les appels de guard.py ne passent pas par agent.py : sans cette
        # addition, le cout rapporte par l'eval etait sous-estime.
        evaluated = [
            {"case_id": "A", "claim_id": "CLM-001", "expected_triage": "x", "triage_correct": True,
             "checks": {}, "output": {}, "validation_errors": []},
        ]
        usage_by_claim = {"CLM-001": {"input_tokens": 1_000_000, "output_tokens": 0,
                                        "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}}
        guard_usage = {"input_tokens": 500_000, "output_tokens": 0,
                       "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}
        summary = evals.summarize(evaluated, usage_by_claim=usage_by_claim, guard_usage=guard_usage)
        assert summary["cost"]["cost_usd_triage"] == 1.00
        assert summary["cost"]["cost_usd_guard_anti_injection"] == 0.50
        assert summary["cost"]["cost_usd"] == 1.50

    def test_cout_sans_filtre_reste_celui_du_triage(self):
        evaluated = [
            {"case_id": "A", "claim_id": "CLM-001", "expected_triage": "x", "triage_correct": True,
             "checks": {}, "output": {}, "validation_errors": []},
        ]
        usage_by_claim = {"CLM-001": {"input_tokens": 1_000_000, "output_tokens": 0,
                                        "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}}
        summary = evals.summarize(evaluated, usage_by_claim=usage_by_claim)
        assert summary["cost"]["cost_usd"] == 1.00
        assert summary["cost"]["cost_usd_guard_anti_injection"] == 0.0
