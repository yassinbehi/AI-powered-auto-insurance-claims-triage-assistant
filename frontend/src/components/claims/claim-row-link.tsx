"use client";

import type * as React from "react";
import { useRouter } from "next/navigation";

import { TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";

/**
 * Ligne de file cliquable dans son ENTIER.
 *
 * Sur une file d'attente, on s'attend a ouvrir un dossier en cliquant sa ligne,
 * pas seulement le bouton au bout. Ce composant n'ajoute que ce confort a la
 * souris : le vrai lien accessible reste le bouton "Ouvrir" de la derniere
 * cellule, atteignable au clavier. Cliquer ailleurs sur la ligne y mene aussi.
 *
 * Les cellules a infobulle (urgence, devis, signalements) reagissent au survol,
 * pas au clic : les rendre cliquables-vers-le-dossier ne casse donc pas leur
 * infobulle.
 */
export function ClaimRowLink({
  href,
  children,
  className,
}: {
  href: string;
  children: React.ReactNode;
  className?: string;
}) {
  const router = useRouter();

  return (
    <TableRow
      className={cn("cursor-pointer hover:bg-muted/50", className)}
      onClick={() => router.push(href)}
    >
      {children}
    </TableRow>
  );
}
