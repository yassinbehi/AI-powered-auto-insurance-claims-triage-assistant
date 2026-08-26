"""Central configuration for thresholds, retry delays, and limits."""

from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
# Ce fichier vit dans backend/src/, d'ou les deux niveaux de racine :
#   BACKEND_ROOT = backend/      (code applicatif : src, evals, prompts, tests)
#   REPO_ROOT    = racine du depot (contient backend/ et data/)
BACKEND_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_ROOT.parent

# data/ est RESTE a la racine du depot, volontairement hors de backend/ : ce
# sont les donnees d'entree fournies avec le sujet, en lecture seule, et elles
# ne sont pas la propriete du backend. Ne pas remplacer ce chemin par
# BACKEND_ROOT / "data" sans deplacer le dossier lui-meme.
DATA_DIR = REPO_ROOT / "data"
PROMPTS_DIR = BACKEND_ROOT / "prompts"

POLICIES_FILE = DATA_DIR / "policies_auto.csv"
CLAIMS_FILE = DATA_DIR / "claims_auto.csv"
REGLES_SINISTRES_FILE = DATA_DIR / "regles_sinistres.md"
SYSTEM_PROMPT_PATH = PROMPTS_DIR / "system_prompt.md"

# Charge backend/.env des l'import de ce module, avant tout appel a
# anthropic.Anthropic() ailleurs dans le code. N'ecrase jamais une variable
# deja presente dans l'environnement (comportement par defaut de load_dotenv).
load_dotenv(BACKEND_ROOT / ".env")

# ---------------------------------------------------------------------------
# Anthropic API
# ---------------------------------------------------------------------------
# budget_tokens.md: "Modele par defaut: Claude Haiku 4.5."
MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 1500
# Temperature 0 : on veut le triage le plus deterministe possible. Un meme
# dossier doit produire le meme classement d'un appel a l'autre, aussi bien
# pour le triage (agent.py) que pour le classifieur anti-injection (guard.py).
TEMPERATURE = 0

# ---------------------------------------------------------------------------
# Agent loop limits
# ---------------------------------------------------------------------------
MAX_TOOL_TURNS = 8

# ---------------------------------------------------------------------------
# API retry (exponential backoff: RETRY_BASE_DELAY_SECONDS * 2^attempt)
# ---------------------------------------------------------------------------
MAX_RETRIES = 3
RETRY_BASE_DELAY_SECONDS = 2

# ---------------------------------------------------------------------------
# Business thresholds (regles_sinistres.md, contrat_sortie.md)
# ---------------------------------------------------------------------------
# Devis > 5000 TND: expertise obligatoire; validation humaine requise.
EXPERTISE_REQUIRED_THRESHOLD_TND = 5000

# ---------------------------------------------------------------------------
# Eval suite (evals/run_evals.py - jamais importe par src/main.py)
# ---------------------------------------------------------------------------
EVAL_CASES_FILE = DATA_DIR / "cases_evaluation.jsonl"

# ---------------------------------------------------------------------------
# Cout (src/cost.py). budget_tokens.md: "Budget plafond: 5 USD. Budget
# cible: 1.50 a 2.75 USD." Tarifs Claude Haiku 4.5, en USD par million de
# tokens.
#
# A VERIFIER par l'utilisateur contre platform.claude.com/docs/en/pricing
# avant toute decision budgetaire critique : PRICE_INPUT/OUTPUT viennent
# d'une reference de pricing mise en cache (datee) ; les tarifs de cache
# sont DERIVES via le multiplicateur standard Anthropic (write 5m = 1.25x
# input, write 1h = 2x input, read = 0.1x input), pas des valeurs listees
# telles quelles pour ce modele precis.
# ---------------------------------------------------------------------------
PRICE_INPUT_PER_MTOK_USD = 1.00
PRICE_OUTPUT_PER_MTOK_USD = 5.00
PRICE_CACHE_WRITE_5M_PER_MTOK_USD = 1.25  # TTL utilisee partout dans agent.py
PRICE_CACHE_WRITE_1H_PER_MTOK_USD = 2.00  # non utilise actuellement (pas de ttl="1h")
PRICE_CACHE_READ_PER_MTOK_USD = 0.10

BUDGET_CEILING_USD = 5.00
BUDGET_TARGET_MIN_USD = 1.50
BUDGET_TARGET_MAX_USD = 2.75
