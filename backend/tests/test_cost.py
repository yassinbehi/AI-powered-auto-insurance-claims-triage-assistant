"""Tests des fonctions pures de suivi cout/usage (src/cost.py). Aucun appel
API : usage_to_dict fonctionne par duck-typing, calculate_cost_usd est une
formule pure sur des dicts.
"""

import pytest

from cost import (
    accumulate_usage,
    calculate_cost_usd,
    empty_usage_totals,
    format_cost_report,
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
