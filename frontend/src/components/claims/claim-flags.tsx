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
import {
  SEUIL_EXPERTISE_TND,
  URGENCE_META,
  formatTnd,
  urgenceMotifLabel,
} from "@/lib/status";
import type { Urgence } from "@/lib/types";
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

export function InjectionFlag() {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Badge variant="warning">
          <ShieldAlert aria-hidden="true" />
          Message signalé
        </Badge>
      </TooltipTrigger>
      <TooltipContent className="max-w-xs">
        Le message du client demande de contourner les règles de traitement. Il sera écarté de
        l&apos;analyse.
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

/**
 * Urgence estimee : une jauge a quatre segments, jamais un badge.
 *
 * La forme est le message. Le triage et la priorite sont des badges ; si
 * l'urgence en etait un de plus, personne ne verrait qu'elle ne repond pas a
 * la meme question. Elle est calculee avant toute analyse, a partir de la
 * seule declaration, et la priorite proposee ensuite par l'agent peut etre
 * differente - l'infobulle le dit explicitement, parce qu'un gestionnaire qui
 * verrait les deux se contredire sans explication perdrait confiance dans les
 * deux a la fois.
 *
 * Le libelle texte accompagne TOUJOURS la jauge : quatre segments colores
 * seuls ne se lisent ni en noir et blanc, ni par un lecteur d'ecran.
 */
export function UrgenceCell({
  urgence,
  motifs,
  className,
}: {
  urgence: Urgence;
  motifs: string[];
  className?: string;
}) {
  const meta = URGENCE_META[urgence];

  // Backend en avance sur le frontend : afficher la valeur brute plutot que
  // de la faire passer en silence pour "normale", ce qui serait un mensonge.
  if (!meta) {
    return (
      <span className={cn("text-sm text-muted-foreground", className)}>{urgence}</span>
    );
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className={cn("inline-flex items-center gap-2", className)}>
          <span className="inline-flex gap-0.5" aria-hidden="true">
            {[0, 1, 2, 3].map((i) => (
              <span
                key={i}
                className={cn(
                  "h-3 w-1 rounded-full",
                  i < meta.segments ? meta.dotClassName : "bg-border",
                )}
              />
            ))}
          </span>
          <span className="text-sm">{meta.label}</span>
        </span>
      </TooltipTrigger>
      <TooltipContent className="max-w-xs space-y-1">
        <p>Estimation calculée avant toute analyse, à partir de la déclaration.</p>
        {motifs.length > 0 ? (
          <p>D&apos;après : {motifs.map(urgenceMotifLabel).join(", ")}.</p>
        ) : (
          <p>Aucun point de vigilance lisible dans la déclaration.</p>
        )}
        <p>Ce n&apos;est pas la priorité proposée par l&apos;analyse.</p>
      </TooltipContent>
    </Tooltip>
  );
}
