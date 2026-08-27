"""
src/dataset_db.py

Base SQLite locale de l'application. Ce module tient les JEUX DE DONNEES
deposes - ce qui leur permet de survivre a un redemarrage du serveur, la ou
ils ne vivaient qu'en memoire. L'historique des analyses partage le meme
fichier et vit dans src/analyses_db.py ; le schema complet est ici, en un seul
endroit.

PLUSIEURS JEUX, UN SEUL ACTIF. L'utilisateur nomme ce qu'il depose et passe
d'un jeu a l'autre sans avoir a redeposer ses fichiers. Le jeu ACTIF est celui
que sert l'application ; les autres attendent. Le nom est ce qui rend ce choix
possible : deux fichiers appeles claims.csv ne se distinguent pas dans une
liste, "Sinistres juillet" et "Jeu de demonstration" si.

CE QUE CE MODULE N'EST PAS : le chemin de lecture. L'application sert les
dossiers depuis les dictionnaires en memoire de src/dataset.py. Cette base est
la copie DURABLE, ecrite au moment du depot et relue au demarrage ou lors d'un
changement de jeu. Aucune requete d'API ne la traverse.

SQLite et non un serveur de base de donnees : le fichier s'ouvre, il n'y a
rien a installer, rien a demarrer et aucun port a surveiller.

POURQUOI DU JSON PAR ENREGISTREMENT, ET NON UNE COLONNE PAR CHAMP :
la forme d'un sinistre est deja definie une fois, dans tools._claims_from_rows.
La recopier en colonnes SQL en ferait une deuxieme definition a tenir a jour,
et la moindre colonne ajoutee au CSV demanderait une migration. La cle
primaire (claim_id / policy_id) reste une vraie colonne, et SQLite sait
interroger le reste avec json_extract() si besoin.

CE QUI N'ENTRE JAMAIS ICI : le texte CSV brut du fichier depose. Un fichier de
declarations peut contenir priorite_attendue et triage_attendu - les reponses
attendues des evaluations. tools._claims_from_rows les ecarte a la lecture, et
c'est le resultat de cette lecture qui est enregistre. Conserver le CSV
d'origine remettrait ces reponses sur le disque.
"""

import json
import sqlite3
import sys
from typing import Optional

from config import DATASET_DB_FILE

# Chemin du fichier de base. Modifiable (use_path) pour que les tests
# travaillent sur un fichier temporaire au lieu de la base de l'utilisateur.
_db_path = DATASET_DB_FILE

# Un nom sert a reconnaitre un jeu dans une liste : vide il n'apprend rien,
# tres long il deborde de partout dans l'interface.
NOM_LONGUEUR_MAX = 60


class NomDejaPris(Exception):
    """Un jeu porte deja ce nom. Refuse plutot que remplace : ecraser en
    silence un jeu de donnees sur une simple collision de nom ferait perdre du
    travail sans le dire."""


class NomInvalide(Exception):
    """Nom vide ou trop long."""


def use_path(path) -> None:
    """Deplace la base. Reservee aux tests et aux outils."""
    global _db_path
    _db_path = path


def path():
    return _db_path


_SCHEMA = """
CREATE TABLE IF NOT EXISTS datasets (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    nom               TEXT NOT NULL UNIQUE COLLATE NOCASE,
    claims_filename   TEXT NOT NULL,
    policies_filename TEXT NOT NULL,
    loaded_at         TEXT NOT NULL,
    lignes_rejetees   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS claims (
    dataset_id INTEGER NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    claim_id   TEXT NOT NULL,
    data       TEXT NOT NULL,
    PRIMARY KEY (dataset_id, claim_id)
);
CREATE TABLE IF NOT EXISTS policies (
    dataset_id INTEGER NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    policy_id  TEXT NOT NULL,
    data       TEXT NOT NULL,
    PRIMARY KEY (dataset_id, policy_id)
);
-- Une seule ligne : le jeu actif. Table separee plutot qu'une colonne
-- `actif` sur datasets, ou il faudrait penser a eteindre l'ancien a chaque
-- changement - et ou deux jeux pourraient se retrouver actifs a la fois.
CREATE TABLE IF NOT EXISTS actif (
    id         INTEGER PRIMARY KEY CHECK (id = 1),
    dataset_id INTEGER NOT NULL REFERENCES datasets(id) ON DELETE CASCADE
);
-- Historique des analyses (src/analyses_db.py). Le nom du jeu y est RECOPIE,
-- et la cle etrangere passe a NULL plutot que d'emporter la ligne : une
-- analyse a eu lieu, elle a coute de l'argent, et supprimer le jeu de donnees
-- ne doit pas effacer la trace de ce qui a ete fait.
CREATE TABLE IF NOT EXISTS analyses (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id          TEXT NOT NULL,
    assure            TEXT NOT NULL DEFAULT '',
    dataset_id        INTEGER REFERENCES datasets(id) ON DELETE SET NULL,
    dataset_nom       TEXT NOT NULL,
    analyse_le        TEXT NOT NULL,
    model             TEXT NOT NULL,
    cost_usd          REAL NOT NULL,
    triage            TEXT,
    priorite          TEXT,
    output            TEXT,
    validation_errors TEXT NOT NULL,
    erreur            TEXT
);
CREATE INDEX IF NOT EXISTS analyses_par_date ON analyses (analyse_le DESC);
"""


def valider_nom(nom: str) -> str:
    """Nom epure, ou NomInvalide."""
    propre = " ".join((nom or "").split())
    if not propre:
        raise NomInvalide("Le nom du jeu de donnees est obligatoire.")
    if len(propre) > NOM_LONGUEUR_MAX:
        raise NomInvalide(
            f"Le nom du jeu de donnees ne doit pas depasser {NOM_LONGUEUR_MAX} caracteres."
        )
    return propre


# =============================================================================
# Connexion et migration
# =============================================================================

def _avertir(message: str) -> None:
    """Sur stderr, jamais en silence.

    Une base illisible ne doit pas empecher l'application de demarrer - mais
    elle ne doit pas non plus se faire passer pour une base VIDE. Les deux se
    ressemblent trop : sans ce message, un jeu de donnees disparu ressemble a
    un jeu jamais depose, et personne ne sait qu'il y a eu un probleme.
    """
    print(f"[dataset_db] {message}", file=sys.stderr)


def ouvrir() -> sqlite3.Connection:
    """Connexion prete a l'emploi, schema applique. Utilisee par les autres
    modules qui partagent ce meme fichier (src/analyses_db.py)."""
    return _connect()


def _connect() -> sqlite3.Connection:
    """Une connexion NEUVE a chaque operation, refermee aussitot.

    L'API sert le triage dans un thread separe et les requetes dans un pool :
    une connexion partagee demanderait check_same_thread=False et un verrou a
    tenir soi-meme. Les ecritures se comptent sur les doigts d'une main (un
    depot, un changement de jeu), la connexion par operation ne coute rien.
    """
    _db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_db_path)
    conn.row_factory = sqlite3.Row
    # Indispensable ici : c'est ce qui fait disparaitre les sinistres et les
    # contrats quand leur jeu est supprime (ON DELETE CASCADE). SQLite laisse
    # les cles etrangeres inactives par defaut.
    conn.execute("PRAGMA foreign_keys = ON")
    _preparer(conn)
    return conn


def _preparer(conn: sqlite3.Connection) -> None:
    """Cree le schema, en reprenant au passage une base de la version
    precedente (un seul jeu, sans nom)."""
    tables = {
        row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }

    a_migrer = "dataset" in tables and "datasets" not in tables
    if a_migrer:
        # RENOMMER PLUTOT QUE SUPPRIMER. La reprise qui suit peut echouer -
        # contenu inattendu, disque plein, bogue. Les anciennes tables sont
        # donc mises de cote sous _v1 et ne disparaissent qu'une fois la
        # reprise reussie : en cas d'echec, les donnees sont toujours dans le
        # fichier et un message le dit, au lieu d'une base vide sans
        # explication.
        with conn:
            for table in ("dataset", "claims", "policies"):
                conn.execute(f"DROP TABLE IF EXISTS {table}_v1")
                conn.execute(f"ALTER TABLE {table} RENAME TO {table}_v1")

    conn.executescript(_SCHEMA)
    _ajouter_colonnes_manquantes(conn)

    if a_migrer:
        _migrer_depuis_v1(conn)


# Colonnes apparues APRES la premiere version d'une table. CREATE TABLE IF NOT
# EXISTS ne touche pas une table deja creee : sans ce rattrapage, une base
# existante resterait sur l'ancienne forme et toute requete nommant la nouvelle
# colonne echouerait.
#
# Ajouter une colonne est la seule migration que SQLite fasse sans reecrire la
# table. Une valeur par defaut est donc obligatoire : les lignes deja
# enregistrees la recevront.
_COLONNES_AJOUTEES = (
    # (table, colonne, definition) - l'assure d'une analyse, recopie a
    # l'enregistrement comme le nom du jeu (voir analyses_db.py).
    ("analyses", "assure", "TEXT NOT NULL DEFAULT ''"),
)


def _ajouter_colonnes_manquantes(conn: sqlite3.Connection) -> None:
    for table, colonne, definition in _COLONNES_AJOUTEES:
        try:
            existantes = {
                row["name"] for row in conn.execute(f"PRAGMA table_info({table})")
            }
            if colonne in existantes:
                continue
            with conn:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {colonne} {definition}")
        except sqlite3.Error as e:
            _avertir(
                f"colonne {table}.{colonne} non ajoutee ({type(e).__name__}: {e})."
            )


def _migrer_depuis_v1(conn: sqlite3.Connection) -> None:
    """Reprend le jeu unique de l'ancien format. Perdre les donnees d'un
    utilisateur parce que le format a change serait le plus sur moyen de lui
    faire perdre confiance dans cette base."""
    try:
        ancien = _lire_ancien_format(conn)
        if ancien is not None:
            with conn:
                dataset_id = _inserer(
                    conn,
                    # Le jeu avait ete depose sans nom : on lui en donne un
                    # tire de son fichier.
                    nom=_nom_par_defaut(conn, ancien["claims_filename"]),
                    claims=ancien["claims"],
                    policies=ancien["policies"],
                    claims_filename=ancien["claims_filename"],
                    policies_filename=ancien["policies_filename"],
                    loaded_at=ancien["loaded_at"],
                    lignes_rejetees=ancien["lignes_rejetees"],
                )
                _activer(conn, dataset_id)
    except (sqlite3.Error, json.JSONDecodeError, KeyError, IndexError) as e:
        _avertir(
            f"reprise de l'ancien format impossible ({type(e).__name__}: {e}). "
            "Les donnees d'origine sont conservees dans les tables dataset_v1, "
            "claims_v1 et policies_v1 de "
            f"{_db_path}. Redeposez vos fichiers pour continuer."
        )
        return

    with conn:
        for table in ("dataset_v1", "claims_v1", "policies_v1"):
            conn.execute(f"DROP TABLE IF EXISTS {table}")


def _lire_ancien_format(conn: sqlite3.Connection) -> Optional[dict]:
    """Le jeu unique de l'ancien format, lu dans les tables mises de cote."""
    meta = conn.execute("SELECT * FROM dataset_v1 WHERE id = 1").fetchone()
    if meta is None:
        return None
    claims = {
        row["claim_id"]: json.loads(row["data"])
        for row in conn.execute("SELECT claim_id, data FROM claims_v1")
    }
    policies = {
        row["policy_id"]: json.loads(row["data"])
        for row in conn.execute("SELECT policy_id, data FROM policies_v1")
    }
    if not claims or not policies:
        return None
    return {
        "claims": claims,
        "policies": policies,
        "claims_filename": meta["claims_filename"],
        "policies_filename": meta["policies_filename"],
        "loaded_at": meta["loaded_at"],
        "lignes_rejetees": json.loads(meta["lignes_rejetees"]),
    }


def _nom_par_defaut(conn: sqlite3.Connection, fichier: str) -> str:
    """Un nom libre derive du nom de fichier."""
    base = (fichier or "Jeu de donnees").rsplit(".", 1)[0][:NOM_LONGUEUR_MAX] or "Jeu de donnees"
    nom = base
    suffixe = 2
    while conn.execute("SELECT 1 FROM datasets WHERE nom = ?", (nom,)).fetchone():
        nom = f"{base[: NOM_LONGUEUR_MAX - 4]} ({suffixe})"
        suffixe += 1
    return nom


# =============================================================================
# Ecriture
# =============================================================================

def _inserer(
    conn: sqlite3.Connection,
    *,
    nom: str,
    claims: dict,
    policies: dict,
    claims_filename: str,
    policies_filename: str,
    loaded_at: str,
    lignes_rejetees: Optional[list],
) -> int:
    curseur = conn.execute(
        "INSERT INTO datasets (nom, claims_filename, policies_filename, "
        "loaded_at, lignes_rejetees) VALUES (?, ?, ?, ?, ?)",
        (
            nom,
            claims_filename,
            policies_filename,
            loaded_at,
            json.dumps(list(lignes_rejetees or []), ensure_ascii=False),
        ),
    )
    dataset_id = curseur.lastrowid
    conn.executemany(
        "INSERT INTO claims (dataset_id, claim_id, data) VALUES (?, ?, ?)",
        [(dataset_id, cid, json.dumps(c, ensure_ascii=False)) for cid, c in claims.items()],
    )
    conn.executemany(
        "INSERT INTO policies (dataset_id, policy_id, data) VALUES (?, ?, ?)",
        [(dataset_id, pid, json.dumps(p, ensure_ascii=False)) for pid, p in policies.items()],
    )
    return dataset_id


def _activer(conn: sqlite3.Connection, dataset_id: int) -> None:
    conn.execute("DELETE FROM actif")
    conn.execute("INSERT INTO actif (id, dataset_id) VALUES (1, ?)", (dataset_id,))


def save(
    nom: str,
    claims: dict,
    policies: dict,
    *,
    claims_filename: str,
    policies_filename: str,
    loaded_at: str,
    lignes_rejetees: Optional[list] = None,
) -> int:
    """Enregistre un NOUVEAU jeu, qui devient le jeu actif. Renvoie son id.

    Leve NomInvalide ou NomDejaPris. Tout se joue dans une transaction : un
    depot interrompu laisse la base sur son etat precedent, jamais sur un
    melange des deux jeux.
    """
    propre = valider_nom(nom)
    conn = _connect()
    try:
        with conn:
            if conn.execute("SELECT 1 FROM datasets WHERE nom = ?", (propre,)).fetchone():
                raise NomDejaPris(f"Un jeu de donnees s'appelle deja {propre!r}.")
            dataset_id = _inserer(
                conn,
                nom=propre,
                claims=claims,
                policies=policies,
                claims_filename=claims_filename,
                policies_filename=policies_filename,
                loaded_at=loaded_at,
                lignes_rejetees=lignes_rejetees,
            )
            _activer(conn, dataset_id)
        return dataset_id
    finally:
        conn.close()


def activer(dataset_id: int) -> bool:
    """Designe le jeu actif. False si l'identifiant est inconnu."""
    conn = _connect()
    try:
        with conn:
            if not conn.execute(
                "SELECT 1 FROM datasets WHERE id = ?", (dataset_id,)
            ).fetchone():
                return False
            _activer(conn, dataset_id)
        return True
    finally:
        conn.close()


def desactiver() -> None:
    """Plus aucun jeu actif, sans rien supprimer.

    C'est ce que fait « changer de fichiers » : l'application revient a son
    ecran de depot, et les jeux enregistres restent disponibles dans la liste.
    """
    conn = _connect()
    try:
        with conn:
            conn.execute("DELETE FROM actif")
    finally:
        conn.close()


def supprimer(dataset_id: int) -> bool:
    """Supprime DEFINITIVEMENT un jeu et tout son contenu. False si inconnu.

    Les sinistres, les contrats et le marqueur d'activation disparaissent avec
    lui (ON DELETE CASCADE) : rien de l'utilisateur ne doit rester sur le
    disque apres une suppression demandee.
    """
    conn = _connect()
    try:
        with conn:
            curseur = conn.execute("DELETE FROM datasets WHERE id = ?", (dataset_id,))
        return curseur.rowcount > 0
    finally:
        conn.close()


def clear() -> None:
    """Vide la base entiere. Reservee aux tests et a une remise a zero."""
    conn = _connect()
    try:
        with conn:
            conn.execute("DELETE FROM actif")
            conn.execute("DELETE FROM claims")
            conn.execute("DELETE FROM policies")
            conn.execute("DELETE FROM datasets")
    finally:
        conn.close()


# =============================================================================
# Lecture
# =============================================================================

def liste() -> list:
    """Tous les jeux enregistres, le plus recent d'abord.

    Sans leur contenu : c'est ce qui alimente le selecteur de l'interface, qui
    n'a besoin que des etiquettes et des comptes.
    """
    try:
        conn = _connect()
    except sqlite3.Error as e:
        _avertir(f"liste des jeux illisible ({type(e).__name__}: {e}).")
        return []
    try:
        actif = _id_actif(conn)
        return [
            {
                "id": row["id"],
                "nom": row["nom"],
                "claims_filename": row["claims_filename"],
                "policies_filename": row["policies_filename"],
                "loaded_at": row["loaded_at"],
                "claims_count": row["claims_count"],
                "policies_count": row["policies_count"],
                "actif": row["id"] == actif,
            }
            for row in conn.execute(
                "SELECT d.*, "
                "(SELECT COUNT(*) FROM claims c WHERE c.dataset_id = d.id) AS claims_count, "
                "(SELECT COUNT(*) FROM policies p WHERE p.dataset_id = d.id) AS policies_count "
                "FROM datasets d ORDER BY d.loaded_at DESC, d.id DESC"
            )
        ]
    except sqlite3.Error as e:
        _avertir(f"liste des jeux illisible ({type(e).__name__}: {e}).")
        return []
    finally:
        conn.close()


def _id_actif(conn: sqlite3.Connection) -> Optional[int]:
    row = conn.execute("SELECT dataset_id FROM actif WHERE id = 1").fetchone()
    return row["dataset_id"] if row else None


def load(dataset_id: Optional[int] = None) -> Optional[dict]:
    """Le contenu d'un jeu, ou du jeu ACTIF si aucun id n'est donne.

    None signifie "rien a charger" : l'application demarre alors sur son ecran
    de depot. Une base illisible (fichier corrompu, schema d'une version
    anterieure) est traitee de la meme facon - refuser de demarrer parce qu'un
    enregistrement ne se relit pas serait hors de proportion.
    """
    try:
        conn = _connect()
    except sqlite3.Error as e:
        _avertir(f"base illisible ({type(e).__name__}: {e}). Redeposez vos fichiers.")
        return None

    try:
        if dataset_id is None:
            dataset_id = _id_actif(conn)
            if dataset_id is None:
                return None

        meta = conn.execute("SELECT * FROM datasets WHERE id = ?", (dataset_id,)).fetchone()
        if meta is None:
            return None

        claims = {
            row["claim_id"]: json.loads(row["data"])
            for row in conn.execute(
                "SELECT claim_id, data FROM claims WHERE dataset_id = ?", (dataset_id,)
            )
        }
        policies = {
            row["policy_id"]: json.loads(row["data"])
            for row in conn.execute(
                "SELECT policy_id, data FROM policies WHERE dataset_id = ?", (dataset_id,)
            )
        }
        # Un enregistrement sans declaration ni contrat n'est pas exploitable :
        # l'API refuserait de repondre sur les sinistres tout en affichant un
        # jeu charge.
        if not claims or not policies:
            return None

        return {
            "id": meta["id"],
            "nom": meta["nom"],
            "claims": claims,
            "policies": policies,
            "claims_filename": meta["claims_filename"],
            "policies_filename": meta["policies_filename"],
            "loaded_at": meta["loaded_at"],
            "lignes_rejetees": json.loads(meta["lignes_rejetees"]),
        }
    except (sqlite3.Error, json.JSONDecodeError, KeyError, IndexError) as e:
        _avertir(
            f"jeu de donnees illisible ({type(e).__name__}: {e}). "
            "Il reste enregistre ; redeposez vos fichiers pour continuer."
        )
        return None
    finally:
        conn.close()
