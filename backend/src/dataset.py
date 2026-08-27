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

DUREE DE VIE : les dictionnaires ci-dessous restent le chemin de LECTURE, en
memoire dans le processus du serveur. Ils sont doubles d'une base SQLite
(src/dataset_db.py) ecrite au moment du depot, et relue au demarrage ou lors
d'un changement de jeu : un redemarrage du serveur ne fait donc plus perdre
les fichiers deposes.

PLUSIEURS JEUX, UN SEUL ACTIF. L'utilisateur nomme ce qu'il depose, et passe
d'un jeu a l'autre sans redeposer ses fichiers (voir activer()). Les
dictionnaires ci-dessous ne contiennent JAMAIS que le jeu actif : deux jeux
peuvent porter les memes identifiants de sinistre, et les melanger ferait
travailler le gestionnaire sur un dossier qu'il ne regarde pas.

CONSEQUENCE ASSUMEE : les dossiers de l'utilisateur - noms, vehicules,
montants, messages clients - sont desormais ECRITS SUR LE DISQUE, dans
backend/dataset.sqlite3. Ce n'etait pas le cas avant, et c'est le prix de la
persistance. Deux garde-fous : DELETE /api/dataset efface reellement la base
(voir clear() ci-dessous), et seul un jeu DEPOSE y est enregistre - jamais un
jeu lu sur le disque par les evaluations ou les tests (voir set_active).
"""

from datetime import datetime, timezone
from typing import Optional

import dataset_db

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
    loaded_at: Optional[str] = None,
    nom: str = "",
    dataset_id: Optional[int] = None,
    persister: bool = True,
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
    rafraichissement ne previent personne.

    `loaded_at` (ISO 8601) impose la date de chargement au lieu de prendre
    l'instant present. Sert au seul restore_from_db() : un jeu retrouve au
    demarrage a ete depose une fois, et doit continuer d'afficher CETTE
    date-la plutot que celle du redemarrage.

    `nom` est l'etiquette choisie par l'utilisateur au depot. Elle est
    OBLIGATOIRE pour un jeu depose (elle seule permet de le reconnaitre dans
    la liste et d'y revenir), et vide pour un jeu lu sur le disque, qui
    n'entre de toute facon pas dans la base.

    `persister` a False n'ecrit pas dans la base. Sert a restore_from_db() et
    a activer(), qui viennent precisement d'en sortir les donnees."""
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
        "nom": nom,
        "dataset_id": dataset_id,
        "claims_filename": claims_filename,
        "policies_filename": policies_filename,
        "claims_count": len(claims),
        "policies_count": len(policies),
        "loaded_at": loaded_at or datetime.now(timezone.utc).isoformat(),
        "lignes_rejetees": list(rejets or []),
    }

    # SEUL UN JEU DEPOSE EST ENREGISTRE. Un jeu lu sur le disque
    # (SOURCE_FICHIERS : evaluations, terminal, tests) ne doit jamais atterrir
    # dans la base : il ecraserait les dossiers de l'utilisateur, et serait
    # ressuscite au demarrage suivant comme s'il les avait deposes - la
    # confusion meme que ce module existe pour empecher.
    if persister and source == SOURCE_DEPOT:
        _meta["dataset_id"] = dataset_db.save(
            nom,
            claims,
            policies,
            claims_filename=claims_filename,
            policies_filename=policies_filename,
            loaded_at=_meta["loaded_at"],
            lignes_rejetees=_meta["lignes_rejetees"],
        )


def clear() -> None:
    """Ferme le jeu actif : l'application n'a plus de donnees a servir et
    revient a son ecran de depot.

    NE SUPPRIME RIEN. Depuis que les jeux portent un nom, ils survivent a
    leur fermeture et restent dans la liste - c'est tout l'interet de les
    avoir nommes. Pour supprimer pour de bon, voir supprimer()."""
    global _claims, _policies, _source, _meta
    _claims = None
    _policies = None
    _source = None
    _meta = {}
    dataset_db.desactiver()


def liste() -> list:
    """Les jeux enregistres, pour le selecteur de l'interface."""
    return dataset_db.liste()


def activer(dataset_id: int) -> bool:
    """Change de jeu actif. False si l'identifiant est inconnu.

    Le contenu est relu depuis la base et remplace INTEGRALEMENT ce qui etait
    en memoire : aucun sinistre du jeu precedent ne survit au changement."""
    if not dataset_db.activer(dataset_id):
        return False

    enregistre = dataset_db.load(dataset_id)
    if enregistre is None:
        return False

    _appliquer(enregistre)
    return True


def supprimer(dataset_id: int) -> bool:
    """Supprime un jeu enregistre. False si l'identifiant est inconnu.

    Supprimer le jeu ACTIF revient a fermer l'application sur son ecran de
    depot : ses donnees ne sont plus nulle part."""
    etait_actif = _meta.get("dataset_id") == dataset_id
    if not dataset_db.supprimer(dataset_id):
        return False
    if etait_actif:
        clear()
    return True


def _appliquer(enregistre: dict) -> None:
    """Installe en memoire un jeu qui SORT de la base (d'ou persister=False,
    et d'ou la date de depot conservee telle quelle)."""
    set_active(
        enregistre["claims"],
        enregistre["policies"],
        # La base ne contient que du depot (voir set_active), donc l'origine
        # retrouvee est necessairement celle-la.
        source=SOURCE_DEPOT,
        claims_filename=enregistre["claims_filename"],
        policies_filename=enregistre["policies_filename"],
        rejets=enregistre["lignes_rejetees"],
        loaded_at=enregistre["loaded_at"],
        nom=enregistre["nom"],
        dataset_id=enregistre["id"],
        persister=False,
    )


def restore_from_db() -> bool:
    """Recharge le dernier jeu DEPOSE, s'il en existe un. Renvoie True si un
    jeu a ete retrouve.

    Appelee une seule fois, au demarrage du serveur (voir api.py). Ne fait
    rien si un jeu est deja actif : une restauration ne doit pas pouvoir
    ecraser ce que l'utilisateur vient de deposer.
    """
    if is_loaded():
        return False

    enregistre = dataset_db.load()
    if enregistre is None:
        return False

    _appliquer(enregistre)
    return True


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
