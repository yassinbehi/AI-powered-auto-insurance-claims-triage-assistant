import { SEUIL_EXPERTISE_TND, formatTnd } from "@/lib/status";
import { cn } from "@/lib/utils";

/**
 * Fourchette de reparation, avec le seuil d'expertise repere sur l'axe.
 *
 * Le repere visuel est double d'une phrase : la position d'un trait sur une
 * barre n'est pas lisible par un lecteur d'ecran, et reste approximative a
 * l'oeil.
 */
export function RepairRangeBar({
  min,
  max,
  className,
}: {
  min: number;
  max: number;
  className?: string;
}) {
  // L'echelle englobe toujours le seuil, sinon celui-ci sortirait du cadre
  // pour les petits sinistres et le repere disparaitrait.
  const echelle = Math.max(max, SEUIL_EXPERTISE_TND) * 1.15;
  const pourcent = (valeur: number) => `${Math.min(100, (valeur / echelle) * 100)}%`;

  const auDessusDuSeuil = max > SEUIL_EXPERTISE_TND;

  return (
    <div className={cn("space-y-2", className)}>
      <p className="text-2xl font-semibold tabular-nums">
        {formatTnd(min)} – {formatTnd(max)}
      </p>

      <div
        className="relative h-2 w-full rounded-full bg-muted"
        role="img"
        aria-label={`Fourchette de ${formatTnd(min)} à ${formatTnd(max)}. Seuil d'expertise à ${formatTnd(SEUIL_EXPERTISE_TND)}.`}
      >
        <div
          className={cn(
            "absolute inset-y-0 rounded-full",
            auDessusDuSeuil ? "bg-warning" : "bg-foreground/70",
          )}
          style={{ left: pourcent(min), width: pourcent(Math.max(0, max - min)) }}
        />
        <div
          className="absolute inset-y-[-3px] w-px bg-foreground"
          style={{ left: pourcent(SEUIL_EXPERTISE_TND) }}
          aria-hidden="true"
        />
      </div>

      <p className="text-xs text-muted-foreground">
        Seuil d&apos;expertise à {formatTnd(SEUIL_EXPERTISE_TND)} :{" "}
        {auDessusDuSeuil ? "dépassé." : "non atteint."}
      </p>
    </div>
  );
}
