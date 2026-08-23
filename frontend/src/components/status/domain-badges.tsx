/**
 * Badges metier. Chacun se contente de piocher son StatusMeta dans
 * lib/status.ts et de le passer a StatusBadge.
 *
 * Le triage et la priorite ont volontairement des formes differentes (aplat
 * translucide contre contour a pastille) : ils s'affichent souvent cote a
 * cote, et deux badges de meme forme se disputeraient l'attention.
 */

import { StatusBadge } from "@/components/status/status-badge";
import { Badge } from "@/components/ui/badge";
import { PRIORITE_META, TRIAGE_META, TYPE_SINISTRE_LABEL } from "@/lib/status";
import type { Priorite, Triage, TypeSinistre } from "@/lib/types";
import { cn } from "@/lib/utils";

export function TriageBadge({ triage, className }: { triage: Triage; className?: string }) {
  const meta = TRIAGE_META[triage];
  if (!meta) {
    // Le modele peut renvoyer une valeur hors contrat : l'afficher telle
    // quelle vaut mieux que de planter ou de la masquer.
    return (
      <Badge variant="outline" className={className}>
        {triage}
      </Badge>
    );
  }
  return (
    <StatusBadge tone={meta.tone} icon={meta.Icon} label={meta.label} className={className} />
  );
}

export function PriorityBadge({
  priorite,
  className,
}: {
  priorite: Priorite;
  className?: string;
}) {
  const meta = PRIORITE_META[priorite];
  if (!meta) {
    return (
      <Badge variant="outline" className={className}>
        {priorite}
      </Badge>
    );
  }
  return (
    <Badge variant="outline" className={cn("gap-1.5", className)}>
      <span className={cn("size-1.5 rounded-full", meta.dotClassName)} aria-hidden="true" />
      {meta.label}
    </Badge>
  );
}

export function TypeSinistreBadge({
  type,
  className,
}: {
  type: TypeSinistre;
  className?: string;
}) {
  // Pas d'icone : un type de sinistre est une categorie, pas un statut. Lui
  // donner une icone banaliserait celles qui signalent vraiment un etat.
  return (
    <Badge variant="outline" className={className}>
      {TYPE_SINISTRE_LABEL[type] ?? type}
    </Badge>
  );
}
