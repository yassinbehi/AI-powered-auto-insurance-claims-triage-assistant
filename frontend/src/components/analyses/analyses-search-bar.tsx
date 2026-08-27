"use client";

import { RotateCcw, Search } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import * as React from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

/**
 * Recherche dans l'historique des analyses.
 *
 * SEUL composant client de cet ecran, comme la barre de la file d'attente.
 * L'etat vit dans l'URL et non dans React : la page reste un Server Component
 * qui filtre lui-meme, le tableau reste purement presentationnel, et un
 * historique cherche se copie-colle.
 *
 * `replace` et non `push` pour la saisie : taper huit lettres empilerait huit
 * entrees d'historique et rendrait le bouton Retour inutilisable. La remise a
 * zero, elle, est un choix delibere - `push`, pour que Retour puisse
 * l'annuler.
 *
 * Pas de liste deroulante ici, contrairement a la file : le champ libre
 * cherche deja dans l'assure, le dossier, le jeu de donnees, le modele et la
 * conclusion (voir lib/analyses-filter.ts). Ajouter trois selecteurs pour
 * refaire ce qu'une phrase fait deja encombrerait l'ecran sans rien ouvrir de
 * nouveau.
 */

const DELAI_SAISIE_MS = 300;

export function AnalysesSearchBar() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const qUrl = searchParams.get("q") ?? "";
  const [texte, setTexte] = React.useState(qUrl);
  const [enCours, demarrerTransition] = React.useTransition();

  /**
   * Resynchronisation du champ depuis l'URL, pendant le rendu et non dans un
   * effet (motif d'ajustement d'etat recommande par React, et qui evite le
   * rendu en cascade d'un useEffect).
   *
   * `dernierEnvoi` retient ce que NOUS avons ecrit dans l'URL. Sans cette
   * garde, l'arrivee de notre propre navigation differee ecraserait les
   * frappes saisies entre-temps. On ne resynchronise donc que sur un
   * changement venu d'ailleurs : la remise a zero, ou Precedent / Suivant.
   */
  const [dernierEnvoi, setDernierEnvoi] = React.useState(qUrl);
  if (qUrl !== dernierEnvoi) {
    setDernierEnvoi(qUrl);
    setTexte(qUrl);
  }

  const minuterie = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  React.useEffect(() => () => {
    if (minuterie.current) clearTimeout(minuterie.current);
  }, []);

  function ecrireDansLUrl(valeur: string, remplacer: boolean) {
    const params = new URLSearchParams(searchParams.toString());
    if (valeur.trim() === "") params.delete("q");
    else params.set("q", valeur);

    const requete = params.toString();
    const href = requete === "" ? pathname : `${pathname}?${requete}`;
    setDernierEnvoi(valeur.trim());
    demarrerTransition(() => {
      if (remplacer) router.replace(href, { scroll: false });
      else router.push(href, { scroll: false });
    });
  }

  function surSaisie(valeur: string) {
    setTexte(valeur);
    if (minuterie.current) clearTimeout(minuterie.current);
    minuterie.current = setTimeout(() => ecrireDansLUrl(valeur, true), DELAI_SAISIE_MS);
  }

  function reinitialiser() {
    if (minuterie.current) clearTimeout(minuterie.current);
    setTexte("");
    ecrireDansLUrl("", false);
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="relative min-w-0 flex-1 sm:max-w-md">
        <Search
          className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
          aria-hidden="true"
        />
        <Input
          type="search"
          value={texte}
          onChange={(e) => surSaisie(e.target.value)}
          placeholder="Rechercher un assuré, un dossier, une conclusion…"
          aria-label="Rechercher dans les analyses"
          className={cn("pl-9", enCours && "opacity-70")}
        />
      </div>

      {qUrl !== "" ? (
        <Button variant="ghost" size="sm" onClick={reinitialiser}>
          <RotateCcw aria-hidden="true" />
          Réinitialiser
        </Button>
      ) : null}
    </div>
  );
}
