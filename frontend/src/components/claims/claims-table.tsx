/**
 * File d'attente.
 *
 * Deux rendus du meme jeu de donnees : un tableau a partir de `md`, une liste
 * de cartes en dessous. Un tableau a six colonnes retreci sur un telephone
 * devient illisible ; la version mobile est donc concue, pas subie.
 *
 * Une ligne cliquable ouvre la FICHE dossier - une lecture gratuite et
 * deterministe - jamais le triage. Le lancement de la boucle agentique, lui,
 * reste un clic explicite depuis la fiche : trop couteux (plusieurs dizaines de
 * secondes, un appel de modele) pour etre a portee d'un clic distrait sur la
 * file.
 *
 * La colonne "Urgence" est la seule valeur CALCULEE de ce tableau, au milieu
 * de faits lus dans le fichier. Le contrat de claim-flags.tsx s'y etend :
 * ce n'est pas une decision, seulement un ordre de lecture propose. Elle
 * vient en premier parce que la question de cet ecran est "par ou je
 * commence", et qu'une bande verticale de jauges se balaie du regard.
 */

import Link from "next/link";

import { ClaimRowLink } from "@/components/claims/claim-row-link";
import { BlessureFlag, MontantCell, UrgenceCell } from "@/components/claims/claim-flags";
import { SortHeader } from "@/components/claims/sort-header";
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
import type { TriFile } from "@/lib/claims-filter";
import { FORMULE_LABEL, formatDate } from "@/lib/status";
import type { ClaimSummary } from "@/lib/types";

function Signalements({ claim }: { claim: ClaimSummary }) {
  // Le message signale n'apparait plus ici : un message ecarte est une trace du
  // filtre, pas un fait a traiter dans la file. Il est desormais montre, avec sa
  // note, a cote du texte du client sur la fiche dossier (declaration-client.tsx).
  if (claim.blessure !== "oui") {
    return <span className="text-sm text-muted-foreground">—</span>;
  }

  return (
    <div className="flex flex-wrap gap-1.5">
      <BlessureFlag />
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

/**
 * File vide. DEUX messages distincts, et la distinction compte : une file
 * filtree a zero resultat n'est pas une application sans donnees. Les
 * confondre ferait croire a une perte de dossiers.
 */
function FileVide({ filtresActifs }: { filtresActifs: boolean }) {
  return (
    <div className="rounded-lg border border-dashed p-8 text-center">
      <p className="text-sm text-muted-foreground">
        {filtresActifs
          ? "Aucun dossier ne correspond à ces filtres."
          : "Aucun dossier dans les fichiers chargés."}
      </p>
      {filtresActifs ? (
        // Un lien simple suffit : retourner a la page nue retire tous les
        // parametres. Aucun composant client necessaire.
        <Button asChild variant="outline" size="sm" className="mt-4">
          <Link href="/">Réinitialiser les filtres</Link>
        </Button>
      ) : null}
    </div>
  );
}

export function ClaimsTable({
  claims,
  filtresActifs = false,
  tri,
}: {
  claims: ClaimSummary[];
  filtresActifs?: boolean;
  tri: TriFile;
}) {
  if (claims.length === 0) {
    return <FileVide filtresActifs={filtresActifs} />;
  }

  return (
    <>
      {/* Tableau : a partir de md */}
      <div className="hidden overflow-x-auto rounded-lg border md:block">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-44">
                <SortHeader champ="urgence" label="Urgence" tri={tri} />
              </TableHead>
              <TableHead>
                <SortHeader
                  champ="date"
                  label="Sinistre"
                  ariaLabel="date du sinistre"
                  tri={tri}
                />
              </TableHead>
              <TableHead>Assuré</TableHead>
              <TableHead>Type</TableHead>
              <TableHead className="text-right">
                <SortHeader champ="devis" label="Devis" align="right" tri={tri} />
              </TableHead>
              <TableHead>Signalements</TableHead>
              <TableHead className="w-0" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {claims.map((claim) => (
              <ClaimRowLink key={claim.claim_id} href={`/claims/${claim.claim_id}`}>
                <TableCell>
                  <UrgenceCell
                    urgence={claim.urgence_estimee}
                    motifs={claim.urgence_motifs}
                  />
                </TableCell>
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
              </ClaimRowLink>
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

                <UrgenceCell
                  urgence={claim.urgence_estimee}
                  motifs={claim.urgence_motifs}
                />

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
