import { MessageSquareWarning } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import type { Screening } from "@/lib/types";

/**
 * Le texte du client, ou l'avertissement qui le remplace.
 *
 * Extrait de client-message-panel.tsx pour que la fiche dossier ET l'ecran
 * d'analyse montrent exactement la meme chose. C'est le seul endroit du
 * frontend qui decide comment presenter une declaration client : dupliquer ce
 * choix, c'est prendre le risque qu'un ecran affiche un jour un texte ecarte
 * comme s'il etait fiable.
 *
 * Composant de presentation pur, sans "use client" : il n'a ni etat ni effet,
 * et peut donc etre rendu par un Server Component sans embarquer de
 * JavaScript.
 */

/** Retire l'encadrement technique ajoute par le backend avant affichage. */
export function texteLisible(brut: string): string {
  return brut.replace(/<\/?donnee_client_non_fiable>/g, "").trim();
}

export function DeclarationClient({ screening }: { screening: Screening }) {
  if (screening.redacted) {
    return (
      <Alert variant="destructive">
        <MessageSquareWarning aria-hidden="true" />
        <AlertTitle>Message écarté</AlertTitle>
        <AlertDescription>
          Le texte transmis par le client demandait de contourner les règles de traitement.
          Il n&apos;a pas été pris en compte dans l&apos;analyse, qui s&apos;appuie
          uniquement sur les éléments vérifiables du dossier.
        </AlertDescription>
      </Alert>
    );
  }

  const texte = texteLisible(screening.text_for_model);

  if (texte === "") {
    return (
      <p className="text-sm text-muted-foreground">
        Le client n&apos;a joint aucun texte à sa déclaration.
      </p>
    );
  }

  return (
    <blockquote className="border-l-2 pl-3 text-sm leading-relaxed whitespace-pre-line">
      {texte}
    </blockquote>
  );
}
