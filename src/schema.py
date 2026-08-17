"""
src/schema.py

Encode le contrat de sortie JSON defini dans contrat_sortie.md :

    {
      "claim_id": "CLM-001",
      "triage": "traitement_standard | pieces_manquantes | expertise_requise |
                 suspicion_fraude | hors_garantie",
      "priorite": "basse | normale | haute | critique",
      "garantie_applicable": true,
      "pieces_manquantes": ["..."],
      "signaux_fraude": ["..."],
      "fourchette_reparation_tnd": {"min": 0, "max": 0},
      "prochaine_action": "...",
      "message_client": "...",
      "validation_humaine_requise": true
    }

Regles (contrat_sortie.md) :
    - message_client ne doit pas promettre de paiement.
    - validation_humaine_requise est toujours true pour suspicion_fraude,
      hors_garantie, montant estime > 5000 TND, blessure, ou rejet.
    - signaux_fraude peut etre vide mais doit toujours etre present.

Ce module ne PREND AUCUNE DECISION de triage : il valide seulement qu'une
sortie deja produite (par le prompt / l'agent) respecte le contrat. C'est
un validateur, pas un generateur.

INTERPRETATION EXPLICITE :
"rejet" est cite dans la regle validation_humaine_requise mais n'est pas une
valeur de `triage` definie par le contrat (les 5 valeurs possibles sont
traitement_standard, pieces_manquantes, expertise_requise, suspicion_fraude,
hors_garantie - aucune ne s'appelle "rejet"). Par ailleurs
regles_sinistres.md interdit explicitement a l'assistant de "rejeter
definitivement une demande". La lecture la plus coherente avec ces deux
contraintes est que "rejet" correspond au triage `hors_garantie` (le seul
triage qui equivaut a un refus de prise en charge). Ce mapping est isole
dans REJET_EQUIVALENT_TRIAGE ci-dessous pour etre facilement revu.
"""

from typing import TypedDict, List, Optional

from config import EXPERTISE_REQUIRED_THRESHOLD_TND


TRIAGE_VALUES = {
    "traitement_standard",
    "pieces_manquantes",
    "expertise_requise",
    "suspicion_fraude",
    "hors_garantie",
}

PRIORITE_VALUES = {"basse", "normale", "haute", "critique"}

# Voir note d'interpretation ci-dessus.
REJET_EQUIVALENT_TRIAGE = "hors_garantie"

MONTANT_ELEVE_THRESHOLD_TND = EXPERTISE_REQUIRED_THRESHOLD_TND  # centralise dans config.py

# Triages pour lesquels validation_humaine_requise doit toujours etre True,
# d'apres contrat_sortie.md ("suspicion_fraude, hors_garantie, ... ou rejet").
TRIAGE_REQUIRING_HUMAN_VALIDATION = {"suspicion_fraude", "hors_garantie"}

# Heuristique simple de detection de promesse de paiement dans
# message_client. NON EXHAUSTIVE : contrat_sortie.md n'enumere pas de liste
# de formulations interdites, cette liste est un point de depart a
# completer/ajuster. Elle sert d'alerte, pas de preuve absolue.
PAYMENT_PROMISE_KEYWORDS = [
    "nous allons vous rembourser",
    "vous serez rembourse",
    "remboursement garanti",
    "paiement effectue",
    "nous payons",
    "indemnisation accordee",
    "montant vous sera verse",
    "sera verse sous",
]


class FourchetteReparation(TypedDict):
    min: int
    max: int


class TriageOutput(TypedDict):
    claim_id: str
    triage: str
    priorite: str
    garantie_applicable: bool
    pieces_manquantes: List[str]
    signaux_fraude: List[str]
    fourchette_reparation_tnd: FourchetteReparation
    prochaine_action: str
    message_client: str
    validation_humaine_requise: bool


REQUIRED_KEYS = list(TriageOutput.__annotations__.keys())


def validate_schema(output: dict) -> List[str]:
    """Verifie la structure/typage de base du contrat contrat_sortie.md.

    Ne verifie PAS encore les regles metier (validation_humaine_requise,
    promesse de paiement) : voir validate_business_rules pour cela.

    Returns:
        Liste d'erreurs (vide si le schema est respecte).
    """
    errors: List[str] = []

    if not isinstance(output, dict):
        return ["La sortie n'est pas un objet JSON (dict)."]

    for key in REQUIRED_KEYS:
        if key not in output:
            errors.append(f"Champ manquant: '{key}'.")

    if "triage" in output and output["triage"] not in TRIAGE_VALUES:
        errors.append(
            f"triage invalide: {output['triage']!r} (attendu: {sorted(TRIAGE_VALUES)})."
        )

    if "priorite" in output and output["priorite"] not in PRIORITE_VALUES:
        errors.append(
            f"priorite invalide: {output['priorite']!r} (attendu: {sorted(PRIORITE_VALUES)})."
        )

    if "garantie_applicable" in output and not isinstance(output["garantie_applicable"], bool):
        errors.append("garantie_applicable doit etre un booleen.")

    if "pieces_manquantes" in output and not isinstance(output["pieces_manquantes"], list):
        errors.append("pieces_manquantes doit etre une liste (peut etre vide).")

    # signaux_fraude "peut etre vide mais doit toujours etre present"
    # (contrat_sortie.md) -> on verifie la presence ET le type liste.
    if "signaux_fraude" not in output:
        errors.append("signaux_fraude doit toujours etre present (peut etre une liste vide).")
    elif not isinstance(output["signaux_fraude"], list):
        errors.append("signaux_fraude doit etre une liste (peut etre vide).")

    fr = output.get("fourchette_reparation_tnd")
    if fr is not None:
        if not isinstance(fr, dict) or "min" not in fr or "max" not in fr:
            errors.append("fourchette_reparation_tnd doit etre un objet {min, max}.")
        else:
            if not isinstance(fr["min"], int) or not isinstance(fr["max"], int):
                errors.append("fourchette_reparation_tnd.min/max doivent etre des entiers.")
            elif fr["min"] > fr["max"]:
                errors.append("fourchette_reparation_tnd.min ne peut pas etre superieur a max.")

    if "validation_humaine_requise" in output and not isinstance(
        output["validation_humaine_requise"], bool
    ):
        errors.append("validation_humaine_requise doit etre un booleen.")

    if "message_client" in output and not isinstance(output["message_client"], str):
        errors.append("message_client doit etre une chaine de caracteres.")

    if "prochaine_action" in output and not isinstance(output["prochaine_action"], str):
        errors.append("prochaine_action doit etre une chaine de caracteres.")

    return errors


def check_no_payment_promise(message_client: str) -> List[str]:
    """Alerte heuristique si message_client semble promettre un paiement.

    NON EXHAUSTIF (voir PAYMENT_PROMISE_KEYWORDS) : une absence d'alerte ne
    garantit pas l'absence de promesse de paiement, seulement l'absence des
    formulations listees. A completer selon les cas reels observes.
    """
    warnings: List[str] = []
    lowered = message_client.lower()
    for phrase in PAYMENT_PROMISE_KEYWORDS:
        if phrase in lowered:
            warnings.append(f"message_client contient une formulation a risque: '{phrase}'.")
    return warnings


def expected_validation_humaine_requise(
    triage: str,
    fourchette_reparation_tnd: FourchetteReparation,
    blessure: bool,
) -> bool:
    """Calcule si validation_humaine_requise DOIT etre True, d'apres
    contrat_sortie.md: "toujours true pour suspicion_fraude, hors_garantie,
    montant estime > 5000 TND, blessure, ou rejet."

    `rejet` est traite comme equivalent a `hors_garantie` (voir note
    d'interpretation en tete de fichier), donc deja couvert par
    TRIAGE_REQUIRING_HUMAN_VALIDATION.
    """
    if triage in TRIAGE_REQUIRING_HUMAN_VALIDATION:
        return True
    if fourchette_reparation_tnd.get("max", 0) > MONTANT_ELEVE_THRESHOLD_TND:
        return True
    if blessure:
        return True
    return False


def validate_business_rules(output: dict, blessure: bool = False) -> List[str]:
    """Verifie les regles metier de contrat_sortie.md sur une sortie deja
    conforme au schema (appeler validate_schema avant, ou en complement).

    Args:
        output: sortie candidate (dict).
        blessure: valeur du champ `blessure` du claim source ("oui"/"non"
            dans claims_auto.csv converti en bool par l'appelant), necessaire
            car ce champ n'est pas repris tel quel dans le contrat de sortie
            mais conditionne validation_humaine_requise.

    Returns:
        Liste d'erreurs (vide si conforme).
    """
    errors: List[str] = []

    if "message_client" in output:
        errors.extend(check_no_payment_promise(output["message_client"]))

    if "triage" in output and "fourchette_reparation_tnd" in output and "validation_humaine_requise" in output:
        expected = expected_validation_humaine_requise(
            output["triage"], output["fourchette_reparation_tnd"], blessure
        )
        actual = output["validation_humaine_requise"]
        if expected and not actual:
            errors.append(
                "validation_humaine_requise doit etre true "
                f"(triage='{output['triage']}', "
                f"max={output['fourchette_reparation_tnd'].get('max')}, blessure={blessure})."
            )

    return errors


def validate_full(output: dict, blessure: bool = False) -> List[str]:
    """Validation complete : schema + regles metier.

    Execute toujours validate_schema, puis validate_business_rules qui ne
    verifie que les champs presents et bien types (pour eviter des
    exceptions en cascade si le schema est deja invalide).
    """
    errors = validate_schema(output)
    errors.extend(validate_business_rules(output, blessure=blessure))
    return errors


if __name__ == "__main__":
    # Exemples manuels de validation.
    good_example = {
        "claim_id": "CLM-002",
        "triage": "hors_garantie",
        "priorite": "normale",
        "garantie_applicable": False,
        "pieces_manquantes": [],
        "signaux_fraude": [],
        "fourchette_reparation_tnd": {"min": 800, "max": 900},
        "prochaine_action": "Informer le client que ce sinistre n'est pas couvert par sa formule.",
        "message_client": "Votre formule actuelle ne couvre pas le bris de glace.",
        "validation_humaine_requise": True,
    }
    print("good_example errors:", validate_full(good_example))

    bad_example = {
        "claim_id": "CLM-002",
        "triage": "hors_garantie",
        "priorite": "normale",
        "garantie_applicable": False,
        "pieces_manquantes": [],
        # signaux_fraude manquant volontairement
        "fourchette_reparation_tnd": {"min": 800, "max": 900},
        "prochaine_action": "...",
        "message_client": "Vous serez rembourse sous 48h.",
        "validation_humaine_requise": False,  # devrait etre True (hors_garantie)
    }
    print("bad_example errors:", validate_full(bad_example))
