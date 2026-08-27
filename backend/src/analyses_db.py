"""
src/analyses_db.py

Historique des analyses : ce que l'agent a produit, dossier par dossier,
conserve apres coup.

POURQUOI CONSERVER. Une analyse coute un appel de modele et plusieurs
dizaines de secondes. Sans historique, le resultat disparaissait a la
fermeture de l'onglet, et relire une conclusion d'hier demandait de la
racheter. Un gestionnaire doit pouvoir revenir sur ce qu'il a deja traite.

CE QUI EST ENREGISTRE : le contrat de sortie tel que le modele l'a produit, le
modele utilise, le cout, la date, le jeu de donnees d'origine, et le NOM DE
L'ASSURE - lu dans le contrat au moment de l'analyse et recopie ici, pour que
l'historique se cherche par nom de personne et pas seulement par identifiant
de dossier.

LES ECHECS AUSSI (`erreur` renseigne, `output` a NULL) : ils ont ete factures
comme les autres, et un historique qui ne montrerait que les reussites
donnerait une image fausse de ce qui a ete depense.

CE QUI N'EST PAS ENREGISTRE : la trace des outils et la reponse brute du
modele. Ce sont des elements de mise au point, deja diffuses en direct vers la
console du navigateur (frontend/src/lib/dev-log.ts), et les conserver
gonflerait la base sans servir a traiter un dossier.

LE NOM DU JEU ET CELUI DE L'ASSURE SONT RECOPIES dans chaque ligne, et la cle
etrangere passe a NULL si le jeu est supprime (voir le schema dans
dataset_db.py). Une analyse a eu lieu : supprimer les fichiers d'origine ne
doit pas effacer la trace de ce qui a ete fait, ni le cout qu'il a represente.
C'est aussi ce qui permet de chercher « Trabelsi » dans l'historique alors que
le contrat qui portait ce nom n'existe plus nulle part.
"""

import json
import sqlite3
from datetime import datetime, timezone
from typing import Optional

import dataset_db

# Colonnes communes a la liste et au detail. La liste ne charge pas `output` :
# afficher un tableau ne demande pas de deserialiser cinquante contrats de
# sortie complets.
_COLONNES_RESUME = (
    "id, claim_id, assure, dataset_id, dataset_nom, analyse_le, model, cost_usd, "
    "triage, priorite, erreur"
)


def _resume(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "claim_id": row["claim_id"],
        # Chaine vide pour une analyse enregistree avant l'ajout de cette
        # colonne, ou dont le contrat etait introuvable.
        "assure": row["assure"] or "",
        "dataset_id": row["dataset_id"],
        "dataset_nom": row["dataset_nom"],
        "analyse_le": row["analyse_le"],
        "model": row["model"],
        "cost_usd": row["cost_usd"],
        "triage": row["triage"],
        "priorite": row["priorite"],
        "erreur": row["erreur"],
    }


def enregistrer(
    resultat: dict, *, dataset_id=None, dataset_nom: str = "", assure: str = ""
) -> Optional[int]:
    """Range le retour de agent.triage_claim. Renvoie l'identifiant cree.

    Ne leve JAMAIS : un historique qui n'a pas pu s'ecrire ne doit pas faire
    echouer une analyse deja payee et deja affichee a l'utilisateur. L'echec
    part sur stderr et l'analyse suit son cours.
    """
    sortie = resultat.get("output")
    try:
        conn = dataset_db.ouvrir()
    except sqlite3.Error as e:
        dataset_db._avertir(f"historique non ecrit ({type(e).__name__}: {e}).")
        return None

    try:
        with conn:
            curseur = conn.execute(
                "INSERT INTO analyses (claim_id, assure, dataset_id, dataset_nom, "
                "analyse_le, model, cost_usd, triage, priorite, output, "
                "validation_errors, erreur) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    resultat.get("claim_id", ""),
                    assure,
                    dataset_id,
                    dataset_nom,
                    datetime.now(timezone.utc).isoformat(),
                    resultat.get("model") or "",
                    float(resultat.get("cost_usd") or 0.0),
                    # Sorties du contrat, remontees en colonnes : ce sont les
                    # deux seules choses qu'on lit dans un tableau, et
                    # json_extract a chaque ligne serait du travail pour rien.
                    (sortie or {}).get("triage"),
                    (sortie or {}).get("priorite"),
                    json.dumps(sortie, ensure_ascii=False) if sortie else None,
                    json.dumps(resultat.get("validation_errors") or [], ensure_ascii=False),
                    resultat.get("error"),
                ),
            )
        return curseur.lastrowid
    except (sqlite3.Error, TypeError, ValueError) as e:
        dataset_db._avertir(f"historique non ecrit ({type(e).__name__}: {e}).")
        return None
    finally:
        conn.close()


def liste(limite: int = 200) -> list:
    """Les analyses, la plus recente d'abord, sans leur contrat de sortie."""
    try:
        conn = dataset_db.ouvrir()
    except sqlite3.Error as e:
        dataset_db._avertir(f"historique illisible ({type(e).__name__}: {e}).")
        return []
    try:
        return [
            _resume(row)
            for row in conn.execute(
                f"SELECT {_COLONNES_RESUME} FROM analyses "
                "ORDER BY analyse_le DESC, id DESC LIMIT ?",
                (limite,),
            )
        ]
    except sqlite3.Error as e:
        dataset_db._avertir(f"historique illisible ({type(e).__name__}: {e}).")
        return []
    finally:
        conn.close()


def get(analyse_id: int) -> Optional[dict]:
    """Une analyse complete, contrat de sortie compris. None si inconnue."""
    try:
        conn = dataset_db.ouvrir()
    except sqlite3.Error as e:
        dataset_db._avertir(f"historique illisible ({type(e).__name__}: {e}).")
        return None
    try:
        row = conn.execute("SELECT * FROM analyses WHERE id = ?", (analyse_id,)).fetchone()
        if row is None:
            return None
        detail = _resume(row)
        detail["output"] = json.loads(row["output"]) if row["output"] else None
        detail["validation_errors"] = json.loads(row["validation_errors"] or "[]")
        return detail
    except (sqlite3.Error, json.JSONDecodeError) as e:
        dataset_db._avertir(f"analyse illisible ({type(e).__name__}: {e}).")
        return None
    finally:
        conn.close()


def supprimer(analyse_id: int) -> bool:
    """Retire une analyse de l'historique. False si inconnue."""
    try:
        conn = dataset_db.ouvrir()
    except sqlite3.Error as e:
        dataset_db._avertir(f"historique inaccessible ({type(e).__name__}: {e}).")
        return False
    try:
        with conn:
            curseur = conn.execute("DELETE FROM analyses WHERE id = ?", (analyse_id,))
        return curseur.rowcount > 0
    except sqlite3.Error as e:
        dataset_db._avertir(f"suppression impossible ({type(e).__name__}: {e}).")
        return False
    finally:
        conn.close()


def total_cout_usd() -> float:
    """Somme des couts enregistres. Contrairement au compteur du bandeau, qui
    vit dans le navigateur, celle-ci vaut pour toute la machine."""
    try:
        conn = dataset_db.ouvrir()
    except sqlite3.Error:
        return 0.0
    try:
        return float(next(conn.execute("SELECT COALESCE(SUM(cost_usd), 0) FROM analyses"))[0])
    except sqlite3.Error:
        return 0.0
    finally:
        conn.close()


def vider() -> None:
    """Efface tout l'historique. Reservee aux tests et a une remise a zero."""
    try:
        conn = dataset_db.ouvrir()
    except sqlite3.Error:
        return
    try:
        with conn:
            conn.execute("DELETE FROM analyses")
    except sqlite3.Error:
        pass
    finally:
        conn.close()
