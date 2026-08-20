/**
 * Badge de statut : icone + libelle, ton pris dans lib/status.ts.
 *
 * C'est le seul composant autorise a traduire un `Tone` en variante visuelle.
 * Les composants metier fournissent un StatusMeta, jamais une couleur.
 */

import type { VariantProps } from "class-variance-authority";
import type { LucideIcon } from "lucide-react";
import type * as React from "react";

import { Badge, badgeVariants } from "@/components/ui/badge";
import type { Tone } from "@/lib/status";
import { cn } from "@/lib/utils";

type BadgeVariant = NonNullable<VariantProps<typeof badgeVariants>["variant"]>;

const TONE_TO_VARIANT: Record<Tone, BadgeVariant> = {
  neutral: "secondary",
  success: "success",
  warning: "warning",
  info: "info",
  destructive: "destructive",
  destructiveSoft: "destructiveOutline",
};

export function StatusBadge({
  tone,
  icon: Icon,
  label,
  className,
  ...props
}: React.ComponentProps<"span"> & {
  tone: Tone;
  icon: LucideIcon;
  label: string;
}) {
  return (
    <Badge variant={TONE_TO_VARIANT[tone]} className={cn(className)} {...props}>
      {/* L'icone double la couleur ; le libelle reste le porteur du sens pour
          les lecteurs d'ecran, d'ou aria-hidden ici. */}
      <Icon aria-hidden="true" />
      {label}
    </Badge>
  );
}
