/**
 * Acces a l'API depuis le navigateur (Client Components).
 *
 * Va directement sur FastAPI, sans passer par un proxy `rewrites` de Next :
 * le proxy de developpement bufferise volontiers les reponses
 * text/event-stream, ce qui ferait arriver tout le triage d'un bloc a la fin -
 * exactement ce que cette interface cherche a montrer en direct. Le backend
 * autorise donc l'origine du frontend via CORS.
 */

import type { DatasetState, Rules, Screening } from "@/lib/types";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

/** L'API refuse un second travail de modele tant que le premier tourne. */
export class ApiBusyError extends Error {}

async function readDetail(response: Response): Promise<string> {
  try {
    const body = await response.json();
    return typeof body?.detail === "string" ? body.detail : response.statusText;
  } catch {
    return response.statusText;
  }
}

/**
 * URL du flux SSE de triage.
 *
 * `confirm=1` est exige par le backend : cet endpoint est un GET qui declenche
 * une boucle agentique complete, et ne doit pas pouvoir partir sur un prefetch
 * de lien ou un crawler.
 */
export function triageStreamUrl(claimId: string, model?: string): string {
  const params = new URLSearchParams({ confirm: "1" });
  // Absent, le backend applique son modele par defaut ; present, il le valide
  // contre config.AVAILABLE_MODELS (400 si inconnu).
  if (model) params.set("model", model);
  return `${API_BASE_URL}/api/triage/${encodeURIComponent(claimId)}/stream?${params.toString()}`;
}

/**
 * Depose les deux fichiers d'entree.
 *
 * Les deux partent ensemble : une declaration sans son contrat n'est pas
 * exploitable, et l'API remplace le jeu de donnees d'un bloc.
 */
export async function uploadDataset(
  claimsFile: File,
  policiesFile: File,
): Promise<DatasetState> {
  const corps = new FormData();
  corps.append("claims_file", claimsFile);
  corps.append("policies_file", policiesFile);

  const response = await fetch(`${API_BASE_URL}/api/dataset`, {
    method: "POST",
    body: corps,
  });

  if (!response.ok) {
    // 422 = fichier inexploitable. Le message de l'API nomme les colonnes
    // manquantes : il est utile tel quel a l'utilisateur.
    throw new Error(await readDetail(response));
  }
  return response.json() as Promise<DatasetState>;
}

export async function clearDataset(): Promise<DatasetState> {
  const response = await fetch(`${API_BASE_URL}/api/dataset`, { method: "DELETE" });
  if (!response.ok) {
    throw new Error(await readDetail(response));
  }
  return response.json() as Promise<DatasetState>;
}

/**
 * Documents de reference. Charges a l'ouverture du panneau plutot qu'au rendu
 * du layout : si le backend est eteint, seul ce panneau echoue, pas toute
 * l'application.
 */
export async function fetchRules(): Promise<Rules> {
  const response = await fetch(`${API_BASE_URL}/api/rules`);
  if (!response.ok) {
    throw new Error(await readDetail(response));
  }
  return response.json() as Promise<Rules>;
}

/** Execute les 3 couches du filtre anti-injection sur un sinistre. */
export async function runScreening(claimId: string): Promise<Screening> {
  const response = await fetch(
    `${API_BASE_URL}/api/claims/${encodeURIComponent(claimId)}/screen`,
    { method: "POST" },
  );

  if (response.status === 409) {
    throw new ApiBusyError(await readDetail(response));
  }
  if (!response.ok) {
    throw new Error(await readDetail(response));
  }
  return response.json() as Promise<Screening>;
}
