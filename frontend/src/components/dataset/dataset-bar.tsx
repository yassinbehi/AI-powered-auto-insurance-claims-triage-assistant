"use client";

import { FileSpreadsheet, LoaderCircle, RefreshCw, TriangleAlert } from "lucide-react";
import { useRouter } from "next/navigation";
import * as React from "react";
import { toast } from "sonner";

import { DatasetSwitcher } from "@/components/dataset/dataset-switcher";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { clearDataset } from "@/lib/api-client";
import { devWarn } from "@/lib/dev-log";
import type { DatasetResume, DatasetState, LigneRejetee } from "@/lib/types";

/**
 * Rappel du jeu de donnees en cours d'utilisation, avec le moyen d'en changer.
 *
 * Sans cette ligne, rien ne distinguerait a l'ecran deux jeux de dossiers
 * differents, et on pourrait travailler des heures sur le mauvais. C'est le
 * NOM qui porte cette distinction depuis que les jeux sont conserves : deux
 * fichiers appeles claims.csv se ressemblent trop pour la porter seuls.
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
          vos fichiers, puis redéposez-les avec « Déposer d&apos;autres fichiers ».
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

export function DatasetBar({
  state,
  datasets,
}: {
  state: DatasetState;
  /** Tous les jeux enregistres, pour le selecteur. */
  datasets: DatasetResume[];
}) {
  const router = useRouter();
  const [enCours, setEnCours] = React.useState(false);
  // `?? []` volontaire : un backend demarre avant cette version ne renvoie pas
  // encore le champ, et l'accueil ne doit pas tomber pour autant.
  const rejets = state.lignes_rejetees ?? [];

  /** Ferme le jeu ouvert et revient a l'ecran de depot. NE SUPPRIME RIEN :
   *  le jeu reste dans la liste et se rouvre d'un clic. */
  async function fermer() {
    setEnCours(true);
    try {
      await clearDataset();
      toast.success("Jeu fermé. Il reste enregistré et peut être rouvert.");
      router.refresh();
    } catch (e) {
      devWarn("fermeture du jeu de données", e);
      toast.error("La fermeture du jeu a échoué.");
    } finally {
      setEnCours(false);
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border bg-muted/30 px-4 py-2.5 text-sm">
        <span className="flex items-center gap-1.5 text-muted-foreground">
          <FileSpreadsheet className="size-4" aria-hidden="true" />
          Jeu ouvert
        </span>
        {/* Le nom d'abord : c'est lui que l'utilisateur a choisi et qu'il
            reconnait. Les noms de fichiers suivent, en retrait, pour qui veut
            verifier ce qui a ete depose. */}
        <span className="truncate font-medium">{state.nom}</span>
        <span className="truncate text-xs text-muted-foreground">
          {state.claims_filename} · {state.policies_filename}
        </span>

        <div className="ml-auto flex items-center gap-1">
          <DatasetSwitcher datasets={datasets} />
          <Button variant="ghost" size="sm" onClick={fermer} disabled={enCours}>
            {enCours ? (
              <LoaderCircle className="animate-spin" aria-hidden="true" />
            ) : (
              <RefreshCw aria-hidden="true" />
            )}
            Déposer d&apos;autres fichiers
          </Button>
        </div>
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
