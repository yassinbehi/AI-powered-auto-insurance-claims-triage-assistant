"use client";

import { CircleAlert, CircleCheck, CircleSlash, TriangleAlert, UserCheck } from "lucide-react";

import { RawJsonDialog } from "@/components/result/raw-json-dialog";
import { RepairRangeBar } from "@/components/result/repair-range-bar";
import { ChipList } from "@/components/status/chip-list";
import { PriorityBadge, TriageBadge } from "@/components/status/domain-badges";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { MESSAGE_CLIENT_MAX_MOTS, countWords, signalLabel } from "@/lib/status";
import type { TriageOutput } from "@/lib/types";
import { cn } from "@/lib/utils";

function Section({
  titre,
  children,
  className,
}: {
  titre: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("space-y-1.5", className)}>
      <h3 className="text-xs font-medium text-muted-foreground">{titre}</h3>
      {children}
    </div>
  );
}

/**
 * Bandeau de validation humaine.
 *
 * Il est en tete de carte et non en bas : c'est la seule information qui
 * change ce qu'un gestionnaire doit FAIRE du dossier. contrat_sortie.md
 * l'impose pour suspicion_fraude, hors_garantie, montant > 5000 TND, blessure
 * ou rejet.
 */
function HumanValidationAlert({ requise }: { requise: boolean }) {
  if (!requise) {
    return (
      <Alert>
        <CircleCheck aria-hidden="true" />
        <AlertTitle>Validation humaine non requise</AlertTitle>
        <AlertDescription>
          Aucune des conditions du contrat de sortie n&apos;est réunie. Le dossier reste
          néanmoins une recommandation, jamais une décision appliquée.
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <Alert variant="destructive">
      <UserCheck aria-hidden="true" />
      <AlertTitle>Validation humaine requise</AlertTitle>
      <AlertDescription>
        Ce dossier ne peut pas avancer sans qu&apos;un gestionnaire le reprenne.
      </AlertDescription>
    </Alert>
  );
}

function ClientMessageBlock({ message }: { message: string }) {
  const mots = countWords(message);
  const tropLong = mots > MESSAGE_CLIENT_MAX_MOTS;

  return (
    <Section titre="Message client">
      <blockquote className="border-l-2 pl-3 text-sm">{message}</blockquote>
      <p className={cn("text-xs", tropLong ? "text-warning" : "text-muted-foreground")}>
        {mots} mots{tropLong ? ` — au-delà de la limite de ${MESSAGE_CLIENT_MAX_MOTS}` : ""}
      </p>
    </Section>
  );
}

/**
 * Les erreurs de validation s'affichent A COTE du resultat, jamais a la place.
 *
 * agent._finalize_result renvoie les deux ensemble : une sortie produite mais
 * non conforme reste une sortie, et c'est precisement le cas qu'il faut
 * pouvoir examiner. La masquer reviendrait a cacher la piece a conviction.
 */
export function ValidationErrorsAlert({ errors }: { errors: string[] }) {
  if (errors.length === 0) return null;

  return (
    <Alert variant="destructive">
      <TriangleAlert aria-hidden="true" />
      <AlertTitle>
        {errors.length === 1
          ? "1 écart au contrat de sortie"
          : `${errors.length} écarts au contrat de sortie`}
      </AlertTitle>
      <AlertDescription>
        <ul className="list-disc space-y-1 pl-4">
          {errors.map((error) => (
            <li key={error}>{error}</li>
          ))}
        </ul>
      </AlertDescription>
    </Alert>
  );
}

export function TriageResultCard({ output }: { output: TriageOutput }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Résultat du triage</CardTitle>
        <div className="flex flex-wrap items-center gap-2">
          <TriageBadge triage={output.triage} />
          <PriorityBadge priorite={output.priorite} />
          <RawJsonDialog value={output} />
        </div>
      </CardHeader>

      <CardContent className="space-y-5">
        <HumanValidationAlert requise={output.validation_humaine_requise} />

        <div className="flex items-center gap-2 text-sm">
          {output.garantie_applicable ? (
            <CircleCheck className="size-4 text-success" aria-hidden="true" />
          ) : (
            <CircleSlash className="size-4 text-destructive" aria-hidden="true" />
          )}
          {output.garantie_applicable
            ? "Garantie applicable"
            : "Garantie non applicable à ce sinistre"}
        </div>

        <Separator />

        <div className="grid gap-5 sm:grid-cols-2">
          <Section titre="Pièces manquantes">
            <ChipList items={output.pieces_manquantes} emptyLabel="Aucune pièce manquante" />
          </Section>
          <Section titre="Signaux de fraude">
            <ChipList
              items={output.signaux_fraude.map(signalLabel)}
              emptyLabel="Aucun signal"
              icon={CircleAlert}
            />
          </Section>
        </div>

        <Section titre="Fourchette de réparation estimée">
          <RepairRangeBar
            min={output.fourchette_reparation_tnd?.min ?? 0}
            max={output.fourchette_reparation_tnd?.max ?? 0}
          />
        </Section>

        <Separator />

        <Section titre="Prochaine action">
          <p className="text-sm">{output.prochaine_action}</p>
        </Section>

        <ClientMessageBlock message={output.message_client} />
      </CardContent>
    </Card>
  );
}
