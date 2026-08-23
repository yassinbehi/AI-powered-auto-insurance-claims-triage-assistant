"use client";

import { FileSpreadsheet, LoaderCircle, TriangleAlert, Upload } from "lucide-react";
import { useRouter } from "next/navigation";
import * as React from "react";
import { toast } from "sonner";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { uploadDataset } from "@/lib/api-client";
import { devWarn } from "@/lib/dev-log";

/**
 * Ecran de depart : l'application n'a aucune donnee tant que l'utilisateur
 * n'a pas fourni ses deux fichiers.
 *
 * Les deux sont demandes ensemble parce qu'ils vont ensemble : une
 * declaration renvoie a un contrat, et sans le fichier des contrats il n'y a
 * rien a verifier.
 */

const COLONNES_DECLARATIONS = [
  "claim_id",
  "policy_id",
  "date_sinistre",
  "type_sinistre",
  "description_client",
  "blessure",
  "constat",
  "photos",
  "devis_tnd",
  "tiers_identifie",
  "kilometrage_declare",
];

const COLONNES_CONTRATS = [
  "policy_id",
  "assure",
  "vehicule",
  "formule",
  "date_debut",
  "date_fin",
  "franchise_tnd",
  "garanties",
  "exclusions",
];

function ChampFichier({
  id,
  label,
  colonnes,
  fichier,
  onChange,
}: {
  id: string;
  label: string;
  colonnes: string[];
  fichier: File | null;
  onChange: (file: File | null) => void;
}) {
  return (
    <div className="space-y-2">
      <label htmlFor={id} className="block text-sm font-medium">
        {label}
      </label>
      <input
        id={id}
        type="file"
        accept=".csv,text/csv"
        onChange={(e) => onChange(e.target.files?.[0] ?? null)}
        className="block w-full cursor-pointer rounded-md border border-input bg-background text-sm file:mr-3 file:cursor-pointer file:border-0 file:bg-muted file:px-3 file:py-2 file:text-sm file:font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
      />
      {fichier ? (
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <FileSpreadsheet className="size-3.5" aria-hidden="true" />
          {fichier.name}
        </p>
      ) : (
        <p className="text-xs text-muted-foreground">
          Colonnes attendues : {colonnes.join(", ")}
        </p>
      )}
    </div>
  );
}

export function DatasetUpload() {
  const router = useRouter();
  const [claimsFile, setClaimsFile] = React.useState<File | null>(null);
  const [policiesFile, setPoliciesFile] = React.useState<File | null>(null);
  const [envoiEnCours, setEnvoiEnCours] = React.useState(false);
  const [erreur, setErreur] = React.useState<string | null>(null);

  const pret = claimsFile !== null && policiesFile !== null;

  async function envoyer(event: React.FormEvent) {
    event.preventDefault();
    if (!claimsFile || !policiesFile) return;

    setEnvoiEnCours(true);
    setErreur(null);
    try {
      const etat = await uploadDataset(claimsFile, policiesFile);
      toast.success(
        `${etat.claims_count} déclarations et ${etat.policies_count} contrats chargés.`,
      );
      // Le detail des lignes refusees reste affiche en permanence par
      // DatasetBar : ce toast ne fait qu'attirer l'oeil dessus tout de suite,
      // pour que personne ne parte travailler sur un fichier ampute.
      const rejets = etat.lignes_rejetees ?? [];
      if (rejets.length > 0) {
        toast.warning(
          `${rejets.length} ligne(s) n'ont pas pu être lues et ne sont pas dans la file.`,
        );
      }
      if (etat.claims_sans_contrat.length > 0) {
        toast.warning(
          `${etat.claims_sans_contrat.length} déclaration(s) renvoient à un contrat absent du fichier.`,
        );
      }
      router.refresh();
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      devWarn("dépôt du jeu de données", e);
      setErreur(message);
    } finally {
      setEnvoiEnCours(false);
    }
  }

  return (
    <Card className="mx-auto w-full max-w-2xl">
      <CardHeader>
        <CardTitle>Chargez vos dossiers</CardTitle>
        <p className="text-sm text-muted-foreground">
          L&apos;application ne contient aucune donnée. Fournissez le fichier des
          déclarations et celui des contrats pour commencer.
        </p>
      </CardHeader>

      <CardContent>
        <form onSubmit={envoyer} className="space-y-6">
          <ChampFichier
            id="claims-file"
            label="Fichier des déclarations (CSV)"
            colonnes={COLONNES_DECLARATIONS}
            fichier={claimsFile}
            onChange={setClaimsFile}
          />
          <ChampFichier
            id="policies-file"
            label="Fichier des contrats (CSV)"
            colonnes={COLONNES_CONTRATS}
            fichier={policiesFile}
            onChange={setPoliciesFile}
          />

          {erreur ? (
            <Alert variant="destructive">
              <TriangleAlert aria-hidden="true" />
              <AlertTitle>Fichier refusé</AlertTitle>
              <AlertDescription>{erreur}</AlertDescription>
            </Alert>
          ) : null}

          <Button type="submit" disabled={!pret || envoiEnCours}>
            {envoiEnCours ? (
              <LoaderCircle className="animate-spin" aria-hidden="true" />
            ) : (
              <Upload aria-hidden="true" />
            )}
            Charger les dossiers
          </Button>

          <p className="text-xs text-muted-foreground">
            Les fichiers restent en mémoire le temps de la session et ne sont pas
            enregistrés sur le serveur. Après un redémarrage, il faut les redéposer.
          </p>
        </form>
      </CardContent>
    </Card>
  );
}
