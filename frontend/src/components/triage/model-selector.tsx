"use client";

import type { ModelOption } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * Choix du modele d'analyse, avant de lancer le triage.
 *
 * Un controle segmente construit sur de VRAIS boutons radio (masques
 * visuellement) : on herite ainsi de l'accessibilite native - navigation aux
 * fleches, annonce du groupe et de l'option cochee, libelle cliquable - sans
 * reimplementer la gestion clavier d'un faux radiogroup.
 *
 * Avec un seul modele disponible, il n'y a pas de choix a offrir : le composant
 * ne rend rien.
 */
export function ModelSelector({
  models,
  value,
  onChange,
  disabled = false,
}: {
  models: ModelOption[];
  value: string;
  onChange: (id: string) => void;
  disabled?: boolean;
}) {
  if (models.length <= 1) return null;

  return (
    <fieldset disabled={disabled} className="min-w-0">
      <legend className="mb-1.5 text-xs font-medium text-muted-foreground">
        Modèle d&apos;analyse
      </legend>
      <div className="inline-flex rounded-lg border bg-muted/40 p-0.5">
        {models.map((modele) => {
          const actif = modele.id === value;
          return (
            <label
              key={modele.id}
              className={cn(
                "cursor-pointer rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                "has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-ring",
                actif
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground",
                disabled && "cursor-not-allowed opacity-60",
              )}
            >
              <input
                type="radio"
                name="modele-analyse"
                value={modele.id}
                checked={actif}
                onChange={() => onChange(modele.id)}
                disabled={disabled}
                className="sr-only"
              />
              {modele.label}
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}
