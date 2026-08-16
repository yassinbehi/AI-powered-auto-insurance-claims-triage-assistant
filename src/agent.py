"""
src/agent.py

Boucle agentique de triage, avec deux modes (decision utilisateur,
conversation) :

    - "normal" (defaut) : appel synchrone en streaming, boucle d'outils
      classique (tool_use -> execution -> tool_result -> ...), pour un
      triage en direct d'un seul sinistre. Repond a l'exigence de
      SUJET_PROJET.md: "Streaming reponse client".
    - "batch"  : pour traiter plusieurs sinistres a la fois sans attendre
      une reponse immediate (ex: evals, cf. budget_tokens.md: "Utiliser
      batch pour evals completes non urgentes").

LIMITE TECHNIQUE IMPORTANTE (a savoir avant d'utiliser le mode batch) :
L'API Batch d'Anthropic ne permet pas d'executer une boucle d'outils
synchrone au sein d'un meme item de batch (le modele ne peut pas "attendre"
un tool_result en plein milieu d'un job batch asynchrone). Pour rester
compatible avec les 5 tools tout en utilisant le batch, ce module :
    1. execute les 5 tools directement en Python (deterministes, aucun
       besoin d'un modele pour un simple lookup CSV / calcul de regles),
    2. envoie en UNE SEULE requete par sinistre (regroupees dans un seul
       batch job) tout le contexte deja calcule, en demandant au modele de
       ne produire QUE le JSON final conforme a contrat_sortie.md.
Le mode normal, lui, garde la vraie boucle agentique tool_use/tool_result,
car il est synchrone et peut se permettre d'attendre les tools a chaque
tour.

CACHE DE PROMPT (budget_tokens.md: "Cacher les regles sinistres") :
Le system prompt (prompts/system_prompt.md) et la liste des tools sont
identiques a chaque appel ; seule la partie sinistre change. On marque donc
le dernier bloc du system prompt et le dernier tool de la liste avec
cache_control: {"type": "ephemeral"}, ce qui met en cache tout ce qui
precede pour les appels suivants.

MODELE : budget_tokens.md precise "Modele par defaut: Claude Haiku 4.5."
-> on utilise ce modele par defaut dans les deux modes ; rien dans les
documents ne demande de changer de modele selon normal/batch.

CE QUI N'EST PAS IMPLEMENTE ICI (faute de specification dans les
documents) :
    - "piece jointe illisible" (cite dans SUJET_PROJET.md, "Gestion
      erreurs") : aucun des 5 tools ni claims_auto.csv ne modelise de piece
      jointe (image, PDF...). Rien a gerer sans une specification
      supplementaire.
    - "service garage indisponible" / "429 simule" : aucun service garage
      externe n'existe dans les documents du projet (tous les tools sont
      des lookups CSV locaux). Le retry ci-dessous couvre les erreurs
      reelles de l'API Anthropic (rate limit, erreurs transitoires), qui
      est la seule dependance externe reellement presente.
"""

import json
import os
import time
from typing import List, Optional

import anthropic

from tools import (
    GET_POLICY_TOOL_SCHEMA,
    GET_CLAIM_TOOL_SCHEMA,
    CHECK_COVERAGE_TOOL_SCHEMA,
    ESTIMATE_REPAIR_BAND_TOOL_SCHEMA,
    DETECT_FRAUD_SIGNALS_TOOL_SCHEMA,
    handle_get_policy_tool_call,
    handle_get_claim_tool_call,
    handle_check_coverage_tool_call,
    handle_estimate_repair_band_tool_call,
    handle_detect_fraud_signals_tool_call,
    get_policy,
    get_claim,
    check_coverage,
    estimate_repair_band,
    detect_fraud_signals,
    PolicyNotFound,
    ClaimNotFound,
)
from schema import validate_full


_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SRC_DIR)
SYSTEM_PROMPT_PATH = os.path.join(_PROJECT_ROOT, "prompts", "system_prompt.md")

# budget_tokens.md: "Modele par defaut: Claude Haiku 4.5."
MODEL = "claude-haiku-4-5-20251001"

# Non documente dans les fichiers du projet : garde-fou de securite pour
# eviter une boucle d'outils infinie. Valeur arbitraire, a ajuster.
MAX_TOOL_TURNS = 8

# Non documente : nombre de tentatives / delai de base pour le retry sur
# erreurs API Anthropic (rate limit, erreurs transitoires).
MAX_RETRIES = 3
RETRY_BASE_DELAY_SECONDS = 2

TOOL_HANDLERS = {
    "get_policy": handle_get_policy_tool_call,
    "get_claim": handle_get_claim_tool_call,
    "check_coverage": handle_check_coverage_tool_call,
    "estimate_repair_band": handle_estimate_repair_band_tool_call,
    "detect_fraud_signals": handle_detect_fraud_signals_tool_call,
}


def _load_system_prompt() -> str:
    with open(SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()


def _build_cached_system_blocks() -> list:
    """System prompt en un seul bloc texte, marque cacheable.

    Voir note "CACHE DE PROMPT" en tete de fichier.
    """
    return [
        {
            "type": "text",
            "text": _load_system_prompt(),
            "cache_control": {"type": "ephemeral"},
        }
    ]


def _build_cached_tools() -> list:
    """Liste des 5 tools, avec cache_control sur le dernier pour mettre en
    cache l'ensemble de la definition des tools (identique a chaque appel).
    """
    tools = [
        GET_POLICY_TOOL_SCHEMA,
        GET_CLAIM_TOOL_SCHEMA,
        CHECK_COVERAGE_TOOL_SCHEMA,
        ESTIMATE_REPAIR_BAND_TOOL_SCHEMA,
        DETECT_FRAUD_SIGNALS_TOOL_SCHEMA,
    ]
    tools = [dict(t) for t in tools]  # copies pour ne pas muter les originaux
    tools[-1] = {**tools[-1], "cache_control": {"type": "ephemeral"}}
    return tools


def _call_with_retry(fn, *args, **kwargs):
    """Retry avec backoff exponentiel sur les erreurs API Anthropic
    transitoires (rate limit, erreurs serveur). Non documente dans les
    fichiers du projet au-dela de la mention generale "Gestion erreurs" de
    SUJET_PROJET.md ; parametres (MAX_RETRIES, delai) arbitraires.
    """
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            return fn(*args, **kwargs)
        except (anthropic.RateLimitError, anthropic.APIStatusError, anthropic.APIConnectionError) as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_BASE_DELAY_SECONDS * (2 ** attempt))
    raise last_error


def _execute_tool_use_block(block) -> dict:
    handler = TOOL_HANDLERS.get(block.name)
    if handler is None:
        return {"error": f"Tool inconnu: {block.name}"}
    return handler(block.input)


# =============================================================================
# Mode "normal" : boucle agentique synchrone, en streaming.
# =============================================================================

def triage_claim_normal(claim_id: str, client: Optional[anthropic.Anthropic] = None) -> dict:
    """Triage d'un seul sinistre en mode normal (streaming, boucle d'outils
    synchrone). Retourne un dict avec le JSON de triage (si produit et
    valide), les erreurs de validation eventuelles, et l'historique des
    tool calls pour tracabilite (SUJET_PROJET.md: "traces par etape").
    """
    client = client or anthropic.Anthropic()

    messages = [
        {
            "role": "user",
            "content": (
                f"Traiter le sinistre {claim_id}. Utilise les tools "
                "necessaires puis produis uniquement le JSON de triage "
                "final conforme au contrat de sortie."
            ),
        }
    ]

    tool_call_trace = []
    claim_snapshot = None  # rempli des que get_claim est appele, pour la validation finale

    for _turn in range(MAX_TOOL_TURNS):
        with _call_with_retry(
            client.messages.stream,
            model=MODEL,
            max_tokens=1500,
            system=_build_cached_system_blocks(),
            tools=_build_cached_tools(),
            messages=messages,
        ) as stream:
            for _event in stream:
                pass  # le texte est deja diffuse au client via le stream ;
                      # ici on se contente de laisser le SDK accumuler le
                      # message final, recupere ci-dessous.
            final_message = stream.get_final_message()

        messages.append({"role": "assistant", "content": final_message.content})

        tool_use_blocks = [b for b in final_message.content if b.type == "tool_use"]

        if not tool_use_blocks:
            # Pas d'appel d'outil -> le modele a produit sa reponse finale.
            text_blocks = [b.text for b in final_message.content if b.type == "text"]
            final_text = "\n".join(text_blocks).strip()
            return _finalize_normal_result(claim_id, final_text, claim_snapshot, tool_call_trace)

        # Executer chaque tool_use et rattacher chaque tool_result au bon
        # tool_use_id (SUJET_PROJET.md: "tool_result correctement rattache
        # au tool_use").
        tool_results = []
        for block in tool_use_blocks:
            result = _execute_tool_use_block(block)
            tool_call_trace.append({"tool": block.name, "input": block.input, "output": result})

            if block.name == "get_claim" and "error" not in result:
                claim_snapshot = result

            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )

        messages.append({"role": "user", "content": tool_results})

    return {
        "claim_id": claim_id,
        "error": f"Nombre maximal de tours d'outils atteint ({MAX_TOOL_TURNS}) sans reponse finale.",
        "tool_call_trace": tool_call_trace,
    }


def _finalize_normal_result(claim_id, final_text, claim_snapshot, tool_call_trace) -> dict:
    try:
        parsed = json.loads(final_text)
    except json.JSONDecodeError:
        return {
            "claim_id": claim_id,
            "error": "La reponse finale du modele n'est pas un JSON valide.",
            "raw_output": final_text,
            "tool_call_trace": tool_call_trace,
        }

    blessure = bool(claim_snapshot and claim_snapshot.get("blessure") == "oui")
    validation_errors = validate_full(parsed, blessure=blessure)

    return {
        "claim_id": claim_id,
        "output": parsed,
        "validation_errors": validation_errors,
        "tool_call_trace": tool_call_trace,
    }


# =============================================================================
# Mode "batch" : tools executes localement, un seul appel modele par
# sinistre (regroupes dans un batch job), pas de boucle d'outils
# synchrone. Voir note "LIMITE TECHNIQUE IMPORTANTE" en tete de fichier.
# =============================================================================

def _prefetch_context(claim_id: str) -> dict:
    """Execute localement les 5 tools pour un sinistre, sans passer par le
    modele (ils sont deterministes). Renvoie soit le contexte complet, soit
    une erreur si le claim/policy est introuvable.
    """
    try:
        claim = get_claim(claim_id)
    except ClaimNotFound as e:
        return {"error": str(e)}

    try:
        policy = get_policy(claim["policy_id"])
    except PolicyNotFound as e:
        return {"error": str(e)}

    coverage = check_coverage(policy, claim)
    repair_band = estimate_repair_band(claim["devis_tnd"])
    fraud_signals = detect_fraud_signals(claim, policy)

    return {
        "claim": claim,
        "policy": policy,
        "coverage": coverage,
        "repair_band": repair_band,
        "fraud_signals": fraud_signals,
    }


def _build_batch_user_message(context: dict) -> str:
    return (
        "Voici le contexte deja calcule pour ce sinistre (resultats des "
        "tools get_claim, get_policy, check_coverage, estimate_repair_band, "
        "detect_fraud_signals). N'appelle aucun tool : produis directement "
        "et uniquement le JSON de triage final conforme au contrat de "
        "sortie, a partir de ce contexte.\n\n"
        f"{json.dumps(context, ensure_ascii=False, indent=2)}"
    )


def submit_batch_triage(claim_ids: List[str], client: Optional[anthropic.Anthropic] = None) -> str:
    """Soumet un job batch pour plusieurs sinistres. Retourne l'id du batch.

    Les sinistres dont le contexte ne peut pas etre pre-calcule (claim_id ou
    policy_id introuvable) sont exclus du batch et remontes separement,
    plutot que d'envoyer un item invalide au modele.
    """
    client = client or anthropic.Anthropic()

    requests = []
    skipped = []
    for claim_id in claim_ids:
        context = _prefetch_context(claim_id)
        if "error" in context:
            skipped.append({"claim_id": claim_id, "error": context["error"]})
            continue

        requests.append(
            {
                "custom_id": claim_id,
                "params": {
                    "model": MODEL,
                    "max_tokens": 1000,
                    "system": _build_cached_system_blocks(),
                    "messages": [
                        {"role": "user", "content": _build_batch_user_message(context)}
                    ],
                },
            }
        )

    if not requests:
        raise ValueError(f"Aucun sinistre valide a soumettre. Ignores: {skipped}")

    batch = _call_with_retry(client.messages.batches.create, requests=requests)
    return batch.id


def retrieve_batch_results(batch_id: str, client: Optional[anthropic.Anthropic] = None) -> List[dict]:
    """Recupere et valide les resultats d'un batch deja termine.

    Ne bloque pas en attendant que le batch se termine : appelant
    responsable de verifier `client.messages.batches.retrieve(batch_id).processing_status`
    avant d'appeler cette fonction (non fait automatiquement ici, car un
    batch peut prendre longtemps et ce module ne doit pas bloquer
    indefiniment sans que l'appelant le decide explicitement).
    """
    client = client or anthropic.Anthropic()
    results = []

    for entry in client.messages.batches.results(batch_id):
        claim_id = entry.custom_id

        if entry.result.type != "succeeded":
            results.append({"claim_id": claim_id, "error": f"Batch item echoue: {entry.result.type}"})
            continue

        message = entry.result.message
        text_blocks = [b.text for b in message.content if b.type == "text"]
        final_text = "\n".join(text_blocks).strip()

        try:
            parsed = json.loads(final_text)
        except json.JSONDecodeError:
            results.append(
                {"claim_id": claim_id, "error": "JSON invalide dans la reponse batch.", "raw_output": final_text}
            )
            continue

        # blessure necessaire pour valider validation_humaine_requise ;
        # recuperee via un nouveau get_claim local (pas d'appel API).
        try:
            claim = get_claim(claim_id)
            blessure = claim.get("blessure") == "oui"
        except ClaimNotFound:
            blessure = False

        validation_errors = validate_full(parsed, blessure=blessure)
        results.append({"claim_id": claim_id, "output": parsed, "validation_errors": validation_errors})

    return results


# =============================================================================
# Point d'entree unique, avec le choix de mode laisse a l'appelant
# (decision utilisateur : defaut = normal, option = batch).
# =============================================================================

def triage(claim_id: str, mode: str = "normal", client: Optional[anthropic.Anthropic] = None) -> dict:
    """Point d'entree pour un triage a l'unite.

    mode="normal" (defaut) : streaming, boucle d'outils synchrone.
    mode="batch" : soumet un batch d'un seul item et attend sa completion en
        interrogeant periodiquement le statut (poll). Utile pour tester le
        mode batch sur un seul sinistre ; pour un vrai usage en masse,
        preferer submit_batch_triage() + retrieve_batch_results() separement
        pour ne pas bloquer sur l'attente.
    """
    if mode == "normal":
        return triage_claim_normal(claim_id, client=client)

    if mode == "batch":
        client = client or anthropic.Anthropic()
        batch_id = submit_batch_triage([claim_id], client=client)
        while True:
            status = client.messages.batches.retrieve(batch_id).processing_status
            if status == "ended":
                break
            time.sleep(5)
        results = retrieve_batch_results(batch_id, client=client)
        return results[0] if results else {"claim_id": claim_id, "error": "Aucun resultat batch."}

    raise ValueError(f"mode invalide: {mode!r} (attendu 'normal' ou 'batch').")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python3 agent.py <claim_id> [normal|batch]")
        sys.exit(1)

    claim_id_arg = sys.argv[1]
    mode_arg = sys.argv[2] if len(sys.argv) > 2 else "normal"

    result = triage(claim_id_arg, mode=mode_arg)
    print(json.dumps(result, ensure_ascii=False, indent=2))