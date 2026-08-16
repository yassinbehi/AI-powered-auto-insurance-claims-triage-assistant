"""Data-loading tools and future business-logic stubs for claims triage."""

import csv
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_POLICIES_FILE = _DATA_DIR / "policies_auto.csv"
_CLAIMS_FILE = _DATA_DIR / "claims_auto.csv"


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def get_policy(policy_id: str) -> dict:
    """Return the policy row matching ``policy_id`` from policies_auto.csv."""
    for row in _read_csv_rows(_POLICIES_FILE):
        if row.get("policy_id") == policy_id:
            return row
    raise ValueError(f"Policy not found: {policy_id!r}")


def get_claim(claim_id: str) -> dict:
    """Return the claim row matching ``claim_id`` from claims_auto.csv."""
    for row in _read_csv_rows(_CLAIMS_FILE):
        if row.get("claim_id") == claim_id:
            return row
    raise ValueError(f"Claim not found: {claim_id!r}")


def check_coverage(policy_id: str, claim_type: str) -> dict:
    """TODO: implement"""
    pass


def estimate_repair_band(devis_tnd: str) -> dict:
    """TODO: implement"""
    pass


def detect_fraud_signals(claim: dict, policy: dict) -> dict:
    """TODO: implement"""
    pass
