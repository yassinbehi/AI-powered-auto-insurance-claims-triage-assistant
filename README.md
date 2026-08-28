# TSA — Assistant de triage des sinistres auto

Trie les déclarations de sinistre automobile : détermine la couverture, repère
les dossiers incomplets ou suspects, recommande la prochaine action et prépare
une réponse client. **L'assistant ne valide jamais un paiement, ne rejette
jamais définitivement une demande, ne clôture jamais un dossier** — il
recommande, un humain décide.

Sujet et spécifications : [`data/SUJET_PROJET.md`](data/SUJET_PROJET.md),
[`data/regles_sinistres.md`](data/regles_sinistres.md),
[`data/contrat_sortie.md`](data/contrat_sortie.md),
[`data/budget_tokens.md`](data/budget_tokens.md).

---

## Ce qu'il faut savoir avant de démarrer

> **`data/claims_auto.csv` n'est pas lisible en l'état.** Chaque ligne y est
> enveloppée dans une paire de guillemets supplémentaire, et le fichier est
> encodé en cp1252 au lieu d'UTF-8. Le chargeur disque renvoie donc **zéro
> déclaration, sans lever d'erreur**. C'est la cause des 5 tests en échec et
> des 67 erreurs de la suite, et cela empêche la suite d'évaluation de
> tourner. `data/policies_auto.csv` est intact.
>
> Tant que ce fichier n'est pas réparé, utilisez vos propres fichiers via
> l'écran de dépôt de l'interface — c'est de toute façon le mode de
> fonctionnement normal de l'application (voir « D'où viennent les données »).

---

## Prérequis

- Python 3.10+
- Node.js 20+
- Une clé API Anthropic

## Installation

```bash
# Backend
python -m venv .venv
.venv/Scripts/pip install -r backend/requirements.txt      # Windows
# .venv/bin/pip install -r backend/requirements.txt        # macOS / Linux

# Frontend
cd frontend && npm install
```

Créez `backend/.env` :

```
ANTHROPIC_API_KEY=sk-ant-...
```

Ce fichier est ignoré par git et ne doit jamais être commité.

Le frontend lit `frontend/.env.local`, déjà présent dans le dépôt :

```
API_BASE_URL=http://127.0.0.1:8000              # utilisé par le rendu serveur Next
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000  # utilisé par le navigateur (SSE, POST)
```

Les deux pointent vers la même API et diffèrent parce que la première est
résolue depuis le serveur Next, la seconde depuis la machine du visiteur.

## Lancement

Deux processus, dans deux terminaux :

```bash
# 1. API  (depuis la racine du dépôt)
.venv/Scripts/python -m uvicorn api:app --app-dir backend/src --port 8000

# 2. Interface
cd frontend && npm run dev
```

Puis ouvrez **http://localhost:3000**. Documentation interactive de l'API :
http://127.0.0.1:8000/docs

> **N'ajoutez pas `--reload` à uvicorn.** Le rechargement à chaud redémarre le
> processus à chaque sauvegarde d'un fichier Python. Après une modification du
> backend, relancez la commande à la main.

## Utilisation en terminal

Le triage fonctionne aussi sans interface. La sortie standard reste du JSON
pur, le rapport de coût part sur la sortie d'erreur :

```bash
.venv/Scripts/python backend/src/main.py CLM-001 | jq .
```

## Tests

```bash
.venv/Scripts/python -m pytest backend/tests -q
```

318 tests. **246 passent** ; les 5 échecs et 67 erreurs restants viennent tous
du `claims_auto.csv` illisible signalé plus haut, pas du code applicatif.

| Fichier | Tests | Couvre |
| --- | ---: | --- |
| `test_api.py` | 67 | endpoints, verrou de triage, flux SSE, garde-fous |
| `test_dataset_db.py` | 37 | persistance des jeux, migrations, changement de jeu |
| `test_evals.py` | 36 | harnais d'évaluation et ses heuristiques |
| `test_tools.py` | 31 | les 5 tools déterministes |
| `test_guard.py` | 31 | les 3 couches du filtre anti-injection |
| `test_schema.py` | 28 | contrat de sortie et règles métier |
| `test_analyses_db.py` | 26 | historique des analyses |
| `test_urgence.py` | 20 | urgence estimée de la file |
| `test_agent_stream.py` | 18 | boucle d'outils, streaming, coût par exécution |
| `test_cost.py` | 17 | tarification par modèle, budget |
| `test_main.py` | 7 | entrée en ligne de commande |

Aucun test n'appelle l'API Anthropic : un faux client SDK rejoue les tours.
La suite est donc gratuite et fonctionne hors ligne.

## Évaluations

```bash
.venv/Scripts/python backend/evals/run_evals.py > resultats.json
```

20 cas dans `data/cases_evaluation.jsonl`, notés par du code (aucun juge LLM).
**Coût réel : environ 0,35 USD par passage complet** — voir
[`RAPPORT_COUT_SECURITE.md`](RAPPORT_COUT_SECURITE.md).

Nécessite un `data/claims_auto.csv` lisible : voir l'avertissement en tête.

---

## Architecture

```
backend/src/
  api.py           couche HTTP (FastAPI). Aucune règle métier.
  agent.py         boucle agentique : streaming, tours d'outils, coût
  guard.py         filtre anti-injection en 3 couches
  tools.py         les 5 tools déterministes + lecture des CSV
  schema.py        validation du contrat de sortie + règles métier
  urgence.py       urgence estimée de la file (pur, sans modèle)
  cost.py          tarification et budget (fonctions pures)
  dataset.py       jeu de données actif, en mémoire
  dataset_db.py    persistance SQLite des jeux déposés
  analyses_db.py   historique des analyses
  config.py        seuils, tarifs, modèles, chemins
  main.py          entrée en ligne de commande

frontend/src/
  app/             routes : file d'attente, dossier, triage, analyses
  components/      interface (claims, dataset, analyses, result, ui)
  lib/             types, appels API, filtres et tri (modules purs)
  hooks/           flux SSE du triage
```

### Les couches, du moins au plus privilégié

```
description_client (texte client, NON FIABLE)
        │
        ├─ [1] marqueurs déterministes        gratuit, toujours exécuté
        ├─ [2] classifieur LLM ISOLÉ          aucun tool, aucune règle
        └─ [3] liste blanche de verdicts      hors enum → SUSPECT, jamais SAFE
        │
        ▼
MODÈLE DE TRIAGE (détient les 5 tools et décide)
        │
        ▼
schema.validate_full  →  contrat de sortie + règles métier
```

Le modèle qui lit du texte potentiellement hostile n'est jamais celui qui
détient les outils. Détail complet dans
[`RAPPORT_COUT_SECURITE.md`](RAPPORT_COUT_SECURITE.md).

### D'où viennent les données

**Les deux fichiers d'entrée sont déposés par l'utilisateur dans
l'interface.** Les fichiers de `data/` ne servent jamais de repli : ce sont
les jeux d'essai de la suite d'évaluation. Les confondre ferait croire à un
gestionnaire qu'il travaille sur ses dossiers alors qu'il regarde des données
de test.

Les jeux déposés sont **nommés**, conservés dans `backend/dataset.sqlite3`, et
survivent à un redémarrage. On passe de l'un à l'autre sans redéposer de
fichiers.

### API

| Méthode | Chemin | Coût |
| --- | --- | --- |
| GET | `/api/health` | gratuit |
| GET · POST · DELETE | `/api/dataset` | gratuit |
| GET | `/api/datasets` | gratuit |
| POST | `/api/datasets/{id}/activer` | gratuit |
| DELETE | `/api/datasets/{id}` | gratuit |
| GET | `/api/claims` · `/api/claims/{id}` | gratuit |
| GET | `/api/policies/{id}` · `/api/rules` | gratuit |
| GET | `/api/models` | gratuit |
| GET · DELETE | `/api/analyses` · `/api/analyses/{id}` | gratuit |
| POST | `/api/claims/{id}/screen` | **payant** — couche [2] du filtre |
| POST | `/api/triage/{id}` | **payant** — boucle agentique complète |
| GET | `/api/triage/{id}/stream` | **payant** — idem, diffusé en SSE |

La quasi-totalité de l'interface tient sur les endpoints gratuits : lecture des
CSV et déroulement déterministe des 5 tools, sans aucun appel de modèle.

Trois garde-fous sur les endpoints payants :

- **`confirm=1` obligatoire** sur le flux SSE. C'est un GET, donc à portée d'un
  prefetch de lien ou d'un crawler, alors qu'il déclenche une boucle agentique
  de plusieurs dizaines de secondes.
- **Verrou unique** : deux triages simultanés se marcheraient dessus (états
  globaux). Une seconde demande reçoit 409 plutôt que d'attendre sans le dire.
- **Modèle validé** contre `config.AVAILABLE_MODELS` : un identifiant inconnu
  est refusé (400) au lieu de retomber en silence sur le défaut.

---

## Décisions de conception non évidentes

Chacune est argumentée en tête du fichier concerné :

- **`temperature` passe par `extra_body`** — le SDK `anthropic` 1.x a retiré ce
  paramètre de la signature, où il lève un `TypeError`. L'API l'accepte
  toujours pour les modèles du projet, et le triage repose sur
  `temperature=0` pour rester déterministe. (`config.py`, `agent.py`,
  `guard.py`)
- **Le mode batch a été retiré** alors que `budget_tokens.md` le suggère : il
  n'exerçait pas la boucle agentique, donc un score mesuré en batch ne disait
  rien de l'agent. (`agent.py`)
- **Les colonnes `priorite_attendue` / `triage_attendu` ne sortent jamais** de
  `tools.get_claim` : ce sont les réponses attendues des évaluations, et les
  exposer rendrait toute mesure de qualité sans valeur. (`tools.py`, `api.py`)
- **L'historique conserve les échecs**, avec leur coût : une analyse
  interrompue a été facturée comme une autre. (`analyses_db.py`)
- **Le tri et les filtres vivent dans l'URL** — un écran filtré se copie-colle,
  et la page reste rendue côté serveur. (`claims-filter.ts`,
  `analyses-filter.ts`)

## Limites connues

- **Mono-utilisateur par construction** : états globaux de module, verrou de
  processus, jeu actif en mémoire. L'application ne peut pas servir deux
  personnes simultanément.
- **Aucune authentification sur l'API.** Prévue pour tourner en local ; voir la
  section correspondante du rapport de sécurité.
- **Aucun test frontend** : les modules purs (`claims-filter`,
  `analyses-filter`, `cumulative-cost`) sont les premiers candidats.
- **Pas de juge LLM** pour la qualité du `message_client`. Le sujet le donne
  pour optionnel ; les évaluations restent entièrement notées par du code.
- **Les données client sont écrites en clair** dans `backend/dataset.sqlite3`
  (ignoré par git). Voir le rapport de sécurité.

## Documents liés

- [`DEMO.md`](DEMO.md) — parcours de démonstration guidé, 10 minutes
- [`RAPPORT_COUT_SECURITE.md`](RAPPORT_COUT_SECURITE.md) — coûts mesurés et
  analyse de sécurité
