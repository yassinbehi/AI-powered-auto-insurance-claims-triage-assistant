"use client";

import { Check, Copy } from "lucide-react";
import * as React from "react";

import { Button } from "@/components/ui/button";
import { devWarn } from "@/lib/dev-log";

/**
 * Copie un texte dans le presse-papiers.
 *
 * Le message client est destine a etre colle dans un courriel ou un outil de
 * gestion : le recopier a la main serait la premiere source d'erreur de toute
 * l'interface.
 */
export function CopyButton({
  value,
  label = "Copier",
  className,
}: {
  value: string;
  label?: string;
  className?: string;
}) {
  const [copie, setCopie] = React.useState(false);

  async function copier() {
    try {
      await navigator.clipboard.writeText(value);
      setCopie(true);
      setTimeout(() => setCopie(false), 2000);
    } catch (error) {
      devWarn("copie dans le presse-papiers refusée", error);
    }
  }

  return (
    <Button variant="outline" size="sm" onClick={copier} className={className}>
      {copie ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />}
      {copie ? "Copié" : label}
    </Button>
  );
}
