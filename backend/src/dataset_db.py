"""
src/dataset_db.py

Base SQLite du jeu de donnees actif : ce qui permet au jeu depose de survivre
a un redemarrage du serveur, la ou il ne vivait qu'en memoire.

CE QUE CE MODULE N'EST PAS : le chemin de lecture. L'application continue de
servir les dossiers depuis les dictionnaires en memoire de src/dataset.py.
Cette base est la copie DURABLE, ecrite au moment du depot et relue une seule
fois, au demarrage. Aucune requete d'API ne la touche. Les deux copies ne
peuvent donc pas diverger : elles sont ecrites ensemble, dans le meme
processus, par un unique appel (dataset.set_active).

SQLite et non un serveur de base de donnees : le fichier s'ouvre, il n'y a
rien a installer, rien a demarrer et aucun port a surveiller. C'est la seule
forme de persistance qui ne complique pas le lancement de l'application.

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
d'origine remettrait ces reponses sur le disque, precisement ce que le reste
du projet s'applique a eviter.
"""

import json
import sqlite3
from typing import Optional

from config import DATASET_DB_FILE

# Chemin du fichier de base. Modifiable (use_path) pour que les tests
# travaillent sur un fichier temporaire au lieu de la base de l'utilisateur.
_db_path = DATASET_DB_FILE


def use_path(path) -> None:
    """Deplace la base. Reservee aux tests et aux outils."""
    global _db_path
    _db_path = path


def path():
    return _db_path


_SCHEMA = """
CREATE TABLE IF NOT EXISTS dataset (
    id                INTEGER PRIMARY KEY CHECK (id = 1),
    claims_filename   TEXT NOT NULL,
    policies_filename TEXT NOT NULL,
    loaded_at         TEXT NOT NULL,
    lignes_rejetees   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS claims (
    claim_id TEXT PRIMARY KEY,
    data     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS policies (
    policy_id TEXT PRIMARY KEY,
    data      TEXT NOT NULL
);
"""


def _connect() -> sqlite3.Connection:
    """Une connexion NEUVE a chaque operation, refermee aussitot.

    L'API sert le triage dans un thread separe et les requetes dans un pool :
    une connexion partagee demanderait check_same_thread=False et un verrou a
    tenir soi-meme. Les ecritures se comptent ici sur les doigts d'une main
    (un depot, un retrait), la connexion par operation ne coute donc rien.
    """
    _db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


def save(
    claims: dict,
    policies: dict,
    *,
    claims_filename: str,
    policies_filename: str,
    loaded_at: str,
    lignes_rejetees: Optional[list] = None,
) -> None:
    """Remplace d'un bloc le jeu de donnees enregistre.

    Tout se joue dans UNE transaction : un depot interrompu laisse la base sur
    l'etat precedent, jamais sur un melange des deux fichiers.
    """
    conn = _connect()
    try:
        with conn:  # transaction : COMMIT en sortie, ROLLBACK si exception
            conn.execute("DELETE FROM claims")
            conn.execute("DELETE FROM policies")
            conn.execute("DELETE FROM dataset")
            conn.executemany(
                "INSERT INTO claims (claim_id, data) VALUES (?, ?)",
                [(cid, json.dumps(c, ensure_ascii=False)) for cid, c in claims.items()],
            )
            conn.executemany(
                "INSERT INTO policies (policy_id, data) VALUES (?, ?)",
                [(pid, json.dumps(p, ensure_ascii=False)) for pid, p in policies.items()],
            )
            conn.execute(
                "INSERT INTO dataset (id, claims_filename, policies_filename, "
                "loaded_at, lignes_rejetees) VALUES (1, ?, ?, ?, ?)",
                (
                    claims_filename,
                    policies_filename,
                    loaded_at,
                    json.dumps(list(lignes_rejetees or []), ensure_ascii=False),
                ),
            )
    finally:
        conn.close()


def load() -> Optional[dict]:
    """Le jeu de donnees enregistre, ou None s'il n'y en a pas.

    None signifie "rien d'enregistre" : l'application demarre alors sur son
    ecran de depot, comme avant l'existence de cette base.

    Une base illisible (fichier corrompu, schema d'une version anterieure) est
    traitee comme une base vide. Refuser de demarrer parce qu'un cache ne se
    relit pas serait hors de proportion : l'utilisateur redepose ses fichiers.
    """
    try:
        conn = _connect()
    except sqlite3.Error:
        return None

    try:
        meta = conn.execute("SELECT * FROM dataset WHERE id = 1").fetchone()
        if meta is None:
            return None

        claims = {
            row["claim_id"]: json.loads(row["data"])
            for row in conn.execute("SELECT claim_id, data FROM claims")
        }
        policies = {
            row["policy_id"]: json.loads(row["data"])
            for row in conn.execute("SELECT policy_id, data FROM policies")
        }
        # Un enregistrement sans aucune declaration n'est pas exploitable :
        # l'API refuserait de repondre sur les sinistres tout en affichant un
        # jeu de donnees charge.
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
    except (sqlite3.Error, json.JSONDecodeError, KeyError):
        return None
    finally:
        conn.close()


def clear() -> None:
    """Efface REELLEMENT le jeu de donnees enregistre.

    Appelee par dataset.clear(), donc par DELETE /api/dataset : quand
    l'utilisateur retire ses donnees, elles ne doivent pas rester sur le
    disque en attendant le prochain demarrage.
    """
    try:
        conn = _connect()
    except sqlite3.Error:
        return
    try:
        with conn:
            conn.execute("DELETE FROM claims")
            conn.execute("DELETE FROM policies")
            conn.execute("DELETE FROM dataset")
    except sqlite3.Error:
        pass
    finally:
        conn.close()
