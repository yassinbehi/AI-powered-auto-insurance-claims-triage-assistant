"""
src/main.py

Point d'entree fonctionnel du triage de sinistres.

Traite des sinistres reels a partir de data/claims_auto.csv (et des polices
associees dans data/policies_auto.csv, recuperees par l'agent via les tools),
les fait passer par l'agent de triage (src/agent.py), et affiche le JSON de
triage produit pour chacun - avec les erreurs de validation (schema.py) et,
en mode normal, la trace des appels d'outils pour tracabilite.

Ce fichier ne contient AUCUNE logique d'evaluation/grading (l'ancien harnais
code-grade et son dossier evals/ ont ete retires : ce n'etait pas souhaite
dans le code applicatif). claims_auto.csv reste la source de donnees des
sinistres a traiter.

Choix du mode laisse a l'utilisateur via --mode (voir triage_claim_normal et
submit_batch_triage/retrieve_batch_results dans agent.py) :
    - normal (streaming, boucle d'outils synchrone, un appel API par sinistre)
    - batch  (tools executes localement, un seul job groupe pour tous les
      sinistres - par defaut, plus economique pour traiter plusieurs
      sinistres a la fois)

Usage:
    python src/main.py                       # tous les sinistres, mode normal (defaut)
    python src/main.py --mode batch           # tous les sinistres, mode batch
    python src/main.py CLM-001                # un seul sinistre, mode normal
    python src/main.py CLM-001 CLM-002 --mode batch
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
from tools import list_claim_ids


def _run_batch(claim_ids: List[str], client: anthropic.Anthropic) -> List[dict]:
    batch_id = agent.submit_batch_triage(claim_ids, client=client)
    agent.wait_for_batch(batch_id, client=client)
    return agent.retrieve_batch_results(batch_id, client=client)


def run(
    claim_ids: Optional[List[str]] = None,
    mode: str = "normal",
    client: Optional[anthropic.Anthropic] = None,
) -> List[dict]:
    """Traite une liste de sinistres (ou tous les sinistres de
    claims_auto.csv si claim_ids est omis) et renvoie leurs resultats de
    triage bruts (voir agent.triage_claim_normal / agent.retrieve_batch_results
    pour le format).
    """
    client = client or anthropic.Anthropic()
    claim_ids = claim_ids or list_claim_ids()

    if mode == "batch":
        return _run_batch(claim_ids, client)
    if mode == "normal":
        return [agent.triage_claim_normal(cid, client=client) for cid in claim_ids]
    raise ValueError(f"mode invalide: {mode!r} (attendu 'normal' ou 'batch').")


def main():
    parser = argparse.ArgumentParser(description="Triage des sinistres auto (data/claims_auto.csv).")
    parser.add_argument(
        "claim_id",
        nargs="*",
        help="Un ou plusieurs claim_id a traiter. Si omis: tous les sinistres de claims_auto.csv.",
    )
    parser.add_argument(
        "--mode",
        choices=["batch", "normal"],
        default="normal",
        help=(
            "'normal' (streaming, boucle d'outils synchrone, un appel API par "
            "sinistre) ou 'batch' (tools executes localement, un seul job "
            "groupe pour tous les sinistres). Defaut: normal."
        ),
    )
    args = parser.parse_args()

    results = run(claim_ids=args.claim_id or None, mode=args.mode)
    print(json.dumps(results, ensure_ascii=False, indent=2))

    # Cout sur stderr (jamais stdout, qui doit rester du JSON pur, ex.
    # `python src/main.py | jq .`). budget_tokens.md: plafond 5 USD, cible
    # 1.50-2.75 USD.
    usage_totals = cost.empty_usage_totals()
    for r in results:
        if "usage" in r:
            usage_totals = cost.accumulate_usage(usage_totals, r["usage"])
    report = cost.format_cost_report(usage_totals)
    print(
        f"\n[cost] ${report['cost_usd']:.4f} "
        f"(plafond {report['budget_ceiling_usd']} USD, "
        f"cible {report['budget_target_min_usd']}-{report['budget_target_max_usd']} USD)",
        file=sys.stderr,
    )
    if report["warning"]:
        print(f"[cost] {report['warning']}", file=sys.stderr)


if __name__ == "__main__":
    main()
