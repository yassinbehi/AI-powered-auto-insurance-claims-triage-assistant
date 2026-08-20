/**
 * Ce que le backend calcule SANS le modele : couverture, fourchette de
 * reparation, signaux de fraude. Trois cartes soeurs, jamais imbriquees.
 *
 * Ce panneau existe autant pour informer que pour montrer la frontiere : tout
 * ce qui est ici est deterministe, reproductible et gratuit. Ce qui vient
 * ensuite du triage est une appreciation du modele, qui reste a valider par un
 * humain.
 */

import { CircleAlert, CircleCheck, CircleSlash, Microscope } from "lucide-react";

import { StatusBadge } from "@/components/status/status-badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import {
  BANDE_META,
  NATURE_META,
  SEUIL_EXPERTISE_TND,
  formatTnd,
  signalLabel,
} from "@/lib/status";
import type { CoverageResult, FraudSignalsResult, RepairBandResult } from "@/lib/types";

export function CoverageCard({ coverage }: { coverage: CoverageResult }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Couverture</CardTitle>
        <StatusBadge
          tone={coverage.garantie_applicable ? "success" : "destructiveSoft"}
          icon={coverage.garantie_applicable ? CircleCheck : CircleSlash}
          label={coverage.garantie_applicable ? "Garantie applicable" : "Hors garantie"}
        />
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex items-baseline justify-between gap-4 text-sm">
          <span className="text-muted-foreground">Garantie recherchée</span>
          <span className="font-mono">{coverage.garantie_recherchee}</span>
        </div>
        <p className="text-sm text-muted-foreground">{coverage.raison}</p>

        {coverage.verification_humaine_recommandee ? (
          <Alert>
            <CircleAlert aria-hidden="true" />
            <AlertTitle>Vérification humaine recommandée</AlertTitle>
            <AlertDescription>
              La question du conducteur et de l&apos;usage ne peut pas être tranchée
              automatiquement pour cette formule.
            </AlertDescription>
          </Alert>
        ) : null}
      </CardContent>
    </Card>
  );
}

export function RepairBandCard({ repairBand }: { repairBand: RepairBandResult }) {
  const bande = BANDE_META[repairBand.bande] ?? { label: repairBand.bande, tone: "neutral" as const };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Fourchette de réparation</CardTitle>
        <Badge variant="outline">{bande.label}</Badge>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-2xl font-semibold tabular-nums">
          {formatTnd(repairBand.borne_inf)} – {formatTnd(repairBand.borne_sup)}
        </p>
        <p className="text-sm text-muted-foreground">
          Estimée à partir du devis de {formatTnd(repairBand.devis_tnd)}. Ce n&apos;est pas
          un montant d&apos;indemnisation.
        </p>

        {repairBand.expertise_obligatoire ? (
          <Alert>
            <Microscope aria-hidden="true" />
            <AlertTitle>Expertise obligatoire</AlertTitle>
            <AlertDescription>
              Devis supérieur à {formatTnd(SEUIL_EXPERTISE_TND)}.
            </AlertDescription>
          </Alert>
        ) : null}
      </CardContent>
    </Card>
  );
}

export function FraudSignalsCard({ fraudSignals }: { fraudSignals: FraudSignalsResult }) {
  const natures = fraudSignals.details.nature_des_signaux ?? {};

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Signaux relevés</CardTitle>
        <Badge variant={fraudSignals.signaux_fraude.length > 0 ? "warning" : "secondary"}>
          {fraudSignals.signaux_fraude.length}
        </Badge>
      </CardHeader>
      <CardContent className="space-y-4">
        {fraudSignals.signaux_fraude.length === 0 ? (
          <p className="text-sm text-muted-foreground">Aucun signal relevé.</p>
        ) : (
          <ul className="space-y-2">
            {fraudSignals.signaux_fraude.map((signal) => {
              const nature = natures[signal];
              const natureMeta = nature ? NATURE_META[nature] : null;
              return (
                <li key={signal} className="flex flex-wrap items-center gap-2 text-sm">
                  <span>{signalLabel(signal)}</span>
                  {natureMeta ? (
                    <Badge variant="outline">
                      <natureMeta.Icon aria-hidden="true" />
                      {natureMeta.label}
                    </Badge>
                  ) : null}
                </li>
              );
            })}
          </ul>
        )}

        <p className="text-xs text-muted-foreground">
          Ces signaux sont des observations. Ils ne concluent pas à une fraude.
        </p>

        {fraudSignals.signaux_non_evaluables.length > 0 ? (
          <>
            <Separator />
            <div className="space-y-1.5">
              <p className="text-xs font-medium text-muted-foreground">
                Non évaluables faute de données
              </p>
              <ul className="space-y-1">
                {fraudSignals.signaux_non_evaluables.map((signal) => (
                  <li key={signal} className="text-xs text-muted-foreground">
                    {signal}
                  </li>
                ))}
              </ul>
            </div>
          </>
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
  return (
    <section className="space-y-3">
      <div className="space-y-1">
        <h2 className="text-lg font-semibold tracking-tight">Analyse déterministe</h2>
        <p className="text-sm text-muted-foreground">
          Calculée en Python à partir des règles du dossier. Aucun appel de modèle, résultat
          reproductible.
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
