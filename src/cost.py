"""
src/cost.py

Suivi cout/usage (budget_tokens.md: "Budget plafond: 5 USD. Budget cible:
1.50 a 2.75 USD."). Fonctions pures uniquement : aucun appel API, aucune
dependance au SDK anthropic (usage_to_dict fonctionne par duck-typing sur
l'objet .usage renvoye par le SDK OU sur un dict equivalent), pour rester
testable sans reseau.
"""

from typing import Optional

from config import (
    BUDGET_CEILING_USD,
    BUDGET_TARGET_MAX_USD,
    BUDGET_TARGET_MIN_USD,
    PRICE_CACHE_READ_PER_MTOK_USD,
    PRICE_CACHE_WRITE_5M_PER_MTOK_USD,
    PRICE_INPUT_PER_MTOK_USD,
    PRICE_OUTPUT_PER_MTOK_USD,
)

USAGE_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
)


def usage_to_dict(usage) -> dict:
    """Normalise un objet `.usage` du SDK (ou un dict deja equivalent) en
    dict simple avec les 4 champs USAGE_FIELDS (0 si absent)."""

    def _get(field):
        value = usage.get(field) if isinstance(usage, dict) else getattr(usage, field, None)
        return value or 0

    return {field: _get(field) for field in USAGE_FIELDS}


def calculate_cost_usd(usage: dict) -> float:
    """Cout en USD d'un usage donne. Suppose un cache TTL de 5 minutes (la
    seule TTL utilisee dans agent.py : cache_control sans ttl explicite)."""
    return (
        usage.get("input_tokens", 0) / 1_000_000 * PRICE_INPUT_PER_MTOK_USD
        + usage.get("output_tokens", 0) / 1_000_000 * PRICE_OUTPUT_PER_MTOK_USD
        + usage.get("cache_creation_input_tokens", 0) / 1_000_000 * PRICE_CACHE_WRITE_5M_PER_MTOK_USD
        + usage.get("cache_read_input_tokens", 0) / 1_000_000 * PRICE_CACHE_READ_PER_MTOK_USD
    )


def empty_usage_totals() -> dict:
    return {field: 0 for field in USAGE_FIELDS}


def accumulate_usage(totals: dict, usage: dict) -> dict:
    """Pure (renvoie un NOUVEAU dict, ne mute pas `totals`)."""
    return {field: totals.get(field, 0) + usage.get(field, 0) for field in USAGE_FIELDS}


def format_cost_report(totals: dict) -> dict:
    """Ajoute cost_usd et les flags de depassement de budget a un dict
    d'usage accumule (voir accumulate_usage)."""
    cost_usd = calculate_cost_usd(totals)
    over_ceiling = cost_usd > BUDGET_CEILING_USD
    over_target = cost_usd > BUDGET_TARGET_MAX_USD

    warning: Optional[str] = None
    if over_ceiling:
        warning = f"COUT ({cost_usd:.4f} USD) DEPASSE LE PLAFOND ({BUDGET_CEILING_USD} USD)."
    elif over_target:
        warning = f"Cout ({cost_usd:.4f} USD) au-dessus de la cible ({BUDGET_TARGET_MIN_USD}-{BUDGET_TARGET_MAX_USD} USD)."

    report = dict(totals)
    report["cost_usd"] = round(cost_usd, 4)
    report["budget_ceiling_usd"] = BUDGET_CEILING_USD
    report["budget_target_min_usd"] = BUDGET_TARGET_MIN_USD
    report["budget_target_max_usd"] = BUDGET_TARGET_MAX_USD
    report["over_ceiling"] = over_ceiling
    report["over_target"] = over_target
    report["warning"] = warning
    return report
