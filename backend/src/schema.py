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

Regle supplementaire (regles_sinistres.md, "Actions interdites a
l'assistant") : ni message_client ni prochaine_action ne doivent recommander
de valider un paiement, rejeter definitivement une demande, modifier une
police ou cloturer un sinistre. Voir check_no_forbidden_action.

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

import unicodedata
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

# Actions que regles_sinistres.md, section "Actions interdites a l'assistant",
# interdit formellement :
#     - Valider un paiement.
#     - Rejeter definitivement une demande.
#     - Modifier une police.
#     - Cloturer un sinistre.
#
# Regroupees par action interdite pour que l'alerte puisse nommer la regle
# violee, et pas seulement le mot trouve.
#
# MEMES LIMITES QUE PAYMENT_PROMISE_KEYWORDS : listes NON EXHAUSTIVES, simple
# correspondance de sous-chaines. Une absence d'alerte ne prouve pas l'absence
# de violation. C'est un filet de securite tardif, pas un controle complet :
# la vraie prevention reste la section 2 de prompts/system_prompt.md.
#
# CE QUI N'EST VOLONTAIREMENT PAS LISTE : les constats de non-couverture du
# type "n'est pas couvert par votre formule" ou "cette garantie n'est pas
# incluse". Ce sont des FAITS calcules par check_coverage, et le triage
# `hors_garantie` existe precisement pour les exprimer - les signaler
# produirait une alerte sur chaque dossier legitimement hors garantie. Seule
# la DECISION ("rejete definitivement", "dossier clos") est interdite, pas la
# description de la couverture.
FORBIDDEN_ACTION_KEYWORDS = {
    "cloturer un sinistre": [
        "cloturer le sinistre",
        "cloturer le dossier",
        "cloture du dossier",
        "cloture le dossier",
        "dossier clos",
        "classer sans suite",
    ],
    # Les formes flechies sont listees explicitement (masculin/feminin) :
    # "demande" etant feminin, le modele ecrit "rejetee definitivement", que
    # "rejete definitivement" n'attrape pas. Illustration concrete de la
    # fragilite de ce mecanisme - toute forme non listee passe.
    "rejeter definitivement une demande": [
        "rejeter definitivement",
        "rejete definitivement",
        "rejetee definitivement",
        "refuser definitivement",
        "refuse definitivement",
        "refusee definitivement",
        "rejet definitif",
        "refus definitif",
    ],
    "valider un paiement": [
        "valider le paiement",
        "approuver le paiement",
        "proceder au paiement",
        "proceder au reglement",
        "autoriser l'indemnisation",
        "approuver l'indemnisation",
    ],
    "modifier une police": [
        "modifier la police",
        "modifier le contrat",
        "mettre a jour la police",
        "resilier la police",
        "resilier le contrat",
    ],
}


def _normalize(text: str) -> str:
    """Minuscules + accents retires, pour que la recherche de mots-cles ne
    depende pas de l'accentuation produite par le modele.

    NECESSAIRE : les listes de mots-cles de ce fichier sont ecrites sans
    accents (comme tout le code du projet), alors que le modele, lui, ecrit
    du francais accentue. Sans cette normalisation, "cloturer le dossier"
    n'attrape pas "cloturer le dossier" ecrit avec un accent circonflexe, et
    "vous serez rembourse" laisse passer "vous serez rembourse" accentue -
    autrement dit les alertes ne se declenchaient que sur les sorties non
    accentuees, au hasard de la generation.
    """
    decomposed = unicodedata.normalize("NFD", (text or "").lower())
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


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
    normalized = _normalize(message_client)
    for phrase in PAYMENT_PROMISE_KEYWORDS:
        if phrase in normalized:
            warnings.append(f"message_client contient une formulation a risque: '{phrase}'.")
    return warnings


def check_no_forbidden_action(text: str, champ: str) -> List[str]:
    """Alerte si `text` recommande ou annonce une action que
    regles_sinistres.md interdit a l'assistant (voir
    FORBIDDEN_ACTION_KEYWORDS).

    POURQUOI CE CONTROLE (revue du 20/08/2026) : sur deux executions
    successives de l'eval, deux sorties ont recommande une action interdite -
    "cloturer le sinistre" dans `prochaine_action` (CLM-006) et un
    vocabulaire de paiement dans `message_client` (CLM-008). Aucune n'a ete
    signalee : `validate_business_rules` ne regardait que les promesses de
    paiement, et uniquement dans `message_client`. Les quatre interdits de
    regles_sinistres.md n'avaient donc aucun controle cote code.

    Args:
        text: le contenu a examiner.
        champ: nom du champ examine, repris dans le message d'alerte pour
            que l'erreur dise OU la formulation a ete trouvee.

    Returns:
        Liste d'alertes (vide si rien trouve). Chaque alerte nomme l'action
        interdite violee, pas seulement le mot-cle.
    """
    warnings: List[str] = []
    normalized = _normalize(text)
    for action, phrases in FORBIDDEN_ACTION_KEYWORDS.items():
        for phrase in phrases:
            if phrase in normalized:
                warnings.append(
                    f"{champ} recommande une action interdite a l'assistant "
                    f"({action}, regles_sinistres.md) : '{phrase}'."
                )
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

    # Les actions interdites sont cherchees dans les DEUX champs de texte
    # libre : `message_client` (ce que le client lit) et `prochaine_action`
    # (la consigne interne au gestionnaire). Ne verifier que le premier
    # laissait passer "cloturer le sinistre" ecrit dans le second, alors
    # qu'y recommander une action interdite est exactement le comportement
    # que regles_sinistres.md proscrit.
    for champ in ("message_client", "prochaine_action"):
        value = output.get(champ)
        if isinstance(value, str):
            errors.extend(check_no_forbidden_action(value, champ))

    fr = output.get("fourchette_reparation_tnd")
    fr_well_typed = (
        isinstance(fr, dict)
        and isinstance(fr.get("min"), int)
        and isinstance(fr.get("max"), int)
    )
    if "triage" in output and fr_well_typed and "validation_humaine_requise" in output:
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
