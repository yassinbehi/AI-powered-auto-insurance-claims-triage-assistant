"use client";

import { CircleAlert, CircleCheck, CircleSlash, Microscope } from "lucide-react";
import * as React from "react";

import { ChipList } from "@/components/status/chip-list";
import { StatusBadge } from "@/components/status/status-badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { devGroup } from "@/lib/dev-log";
import { BANDE_META, SEUIL_EXPERTISE_TND, formatTnd, signalLabel } from "@/lib/status";
import type { CoverageResult, FraudSignalsResult, RepairBandResult } from "@/lib/types";

/**
 * Verifications faites a partir du contrat et de la declaration, avant toute
 * analyse par le modele.
 *
 * Formule en langage de gestion, pas de developpement : ni nom de garantie
 * technique, ni nature de signal, ni liste des controles impossibles faute de
 * colonne dans le CSV. Ces elements partent dans la console.
 */

function CoverageCard({ coverage }: { coverage: CoverageResult }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Couverture</CardTitle>
        <StatusBadge
          tone={coverage.garantie_applicable ? "success" : "destructiveSoft"}
          icon={coverage.garantie_applicable ? CircleCheck : CircleSlash}
          label={coverage.garantie_applicable ? "Couvert" : "Non couvert"}
        />
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-muted-foreground">{coverage.raison}</p>

        {coverage.verification_humaine_recommandee ? (
          <Alert>
            <CircleAlert aria-hidden="true" />
            <AlertTitle>À vérifier manuellement</AlertTitle>
            <AlertDescription>
              La question du conducteur et de l&apos;usage du véhicule ne peut pas être
              tranchée automatiquement sur ce type de contrat.
            </AlertDescription>
          </Alert>
        ) : null}
      </CardContent>
    </Card>
  );
}

function RepairBandCard({ repairBand }: { repairBand: RepairBandResult }) {
  const bande = BANDE_META[repairBand.bande];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Coût des réparations</CardTitle>
        {bande ? <Badge variant="outline">{bande.label}</Badge> : null}
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-2xl font-semibold tabular-nums">
          {formatTnd(repairBand.borne_inf)} à {formatTnd(repairBand.borne_sup)}
        </p>
        <p className="text-sm text-muted-foreground">
          Estimation à partir du devis de {formatTnd(repairBand.devis_tnd)}. Ce n&apos;est pas
          un montant d&apos;indemnisation.
        </p>

        {repairBand.expertise_obligatoire ? (
          <Alert>
            <Microscope aria-hidden="true" />
            <AlertTitle>Expertise obligatoire</AlertTitle>
            <AlertDescription>
              Le devis dépasse {formatTnd(SEUIL_EXPERTISE_TND)}.
            </AlertDescription>
          </Alert>
        ) : null}
      </CardContent>
    </Card>
  );
}

function FraudSignalsCard({ fraudSignals }: { fraudSignals: FraudSignalsResult }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Points de vigilance</CardTitle>
        <Badge variant={fraudSignals.signaux_fraude.length > 0 ? "warning" : "secondary"}>
          {fraudSignals.signaux_fraude.length}
        </Badge>
      </CardHeader>
      <CardContent className="space-y-3">
        <ChipList
          items={fraudSignals.signaux_fraude.map(signalLabel)}
          emptyLabel="Rien à signaler sur ce dossier."
        />
        {fraudSignals.signaux_fraude.length > 0 ? (
          <p className="text-xs text-muted-foreground">
            Ce sont des observations à vérifier, pas une conclusion.
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

export function DeterministicAnalysis({
  coverage,
  repairBand,
  fraudSignals,
}: {
  coverage: CoverageResult;
  repairBand: RepairBandResult;
  fraudSignals: FraudSignalsResult;
}) {
  React.useEffect(() => {
    devGroup(`vérifications · ${coverage.claim_id}`, { coverage, repairBand, fraudSignals });
  }, [coverage, repairBand, fraudSignals]);

  return (
    <section className="space-y-3">
      <div className="space-y-1">
        <h2 className="text-lg font-semibold tracking-tight">Vérifications du dossier</h2>
        <p className="text-sm text-muted-foreground">
          Établies à partir du contrat et de la déclaration, avant l&apos;analyse.
        </p>
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <CoverageCard coverage={coverage} />
        <RepairBandCard repairBand={repairBand} />
        <FraudSignalsCard fraudSignals={fraudSignals} />
      </div>
    </section>
  );
}
