"use client";

import * as React from "react";

/**
 * Cout CUMULE des analyses, conserve dans le navigateur.
 *
 * Ce n'est pas le cout d'une execution : chaque triage renvoie le sien
 * (`cost_usd`, calcule cote Python dans agent._run_cost_usd, filtre
 * anti-injection compris), et ce module en tient la somme depuis la premiere
 * analyse. Le total survit donc au rechargement de la page et a la fermeture
 * du navigateur, ce que ne ferait aucun etat React.
 *
 * PORTEE : localStorage est propre a UN navigateur et a UN profil. Le total
 * affiche est celui des analyses lancees depuis ce poste, pas la facture de
 * l'organisation - le libelle a l'ecran doit le dire, sans quoi le chiffre
 * serait lu comme une consommation globale. Un compteur partage se tiendrait
 * cote serveur ; ce n'est pas ce qui est demande ici.
 *
 * Le stockage est volontairement tolerant a la panne : navigation privee,
 * quota depasse, stockage desactive par une politique d'entreprise. Dans tous
 * ces cas la lecture rend un total vide et l'ecriture est perdue en silence -
 * jamais au prix d'une exception qui interromprait un triage deja paye.
 */

/** Le suffixe de version permet d'abandonner un format devenu incompatible
 *  sans avoir a lire l'ancien : une nouvelle cle repart simplement de zero. */
const CLE = "tsa.cout-cumule.v1";

export interface CoutCumule {
  /** Somme en USD, arrondie a 6 decimales (voir `arrondir`). */
  total_usd: number;
  /** Nombre d'analyses comptees dans ce total. */
  analyses: number;
  /** ISO 8601, ou null tant qu'aucune analyse n'a ete comptee. */
  maj_le: string | null;
}

const VIDE: CoutCumule = { total_usd: 0, analyses: 0, maj_le: null };

/**
 * Six decimales : une analyse coute de l'ordre du millieme de dollar, et
 * additionner des flottants sans arrondir ferait deriver le total vers des
 * artefacts du type 0.030000000000000002. L'affichage n'en montre que quatre.
 */
function arrondir(usd: number): number {
  return Math.round(usd * 1_000_000) / 1_000_000;
}

// =============================================================================
// Stockage
// =============================================================================

/** Instantane memorise. useSyncExternalStore exige qu'une lecture inchangee
 *  rende la MEME reference : relire et reparser le JSON a chaque rendu
 *  produirait un objet neuf a chaque fois, donc une boucle de rendus. */
let instantaneMemorise: CoutCumule | null = null;

const abonnes = new Set<() => void>();

function prevenirLesAbonnes(): void {
  for (const rappel of abonnes) rappel();
}

/** Une ecriture faite dans un AUTRE onglet. `key === null` signale un
 *  localStorage vide en bloc (clear()), qui nous concerne aussi. */
function surStorage(evenement: StorageEvent): void {
  if (evenement.key !== null && evenement.key !== CLE) return;
  instantaneMemorise = null;
  prevenirLesAbonnes();
}

function lireDepuisLeStockage(): CoutCumule {
  if (typeof window === "undefined") return VIDE;

  try {
    const brut = window.localStorage.getItem(CLE);
    if (!brut) return VIDE;

    // Contenu ecrit par une version anterieure, tronque, ou modifie a la main
    // dans les outils du navigateur : on valide au lieu de faire confiance.
    const valeur = JSON.parse(brut) as Partial<CoutCumule> | null;
    const total = Number(valeur?.total_usd);
    if (!Number.isFinite(total) || total < 0) return VIDE;

    const analyses = Number(valeur?.analyses);
    return {
      total_usd: total,
      analyses: Number.isFinite(analyses) && analyses > 0 ? Math.floor(analyses) : 0,
      maj_le: typeof valeur?.maj_le === "string" ? valeur.maj_le : null,
    };
  } catch {
    return VIDE;
  }
}

function ecrireDansLeStockage(etat: CoutCumule): CoutCumule {
  instantaneMemorise = etat;

  if (typeof window !== "undefined") {
    try {
      window.localStorage.setItem(CLE, JSON.stringify(etat));
    } catch {
      // Stockage indisponible ou plein. Le compteur reste juste pour cette
      // page et repartira de zero au rechargement : c'est une degradation
      // acceptable, contrairement a une exception au milieu d'un triage.
    }
  }

  prevenirLesAbonnes();
  return etat;
}

// =============================================================================
// API du module
// =============================================================================

/** Lecture synchrone, hors composant React. */
export function lireCoutCumule(): CoutCumule {
  if (instantaneMemorise === null) instantaneMemorise = lireDepuisLeStockage();
  return instantaneMemorise;
}

/**
 * Ajoute le cout d'UNE analyse au total et le persiste.
 *
 * Un cout nul, absent ou aberrant est ignore plutot que compte comme une
 * analyse a 0 $ : le compteur d'analyses doit rester lisible.
 */
export function ajouterCout(usd: number | undefined | null): CoutCumule {
  if (typeof usd !== "number" || !Number.isFinite(usd) || usd <= 0) {
    return lireCoutCumule();
  }

  const actuel = lireCoutCumule();
  return ecrireDansLeStockage({
    total_usd: arrondir(actuel.total_usd + usd),
    analyses: actuel.analyses + 1,
    maj_le: new Date().toISOString(),
  });
}

/** Remet le compteur a zero et efface la valeur persistee. */
export function reinitialiserCoutCumule(): CoutCumule {
  if (typeof window !== "undefined") {
    try {
      window.localStorage.removeItem(CLE);
    } catch {
      // Meme raisonnement que ci-dessus : l'etat en memoire fait foi.
    }
  }
  instantaneMemorise = VIDE;
  prevenirLesAbonnes();
  return VIDE;
}

function sAbonner(rappel: () => void): () => void {
  abonnes.add(rappel);
  if (abonnes.size === 1 && typeof window !== "undefined") {
    window.addEventListener("storage", surStorage);
  }

  return () => {
    abonnes.delete(rappel);
    if (abonnes.size === 0 && typeof window !== "undefined") {
      window.removeEventListener("storage", surStorage);
    }
  };
}

/**
 * Le total cumule, tenu a jour.
 *
 * useSyncExternalStore et non useState + useEffect : le stockage est une
 * source de verite EXTERIEURE a React, partagee par plusieurs onglets et
 * modifiee par du code hors composant (le flux SSE). Le troisieme argument
 * est l'instantane rendu cote serveur - un total vide, puisque le serveur
 * n'a acces a aucun localStorage. React remplace ce total par la vraie valeur
 * juste apres l'hydratation, sans avertissement d'ecart.
 */
export function useCoutCumule(): CoutCumule {
  return React.useSyncExternalStore(sAbonner, lireCoutCumule, () => VIDE);
}

/** Rien a surveiller : l'etat "hydrate" ne change qu'une fois, et c'est React
 *  qui le fait changer en passant de l'instantane serveur au client. */
const AUCUN_ABONNEMENT = () => () => {};

/**
 * `false` pendant le rendu serveur et l'hydratation, `true` ensuite.
 *
 * Meme mecanique que ci-dessus, et pour la meme raison : un drapeau pose dans
 * un useEffect declencherait un rendu en cascade a chaque montage (c'est aussi
 * ce que refuse la regle react-hooks/set-state-in-effect). Sert a ne pas
 * afficher un montant que le serveur ne peut pas connaitre.
 */
export function useHydrate(): boolean {
  return React.useSyncExternalStore(
    AUCUN_ABONNEMENT,
    () => true,
    () => false,
  );
}

// =============================================================================
// Affichage
// =============================================================================

/** Reexport : le formatage vit dans lib/status.ts, partage avec la page des
 *  analyses. Deux formateurs afficheraient tot ou tard deux montants
 *  differents pour la meme somme. */
export { formatUsd as formaterCout } from "@/lib/status";
