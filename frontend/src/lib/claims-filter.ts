/**
 * Filtrage de la file d'attente.
 *
 * Filtrer, c'est choisir quelles lignes montrer : une decision d'AFFICHAGE,
 * pas une regle metier. C'est ce qui autorise ce code a vivre cote frontend
 * alors que le projet tient par ailleurs tout calcul metier cote Python. Le
 * seul jugement de cet ecran - l'urgence estimee - est calcule par
 * backend/src/urgence.py et arrive deja fait dans la charge utile ; on ne fait
 * ici que comparer des valeurs.
 *
 * Module pur : aucun React, aucun JSX, aucune lecture d'URL. Il recoit un
 * objet de parametres deja lu et rend un tableau filtre, ce qui le rend
 * testable et utilisable depuis un Server Component.
 *
 * PRINCIPE DE LECTURE DES PARAMETRES : une valeur inconnue est IGNOREE, pas
 * appliquee. `?urgence=nimportequoi` veut dire "pas de filtre d'urgence", et
 * non "aucun resultat" - un lien copie-colle de travers doit degrader vers la
 * liste complete, jamais vers un ecran vide inexplicable.
 */

import { FORMULE_LABEL } from "@/lib/status";
import { normaliser } from "@/lib/utils";
import {
  TYPE_SINISTRE_VALUES,
  URGENCE_VALUES,
  type ClaimSummary,
  type TypeSinistre,
  type Urgence,
} from "@/lib/types";

export interface FiltresFile {
  /** Recherche libre : identifiant, assure, vehicule. */
  q: string;
  /** Bornes INCLUSES sur date_sinistre, au format ISO YYYY-MM-DD. */
  du: string | null;
  au: string | null;
  urgence: Urgence | null;
  type: TypeSinistre | null;
  formule: string | null;
}

export const FILTRES_VIDES: FiltresFile = {
  q: "",
  du: null,
  au: null,
  urgence: null,
  type: null,
  formule: null,
};

/** Cles de recherche telles qu'elles apparaissent dans l'URL. */
export const PARAM_KEYS = ["q", "du", "au", "urgence", "type", "formule"] as const;

type ParamsBruts = Record<string, string | string[] | undefined>;

const FORMAT_ISO = /^\d{4}-\d{2}-\d{2}$/;

/** Un meme parametre peut arriver plusieurs fois dans une URL. On retient le
 *  premier plutot que de concatener silencieusement. */
function premiere(valeur: string | string[] | undefined): string {
  if (Array.isArray(valeur)) return valeur[0] ?? "";
  return valeur ?? "";
}

function dansLaListe<T extends string>(
  valeur: string,
  autorisees: readonly T[],
): T | null {
  return (autorisees as readonly string[]).includes(valeur) ? (valeur as T) : null;
}

function dateValide(valeur: string): string | null {
  return FORMAT_ISO.test(valeur) ? valeur : null;
}

export function lireFiltres(params: ParamsBruts): FiltresFile {
  const formule = premiere(params.formule);

  return {
    q: premiere(params.q).trim(),
    du: dateValide(premiere(params.du)),
    au: dateValide(premiere(params.au)),
    urgence: dansLaListe(premiere(params.urgence), URGENCE_VALUES),
    type: dansLaListe(premiere(params.type), TYPE_SINISTRE_VALUES),
    // La formule reste une chaine libre sur le fil (c'est une colonne de CSV
    // fournie par l'utilisateur), mais on ne propose a filtrer que celles
    // qu'on sait nommer.
    formule: formule in FORMULE_LABEL ? formule : null,
  };
}

export function filtresActifs(filtres: FiltresFile): number {
  return [
    filtres.q !== "",
    filtres.du !== null,
    filtres.au !== null,
    filtres.urgence !== null,
    filtres.type !== null,
    filtres.formule !== null,
  ].filter(Boolean).length;
}

/** Vrai quand la borne de debut est posterieure a la borne de fin. On filtre
 *  quand meme (le resultat sera vide) : l'interface le signale plutot que de
 *  corriger en douce un choix de l'utilisateur. */
export function datesIncoherentes(filtres: FiltresFile): boolean {
  return filtres.du !== null && filtres.au !== null && filtres.du > filtres.au;
}

function correspondAuTexte(claim: ClaimSummary, q: string): boolean {
  const cible = normaliser(
    [claim.claim_id, claim.assure ?? "", claim.vehicule ?? ""].join(" "),
  );
  // Termes combines en ET : "peugeot benali" doit trouver la ligne qui porte
  // les deux, dans n'importe quel ordre.
  return normaliser(q)
    .split(/\s+/)
    .filter(Boolean)
    .every((terme) => cible.includes(terme));
}

// ---------------------------------------------------------------------------
// Tri
// ---------------------------------------------------------------------------
// La file est un outil de TRIAGE : par defaut le plus urgent remonte en tete,
// sans que personne ait a le demander. Le tri, comme les filtres, est une
// decision d'affichage - il vit dans l'URL et se recopie avec le lien.

export const TRI_CHAMPS = ["urgence", "devis", "date"] as const;
export type TriChamp = (typeof TRI_CHAMPS)[number];
export type TriSens = "asc" | "desc";

export interface TriFile {
  champ: TriChamp;
  sens: TriSens;
}

/** Urgence decroissante : critique d'abord. C'est l'ordre attendu d'une file
 *  de traitement, et celui vers lequel toute URL incomplete degrade. */
export const TRI_DEFAUT: TriFile = { champ: "urgence", sens: "desc" };

export function lireTri(params: ParamsBruts): TriFile {
  const champ = dansLaListe(premiere(params.tri), TRI_CHAMPS);
  if (champ === null) return TRI_DEFAUT;
  const sens: TriSens = premiere(params.sens) === "asc" ? "asc" : "desc";
  return { champ, sens };
}

function comparer(a: ClaimSummary, b: ClaimSummary, champ: TriChamp): number {
  switch (champ) {
    case "urgence":
      // Rang ordinal : l'index dans URGENCE_VALUES va de basse (0) a critique.
      return (
        URGENCE_VALUES.indexOf(a.urgence_estimee) -
        URGENCE_VALUES.indexOf(b.urgence_estimee)
      );
    case "devis":
      return a.devis_tnd - b.devis_tnd;
    case "date":
      // Chaines ISO : comparaison lexicographique correcte, sans objet Date.
      return a.date_sinistre < b.date_sinistre
        ? -1
        : a.date_sinistre > b.date_sinistre
          ? 1
          : 0;
  }
}

export function trierClaims(claims: ClaimSummary[], tri: TriFile): ClaimSummary[] {
  const facteur = tri.sens === "asc" ? 1 : -1;
  // Copie : sort() modifie en place, et la liste vient d'un fetch qu'on ne veut
  // pas muter. Depart d'egalite stable par identifiant, pour un ordre
  // reproductible d'un rendu a l'autre.
  return [...claims].sort((a, b) => {
    const base = comparer(a, b, tri.champ) * facteur;
    return base !== 0 ? base : a.claim_id.localeCompare(b.claim_id);
  });
}

export function filtrerClaims(
  claims: ClaimSummary[],
  filtres: FiltresFile,
): ClaimSummary[] {
  return claims.filter((claim) => {
    if (filtres.q !== "" && !correspondAuTexte(claim, filtres.q)) return false;

    // Comparaison de chaines ISO : lexicographiquement correcte sur
    // YYYY-MM-DD, et sans objet Date, donc sans decalage de fuseau horaire.
    if (filtres.du !== null && claim.date_sinistre < filtres.du) return false;
    if (filtres.au !== null && claim.date_sinistre > filtres.au) return false;

    if (filtres.urgence !== null && claim.urgence_estimee !== filtres.urgence) {
      return false;
    }
    if (filtres.type !== null && claim.type_sinistre !== filtres.type) return false;

    // Un sinistre dont le contrat manque au fichier a `formule: null`. Il
    // n'appartient a aucune formule : il sort des que ce filtre est pose.
    if (filtres.formule !== null && claim.formule !== filtres.formule) return false;

    return true;
  });
}
