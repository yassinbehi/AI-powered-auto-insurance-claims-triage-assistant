"""
src/main.py

Point d'entree en ligne de commande du triage de sinistres.

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

AUCUNE ANALYSE AUTOMATIQUE (decision utilisateur) :
Cette commande a longtemps traite TOUS les sinistres du CSV quand on
l'appelait sans argument. C'est retire. Le sinistre a traiter doit desormais
etre nomme explicitement, pour deux raisons :

    1. Aucun triage ne doit partir sans que quelqu'un l'ait demande pour un
       dossier precis. La meme regle vaut dans l'interface web, ou l'analyse
       part d'un bouton, dossier par dossier, et ou aucun bouton "tout
       analyser" n'existe.
    2. Un appel sans argument declenchait huit appels de modele d'affilee,
       soit environ dix fois le cout d'une analyse, sur une simple faute de
       frappe.

Usage (depuis la racine du depot) :
    python backend/src/main.py CLM-001
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
import tools


def run(
    claim_ids: List[str],
    client: Optional[anthropic.Anthropic] = None,
) -> List[dict]:
    """Traite les sinistres nommes et renvoie leurs resultats de triage bruts
    (voir agent.triage_claim pour le format).

    `claim_ids` est OBLIGATOIRE et ne peut pas etre vide : il n'existe aucun
    comportement par defaut du type "traiter tout le fichier". Voir la note
    "AUCUNE ANALYSE AUTOMATIQUE" en tete de module.
    """
    if not claim_ids:
        raise ValueError(
            "Aucun sinistre a traiter : indiquez au moins un claim_id. "
            "Cette fonction ne traite jamais l'ensemble du fichier d'elle-meme."
        )

    # Les CSV de data/ sont les jeux d'essai du projet. La commande en
    # terminal les charge EXPLICITEMENT : depuis que le repli automatique a
    # ete retire, rien ne lit plus data/ sans qu'on le demande.
    tools.load_dataset_from_files()

    client = client or anthropic.Anthropic()
    return [agent.triage_claim(cid, client=client) for cid in claim_ids]


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Triage d'un ou plusieurs sinistres de data/claims_auto.csv. "
            "Chaque sinistre traite declenche un appel de modele."
        ),
    )
    # nargs="+" : argparse refuse la commande sans argument et affiche l'aide,
    # avant qu'aucun appel de modele ne parte.
    parser.add_argument(
        "claim_id",
        nargs="+",
        help="Un ou plusieurs claim_id a traiter, ex: CLM-001. Obligatoire.",
    )
    args = parser.parse_args()

    results = run(claim_ids=args.claim_id)
    print(json.dumps(results, ensure_ascii=False, indent=2))

    # Cout sur stderr (jamais stdout, qui doit rester du JSON pur, ex.
    # `python backend/src/main.py CLM-001 | jq .`). budget_tokens.md: plafond
    # 5 USD, cible 1.50-2.75 USD.
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
