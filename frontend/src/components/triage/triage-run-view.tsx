"use client";

import { CircleCheck, LoaderCircle, Play, TriangleAlert } from "lucide-react";
import * as React from "react";

import { ModelSelector } from "@/components/triage/model-selector";
import { TriageResultCard } from "@/components/result/triage-result-card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useTriageStream, type ProgressStep } from "@/hooks/use-triage-stream";
import type { ModelOption } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Modele par defaut : celui marque `default`, sinon le premier de la liste. */
function modeleParDefaut(models: ModelOption[]): string {
  return (models.find((m) => m.default) ?? models[0])?.id ?? "";
}

/**
 * Avancement de l'analyse, en termes de dossier.
 *
 * L'ancienne version montrait ici la boucle d'outils : noms de fonctions,
 * entrees et sorties JSON, numeros de tour. C'est utile pour mettre au point
 * l'agent, inutile pour traiter un sinistre. Le detail est desormais dans la
 * console du navigateur ; l'ecran ne garde que ce qui se passe, en clair.
 */
function Avancement({ steps, termine }: { steps: ProgressStep[]; termine: boolean }) {
  if (steps.length === 0) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
        Ouverture du dossier…
      </p>
    );
  }

  return (
    <ol className="space-y-2">
      {steps.map((step) => (
        <li key={step.key} className="flex items-center gap-2 text-sm">
          {step.done ? (
            <CircleCheck className="size-4 shrink-0 text-success" aria-hidden="true" />
          ) : (
            <LoaderCircle
              className="size-4 shrink-0 animate-spin text-muted-foreground"
              aria-hidden="true"
            />
          )}
          <span className={cn(step.done ? "text-muted-foreground" : "font-medium")}>
            {step.label}
          </span>
          <span className="sr-only">{step.done ? "terminé" : "en cours"}</span>
        </li>
      ))}
      {termine ? null : (
        <li className="text-xs text-muted-foreground">L&apos;analyse prend quelques secondes.</li>
      )}
    </ol>
  );
}

/**
 * `brief` est le contenu de "Le sinistre en bref", construit par la page cote
 * serveur et transmis tel quel a la carte de resultat, qui l'affiche comme un
 * bloc parmi les autres. Il apparait donc avec le resultat de l'analyse, ni
 * avant ni separement.
 */
export function TriageRunView({
  claimId,
  brief,
  models,
  messageSignale = false,
}: {
  claimId: string;
  brief?: React.ReactNode;
  /** Modeles proposes pour l'analyse (GET /api/models). Vide = le backend
   *  appliquera son defaut, et le selecteur ne s'affiche pas. */
  models: ModelOption[];
  /** Le message du client a ete ecarte du filtre. On le rappelle une fois
   *  l'analyse terminee : le triage ne l'a pas lu, mais le gestionnaire peut le
   *  relire (avec sa note) dans « Le sinistre en bref » ci-dessous. */
  messageSignale?: boolean;
}) {
  const { status, steps, output, error, start, cancel } = useTriageStream(claimId);
  const [modele, setModele] = React.useState(() => modeleParDefaut(models));
  // Le modele REELLEMENT lance, fige au moment du clic : le selecteur peut
  // changer ensuite sans faire mentir le « analysé avec … » du resultat.
  const [modeleLance, setModeleLance] = React.useState<string | null>(null);

  const enCours = status === "running";
  const termine = status === "done";
  const lance = status !== "idle";

  const labelDe = (id: string | null) =>
    models.find((m) => m.id === id)?.label ?? id ?? "";

  function lancer() {
    setModeleLance(modele);
    start(modele || undefined);
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end gap-4">
        <ModelSelector
          models={models}
          value={modele}
          onChange={setModele}
          disabled={enCours}
        />

        <div className="flex flex-wrap items-center gap-3">
          <Button onClick={lancer} disabled={enCours}>
            {enCours ? (
              <LoaderCircle className="animate-spin" aria-hidden="true" />
            ) : (
              <Play aria-hidden="true" />
            )}
            {status === "idle" ? "Analyser le dossier" : "Relancer l'analyse"}
          </Button>

          {enCours ? (
            <Button variant="outline" onClick={cancel}>
              Arrêter
            </Button>
          ) : null}

          <p role="status" aria-live="polite" className="text-sm text-muted-foreground">
            {enCours
              ? `Analyse en cours${modeleLance ? ` avec ${labelDe(modeleLance)}` : ""}…`
              : termine
                ? `Analyse terminée${modeleLance ? ` avec ${labelDe(modeleLance)}` : ""}.`
                : status === "cancelled"
                  ? "Analyse interrompue."
                  : status === "error"
                    ? ""
                    : "Aucune analyse lancée pour ce dossier."}
          </p>
        </div>
      </div>

      {error ? (
        <Alert variant="destructive">
          <TriangleAlert aria-hidden="true" />
          <AlertTitle>L&apos;analyse n&apos;a pas abouti</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      {output ? (
        <TriageResultCard output={output} brief={brief} messageSignale={messageSignale} />
      ) : null}

      {lance && !output ? (
        <Card>
          <CardContent>
            <Avancement steps={steps} termine={termine} />
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
