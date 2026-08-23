"use client";

import { CircleCheck, CircleSlash, FileText, ListChecks, Mail, UserCheck } from "lucide-react";

import { CopyButton } from "@/components/result/copy-button";
import { ChipList } from "@/components/status/chip-list";
import { PriorityBadge, TriageBadge } from "@/components/status/domain-badges";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { formatTnd, signalLabel } from "@/lib/status";
import type { TriageOutput } from "@/lib/types";

/**
 * Le resultat d'un triage, tel qu'un gestionnaire de sinistres doit le lire.
 *
 * Le sinistre en bref vient d'abord : on ne peut pas juger une prochaine
 * action sans savoir de quel dossier il s'agit. Viennent ensuite les deux
 * blocs qui portent la valeur de l'ecran - les prochaines etapes et le message
 * a envoyer au client. Le reste (couverture, montants, anomalies) sert a les
 * justifier et vient apres.
 *
 * `brief` est fabrique par la page cote serveur et seulement affiche ici : son
 * contenu est lu dans les fichiers deposes, pas produit par le modele.
 *
 * Ce qui n'aide pas a traiter le dossier n'est pas affiche : trace des
 * outils, JSON du contrat, ecarts de schema, tokens consommes. Tout cela part
 * dans la console (lib/dev-log.ts).
 */

function BlocPrincipal({
  icon: Icon,
  titre,
  action,
  children,
}: {
  icon: typeof Mail;
  titre: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-lg border bg-muted/30 p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h3 className="flex items-center gap-2 text-sm font-semibold">
          <Icon className="size-4 text-muted-foreground" aria-hidden="true" />
          {titre}
        </h3>
        {action}
      </div>
      {children}
    </section>
  );
}

function ValidationHumaine({ requise }: { requise: boolean }) {
  if (!requise) return null;

  return (
    <Alert variant="destructive">
      <UserCheck aria-hidden="true" />
      <AlertTitle>À faire valider avant d&apos;envoyer</AlertTitle>
      <AlertDescription>
        Ce dossier ne peut pas être clôturé sur cette seule analyse. Faites-le relire par un
        responsable avant toute réponse au client.
      </AlertDescription>
    </Alert>
  );
}

export function TriageResultCard({
  output,
  brief,
}: {
  output: TriageOutput;
  brief?: React.ReactNode;
}) {
  const fourchette = output.fourchette_reparation_tnd;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Résultat de l&apos;analyse</CardTitle>
        <div className="flex flex-wrap items-center gap-2">
          <TriageBadge triage={output.triage} />
          <PriorityBadge priorite={output.priorite} />
        </div>
      </CardHeader>

      <CardContent className="space-y-5">
        <ValidationHumaine requise={output.validation_humaine_requise} />

        {brief ? (
          <BlocPrincipal icon={FileText} titre="Le sinistre en bref">
            {brief}
          </BlocPrincipal>
        ) : null}

        <BlocPrincipal icon={ListChecks} titre="Prochaines étapes">
          <p className="text-sm leading-relaxed">{output.prochaine_action}</p>

          {output.pieces_manquantes.length > 0 ? (
            <div className="mt-3 space-y-1.5">
              <p className="text-xs font-medium text-muted-foreground">
                Pièces à réclamer au client
              </p>
              <ChipList items={output.pieces_manquantes} />
            </div>
          ) : null}
        </BlocPrincipal>

        <BlocPrincipal
          icon={Mail}
          titre="Message à envoyer au client"
          action={<CopyButton value={output.message_client} label="Copier le message" />}
        >
          <p className="text-sm leading-relaxed whitespace-pre-line">{output.message_client}</p>
        </BlocPrincipal>

        <Separator />

        <dl className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1">
            <dt className="text-xs font-medium text-muted-foreground">Couverture</dt>
            <dd className="flex items-center gap-2 text-sm">
              {output.garantie_applicable ? (
                <>
                  <CircleCheck className="size-4 text-success" aria-hidden="true" />
                  Sinistre couvert par le contrat
                </>
              ) : (
                <>
                  <CircleSlash className="size-4 text-destructive" aria-hidden="true" />
                  Sinistre non couvert par le contrat
                </>
              )}
            </dd>
          </div>

          <div className="space-y-1">
            <dt className="text-xs font-medium text-muted-foreground">
              Coût estimé des réparations
            </dt>
            <dd className="text-sm tabular-nums">
              {formatTnd(fourchette?.min ?? 0)} à {formatTnd(fourchette?.max ?? 0)}
            </dd>
          </div>
        </dl>

        {output.signaux_fraude.length > 0 ? (
          <div className="space-y-1.5">
            <p className="text-xs font-medium text-muted-foreground">Points de vigilance</p>
            <ChipList items={output.signaux_fraude.map(signalLabel)} />
            <p className="text-xs text-muted-foreground">
              Ce sont des observations à vérifier, pas une conclusion.
            </p>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
