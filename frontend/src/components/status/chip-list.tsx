/**
 * Liste de valeurs sous forme de puces.
 *
 * Rend un etat vide EXPLICITE plutot que rien du tout : contrat_sortie.md
 * impose que `signaux_fraude` et `pieces_manquantes` soient toujours presents,
 * meme vides. Une zone blanche ne dit pas si la liste est vide ou si le champ
 * manque - ce sont deux situations tres differentes en revue de dossier.
 */

import type { LucideIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export function ChipList({
  items,
  emptyLabel = "Aucun",
  icon: Icon,
  className,
}: {
  items: string[];
  emptyLabel?: string;
  icon?: LucideIcon;
  className?: string;
}) {
  if (items.length === 0) {
    return <p className={cn("text-sm text-muted-foreground", className)}>{emptyLabel}</p>;
  }

  return (
    <ul className={cn("flex flex-wrap gap-1.5", className)}>
      {items.map((item) => (
        <li key={item}>
          <Badge variant="outline" className="max-w-full whitespace-normal">
            {Icon ? <Icon aria-hidden="true" /> : null}
            {item}
          </Badge>
        </li>
      ))}
    </ul>
  );
}
