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
 *
 * Les libelles s'adressent a un gestionnaire de sinistres : pas de nom de
 * champ, pas de vocabulaire technique.
 */

import {
  CircleCheck,
  CircleSlash,
  FileQuestionMark,
  Microscope,
  ShieldAlert,
  type LucideIcon,
} from "lucide-react";

import type { Priorite, Triage, TypeSinistre, Urgence } from "@/lib/types";

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
// Decision de triage (contrat_sortie.md)
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
// Urgence estimee (backend/src/urgence.py)
// =============================================================================

/**
 * TROISIEME FORME, et c'est tout l'enjeu.
 *
 * Le triage est un badge plein a icone ; la priorite, un badge contour a
 * pastille ; l'urgence n'est pas un badge du tout, c'est une jauge a quatre
 * segments. Elle ne dit pas la meme chose : elle existe AVANT toute analyse,
 * gratuitement, et la priorite proposee ensuite par l'agent peut differer.
 *
 * Les libelles ne reprennent donc jamais le mot "Priorite". Sur les quatre
 * niveaux, seul "normale" est un mot commun aux deux echelles, et c'est celui
 * sur lequel personne n'agit.
 */
export interface UrgenceMeta {
  label: string;
  /** Segments allumes, de 1 a 4. Un statut ne se lit jamais a la seule
   *  couleur : ici elle est doublee d'un decompte visible. */
  segments: number;
  /** Meme palette que PRIORITE_META : une seule echelle de couleur dans le
   *  produit, meme quand les grandeurs different. */
  dotClassName: string;
}

export const URGENCE_META: Record<Urgence, UrgenceMeta> = {
  basse: { label: "Urgence basse", segments: 1, dotClassName: "bg-muted-foreground/50" },
  normale: { label: "Urgence normale", segments: 2, dotClassName: "bg-muted-foreground" },
  haute: { label: "Urgence haute", segments: 3, dotClassName: "bg-warning" },
  critique: { label: "Urgence critique", segments: 4, dotClassName: "bg-destructive" },
};

/** Motifs produits par urgence.MOTIF_*. Repli sur humanize() comme
 *  signalLabel : ce vocabulaire peut evoluer cote Python avant ici. */
const URGENCE_MOTIF_LABELS: Record<string, string> = {
  blessure_declaree: "Blessure déclarée",
  devis_au_dessus_du_seuil: "Devis au-dessus du seuil d'expertise",
  message_client_signale: "Message du client signalé",
  montant_faible: "Montant faible",
  montant_inconnu: "Montant non renseigné",
};

export function urgenceMotifLabel(motif: string): string {
  return URGENCE_MOTIF_LABELS[motif] ?? humanize(motif);
}

// =============================================================================
// Points de vigilance
// =============================================================================

/** Ensemble ferme produit par tools.detect_fraud_signals. Le modele peut
 *  toutefois écrire ses propres chaînes dans `signaux_fraude` : d'où le
 *  repli sur une simple mise en forme. */
const SIGNAL_LABELS: Record<string, string> = {
  incoherence_police_date_hors_couverture: "Date hors période de couverture",
  sinistre_juste_apres_ouverture_police: "Sinistre juste après l'ouverture du contrat",
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
 *  config.EXPERTISE_REQUIRED_THRESHOLD_TND). Repris ici uniquement pour
 *  l'affichage : le calcul metier reste cote Python. */
export const SEUIL_EXPERTISE_TND = 5000;

const NUMBER_FORMAT = new Intl.NumberFormat("fr-FR");

export function formatTnd(amount: number): string {
  return `${NUMBER_FORMAT.format(amount)} TND`;
}

/**
 * Date ET heure, pour un horodatage complet (ISO 8601 avec fuseau).
 *
 * Distincte de formatDate, qui recoit une date SEULE (`2026-07-18`) venue des
 * fichiers deposes et lui ajoute une heure de minuit. Passer un horodatage
 * complet a formatDate donnerait une date invalide.
 */
export function formatDateHeure(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat("fr-FR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

/**
 * Un cout en dollars. Quatre decimales, comme les rapports du backend
 * (`[cost] $0.0043`) : une analyse coute quelques milliemes de dollar, et deux
 * decimales afficheraient "0,00 $US" tant que le total n'a pas depasse le
 * demi-centime.
 */
const FORMAT_USD = new Intl.NumberFormat("fr-FR", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 4,
  maximumFractionDigits: 4,
});

export function formatUsd(usd: number): string {
  return FORMAT_USD.format(usd);
}

export function formatDate(iso: string): string {
  const date = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat("fr-FR", { dateStyle: "medium" }).format(date);
}
