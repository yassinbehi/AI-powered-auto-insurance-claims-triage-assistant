/**
 * Langage de statut de l'application : source unique des libelles, des tons et
 * des icones.
 *
 * REGLE : aucun composant ne code en dur un libelle francais ni une couleur de
 * statut. Tout passe par ce fichier, pour que renommer une categorie ou
 * reequilibrer la palette soit une modification d'un seul endroit.
 *
 * DEUX PRINCIPES DE LECTURE :
 *
 * 1. Le triage et la priorite ont des FORMES differentes, pas seulement des
 *    couleurs differentes : badge plein pour le triage, badge contour avec
 *    pastille pour la priorite. Les deux sont souvent cote a cote, et deux
 *    badges pleins de couleurs voisines se disputeraient l'attention.
 *
 * 2. Chaque statut porte une icone EN PLUS de sa couleur. Un statut ne doit
 *    jamais se lire uniquement a la couleur : daltonisme, impression en noir
 *    et blanc de la demo, contraste degrade sur videoprojecteur.
 */

import {
  CircleCheck,
  CircleSlash,
  FileQuestionMark,
  FileText,
  Microscope,
  ShieldAlert,
  ShieldCheck,
  ShieldOff,
  TriangleAlert,
  UserSearch,
  type LucideIcon,
} from "lucide-react";

import type { NatureSignal, Priorite, Triage, TypeSinistre, Verdict } from "@/lib/types";

/** Tons disponibles pour StatusBadge. `destructiveSoft` est un contour rouge
 *  et non un aplat : il exprime un refus de prise en charge, pas une alerte. */
export type Tone =
  | "neutral"
  | "success"
  | "warning"
  | "info"
  | "destructive"
  | "destructiveSoft";

export interface StatusMeta {
  label: string;
  tone: Tone;
  Icon: LucideIcon;
}

// =============================================================================
// Triage (contrat_sortie.md)
// =============================================================================

export const TRIAGE_META: Record<Triage, StatusMeta> = {
  traitement_standard: {
    label: "Traitement standard",
    tone: "success",
    Icon: CircleCheck,
  },
  pieces_manquantes: {
    label: "Pièces manquantes",
    tone: "warning",
    Icon: FileQuestionMark,
  },
  expertise_requise: {
    label: "Expertise requise",
    tone: "info",
    Icon: Microscope,
  },
  suspicion_fraude: {
    label: "Suspicion de fraude",
    tone: "destructive",
    Icon: ShieldAlert,
  },
  hors_garantie: {
    label: "Hors garantie",
    tone: "destructiveSoft",
    Icon: CircleSlash,
  },
};

// =============================================================================
// Priorite
// =============================================================================

export interface PrioriteMeta {
  label: string;
  /** Classe de la pastille. Toujours un token, jamais une couleur litterale. */
  dotClassName: string;
}

export const PRIORITE_META: Record<Priorite, PrioriteMeta> = {
  basse: { label: "Priorité basse", dotClassName: "bg-muted-foreground/50" },
  normale: { label: "Priorité normale", dotClassName: "bg-muted-foreground" },
  haute: { label: "Priorité haute", dotClassName: "bg-warning" },
  critique: { label: "Priorité critique", dotClassName: "bg-destructive" },
};

// =============================================================================
// Verdict du filtre anti-injection (guard.py)
// =============================================================================

/** Cle interne pour l'absence de verdict. Le backend renvoie `null` quand la
 *  couche [2] n'a pas ete executee : ce n'est pas un feu vert, et l'interface
 *  ne doit surtout pas le presenter comme un SAFE. */
export const VERDICT_NON_EVALUE = "NON_EVALUE" as const;

export type VerdictKey = Verdict | typeof VERDICT_NON_EVALUE;

export const VERDICT_META: Record<VerdictKey, StatusMeta & { hint: string }> = {
  SAFE: {
    label: "Texte sain",
    tone: "success",
    Icon: ShieldCheck,
    hint: "Les trois couches du filtre ont été exécutées : aucune tentative d'instruction détectée.",
  },
  SUSPECT: {
    label: "Texte suspect",
    tone: "warning",
    Icon: TriangleAlert,
    hint: "Formulation ambiguë, ou classifieur indisponible. Le filtre se ferme par défaut plutôt que de conclure au vert.",
  },
  INJECTION: {
    label: "Injection détectée",
    tone: "destructive",
    Icon: ShieldAlert,
    hint: "Une instruction adressée à l'assistant a été détectée. Le texte a été retiré avant d'atteindre le modèle de triage.",
  },
  [VERDICT_NON_EVALUE]: {
    label: "Couche 2 non exécutée",
    tone: "neutral",
    Icon: ShieldOff,
    hint: "Seules les couches déterministes ont tourné. Sans le classifieur, rien n'atteste que ce texte est sain — c'est une absence d'analyse, pas un feu vert.",
  },
};

export function verdictKey(verdict: Verdict | null): VerdictKey {
  return verdict ?? VERDICT_NON_EVALUE;
}

// =============================================================================
// Signaux de fraude (tools.SIGNAL_NATURE)
// =============================================================================

export const NATURE_META: Record<NatureSignal, { label: string; Icon: LucideIcon }> = {
  administratif: { label: "Administratif", Icon: FileText },
  comportemental: { label: "Comportemental", Icon: UserSearch },
};

/** Ensemble ferme produit par tools.detect_fraud_signals. Le modele peut
 *  toutefois écrire ses propres chaînes dans `signaux_fraude` : d'où le
 *  repli sur une simple mise en forme. */
const SIGNAL_LABELS: Record<string, string> = {
  incoherence_police_date_hors_couverture: "Date hors période de couverture",
  sinistre_juste_apres_ouverture_police: "Sinistre juste après l'ouverture de la police",
  vol_recent: "Vol récent",
  montant_eleve: "Montant élevé",
  pieces_insuffisantes: "Pièces insuffisantes",
  achat_recent_suivi_perte_declaree: "Achat récent suivi d'une perte déclarée",
};

export function signalLabel(signal: string): string {
  return SIGNAL_LABELS[signal] ?? humanize(signal);
}

/** `sinistre_juste_apres_ouverture` -> `Sinistre juste apres ouverture`. */
export function humanize(value: string): string {
  const words = value.replace(/_/g, " ").trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

// =============================================================================
// Referentiel
// =============================================================================

export const TYPE_SINISTRE_LABEL: Record<TypeSinistre, string> = {
  collision: "Collision",
  bris_glace: "Bris de glace",
  vol: "Vol",
  incendie: "Incendie",
  rc_tiers: "RC tiers",
};

export const FORMULE_LABEL: Record<string, string> = {
  rc_simple: "RC simple",
  tiers_plus: "Tiers plus",
  tous_risques: "Tous risques",
  flotte_pro: "Flotte pro",
};

/** Les 5 tools de backend/src/tools.py. */
export const TOOL_LABEL: Record<string, string> = {
  get_claim: "Lire la déclaration",
  get_policy: "Lire la police",
  check_coverage: "Vérifier la couverture",
  estimate_repair_band: "Estimer la réparation",
  detect_fraud_signals: "Relever les signaux",
};

export const BANDE_META: Record<string, { label: string; tone: Tone }> = {
  leger: { label: "Léger", tone: "success" },
  modere: { label: "Modéré", tone: "neutral" },
  important: { label: "Important", tone: "warning" },
  majeur: { label: "Majeur", tone: "destructive" },
};

// =============================================================================
// Formatage
// =============================================================================

/** Seuil d'expertise obligatoire (regles_sinistres.md, via
 *  config.EXPERTISE_REQUIRED_THRESHOLD_TND). Repris ici uniquement pour le
 *  reperage visuel : le calcul metier reste cote Python. */
export const SEUIL_EXPERTISE_TND = 5000;

/** Plafond de longueur de message_client impose par le system prompt. */
export const MESSAGE_CLIENT_MAX_MOTS = 40;

const NUMBER_FORMAT = new Intl.NumberFormat("fr-FR");

export function formatTnd(amount: number): string {
  return `${NUMBER_FORMAT.format(amount)} TND`;
}

export function formatDate(iso: string): string {
  const date = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat("fr-FR", { dateStyle: "medium" }).format(date);
}

export function countWords(text: string): number {
  return text.trim().split(/\s+/).filter(Boolean).length;
}
