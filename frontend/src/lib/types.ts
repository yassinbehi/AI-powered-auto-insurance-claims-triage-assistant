/**
 * Contrat de l'API de triage (backend/src/api_models.py).
 *
 * Ces types sont ecrits a la main plutot que generes : le backend est la
 * source de verite, et toute divergence doit se voir en revue de code. Les
 * valeurs d'enum viennent de backend/src/schema.py et de data/contrat_sortie.md.
 */

// =============================================================================
// Enums metier (contrat_sortie.md)
// =============================================================================

export const TRIAGE_VALUES = [
  "traitement_standard",
  "pieces_manquantes",
  "expertise_requise",
  "suspicion_fraude",
  "hors_garantie",
] as const;
export type Triage = (typeof TRIAGE_VALUES)[number];

export const PRIORITE_VALUES = ["basse", "normale", "haute", "critique"] as const;
export type Priorite = (typeof PRIORITE_VALUES)[number];

/**
 * Urgence estimee de la file, calculee par backend/src/urgence.py a partir des
 * seules colonnes deja presentes dans la file.
 *
 * MEMES quatre valeurs que Priorite, et c'est volontaire : il n'y a qu'une
 * echelle ordinale a apprendre dans ce produit. Ce n'est PAS la meme grandeur
 * pour autant. La priorite est une conclusion du modele et n'existe qu'apres
 * un triage ; l'urgence existe avant, gratuitement, et les deux peuvent
 * diverger sur un meme dossier. Elles ne portent jamais les memes mots ni la
 * meme forme a l'ecran : voir URGENCE_META dans lib/status.ts.
 *
 * La liste est dupliquee a dessein plutot que derivee de PRIORITE_VALUES :
 * les deux echelles doivent pouvoir evoluer separement.
 */
export const URGENCE_VALUES = ["basse", "normale", "haute", "critique"] as const;
export type Urgence = (typeof URGENCE_VALUES)[number];

/** guard.ALLOWED_VERDICTS. `null` = couche [2] non executee, ce qui n'est PAS
 *  un verdict favorable. */
export type Verdict = "SAFE" | "SUSPECT" | "INJECTION";

/** Tableau et non simple union : le filtre de la file doit valider a
 *  l'execution ce qui arrive de l'URL. */
export const TYPE_SINISTRE_VALUES = [
  "collision",
  "bris_glace",
  "vol",
  "incendie",
  "rc_tiers",
] as const;
export type TypeSinistre = (typeof TYPE_SINISTRE_VALUES)[number];

/** tools.SIGNAL_NATURE */
export type NatureSignal = "administratif" | "comportemental";

/** Colonnes CSV valant "oui" ou "non". */
export type OuiNon = "oui" | "non";

// =============================================================================
// Referentiel
// =============================================================================

/**
 * Etat du jeu de donnees depose par l'utilisateur.
 *
 * `loaded: false` signifie que l'application n'a AUCUNE donnee. Les fichiers
 * du depot ne servent jamais de repli : ce sont les jeux d'essai des
 * evaluations.
 */
/**
 * Ligne d'un fichier depose qui n'a pas pu etre lue.
 *
 * Ces lignes etaient auparavant supprimees en silence : l'utilisateur
 * travaillait sur un fichier ampute sans aucun moyen de l'apprendre. Le
 * numero est celui du tableur, en-tete compris, pour que la correction soit
 * immediate.
 */
export interface LigneRejetee {
  /** "declarations" ou "contrats". */
  fichier: string;
  ligne: number;
  /** claim_id / policy_id si lisible, sinon chaine vide. */
  identifiant: string;
  raison: string;
}

export interface DatasetState {
  loaded: boolean;
  claims_filename: string | null;
  policies_filename: string | null;
  claims_count: number | null;
  policies_count: number | null;
  loaded_at: string | null;
  /** Declarations dont le contrat est absent du fichier des contrats. */
  claims_sans_contrat: string[];
  /** Lignes des deux fichiers qui n'ont pas pu etre lues. */
  lignes_rejetees: LigneRejetee[];
}

export interface Policy {
  policy_id: string;
  assure: string;
  vehicule: string;
  formule: string;
  date_debut: string;
  date_fin: string;
  franchise_tnd: number;
  garanties: string[];
  exclusions: string[];
}

export interface Claim {
  claim_id: string;
  policy_id: string;
  date_sinistre: string;
  type_sinistre: TypeSinistre;
  /** Version filtree (assainie et encadree, ou remplacee par le placeholder) :
   *  c'est ce que le MODELE recoit. Le texte brut du client n'arrive jamais
   *  ici ; il ne traverse HTTP que via Screening.original_text, pour lecture
   *  humaine. */
  description_client: string;
  blessure: OuiNon;
  constat: OuiNon;
  photos: OuiNon;
  devis_tnd: number;
  tiers_identifie: OuiNon;
  kilometrage_declare: number;
}

export interface Screening {
  verdict: Verdict | null;
  markers_found: string[];
  classifier_available: boolean;
  classifier_called: boolean;
  text_for_model: string;
  /** Texte brut du client, expose pour LECTURE HUMAINE uniquement. Rendu
   *  inerte par React (jamais dangerouslySetInnerHTML) : un gestionnaire peut
   *  le lire, mais le modele ne recoit que `text_for_model` (assaini/encadre,
   *  ou placeholder si le message a ete ecarte). Voir api_models.Screening. */
  original_text: string;
  redacted: boolean;
}

export interface CoverageResult {
  policy_id: string;
  claim_id: string;
  type_sinistre: string;
  garantie_recherchee: string;
  formule: string;
  garantie_applicable: boolean;
  raison: string;
  verification_humaine_recommandee: boolean;
}

export interface RepairBandResult {
  devis_tnd: number;
  bande: "leger" | "modere" | "important" | "majeur";
  borne_inf: number;
  borne_sup: number;
  expertise_obligatoire: boolean;
}

export interface FraudSignalsResult {
  claim_id: string;
  policy_id: string;
  signaux_fraude: string[];
  signaux_non_evaluables: string[];
  details: {
    nature_des_signaux?: Record<string, NatureSignal>;
    [key: string]: unknown;
  };
}

export interface ClaimSummary {
  claim_id: string;
  policy_id: string;
  date_sinistre: string;
  type_sinistre: TypeSinistre;
  blessure: OuiNon;
  devis_tnd: number;
  tiers_identifie: OuiNon;
  assure: string | null;
  vehicule: string | null;
  formule: string | null;
  injection_markers_found: string[];
  /** Repere de lecture calcule cote Python. Voir URGENCE_VALUES ci-dessus :
   *  ce n'est pas TriageOutput.priorite. */
  urgence_estimee: Urgence;
  /** Ensemble ferme cote Python (urgence.MOTIF_*), type large ici avec repli
   *  sur humanize(), comme signaux_fraude. */
  urgence_motifs: string[];
}

export interface ClaimDetail {
  claim: Claim;
  policy: Policy;
  coverage: CoverageResult;
  repair_band: RepairBandResult;
  fraud_signals: FraudSignalsResult;
  screening: Screening;
}

/**
 * Un modele proposable pour l'analyse d'un dossier. Source de verite :
 * GET /api/models (backend config.AVAILABLE_MODELS), qui valide aussi le choix
 * renvoye au lancement. `default` marque celui applique a defaut de choix.
 */
export interface ModelOption {
  id: string;
  label: string;
  default: boolean;
}

// =============================================================================
// Triage
// =============================================================================

/** Le contrat de sortie de data/contrat_sortie.md, tel que le modele est cense
 *  le produire. Il peut arriver malforme : c'est ce que mesure
 *  `validation_errors`, et l'interface doit afficher les deux. */
export interface TriageOutput {
  claim_id: string;
  triage: Triage;
  priorite: Priorite;
  garantie_applicable: boolean;
  pieces_manquantes: string[];
  signaux_fraude: string[];
  fourchette_reparation_tnd: { min: number; max: number };
  prochaine_action: string;
  message_client: string;
  validation_humaine_requise: boolean;
}

export interface ToolCall {
  tool: string;
  input: Record<string, unknown>;
  output: Record<string, unknown>;
}

export interface Usage {
  input_tokens?: number;
  output_tokens?: number;
  cache_creation_input_tokens?: number;
  cache_read_input_tokens?: number;
}

export interface TriageResult {
  claim_id: string;
  output: TriageOutput | null;
  validation_errors: string[];
  tool_call_trace: ToolCall[];
  usage: Usage;
  error: string | null;
  raw_output: string | null;
  /** Modele effectivement utilise (backend api._valider_modele). */
  model: string | null;
  /** Cout en USD de CETTE execution, filtre anti-injection compris et au tarif
   *  de chaque modele (backend agent._run_cost_usd). Renseigne aussi sur les
   *  chemins d'echec : une analyse interrompue a quand meme ete facturee.
   *  C'est ce montant que lib/cumulative-cost.ts additionne. */
  cost_usd: number;
}

export interface RulesDocument {
  name: string;
  content: string;
}

export interface Rules {
  documents: RulesDocument[];
}

// =============================================================================
// Evenements SSE (backend/src/api.py + agent._emit)
// =============================================================================

export type StreamEvent =
  | { type: "stream_open"; claim_id: string; started_at: string }
  | { type: "run_started"; claim_id: string; model: string }
  | { type: "turn_started"; turn: number }
  | { type: "text_delta"; text: string }
  | { type: "tool_use"; turn: number; tool: string; input: Record<string, unknown> }
  | { type: "tool_result"; turn: number; tool: string; output: Record<string, unknown> }
  | { type: "turn_completed"; turn: number; usage: Usage }
  | {
      type: "result";
      claim_id: string;
      output: TriageOutput | null;
      validation_errors: string[];
      tool_call_trace: ToolCall[];
      usage: Usage;
      model: string;
      /** Voir TriageResult.cost_usd. */
      cost_usd: number;
    }
  // `run_error` et non `error` : cote navigateur, EventSource reserve deja le
  // nom "error" a ses pannes de transport. Voir _EVENT_NAME_OVERRIDES dans
  // backend/src/api.py.
  // `cost_usd` est present ici aussi : un triage qui echoue apres plusieurs
  // tours a deja ete facture, et l'omettre sous-estimerait le cumul.
  | { type: "run_error"; message: string; raw_output?: string; cost_usd?: number }
  | { type: "done" };
