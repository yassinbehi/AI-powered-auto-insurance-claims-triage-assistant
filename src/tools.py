"""Data-loading tools and future business-logic stubs for claims triage."""

import csv
import functools
from pathlib import Path

from config import CLAIMS_FILE, POLICIES_FILE


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as file:
            return list(csv.DictReader(file))
    except (OSError, UnicodeDecodeError, csv.Error):
        return []


def _build_index(path: Path, id_field: str) -> dict[str, dict[str, str]]:
    index: dict[str, dict[str, str]] = {}
    for row in _read_csv_rows(path):
        try:
            record_id = row.get(id_field, "").strip()
            if not record_id:
                continue
            index[record_id] = row
        except (AttributeError, TypeError, ValueError):
            continue
    return index


@functools.lru_cache(maxsize=1)
def _policies_by_id() -> dict[str, dict[str, str]]:
    return _build_index(POLICIES_FILE, "policy_id")


@functools.lru_cache(maxsize=1)
def _claims_by_id() -> dict[str, dict[str, str]]:
    return _build_index(CLAIMS_FILE, "claim_id")


def get_policy(policy_id: str) -> dict:
    """Return the policy row matching ``policy_id`` from policies_auto.csv."""
    try:
        return _policies_by_id()[policy_id]
    except KeyError as exc:
        raise ValueError(f"Policy not found: {policy_id!r}") from exc


def get_claim(claim_id: str) -> dict:
    """Return the claim row matching ``claim_id`` from claims_auto.csv."""
    try:
        return _claims_by_id()[claim_id]
    except KeyError as exc:
        raise ValueError(f"Claim not found: {claim_id!r}") from exc


def check_coverage(policy_id: str, claim_type: str) -> dict:
    """TODO: implement"""
    pass


def estimate_repair_band(devis_tnd: str) -> dict:
    """TODO: implement"""
    pass


def detect_fraud_signals(claim: dict, policy: dict) -> dict:
    """TODO: implement"""
    pass
