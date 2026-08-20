"""
src/api.py

Couche HTTP au-dessus du domaine existant. N'implemente AUCUNE regle metier :
elle expose ce que src/agent.py, src/tools.py et src/guard.py produisent deja.

Lancement (depuis la racine du depot) :
    uvicorn api:app --app-dir backend/src --reload

Deux familles d'endpoints, volontairement separees :

    GRATUITS    lecture des CSV et deroulement deterministe des 5 tools.
                Aucun appel de modele, donc aucun cout et aucune latence.
                C'est la quasi-totalite de l'interface.

    PAYANTS     POST /api/claims/{id}/screen  (couche [2] du filtre)
                POST /api/triage/{id}         (boucle agentique complete)
                GET  /api/triage/{id}/stream  (idem, diffuse en SSE)

TROIS POINTS DE VIGILANCE, dans l'ordre d'importance :

1. LES COLONNES DE REFERENCE NE SORTENT JAMAIS.
   claims_auto.csv contient `priorite_attendue` et `triage_attendu`, qui sont
   les reponses attendues des evals. tools.get_claim les retire deja, et
   tools.get_claim_eval_labels (qui, lui, les lit) n'est deliberement importe
   NULLE PART dans ce module. Les exposer rendrait toute mesure de qualite
   sans valeur. Un test dedie verifie cette absence sur les 8 sinistres.

2. LE TRAVAIL PAYANT EST SERIALISE.
   guard._guard_usage_total et guard._screening_cache sont des globales de
   module modifiees sans verrou, et agent.triage_claim est du code bloquant.
   Deux triages simultanes se marcheraient dessus. Un verrou unique protege
   donc tout appel de modele ; une seconde demande recoit 409 plutot que
   d'etre mise en file (application mono-utilisateur : refuser est plus
   honnete que de faire patienter sans le dire).

3. UN GET NE DOIT PAS DECLENCHER UN TRIAGE PAR ACCIDENT.
   L'endpoint SSE est un GET (contrainte d'EventSource) mais lance une boucle
   agentique de plusieurs dizaines de secondes. Le prefetch de liens de
   Next.js, le preconnect du navigateur ou un crawler pourraient l'appeler
   sans intention. D'ou le parametre obligatoire `confirm=1`.
"""

import functools
import json
import os
import queue
import threading
from datetime import datetime, timezone

import anyio
from fastapi import FastAPI, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

import agent
import guard
from api_models import (
    ClaimDetail,
    ClaimSummary,
    Health,
    Policy,
    Rules,
    Screening,
    TriageResult,
)
from config import DATA_DIR, MODEL, REGLES_SINISTRES_FILE
from tools import (
    ClaimNotFound,
    PolicyNotFound,
    get_claim,
    get_policy,
    list_claim_ids,
)

app = FastAPI(
    title="Neopolis - triage de sinistres auto",
    description=__doc__,
    version="1.0.0",
)

# Le frontend Next.js tourne sur un autre port. On preferre CORS a un proxy
# `rewrites` cote Next : le proxy de developpement de Next bufferise volontiers
# les reponses text/event-stream, ce qui ferait arriver le triage d'un seul
# bloc a la fin - exactement ce que cette interface cherche a montrer en direct.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# =============================================================================
# Serialisation du travail payant (point de vigilance 2)
# =============================================================================

_RUN_LOCK = threading.Lock()

_BUSY_DETAIL = (
    "Un triage est deja en cours. Cette application traite un sinistre a la "
    "fois : la boucle agentique s'appuie sur des etats globaux (memo de "
    "screening, compteur d'usage) qui ne sont pas concurrents."
)


def _acquire_run_lock() -> None:
    """Prend le verrou ou refuse la demande. A appeler AVANT de lancer le
    moindre appel de modele."""
    if not _RUN_LOCK.acquire(blocking=False):
        raise HTTPException(status_code=409, detail=_BUSY_DETAIL)


# =============================================================================
# Helpers
# =============================================================================

def _get_claim_or_404(claim_id: str) -> dict:
    try:
        return get_claim(claim_id)
    except ClaimNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


def _get_policy_or_404(policy_id: str) -> dict:
    try:
        return get_policy(policy_id)
    except PolicyNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


def _screening_from(screened_claim: dict) -> dict:
    """Extrait le bloc de trace du filtre et y joint le texte reellement
    transmis au modele. `original_text` n'est jamais repris (api_models.py)."""
    trace = screened_claim.get("_screening", {})
    text_for_model = screened_claim.get("description_client", "")
    return {
        "verdict": trace.get("verdict"),
        "markers_found": trace.get("markers_found", []),
        "classifier_available": trace.get("classifier_available", True),
        "classifier_called": trace.get("classifier_called", False),
        "text_for_model": text_for_model,
        "redacted": text_for_model == guard.REDACTED_PLACEHOLDER,
    }


def _claim_without_trace(screened_claim: dict) -> dict:
    """`_screening` est remonte a la racine de la reponse plutot que laisse
    dans le claim : c'est une trace du pipeline, pas un champ du sinistre."""
    return {k: v for k, v in screened_claim.items() if k != "_screening"}


# =============================================================================
# Endpoints gratuits
# =============================================================================

@app.get("/api/health", response_model=Health, tags=["referentiel"])
def health() -> dict:
    return {
        "status": "ok",
        "model": MODEL,
        "api_key_configured": bool(os.environ.get("ANTHROPIC_API_KEY")),
    }


@app.get("/api/claims", response_model=list[ClaimSummary], tags=["referentiel"])
def claims() -> list[dict]:
    """File d'attente. Joint quelques champs de la police pour que la liste
    soit lisible sans ouvrir chaque dossier.

    Les marqueurs d'injection sont calcules par guard.find_injection_markers,
    qui est une fonction pure : la file signale les dossiers a texte hostile
    sans depenser le moindre appel de modele.
    """
    summaries = []
    for claim_id in list_claim_ids():
        claim = _get_claim_or_404(claim_id)
        try:
            policy = get_policy(claim["policy_id"])
        except PolicyNotFound:
            # Un sinistre dont la police a disparu du CSV reste affichable :
            # la file ne doit pas tomber entierement pour une ligne isolee.
            policy = {}

        summaries.append(
            {
                "claim_id": claim["claim_id"],
                "policy_id": claim["policy_id"],
                "date_sinistre": claim["date_sinistre"],
                "type_sinistre": claim["type_sinistre"],
                "blessure": claim["blessure"],
                "devis_tnd": claim["devis_tnd"],
                "tiers_identifie": claim["tiers_identifie"],
                "assure": policy.get("assure"),
                "vehicule": policy.get("vehicule"),
                "formule": policy.get("formule"),
                "injection_markers_found": guard.find_injection_markers(
                    claim.get("description_client", "")
                ),
            }
        )
    return summaries


@app.get("/api/claims/{claim_id}", response_model=ClaimDetail, tags=["referentiel"])
def claim_detail(claim_id: str) -> dict:
    """Fiche dossier : les 5 tools deroules de facon deterministe.

    use_classifier=False -> aucun appel de modele. Le verdict de screening
    vaut alors None, ce que l'interface doit afficher comme une absence
    d'analyse et non comme un feu vert (voir guard.classify_client_text).
    """
    _get_claim_or_404(claim_id)  # 404 explicite avant tout le reste

    context = agent.build_context(claim_id, use_classifier=False)
    if "error" in context:
        # Le sinistre existe (verifie ci-dessus) : l'erreur restante ne peut
        # venir que d'une police referencee mais absente de policies_auto.csv.
        # C'est une incoherence de donnees, pas une URL erronee.
        raise HTTPException(status_code=422, detail=context["error"])

    screened_claim = context["claim"]
    return {
        "claim": _claim_without_trace(screened_claim),
        "policy": context["policy"],
        "coverage": context["coverage"],
        "repair_band": context["repair_band"],
        "fraud_signals": context["fraud_signals"],
        "screening": _screening_from(screened_claim),
    }


@app.get("/api/policies/{policy_id}", response_model=Policy, tags=["referentiel"])
def policy_detail(policy_id: str) -> dict:
    return _get_policy_or_404(policy_id)


@app.get("/api/rules", response_model=Rules, tags=["referentiel"])
def rules() -> dict:
    """Sert les documents de reference tels quels. Ils font foi : l'interface
    doit pouvoir les montrer sans les reformuler."""
    wanted = [
        ("regles_sinistres.md", REGLES_SINISTRES_FILE),
        ("contrat_sortie.md", DATA_DIR / "contrat_sortie.md"),
    ]
    documents = []
    for name, path in wanted:
        try:
            documents.append({"name": name, "content": path.read_text(encoding="utf-8")})
        except FileNotFoundError as e:
            raise HTTPException(status_code=503, detail=f"Document introuvable: {name}") from e
    return {"documents": documents}


# =============================================================================
# Endpoints payants
# =============================================================================

@app.post("/api/claims/{claim_id}/screen", response_model=Screening, tags=["modele"])
async def screen(claim_id: str) -> dict:
    """Execute les 3 couches du filtre anti-injection sur un seul sinistre.

    Passe par guard.screen_claim (et non directement par classify_client_text)
    pour que le memo par claim_id soit renseigne : un triage lance ensuite sur
    le meme sinistre reutilisera ce verdict au lieu de repayer la couche [2].
    """
    claim = _get_claim_or_404(claim_id)

    _acquire_run_lock()
    try:
        screened = await run_in_threadpool(guard.screen_claim, claim)
    finally:
        _RUN_LOCK.release()

    return _screening_from(screened)


@app.post("/api/triage/{claim_id}", response_model=TriageResult, tags=["modele"])
async def triage(claim_id: str) -> dict:
    """Boucle agentique complete, en bloquant jusqu'au resultat.

    Compter plusieurs dizaines de secondes : un aller-retour de modele par
    tour d'outils (jusqu'a MAX_TOOL_TURNS), plus l'appel du filtre. Pour
    suivre la progression, utiliser plutot l'endpoint SSE ci-dessous.
    """
    _get_claim_or_404(claim_id)

    _acquire_run_lock()
    try:
        return await run_in_threadpool(agent.triage_claim, claim_id)
    finally:
        _RUN_LOCK.release()


# =============================================================================
# SSE
# =============================================================================

_HEARTBEAT_SECONDS = 15
_QUEUE_SENTINEL = object()

# L'agent emet un evenement de type "error" ; on le diffuse sous le nom
# "run_error".
#
# POURQUOI CE RENOMMAGE : cote navigateur, EventSource utilise deja "error"
# pour ses propres pannes de transport (connexion coupee, serveur injoignable).
# Un `addEventListener("error", ...)` recevrait donc DEUX choses de nature
# differente - un echec de triage et une coupure reseau - et le code client
# devrait les distinguer en inspectant la presence d'un champ `data`. Nommer
# l'evenement applicatif autrement supprime l'ambiguite a la source.
_EVENT_NAME_OVERRIDES = {"error": "run_error"}


def _sse(event: str, data: dict) -> str:
    """Une trame SSE. json.dumps echappe les retours a la ligne, ce qui est
    indispensable ici : un `\\n` brut dans `data:` couperait la trame en deux."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.get("/api/triage/{claim_id}/stream", tags=["modele"])
async def triage_stream(
    claim_id: str,
    confirm: int = Query(
        0,
        description="Doit valoir 1. Garde-fou contre un declenchement accidentel "
        "de ce GET (prefetch de liens, preconnect, crawler).",
    ),
) -> StreamingResponse:
    """Meme triage que POST /api/triage/{id}, diffuse au fil de l'eau.

    Noms d'evenements diffuses :
        stream_open, run_started, turn_started, text_delta, tool_use,
        tool_result, turn_completed, result, run_error, done

    `stream_open` et `done` encadrent le flux : ce sont des marqueurs de
    transport, le domaine n'a pas a connaitre l'existence de SSE.
    `run_error` correspond au type "error" de l'agent (voir
    _EVENT_NAME_OVERRIDES).

    `text_delta` transporte le message final du modele tel qu'il s'ecrit,
    c'est-a-dire le JSON de triage caractere par caractere. Aucun parsing
    incremental n'est tente : le resultat structure arrive dans `result`.
    """
    if confirm != 1:
        raise HTTPException(
            status_code=400,
            detail="Parametre `confirm=1` requis : ce GET declenche une boucle "
            "agentique complete et ne doit pas partir sur un prefetch.",
        )

    _get_claim_or_404(claim_id)
    _acquire_run_lock()

    events: queue.Queue = queue.Queue()

    def worker() -> None:
        """Le triage tourne dans son propre thread ; la boucle d'evenements
        reste libre de pousser les trames au fur et a mesure.

        C'est CE thread qui libere le verrou, et non le generateur : si le
        client se deconnecte, le generateur est ferme immediatement alors que
        l'appel de modele, lui, continue. Liberer cote generateur laisserait
        donc une seconde demande demarrer par-dessus un triage encore en cours.
        """
        try:
            agent.triage_claim(claim_id, on_event=events.put)
        except Exception as e:  # noqa: BLE001 - remonte au client puis termine proprement
            events.put({"type": "error", "message": f"{type(e).__name__}: {e}"})
        finally:
            events.put(_QUEUE_SENTINEL)
            _RUN_LOCK.release()

    # Demarre ici, et non dans le generateur : un generateur jamais consomme
    # ne s'executerait pas, et le verrou pris juste au-dessus fuirait.
    threading.Thread(target=worker, name=f"triage-{claim_id}", daemon=True).start()

    async def frames():
        yield _sse(
            "stream_open",
            {"claim_id": claim_id, "started_at": datetime.now(timezone.utc).isoformat()},
        )
        while True:
            try:
                event = await anyio.to_thread.run_sync(
                    functools.partial(events.get, timeout=_HEARTBEAT_SECONDS)
                )
            except queue.Empty:
                # Un tour d'outils peut etre long : ce commentaire SSE evite
                # qu'un intermediaire ne juge la connexion morte.
                yield ": ping\n\n"
                continue

            if event is _QUEUE_SENTINEL:
                break

            payload = {k: v for k, v in event.items() if k != "type"}
            name = _EVENT_NAME_OVERRIDES.get(event["type"], event["type"])
            yield _sse(name, payload)

        yield _sse("done", {})

    return StreamingResponse(
        frames(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # desactive le buffering d'un proxy eventuel
        },
    )
