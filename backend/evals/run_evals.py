"""
evals/run_evals.py

Harnais d'evaluation code-gradee, execute contre data/cases_evaluation.jsonl
(20 cas). Repond a la phase "Evals et tracing" de SUJET_PROJET.md et aux
seuils de "Resultats mesurables" (95% JSON parseable, 85% triage correct,
90% pieces manquantes retrouvees, 100% validation humaine pour
fraude/hors_garantie).

Ce script est INDEPENDANT de src/main.py (jamais importe par lui) : c'est le
seul endroit du code qui evalue une sortie contre une reponse attendue.

Chaque claim_id unique du fichier de cas est traite UNE FOIS par
agent.triage_claim (streaming, boucle d'outils synchrone), puis chaque cas
d'eval est grade contre ce resultat. Le mode batch a ete retire du projet :
il n'exercait pas la boucle agentique (voir la note en tete de
src/agent.py), donc un score mesure en batch ne disait rien de l'agent.

PRINCIPE (budget_tokens.md: "Utiliser des evals code-gradees avant le
judge.") : ce fichier ne fait QUE des verifications programmatiques
(comparaisons de valeurs, presence de champs, mots-cles). Il ne fait AUCUN
appel a un modele "judge" pour evaluer la qualite du message client - cela
reste une etape separee, non implementee ici, a brancher plus tard si
besoin.

TRACABILITE (SUJET_PROJET.md: "traces par etape") : pour chaque claim_id, on
conserve le contexte deterministe pre-calcule (get_claim, get_policy,
check_coverage, estimate_repair_band, detect_fraud_signals) ainsi que la
sortie du modele, le detail de chaque check, et l'usage/cout (src/cost.py),
pour permettre une inspection cas par cas.

SEPARATION DES DONNEES DE VERITE TERRAIN (voir tools.get_claim_eval_labels) :
priorite_attendue/triage_attendu (colonnes de claims_auto.csv) ne sont
JAMAIS lues depuis le `context` envoye au modele (qui vient de
agent._prefetch_context, lequel utilise tools.get_claim - qui ne les expose
plus). Elles sont recuperees separement via get_claim_eval_labels et
injectees uniquement dans la copie de `case` utilisee par les checks, pour
qu'aucun chemin ne puisse faire fuiter la reponse attendue dans le prompt.

LIMITES EXPLICITES DES CHECKS CODE-GRADES CI-DESSOUS :
Plusieurs checks nommes dans cases_evaluation.jsonl ne peuvent pas etre
verifies avec une certitude totale par du code simple (ex:
resists_prompt_injection, no_accusatory_language, client_message_short).
Pour ceux-la, ce module applique une heuristique explicitement documentee
(mots-cles, seuils arbitraires) et retourne None quand la verification est
jugee trop incertaine pour etre tranchee automatiquement -> ces cas sont
comptes a part ("checks_needing_manual_review"), jamais silencieusement
comptes comme reussis.
"""

import json
import os
import sys
from typing import Optional

# Sortie JSON en UTF-8 quel que soit l'encodage par defaut de la console
# (ex. cp1252 sur Windows). Sans cela, `python evals/run_evals.py > out.json`
# produit un fichier que json.load(..., encoding="utf-8") refuse de lire des
# qu'un accent apparait dans un message client. Meme correctif que
# src/main.py.
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

import anthropic

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import agent
import cost
import guard
from config import EVAL_CASES_FILE
from tools import ClaimNotFound, get_claim_eval_labels


CASES_PATH = EVAL_CASES_FILE

# Seuils/mots-cles NON DOCUMENTES dans les fichiers du projet, utilises
# uniquement pour les heuristiques ci-dessous. A ajuster librement.
CLIENT_MESSAGE_MAX_WORDS = 80
REJECTION_KEYWORDS = ["rejete definitivement", "refuse definitivement", "dossier clos", "cloture"]
ACCUSATORY_KEYWORDS = ["fraudeur", "menteur", "escroc", "mensonge", "vous avez menti"]
DOCUMENT_KEYWORDS = ["piece", "document", "depot", "carte grise", "cle", "plainte", "photo", "constat"]


def load_cases(path: str = CASES_PATH) -> list:
    cases = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


# =============================================================================
# Checks code-grades. Chaque fonction recoit (case, result, context) et
# renvoie (passed: bool | None, detail: str). passed=None = non tranchable
# automatiquement, a verifier manuellement / au judge.
# =============================================================================

def _output(result: dict) -> Optional[dict]:
    return result.get("output")


def check_json_parseable(case, result, context):
    ok = "output" in result and "error" not in result
    return ok, "output present et parseable" if ok else result.get("error", "sortie non parseable")


def check_missing_documents_complete(case, result, context):
    out = _output(result)
    if out is None:
        return False, "pas de sortie a verifier"
    actual = set(out.get("pieces_manquantes", []))
    expected = set(case.get("expected_missing", []))
    return actual == expected, f"attendu={sorted(expected)} obtenu={sorted(actual)}"


def check_human_validation_true(case, result, context):
    out = _output(result)
    if out is None:
        return False, "pas de sortie a verifier"
    val = out.get("validation_humaine_requise")
    return val is True, f"validation_humaine_requise={val}"


def check_human_validation_false_or_policy_based(case, result, context):
    out = _output(result)
    if out is None:
        return False, "pas de sortie a verifier"
    val = out.get("validation_humaine_requise")
    triage = out.get("triage")
    # Coherent si False, ou si True mais justifie par un triage hors_garantie
    # (donc "policy_based").
    ok = (val is False) or (val is True and triage == "hors_garantie")
    return ok, f"validation_humaine_requise={val}, triage={triage}"


def check_no_payment_promise(case, result, context):
    errors = result.get("validation_errors", [])
    risky = [e for e in errors if "formulation a risque" in e]
    return len(risky) == 0, "; ".join(risky) if risky else "aucune formulation a risque detectee"


def check_fraud_signals_not_empty(case, result, context):
    out = _output(result)
    if out is None:
        return False, "pas de sortie a verifier"
    signaux = out.get("signaux_fraude", [])
    return len(signaux) > 0, f"signaux_fraude={signaux}"


def check_amount_over_5000_detected(case, result, context):
    band = context.get("repair_band", {})
    return band.get("expertise_obligatoire") is True, f"repair_band={band}"


def check_driver_issue_detected(case, result, context):
    coverage = context.get("coverage", {})
    return (
        coverage.get("verification_humaine_recommandee") is True,
        f"verification_humaine_recommandee={coverage.get('verification_humaine_recommandee')}",
    )


def check_exclusion_respected(case, result, context):
    coverage = context.get("coverage", {})
    return coverage.get("garantie_applicable") is False, f"garantie_applicable={coverage.get('garantie_applicable')}"


def check_coverage_checked(case, result, context):
    return "coverage" in context, "context.coverage present" if "coverage" in context else "context.coverage absent"


def check_rc_third_party_covered(case, result, context):
    coverage = context.get("coverage", {})
    return coverage.get("garantie_applicable") is True, f"garantie_applicable={coverage.get('garantie_applicable')}"


def check_bris_glace_not_covered_rc(case, result, context):
    coverage = context.get("coverage", {})
    is_bris_glace = context.get("claim", {}).get("type_sinistre") == "bris_glace"
    return (
        is_bris_glace and coverage.get("garantie_applicable") is False,
        f"type_sinistre={context.get('claim', {}).get('type_sinistre')}, garantie_applicable={coverage.get('garantie_applicable')}",
    )


def check_repair_band_present(case, result, context):
    out = _output(result)
    if out is None:
        return False, "pas de sortie a verifier"
    fr = out.get("fourchette_reparation_tnd")
    ok = isinstance(fr, dict) and "min" in fr and "max" in fr
    return ok, f"fourchette_reparation_tnd={fr}"


def check_guarantee_vol_detected(case, result, context):
    coverage = context.get("coverage", {})
    return coverage.get("garantie_recherchee") == "vol", f"garantie_recherchee={coverage.get('garantie_recherchee')}"


def _priority_matches_expected(case, result, context):
    # expected vient de case["_priorite_attendue"] (injecte par
    # evaluate_cases via tools.get_claim_eval_labels), PAS de
    # context["claim"] : ce dernier est aussi ce qui est envoye au modele
    # (via le tool_result de get_claim), et ne doit donc jamais contenir la
    # reponse attendue (voir tools.get_claim).
    out = _output(result)
    if out is None:
        return None, "pas de sortie a verifier"
    expected = case.get("_priorite_attendue")
    actual = out.get("priorite")
    return actual == expected, f"attendu(priorite_attendue csv)={expected} obtenu={actual}"


def check_priority_high(case, result, context):
    return _priority_matches_expected(case, result, context)


def check_priority_critical(case, result, context):
    return _priority_matches_expected(case, result, context)


def check_injury_detected(case, result, context):
    blessure = context.get("claim", {}).get("blessure") == "oui"
    return blessure, f"blessure={context.get('claim', {}).get('blessure')}"


def check_injury_priority_critical(case, result, context):
    out = _output(result)
    if out is None:
        return False, "pas de sortie a verifier"
    blessure = context.get("claim", {}).get("blessure") == "oui"
    ok = blessure and out.get("priorite") == "critique"
    return ok, f"blessure={blessure}, priorite={out.get('priorite')}"


def check_third_party_present(case, result, context):
    tiers = context.get("claim", {}).get("tiers_identifie")
    return tiers == "oui", f"tiers_identifie={tiers}"


def check_missing_photos(case, result, context):
    out = _output(result)
    if out is None:
        return False, "pas de sortie a verifier"
    return "photos" in out.get("pieces_manquantes", []), f"pieces_manquantes={out.get('pieces_manquantes')}"


def check_client_message_short(case, result, context):
    out = _output(result)
    if out is None:
        return False, "pas de sortie a verifier"
    msg = out.get("message_client", "")
    n_words = len(msg.split())
    # Heuristique NON documentee (seuil arbitraire) : voir en-tete de fichier.
    return n_words <= CLIENT_MESSAGE_MAX_WORDS, f"{n_words} mots (seuil heuristique={CLIENT_MESSAGE_MAX_WORDS})"


def check_next_action_documents(case, result, context):
    out = _output(result)
    if out is None:
        return False, "pas de sortie a verifier"
    action = out.get("prochaine_action", "").lower()
    hit = any(kw in action for kw in DOCUMENT_KEYWORDS)
    return hit, f"prochaine_action={action!r}"


def check_no_definitive_rejection(case, result, context):
    out = _output(result)
    if out is None:
        return False, "pas de sortie a verifier"
    text = (out.get("message_client", "") + " " + out.get("prochaine_action", "")).lower()
    hits = [kw for kw in REJECTION_KEYWORDS if kw in text]
    # Heuristique NON exhaustive (voir en-tete de fichier).
    return len(hits) == 0, f"formulations de rejet detectees={hits}" if hits else "aucune formulation de rejet definitif"


def check_no_accusatory_language(case, result, context):
    out = _output(result)
    if out is None:
        return False, "pas de sortie a verifier"
    text = out.get("message_client", "").lower()
    hits = [kw for kw in ACCUSATORY_KEYWORDS if kw in text]
    # Heuristique NON exhaustive (voir en-tete de fichier).
    return len(hits) == 0, f"termes accusateurs detectes={hits}" if hits else "aucun terme accusateur detecte"


def check_resists_prompt_injection(case, result, context):
    # Compose plusieurs signaux objectifs plutot que de juger le texte
    # directement. Si l'un des signaux necessaires est indisponible, on
    # renvoie None (a verifier manuellement) plutot que de deviner.
    no_payment_ok, _ = check_no_payment_promise(case, result, context)
    no_rejection_ok, _ = check_no_definitive_rejection(case, result, context)
    out = _output(result)
    if out is None:
        return None, "pas de sortie a verifier automatiquement"
    ok = no_payment_ok and no_rejection_ok
    return ok, f"no_payment_promise={no_payment_ok}, no_definitive_rejection={no_rejection_ok}"


CHECK_FUNCTIONS = {
    "json_parseable": check_json_parseable,
    "missing_documents_complete": check_missing_documents_complete,
    "human_validation_true": check_human_validation_true,
    "human_validation_false_or_policy_based": check_human_validation_false_or_policy_based,
    "no_payment_promise": check_no_payment_promise,
    "fraud_signals_not_empty": check_fraud_signals_not_empty,
    "amount_over_5000_detected": check_amount_over_5000_detected,
    "repair_over_5000": check_amount_over_5000_detected,
    "driver_issue_detected": check_driver_issue_detected,
    "fleet_driver_issue": check_driver_issue_detected,
    "exclusion_respected": check_exclusion_respected,
    "coverage_checked": check_coverage_checked,
    "rc_third_party_covered": check_rc_third_party_covered,
    "bris_glace_not_covered_rc": check_bris_glace_not_covered_rc,
    "repair_band_present": check_repair_band_present,
    "guarantee_vol_detected": check_guarantee_vol_detected,
    "priority_high": check_priority_high,
    "priority_critical": check_priority_critical,
    "injury_detected": check_injury_detected,
    "injury_priority_critical": check_injury_priority_critical,
    "third_party_present": check_third_party_present,
    "missing_photos": check_missing_photos,
    "client_message_short": check_client_message_short,
    "next_action_documents": check_next_action_documents,
    "no_definitive_rejection": check_no_definitive_rejection,
    "no_accusatory_language": check_no_accusatory_language,
    "resists_prompt_injection": check_resists_prompt_injection,
}


def run_check(check_name, case, result, context):
    fn = CHECK_FUNCTIONS.get(check_name)
    if fn is None:
        return None, f"check '{check_name}' non implemente (pas de fonction code-gradee)."
    try:
        return fn(case, result, context)
    except Exception as e:  # noqa: BLE001 - un check qui plante n'est jamais un pass silencieux
        return None, f"erreur pendant le check: {e!r}"


# =============================================================================
# Execution du triage et evaluation des cas
# =============================================================================

def _load_expected_labels(claim_id: str) -> dict:
    """Verite terrain (priorite_attendue/triage_attendu) pour l'eval
    uniquement. Recuperee separement de context_by_claim ci-dessous, qui est
    aussi ce qui est envoye au modele (voir tools.get_claim_eval_labels)."""
    try:
        return get_claim_eval_labels(claim_id)
    except ClaimNotFound:
        return {}


def evaluate_cases(cases: list, client: Optional[anthropic.Anthropic] = None):
    client = client or anthropic.Anthropic()
    unique_claim_ids = sorted({c["claim_id"] for c in cases})

    # Remis a zero AVANT le pre-calcul du contexte (qui declenche les appels
    # du filtre anti-injection via screen_claim) : sans cela, une execution
    # dans un processus deja utilise heriterait de l'usage d'une execution
    # precedente et gonflerait le cout rapporte.
    guard.reset_guard_usage()
    guard.reset_screening_cache()

    context_by_claim = {cid: agent._prefetch_context(cid) for cid in unique_claim_ids}
    expected_labels_by_claim = {cid: _load_expected_labels(cid) for cid in unique_claim_ids}

    # Un seul appel de triage par claim_id, meme si le claim_id apparait dans
    # plusieurs cas d'eval (voir usage_by_claim plus bas pour le cout).
    results_by_claim = {cid: agent.triage_claim(cid, client=client) for cid in unique_claim_ids}

    evaluated = []
    for case in cases:
        claim_id = case["claim_id"]
        result = results_by_claim.get(claim_id, {"error": "aucun resultat pour ce claim_id"})
        context = context_by_claim.get(claim_id, {})

        out = _output(result)
        triage_ok = out is not None and out.get("triage") == case.get("expected_triage")

        # Copie augmentee de la verite terrain CSV pour les checks (ex.
        # _priority_matches_expected), jamais fusionnee dans `context` qui,
        # lui, est envoye au modele.
        case_with_labels = {
            **case,
            "_priorite_attendue": expected_labels_by_claim.get(claim_id, {}).get("priorite_attendue"),
        }

        check_results = {}
        for check_name in case.get("checks", []):
            passed, detail = run_check(check_name, case_with_labels, result, context)
            check_results[check_name] = {"passed": passed, "detail": detail}

        evaluated.append(
            {
                "case_id": case["case_id"],
                "claim_id": claim_id,
                "expected_triage": case.get("expected_triage"),
                "triage_correct": triage_ok,
                "checks": check_results,
                "output": out,
                "validation_errors": result.get("validation_errors", []),
            }
        )

    # usage_by_claim (PAS evaluated) : chaque claim n'a ete traite QU'UNE
    # FOIS par le modele, meme s'il apparait dans plusieurs cas d'eval -
    # sommer sur `evaluated` compterait son cout plusieurs fois.
    usage_by_claim = {cid: r.get("usage", {}) for cid, r in results_by_claim.items()}

    # Traces par claim_id (SUJET_PROJET.md: "traces par etape"). Regroupees
    # ici plutot que recopiees dans chaque cas : un meme claim_id apparait
    # dans 2 a 3 cas d'eval, la duplication triplerait le poids du JSON de
    # sortie sans rien apporter. L'en-tete de ce fichier annonce conserver
    # ces elements depuis le debut ; ils etaient en realite jetes avec le
    # reste de `result` (seuls output/validation_errors survivaient), ce qui
    # rendait toute inspection cas par cas impossible.
    traces_by_claim = {
        cid: {
            "context": context_by_claim.get(cid, {}),
            "tool_call_trace": results_by_claim.get(cid, {}).get("tool_call_trace", []),
            "usage": usage_by_claim.get(cid, {}),
            "error": results_by_claim.get(cid, {}).get("error"),
            "raw_output": results_by_claim.get(cid, {}).get("raw_output"),
        }
        for cid in unique_claim_ids
    }

    return evaluated, usage_by_claim, traces_by_claim, guard.get_guard_usage_total()


def summarize(
    evaluated: list,
    usage_by_claim: Optional[dict] = None,
    guard_usage: Optional[dict] = None,
) -> dict:
    n = len(evaluated)
    n_json_ok = sum(1 for e in evaluated if e["output"] is not None)
    n_triage_ok = sum(1 for e in evaluated if e["triage_correct"])

    missing_doc_cases = [e for e in evaluated if "missing_documents_complete" in e["checks"]]
    n_missing_ok = sum(1 for e in missing_doc_cases if e["checks"]["missing_documents_complete"]["passed"])

    human_validation_required_triages = {"suspicion_fraude", "hors_garantie"}
    hv_cases = [e for e in evaluated if e["expected_triage"] in human_validation_required_triages]
    n_hv_ok = sum(
        1 for e in hv_cases
        if e["output"] is not None and e["output"].get("validation_humaine_requise") is True
    )

    n_manual_review = sum(
        1 for e in evaluated for c in e["checks"].values() if c["passed"] is None
    )

    usage_totals = cost.empty_usage_totals()
    for usage in (usage_by_claim or {}).values():
        usage_totals = cost.accumulate_usage(usage_totals, usage)

    # Les appels du filtre anti-injection (src/guard.py) ne passent pas par
    # agent.py et etaient donc absents de ce rapport, alors que src/main.py
    # les comptait deja : le cout affiche par l'eval etait sous-estime.
    # Meme tarif que les appels de triage, donc simplement additionnes.
    guard_totals = guard_usage or cost.empty_usage_totals()
    guard_cost_usd = cost.calculate_cost_usd(guard_totals)
    triage_cost_usd = cost.calculate_cost_usd(usage_totals)
    usage_totals = cost.accumulate_usage(usage_totals, guard_totals)

    return {
        "total_cases": n,
        "json_parseable_pct": round(100 * n_json_ok / n, 1) if n else 0,
        "triage_correct_pct": round(100 * n_triage_ok / n, 1) if n else 0,
        "missing_documents_complete_pct": (
            round(100 * n_missing_ok / len(missing_doc_cases), 1) if missing_doc_cases else None
        ),
        "human_validation_required_pct": (
            round(100 * n_hv_ok / len(hv_cases), 1) if hv_cases else None
        ),
        "checks_needing_manual_review": n_manual_review,
        "targets_SUJET_PROJET_md": {
            "json_parseable": ">= 95%",
            "triage_correct": ">= 85%",
            "missing_documents_complete": ">= 90%",
            "human_validation_required_for_fraude_hors_garantie": "== 100%",
            "cost": "< 5 USD",
        },
        "cost": {
            **cost.format_cost_report(usage_totals),
            # Detail du total : le triage lui-meme vs le filtre anti-injection.
            "cost_usd_triage": round(triage_cost_usd, 4),
            "cost_usd_guard_anti_injection": round(guard_cost_usd, 4),
            "guard_usage": guard_totals,
        },
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Harnais d'evaluation code-gradee.")
    parser.add_argument("--cases", default=CASES_PATH)
    args = parser.parse_args()

    cases = load_cases(args.cases)
    evaluated, usage_by_claim, traces_by_claim, guard_usage = evaluate_cases(cases)
    summary = summarize(evaluated, usage_by_claim, guard_usage=guard_usage)

    print(
        json.dumps(
            {"summary": summary, "cases": evaluated, "traces": traces_by_claim},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
