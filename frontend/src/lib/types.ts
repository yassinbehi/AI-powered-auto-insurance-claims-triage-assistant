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

/** guard.ALLOWED_VERDICTS. `null` = couche [2] non executee, ce qui n'est PAS
 *  un verdict favorable. */
export type Verdict = "SAFE" | "SUSPECT" | "INJECTION";

export type TypeSinistre =
  | "collision"
  | "bris_glace"
  | "vol"
  | "incendie"
  | "rc_tiers";

/** tools.SIGNAL_NATURE */
export type NatureSignal = "administratif" | "comportemental";

/** Colonnes CSV valant "oui" ou "non". */
export type OuiNon = "oui" | "non";

// =============================================================================
// Referentiel
// =============================================================================

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
  /** Version filtree (assainie et encadree, ou remplacee par le placeholder).
   *  Le texte brut du client ne franchit jamais la frontiere HTTP. */
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
}

export interface ClaimDetail {
  claim: Claim;
  policy: Policy;
  coverage: CoverageResult;
  repair_band: RepairBandResult;
  fraud_signals: FraudSignalsResult;
  screening: Screening;
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
    }
  // `run_error` et non `error` : cote navigateur, EventSource reserve deja le
  // nom "error" a ses pannes de transport. Voir _EVENT_NAME_OVERRIDES dans
  // backend/src/api.py.
  | { type: "run_error"; message: string; raw_output?: string }
  | { type: "done" };
