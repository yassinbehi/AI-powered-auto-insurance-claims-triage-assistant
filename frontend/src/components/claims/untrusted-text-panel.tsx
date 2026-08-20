"use client";

import { LoaderCircle, ShieldAlert } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { ScreeningBadge } from "@/components/status/domain-badges";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { ApiBusyError, runScreening } from "@/lib/api-client";
import { VERDICT_META, verdictKey } from "@/lib/status";
import type { Screening } from "@/lib/types";

/**
 * Le texte redige par le client, mis en quarantaine visuelle.
 *
 * Ce composant est le pendant, dans l'interface, de la barriere que
 * backend/src/guard.py pose dans le pipeline : le texte du client n'est pas un
 * champ de dossier comme un autre, et il ne doit pas en avoir l'air.
 *
 * La quarantaine est exprimee par un CONTOUR EN TIRETS, utilise nulle part
 * ailleurs dans l'application, plus une icone et un intitule explicite. Pas de
 * hachures ni d'effet decoratif : le tiret est un signal, et il ne signifie
 * que cela.
 *
 * Ce qui est affiche est `text_for_model`, VERBATIM - y compris ses balises
 * <donnee_client_non_fiable>. C'est exactement l'octet que le modele de triage
 * recoit. Afficher une version nettoyee pour faire joli ferait mentir le
 * panneau sur ce qu'il documente.
 */
export function UntrustedTextPanel({
  claimId,
  screening: screeningInitial,
}: {
  claimId: string;
  screening: Screening;
}) {
  const [screening, setScreening] = React.useState(screeningInitial);
  const [enCours, setEnCours] = React.useState(false);

  const meta = VERDICT_META[verdictKey(screening.verdict)];

  async function executerFiltreComplet() {
    setEnCours(true);
    try {
      const resultat = await runScreening(claimId);
      setScreening(resultat);
      toast.success(`Filtre exécuté : ${VERDICT_META[verdictKey(resultat.verdict)].label}`);
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      toast.error(
        e instanceof ApiBusyError ? "Un travail de modèle est déjà en cours." : message,
      );
    } finally {
      setEnCours(false);
    }
  }

  return (
    <Card className="border-dashed bg-muted/40">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <ShieldAlert className="size-4 text-muted-foreground" aria-hidden="true" />
          Donnée client non fiable
        </CardTitle>
        <div className="flex flex-wrap items-center gap-2">
          <ScreeningBadge verdict={screening.verdict} />
          {screening.classifier_available ? null : (
            <Badge variant="warning">Classifieur indisponible</Badge>
          )}
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        <p className="text-xs text-muted-foreground">{meta.hint}</p>

        <div className="space-y-1.5">
          <p className="text-xs font-medium">Ce que le modèle reçoit, verbatim</p>
          <pre className="overflow-x-auto rounded-md border bg-background p-3 font-mono text-xs leading-relaxed whitespace-pre-wrap">
            {screening.text_for_model}
          </pre>
          {screening.redacted ? (
            <p className="text-xs text-muted-foreground">
              Le texte d&apos;origine a été retiré avant d&apos;atteindre le modèle et
              n&apos;est pas exposé par l&apos;API. Le dossier doit être traité à partir des
              seuls champs structurés.
            </p>
          ) : null}
        </div>

        {screening.markers_found.length > 0 ? (
          <>
            <Separator />
            <div className="space-y-1.5">
              <p className="text-xs font-medium">
                Marqueurs détectés par la couche 1 (analyse déterministe, sans appel de
                modèle)
              </p>
              <ul className="flex flex-wrap gap-1.5">
                {screening.markers_found.map((marker) => (
                  <li key={marker}>
                    <Badge variant="destructiveOutline" className="font-mono">
                      {marker}
                    </Badge>
                  </li>
                ))}
              </ul>
            </div>
          </>
        ) : null}

        {screening.verdict === null ? (
          <>
            <Separator />
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-xs text-muted-foreground">
                La couche 2 appelle un classifieur isolé, sans outil ni donnée de police.
              </p>
              <Button
                variant="outline"
                size="sm"
                onClick={executerFiltreComplet}
                disabled={enCours}
              >
                {enCours ? (
                  <LoaderCircle className="animate-spin" aria-hidden="true" />
                ) : null}
                Exécuter le filtre complet
              </Button>
            </div>
          </>
        ) : null}
      </CardContent>
    </Card>
  );
}
