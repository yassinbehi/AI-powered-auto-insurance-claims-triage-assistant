"use client";

import { Download, FileSpreadsheet, LoaderCircle, TriangleAlert, Upload } from "lucide-react";
import { useRouter } from "next/navigation";
import * as React from "react";
import { toast } from "sonner";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { uploadDataset } from "@/lib/api-client";
import { devWarn } from "@/lib/dev-log";
import { cn } from "@/lib/utils";

/**
 * Ecran de depart : l'application n'a aucune donnee tant que l'utilisateur
 * n'a pas fourni ses deux fichiers.
 *
 * Les deux sont demandes ensemble parce qu'ils vont ensemble : une
 * declaration renvoie a un contrat, et sans le fichier des contrats il n'y a
 * rien a verifier.
 *
 * UN NOM EST DEMANDE AVEC LES FICHIERS. Les jeux deposes sont conserves et
 * l'utilisateur passe de l'un a l'autre : sans nom, il choisirait entre
 * plusieurs lignes "claims.csv" identiques. Le champ est en tete du
 * formulaire, avant les fichiers, parce qu'il decrit ce qu'on est en train de
 * constituer.
 */

/** Meme limite que dataset_db.NOM_LONGUEUR_MAX cote Python. Le backend
 *  revalide de toute facon : ceci n'est qu'une courtoisie de saisie. */
const NOM_LONGUEUR_MAX = 60;

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

/**
 * Fichiers d'exemple, generes cote navigateur.
 *
 * Ils donnent un gabarit VALIDE tout de suite : bon en-tete, bon encodage
 * (UTF-8), et le meme separateur `;` pour les listes (garanties, exclusions)
 * que celui attendu par la lecture. Un utilisateur qui doute du format part
 * d'un fichier qui marche plutot que de deviner.
 */
const EXEMPLE_DECLARATIONS = [
  COLONNES_DECLARATIONS.join(","),
  'CLM-001,POL-001,2026-07-18,collision,"Choc arrière à un feu rouge, le tiers a signé le constat.",non,oui,oui,2400,oui,48200',
  'CLM-002,POL-002,2026-08-05,bris_glace,"Pare-brise fissuré sur autoroute.",non,non,oui,850,non,31200',
].join("\r\n");

const EXEMPLE_CONTRATS = [
  COLONNES_CONTRATS.join(","),
  "POL-001,Amira Ben Salah,Peugeot 208,tous_risques,2025-02-01,2027-02-01,350,rc;collision;bris_glace;vol,alcool;course",
  "POL-002,Youssef Trabelsi,Renault Clio,tiers_plus,2025-07-15,2027-07-15,500,rc;bris_glace;vol,conducteur_non_declare",
].join("\r\n");

/** Telecharge une chaine comme fichier, sans passer par le serveur. */
function telechargerExemple(nom: string, contenu: string) {
  const blob = new Blob([contenu], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const lien = document.createElement("a");
  lien.href = url;
  lien.download = nom;
  lien.click();
  URL.revokeObjectURL(url);
}

function ChampFichier({
  id,
  label,
  colonnes,
  fichier,
  onChange,
  exempleNom,
  exempleContenu,
}: {
  id: string;
  label: string;
  colonnes: string[];
  fichier: File | null;
  onChange: (file: File | null) => void;
  exempleNom: string;
  exempleContenu: string;
}) {
  const [survol, setSurvol] = React.useState(false);

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <label htmlFor={id} className="block text-sm font-medium">
          {label}
        </label>
        <Button
          type="button"
          variant="link"
          size="sm"
          className="h-auto gap-1 p-0 text-xs"
          onClick={() => telechargerExemple(exempleNom, exempleContenu)}
        >
          <Download className="size-3.5" aria-hidden="true" />
          Télécharger un exemple
        </Button>
      </div>

      {/* Zone de depot : le survol d'un fichier l'eclaire, et le clic ouvre le
          selecteur natif (le meme input, en fallback clavier/souris). */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setSurvol(true);
        }}
        onDragLeave={() => setSurvol(false)}
        onDrop={(e) => {
          e.preventDefault();
          setSurvol(false);
          const depose = e.dataTransfer.files?.[0];
          if (depose) onChange(depose);
        }}
        className={cn(
          "rounded-lg border border-dashed p-3 transition-colors",
          survol ? "border-ring bg-muted/50" : "border-input",
        )}
      >
        <input
          id={id}
          type="file"
          accept=".csv,text/csv"
          onChange={(e) => onChange(e.target.files?.[0] ?? null)}
          className="block w-full cursor-pointer rounded-md bg-background text-sm file:mr-3 file:cursor-pointer file:border-0 file:bg-muted file:px-3 file:py-2 file:text-sm file:font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
        />
        <p className="mt-2 text-xs text-muted-foreground">
          Glissez le fichier CSV ici, ou parcourez avec le bouton ci-dessus.
        </p>
      </div>

      {fichier ? (
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <FileSpreadsheet className="size-3.5" aria-hidden="true" />
          {fichier.name}
        </p>
      ) : (
        <div className="space-y-1">
          <p className="text-xs text-muted-foreground">Colonnes attendues :</p>
          <div className="flex flex-wrap gap-1">
            {colonnes.map((colonne) => (
              <code
                key={colonne}
                className="rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground"
              >
                {colonne}
              </code>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function DatasetUpload() {
  const router = useRouter();
  const [nom, setNom] = React.useState("");
  const [claimsFile, setClaimsFile] = React.useState<File | null>(null);
  const [policiesFile, setPoliciesFile] = React.useState<File | null>(null);
  const [envoiEnCours, setEnvoiEnCours] = React.useState(false);
  const [erreur, setErreur] = React.useState<string | null>(null);

  const nomPropre = nom.trim();
  const pret = nomPropre !== "" && claimsFile !== null && policiesFile !== null;

  async function envoyer(event: React.FormEvent) {
    event.preventDefault();
    if (!pret || !claimsFile || !policiesFile) return;

    setEnvoiEnCours(true);
    setErreur(null);
    try {
      const etat = await uploadDataset(nomPropre, claimsFile, policiesFile);
      toast.success(
        `« ${etat.nom} » chargé : ${etat.claims_count} déclarations et ` +
          `${etat.policies_count} contrats.`,
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
          <div className="space-y-2">
            <label htmlFor="dataset-nom" className="block text-sm font-medium">
              Nom de ce jeu de données
            </label>
            <Input
              id="dataset-nom"
              value={nom}
              onChange={(e) => setNom(e.target.value)}
              maxLength={NOM_LONGUEUR_MAX}
              placeholder="Sinistres juillet 2026"
              autoComplete="off"
              // Le bouton d'envoi reste desactive tant que le champ est vide ;
              // `required` double la regle pour la validation native et les
              // technologies d'assistance.
              required
            />
            <p className="text-xs text-muted-foreground">
              Ce nom vous servira à retrouver ces dossiers et à revenir dessus
              plus tard. Deux jeux ne peuvent pas porter le même nom.
            </p>
          </div>

          <ChampFichier
            id="claims-file"
            label="Fichier des déclarations (CSV)"
            colonnes={COLONNES_DECLARATIONS}
            fichier={claimsFile}
            onChange={setClaimsFile}
            exempleNom="declarations-exemple.csv"
            exempleContenu={EXEMPLE_DECLARATIONS}
          />
          <ChampFichier
            id="policies-file"
            label="Fichier des contrats (CSV)"
            colonnes={COLONNES_CONTRATS}
            fichier={policiesFile}
            onChange={setPoliciesFile}
            exempleNom="contrats-exemple.csv"
            exempleContenu={EXEMPLE_CONTRATS}
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
            Les dossiers sont enregistrés sur cette machine et restent
            disponibles après un redémarrage. Vous pourrez passer d&apos;un jeu à
            l&apos;autre, ou supprimer celui-ci depuis la file d&apos;attente.
          </p>
        </form>
      </CardContent>
    </Card>
  );
}
