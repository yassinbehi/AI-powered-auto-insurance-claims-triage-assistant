"use client";

import * as React from "react";

import { DeclarationClient } from "@/components/claims/declaration-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { devGroup } from "@/lib/dev-log";
import type { Screening } from "@/lib/types";

/**
 * Ce que le client a ecrit dans sa declaration.
 *
 * La version precedente exposait ici toute la mecanique du filtre
 * anti-injection : verdict SAFE / SUSPECT / INJECTION, marqueurs detectes,
 * balises <donnee_client_non_fiable> affichees telles quelles, bouton pour
 * lancer la couche 2. Rien de tout cela n'aide un gestionnaire a traiter un
 * sinistre, et le vocabulaire ne lui parle pas.
 *
 * L'ecran ne garde donc que deux choses : le texte du client, et un
 * avertissement en clair quand ce texte a ete ecarte. Le detail du filtre
 * part dans la console.
 *
 * L'affichage lui-meme vit dans declaration-client.tsx, partage avec l'ecran
 * d'analyse. Ce composant n'ajoute que le cadre et la trace console.
 */
export function ClientMessagePanel({
  claimId,
  screening,
}: {
  claimId: string;
  screening: Screening;
}) {
  React.useEffect(() => {
    devGroup(`filtre anti-injection · ${claimId}`, screening);
  }, [claimId, screening]);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Ce que le client a déclaré</CardTitle>
      </CardHeader>
      <CardContent>
        <DeclarationClient screening={screening} />
      </CardContent>
    </Card>
  );
}
