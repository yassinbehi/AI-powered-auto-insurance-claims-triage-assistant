import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Minuscules sans accents, pour comparer du texte saisi a du texte affiche.
 *
 * Indispensable sur des noms francais : sans cela, "benali" ne trouve pas
 * "Bénali", et l'utilisateur conclut que la recherche ne marche pas. Partage
 * par la file d'attente et par l'historique des analyses - deux copies
 * finiraient par ne plus se comporter pareil.
 */
export function normaliser(texte: string): string {
  return texte
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase()
}
