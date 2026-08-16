"""Simple entry point to verify data-loading functions."""

import json

from tools import get_claim, get_policy


def main() -> None:
    claim = get_claim("CLM-001")
    policy = get_policy(claim["policy_id"])

    print("Claim:")
    print(json.dumps(claim, indent=2, ensure_ascii=False))
    print()
    print("Policy:")
    print(json.dumps(policy, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
