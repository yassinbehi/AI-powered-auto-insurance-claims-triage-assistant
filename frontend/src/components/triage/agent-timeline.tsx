"use client";

import { ChevronRight, CircleCheck, LoaderCircle, Wrench } from "lucide-react";
import * as React from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { TOOL_LABEL } from "@/lib/status";
import type { TimelineToolCall, TimelineTurn } from "@/hooks/use-triage-stream";
import { cn } from "@/lib/utils";

function ToolCallItem({ call }: { call: TimelineToolCall }) {
  const [ouvert, setOuvert] = React.useState(false);
  const enCours = call.output === null;
  const enErreur = call.output !== null && "error" in call.output;

  return (
    <Collapsible open={ouvert} onOpenChange={setOuvert}>
      <Card
        className={cn(
          "gap-0 py-0 transition-opacity",
          // Apparition sobre, desactivee si l'utilisateur a demande moins de
          // mouvement.
          "motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-bottom-1",
        )}
      >
        <CollapsibleTrigger className="flex w-full items-center gap-2 rounded-lg p-3 text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring">
          <ChevronRight
            className={cn(
              "size-4 shrink-0 text-muted-foreground transition-transform",
              ouvert && "rotate-90",
            )}
            aria-hidden="true"
          />
          <Wrench className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
          <span className="min-w-0 flex-1 truncate text-sm font-medium">
            {TOOL_LABEL[call.tool] ?? call.tool}
          </span>
          {enCours ? (
            <LoaderCircle className="size-4 animate-spin text-muted-foreground" aria-hidden="true" />
          ) : enErreur ? (
            <Badge variant="destructive">Erreur</Badge>
          ) : (
            <CircleCheck className="size-4 text-success" aria-hidden="true" />
          )}
          <span className="sr-only">
            {enCours ? "en cours" : enErreur ? "terminé en erreur" : "terminé"}
          </span>
        </CollapsibleTrigger>

        <CollapsibleContent>
          <CardContent className="space-y-3 border-t p-3">
            <div className="space-y-1">
              <p className="text-xs font-medium text-muted-foreground">Entrée</p>
              <pre className="overflow-x-auto rounded-md bg-muted p-2 font-mono text-xs">
                {JSON.stringify(call.input, null, 2)}
              </pre>
            </div>
            {call.output ? (
              <div className="space-y-1">
                <p className="text-xs font-medium text-muted-foreground">Sortie</p>
                <pre className="max-h-64 overflow-auto rounded-md bg-muted p-2 font-mono text-xs">
                  {JSON.stringify(call.output, null, 2)}
                </pre>
              </div>
            ) : null}
          </CardContent>
        </CollapsibleContent>
      </Card>
    </Collapsible>
  );
}

/**
 * Deroule de la boucle d'outils, tour par tour.
 *
 * Les appels d'un MEME tour sont poses cote a cote : le system prompt impose
 * d'emettre check_coverage, estimate_repair_band et detect_fraud_signals
 * ensemble, et cette simultaneite doit se voir. Les empiler verticalement
 * donnerait l'impression d'appels successifs.
 */
export function AgentTimeline({ turns }: { turns: TimelineTurn[] }) {
  if (turns.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Le déroulé des appels d&apos;outils apparaîtra ici.
      </p>
    );
  }

  return (
    <ol className="space-y-6">
      {turns.map((turn) => (
        <li key={turn.turn} className="space-y-2">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-medium">Tour {turn.turn}</h3>
            {turn.toolCalls.length > 1 ? (
              <Badge variant="secondary">{turn.toolCalls.length} appels en parallèle</Badge>
            ) : null}
            {!turn.completed ? (
              <LoaderCircle
                className="size-3.5 animate-spin text-muted-foreground"
                aria-hidden="true"
              />
            ) : null}
          </div>

          {turn.toolCalls.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              {turn.completed
                ? "Réponse du modèle, sans appel d'outil."
                : "Le modèle réfléchit…"}
            </p>
          ) : (
            <div
              className={cn(
                "grid gap-2",
                turn.toolCalls.length > 1 && "md:grid-cols-2 xl:grid-cols-3",
              )}
            >
              {turn.toolCalls.map((call) => (
                <ToolCallItem key={call.key} call={call} />
              ))}
            </div>
          )}
        </li>
      ))}
    </ol>
  );
}
