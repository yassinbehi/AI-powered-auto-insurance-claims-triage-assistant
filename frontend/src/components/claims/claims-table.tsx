/**
 * File d'attente.
 *
 * Deux rendus du meme jeu de donnees : un tableau a partir de `md`, une liste
 * de cartes en dessous. Un tableau a six colonnes retreci sur un telephone
 * devient illisible ; la version mobile est donc concue, pas subie.
 *
 * Le lancement d'un triage ne figure pas ici : il part de la fiche dossier.
 * Une ligne de tableau cliquable qui declencherait une boucle agentique de
 * plusieurs dizaines de secondes serait trop facile a atteindre par erreur.
 */

import Link from "next/link";

import { BlessureFlag, InjectionFlag, MontantCell } from "@/components/claims/claim-flags";
import { TypeSinistreBadge } from "@/components/status/domain-badges";
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
import { FORMULE_LABEL, formatDate } from "@/lib/status";
import type { ClaimSummary } from "@/lib/types";

function Signalements({ claim }: { claim: ClaimSummary }) {
  const aDesSignalements =
    claim.blessure === "oui" || claim.injection_markers_found.length > 0;

  if (!aDesSignalements) {
    return <span className="text-sm text-muted-foreground">—</span>;
  }

  return (
    <div className="flex flex-wrap gap-1.5">
      {claim.blessure === "oui" ? <BlessureFlag /> : null}
      {claim.injection_markers_found.length > 0 ? (
        <InjectionFlag markers={claim.injection_markers_found} />
      ) : null}
    </div>
  );
}

function Assure({ claim }: { claim: ClaimSummary }) {
  return (
    <div className="min-w-0">
      <p className="truncate">{claim.assure ?? "—"}</p>
      <p className="truncate text-xs text-muted-foreground">
        {claim.vehicule ?? "—"}
        {claim.formule ? ` · ${FORMULE_LABEL[claim.formule] ?? claim.formule}` : ""}
      </p>
    </div>
  );
}

export function ClaimsTable({ claims }: { claims: ClaimSummary[] }) {
  return (
    <>
      {/* Tableau : a partir de md */}
      <div className="hidden overflow-x-auto rounded-lg border md:block">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Sinistre</TableHead>
              <TableHead>Assuré</TableHead>
              <TableHead>Type</TableHead>
              <TableHead className="text-right">Devis</TableHead>
              <TableHead>Signalements</TableHead>
              <TableHead className="w-0" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {claims.map((claim) => (
              <TableRow key={claim.claim_id}>
                <TableCell>
                  <p className="font-mono font-medium">{claim.claim_id}</p>
                  <p className="text-xs text-muted-foreground tabular-nums">
                    {formatDate(claim.date_sinistre)}
                  </p>
                </TableCell>
                <TableCell className="max-w-56">
                  <Assure claim={claim} />
                </TableCell>
                <TableCell>
                  <TypeSinistreBadge type={claim.type_sinistre} />
                </TableCell>
                <TableCell className="text-right">
                  <MontantCell devisTnd={claim.devis_tnd} />
                </TableCell>
                <TableCell>
                  <Signalements claim={claim} />
                </TableCell>
                <TableCell className="text-right">
                  <Button asChild variant="ghost" size="sm">
                    <Link href={`/claims/${claim.claim_id}`}>
                      Ouvrir
                      <span className="sr-only"> le dossier {claim.claim_id}</span>
                    </Link>
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Cartes : en dessous de md */}
      <ul className="space-y-3 md:hidden">
        {claims.map((claim) => (
          <li key={claim.claim_id}>
            <Card>
              <CardContent className="space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-mono font-medium">{claim.claim_id}</p>
                    <p className="text-xs text-muted-foreground tabular-nums">
                      {formatDate(claim.date_sinistre)}
                    </p>
                  </div>
                  <TypeSinistreBadge type={claim.type_sinistre} />
                </div>

                <Assure claim={claim} />

                <div className="flex items-center justify-between gap-3">
                  <MontantCell devisTnd={claim.devis_tnd} className="text-sm" />
                  <Signalements claim={claim} />
                </div>

                <Button asChild variant="outline" size="sm" className="w-full">
                  <Link href={`/claims/${claim.claim_id}`}>
                    Ouvrir le dossier
                    <span className="sr-only"> {claim.claim_id}</span>
                  </Link>
                </Button>
              </CardContent>
            </Card>
          </li>
        ))}
      </ul>
    </>
  );
}
