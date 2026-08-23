/**
 * Acces a l'API depuis les Server Components.
 *
 * Utilise API_BASE_URL (variable serveur) : le rendu initial des pages de
 * consultation part donc du serveur Next vers FastAPI, sans transiter par le
 * navigateur. Les composants interactifs utilisent lib/api-client.ts.
 *
 * `cache: "no-store"` partout : les CSV sont relus a chaque appel cote Python
 * et une fiche dossier doit refleter l'etat courant, pas une capture.
 */

import type { ClaimDetail, ClaimSummary, DatasetState, Rules } from "@/lib/types";

const BASE_URL = process.env.API_BASE_URL ?? "http://127.0.0.1:8000";

/** Levee quand l'API repond 404 : la page appelante la traduit en notFound(). */
export class ApiNotFoundError extends Error {}

/** Levee quand l'API est injoignable, pour distinguer "backend eteint" d'une
 *  vraie erreur applicative - c'est la panne la plus frequente en demo. */
export class ApiUnreachableError extends Error {}

/** Levee quand aucun fichier n'a ete depose : l'application n'a pas de
 *  donnees, et la page appelante doit renvoyer vers l'ecran de depot. */
export class ApiNoDatasetError extends Error {}

/**
 * Next signale certaines situations en LEVANT une erreur : bascule d'une route
 * en rendu dynamique, notFound(), redirect(). Ces erreurs portent un `digest`
 * et doivent remonter intactes.
 *
 * Les intercepter casse le framework de facon deroutante : un `catch (e)` trop
 * large autour d'un fetch transformait ici la bascule en dynamique en un
 * "API injoignable" pendant `next build`, alors que l'API tournait.
 */
function estSignalInterneNext(error: unknown): boolean {
  return typeof error === "object" && error !== null && "digest" in error;
}

async function get<T>(path: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, { cache: "no-store" });
  } catch (cause) {
    if (estSignalInterneNext(cause)) throw cause;
    throw new ApiUnreachableError(
      `L'API de triage est injoignable sur ${BASE_URL}. Demarrez-la avec : ` +
        `uvicorn api:app --app-dir backend/src`,
      { cause },
    );
  }

  if (response.status === 404) {
    throw new ApiNotFoundError(`Ressource introuvable : ${path}`);
  }
  if (response.status === 409) {
    throw new ApiNoDatasetError("Aucun fichier déposé.");
  }
  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    throw new Error(`L'API a repondu ${response.status} sur ${path}. ${detail}`);
  }
  return response.json() as Promise<T>;
}

export function fetchDatasetState() {
  return get<DatasetState>("/api/dataset");
}

export function fetchClaims() {
  return get<ClaimSummary[]>("/api/claims");
}

export function fetchClaimDetail(claimId: string) {
  return get<ClaimDetail>(`/api/claims/${encodeURIComponent(claimId)}`);
}

export function fetchRules() {
  return get<Rules>("/api/rules");
}
