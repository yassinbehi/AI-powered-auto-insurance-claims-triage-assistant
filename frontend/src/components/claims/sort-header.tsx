"use client";

import { ArrowDown, ArrowUp, ChevronsUpDown } from "lucide-react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";

import type { TriChamp, TriFile } from "@/lib/claims-filter";
import { cn } from "@/lib/utils";

/**
 * En-tete de colonne triable de la file.
 *
 * Le tri vit dans l'URL, comme les filtres (voir claims-filter-bar.tsx) : cet
 * en-tete n'est qu'un lien qui recrit `tri` et `sens`. La page, cote serveur,
 * relit ces parametres et renvoie la liste deja triee - le composant ne trie
 * rien lui-meme, il ne fait que montrer l'etat et proposer le suivant.
 */
export function SortHeader({
  champ,
  label,
  tri,
  align = "left",
  ariaLabel,
}: {
  champ: TriChamp;
  label: string;
  tri: TriFile;
  align?: "left" | "right";
  /** Libelle lu par les lecteurs d'ecran quand il differe du texte visible
   *  (ex. colonne "Sinistre" qui se trie par date). */
  ariaLabel?: string;
}) {
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const actif = tri.champ === champ;
  // Colonne active : on inverse le sens. Colonne inactive : on part en
  // decroissant - le plus urgent, le plus cher ou le plus recent d'abord, soit
  // l'entree la plus utile en tete d'une file de traitement.
  const prochainSens = actif && tri.sens === "desc" ? "asc" : "desc";

  const params = new URLSearchParams(searchParams.toString());
  params.set("tri", champ);
  params.set("sens", prochainSens);
  const href = `${pathname}?${params.toString()}`;

  const Icone = !actif ? ChevronsUpDown : tri.sens === "desc" ? ArrowDown : ArrowUp;
  const sensLu = actif ? (tri.sens === "desc" ? ", décroissant" : ", croissant") : "";

  return (
    <Link
      href={href}
      scroll={false}
      aria-label={`Trier par ${ariaLabel ?? label.toLowerCase()}${sensLu}`}
      className={cn(
        "group inline-flex items-center gap-1 rounded-md transition-colors hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
        align === "right" && "flex-row-reverse",
        actif ? "text-foreground" : "text-muted-foreground",
      )}
    >
      {label}
      <Icone
        className={cn("size-3.5 shrink-0", !actif && "opacity-40 group-hover:opacity-100")}
        aria-hidden="true"
      />
    </Link>
  );
}
