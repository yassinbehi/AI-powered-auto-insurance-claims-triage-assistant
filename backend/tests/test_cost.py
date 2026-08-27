"""Tests des fonctions pures de suivi cout/usage (src/cost.py). Aucun appel
API : usage_to_dict fonctionne par duck-typing, calculate_cost_usd est une
formule pure sur des dicts.
"""

import pytest

from config import MODEL
from cost import (
    accumulate_usage,
    calculate_cost_usd,
    empty_usage_totals,
    format_cost_report,
    prices_for_model,
    usage_to_dict,
)


class _FakeUsage:
    """Simule l'objet .usage renvoye par le SDK anthropic (attributs, pas
    un dict)."""

    def __init__(self, input_tokens=0, output_tokens=0, cache_creation_input_tokens=0, cache_read_input_tokens=0):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cache_creation_input_tokens = cache_creation_input_tokens
        self.cache_read_input_tokens = cache_read_input_tokens


class TestUsageToDict:
    def test_from_dict(self):
        result = usage_to_dict({"input_tokens": 100, "output_tokens": 50})
        assert result == {
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
        }

    def test_from_sdk_like_object(self):
        result = usage_to_dict(_FakeUsage(input_tokens=200, output_tokens=30, cache_read_input_tokens=500))
        assert result == {
            "input_tokens": 200,
            "output_tokens": 30,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 500,
        }

    def test_missing_fields_default_to_zero(self):
        assert usage_to_dict({}) == empty_usage_totals()


class TestCalculateCostUsd:
    def test_one_million_input_tokens_costs_exactly_input_rate(self):
        cost_usd = calculate_cost_usd({"input_tokens": 1_000_000, "output_tokens": 0})
        assert cost_usd == pytest.approx(1.00)

    def test_one_million_output_tokens_costs_exactly_output_rate(self):
        cost_usd = calculate_cost_usd({"output_tokens": 1_000_000})
        assert cost_usd == pytest.approx(5.00)

    def test_mixed_usage(self):
        usage = {
            "input_tokens": 500_000,
            "output_tokens": 100_000,
            "cache_creation_input_tokens": 200_000,
            "cache_read_input_tokens": 1_000_000,
        }
        # 0.5*1.00 + 0.1*5.00 + 0.2*1.25 + 1.0*0.10 = 0.50 + 0.50 + 0.25 + 0.10 = 1.35
        assert calculate_cost_usd(usage) == pytest.approx(1.35)

    def test_empty_usage_costs_nothing(self):
        assert calculate_cost_usd(empty_usage_totals()) == 0.0


class TestTarifsParModele:
    """L'utilisateur peut lancer un triage sur un autre modele que le defaut
    (config.AVAILABLE_MODELS) : tout facturer au tarif du defaut
    sous-estimerait le cout affiche."""

    _USAGE = {"input_tokens": 1_000_000, "output_tokens": 1_000_000}

    def test_le_defaut_reste_le_comportement_sans_argument(self):
        assert calculate_cost_usd(self._USAGE) == calculate_cost_usd(
            self._USAGE, model=MODEL
        )

    def test_un_modele_plus_cher_coute_plus_cher(self):
        # Sonnet 4.6 : 3.00 / 15.00 par MTok, contre 1.00 / 5.00 pour Haiku 4.5.
        assert calculate_cost_usd(self._USAGE, model="claude-sonnet-4-6") == pytest.approx(18.00)
        assert calculate_cost_usd(self._USAGE, model=MODEL) == pytest.approx(6.00)

    def test_un_modele_inconnu_retombe_sur_le_defaut(self):
        """Un triage DEJA PAYE ne doit pas se terminer par une exception parce
        que la table de tarifs ignore le modele."""
        assert prices_for_model("modele-jamais-vu") == prices_for_model(MODEL)
        assert calculate_cost_usd(self._USAGE, model="modele-jamais-vu") == pytest.approx(6.00)

    def test_les_tarifs_de_cache_derivent_du_tarif_d_entree(self):
        """Multiplicateurs standards Anthropic : ecriture 5m = 1.25x l'entree,
        lecture = 0.1x. Voir config.MODEL_PRICES_PER_MTOK_USD."""
        for modele in (MODEL, "claude-sonnet-4-6"):
            tarifs = prices_for_model(modele)
            assert tarifs["cache_write_5m"] == pytest.approx(1.25 * tarifs["input"])
            assert tarifs["cache_read"] == pytest.approx(0.10 * tarifs["input"])


class TestAccumulateUsage:
    def test_accumulates_across_calls(self):
        totals = empty_usage_totals()
        totals = accumulate_usage(totals, {"input_tokens": 100, "output_tokens": 10})
        totals = accumulate_usage(totals, {"input_tokens": 50, "output_tokens": 5})
        assert totals["input_tokens"] == 150
        assert totals["output_tokens"] == 15

    def test_does_not_mutate_input(self):
        totals = empty_usage_totals()
        accumulate_usage(totals, {"input_tokens": 100})
        assert totals["input_tokens"] == 0


class TestFormatCostReport:
    def test_within_budget_has_no_warning(self):
        report = format_cost_report({"input_tokens": 1000, "output_tokens": 200,
                                       "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0})
        assert report["over_ceiling"] is False
        assert report["over_target"] is False
        assert report["warning"] is None

    def test_over_target_but_under_ceiling_warns(self):
        # ~3 USD input-only: 3_000_000 tokens * $1.00/MTok = $3.00 (> target 2.75, < ceiling 5.00)
        report = format_cost_report({"input_tokens": 3_000_000, "output_tokens": 0,
                                       "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0})
        assert report["over_ceiling"] is False
        assert report["over_target"] is True
        assert report["warning"] is not None
        assert "cible" in report["warning"]

    def test_over_ceiling_warns(self):
        report = format_cost_report({"input_tokens": 10_000_000, "output_tokens": 0,
                                       "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0})
        assert report["over_ceiling"] is True
        assert "PLAFOND" in report["warning"]

    def test_includes_budget_constants(self):
        report = format_cost_report(empty_usage_totals())
        assert report["budget_ceiling_usd"] == 5.00
        assert report["budget_target_min_usd"] == 1.50
        assert report["budget_target_max_usd"] == 2.75
