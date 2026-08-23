"""
src/dataset.py

Jeu de donnees actif de l'application web.

D'OU VIENNENT LES DONNEES (decision utilisateur) :
Les deux fichiers d'entree - declarations et contrats - sont DEPOSES PAR
L'UTILISATEUR dans l'interface. Ils ne sont pas lus dans le depot.

Les fichiers de data/ (claims_auto.csv, policies_auto.csv) ne sont PAS la
source de l'application : ce sont les jeux d'essai de la suite d'evaluation,
qui tourne en terminal contre des sinistres dont on connait les reponses
attendues. Les confondre reviendrait a faire croire a l'utilisateur qu'il
travaille sur ses dossiers alors qu'il regarde des donnees de test.

CONSEQUENCE : tant que rien n'a ete depose, l'application n'a rien a montrer.
L'API refuse alors de repondre sur les sinistres, et l'interface affiche un
ecran de depot. Il n'existe AUCUN repli silencieux sur data/ : ce repli
serait precisement le defaut a eviter.

DUREE DE VIE : en memoire, dans le processus du serveur. Un redemarrage vide
le jeu de donnees et l'utilisateur redepose ses fichiers. Rien n'est ecrit
sur le disque, donc rien a nettoyer et aucune donnee client oubliee sur la
machine.
"""

from datetime import datetime, timezone
from typing import Optional

# D'OU VIENT LE JEU DE DONNEES ACTIF.
#
# L'etiquette est OBLIGATOIRE a chaque chargement, et c'est elle qui permet a
# l'API web de refuser un jeu de donnees qu'elle n'a pas recu de l'utilisateur.
# Sans elle, il suffirait qu'un chemin de code appelle
# tools.load_dataset_from_files() dans le processus du serveur pour que les
# jeux d'essai de data/ s'affichent comme s'il s'agissait des dossiers du
# gestionnaire - exactement la confusion que ce module existe pour empecher.
SOURCE_DEPOT = "depot"        # fichiers deposes par l'utilisateur dans l'interface
SOURCE_FICHIERS = "fichiers"  # fichiers lus sur le disque (evals, terminal, tests)

_SOURCES = (SOURCE_DEPOT, SOURCE_FICHIERS)

_claims: Optional[dict] = None
_policies: Optional[dict] = None
_source: Optional[str] = None
_meta: dict = {}


def set_active(
    claims: dict,
    policies: dict,
    *,
    source: str,
    claims_filename: str = "",
    policies_filename: str = "",
    rejets: Optional[list] = None,
) -> None:
    """Remplace le jeu de donnees actif. Les deux fichiers vont toujours
    ensemble : une declaration sans son contrat n'est pas exploitable.

    `source` dit d'ou viennent ces donnees (SOURCE_DEPOT ou SOURCE_FICHIERS).
    Il est obligatoire et sans valeur par defaut : personne ne doit pouvoir
    charger un jeu de donnees sans declarer son origine.

    `rejets` liste les lignes des fichiers qui n'ont pas pu etre lues
    (tools.LigneRejetee). Elles sont conservees AVEC le jeu de donnees, et non
    renvoyees seulement en reponse au depot : l'interface se rafraichit en
    relisant /api/dataset, et un avertissement qui disparait au premier
    rafraichissement ne previent personne."""
    if source not in _SOURCES:
        raise ValueError(
            f"source={source!r} inconnue : attendu {SOURCE_DEPOT!r} "
            f"(depose par l'utilisateur) ou {SOURCE_FICHIERS!r} (lu sur disque)."
        )
    global _claims, _policies, _source, _meta
    _claims = claims
    _policies = policies
    _source = source
    _meta = {
        "claims_filename": claims_filename,
        "policies_filename": policies_filename,
        "claims_count": len(claims),
        "policies_count": len(policies),
        "loaded_at": datetime.now(timezone.utc).isoformat(),
        "lignes_rejetees": list(rejets or []),
    }


def clear() -> None:
    global _claims, _policies, _source, _meta
    _claims = None
    _policies = None
    _source = None
    _meta = {}


def source() -> Optional[str]:
    """Origine du jeu de donnees actif, ou None si rien n'est charge.

    L'API web s'en sert pour ne servir QUE des donnees deposees par
    l'utilisateur (voir api._exiger_jeu_de_donnees)."""
    return _source


def is_loaded() -> bool:
    return _claims is not None and _policies is not None


def get_claims() -> Optional[dict]:
    """Declarations actives, ou None si rien n'a ete depose.

    None signifie "aucun jeu de donnees" et non "jeu de donnees vide" : c'est
    ce qui permet a tools.py de distinguer les deux et de ne pas se rabattre
    sur les fichiers du depot."""
    return _claims


def get_policies() -> Optional[dict]:
    return _policies


def summary() -> dict:
    """Etat du jeu de donnees, pour l'interface."""
    if not is_loaded():
        return {"loaded": False}
    return {"loaded": True, **_meta}
