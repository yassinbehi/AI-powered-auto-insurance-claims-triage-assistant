"use client";

import { ChevronRight } from "lucide-react";
import * as React from "react";

import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";

/**
 * La reponse du modele telle qu'elle s'ecrit.
 *
 * Ce flux EST le JSON de triage, produit caractere par caractere : aucune
 * tentative de le parser au vol, ce serait fragile pour rien. Le resultat
 * structure arrive dans l'evenement `result`.
 *
 * aria-live vaut explicitement "off" : annoncer chaque fragment rendrait la
 * page inutilisable au lecteur d'ecran. La progression est annoncee ailleurs,
 * par jalons (voir TriageRunView).
 */
export function RawStreamPane({ text }: { text: string }) {
  const [ouvert, setOuvert] = React.useState(false);
  const zoneRef = React.useRef<HTMLPreElement>(null);

  React.useEffect(() => {
    const zone = zoneRef.current;
    if (!zone || !ouvert) return;
    // Defilement instantane : un defilement anime a chaque fragment serait
    // perpetuellement en retard sur le flux.
    zone.scrollTop = zone.scrollHeight;
  }, [text, ouvert]);

  return (
    <Collapsible open={ouvert} onOpenChange={setOuvert}>
      <CollapsibleTrigger className="flex w-full items-center gap-2 rounded-md py-1 text-left text-sm font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring">
        <ChevronRight
          className={cn(
            "size-4 text-muted-foreground transition-transform",
            ouvert && "rotate-90",
          )}
          aria-hidden="true"
        />
        Réponse brute du modèle
        <span className="font-normal text-muted-foreground tabular-nums">
          {text.length} caractères
        </span>
      </CollapsibleTrigger>

      <CollapsibleContent>
        <pre
          ref={zoneRef}
          aria-live="off"
          className="mt-2 max-h-72 overflow-auto rounded-md bg-muted p-3 font-mono text-xs leading-relaxed whitespace-pre-wrap"
        >
          {text || "En attente du premier fragment…"}
        </pre>
      </CollapsibleContent>
    </Collapsible>
  );
}
