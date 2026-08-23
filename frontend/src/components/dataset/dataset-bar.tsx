"use client";

import { FileSpreadsheet, LoaderCircle, RefreshCw, TriangleAlert } from "lucide-react";
import { useRouter } from "next/navigation";
import * as React from "react";
import { toast } from "sonner";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { clearDataset } from "@/lib/api-client";
import { devWarn } from "@/lib/dev-log";
import type { DatasetState, LigneRejetee } from "@/lib/types";

/**
 * Rappel des fichiers en cours d'utilisation, avec le moyen d'en changer.
 *
 * Sans cette ligne, rien ne distinguerait a l'ecran deux jeux de dossiers
 * differents, et on pourrait travailler des heures sur le mauvais fichier.
 */
/** Au-dela, la liste devient un mur de texte qu'on ne lit plus. Le compte
 *  total reste annonce dans le titre. */
const REJETS_AFFICHES = 8;

/**
 * Lignes que l'application n'a pas su lire dans les fichiers deposes.
 *
 * Cet encart est la contrepartie visible d'un defaut qui, longtemps, n'en
 * avait aucune : ces lignes etaient jetees en silence. Le gestionnaire
 * travaillait alors sur un fichier ampute en croyant l'avoir charge en
 * entier. On lui donne donc le numero de ligne de son tableur et la raison,
 * pour qu'il puisse corriger et redeposer.
 */
function LignesRejetees({ rejets }: { rejets: LigneRejetee[] }) {
  const visibles = rejets.slice(0, REJETS_AFFICHES);
  const reste = rejets.length - visibles.length;

  return (
    <Alert variant="destructive">
      <TriangleAlert aria-hidden="true" />
      <AlertTitle>
        {rejets.length} ligne(s) de vos fichiers n&apos;ont pas pu être lues
      </AlertTitle>
      <AlertDescription className="space-y-2">
        <p>
          Ces lignes ne figurent pas dans la file d&apos;attente. Corrigez-les dans
          vos fichiers, puis rechargez-les avec « Changer de fichiers ».
        </p>
        <ul className="space-y-1">
          {visibles.map((rejet) => (
            <li key={`${rejet.fichier}-${rejet.ligne}`}>
              <span className="font-medium">
                {rejet.fichier === "contrats" ? "Contrats" : "Déclarations"}, ligne{" "}
                {rejet.ligne}
                {rejet.identifiant ? ` (${rejet.identifiant})` : ""}
              </span>{" "}
              — {rejet.raison}
            </li>
          ))}
        </ul>
        {reste > 0 ? <p>et {reste} autre(s).</p> : null}
      </AlertDescription>
    </Alert>
  );
}

export function DatasetBar({ state }: { state: DatasetState }) {
  const router = useRouter();
  const [enCours, setEnCours] = React.useState(false);
  // `?? []` volontaire : un backend demarre avant cette version ne renvoie pas
  // encore le champ, et l'accueil ne doit pas tomber pour autant.
  const rejets = state.lignes_rejetees ?? [];

  async function changer() {
    setEnCours(true);
    try {
      await clearDataset();
      toast.success("Dossiers retirés. Chargez de nouveaux fichiers.");
      router.refresh();
    } catch (e) {
      devWarn("retrait du jeu de données", e);
      toast.error("Le retrait des dossiers a échoué.");
    } finally {
      setEnCours(false);
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border bg-muted/30 px-4 py-2.5 text-sm">
        <span className="flex items-center gap-1.5 text-muted-foreground">
          <FileSpreadsheet className="size-4" aria-hidden="true" />
          Fichiers chargés
        </span>
        <span className="truncate font-medium">{state.claims_filename}</span>
        <span className="truncate font-medium">{state.policies_filename}</span>
        <Button
          variant="ghost"
          size="sm"
          onClick={changer}
          disabled={enCours}
          className="ml-auto"
        >
          {enCours ? (
            <LoaderCircle className="animate-spin" aria-hidden="true" />
          ) : (
            <RefreshCw aria-hidden="true" />
          )}
          Changer de fichiers
        </Button>
      </div>

      {rejets.length > 0 ? <LignesRejetees rejets={rejets} /> : null}

      {state.claims_sans_contrat.length > 0 ? (
        <Alert>
          <TriangleAlert aria-hidden="true" />
          <AlertTitle>
            {state.claims_sans_contrat.length} déclaration(s) sans contrat correspondant
          </AlertTitle>
          <AlertDescription>
            Ces dossiers ne pourront pas être analysés tant que leur contrat ne figure pas
            dans le fichier des contrats : {state.claims_sans_contrat.join(", ")}.
          </AlertDescription>
        </Alert>
      ) : null}
    </div>
  );
}
