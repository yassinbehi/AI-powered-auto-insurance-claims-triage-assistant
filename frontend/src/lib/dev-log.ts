/**
 * Journal technique.
 *
 * L'interface s'adresse a un gestionnaire de sinistres, pas a un developpeur :
 * la trace des outils, la reponse brute du modele, la consommation de tokens,
 * les ecarts de schema et le detail du filtre anti-injection n'ont rien a
 * faire a l'ecran. Ils restent neanmoins indispensables pour diagnostiquer un
 * dossier qui se comporte mal.
 *
 * Ils sont donc DEPLACES ici, dans la console du navigateur, et non
 * supprimes. Ouvrir les outils de developpement redonne la vue complete.
 */

const PREFIXE = "%c[triage]";
const STYLE = "color:#6b7280;font-weight:600";

/** Une ligne simple : un libelle et sa donnee. */
export function devLog(libelle: string, donnee?: unknown): void {
  if (typeof console === "undefined") return;
  if (donnee === undefined) {
    console.log(PREFIXE, STYLE, libelle);
  } else {
    console.log(PREFIXE, STYLE, libelle, donnee);
  }
}

/** Un bloc replie, pour les objets volumineux (trace d'outils, JSON final). */
export function devGroup(libelle: string, donnee: unknown): void {
  if (typeof console === "undefined") return;
  console.groupCollapsed(PREFIXE, STYLE, libelle);
  console.log(donnee);
  console.groupEnd();
}

/** Un probleme technique, signale sans etre montre a l'utilisateur. */
export function devWarn(libelle: string, donnee?: unknown): void {
  if (typeof console === "undefined") return;
  console.warn(PREFIXE, STYLE, libelle, donnee ?? "");
}
