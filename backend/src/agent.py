"""
src/agent.py

Boucle agentique de triage : appel synchrone en streaming, boucle d'outils
classique (tool_use -> execution -> tool_result -> ...), pour un triage en
direct d'un sinistre. Repond a l'exigence de SUJET_PROJET.md: "Streaming
reponse client" et "Agent loop avec tool_result correctement rattache au
tool_use".

MODE BATCH RETIRE (decision utilisateur, 20/08/2026) :
Ce module a longtemps propose un second mode "batch" (API Batch d'Anthropic,
-50% sur le tarif) pour traiter plusieurs sinistres sans reponse immediate.
Il a ete supprime de tout le projet. La raison de fond : l'API Batch ne
permet pas de derouler une boucle d'outils synchrone au sein d'un item de
batch (le modele ne peut pas "attendre" un tool_result au milieu d'un job
asynchrone). Le mode batch devait donc executer les 5 tools en Python et
n'envoyer au modele que le contexte deja calcule - autrement dit il
n'exercait PAS la boucle agentique, qui est justement le coeur du sujet. Un
score mesure en batch ne disait rien de l'agent.

A NOTER : budget_tokens.md demande "Utiliser batch pour evals completes non
urgentes". Le projet s'ecarte donc volontairement de cette ligne, au profit
d'un mode unique qui exerce reellement la boucle d'outils. Le cache de
prompt (ci-dessous) reste l'optimisation de cout principale.

CACHE DE PROMPT (budget_tokens.md: "Cacher les regles sinistres") :
Le system prompt (prompts/system_prompt.md) et la liste des tools sont
identiques a chaque appel ; seule la partie sinistre change. On marque donc
le dernier bloc du system prompt et le dernier tool de la liste avec
cache_control: {"type": "ephemeral"}, ce qui met en cache tout ce qui
precede pour les appels suivants.

MODELE : budget_tokens.md precise "Modele par defaut: Claude Haiku 4.5."
-> c'est le modele utilise ici.

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
import re
import time
from typing import Optional

import anthropic

import cost
from config import (
    MAX_RETRIES,
    MAX_TOKENS,
    MAX_TOOL_TURNS,
    MODEL,
    REGLES_SINISTRES_FILE,
    RETRY_BASE_DELAY_SECONDS,
    SYSTEM_PROMPT_PATH,
    TEMPERATURE,
)
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
from guard import screen_claim
from schema import validate_full


TOOL_HANDLERS = {
    "get_policy": handle_get_policy_tool_call,
    "get_claim": handle_get_claim_tool_call,
    "check_coverage": handle_check_coverage_tool_call,
    "estimate_repair_band": handle_estimate_repair_band_tool_call,
    "detect_fraud_signals": handle_detect_fraud_signals_tool_call,
}


def _load_system_prompt() -> str:
    with SYSTEM_PROMPT_PATH.open("r", encoding="utf-8") as f:
        return f.read()


def _load_regles_sinistres() -> str:
    with REGLES_SINISTRES_FILE.open("r", encoding="utf-8") as f:
        return f.read()


def _build_cached_system_blocks() -> list:
    """System prompt + texte integral de regles_sinistres.md, le point de
    cache etant place sur le DERNIER bloc (ce qui met en cache tout ce qui
    precede). Voir note "CACHE DE PROMPT" en tete de fichier.

    POURQUOI JOINDRE regles_sinistres.md ICI :
    budget_tokens.md demande explicitement de "Cacher les regles sinistres".
    Or le fichier n'etait jusqu'ici jamais envoye au modele (le system prompt
    se contentait de les reformuler), donc il n'y avait litteralement rien a
    mettre en cache. Deux consequences corrigees d'un coup :
      1. le modele dispose maintenant du texte de reference, pas d'une
         paraphrase (les documents du projet font foi) ;
      2. le prefixe cacheable passe nettement au-dessus du minimum requis
         pour que le cache s'active (les modeles Haiku exigent un prefixe
         d'au moins 2048 tokens ; en dessous, cache_control est ignore en
         silence et aucun cache n'est cree - ce qui explique les
         cache_creation_input_tokens / cache_read_input_tokens a 0 observes
         sur toutes les executions precedentes).
    """
    return [
        {
            "type": "text",
            "text": _load_system_prompt(),
        },
        {
            "type": "text",
            "text": (
                "# Texte integral de regles_sinistres.md (source de verite)\n\n"
                "Ce document fait foi. En cas d'ecart avec une reformulation "
                "du system prompt, c'est ce texte qui prime.\n\n"
                + _load_regles_sinistres()
            ),
            "cache_control": {"type": "ephemeral"},
        },
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


def _emit(on_event, event_type: str, **payload) -> None:
    """Transmet un evenement d'avancement a l'observateur, s'il y en a un.

    `on_event` est optionnel et vaut None partout ailleurs dans le projet
    (CLI, evals) : la boucle de triage fonctionne exactement comme avant sans
    observateur. Il sert a l'API HTTP (src/api.py), qui a besoin de voir la
    progression en direct pour la diffuser en SSE.

    Les exceptions de l'observateur sont avalees VOLONTAIREMENT : un client
    HTTP qui se deconnecte au milieu d'un triage ne doit pas faire echouer un
    appel de modele deja paye et deja en cours.
    """
    if on_event is None:
        return
    try:
        on_event({"type": event_type, **payload})
    except Exception:  # noqa: BLE001 - voir docstring
        pass


def _stream_final_message(client: anthropic.Anthropic, on_event=None, **kwargs):
    """Ouvre le stream, le consomme entierement, et renvoie le message final.

    A APPELER VIA _call_with_retry, jamais l'inverse : `client.messages.stream()`
    ne declenche AUCUNE requete HTTP, il ne fait que construire un context
    manager (la requete part dans `__enter__`). Passer `client.messages.stream`
    directement a _call_with_retry ne protegeait donc rien du tout : la
    fonction retournait le manager sans qu'aucune exception reseau ne puisse
    survenir dans la boucle de retry, et les erreurs 429 / 5xx du mode normal
    n'etaient jamais reessayees (SUJET_PROJET.md: "Gestion erreurs ... statut
    429 simule"). En encapsulant ici l'ouverture ET la consommation du stream,
    le retry couvre bien l'appel reseau complet.
    """
    with client.messages.stream(**kwargs) as stream:
        for event in stream:
            # On n'ecoute que les evenements bruts de l'API (content_block_delta)
            # et pas les evenements de commodite du SDK (type "text"), qui
            # portent la MEME donnee : ecouter les deux dupliquerait chaque
            # fragment. Les evenements bruts sont aussi le contrat le plus
            # stable d'une version du SDK a l'autre.
            if getattr(event, "type", None) != "content_block_delta":
                continue
            delta = getattr(event, "delta", None)
            if getattr(delta, "type", None) == "text_delta":
                _emit(on_event, "text_delta", text=delta.text)
        # Le SDK a accumule le message final pendant l'iteration ci-dessus.
        return stream.get_final_message()


def _execute_tool_use_block(block) -> dict:
    handler = TOOL_HANDLERS.get(block.name)
    if handler is None:
        return {"error": f"Tool inconnu: {block.name}"}
    return handler(block.input)


# =============================================================================
# Mode "normal" : boucle agentique synchrone, en streaming.
# =============================================================================

def triage_claim(
    claim_id: str,
    client: Optional[anthropic.Anthropic] = None,
    on_event=None,
) -> dict:
    """Triage d'un seul sinistre en mode normal (streaming, boucle d'outils
    synchrone). Retourne un dict avec le JSON de triage (si produit et
    valide), les erreurs de validation eventuelles, et l'historique des
    tool calls pour tracabilite (SUJET_PROJET.md: "traces par etape").

    `on_event` (optionnel) recoit la progression au fil de l'eau : voir _emit.
    La valeur de retour est identique avec ou sans observateur.
    """
    client = client or anthropic.Anthropic()
    _emit(on_event, "run_started", claim_id=claim_id, model=MODEL)

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
    usage_totals = cost.empty_usage_totals()  # accumule sur tous les tours (budget_tokens.md)

    # Construits UNE SEULE fois : leur contenu est identique a chaque tour, et
    # les reconstruire relisait deux fichiers du disque a chaque iteration.
    # C'est aussi ce qui doit rester strictement identique d'un appel a
    # l'autre pour que le cache de prompt puisse s'appliquer.
    system_blocks = _build_cached_system_blocks()
    cached_tools = _build_cached_tools()

    for turn_index in range(MAX_TOOL_TURNS):
        turn = turn_index + 1
        _emit(on_event, "turn_started", turn=turn)

        final_message = _call_with_retry(
            _stream_final_message,
            client,
            on_event=on_event,
            model=MODEL,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            system=system_blocks,
            tools=cached_tools,
            messages=messages,
        )

        turn_usage = cost.usage_to_dict(final_message.usage)
        usage_totals = cost.accumulate_usage(usage_totals, turn_usage)
        messages.append({"role": "assistant", "content": final_message.content})

        tool_use_blocks = [b for b in final_message.content if b.type == "tool_use"]

        if not tool_use_blocks:
            # Pas d'appel d'outil -> le modele a produit sa reponse finale.
            text_blocks = [b.text for b in final_message.content if b.type == "text"]
            final_text = "\n".join(text_blocks).strip()
            _emit(on_event, "turn_completed", turn=turn, usage=turn_usage)
            return _finalize_result(
                claim_id, final_text, claim_snapshot, tool_call_trace, usage_totals,
                on_event=on_event,
            )

        # Executer chaque tool_use et rattacher chaque tool_result au bon
        # tool_use_id (SUJET_PROJET.md: "tool_result correctement rattache
        # au tool_use").
        tool_results = []
        for block in tool_use_blocks:
            _emit(on_event, "tool_use", turn=turn, tool=block.name, input=block.input)

            result = _execute_tool_use_block(block)
            tool_call_trace.append({"tool": block.name, "input": block.input, "output": result})

            _emit(on_event, "tool_result", turn=turn, tool=block.name, output=result)

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
        _emit(on_event, "turn_completed", turn=turn, usage=turn_usage)

    result = {
        "claim_id": claim_id,
        "error": f"Nombre maximal de tours d'outils atteint ({MAX_TOOL_TURNS}) sans reponse finale.",
        "tool_call_trace": tool_call_trace,
        "usage": usage_totals,
    }
    _emit(on_event, "error", message=result["error"])
    return result


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _parse_final_json(text: str) -> Optional[dict]:
    """Extrait et parse le JSON de triage depuis la reponse finale du
    modele, meme entouree de texte explicatif et/ou de balises markdown
    (```json ... ```) : malgre la consigne du system prompt de ne
    produire QUE le JSON brut, le modele y ajoute parfois une analyse ou
    des balises markdown. Essaie, dans l'ordre : le texte tel quel, le
    dernier bloc ```json``` trouve, puis le dernier objet {...} du texte.
    Renvoie None si aucune des trois strategies ne produit de JSON valide."""
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fence_matches = _JSON_FENCE_RE.findall(text)
    if fence_matches:
        try:
            return json.loads(fence_matches[-1])
        except json.JSONDecodeError:
            pass

    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        try:
            return json.loads(text[first_brace : last_brace + 1])
        except json.JSONDecodeError:
            pass

    return None


def _finalize_result(
    claim_id, final_text, claim_snapshot, tool_call_trace, usage_totals, on_event=None
) -> dict:
    parsed = _parse_final_json(final_text)
    if parsed is None:
        result = {
            "claim_id": claim_id,
            "error": "La reponse finale du modele n'est pas un JSON valide.",
            "raw_output": final_text,
            "tool_call_trace": tool_call_trace,
            "usage": usage_totals,
        }
        _emit(on_event, "error", message=result["error"], raw_output=final_text)
        return result

    blessure = bool(claim_snapshot and claim_snapshot.get("blessure") == "oui")
    validation_errors = validate_full(parsed, blessure=blessure)

    result = {
        "claim_id": claim_id,
        "output": parsed,
        "validation_errors": validation_errors,
        "tool_call_trace": tool_call_trace,
        "usage": usage_totals,
    }
    _emit(
        on_event,
        "result",
        claim_id=claim_id,
        output=parsed,
        validation_errors=validation_errors,
        tool_call_trace=tool_call_trace,
        usage=usage_totals,
    )
    return result


# =============================================================================
# Pre-calcul deterministe du contexte d'un sinistre.
# =============================================================================

def build_context(claim_id: str, use_classifier: bool = True) -> dict:
    """Execute localement les 5 tools pour un sinistre, sans passer par le
    modele (ils sont deterministes). Renvoie soit le contexte complet, soit
    une erreur si le claim/policy est introuvable.

    N'est PAS utilise par la boucle de triage (le modele appelle les tools
    lui-meme, c'est tout l'interet du mode agentique). Cette fonction sert a
    evals/run_evals.py, qui a besoin des resultats de reference des tools
    pour grader certains checks, a l'API HTTP (fiche dossier), et a toute
    inspection hors ligne d'un dossier.

    use_classifier=False rend la fonction entierement gratuite : c'est alors
    la seule facon d'obtenir le dossier complet sans aucun appel de modele
    (voir guard.screen_claim). Le verdict de screening vaut alors None.
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

    # Les signaux de fraude sont calcules sur le claim BRUT : c'est du code
    # deterministe, insensible a une injection, et il doit voir le texte
    # d'origine pour que la detection par mots-cles fonctionne.
    fraud_signals = detect_fraud_signals(claim, policy)

    # Le modele, lui, ne recoit QUE la version filtree (src/guard.py).
    screened_claim = screen_claim(claim, use_classifier=use_classifier)

    return {
        "claim": screened_claim,
        "policy": policy,
        "coverage": coverage,
        "repair_band": repair_band,
        "fraud_signals": fraud_signals,
        # Texte brut du client, pour LECTURE HUMAINE cote API uniquement. Sortir
        # de build_context est sans risque : cette fonction n'alimente jamais le
        # prompt de triage (le modele appelle les tools lui-meme). A ne PAS
        # remettre dans `claim`, qui lui peut atteindre le modele via get_claim.
        "original_text": claim.get("description_client", ""),
    }


# Ancien nom, conserve pour evals/run_evals.py et les appelants existants.
_prefetch_context = build_context


# =============================================================================
# Point d'entree unique.
# =============================================================================

def triage(
    claim_id: str,
    client: Optional[anthropic.Anthropic] = None,
    on_event=None,
) -> dict:
    """Point d'entree pour un triage a l'unite : streaming, boucle d'outils
    synchrone. Alias de triage_claim, conserve comme nom d'API stable
    pour les appelants."""
    return triage_claim(claim_id, client=client, on_event=on_event)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python backend/src/agent.py <claim_id>")
        sys.exit(1)

    result = triage(sys.argv[1])
    print(json.dumps(result, ensure_ascii=False, indent=2))