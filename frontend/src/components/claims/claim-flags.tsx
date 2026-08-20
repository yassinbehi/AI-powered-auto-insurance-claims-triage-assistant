/**
 * Signalements affiches dans la file d'attente et en tete de dossier.
 *
 * Aucun de ces signalements n'est une DECISION : ce sont des faits lus dans
 * claims_auto.csv ou releves par une fonction pure du backend. La decision de
 * triage n'existe qu'apres un passage de l'agent.
 */

import { HeartPulse, Microscope, ShieldAlert } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { SEUIL_EXPERTISE_TND, formatTnd } from "@/lib/status";
import { cn } from "@/lib/utils";

export function BlessureFlag() {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Badge variant="destructive">
          <HeartPulse aria-hidden="true" />
          Blessure
        </Badge>
      </TooltipTrigger>
      <TooltipContent>
        Blessure déclarée : expertise requise et priorité critique
        (regles_sinistres.md).
      </TooltipContent>
    </Tooltip>
  );
}

export function InjectionFlag({ markers }: { markers: string[] }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Badge variant="warning">
          <ShieldAlert aria-hidden="true" />
          Instruction détectée
        </Badge>
      </TooltipTrigger>
      <TooltipContent className="max-w-xs">
        Le texte du client contient {markers.length}{" "}
        {markers.length > 1 ? "marqueurs connus" : "marqueur connu"} d&apos;injection. Détecté
        par une simple analyse de mots-clés, sans appel de modèle.
      </TooltipContent>
    </Tooltip>
  );
}

/**
 * Montant du devis. Au-dessus du seuil, la couleur est doublee d'une icone et
 * d'un texte lisible par lecteur d'ecran : un statut ne doit jamais se lire
 * uniquement a la couleur.
 */
export function MontantCell({
  devisTnd,
  className,
}: {
  devisTnd: number;
  className?: string;
}) {
  const auDessusDuSeuil = devisTnd > SEUIL_EXPERTISE_TND;

  if (!auDessusDuSeuil) {
    return <span className={cn("tabular-nums", className)}>{formatTnd(devisTnd)}</span>;
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          className={cn(
            "inline-flex items-center gap-1.5 font-medium text-warning tabular-nums",
            className,
          )}
        >
          {formatTnd(devisTnd)}
          <Microscope className="size-3.5" aria-hidden="true" />
          <span className="sr-only">— au-dessus du seuil d&apos;expertise obligatoire</span>
        </span>
      </TooltipTrigger>
      <TooltipContent>
        Au-dessus de {formatTnd(SEUIL_EXPERTISE_TND)} : expertise obligatoire.
      </TooltipContent>
    </Tooltip>
  );
}
