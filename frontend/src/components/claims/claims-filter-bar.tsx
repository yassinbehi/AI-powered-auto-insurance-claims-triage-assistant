"use client";

import { ChevronDown, RotateCcw, Search } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import * as React from "react";

import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  FORMULE_LABEL,
  TYPE_SINISTRE_LABEL,
  URGENCE_META,
} from "@/lib/status";
import { TYPE_SINISTRE_VALUES, URGENCE_VALUES } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * Barre de recherche et de filtres de la file d'attente.
 *
 * SEUL composant client de cet ecran. L'etat vit dans l'URL et non dans React :
 * la page reste un Server Component qui filtre lui-meme, le tableau reste
 * purement presentationnel, et un lien vers une file filtree se copie-colle.
 *
 * DEUX SORTES DE NAVIGATION, volontairement :
 *   - `replace` pour la saisie de texte (avec un delai), sinon taper huit
 *     lettres empile huit entrees d'historique et le bouton Retour devient
 *     inutilisable ;
 *   - `push` pour les listes, les dates et la reinitialisation, parce que ce
 *     sont des choix deliberes que Retour doit pouvoir annuler.
 */

/** Radix Select refuse une valeur vide. Sentinelle interne, retiree au moment
 *  d'ecrire l'URL. */
const TOUTES = "toutes";

const DELAI_SAISIE_MS = 300;

export function ClaimsFilterBar({ datesIncoherentes }: { datesIncoherentes: boolean }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const qUrl = searchParams.get("q") ?? "";
  const [texte, setTexte] = React.useState(qUrl);
  const [enCours, demarrerTransition] = React.useTransition();

  /**
   * Resynchronisation du champ depuis l'URL, pendant le rendu et non dans un
   * effet : c'est le motif d'ajustement d'etat recommande par React, et il
   * evite le rendu en cascade qu'un useEffect provoquerait.
   *
   * `dernierEnvoi` retient ce que NOUS avons ecrit dans l'URL. Sans cette
   * garde, l'arrivee de notre propre navigation differee ecraserait les
   * frappes saisies entre-temps : taper "benali" verrait le champ revenir a
   * "ben" 300 ms plus tard. On ne resynchronise donc que sur un changement
   * d'URL venu d'ailleurs - un clic sur Reinitialiser, ou les boutons
   * Precedent / Suivant du navigateur.
   */
  const [synchro, setSynchro] = React.useState({ vu: qUrl, envoye: qUrl });
  if (qUrl !== synchro.vu) {
    if (qUrl === synchro.envoye) {
      // Notre propre navigation differee vient d'arriver : on prend acte sans
      // toucher au champ, qui a pu avancer depuis.
      setSynchro({ vu: qUrl, envoye: synchro.envoye });
    } else {
      setSynchro({ vu: qUrl, envoye: qUrl });
      setTexte(qUrl);
    }
  }

  const nbActifs = React.useMemo(
    () =>
      ["q", "du", "au", "urgence", "type", "formule"].filter((cle) =>
        searchParams.get(cle),
      ).length,
    [searchParams],
  );

  function urlAvec(cle: string, valeur: string): string {
    const params = new URLSearchParams(searchParams.toString());
    if (valeur === "" || valeur === TOUTES) {
      params.delete(cle);
    } else {
      params.set(cle, valeur);
    }
    const suffixe = params.toString();
    return suffixe ? `${pathname}?${suffixe}` : pathname;
  }

  function appliquer(cle: string, valeur: string) {
    demarrerTransition(() => router.push(urlAvec(cle, valeur), { scroll: false }));
  }

  // Le delai evite une requete par frappe : la page est rendue cote serveur et
  // chaque navigation relit l'API.
  const minuterie = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  React.useEffect(() => () => {
    if (minuterie.current) clearTimeout(minuterie.current);
  }, []);

  function saisirTexte(valeur: string) {
    setTexte(valeur);
    if (minuterie.current) clearTimeout(minuterie.current);
    minuterie.current = setTimeout(() => {
      const envoye = valeur.trim();
      setSynchro((s) => ({ ...s, envoye }));
      demarrerTransition(() => router.replace(urlAvec("q", envoye), { scroll: false }));
    }, DELAI_SAISIE_MS);
  }

  function reinitialiser() {
    if (minuterie.current) clearTimeout(minuterie.current);
    setSynchro((s) => ({ ...s, envoye: "" }));
    setTexte("");
    demarrerTransition(() => router.push(pathname, { scroll: false }));
  }

  const listes = (
    <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
      <ChampListe
        id="filtre-urgence"
        label="Urgence"
        valeurTous="Toutes urgences"
        valeur={searchParams.get("urgence") ?? TOUTES}
        onChange={(v) => appliquer("urgence", v)}
        options={URGENCE_VALUES.map((v) => ({ valeur: v, label: URGENCE_META[v].label }))}
      />
      <ChampListe
        id="filtre-type"
        label="Type de sinistre"
        valeurTous="Tous les types"
        valeur={searchParams.get("type") ?? TOUTES}
        onChange={(v) => appliquer("type", v)}
        options={TYPE_SINISTRE_VALUES.map((v) => ({
          valeur: v,
          label: TYPE_SINISTRE_LABEL[v],
        }))}
      />
      <ChampListe
        id="filtre-formule"
        label="Formule"
        valeurTous="Toutes les formules"
        valeur={searchParams.get("formule") ?? TOUTES}
        onChange={(v) => appliquer("formule", v)}
        options={Object.entries(FORMULE_LABEL).map(([valeur, label]) => ({
          valeur,
          label,
        }))}
      />

      {/* Les deux bornes forment un groupe, mais leurs libelles sont masques
          visuellement : un second niveau de libelle ferait decrocher cette
          colonne de la ligne de base des trois listes. Le champ de date natif
          affiche de lui-meme son format (jj/mm/aaaa), et les libelles restent
          annonces par les lecteurs d'ecran. */}
      <div className="space-y-2">
        <span className="block text-sm font-medium" id="filtre-dates-titre">
          Date du sinistre
        </span>
        <div
          className="flex items-center gap-2"
          role="group"
          aria-labelledby="filtre-dates-titre"
        >
          <ChampDate
            id="filtre-du"
            label="À partir du"
            valeur={searchParams.get("du") ?? ""}
            onChange={(v) => appliquer("du", v)}
          />
          <span className="text-sm text-muted-foreground" aria-hidden="true">
            au
          </span>
          <ChampDate
            id="filtre-au"
            label="Jusqu'au"
            valeur={searchParams.get("au") ?? ""}
            onChange={(v) => appliquer("au", v)}
          />
        </div>
        {datesIncoherentes ? (
          <p className="text-sm text-destructive">
            La date de début est postérieure à la date de fin.
          </p>
        ) : null}
      </div>
    </div>
  );

  return (
    <div
      className={cn("space-y-3 transition-opacity", enCours && "opacity-60")}
      aria-busy={enCours}
    >
      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <Label htmlFor="filtre-recherche" className="sr-only">
            Rechercher un dossier
          </Label>
          <Search
            className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
          <Input
            id="filtre-recherche"
            type="search"
            value={texte}
            onChange={(e) => saisirTexte(e.target.value)}
            placeholder="Nom de l'assuré, véhicule ou n° de dossier"
            className="pl-9"
          />
        </div>
        {nbActifs > 0 ? (
          <Button variant="ghost" size="sm" onClick={reinitialiser}>
            <RotateCcw aria-hidden="true" />
            Réinitialiser
          </Button>
        ) : null}
      </div>

      {/* Sous `sm`, les listes se replient derriere un seul declencheur : cinq
          controles empiles pousseraient la file entiere hors de l'ecran.
          A partir de `sm`, elles sont montrees en permanence.

          `forceMount` + visibilite en CSS, et non deux rendus : dupliquer le
          bloc dupliquerait les `id`, ce qui casserait les <Label htmlFor>. */}
      <Collapsible>
        <CollapsibleTrigger asChild>
          <Button variant="outline" size="sm" className="w-full sm:hidden">
            Filtres
            {nbActifs > 0 ? (
              <span className="ml-1 rounded-full bg-muted px-1.5 text-xs tabular-nums">
                {nbActifs}
              </span>
            ) : null}
            <ChevronDown
              className="ml-auto transition-transform [[data-state=open]>&]:rotate-180"
              aria-hidden="true"
            />
          </Button>
        </CollapsibleTrigger>
        <CollapsibleContent
          forceMount
          className="pt-3 data-[state=closed]:hidden sm:!block sm:pt-0"
        >
          {listes}
        </CollapsibleContent>
      </Collapsible>
    </div>
  );
}

function ChampListe({
  id,
  label,
  valeurTous,
  valeur,
  onChange,
  options,
}: {
  id: string;
  label: string;
  valeurTous: string;
  valeur: string;
  onChange: (valeur: string) => void;
  options: { valeur: string; label: string }[];
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      <Select value={valeur} onValueChange={onChange}>
        <SelectTrigger id={id} className="w-full sm:w-48">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={TOUTES}>{valeurTous}</SelectItem>
          {options.map((option) => (
            <SelectItem key={option.valeur} value={option.valeur}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

/**
 * Champ de date natif. Il s'affiche dans la locale du systeme (jj/mm/aaaa en
 * francais), mais sa valeur est toujours ISO. C'est le prix a payer pour ne
 * pas embarquer un selecteur de dates entier : en echange, on herite du
 * calendrier du systeme, de la saisie clavier et de l'accessibilite.
 */
function ChampDate({
  id,
  label,
  valeur,
  onChange,
}: {
  id: string;
  label: string;
  valeur: string;
  onChange: (valeur: string) => void;
}) {
  return (
    <>
      <Label htmlFor={id} className="sr-only">
        {label}
      </Label>
      <Input
        id={id}
        type="date"
        lang="fr"
        value={valeur}
        onChange={(e) => onChange(e.target.value)}
        className="w-full sm:w-40"
      />
    </>
  );
}
