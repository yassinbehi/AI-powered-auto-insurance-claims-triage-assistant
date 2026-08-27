/**
 * Recherche et tri de l'historique des analyses.
 *
 * Meme parti pris que lib/claims-filter.ts, et pour les memes raisons :
 * module PUR - aucun React, aucun JSX, aucune lecture d'URL. Il recoit des
 * parametres deja lus et rend un tableau, ce qui le rend utilisable depuis un
 * Server Component. Chercher et trier sont des decisions d'AFFICHAGE, pas des
 * regles metier : c'est ce qui autorise ce code a vivre cote frontend.
 *
 * L'ETAT VIT DANS L'URL. Un historique cherche et trie se copie-colle, se met
 * en favori, et les boutons Precedent / Suivant du navigateur y fonctionnent.
 *
 * PRINCIPE DE LECTURE DES PARAMETRES, repris de la file : une valeur inconnue
 * est IGNOREE, pas appliquee. `?tri=nimportequoi` veut dire "tri par defaut",
 * jamais "aucun resultat" - un lien copie de travers doit degrader vers la
 * liste complete plutot que vers un ecran vide inexplicable.
 */

import { PRIORITE_META, TRIAGE_META } from "@/lib/status";
import type { AnalyseResume } from "@/lib/types";
import { normaliser } from "@/lib/utils";

type ParamsBruts = Record<string, string | string[] | undefined>;

/** Un meme parametre peut arriver plusieurs fois dans une URL. On retient le
 *  premier plutot que de concatener silencieusement. */
function premiere(valeur: string | string[] | undefined): string {
  if (Array.isArray(valeur)) return valeur[0] ?? "";
  return valeur ?? "";
}

// =============================================================================
// Recherche
// =============================================================================

export function lireRecherche(params: ParamsBruts): string {
  return premiere(params.q).trim();
}

/**
 * Le texte sur lequel porte la recherche, pour UNE analyse.
 *
 * On cherche sur ce que l'ecran MONTRE, pas sur les valeurs brutes du
 * backend : taper "pieces manquantes" doit trouver la ligne qui affiche
 * « Pièces manquantes », alors que la donnee vaut `pieces_manquantes`. Les
 * deux formes sont donc dans la cible, avec le libelle d'echec pour les
 * analyses qui n'ont pas abouti.
 */
function texteCherchable(analyse: AnalyseResume): string {
  const morceaux = [
    analyse.claim_id,
    analyse.dataset_nom,
    analyse.model,
    analyse.triage ?? "",
    analyse.triage ? (TRIAGE_META[analyse.triage]?.label ?? "") : "",
    analyse.priorite ?? "",
    analyse.priorite ? (PRIORITE_META[analyse.priorite]?.label ?? "") : "",
    // Les echecs doivent se trouver eux aussi : c'est meme la recherche la
    // plus probable sur cet ecran ("qu'est-ce qui a rate ?").
    analyse.erreur ? `echec n'a pas abouti ${analyse.erreur}` : "",
  ];
  return normaliser(morceaux.join(" "));
}

export function filtrerAnalyses(analyses: AnalyseResume[], q: string): AnalyseResume[] {
  if (q === "") return analyses;

  // Termes combines en ET : "CLM-101 fraude" doit trouver la ligne qui porte
  // les deux, dans n'importe quel ordre.
  const termes = normaliser(q).split(/\s+/).filter(Boolean);
  if (termes.length === 0) return analyses;

  return analyses.filter((analyse) => {
    const cible = texteCherchable(analyse);
    return termes.every((terme) => cible.includes(terme));
  });
}

// =============================================================================
// Tri
// =============================================================================

export const TRI_CHAMPS = ["date", "cout", "dossier", "jeu"] as const;
export type TriChampAnalyse = (typeof TRI_CHAMPS)[number];
export type TriSens = "asc" | "desc";

export interface TriAnalyses {
  champ: TriChampAnalyse;
  sens: TriSens;
}

/** La plus recente d'abord : c'est l'ordre attendu d'un historique, et celui
 *  vers lequel toute URL incomplete degrade. */
export const TRI_DEFAUT: TriAnalyses = { champ: "date", sens: "desc" };

export function lireTri(params: ParamsBruts): TriAnalyses {
  const champ = premiere(params.tri);
  if (!(TRI_CHAMPS as readonly string[]).includes(champ)) return TRI_DEFAUT;
  const sens: TriSens = premiere(params.sens) === "asc" ? "asc" : "desc";
  return { champ: champ as TriChampAnalyse, sens };
}

function comparer(a: AnalyseResume, b: AnalyseResume, champ: TriChampAnalyse): number {
  switch (champ) {
    case "date":
      // Horodatages ISO 8601 tous produits par le meme backend, donc au meme
      // format et dans le meme fuseau : la comparaison lexicographique suffit,
      // sans construire deux objets Date par comparaison.
      return a.analyse_le < b.analyse_le ? -1 : a.analyse_le > b.analyse_le ? 1 : 0;
    case "cout":
      return a.cost_usd - b.cost_usd;
    case "dossier":
      return a.claim_id.localeCompare(b.claim_id, "fr");
    case "jeu":
      return a.dataset_nom.localeCompare(b.dataset_nom, "fr");
  }
}

export function trierAnalyses(
  analyses: AnalyseResume[],
  tri: TriAnalyses,
): AnalyseResume[] {
  const facteur = tri.sens === "asc" ? 1 : -1;
  // Copie : sort() modifie en place, et la liste vient d'un fetch qu'on ne
  // veut pas muter. Depart d'egalite par identifiant DECROISSANT, pour que
  // deux analyses du meme dossier restent dans l'ordre ou elles ont eu lieu.
  return [...analyses].sort((a, b) => {
    const base = comparer(a, b, tri.champ) * facteur;
    return base !== 0 ? base : b.id - a.id;
  });
}
