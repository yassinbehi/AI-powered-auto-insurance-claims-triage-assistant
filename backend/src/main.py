"""
src/main.py

Point d'entree fonctionnel du triage de sinistres.

Traite des sinistres reels a partir de data/claims_auto.csv (et des polices
associees dans data/policies_auto.csv, recuperees par l'agent via les tools),
les fait passer par l'agent de triage (src/agent.py), et affiche le JSON de
triage produit pour chacun - avec les erreurs de validation (schema.py) et la
trace des appels d'outils pour tracabilite.

Ce fichier ne contient AUCUNE logique d'evaluation/grading (l'ancien harnais
code-grade et son dossier evals/ ont ete retires : ce n'etait pas souhaite
dans le code applicatif). claims_auto.csv reste la source de donnees des
sinistres a traiter.

Un seul mode d'execution : streaming avec boucle d'outils synchrone, un
appel API par sinistre (voir agent.triage_claim). Le mode batch a ete retire
du projet - voir la note en tete de src/agent.py.

Usage (depuis la racine du depot) :
    python backend/src/main.py               # tous les sinistres de claims_auto.csv
    python backend/src/main.py CLM-001       # un seul sinistre
    python backend/src/main.py CLM-001 CLM-002
"""

import argparse
import json
import sys
from typing import List, Optional

# Sortie JSON en UTF-8 quel que soit l'encodage par defaut de la console
# (ex. cp1252 sur Windows, qui plante des que la reponse du modele contient
# un caractere hors de son repertoire).
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

import anthropic

import agent
import cost
import guard
from tools import list_claim_ids


def run(
    claim_ids: Optional[List[str]] = None,
    client: Optional[anthropic.Anthropic] = None,
) -> List[dict]:
    """Traite une liste de sinistres (ou tous les sinistres de
    claims_auto.csv si claim_ids est omis) et renvoie leurs resultats de
    triage bruts (voir agent.triage_claim pour le format).
    """
    client = client or anthropic.Anthropic()
    claim_ids = claim_ids or list_claim_ids()
    return [agent.triage_claim(cid, client=client) for cid in claim_ids]


def main():
    parser = argparse.ArgumentParser(description="Triage des sinistres auto (data/claims_auto.csv).")
    parser.add_argument(
        "claim_id",
        nargs="*",
        help="Un ou plusieurs claim_id a traiter. Si omis: tous les sinistres de claims_auto.csv.",
    )
    args = parser.parse_args()

    results = run(claim_ids=args.claim_id or None)
    print(json.dumps(results, ensure_ascii=False, indent=2))

    # Cout sur stderr (jamais stdout, qui doit rester du JSON pur, ex.
    # `python src/main.py | jq .`). budget_tokens.md: plafond 5 USD, cible
    # 1.50-2.75 USD.
    usage_totals = cost.empty_usage_totals()
    for r in results:
        if "usage" in r:
            usage_totals = cost.accumulate_usage(usage_totals, r["usage"])

    # Les appels du filtre anti-injection (src/guard.py) ne passent pas par
    # agent.py : sans cette ligne ils seraient absents du total et le cout
    # affiche serait sous-estime (budget_tokens.md).
    guard_usage = guard.get_guard_usage_total()
    usage_totals = cost.accumulate_usage(usage_totals, guard_usage)

    report = cost.format_cost_report(usage_totals)
    guard_cost = cost.calculate_cost_usd(guard_usage)
    print(
        f"\n[cost] ${report['cost_usd']:.4f} "
        f"(dont ${guard_cost:.4f} de filtrage anti-injection ; "
        f"plafond {report['budget_ceiling_usd']} USD, "
        f"cible {report['budget_target_min_usd']}-{report['budget_target_max_usd']} USD)",
        file=sys.stderr,
    )
    if report["warning"]:
        print(f"[cost] {report['warning']}", file=sys.stderr)


if __name__ == "__main__":
    main()
