"""
src/api_models.py

Contrat de reponse de l'API HTTP (src/api.py). Ces modeles refletent les
TypedDict deja definis dans le domaine :

    tools.Policy, tools.Claim, tools.CoverageResult,
    tools.RepairBandResult, tools.FraudSignalsResult,
    schema.TriageOutput (contrat_sortie.md)

Ils ne sont PAS une seconde source de verite metier : aucune regle, aucun
seuil, aucune valeur d'enum metier n'est redefinie ici. Leur seul role est de
figer la forme de ce qui sort par HTTP, et de servir de reference au frontend.

DEUX CHOIX EXPLICITES :

1. `TriageResult.output` est un dict libre, PAS un modele valide.
   La sortie du modele peut etre malformee - c'est precisement ce que
   schema.validate_full mesure et ce que `validation_errors` rapporte. Un
   modele de reponse strict rejetterait la reponse HTTP entiere en cas de
   sortie invalide, c'est-a-dire masquerait exactement les echecs que le
   projet cherche a rendre visibles. La sortie est donc transmise telle
   quelle, accompagnee de ses erreurs de validation.

2. `Screening` expose `original_text`, mais UNIQUEMENT pour lecture humaine.
   guard.classify_client_text conserve le texte client d'origine ; il sort
   maintenant par HTTP pour que l'interface puisse le donner A LIRE au
   gestionnaire (rendu inerte par React, jamais interprete). Il ne franchit
   JAMAIS la frontiere du modele : c'est `text_for_model` qui va au triage,
   c'est-a-dire la version assainie et encadree, ou le placeholder si le
   verdict est INJECTION. Lisible par l'humain, invisible pour le modele.
"""

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# =============================================================================
# Referentiel (lecture seule, aucun appel de modele)
# =============================================================================

class Policy(BaseModel):
    """Miroir de tools.Policy."""

    policy_id: str
    assure: str
    vehicule: str
    formule: str
    date_debut: str
    date_fin: str
    franchise_tnd: int
    garanties: list[str]
    exclusions: list[str]


class Claim(BaseModel):
    """Miroir de tools.Claim.

    `description_client` porte ici la version SCREENEE (assainie et encadree,
    ou redigee), jamais le texte brut : cette API expose ce que le modele
    voit, pas ce que le client a ecrit.

    Les colonnes de reference `priorite_attendue` / `triage_attendu` de
    claims_auto.csv sont absentes de ce modele, comme elles le sont deja de
    tools.get_claim. Elles ne doivent jamais sortir par HTTP.
    """

    claim_id: str
    policy_id: str
    date_sinistre: str
    type_sinistre: str
    description_client: str
    blessure: str
    constat: str
    photos: str
    devis_tnd: int
    tiers_identifie: str
    kilometrage_declare: int


class Screening(BaseModel):
    """Trace du filtre anti-injection (src/guard.py).

    `verdict` vaut None quand la couche [2] (classifieur LLM) n'a pas ete
    executee - cas de la consultation gratuite. C'est une absence de verdict,
    pas un verdict favorable : l'interface doit l'afficher comme telle et ne
    jamais la presenter comme un SAFE.
    """

    verdict: Optional[Literal["SAFE", "SUSPECT", "INJECTION"]] = None
    markers_found: list[str] = Field(default_factory=list)
    classifier_available: bool = True
    classifier_called: bool = False
    text_for_model: str = ""
    # Texte brut du client, expose pour lecture HUMAINE uniquement (voir le
    # choix 2 du module). Le modele ne voit que `text_for_model`.
    original_text: str = ""
    redacted: bool = False


class CoverageResult(BaseModel):
    """Miroir de tools.CoverageResult."""

    policy_id: str
    claim_id: str
    type_sinistre: str
    garantie_recherchee: str
    formule: str
    garantie_applicable: bool
    raison: str
    verification_humaine_recommandee: bool


class RepairBandResult(BaseModel):
    """Miroir de tools.RepairBandResult."""

    devis_tnd: int
    bande: str
    borne_inf: int
    borne_sup: int
    expertise_obligatoire: bool


class FraudSignalsResult(BaseModel):
    """Miroir de tools.FraudSignalsResult.

    `details` reste un dict libre : ses cles varient selon le type de sinistre
    et les donnees disponibles (voir tools.detect_fraud_signals).
    """

    claim_id: str
    policy_id: str
    signaux_fraude: list[str] = Field(default_factory=list)
    signaux_non_evaluables: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class ClaimSummary(BaseModel):
    """Ligne de la file d'attente.

    Ne contient PAS `description_client` : la file n'a pas besoin du texte
    client, et ne pas l'y faire figurer evite d'exposer du contenu non fiable
    hors du composant qui sait le mettre en quarantaine. Le drapeau
    `injection_markers_found` suffit a signaler le dossier.
    """

    claim_id: str
    policy_id: str
    date_sinistre: str
    type_sinistre: str
    blessure: str
    devis_tnd: int
    tiers_identifie: str
    assure: Optional[str] = None
    vehicule: Optional[str] = None
    formule: Optional[str] = None
    injection_markers_found: list[str] = Field(default_factory=list)

    # Repere de lecture calcule par src/urgence.py a partir des seules colonnes
    # ci-dessus : deterministe, gratuit, disponible avant toute analyse.
    #
    # CE N'EST PAS TriageOutput.priorite. Celle-ci est une conclusion du
    # modele, n'existe qu'apres un passage de l'agent, et rien ne la persiste.
    # Les deux peuvent legitimement diverger sur un meme dossier ; l'interface
    # ne leur donne ni les memes mots ni la meme forme. Voir urgence.py pour le
    # bareme et pour la part qui en est deduite plutot que documentee.
    #
    # `str` et non Literal[...] : ce fichier tient deja les enums metier
    # dehors (Claim.type_sinistre, RepairBandResult.bande) pour ne pas devenir
    # une seconde source de verite a cote de urgence.NIVEAUX.
    urgence_estimee: str = "normale"
    urgence_motifs: list[str] = Field(default_factory=list)


class ClaimDetail(BaseModel):
    """Fiche dossier complete : les 5 tools deroules de facon deterministe,
    sans aucun appel de modele (voir agent.build_context)."""

    claim: Claim
    policy: Policy
    coverage: CoverageResult
    repair_band: RepairBandResult
    fraud_signals: FraudSignalsResult
    screening: Screening


# =============================================================================
# Triage (appels de modele)
# =============================================================================

class ToolCall(BaseModel):
    """Une entree de `tool_call_trace` (SUJET_PROJET.md: "traces par etape")."""

    tool: str
    input: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] = Field(default_factory=dict)


class TriageResult(BaseModel):
    """Retour de agent.triage_claim, transmis tel quel.

    Les trois formes possibles cohabitent dans un seul modele, car elles se
    distinguent par la presence de champs et non par un discriminant :

      - succes            : `output` renseigne, `validation_errors` eventuel
      - JSON non parseable: `error` + `raw_output`
      - plafond de tours  : `error` seul

    `output` et `validation_errors` peuvent etre renseignes EN MEME TEMPS :
    une sortie produite mais non conforme reste une sortie. L'interface doit
    afficher les deux, jamais l'une a la place de l'autre.
    """

    claim_id: str
    output: Optional[dict[str, Any]] = None
    validation_errors: list[str] = Field(default_factory=list)
    tool_call_trace: list[ToolCall] = Field(default_factory=list)
    usage: dict[str, int] = Field(default_factory=dict)
    error: Optional[str] = None
    raw_output: Optional[str] = None

    # Modele effectivement utilise pour le triage, et cout facture par cette
    # execution - filtre anti-injection compris, et au tarif de CHAQUE modele
    # (le filtre reste sur le defaut, voir agent._run_cost_usd). Il est
    # renseigne sur les trois formes ci-dessus, echecs compris : une execution
    # interrompue a quand meme ete payee.
    model: Optional[str] = None
    cost_usd: float = 0.0


# =============================================================================
# Divers
# =============================================================================

class Health(BaseModel):
    status: str
    model: str
    api_key_configured: bool


class ModelOption(BaseModel):
    """Un modele proposable pour l'analyse (voir config.AVAILABLE_MODELS).

    `default` marque celui applique quand l'utilisateur n'en choisit aucun.
    """

    id: str
    label: str
    default: bool = False


class LigneRejetee(BaseModel):
    """Ligne d'un fichier depose qui n'a pas pu etre lue.

    Sert a rendre visible ce qui etait auparavant supprime en silence : une
    ligne mal formee disparaissait du jeu de donnees sans que l'utilisateur,
    qui l'avait pourtant fournie, puisse l'apprendre. Le numero de ligne est
    celui du tableur (l'en-tete est la ligne 1) pour que la correction soit
    immediate.
    """

    fichier: str
    ligne: int
    identifiant: str
    raison: str


class AnalyseResume(BaseModel):
    """Une ligne de l'historique (GET /api/analyses).

    `triage` et `priorite` sont a None quand l'analyse n'a pas abouti ;
    `erreur` porte alors le motif. Les echecs figurent dans l'historique au
    meme titre que les reussites : ils ont ete factures.
    """

    id: int
    claim_id: str
    #: None si le jeu de donnees d'origine a ete supprime depuis.
    dataset_id: Optional[int] = None
    #: Recopie a l'enregistrement, donc toujours lisible meme apres suppression.
    dataset_nom: str
    analyse_le: str
    model: str
    cost_usd: float
    triage: Optional[str] = None
    priorite: Optional[str] = None
    erreur: Optional[str] = None


class AnalyseDetail(AnalyseResume):
    """Une analyse conservee, avec le contrat de sortie produit par le modele."""

    output: Optional[dict[str, Any]] = None
    validation_errors: list[str] = Field(default_factory=list)


class DatasetResume(BaseModel):
    """Une ligne de la liste des jeux enregistres (GET /api/datasets).

    Sans le contenu : le selecteur de l'interface n'a besoin que des
    etiquettes et des comptes, et charger huit jeux de dossiers pour afficher
    une liste deroulante serait absurde.
    """

    id: int
    nom: str
    claims_filename: str
    policies_filename: str
    claims_count: int
    policies_count: int
    loaded_at: str
    #: Celui que l'application sert en ce moment.
    actif: bool


class DatasetState(BaseModel):
    """Etat du jeu de donnees depose par l'utilisateur (src/dataset.py).

    `loaded` a false signifie que l'application n'a AUCUNE donnee : il n'y a
    rien a lister et rien a analyser tant que les deux fichiers n'ont pas ete
    deposes. Les fichiers de data/ ne servent jamais de repli.
    """

    loaded: bool

    # Nom donne par l'utilisateur au depot. C'est ce que l'interface affiche
    # pour dire SUR QUOI on travaille : les noms de fichiers ne suffisent pas
    # a distinguer deux jeux, qui s'appellent souvent tous les deux
    # claims.csv.
    nom: Optional[str] = None
    dataset_id: Optional[int] = None

    claims_filename: Optional[str] = None
    policies_filename: Optional[str] = None
    claims_count: Optional[int] = None
    policies_count: Optional[int] = None
    loaded_at: Optional[str] = None

    # Declarations dont le contrat est absent du fichier des contrats. Ce
    # n'est pas bloquant - les autres dossiers restent traitables - mais
    # l'utilisateur doit le savoir avant de s'etonner d'une erreur.
    claims_sans_contrat: list[str] = Field(default_factory=list)

    # Lignes des deux fichiers qui n'ont pas pu etre lues. Le depot reussit
    # malgre elles - les autres lignes sont exploitables - mais elles doivent
    # etre affichees : sinon l'utilisateur travaille sur un fichier ampute
    # sans le savoir.
    lignes_rejetees: list[LigneRejetee] = Field(default_factory=list)


class RulesDocument(BaseModel):
    name: str
    content: str


class Rules(BaseModel):
    """Documents de reference, servis tels quels : ils font foi, et
    l'interface doit pouvoir les montrer sans reformulation."""

    documents: list[RulesDocument]
