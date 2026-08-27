/**
 * Historique des analyses.
 *
 * Meme parti pris que la file d'attente : un tableau a partir de `md`, des
 * cartes en dessous. Un tableau a six colonnes retreci sur un telephone
 * devient illisible.
 *
 * Ce que cet ecran doit repondre, dans l'ordre : quand, quel dossier, quelle
 * conclusion, et ce que ca a coute. Le modele utilise vient en dernier - il
 * n'interesse que si l'on compare deux analyses du meme dossier.
 *
 * LES ECHECS Y FIGURENT, avec leur cout. Une analyse interrompue a ete
 * facturee comme une autre, et un historique qui ne montrerait que les
 * reussites donnerait une image fausse de la depense.
 */

import { TriangleAlert } from "lucide-react";
import Link from "next/link";

import { ClaimRowLink } from "@/components/claims/claim-row-link";
import { PriorityBadge, TriageBadge } from "@/components/status/domain-badges";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatDateHeure, formatUsd } from "@/lib/status";
import type { AnalyseResume } from "@/lib/types";

/** Conclusion de l'analyse, ou la raison de son echec. */
function Conclusion({ analyse }: { analyse: AnalyseResume }) {
  if (analyse.triage === null) {
    return (
      <span className="flex items-center gap-1.5 text-sm text-muted-foreground">
        <TriangleAlert className="size-4 shrink-0 text-destructive" aria-hidden="true" />
        N&apos;a pas abouti
      </span>
    );
  }
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <TriageBadge triage={analyse.triage} />
      {analyse.priorite ? <PriorityBadge priorite={analyse.priorite} /> : null}
    </div>
  );
}

function Vide() {
  return (
    <Card>
      <CardContent className="py-10 text-center">
        <p className="font-medium">Aucune analyse conservée</p>
        <p className="mt-1 text-sm text-muted-foreground">
          Les analyses lancées depuis un dossier apparaîtront ici, avec leur
          conclusion et leur coût.
        </p>
        <Button asChild variant="outline" size="sm" className="mt-4">
          <Link href="/">Aller à la file d&apos;attente</Link>
        </Button>
      </CardContent>
    </Card>
  );
}

export function AnalysesTable({ analyses }: { analyses: AnalyseResume[] }) {
  if (analyses.length === 0) return <Vide />;

  return (
    <>
      <Card className="hidden overflow-hidden py-0 md:block">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Analysé le</TableHead>
              <TableHead>Dossier</TableHead>
              <TableHead>Jeu de données</TableHead>
              <TableHead>Conclusion</TableHead>
              <TableHead className="text-right">Coût</TableHead>
              <TableHead className="w-24" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {analyses.map((analyse) => (
              <ClaimRowLink key={analyse.id} href={`/analyses/${analyse.id}`}>
                <TableCell className="whitespace-nowrap text-muted-foreground">
                  {formatDateHeure(analyse.analyse_le)}
                </TableCell>
                <TableCell className="font-medium">{analyse.claim_id}</TableCell>
                <TableCell className="max-w-[14rem] truncate text-muted-foreground">
                  {analyse.dataset_nom || "—"}
                </TableCell>
                <TableCell>
                  <Conclusion analyse={analyse} />
                </TableCell>
                <TableCell className="text-right font-mono tabular-nums text-muted-foreground">
                  {formatUsd(analyse.cost_usd)}
                </TableCell>
                <TableCell className="text-right">
                  <Button asChild variant="ghost" size="sm">
                    <Link href={`/analyses/${analyse.id}`}>Relire</Link>
                  </Button>
                </TableCell>
              </ClaimRowLink>
            ))}
          </TableBody>
        </Table>
      </Card>

      <ul className="space-y-3 md:hidden">
        {analyses.map((analyse) => (
          <li key={analyse.id}>
            <Card>
              <CardContent className="space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="font-medium">{analyse.claim_id}</p>
                    <p className="truncate text-xs text-muted-foreground">
                      {formatDateHeure(analyse.analyse_le)} · {analyse.dataset_nom || "—"}
                    </p>
                  </div>
                  <span className="shrink-0 font-mono text-sm tabular-nums text-muted-foreground">
                    {formatUsd(analyse.cost_usd)}
                  </span>
                </div>
                <Conclusion analyse={analyse} />
                <Button asChild variant="outline" size="sm" className="w-full">
                  <Link href={`/analyses/${analyse.id}`}>Relire l&apos;analyse</Link>
                </Button>
              </CardContent>
            </Card>
          </li>
        ))}
      </ul>
    </>
  );
}
