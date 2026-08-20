"use client";

import { LoaderCircle, Play, Square, TriangleAlert } from "lucide-react";

import { RawStreamPane } from "@/components/triage/raw-stream-pane";
import { AgentTimeline } from "@/components/triage/agent-timeline";
import {
  TriageResultCard,
  ValidationErrorsAlert,
} from "@/components/result/triage-result-card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useTriageStream } from "@/hooks/use-triage-stream";

function texteDeStatut(
  status: ReturnType<typeof useTriageStream>["status"],
  tours: number,
): string {
  switch (status) {
    case "idle":
      return "Prêt à lancer le triage.";
    case "running":
      return tours === 0 ? "Triage lancé, en attente du modèle." : `Triage en cours, tour ${tours}.`;
    case "done":
      return "Triage terminé.";
    case "cancelled":
      return "Suivi interrompu.";
    case "error":
      return "Le triage a échoué.";
  }
}

export function TriageRunView({ claimId }: { claimId: string }) {
  const { status, turns, text, result, error, start, cancel } = useTriageStream(claimId);

  const enCours = status === "running";
  const statut = texteDeStatut(status, turns.length);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={start} disabled={enCours}>
          {enCours ? (
            <LoaderCircle className="animate-spin" aria-hidden="true" />
          ) : (
            <Play aria-hidden="true" />
          )}
          {status === "idle" ? "Lancer le triage" : "Relancer le triage"}
        </Button>

        {enCours ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="outline" onClick={cancel}>
                <Square aria-hidden="true" />
                Arrêter le suivi
              </Button>
            </TooltipTrigger>
            <TooltipContent className="max-w-xs">
              Ferme le flux côté navigateur. L&apos;appel de modèle déjà engagé se termine
              sur le serveur : il est payé, l&apos;interrompre à mi-chemin ne rendrait rien.
            </TooltipContent>
          </Tooltip>
        ) : null}

        {/* Progression annoncee par jalons. Le flux brut, lui, est en
            aria-live="off" : l'annoncer fragment par fragment rendrait la page
            inutilisable au lecteur d'ecran. */}
        <p role="status" aria-live="polite" className="text-sm text-muted-foreground">
          {statut}
        </p>
      </div>

      {error ? (
        <Alert variant="destructive">
          <TriangleAlert aria-hidden="true" />
          <AlertTitle>Le triage n&apos;a pas abouti</AlertTitle>
          <AlertDescription className="space-y-2">
            <p>{error.message}</p>
            {error.rawOutput ? (
              <>
                <p className="text-xs">Réponse brute du modèle :</p>
                <pre className="max-h-48 w-full overflow-auto rounded-md bg-muted p-3 font-mono text-xs text-foreground">
                  {error.rawOutput}
                </pre>
              </>
            ) : null}
          </AlertDescription>
        </Alert>
      ) : null}

      {result?.output ? <TriageResultCard output={result.output} /> : null}
      {result ? <ValidationErrorsAlert errors={result.validation_errors} /> : null}

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Déroulé de l&apos;agent</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <AgentTimeline turns={turns} />
          {status !== "idle" ? <RawStreamPane text={text} /> : null}
        </CardContent>
      </Card>
    </div>
  );
}
