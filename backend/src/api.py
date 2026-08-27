"""
src/api.py

Couche HTTP au-dessus du domaine existant. N'implemente AUCUNE regle metier :
elle expose ce que src/agent.py, src/tools.py et src/guard.py produisent deja.

Lancement (depuis la racine du depot) :
    uvicorn api:app --app-dir backend/src

NE PAS ajouter --reload. Le jeu de donnees depose vit dans la memoire du
processus (src/dataset.py) : le rechargement a chaud redemarre le processus a
chaque enregistrement d'un fichier Python, ce qui EFFACE les dossiers du
gestionnaire en pleine session et le renvoie sans prevenir a l'ecran de depot.
Pendant un developpement du backend, relancer la commande a la main est plus
sur que de perdre les fichiers de l'utilisateur a chaque sauvegarde.

Deux familles d'endpoints, volontairement separees :

    GRATUITS    lecture des CSV et deroulement deterministe des 5 tools.
                Aucun appel de modele, donc aucun cout et aucune latence.
                C'est la quasi-totalite de l'interface.

    PAYANTS     POST /api/claims/{id}/screen  (couche [2] du filtre)
                POST /api/triage/{id}         (boucle agentique complete)
                GET  /api/triage/{id}/stream  (idem, diffuse en SSE)

TROIS POINTS DE VIGILANCE, dans l'ordre d'importance :

1. LES COLONNES DE REFERENCE NE SORTENT JAMAIS.
   Un fichier de declarations peut contenir `priorite_attendue` et
   `triage_attendu` (c'est le cas des jeux d'essai), les reponses des evals. tools.get_claim les retire deja, et
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

import contextlib
import functools
import json
import os
import queue
import threading
from datetime import datetime, timezone
from typing import Optional

import anyio
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

import agent
import dataset
import guard
import urgence
from api_models import (
    ClaimDetail,
    ClaimSummary,
    DatasetState,
    Health,
    ModelOption,
    Policy,
    Rules,
    Screening,
    TriageResult,
)
from config import AVAILABLE_MODELS, DATA_DIR, MODEL, REGLES_SINISTRES_FILE
from tools import (
    ClaimNotFound,
    EncodageIllisible,
    InvalidDatasetFile,
    NoDatasetLoaded,
    PolicyNotFound,
    decode_csv,
    get_claim,
    get_policy,
    list_claim_ids,
    parse_claims_csv,
    parse_policies_csv,
)

@contextlib.asynccontextmanager
async def lifespan(_app: FastAPI):
    """Au demarrage : recharge le dernier jeu de donnees depose, s'il en reste
    un dans la base (src/dataset_db.py).

    Avant cette base, un redemarrage du serveur renvoyait l'utilisateur a
    l'ecran de depot en pleine session de travail. La restauration est
    silencieuse si rien n'est enregistre : l'ecran de depot reste le point de
    depart d'une premiere utilisation.
    """
    if dataset.restore_from_db():
        etat = dataset.summary()
        print(
            f"[dataset] jeu restaure : {etat['claims_count']} declarations, "
            f"{etat['policies_count']} contrats "
            f"({etat['claims_filename']}, depose le {etat['loaded_at']})"
        )
    yield


app = FastAPI(
    title="TSA - Triage Sinistres Auto",
    description=__doc__,
    version="1.0.0",
    lifespan=lifespan,
)

# Le frontend Next.js tourne sur un autre port. On preferre CORS a un proxy
# `rewrites` cote Next : le proxy de developpement de Next bufferise volontiers
# les reponses text/event-stream, ce qui ferait arriver le triage d'un seul
# bloc a la fin - exactement ce que cette interface cherche a montrer en direct.
#
# allow_methods DOIT LISTER TOUTES LES METHODES QUE LE NAVIGATEUR APPELLE.
# Une methode absente n'echoue pas cote serveur : le navigateur envoie d'abord
# un preflight OPTIONS, le middleware le refuse, et la requete ne part jamais.
# Cote interface, cela se voit comme un "TypeError: Failed to fetch" sans
# aucune trace applicative - le retrait du jeu de donnees (DELETE) a echoue
# ainsi, alors que le meme appel passait en curl, qui ignore CORS.
# A completer en meme temps que tout nouvel endpoint appele depuis le client.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET", "POST", "DELETE"],
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

_AUCUN_JEU_DE_DONNEES = (
    "Aucun fichier n'a ete depose. Deposez le fichier des declarations et "
    "celui des contrats pour commencer."
)


_JEU_NON_DEPOSE = (
    "Le jeu de donnees charge dans ce processus a ete lu sur le disque (jeux "
    "d'essai des evaluations) et ne sera pas servi. Deposez le fichier des "
    "declarations et celui des contrats."
)


def _exiger_jeu_de_donnees() -> None:
    """Refuse de servir des sinistres qui ne viennent pas de l'utilisateur.

    DEUX refus, et non un seul :

      - rien n'est charge : sans ce garde-fou, les lecteurs de tools.py
        leveraient NoDatasetLoaded au fond de la pile plutot que de renvoyer
        un 409 clair ;

      - quelque chose est charge, mais depuis le disque : c'est le cas d'un
        appel a tools.load_dataset_from_files() (suite d'evaluation, commande
        en terminal, tests) qui se produirait dans le processus du serveur.
        Servir ces lignes ferait croire au gestionnaire qu'il travaille sur
        ses dossiers alors qu'il regarderait les jeux d'essai de data/. Ce
        refus est la traduction en code de la regle du projet : l'application
        web ne traite QUE des fichiers deposes.
    """
    if not dataset.is_loaded():
        raise HTTPException(status_code=409, detail=_AUCUN_JEU_DE_DONNEES)
    if dataset.source() != dataset.SOURCE_DEPOT:
        raise HTTPException(status_code=409, detail=_JEU_NON_DEPOSE)


def _get_claim_or_404(claim_id: str) -> dict:
    try:
        return get_claim(claim_id)
    except ClaimNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except NoDatasetLoaded as e:
        # Filet : _exiger_jeu_de_donnees passe normalement avant.
        raise HTTPException(status_code=409, detail=_AUCUN_JEU_DE_DONNEES) from e


def _get_policy_or_404(policy_id: str) -> dict:
    try:
        return get_policy(policy_id)
    except PolicyNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except NoDatasetLoaded as e:
        raise HTTPException(status_code=409, detail=_AUCUN_JEU_DE_DONNEES) from e


def _screening_from(screened_claim: dict, original_text: str = "") -> dict:
    """Extrait le bloc de trace du filtre et y joint le texte reellement
    transmis au modele.

    `original_text` (le texte brut du client, pour LECTURE HUMAINE) est fourni
    SEPAREMENT par l'appelant, jamais lu dans `screened_claim`. C'est
    deliberement le cas : `screened_claim["_screening"]` est le meme dict que le
    tool get_claim renvoie au modele (voir guard.screen_claim), donc y ranger le
    texte brut le ferait fuiter dans le prompt. L'appelant le prend sur le claim
    BRUT, hors de portee du modele."""
    trace = screened_claim.get("_screening", {})
    text_for_model = screened_claim.get("description_client", "")
    return {
        "verdict": trace.get("verdict"),
        "markers_found": trace.get("markers_found", []),
        "classifier_available": trace.get("classifier_available", True),
        "classifier_called": trace.get("classifier_called", False),
        "text_for_model": text_for_model,
        "original_text": original_text,
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


# =============================================================================
# Jeu de donnees depose par l'utilisateur
# =============================================================================

def _claims_sans_contrat(claims: dict, policies: dict) -> list:
    return sorted(
        claim_id
        for claim_id, claim in claims.items()
        if claim.get("policy_id") not in policies
    )


def _etat_du_jeu_de_donnees() -> dict:
    # Un jeu de donnees lu sur le disque n'existe pas pour l'application web
    # (voir _exiger_jeu_de_donnees) : l'interface doit voir un etat vide et
    # afficher son ecran de depot, plutot qu'une file qu'elle ne pourra pas
    # charger ensuite.
    if dataset.source() != dataset.SOURCE_DEPOT:
        return {"loaded": False}

    etat = dataset.summary()
    if etat.get("loaded"):
        etat["claims_sans_contrat"] = _claims_sans_contrat(
            dataset.get_claims() or {}, dataset.get_policies() or {}
        )
    return etat


@app.get("/api/dataset", response_model=DatasetState, tags=["donnees"])
def dataset_state() -> dict:
    """Y a-t-il des donnees dans l'application ? L'interface s'en sert pour
    choisir entre l'ecran de depot et la file d'attente."""
    return _etat_du_jeu_de_donnees()


@app.post("/api/dataset", response_model=DatasetState, tags=["donnees"])
async def upload_dataset(
    claims_file: UploadFile = File(..., description="CSV des declarations."),
    policies_file: UploadFile = File(..., description="CSV des contrats."),
) -> dict:
    """Depose les deux fichiers d'entree.

    Les deux vont ensemble et sont remplaces d'un bloc : une declaration sans
    son contrat n'est pas exploitable, et accepter un fichier a la fois
    laisserait l'application dans un etat incoherent.

    Le jeu de donnees vit en memoire pour la lecture, et est enregistre dans
    backend/dataset.sqlite3 pour survivre a un redemarrage (voir
    src/dataset.py et src/dataset_db.py). DELETE /api/dataset l'efface des
    deux.
    """
    def _decode(contenu: bytes, quel_fichier: str) -> str:
        # tools.decode_csv est la source unique : la lecture disque (evals,
        # terminal, tests) et le depot HTTP doivent accepter exactement les
        # memes fichiers.
        try:
            return decode_csv(contenu)
        except EncodageIllisible as e:
            raise HTTPException(
                status_code=422,
                detail=f"{quel_fichier} : {e} Enregistrez le fichier en UTF-8.",
            ) from e

    texte_claims = _decode(await claims_file.read(), "Fichier des declarations")
    texte_policies = _decode(await policies_file.read(), "Fichier des contrats")

    # AUCUN FILTRE SUR LE CONTENU, AUCUN SUR LE NOM DU FICHIER.
    #
    # Le seul refus possible ici est technique : un CSV illisible ou auquel il
    # manque des colonnes (parse_*_csv). Ce que contiennent les lignes ne
    # regarde pas l'API.
    #
    # Une version precedente inspectait le fichier pour reconnaitre le jeu
    # d'essai de data/ et refusait le depot. C'etait une erreur : la regle du
    # projet veut que le systeme n'aille JAMAIS chercher les fichiers de data/
    # tout seul, pas qu'il inspecte ceux que l'utilisateur lui donne. Ces deux
    # choses sont independantes, et la seconde revenait a decider a sa place
    # ce qu'il a le droit de charger.
    #
    # Ce qui garantit que data/ ne s'affiche jamais tout seul, c'est
    # _exiger_jeu_de_donnees (source="depot" obligatoire) et l'absence totale
    # de repli dans tools._load_claims - pas une inspection du contenu.
    try:
        declarations = parse_claims_csv(texte_claims)
        contrats = parse_policies_csv(texte_policies)
    except InvalidDatasetFile as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    # Le screening est memorise par claim_id : sans ce vidage, un nouveau
    # fichier reutiliserait les verdicts calcules sur l'ancien.
    guard.reset_screening_cache()
    dataset.set_active(
        declarations.lignes,
        contrats.lignes,
        source=dataset.SOURCE_DEPOT,
        claims_filename=claims_file.filename or "",
        policies_filename=policies_file.filename or "",
        rejets=declarations.rejets + contrats.rejets,
    )
    return _etat_du_jeu_de_donnees()


@app.delete("/api/dataset", response_model=DatasetState, tags=["donnees"])
def clear_dataset() -> dict:
    guard.reset_screening_cache()
    dataset.clear()
    return _etat_du_jeu_de_donnees()


# =============================================================================
# Endpoints gratuits (necessitent un jeu de donnees)
# =============================================================================

@app.get("/api/claims", response_model=list[ClaimSummary], tags=["referentiel"])
def claims() -> list[dict]:
    """File d'attente. Joint quelques champs de la police pour que la liste
    soit lisible sans ouvrir chaque dossier.

    Les marqueurs d'injection sont calcules par guard.find_injection_markers,
    qui est une fonction pure : la file signale les dossiers a texte hostile
    sans depenser le moindre appel de modele.

    Meme logique pour `urgence_estimee` : urgence.estimate_urgency est
    deterministe et ne coute rien, ce qui permet d'ordonner la file avant
    toute analyse. Ce n'est PAS la `priorite` que rend l'agent, et les deux
    peuvent diverger sur un meme dossier (voir src/urgence.py).
    """
    _exiger_jeu_de_donnees()

    summaries = []
    for claim_id in list_claim_ids():
        claim = _get_claim_or_404(claim_id)
        try:
            policy = get_policy(claim["policy_id"])
        except PolicyNotFound:
            # Un sinistre dont la police a disparu du CSV reste affichable :
            # la file ne doit pas tomber entierement pour une ligne isolee.
            policy = {}

        # Calcules une seule fois : l'estimation d'urgence les relit.
        markers = guard.find_injection_markers(claim.get("description_client", ""))
        estimation = urgence.estimate_urgency(claim, markers)

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
                "injection_markers_found": markers,
                "urgence_estimee": estimation["niveau"],
                "urgence_motifs": estimation["motifs"],
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
    _exiger_jeu_de_donnees()
    _get_claim_or_404(claim_id)  # 404 explicite avant tout le reste

    context = agent.build_context(claim_id, use_classifier=False)
    if "error" in context:
        # Le sinistre existe (verifie ci-dessus) : l'erreur restante ne peut
        # venir que d'une police referencee mais absente du fichier des contrats.
        # C'est une incoherence de donnees, pas une URL erronee.
        raise HTTPException(status_code=422, detail=context["error"])

    screened_claim = context["claim"]
    return {
        "claim": _claim_without_trace(screened_claim),
        "policy": context["policy"],
        "coverage": context["coverage"],
        "repair_band": context["repair_band"],
        "fraud_signals": context["fraud_signals"],
        # original_text vient de build_context (claim brut), jamais du claim
        # filtre : il est destine au gestionnaire humain, pas au modele.
        "screening": _screening_from(screened_claim, original_text=context["original_text"]),
    }


@app.get("/api/policies/{policy_id}", response_model=Policy, tags=["referentiel"])
def policy_detail(policy_id: str) -> dict:
    _exiger_jeu_de_donnees()
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
    _exiger_jeu_de_donnees()
    claim = _get_claim_or_404(claim_id)

    _acquire_run_lock()
    try:
        screened = await run_in_threadpool(guard.screen_claim, claim)
    finally:
        _RUN_LOCK.release()

    # original_text : le texte brut du client (claim), pour lecture humaine.
    # Pris sur le claim BRUT, jamais sur `screened`, qui ne le contient plus.
    return _screening_from(screened, original_text=claim.get("description_client", ""))


def _valider_modele(model: Optional[str]) -> str:
    """Ramene le parametre `model` recu a un identifiant AUTORISE.

    Absent -> le defaut (config.MODEL). Present mais inconnu -> 400 : on refuse
    net plutot que de retomber en silence sur le defaut, pour qu'une faute de
    frappe ou un modele retire se voie tout de suite au lieu de facturer un
    triage sur un autre modele que celui demande.
    """
    if not model:
        return MODEL
    if model not in AVAILABLE_MODELS:
        raise HTTPException(
            status_code=400,
            detail=f"Modele inconnu: {model!r}. Choix possibles: {sorted(AVAILABLE_MODELS)}.",
        )
    return model


@app.get("/api/models", response_model=list[ModelOption], tags=["modele"])
def list_models() -> list[dict]:
    """Modeles proposes pour l'analyse. Le frontend en fait la liste de choix ;
    l'ordre est celui de config.AVAILABLE_MODELS, le premier etant le defaut."""
    return [
        {"id": mid, "label": label, "default": mid == MODEL}
        for mid, label in AVAILABLE_MODELS.items()
    ]


@app.post("/api/triage/{claim_id}", response_model=TriageResult, tags=["modele"])
async def triage(claim_id: str, model: Optional[str] = Query(None)) -> dict:
    """Boucle agentique complete, en bloquant jusqu'au resultat.

    Compter plusieurs dizaines de secondes : un aller-retour de modele par
    tour d'outils (jusqu'a MAX_TOOL_TURNS), plus l'appel du filtre. Pour
    suivre la progression, utiliser plutot l'endpoint SSE ci-dessous.

    `model` (optionnel) : l'un des identifiants de config.AVAILABLE_MODELS ;
    absent, le defaut s'applique.
    """
    _exiger_jeu_de_donnees()
    _get_claim_or_404(claim_id)
    modele = _valider_modele(model)

    _acquire_run_lock()
    try:
        return await run_in_threadpool(
            functools.partial(agent.triage_claim, claim_id, model=modele)
        )
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
    model: Optional[str] = Query(
        None,
        description="Identifiant de modele (config.AVAILABLE_MODELS). Absent : le defaut.",
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

    _exiger_jeu_de_donnees()
    _get_claim_or_404(claim_id)
    modele = _valider_modele(model)  # avant le verrou : un 400 ne doit pas le prendre
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
            agent.triage_claim(claim_id, on_event=events.put, model=modele)
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
